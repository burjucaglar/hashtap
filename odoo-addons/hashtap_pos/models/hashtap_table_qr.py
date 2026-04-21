import base64
import secrets

from odoo import api, fields, models


BASE32_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"
SLUG_LENGTH = 8


def _generate_slug():
    return "".join(secrets.choice(BASE32_ALPHABET) for _ in range(SLUG_LENGTH))


class RestaurantTable(models.Model):
    _inherit = "restaurant.table"

    hashtap_qr_slug = fields.Char(
        string="QR Slug",
        size=32,
        index=True,
        copy=False,
        readonly=True,
        help="URL-safe kısa tanımlayıcı. Masa oluşturulurken üretilir, değişmez.",
    )
    hashtap_qr_url = fields.Char(
        string="QR URL",
        compute="_compute_hashtap_qr_url",
    )
    hashtap_enabled = fields.Boolean(
        string="QR Akışı Açık",
        default=True,
        help="Kapalıysa bu masaya QR'dan sipariş verilemez.",
    )

    _sql_constraints = [
        (
            "unique_hashtap_qr_slug",
            "unique(hashtap_qr_slug)",
            "QR slug benzersiz olmalı.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("hashtap_qr_slug"):
                vals["hashtap_qr_slug"] = self._generate_unique_slug()
        return super().create(vals_list)

    def _generate_unique_slug(self):
        for _ in range(8):
            candidate = _generate_slug()
            exists = self.sudo().search_count(
                [("hashtap_qr_slug", "=", candidate)]
            )
            if not exists:
                return candidate
        raise RuntimeError("QR slug üretilemedi — 8 deneme sonrası çakışma.")

    @api.depends("hashtap_qr_slug")
    def _compute_hashtap_qr_url(self):
        icp = self.env["ir.config_parameter"].sudo()
        base = icp.get_param("hashtap.pwa_base_url", "https://example.com")
        tenant = icp.get_param("hashtap.tenant_slug", "default")
        for rec in self:
            if rec.hashtap_qr_slug:
                rec.hashtap_qr_url = (
                    f"{base.rstrip('/')}/r/{tenant}/t/{rec.hashtap_qr_slug}"
                )
            else:
                rec.hashtap_qr_url = False
