from odoo import api, fields, models
from odoo.exceptions import ValidationError


DIETARY_SELECTION = [
    ("none", "Standart"),
    ("vegan", "Vegan"),
    ("vegetarian", "Vejetaryen"),
    ("halal", "Helal"),
]


class HashtapMenuItem(models.Model):
    _name = "hashtap.menu.item"
    _description = "HashTap QR Menu Item"
    _inherit = ["mail.thread"]
    _order = "category_id, sequence, id"

    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Ürün",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    category_id = fields.Many2one(
        "hashtap.menu.category", string="Kategori", required=True, tracking=True
    )
    name_tr = fields.Char(string="Menü Adı (TR)", required=True, tracking=True)
    name_en = fields.Char(string="Menu Name (EN)", required=True, tracking=True)
    description_tr = fields.Text(string="Açıklama (TR)")
    description_en = fields.Text(string="Description (EN)")
    image = fields.Binary(string="Fotoğraf")
    allergen_ids = fields.Many2many(
        "hashtap.allergen", string="Alerjenler"
    )
    dietary_tag = fields.Selection(DIETARY_SELECTION, default="none")
    prep_time_minutes = fields.Integer(string="Hazırlık (dk)")
    is_featured = fields.Boolean(string="Öne Çıkan")
    sequence = fields.Integer(default=10)
    modifier_group_ids = fields.Many2many(
        "hashtap.modifier.group", string="Modifier Grupları"
    )
    price_display = fields.Float(
        related="product_tmpl_id.list_price",
        string="Fiyat",
        digits="Product Price",
        readonly=True,
    )
    currency_id = fields.Many2one(
        related="product_tmpl_id.currency_id", readonly=True, store=True
    )
    taxes_id = fields.Many2many(
        related="product_tmpl_id.taxes_id", string="Vergiler", readonly=True
    )
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, required=True
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "unique_product_tmpl",
            "unique(product_tmpl_id)",
            "Bu ürün başka bir menü kaleminde kullanılıyor.",
        ),
    ]

    @api.constrains("product_tmpl_id")
    def _check_product_type(self):
        for rec in self:
            if rec.product_tmpl_id.detailed_type not in ("product", "consu"):
                raise ValidationError(
                    "Menüye sadece stoklanan veya sarf ürün eklenebilir (servis değil)."
                )
