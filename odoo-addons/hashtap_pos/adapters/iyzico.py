"""iyzico adapter — 3DS başlatma + callback + webhook doğrulaması.

Not: gerçek iyzico SDK'sı (pip: iyzipay) modülün opsiyonel bağımlılığı.
SDK kurulu değilse veya sandbox key yoksa adapter deterministik bir
"mock" cevap döner ki dev/test ortamında ağ olmadan akış çalıştırılabilir.

Gerçek entegrasyon için:
  - `pip install iyzipay`
  - Provider kaydında `api_key`, `api_secret`, `sub_merchant_key`,
    `webhook_secret` doldurulur.
  - `sandbox=True` iken iyzico'nun sandbox base URL'si,
    `sandbox=False` iken prod base URL kullanılır.
"""
import base64
import hashlib
import hmac
import json
import logging
import secrets

from .base import BasePaymentAdapter, CallbackResult, InitPaymentRequest, InitPaymentResult

_logger = logging.getLogger(__name__)

SANDBOX_BASE_URL = "https://sandbox-api.iyzipay.com"
PROD_BASE_URL = "https://api.iyzipay.com"


class IyzicoAdapter(BasePaymentAdapter):
    code = "iyzico"

    @property
    def base_url(self) -> str:
        if self.provider.base_url:
            return self.provider.base_url.rstrip("/")
        return SANDBOX_BASE_URL if self.is_sandbox else PROD_BASE_URL

    def _has_credentials(self) -> bool:
        return bool(self.provider.api_key and self.provider.api_secret)

    def init_payment(self, req: InitPaymentRequest) -> InitPaymentResult:
        if not self._has_credentials():
            # Credential yoksa deterministik stub — dev/demo akışı için.
            _logger.warning("iyzico credentials missing, returning stub init")
            ref = f"IYZ-STUB-{secrets.token_hex(6).upper()}"
            return InitPaymentResult(
                ok=True,
                provider_ref=ref,
                threeds_redirect_url=f"{req.callback_url}&stub=1",
                raw={"stub": True, "reason": "credentials_missing"},
            )

        try:
            import iyzipay  # type: ignore
        except ImportError:
            _logger.warning("iyzipay SDK not installed; using stub init")
            ref = f"IYZ-NOSDK-{secrets.token_hex(6).upper()}"
            return InitPaymentResult(
                ok=True,
                provider_ref=ref,
                threeds_redirect_url=f"{req.callback_url}&stub=1",
                raw={"stub": True, "reason": "sdk_missing"},
            )

        options = {
            "api_key": self.provider.api_key,
            "secret_key": self.provider.api_secret,
            "base_url": self.base_url,
        }
        price_str = f"{req.amount_kurus / 100.0:.2f}"
        buyer = req.customer or {}
        payload = {
            "locale": "tr",
            "conversationId": req.conversation_id,
            "price": price_str,
            "paidPrice": price_str,
            "currency": req.currency,
            "basketId": str(req.order_id),
            "paymentGroup": "PRODUCT",
            "callbackUrl": req.callback_url,
            "buyer": {
                "id": buyer.get("id", f"guest-{req.order_id}"),
                "name": buyer.get("name", "Misafir"),
                "surname": buyer.get("surname", "Müşteri"),
                "email": buyer.get("email", "noreply@example.com"),
                "identityNumber": buyer.get("identity", "11111111111"),
                "registrationAddress": buyer.get("address", "N/A"),
                "city": buyer.get("city", "Istanbul"),
                "country": "Turkey",
                "ip": buyer.get("ip", "0.0.0.0"),
            },
            "billingAddress": {
                "contactName": buyer.get("name", "Misafir"),
                "city": buyer.get("city", "Istanbul"),
                "country": "Turkey",
                "address": buyer.get("address", "N/A"),
            },
            "shippingAddress": {
                "contactName": buyer.get("name", "Misafir"),
                "city": buyer.get("city", "Istanbul"),
                "country": "Turkey",
                "address": buyer.get("address", "N/A"),
            },
            "basketItems": [
                {
                    "id": str(it.get("id", idx)),
                    "name": it.get("name", f"item-{idx}"),
                    "category1": it.get("category", "Food"),
                    "itemType": "PHYSICAL",
                    "price": f"{it.get('price_kurus', 0) / 100.0:.2f}",
                }
                for idx, it in enumerate(req.items, start=1)
            ] or [{
                "id": str(req.order_id),
                "name": "Sipariş",
                "category1": "Food",
                "itemType": "PHYSICAL",
                "price": price_str,
            }],
        }
        try:
            response = iyzipay.CheckoutFormInitialize().create(payload, options)
            body = response.read().decode("utf-8")
            data = json.loads(body)
        except Exception as e:  # noqa: BLE001
            _logger.exception("iyzico init_payment failed")
            return InitPaymentResult(
                ok=False, error_code="network_error", error_message=str(e),
            )

        if data.get("status") != "success":
            return InitPaymentResult(
                ok=False,
                raw=data,
                error_code=data.get("errorCode", "provider_error"),
                error_message=data.get("errorMessage", "iyzico init failed"),
            )
        return InitPaymentResult(
            ok=True,
            provider_ref=data.get("token"),
            threeds_redirect_url=data.get("paymentPageUrl"),
            raw=data,
        )

    def handle_callback(self, payload: dict) -> CallbackResult:
        # Stub modunda callback direkt payload'a göre karar verir.
        token = payload.get("token") or payload.get("provider_ref")
        if payload.get("stub") or payload.get("mock"):
            return CallbackResult(
                ok=True, captured=True, provider_ref=token,
                conversation_id=payload.get("conversation_id"), raw=payload,
            )

        if not self._has_credentials() or not token:
            return CallbackResult(
                ok=False, error_code="missing_token",
                error_message="Callback token yok",
            )

        try:
            import iyzipay  # type: ignore
        except ImportError:
            return CallbackResult(
                ok=False, error_code="sdk_missing",
                error_message="iyzipay kurulu değil",
            )

        options = {
            "api_key": self.provider.api_key,
            "secret_key": self.provider.api_secret,
            "base_url": self.base_url,
        }
        try:
            response = iyzipay.CheckoutForm().retrieve({"token": token}, options)
            body = response.read().decode("utf-8")
            data = json.loads(body)
        except Exception as e:  # noqa: BLE001
            _logger.exception("iyzico handle_callback failed")
            return CallbackResult(
                ok=False, error_code="network_error", error_message=str(e),
            )

        success = (data.get("paymentStatus") == "SUCCESS"
                   and data.get("status") == "success")
        return CallbackResult(
            ok=True,
            captured=success,
            provider_ref=data.get("paymentId") or token,
            conversation_id=data.get("conversationId"),
            raw=data,
            error_code=None if success else data.get("errorCode", "declined"),
            error_message=None if success else data.get("errorMessage", ""),
        )

    def verify_webhook(self, raw_body: bytes, headers: dict) -> bool:
        secret = (self.provider.webhook_secret or "").encode()
        signature = (headers.get("X-Iyzico-Signature")
                     or headers.get("x-iyzico-signature") or "")
        if not secret or not signature:
            return False
        digest = hmac.new(secret, raw_body, hashlib.sha256).digest()
        expected = base64.b64encode(digest).decode("ascii")
        return hmac.compare_digest(expected, signature)

    def parse_webhook(self, raw_body: bytes, headers: dict) -> CallbackResult:
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return CallbackResult(
                ok=False, error_code="bad_json", error_message="invalid body",
            )
        return self.handle_callback(payload)
