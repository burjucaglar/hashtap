from odoo import http
from odoo.http import request


def _price_to_kurus(amount):
    return int(round(float(amount or 0) * 100))


def _vat_rate_percent(taxes):
    """Tek bir KDV oranı çıkar. Bileşik vergilerde ilk non-zero'yu alır.

    Odoo'nun tax sistemini sadeleştirerek PWA'ya sade bir yüzde döndürür;
    karmaşık birden fazla vergi senaryosu Faz 4 kapsamı.
    """
    for tax in taxes:
        if tax.amount_type == "percent" and tax.amount:
            return tax.amount
    return 0


def _serialize_modifier(m, lang):
    return {
        "id": m.id,
        "name": {"tr": m.name_tr, "en": m.name_en},
        "price_delta_kurus": _price_to_kurus(m.price_delta),
    }


def _serialize_modifier_group(g, lang):
    return {
        "id": g.id,
        "name": {"tr": g.name_tr, "en": g.name_en},
        "min_select": g.min_select,
        "max_select": g.max_select,
        "modifiers": [_serialize_modifier(m, lang) for m in g.modifier_ids if m.active],
    }


def _serialize_item(item, lang):
    return {
        "id": item.id,
        "name": {"tr": item.name_tr, "en": item.name_en},
        "description": {"tr": item.description_tr or "", "en": item.description_en or ""},
        "image_url": (
            f"/web/image/hashtap.menu.item/{item.id}/image" if item.image else None
        ),
        "price_kurus": _price_to_kurus(item.price_display),
        "currency": item.currency_id.name or "TRY",
        "vat_rate": _vat_rate_percent(item.taxes_id),
        "allergens": [a.code for a in item.allergen_ids],
        "dietary": [item.dietary_tag] if item.dietary_tag and item.dietary_tag != "none" else [],
        "prep_time_minutes": item.prep_time_minutes,
        "is_featured": item.is_featured,
        "modifier_groups": [
            _serialize_modifier_group(g, lang) for g in item.modifier_group_ids if g.active
        ],
    }


def _serialize_category(cat, lang):
    return {
        "id": cat.id,
        "name": {"tr": cat.name_tr, "en": cat.name_en},
        "sequence": cat.sequence,
        "items": [_serialize_item(i, lang) for i in cat.item_ids if i.active],
    }


class HashTapMenu(http.Controller):
    """Public menu endpoint consumed by the customer PWA (via gateway).

    Single-tenant MVP: tenant_slug is validated against the
    `hashtap.tenant_slug` config parameter. Multi-tenant routing is the
    gateway's responsibility (Faz 7).
    """

    @http.route(
        "/hashtap/menu/<string:tenant_slug>/<string:table_slug>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_menu(self, tenant_slug, table_slug, **kw):
        icp = request.env["ir.config_parameter"].sudo()
        expected_tenant = icp.get_param("hashtap.tenant_slug", "default")

        if tenant_slug != expected_tenant:
            return request.make_json_response(
                {"error": "tenant_not_found"}, status=404
            )

        table = (
            request.env["restaurant.table"]
            .sudo()
            .search(
                [
                    ("hashtap_qr_slug", "=", table_slug),
                    ("hashtap_enabled", "=", True),
                    ("active", "=", True),
                ],
                limit=1,
            )
        )
        if not table:
            return request.make_json_response(
                {"error": "table_not_found"}, status=404
            )

        lang = (kw.get("lang") or "tr").lower()
        if lang not in ("tr", "en"):
            lang = "tr"

        company = request.env.company
        categories = (
            request.env["hashtap.menu.category"]
            .sudo()
            .search([("active", "=", True)], order="sequence, id")
        )

        payload = {
            "tenant": {
                "slug": tenant_slug,
                "name": company.name,
                "currency": company.currency_id.name,
                "language": lang,
            },
            "table": {
                "slug": table.hashtap_qr_slug,
                "label": table.name,
            },
            "categories": [
                _serialize_category(c, lang) for c in categories if c.item_ids
            ],
        }
        return request.make_json_response(payload)
