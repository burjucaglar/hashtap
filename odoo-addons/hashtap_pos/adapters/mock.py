"""Dev / test için mock adapter.

Gerçek ağa çıkmadan init → callback → capture akışını simüle eder.
Sandbox modunda iyzico yerine bu devreye alınabilir.

Akış:
    init_payment → 3DS benzeri bir simülatör sayfasına redirect URL döner
    (/hashtap/payment/mock/simulator?token=...). Kullanıcı sayfada
    "Onayla" → callback?result=success, "Reddet" → callback?result=fail.
"""
import hashlib
import hmac
import secrets
from urllib.parse import parse_qs, urlparse

from .base import BasePaymentAdapter, CallbackResult, InitPaymentRequest, InitPaymentResult


class MockAdapter(BasePaymentAdapter):
    code = "mock"

    def init_payment(self, req: InitPaymentRequest) -> InitPaymentResult:
        provider_ref = f"MOCK-{secrets.token_hex(8).upper()}"
        parsed = urlparse(req.callback_url)
        token = (parse_qs(parsed.query).get("token") or [""])[0]
        simulator_url = (
            f"{parsed.scheme}://{parsed.netloc}"
            f"/hashtap/payment/mock/simulator"
            f"?token={token}&amount_kurus={req.amount_kurus}"
        )
        return InitPaymentResult(
            ok=True,
            provider_ref=provider_ref,
            threeds_redirect_url=simulator_url,
            raw={"mock": True, "conversation_id": req.conversation_id,
                 "amount_kurus": req.amount_kurus},
        )

    def handle_callback(self, payload: dict) -> CallbackResult:
        result = (payload.get("result") or "success").lower()
        captured = result == "success"
        return CallbackResult(
            ok=True,
            captured=captured,
            provider_ref=payload.get("provider_ref"),
            conversation_id=payload.get("conversation_id"),
            raw=payload,
            error_code=None if captured else payload.get("error_code", "declined"),
            error_message=None if captured else "Mock ödeme reddedildi",
        )

    def verify_webhook(self, raw_body: bytes, headers: dict) -> bool:
        secret = (self.provider.webhook_secret or "").encode()
        signature = headers.get("X-Hashtap-Signature") or headers.get("x-hashtap-signature")
        if not secret or not signature:
            return False
        expected = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_webhook(self, raw_body: bytes, headers: dict) -> CallbackResult:
        import json
        payload = json.loads(raw_body.decode("utf-8") or "{}")
        return self.handle_callback(payload)
