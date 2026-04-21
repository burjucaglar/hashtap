from odoo import fields, models


class HashtapModifier(models.Model):
    _name = "hashtap.modifier"
    _description = "HashTap Modifier Option"
    _order = "group_id, sequence, id"

    group_id = fields.Many2one(
        "hashtap.modifier.group", required=True, ondelete="cascade"
    )
    name_tr = fields.Char(string="Seçenek (TR)", required=True)
    name_en = fields.Char(string="Option (EN)", required=True)
    price_delta = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )
    linked_product_id = fields.Many2one(
        "product.product",
        string="Bağlı Ürün",
        help="Seçilirse bu ürün stoktan düşer (opsiyonel).",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
