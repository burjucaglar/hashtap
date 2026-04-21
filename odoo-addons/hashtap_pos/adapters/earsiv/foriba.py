"""Foriba e-Arşiv adapter — iskelet.

Gerçek entegrasyon için Foriba'nın REST API dokümanı + test hesabı gerek.
Credential boşsa veya HTTP client hata verirse deterministik stub yanıt
döner (dev/demo akışını bozmamak için). Production'a geçerken bu stub
düşer; IyzicoAdapter ile aynı "credential → real API, yok → stub" deseni.
"""
import json
import logging
import uuid

import requests

from .base import BaseEArsivAdapter, IssueReceiptRequest, IssueReceiptResult

_logger = logging.getLogger(__name__)

SANDBOX_BASE_URL = "https://efatura-test.foriba.com"
PROD_BASE_URL = "https://efatura.foriba.com"

REQUEST_TIMEOUT = 10  # saniye — fail-close için kısa tutuyoruz.


class ForibaEArsivAdapter(BaseEArsivAdapter):
    code = "foriba"

    @property
    def base_url(self) -> str:
        if self.provider.base_url:
            return self.provider.base_url.rstrip("/")
        return SANDBOX_BASE_URL if self.is_sandbox else PROD_BASE_URL

    def _has_credentials(self) -> bool:
        return bool(
            (self.provider.api_key and self.provider.api_secret)
            or (self.provider.api_username and self.provider.api_password)
        )

    def issue_receipt(self, req: IssueReceiptRequest) -> IssueReceiptResult:
        if not self._has_credentials():
            _logger.warning(
                "foriba credentials missing, returning stub receipt for order %s",
                req.order_ref,
            )
            return self._stub_result(req, reason="credentials_missing")

        payload = self._build_payload(req)
        try:
            response = requests.post(
                f"{self.base_url}/earsiv/api/invoice",
                json=payload,
                auth=(self.provider.api_username or "",
                      self.provider.api_password or ""),
                headers={
                    "X-API-Key": self.provider.api_key or "",
                    "Content-Type": "application/json",
                },
                timeout=REQUEST_TIMEOUT,
            )
        except requests.Timeout:
            return IssueReceiptResult(
                ok=False,
                error_code="timeout",
                error_message=f"Foriba {REQUEST_TIMEOUT}s içinde yanıt vermedi",
                retryable=True,
            )
        except requests.RequestException as e:
            return IssueReceiptResult(
                ok=False,
                error_code="network_error",
                error_message=str(e),
                retryable=True,
            )

        try:
            data = response.json()
        except ValueError:
            return IssueReceiptResult(
                ok=False,
                error_code="bad_json",
                error_message=response.text[:200],
                retryable=False,
            )

        if response.status_code >= 500:
            return IssueReceiptResult(
                ok=False,
                raw=data,
                error_code=f"server_{response.status_code}",
                error_message=data.get("message") or "Foriba sunucu hatası",
                retryable=True,
            )
        if response.status_code >= 400:
            return IssueReceiptResult(
                ok=False,
                raw=data,
                error_code=data.get("errorCode") or f"http_{response.status_code}",
                error_message=data.get("message") or "Foriba doğrulama hatası",
                retryable=False,  # 4xx → payload hatalı, retry anlamsız
            )

        return IssueReceiptResult(
            ok=True,
            ettn=data.get("ettn"),
            pdf_url=data.get("pdfUrl"),
            qr_content=data.get("qrContent"),
            raw=data,
        )

    def cancel_receipt(self, ettn: str, reason: str) -> IssueReceiptResult:
        if not self._has_credentials():
            return IssueReceiptResult(
                ok=True, ettn=ettn,
                raw={"stub": True, "cancelled": True, "reason": reason},
            )
        try:
            response = requests.post(
                f"{self.base_url}/earsiv/api/invoice/{ettn}/cancel",
                json={"reason": reason},
                auth=(self.provider.api_username or "",
                      self.provider.api_password or ""),
                headers={"X-API-Key": self.provider.api_key or ""},
                timeout=REQUEST_TIMEOUT,
            )
            data = response.json() if response.content else {}
        except requests.RequestException as e:
            return IssueReceiptResult(
                ok=False, error_code="network_error",
                error_message=str(e), retryable=True,
            )
        if response.status_code >= 400:
            return IssueReceiptResult(
                ok=False, raw=data,
                error_code=data.get("errorCode") or f"http_{response.status_code}",
                error_message=data.get("message", ""),
                retryable=response.status_code >= 500,
            )
        return IssueReceiptResult(ok=True, ettn=ettn, raw=data)

    # ---- helpers --------------------------------------------------------
    def _stub_result(self, req: IssueReceiptRequest, reason: str) -> IssueReceiptResult:
        ettn = str(uuid.uuid4()).upper()
        return IssueReceiptResult(
            ok=True,
            ettn=ettn,
            pdf_url=f"/hashtap/receipt/{req.receipt_id}/pdf",
            qr_content=(
                f"https://efatura.foriba.com/earsiv/verify?ettn={ettn}&stub=1"
            ),
            raw={"stub": True, "reason": reason, "ettn": ettn},
        )

    def _build_payload(self, req: IssueReceiptRequest) -> dict:
        """Foriba e-Arşiv JSON şeması.

        NOT: gerçek alan isimleri Foriba dokümanıyla doğrulanmalı. Aşağıdaki
        şema `docs/integrations/E_ARSIV.md` §6 tablosunu baz alır.
        """
        price_str = f"{req.amount_kurus / 100:.2f}"
        return {
            "invoiceNumber": req.order_ref,
            "invoiceDate": None,  # Provider sunucu saatini kullanır
            "invoiceType": "EARSIVFATURA",
            "currency": req.currency,
            "seller": {"vkn": req.seller_vkn},
            "buyer": {
                "vkn": req.buyer_vkn or "11111111111",
                "name": req.buyer_name or "Genel Müşteri",
            },
            "lines": [
                {
                    "name": ln.get("name"),
                    "quantity": ln.get("quantity"),
                    "unitPrice": f"{(ln.get('unit_price_kurus') or 0) / 100:.2f}",
                    "totalPrice": f"{(ln.get('total_kurus') or 0) / 100:.2f}",
                    "vatRate": ln.get("tax_rate") or 10,
                }
                for ln in req.lines
            ],
            "totalAmount": price_str,
        }
