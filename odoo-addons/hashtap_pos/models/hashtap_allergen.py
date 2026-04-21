from odoo import fields, models


class HashtapAllergen(models.Model):
    _name = "hashtap.allergen"
    _description = "HashTap Allergen"
    _order = "name_tr"

    name_tr = fields.Char(string="Alerjen (TR)", required=True)
    name_en = fields.Char(string="Allergen (EN)", required=True)
    code = fields.Char(
        required=True,
        help="URL-safe kısa kod (örn: gluten, sesame). API yanıtında kullanılır.",
    )
    icon = fields.Char(help="Emoji veya simge kodu")

    _sql_constraints = [
        ("unique_code", "unique(code)", "Alerjen kodu benzersiz olmalı."),
    ]
