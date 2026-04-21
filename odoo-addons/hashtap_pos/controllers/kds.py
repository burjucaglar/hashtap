"""KDS (Kitchen Display System) — mutfak personeli için canlı sipariş paneli.

Arayüz: HashTap markalı, tam ekran, touch-optimized.
  - /hashtap/kds                  → HTML sayfası
  - /hashtap/kds/orders.json      → aktif siparişler (polling)
  - /hashtap/kds/order/<id>/advance → durum ilerlet

Erişim: auth="user" — restoran içi çalışan tableti Odoo'da login kalır.
Mutfak tableti için ayrı bir "kitchen" grup kullanıcısı yaratılabilir
(faz 8 ile). Şimdilik standart internal user yeterli.
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


# order.state → KDS kolonu eşleşmesi.
_KDS_COLUMN = {
    "kitchen_sent": "new",
    "preparing": "preparing",
    "ready": "ready",
}

# "Servis edildi" olarak işaretlenenleri KDS'den düşürmek için
# ready kolonunda gösterim süresi — bu süreden eski ready siparişler
# hâlâ görünür, garsonun kaçırmasını önler.
# (Servis edildi butonuna basılana kadar ekranda kalır.)


def _serialize_kds_order(order):
    lines = []
    for line in order.line_ids:
        lines.append({
            "item_name": line.item_name,
            "quantity": line.quantity,
            "note": line.note or "",
            "modifier_names": line.modifier_ids.mapped("name_tr"),
        })
    return {
        "id": order.id,
        "reference": order.name,
        "table": order.table_id.name or order.table_slug or "",
        "column": _KDS_COLUMN.get(order.state, "new"),
        "state": order.state,
        "customer_note": order.customer_note or "",
        "lines": lines,
        "total_kurus": order.total_kurus,
        "currency": order.currency,
        "fired_at": (
            order.kitchen_fired_at.isoformat() if order.kitchen_fired_at else None
        ),
        "ready_at": order.ready_at.isoformat() if order.ready_at else None,
    }


class HashTapKDS(http.Controller):

    @http.route("/hashtap/kds", type="http", auth="user", website=False)
    def kds_page(self, **kw):
        # QWeb XML parser <!DOCTYPE html>'yi template içinde kabul etmiyor;
        # response body'nin başına manuel ekliyoruz.
        response = request.render("hashtap_pos.kds_page", {})
        if hasattr(response, "data") and response.data:
            body = response.data
            if isinstance(body, bytes):
                response.data = b"<!DOCTYPE html>\n" + body
            else:
                response.data = "<!DOCTYPE html>\n" + body
        return response

    @http.route(
        "/hashtap/kds/orders.json",
        type="json", auth="user", methods=["POST"], csrf=False,
    )
    def kds_orders(self, **kw):
        Order = request.env["hashtap.order"].sudo()
        orders = Order.search(
            [("state", "in", ["kitchen_sent", "preparing", "ready"])],
            order="kitchen_fired_at asc, id asc",
        )
        return {"orders": [_serialize_kds_order(o) for o in orders]}

    @http.route(
        "/hashtap/kds/order/<int:order_id>/advance",
        type="json", auth="user", methods=["POST"], csrf=False,
    )
    def kds_advance(self, order_id, **kw):
        """Bir sonraki duruma ilerlet.

        kitchen_sent → preparing → ready → served
        """
        order = request.env["hashtap.order"].sudo().browse(order_id)
        if not order.exists():
            return {"ok": False, "error": "not_found"}

        transitions = {
            "kitchen_sent": ("action_mark_preparing", "preparing"),
            "preparing": ("action_mark_ready", "ready"),
            "ready": ("action_mark_served", "served"),
        }
        step = transitions.get(order.state)
        if not step:
            return {"ok": False, "error": "invalid_state", "state": order.state}

        method_name, _expected = step
        getattr(order, method_name)()
        return {"ok": True, "state": order.state}

    @http.route(
        "/hashtap/kds/order/<int:order_id>/recall",
        type="json", auth="user", methods=["POST"], csrf=False,
    )
    def kds_recall(self, order_id, **kw):
        """Geri al: ready → preparing veya preparing → kitchen_sent.

        Garson yanlış "hazır" bastıysa kurtarma yolu.
        """
        order = request.env["hashtap.order"].sudo().browse(order_id)
        if not order.exists():
            return {"ok": False, "error": "not_found"}
        reverse = {"ready": "preparing", "preparing": "kitchen_sent"}
        prev = reverse.get(order.state)
        if not prev:
            return {"ok": False, "error": "cannot_recall", "state": order.state}
        order.state = prev
        if prev != "ready":
            order.ready_at = False
        return {"ok": True, "state": order.state}
