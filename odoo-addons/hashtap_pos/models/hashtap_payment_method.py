from odoo import api, fields, models


METHOD_CODES = [
    ("card", "Kredi/Banka Kartı (3DS)"),
    ("apple_pay", "Apple Pay"),
    ("google_pay", "Google Pay"),
    ("cash", "Nakit (kasada)"),
    ("pay_at_counter", "Kasada öde (kart/nakit)"),
]

# Hangi metodlar bir sağlayıcı adapter'ı tarafından işlenir, hangileri
# offline (kasada) akıştır — controller buna göre karar verir.
ONLINE_METHODS = {"card", "apple_pay", "google_pay"}


class HashtapPaymentMethod(models.Model):
    _name = "hashtap.payment.method"
    _description = "HashTap Payment Method"
    _order = "sequence, id"

    name = fields.Char(string="Görünen Ad", required=True)
    code = fields.Selection(METHOD_CODES, string="Kod", required=True)
    provider_id = fields.Many2one(
        "hashtap.payment.provider",
        string="Sağlayıcı",
        ondelete="set null",
        help="Online ödeme yöntemleri için bir sağlayıcı bağlanmalı. "
             "Kasada ödeme için boş bırakılabilir.",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    min_amount_kurus = fields.Integer(
        string="Min. Tutar (kuruş)",
        default=0,
        help="Bu tutarın altında sepetlerde bu yöntem listelenmez.",
    )
    icon = fields.Char(
        string="İkon",
        help="PWA'da gösterilecek lucide-react ikon adı (ör. 'credit-card').",
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )

    _sql_constraints = [
        (
            "unique_method_per_company",
            "unique(code, company_id)",
            "Her yöntem şirket başına tek kez tanımlanabilir.",
        ),
    ]

    @api.model
    def list_for_tenant(self, company=None, amount_kurus=0):
        """PWA için aktif metodları dön."""
        company = company or self.env.company
        methods = self.search(
            [
                ("company_id", "=", company.id),
                ("active", "=", True),
                ("min_amount_kurus", "<=", amount_kurus),
            ],
            order="sequence, id",
        )
        return [
            {
                "code": m.code,
                "name": m.name,
                "icon": m.icon or "",
                "is_online": m.code in ONLINE_METHODS,
            }
            for m in methods
            if m.code not in ONLINE_METHODS or (m.provider_id and m.provider_id.active)
        ]
