from odoo import api, fields, models


class HashtapModifierGroup(models.Model):
    _name = "hashtap.modifier.group"
    _description = "HashTap Modifier Group"
    _order = "sequence, id"

    name_tr = fields.Char(string="Grup (TR)", required=True)
    name_en = fields.Char(string="Group (EN)", required=True)
    min_select = fields.Integer(default=0)
    max_select = fields.Integer(default=1, help="0 = sınırsız")
    is_required = fields.Boolean(compute="_compute_is_required", store=True)
    modifier_ids = fields.One2many(
        "hashtap.modifier", "group_id", string="Seçenekler"
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    @api.depends("min_select")
    def _compute_is_required(self):
        for rec in self:
            rec.is_required = rec.min_select > 0
