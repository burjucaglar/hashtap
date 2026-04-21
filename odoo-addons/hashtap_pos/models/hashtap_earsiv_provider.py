from odoo import api, fields, models


EARSIV_PROVIDER_CODES = [
    ("foriba", "Foriba"),
    ("uyumsoft", "Uyumsoft"),
    ("mock", "Mock (dev)"),
]


class HashtapEArsivProvider(models.Model):
    """e-Arşiv sağlayıcı yapılandırması.

    Paralel tasarım: hashtap.payment.provider ile aynı pattern. Credential
    admin'den girilir; adapter credential boşsa stub/mock moduna düşer.
    """
    _name = "hashtap.earsiv.provider"
    _description = "HashTap e-Arşiv Provider Configuration"
    _inherit = ["mail.thread"]
    _order = "sequence, id"

    name = fields.Char(string="Ad", required=True)
    code = fields.Selection(
        EARSIV_PROVIDER_CODES,
        string="Sağlayıcı",
        required=True,
        default="foriba",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    sandbox = fields.Boolean(
        string="Sandbox",
        default=True,
        tracking=True,
        help="İşaretliyken gerçek GİB gönderimi yapılmaz; sağlayıcının test endpoint'i kullanılır.",
    )
    api_key = fields.Char(string="API Key")
    api_secret = fields.Char(string="API Secret", groups="base.group_system")
    api_username = fields.Char(string="API Kullanıcı")
    api_password = fields.Char(string="API Şifre", groups="base.group_system")
    base_url = fields.Char(
        string="Base URL",
        help="Sağlayıcı REST endpoint'i. Boşsa adapter varsayılanı kullanır.",
    )
    seller_vkn = fields.Char(
        string="Satıcı VKN/TCKN",
        help="Restoranın vergi kimlik numarası. Şirket kaydından otomatik alınır.",
    )
    webhook_secret = fields.Char(
        string="Webhook Secret",
        groups="base.group_system",
        help="Sağlayıcıdan gelen bildirim/webhook imza doğrulaması için.",
    )
    # Mock/chaos testi için — sadece code=mock'ta anlamlı.
    mock_fail_rate = fields.Integer(
        string="Mock Hata Oranı (%)",
        default=0,
        help="Mock adapter kaç yüzde ihtimalle fail dönsün. Chaos testi için.",
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    receipt_count = fields.Integer(
        string="Fiş Sayısı",
        compute="_compute_receipt_count",
    )

    _sql_constraints = [
        (
            "unique_earsiv_provider_per_company",
            "unique(code, company_id)",
            "Her e-Arşiv sağlayıcı şirket başına tek kez yapılandırılabilir.",
        ),
    ]

    @api.depends("code")
    def _compute_receipt_count(self):
        Receipt = self.env["hashtap.earsiv.receipt"]
        for prov in self:
            prov.receipt_count = Receipt.search_count([("provider_id", "=", prov.id)])

    @api.model
    def resolve_active(self, company=None):
        """İlk aktif e-Arşiv sağlayıcısını döner; yoksa False."""
        company = company or self.env.company
        return self.search(
            [("company_id", "=", company.id), ("active", "=", True)],
            order="sequence, id",
            limit=1,
        )

    def action_view_receipts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "e-Arşiv Fişleri",
            "res_model": "hashtap.earsiv.receipt",
            "view_mode": "tree,form",
            "domain": [("provider_id", "=", self.id)],
        }
