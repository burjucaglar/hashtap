import json
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..adapters.earsiv.base import IssueReceiptRequest
from ..adapters.earsiv.registry import get_adapter as get_earsiv_adapter


_logger = logging.getLogger(__name__)


HASHTAP_ORDER_STATE = [
    ("placed", "Alındı"),
    ("paid", "Ödendi"),
    ("kitchen_sent", "Mutfakta (Yeni)"),
    ("preparing", "Hazırlanıyor"),
    ("ready", "Hazır"),
    ("served", "Servis edildi"),
    ("cancelled", "İptal"),
]

KDS_ACTIVE_STATES = ("kitchen_sent", "preparing", "ready")

PAYMENT_STATE = [
    ("unpaid", "Ödenmedi"),
    ("pending", "Beklemede"),
    ("paid", "Ödendi"),
    ("failed", "Başarısız"),
    ("refunded", "İade edildi"),
]

# e-Arşiv ekseni HASHTAP_ORDER_STATE'den bağımsız. Fail-close kuralı:
# require_receipt=True ve earsiv_state!="issued" iken kitchen_sent geçişi
# ve `action_mark_kitchen_sent` engellenir.
EARSIV_STATE = [
    ("not_required", "Gerekli değil"),
    ("pending", "Kesiliyor"),
    ("issued", "Kesildi"),
    ("failed", "Başarısız"),
]


class HashtapOrder(models.Model):
    _name = "hashtap.order"
    _description = "HashTap QR Order"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    name = fields.Char(
        string="Referans",
        readonly=True,
        copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code("hashtap.order") or "/",
    )
    table_id = fields.Many2one(
        "restaurant.table",
        string="Masa",
        required=True,
        ondelete="restrict",
        index=True,
    )
    table_slug = fields.Char(
        string="Masa Slug",
        related="table_id.hashtap_qr_slug",
        store=True,
        index=True,
    )
    state = fields.Selection(
        HASHTAP_ORDER_STATE,
        string="Durum",
        default="placed",
        required=True,
        tracking=True,
        index=True,
    )
    line_ids = fields.One2many(
        "hashtap.order.line",
        "order_id",
        string="Kalemler",
    )
    subtotal_kurus = fields.Integer(
        string="Ara Toplam (kuruş)",
        compute="_compute_totals",
        store=True,
    )
    total_kurus = fields.Integer(
        string="Toplam (kuruş)",
        compute="_compute_totals",
        store=True,
        tracking=True,
    )
    subtotal = fields.Monetary(
        string="Ara Toplam",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    total = fields.Monetary(
        string="Toplam",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    currency = fields.Char(default="TRY", required=True)
    currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_currency_id",
        store=True,
    )
    customer_note = fields.Text(string="Müşteri Notu")
    pos_order_id = fields.Many2one(
        "pos.order",
        string="Bağlı POS Siparişi",
        copy=False,
        readonly=True,
        help="Ödeme sonrası oluşturulan pos.order kaydı (Faz 4+).",
    )
    payment_state = fields.Selection(
        PAYMENT_STATE,
        string="Ödeme Durumu",
        default="unpaid",
        required=True,
        tracking=True,
        index=True,
    )
    payment_method_code = fields.Char(
        string="Ödeme Yöntemi",
        help="Müşterinin seçtiği metot kodu (card / apple_pay / pay_at_counter vb).",
    )
    paid_amount_kurus = fields.Integer(
        string="Ödenen Tutar (kuruş)", default=0, tracking=True,
    )
    paid_amount = fields.Monetary(
        string="Ödenen Tutar",
        compute="_compute_paid_amount",
        store=True,
        currency_field="currency_id",
    )
    payment_transaction_ids = fields.One2many(
        "hashtap.payment.transaction",
        "order_id",
        string="Ödeme İşlemleri",
    )
    active_transaction_id = fields.Many2one(
        "hashtap.payment.transaction",
        string="Aktif İşlem",
        compute="_compute_active_transaction",
    )
    require_receipt = fields.Boolean(
        string="Fiş Gerekli",
        default=True,
        help="B2C QR siparişlerinde True — ödendiğinde otomatik e-Arşiv kesilir.",
    )
    earsiv_state = fields.Selection(
        EARSIV_STATE,
        string="e-Arşiv Durumu",
        default="not_required",
        tracking=True,
        index=True,
    )
    earsiv_receipt_ids = fields.One2many(
        "hashtap.earsiv.receipt",
        "order_id",
        string="e-Arşiv Fişleri",
    )
    earsiv_receipt_id = fields.Many2one(
        "hashtap.earsiv.receipt",
        string="Aktif Fiş",
        compute="_compute_earsiv_receipt_id",
        store=True,
    )
    is_earsiv_blocked = fields.Boolean(
        string="e-Arşiv Bekliyor",
        compute="_compute_is_earsiv_blocked",
        store=True,
        help="True iken sipariş mutfağa gitmez (fail-close).",
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    kitchen_fired_at = fields.Datetime(
        string="Mutfağa Gönderildi",
        copy=False,
        readonly=True,
        index=True,
        help="KDS sıralama ve bekleme süresi için.",
    )
    ready_at = fields.Datetime(
        string="Hazır Saati", copy=False, readonly=True,
    )

    @api.depends("line_ids.subtotal_kurus")
    def _compute_totals(self):
        for order in self:
            subtotal = sum(order.line_ids.mapped("subtotal_kurus"))
            order.subtotal_kurus = subtotal
            order.total_kurus = subtotal
            order.subtotal = subtotal / 100.0
            order.total = subtotal / 100.0

    @api.depends("currency")
    def _compute_currency_id(self):
        for order in self:
            order.currency_id = self.env["res.currency"].search(
                [("name", "=", order.currency or "TRY")], limit=1
            )

    @api.depends("paid_amount_kurus")
    def _compute_paid_amount(self):
        for order in self:
            order.paid_amount = order.paid_amount_kurus / 100.0

    @api.depends(
        "payment_transaction_ids", "payment_transaction_ids.state",
    )
    def _compute_active_transaction(self):
        for order in self:
            priority = {"pending": 0, "authorized": 1, "captured": 2,
                        "draft": 3, "failed": 4, "cancelled": 5, "refunded": 6}
            txs = sorted(
                order.payment_transaction_ids,
                key=lambda t: (priority.get(t.state, 9), -(t.id or 0)),
            )
            order.active_transaction_id = txs[0] if txs else False

    @api.depends("earsiv_receipt_ids", "earsiv_receipt_ids.state")
    def _compute_earsiv_receipt_id(self):
        for order in self:
            # issued > pending > failed > draft > cancelled önceliği.
            priority = {"issued": 0, "pending": 1, "failed": 2,
                        "draft": 3, "cancelled": 4}
            receipts = sorted(
                order.earsiv_receipt_ids,
                key=lambda r: (priority.get(r.state, 9), -(r.id or 0)),
            )
            order.earsiv_receipt_id = receipts[0] if receipts else False

    @api.depends("require_receipt", "earsiv_state")
    def _compute_is_earsiv_blocked(self):
        for order in self:
            order.is_earsiv_blocked = bool(
                order.require_receipt and order.earsiv_state != "issued"
                and order.state in ("paid", "placed")
            )

    def _on_payment_captured(self, transaction):
        for order in self:
            order.write({
                "payment_state": "paid",
                "paid_amount_kurus": transaction.amount_kurus,
                "state": "paid" if order.state == "placed" else order.state,
            })
            order.message_post(body=f"Ödeme tamamlandı: {transaction.name}")
            if order.require_receipt:
                # Fail-close: fiş başarıyla kesilmeden mutfak tetiklenmez.
                order._issue_earsiv_receipt()
            else:
                # Fiş gerektirmeyen senaryo (örn. kasada ödeme sonrası
                # ÖKC kullanılıyor). Otomatik mutfağa gönder.
                order._fire_kitchen()

    def _on_payment_failed(self, transaction):
        for order in self:
            if order.payment_state == "paid":
                continue
            order.payment_state = "failed"
            order.message_post(
                body=f"Ödeme başarısız: {transaction.name} ({transaction.error_code or ''})"
            )

    # ---------------------------------------------------------- e-Arşiv --
    def _issue_earsiv_receipt(self, force=False):
        """Aktif provider'dan fiş kesmeyi dener.

        Fail-close: başarısızsa sipariş mutfağa gönderilmez, earsiv_state
        'failed' olur. Başarılıysa otomatik `_fire_kitchen()` çağrılır.
        """
        Provider = self.env["hashtap.earsiv.provider"]
        Receipt = self.env["hashtap.earsiv.receipt"]
        for order in self:
            if not order.require_receipt:
                continue
            if order.earsiv_state == "issued" and not force:
                continue
            provider = Provider.sudo().resolve_active(company=order.company_id)
            if not provider:
                _logger.warning(
                    "e-Arşiv provider yok; sipariş %s fail-close'da bekliyor.",
                    order.name,
                )
                order.earsiv_state = "failed"
                order.message_post(
                    body="e-Arşiv sağlayıcısı yapılandırılmamış — "
                         "fiş kesilemedi, sipariş mutfağa gitmiyor.",
                )
                continue

            order.earsiv_state = "pending"
            receipt = Receipt.sudo().create({
                "order_id": order.id,
                "provider_id": provider.id,
                "state": "pending",
                "amount_kurus": order.total_kurus,
                "currency": order.currency,
            })

            adapter = get_earsiv_adapter(provider)
            seller_vkn = (order.company_id.vat or "").strip()
            lines = [
                {
                    "name": ln.item_name,
                    "quantity": ln.quantity,
                    "unit_price_kurus": ln.unit_price_kurus + ln.modifier_total_kurus,
                    "total_kurus": ln.subtotal_kurus,
                    "tax_rate": 10,  # MVP: restoran KDV'si varsayılan %10
                }
                for ln in order.line_ids
            ]
            req = IssueReceiptRequest(
                receipt_id=receipt.id,
                order_id=order.id,
                order_ref=order.name or f"HT-{order.id}",
                amount_kurus=order.total_kurus,
                currency=order.currency,
                seller_vkn=seller_vkn,
                lines=lines,
            )
            try:
                result = adapter.issue_receipt(req)
            except Exception as e:  # noqa: BLE001
                _logger.exception("e-Arşiv adapter crashed")
                receipt.mark_failed(
                    error_code="adapter_crash",
                    error_message=str(e),
                    retryable=True,
                )
                continue

            if result.ok:
                receipt.mark_issued(
                    ettn=result.ettn,
                    pdf_url=result.pdf_url,
                    qr_content=result.qr_content,
                    raw_response=json.dumps(result.raw) if result.raw else None,
                )
            else:
                receipt.mark_failed(
                    error_code=result.error_code,
                    error_message=result.error_message,
                    retryable=result.retryable,
                    raw_response=json.dumps(result.raw) if result.raw else None,
                )

    def _on_earsiv_issued(self, receipt):
        for order in self:
            order.earsiv_state = "issued"
            order.message_post(
                body=f"e-Arşiv fişi kesildi: {receipt.ettn or receipt.name}"
            )
            order._fire_kitchen()

    def _on_earsiv_failed(self, receipt):
        for order in self:
            order.earsiv_state = "failed"
            order.message_post(
                body=(
                    f"e-Arşiv fiş kesimi başarısız: "
                    f"{receipt.error_code or '?'} — {receipt.error_message or ''}. "
                    "Sipariş mutfağa gönderilmiyor (fail-close)."
                )
            )

    def action_retry_earsiv(self):
        """Admin panelinden tek tıkla yeniden fiş kesmeyi dene."""
        for order in self:
            order._issue_earsiv_receipt(force=True)

    # ---------------------------------------------------------- mutfak --
    def _fire_kitchen(self):
        """İç yardımcı: fail-close geçilmişse siparişi mutfağa gönder."""
        for order in self:
            if order.require_receipt and order.earsiv_state != "issued":
                continue
            if order.state == "paid":
                order.write({
                    "state": "kitchen_sent",
                    "kitchen_fired_at": fields.Datetime.now(),
                })

    def action_mark_kitchen_sent(self):
        for order in self:
            if order.state not in ("placed", "paid"):
                continue
            if order.is_earsiv_blocked:
                raise ValidationError(
                    "e-Arşiv fişi kesilmeden sipariş mutfağa gönderilemez. "
                    "Önce 'Fişi yeniden dene' aksiyonunu kullan."
                )
            order.write({
                "state": "kitchen_sent",
                "kitchen_fired_at": fields.Datetime.now(),
            })

    def action_mark_preparing(self):
        for order in self:
            if order.state == "kitchen_sent":
                order.state = "preparing"

    def action_mark_ready(self):
        for order in self:
            if order.state in ("kitchen_sent", "preparing"):
                order.write({
                    "state": "ready",
                    "ready_at": fields.Datetime.now(),
                })

    def action_mark_served(self):
        for order in self:
            if order.state in ("kitchen_sent", "preparing", "ready"):
                order.state = "served"

    def action_cancel(self):
        for order in self:
            if order.state not in ("served", "cancelled"):
                order.state = "cancelled"

    def action_mark_paid_offline(self):
        """Kasada ödeme aldıktan sonra operatörün el ile işaretlemesi.

        Bu yalnızca pay_at_counter / cash yöntemlerinde beklenir.
        Online metodlarda provider callback'i otomatik kapatır.
        Kasada ödeme genellikle ÖKC ile beraber gider; require_receipt
        False ise e-Arşiv tetiklenmez.
        """
        for order in self:
            if order.payment_state == "paid":
                continue
            order.write({
                "payment_state": "paid",
                "paid_amount_kurus": order.total_kurus,
                "state": "paid" if order.state == "placed" else order.state,
            })
            order.message_post(body="Ödeme kasada alındı olarak işaretlendi.")
            if order.require_receipt:
                order._issue_earsiv_receipt()
            else:
                order._fire_kitchen()


class HashtapOrderLine(models.Model):
    _name = "hashtap.order.line"
    _description = "HashTap QR Order Line"
    _order = "sequence, id"

    order_id = fields.Many2one(
        "hashtap.order",
        string="Sipariş",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    item_id = fields.Many2one(
        "hashtap.menu.item",
        string="Ürün",
        required=True,
        ondelete="restrict",
    )
    item_name = fields.Char(
        string="Görünen Ad",
        required=True,
        help="Sipariş anındaki menü adı (sonradan değişse bile korunur).",
    )
    quantity = fields.Integer(
        string="Adet",
        required=True,
        default=1,
    )
    unit_price_kurus = fields.Integer(
        string="Birim Fiyat (kuruş)",
        required=True,
        help="Menü kaleminin sipariş anındaki fiyatı; değişmez.",
    )
    modifier_ids = fields.Many2many(
        "hashtap.modifier",
        string="Modifier'lar",
    )
    modifier_total_kurus = fields.Integer(
        string="Modifier Farkı (kuruş)",
        help="Tüm seçili modifier'ların birim başı farkı toplamı.",
    )
    subtotal_kurus = fields.Integer(
        string="Ara Toplam (kuruş)",
        compute="_compute_subtotal",
        store=True,
    )
    unit_price = fields.Monetary(
        string="Birim Fiyat",
        compute="_compute_display_prices",
        store=True,
        currency_field="currency_id",
    )
    subtotal = fields.Monetary(
        string="Ara Toplam",
        compute="_compute_display_prices",
        store=True,
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="order_id.currency_id", store=True, readonly=True,
    )
    note = fields.Char(string="Not")

    @api.depends("quantity", "unit_price_kurus", "modifier_total_kurus")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal_kurus = line.quantity * (
                line.unit_price_kurus + line.modifier_total_kurus
            )

    @api.depends("unit_price_kurus", "modifier_total_kurus", "subtotal_kurus")
    def _compute_display_prices(self):
        for line in self:
            line.unit_price = (line.unit_price_kurus + line.modifier_total_kurus) / 100.0
            line.subtotal = line.subtotal_kurus / 100.0
