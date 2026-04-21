from odoo import api, fields, models


class HashtapMenuCategory(models.Model):
    _name = "hashtap.menu.category"
    _description = "HashTap QR Menu Category"
    _inherit = ["mail.thread"]
    _order = "sequence, id"

    name_tr = fields.Char(string="Ad (TR)", required=True, tracking=True)
    name_en = fields.Char(string="Name (EN)", required=True, tracking=True)
    sequence = fields.Integer(default=10)
    icon = fields.Binary(string="İkon")
    item_ids = fields.One2many(
        "hashtap.menu.item", "category_id", string="Kalemler"
    )
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, required=True
    )
    active = fields.Boolean(default=True)
    available_from = fields.Float(help="Gün saati başlangıcı. Boşsa tüm gün.")
    available_to = fields.Float(help="Gün saati bitişi. Boşsa tüm gün.")

    @api.constrains("available_from", "available_to")
    def _check_time_window(self):
        for rec in self:
            if rec.available_from and rec.available_to and rec.available_from >= rec.available_to:
                raise models.ValidationError(
                    "Kategori başlangıç saati bitişten önce olmalı."
                )
