"""e-Arşiv sağlayıcı adapter sözleşmesi.

Yeni sağlayıcı eklemek için `BaseEArsivAdapter` alt sınıfını yaz,
`registry.register_adapter(code, cls)` çağır. Service/controller her
zaman bu arayüz üzerinden konuşur; Foriba'ya bağımlı kod servise sızmaz.
"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class IssueReceiptRequest:
    """Bir siparişi fişe dönüştürürken gerekli tüm bilgiler."""
    receipt_id: int
    order_id: int
    order_ref: str
    amount_kurus: int
    currency: str
    seller_vkn: str  # Satıcı (restoran) VKN
    # Alıcı (müşteri) bilgisi — QR siparişlerde çoğunlukla anonim.
    # VKN/TCKN boşsa GİB genel alıcı formatını kullan ("11111111111").
    buyer_vkn: str = ""
    buyer_name: str = ""
    # Kalemler: [{name, quantity, unit_price_kurus, tax_rate, total_kurus}]
    lines: list = field(default_factory=list)


@dataclass
class IssueReceiptResult:
    ok: bool
    ettn: Optional[str] = None
    pdf_url: Optional[str] = None
    qr_content: Optional[str] = None
    raw: Any = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    # Retry mantığı için: timeout/5xx → True, validation/400 → False.
    retryable: bool = True


class BaseEArsivAdapter:
    """Adapter arayüzü. Foriba/Uyumsoft/Mock bu kontratı uygular."""

    code: str = ""

    def __init__(self, provider):
        self.provider = provider

    def issue_receipt(self, req: IssueReceiptRequest) -> IssueReceiptResult:
        raise NotImplementedError

    def cancel_receipt(self, ettn: str, reason: str) -> IssueReceiptResult:
        """İade için fiş iptali. MVP'de implementasyon opsiyonel."""
        return IssueReceiptResult(
            ok=False, error_code="not_implemented",
            error_message="İptal henüz desteklenmiyor",
        )

    @property
    def is_sandbox(self) -> bool:
        return bool(self.provider and self.provider.sandbox)
