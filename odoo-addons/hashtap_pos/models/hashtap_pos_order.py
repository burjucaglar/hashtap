from odoo import fields, models


HASHTAP_SOURCE = [
    ("pos", "POS (kasa)"),
    ("qr", "QR (müşteri PWA)"),
]


class PosOrder(models.Model):
    _inherit = "pos.order"

    hashtap_source = fields.Selection(
        HASHTAP_SOURCE,
        string="Kaynak",
        default="pos",
        help="QR akışından gelenler 'qr'; kasadan girilenler 'pos'.",
    )
    hashtap_table_slug = fields.Char(
        string="QR Masa Slug",
        index=True,
        copy=False,
        help="Sipariş QR'dan geldiyse masa kısa kimliği. Debug ve trace için.",
    )
    hashtap_paid = fields.Boolean(
        string="HashTap Ödendi",
        help="iyzico callback'inden sonra True olur. Ödenmeden mutfağa gitmez.",
    )
    hashtap_kitchen_sent = fields.Boolean(
        string="Mutfağa Gönderildi",
        help="True iken KDS/mutfak printer akışına düştü demektir.",
    )
    hashtap_customer_note = fields.Text(
        string="Müşteri Notu",
        help="QR akışında müşterinin yazdığı serbest metin.",
    )
