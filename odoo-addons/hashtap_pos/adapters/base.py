"""Ödeme sağlayıcı adapter sözleşmesi.

Yeni sağlayıcı eklemek için `BasePaymentAdapter` alt sınıfını yaz,
`registry.register_adapter(code, cls)` çağır. Controller her zaman bu
arayüz üzerinden konuşur; iyzico'ya bağımlı kod controller'a sızmaz.
"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class InitPaymentRequest:
    transaction_id: int
    order_id: int
    amount_kurus: int
    currency: str
    method_code: str
    callback_url: str
    conversation_id: str
    customer: dict = field(default_factory=dict)
    items: list = field(default_factory=list)


@dataclass
class InitPaymentResult:
    ok: bool
    provider_ref: Optional[str] = None
    threeds_redirect_url: Optional[str] = None
    raw: Any = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class CallbackResult:
    ok: bool
    captured: bool = False
    provider_ref: Optional[str] = None
    conversation_id: Optional[str] = None
    raw: Any = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class BasePaymentAdapter:
    """Adapter arayüzü. Gerçek sağlayıcı sınıfları bu kontratı uygular."""

    code: str = ""

    def __init__(self, provider):
        # `provider` bir `hashtap.payment.provider` kaydı.
        self.provider = provider

    # --- Lifecycle -------------------------------------------------------
    def init_payment(self, req: InitPaymentRequest) -> InitPaymentResult:
        raise NotImplementedError

    def handle_callback(self, payload: dict) -> CallbackResult:
        raise NotImplementedError

    # --- Webhook ---------------------------------------------------------
    def verify_webhook(self, raw_body: bytes, headers: dict) -> bool:
        """Webhook HMAC doğrulaması. Varsayılan: secret yoksa reddet."""
        return False

    def parse_webhook(self, raw_body: bytes, headers: dict) -> CallbackResult:
        raise NotImplementedError

    # --- Yardımcılar -----------------------------------------------------
    @property
    def is_sandbox(self) -> bool:
        return bool(self.provider and self.provider.sandbox)
