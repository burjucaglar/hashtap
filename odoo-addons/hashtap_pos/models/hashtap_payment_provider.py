from odoo import api, fields, models


PROVIDER_CODES = [
    ("iyzico", "iyzico"),
    ("mock", "Mock (dev)"),
]


class HashtapPaymentProvider(models.Model):
    _name = "hashtap.payment.provider"
    _description = "HashTap Payment Provider Configuration"
    _inherit = ["mail.thread"]
    _order = "sequence, id"

    name = fields.Char(string="Ad", required=True)
    code = fields.Selection(
        PROVIDER_CODES,
        string="Sağlayıcı",
        required=True,
        default="iyzico",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    sandbox = fields.Boolean(
        string="Sandbox",
        default=True,
        tracking=True,
        help="İşaretliyken gerçek kart çekimi yapılmaz; test endpoint'leri kullanılır.",
    )
    api_key = fields.Char(string="API Key")
    api_secret = fields.Char(string="API Secret", groups="base.group_system")
    sub_merchant_key = fields.Char(
        string="subMerchant Key",
        help="iyzico facilitator modeli için restoran alt-üye işyeri anahtarı.",
    )
    webhook_secret = fields.Char(
        string="Webhook Secret",
        groups="base.group_system",
        help="Webhook isteklerinin HMAC imzasını doğrulamak için paylaşılan sır.",
    )
    base_url = fields.Char(
        string="Base URL",
        help="Sağlayıcı REST endpoint'i. Boşsa adapter varsayılanı kullanır.",
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    method_ids = fields.One2many(
        "hashtap.payment.method",
        "provider_id",
        string="Ödeme Yöntemleri",
    )
    transaction_count = fields.Integer(
        string="İşlem Sayısı",
        compute="_compute_transaction_count",
    )

    _sql_constraints = [
        (
            "unique_provider_per_company",
            "unique(code, company_id)",
            "Her sağlayıcı şirket başına tek kez yapılandırılabilir.",
        ),
    ]

    @api.depends("code")
    def _compute_transaction_count(self):
        Tx = self.env["hashtap.payment.transaction"]
        for prov in self:
            prov.transaction_count = Tx.search_count([("provider_id", "=", prov.id)])

    @api.model
    def resolve_active(self, company=None):
        """Bulunan ilk aktif sağlayıcıyı döner; yoksa False."""
        company = company or self.env.company
        return self.search(
            [("company_id", "=", company.id), ("active", "=", True)],
            order="sequence, id",
            limit=1,
        )

    def action_view_transactions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Ödeme İşlemleri",
            "res_model": "hashtap.payment.transaction",
            "view_mode": "tree,form",
            "domain": [("provider_id", "=", self.id)],
        }
