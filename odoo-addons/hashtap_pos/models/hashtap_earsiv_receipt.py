from odoo import api, fields, models


RECEIPT_STATE = [
    ("draft", "Taslak"),
    ("pending", "Kesiliyor"),
    ("issued", "Kesildi"),
    ("failed", "Başarısız"),
    ("cancelled", "İptal"),
]


class HashtapEArsivReceipt(models.Model):
    """Bir siparişin e-Arşiv fiş kaydı.

    Aynı sipariş için tek bir active fiş beklenir ama retry sırasında
    tarihsel kayıtlar saklanır (silmiyoruz).
    """
    _name = "hashtap.earsiv.receipt"
    _description = "HashTap e-Arşiv Receipt"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    name = fields.Char(
        string="Referans",
        readonly=True,
        copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "hashtap.earsiv.receipt"
        ) or "/",
    )
    order_id = fields.Many2one(
        "hashtap.order",
        string="Sipariş",
        required=True,
        ondelete="restrict",
        index=True,
    )
    provider_id = fields.Many2one(
        "hashtap.earsiv.provider",
        string="Sağlayıcı",
        ondelete="restrict",
        index=True,
    )
    state = fields.Selection(
        RECEIPT_STATE, string="Durum", default="draft", tracking=True, index=True,
    )
    # Sağlayıcı tarafında fişin benzersiz ID'si (ETTN: Evrensel Tekil
    # Tanımlama Numarası). GİB nezdinde fiş bu ID ile bilinir.
    ettn = fields.Char(string="ETTN", index=True, copy=False)
    pdf_url = fields.Char(string="PDF URL")
    qr_content = fields.Char(string="QR İçeriği")
    issued_at = fields.Datetime(string="Kesim Zamanı", tracking=True)
    retry_count = fields.Integer(string="Deneme Sayısı", default=0, tracking=True)
    retryable = fields.Boolean(
        string="Tekrar Denenebilir",
        default=True,
        help="Son hata geçici mi (timeout/5xx) yoksa kalıcı mı (validation)?",
    )
    amount_kurus = fields.Integer(string="Tutar (kuruş)", required=True)
    currency = fields.Char(default="TRY")
    error_code = fields.Char(string="Hata Kodu")
    error_message = fields.Char(string="Hata Mesajı")
    raw_request = fields.Text(string="İstek (json)", groups="base.group_system")
    raw_response = fields.Text(string="Yanıt (json)", groups="base.group_system")
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )

    _sql_constraints = [
        (
            "unique_provider_ettn",
            "unique(provider_id, ettn)",
            "Aynı ETTN ile iki fiş kaydı oluşturulamaz.",
        ),
    ]

    def mark_issued(self, ettn=None, pdf_url=None, qr_content=None,
                    raw_response=None):
        for rec in self:
            vals = {
                "state": "issued",
                "issued_at": fields.Datetime.now(),
                "error_code": False,
                "error_message": False,
            }
            if ettn:
                vals["ettn"] = ettn
            if pdf_url:
                vals["pdf_url"] = pdf_url
            if qr_content:
                vals["qr_content"] = qr_content
            if raw_response is not None:
                vals["raw_response"] = raw_response
            rec.write(vals)
            rec.order_id._on_earsiv_issued(rec)

    def mark_failed(self, error_code=None, error_message=None,
                    retryable=True, raw_response=None):
        for rec in self:
            rec.write({
                "state": "failed",
                "retry_count": rec.retry_count + 1,
                "retryable": retryable,
                "error_code": error_code or "unknown",
                "error_message": error_message or "",
                "raw_response": raw_response or rec.raw_response,
            })
            rec.order_id._on_earsiv_failed(rec)

    def action_retry(self):
        """Admin panelinden manuel retry."""
        for rec in self:
            if rec.state == "issued":
                continue
            rec.order_id._issue_earsiv_receipt(force=True)
