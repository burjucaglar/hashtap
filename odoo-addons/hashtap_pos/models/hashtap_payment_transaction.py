import secrets

from odoo import api, fields, models


TX_STATE = [
    ("draft", "Taslak"),
    ("pending", "3DS bekliyor"),
    ("authorized", "Yetki alındı"),
    ("captured", "Ödeme alındı"),
    ("failed", "Başarısız"),
    ("cancelled", "İptal"),
    ("refunded", "İade edildi"),
]


class HashtapPaymentTransaction(models.Model):
    _name = "hashtap.payment.transaction"
    _description = "HashTap Payment Transaction"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    name = fields.Char(
        string="Referans",
        readonly=True,
        copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code("hashtap.payment.transaction") or "/",
    )
    order_id = fields.Many2one(
        "hashtap.order",
        string="Sipariş",
        required=True,
        ondelete="restrict",
        index=True,
    )
    provider_id = fields.Many2one(
        "hashtap.payment.provider",
        string="Sağlayıcı",
        ondelete="restrict",
        index=True,
    )
    method_code = fields.Char(string="Yöntem Kodu", required=True)
    state = fields.Selection(
        TX_STATE, string="Durum", default="draft", tracking=True, index=True,
    )
    amount_kurus = fields.Integer(string="Tutar (kuruş)", required=True)
    currency = fields.Char(default="TRY", required=True)
    idempotency_key = fields.Char(
        string="Idempotency Key",
        index=True,
        copy=False,
        help="Aynı anahtarla gelen ikinci init isteği yeni kayıt açmaz.",
    )
    provider_ref = fields.Char(
        string="Sağlayıcı Ref.",
        index=True,
        copy=False,
        help="Sağlayıcının bu işleme verdiği benzersiz ID (iyzico paymentId vb).",
    )
    conversation_id = fields.Char(
        string="Conversation ID",
        copy=False,
        help="iyzico conversationId — callback'te işlemi eşleştirmek için.",
    )
    callback_token = fields.Char(
        string="Callback Token",
        copy=False,
        help="Dönüş URL'sinde kullanılan tek kullanımlık rastgele anahtar.",
    )
    threeds_redirect_url = fields.Char(string="3DS URL")
    raw_request = fields.Text(string="İstek (json)", groups="base.group_system")
    raw_response = fields.Text(string="Yanıt (json)", groups="base.group_system")
    error_code = fields.Char(string="Hata Kodu")
    error_message = fields.Char(string="Hata Mesajı")
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )

    _sql_constraints = [
        (
            "unique_provider_ref",
            "unique(provider_id, provider_ref)",
            "Aynı provider_ref ile iki işlem oluşturulamaz.",
        ),
    ]

    @api.model
    def new_callback_token(self):
        return secrets.token_urlsafe(24)

    def mark_authorized(self, provider_ref=None, raw_response=None):
        for tx in self:
            vals = {"state": "authorized"}
            if provider_ref:
                vals["provider_ref"] = provider_ref
            if raw_response is not None:
                vals["raw_response"] = raw_response
            tx.write(vals)

    def mark_captured(self, provider_ref=None, raw_response=None):
        for tx in self:
            vals = {"state": "captured"}
            if provider_ref:
                vals["provider_ref"] = provider_ref
            if raw_response is not None:
                vals["raw_response"] = raw_response
            tx.write(vals)
            tx.order_id._on_payment_captured(tx)

    def mark_failed(self, error_code=None, error_message=None, raw_response=None):
        for tx in self:
            tx.write({
                "state": "failed",
                "error_code": error_code or "unknown",
                "error_message": error_message or "",
                "raw_response": raw_response or tx.raw_response,
            })
            tx.order_id._on_payment_failed(tx)
