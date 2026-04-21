import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


MAX_QUANTITY_PER_LINE = 20
MAX_LINES_PER_ORDER = 50


def _kurus(amount):
    return int(round(float(amount or 0) * 100))


def _json_error(code, status):
    return request.make_json_response({"error": code}, status=status)


def _serialize_order(order):
    return {
        "id": order.id,
        "reference": order.name,
        "state": order.state,
        "payment_state": order.payment_state,
        "payment_method_code": order.payment_method_code or "",
        "paid_amount_kurus": order.paid_amount_kurus,
        "subtotal_kurus": order.subtotal_kurus,
        "total_kurus": order.total_kurus,
        "currency": order.currency,
        "table_slug": order.table_slug,
        "customer_note": order.customer_note or "",
        "created_at": order.create_date.isoformat() if order.create_date else None,
        "lines": [
            {
                "id": line.id,
                "item_id": line.item_id.id,
                "item_name": line.item_name,
                "quantity": line.quantity,
                "unit_price_kurus": line.unit_price_kurus,
                "modifier_total_kurus": line.modifier_total_kurus,
                "subtotal_kurus": line.subtotal_kurus,
                "modifier_ids": line.modifier_ids.ids,
                "note": line.note or "",
            }
            for line in order.line_ids
        ],
    }


class HashTapOrder(http.Controller):
    """Sepet kabul + sipariş durumu sorgusu.

    Fiyat güvenliği: PWA'dan gelen fiyata hiçbir zaman güvenilmez; sunucu her
    kalemi `hashtap.menu.item` ve `hashtap.modifier` kayıtlarından yeniden hesaplar.
    """

    @http.route(
        "/hashtap/order",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def create_order(self, tenant_slug=None, table_slug=None, items=None,
                     customer_note=None, **_kw):
        items_input = items or []
        customer_note = (customer_note or "").strip()[:500]

        icp = request.env["ir.config_parameter"].sudo()
        expected_tenant = icp.get_param("hashtap.tenant_slug", "default")
        if tenant_slug != expected_tenant:
            return {"error": "tenant_not_found"}

        table = request.env["restaurant.table"].sudo().search(
            [
                ("hashtap_qr_slug", "=", table_slug),
                ("hashtap_enabled", "=", True),
                ("active", "=", True),
            ],
            limit=1,
        )
        if not table:
            return {"error": "table_not_found"}

        if not isinstance(items_input, list) or not items_input:
            return {"error": "empty_cart"}
        if len(items_input) > MAX_LINES_PER_ORDER:
            return {"error": "too_many_lines"}

        line_vals = []
        for idx, raw in enumerate(items_input):
            if not isinstance(raw, dict):
                return {"error": "malformed_line", "index": idx}
            item_id = raw.get("item_id")
            quantity = raw.get("quantity", 1)
            modifier_ids = raw.get("modifier_ids") or []
            note = (raw.get("note") or "").strip()[:200]

            if not isinstance(item_id, int) or not isinstance(quantity, int):
                return {"error": "malformed_line", "index": idx}
            if quantity < 1 or quantity > MAX_QUANTITY_PER_LINE:
                return {"error": "invalid_quantity", "index": idx}
            if not isinstance(modifier_ids, list) or not all(
                isinstance(m, int) for m in modifier_ids
            ):
                return {"error": "malformed_line", "index": idx}

            item = request.env["hashtap.menu.item"].sudo().browse(item_id).exists()
            if not item or not item.active:
                return {"error": "item_not_found", "index": idx}

            allowed_modifier_ids = item.modifier_group_ids.mapped("modifier_ids").ids
            for m_id in modifier_ids:
                if m_id not in allowed_modifier_ids:
                    return {"error": "modifier_not_allowed", "index": idx}

            modifiers = (
                request.env["hashtap.modifier"].sudo().browse(modifier_ids)
                if modifier_ids
                else request.env["hashtap.modifier"]
            )
            modifier_total = sum(_kurus(m.price_delta) for m in modifiers if m.active)

            line_vals.append((0, 0, {
                "item_id": item.id,
                "item_name": item.name_tr,
                "quantity": quantity,
                "unit_price_kurus": _kurus(item.price_display),
                "modifier_total_kurus": modifier_total,
                "modifier_ids": [(6, 0, modifiers.ids)],
                "note": note,
            }))

        order = request.env["hashtap.order"].sudo().create({
            "table_id": table.id,
            "customer_note": customer_note,
            "line_ids": line_vals,
        })

        _logger.info(
            "hashtap_order: created %s (table=%s total=%s)",
            order.name, table_slug, order.total_kurus,
        )
        return {"order": _serialize_order(order)}

    @http.route(
        "/hashtap/order/<int:order_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_order(self, order_id, **kw):
        order = request.env["hashtap.order"].sudo().browse(order_id).exists()
        if not order:
            return _json_error("order_not_found", 404)
        return request.make_json_response({"order": _serialize_order(order)})
