"""Dev / test için mock e-Arşiv adapter.

Başarı varsayılan, `provider.mock_fail_rate` ile yüzde chaos eklenebilir.
ETTN UUID formatında üretilir (gerçek GİB ETTN'i de UUID biçiminde).
"""
import random
import uuid

from .base import BaseEArsivAdapter, IssueReceiptRequest, IssueReceiptResult


class MockEArsivAdapter(BaseEArsivAdapter):
    code = "mock"

    def issue_receipt(self, req: IssueReceiptRequest) -> IssueReceiptResult:
        fail_rate = max(0, min(100, int(self.provider.mock_fail_rate or 0)))
        if fail_rate and random.randint(1, 100) <= fail_rate:
            return IssueReceiptResult(
                ok=False,
                error_code="mock_random_failure",
                error_message=f"Mock chaos: %{fail_rate} fail rate",
                retryable=True,
                raw={"mock": True, "chaos": True, "fail_rate": fail_rate},
            )

        ettn = str(uuid.uuid4()).upper()
        # GİB QR içeriği gerçekte imzalı doğrulama URL'i olur; burada
        # deterministik bir string döneriz ki PWA QR'ı render edebilsin.
        qr = (
            f"https://earsivportal.efatura.gov.tr/earsiv-services/download?"
            f"ettn={ettn}&token=MOCK"
        )
        pdf = f"/hashtap/receipt/{req.receipt_id}/pdf"
        return IssueReceiptResult(
            ok=True,
            ettn=ettn,
            pdf_url=pdf,
            qr_content=qr,
            raw={
                "mock": True,
                "ettn": ettn,
                "amount_kurus": req.amount_kurus,
                "order_ref": req.order_ref,
            },
        )

    def cancel_receipt(self, ettn: str, reason: str) -> IssueReceiptResult:
        return IssueReceiptResult(
            ok=True,
            ettn=ettn,
            raw={"mock": True, "cancelled": True, "reason": reason},
        )
