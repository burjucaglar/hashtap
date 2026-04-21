"""Ödeme akışı endpoint'leri.

Akış:
  1. PWA sepeti gönderir → /hashtap/order → order (payment_state=unpaid)
  2. Müşteri metot seçer → /hashtap/payment/init
     - Online metot: provider adapter init_payment → 3DS redirect URL döner,
       transaction pending olur.
     - Offline metot (pay_at_counter / cash): order.payment_state=pending,
       restoran kasada onaylar.
  3. 3DS sonrası iyzico callback_url'ine GET/POST döner →
     /hashtap/payment/callback/<provider>?token=... → transaction captured,
     order.payment_state=paid, order.state=paid.
  4. (Redundant ama güvenli) Sağlayıcı webhook /hashtap/payment/webhook/<provider>
     HMAC doğrulaması ile aynı capture'ı idempotent şekilde tekrarlar.
"""
import json
import logging

from odoo import http
from odoo.http import request

from ..adapters.base import InitPaymentRequest
from ..adapters.registry import get_adapter
from ..models.hashtap_payment_method import ONLINE_METHODS

_logger = logging.getLogger(__name__)


def _json(payload, status=200):
    return request.make_json_response(payload, status=status)


def _build_callback_url(base_url, provider_code, token):
    return (
        f"{base_url.rstrip('/')}/hashtap/payment/callback/"
        f"{provider_code}?token={token}"
    )


def _resolve_method(method_code, company):
    return request.env["hashtap.payment.method"].sudo().search(
        [("company_id", "=", company.id),
         ("code", "=", method_code),
         ("active", "=", True)],
        limit=1,
    )


def _resolve_provider_for_method(method):
    if method.provider_id and method.provider_id.active:
        return method.provider_id
    return request.env["hashtap.payment.provider"].sudo().resolve_active(
        company=method.company_id
    )


class HashTapPayment(http.Controller):
    """Ödeme başlatma + callback + webhook.

    Güvenlik notları:
      - Kredi kartı bilgisi HashTap'e hiç değmez; PWA iyzico'nun hosted
        3DS formuna redirect olur.
      - Callback query-string'indeki `token` sunucuda transaction.callback_token
        ile eşleşmeli — başka bir müşterinin transaction'ını kapatmak
        mümkün değil.
      - Webhook: HMAC imzası doğrulanmadan state ilerletilmez.
      - Idempotency: aynı provider_ref ile gelen ikinci callback yeni
        capture tetiklemez.
    """

    # ---------------------------------------------------------- init ----
    @http.route(
        "/hashtap/payment/methods/<string:tenant_slug>",
        type="http", auth="public", methods=["GET"], csrf=False,
    )
    def list_methods(self, tenant_slug, **kw):
        icp = request.env["ir.config_parameter"].sudo()
        expected = icp.get_param("hashtap.tenant_slug", "default")
        if tenant_slug != expected:
            return _json({"error": "tenant_not_found"}, status=404)
        amount = int(kw.get("amount_kurus") or 0)
        methods = request.env["hashtap.payment.method"].sudo().list_for_tenant(
            amount_kurus=amount,
        )
        return _json({"methods": methods})

    @http.route(
        "/hashtap/payment/init",
        type="json", auth="public", methods=["POST"], csrf=False,
    )
    def init_payment(self, order_id=None, method_code=None,
                     return_base_url=None, customer=None, **_kw):
        if not isinstance(order_id, int) or not method_code:
            return {"error": "bad_request"}

        order = request.env["hashtap.order"].sudo().browse(order_id).exists()
        if not order:
            return {"error": "order_not_found"}
        if order.payment_state == "paid":
            return {"error": "already_paid"}
        if order.total_kurus <= 0:
            return {"error": "empty_order"}

        method = _resolve_method(method_code, order.company_id)
        if not method:
            return {"error": "method_not_allowed"}

        order.payment_method_code = method.code

        if method.code not in ONLINE_METHODS:
            # Kasada ödeme: online akış yok, restoran operatörü kasada
            # manuel onaylayınca `action_mark_paid` çağrılır.
            order.payment_state = "pending"
            return {
                "mode": "offline",
                "order_id": order.id,
                "payment_state": order.payment_state,
                "method_code": method.code,
            }

        provider = _resolve_provider_for_method(method)
        if not provider:
            return {"error": "provider_not_configured"}

        Tx = request.env["hashtap.payment.transaction"].sudo()
        callback_token = Tx.new_callback_token()
        conversation_id = f"order-{order.id}-{callback_token[:10]}"
        tx = Tx.create({
            "order_id": order.id,
            "provider_id": provider.id,
            "method_code": method.code,
            "state": "pending",
            "amount_kurus": order.total_kurus,
            "currency": order.currency,
            "callback_token": callback_token,
            "conversation_id": conversation_id,
        })

        base = (return_base_url
                or request.env["ir.config_parameter"].sudo().get_param(
                    "hashtap.pwa_base_url", request.httprequest.host_url.rstrip("/"),
                ))
        callback_url = _build_callback_url(
            request.httprequest.host_url.rstrip("/"),
            provider.code,
            callback_token,
        )

        items = [{
            "id": l.item_id.id,
            "name": l.item_name,
            "price_kurus": l.subtotal_kurus,
        } for l in order.line_ids]

        adapter = get_adapter(provider)
        try:
            result = adapter.init_payment(InitPaymentRequest(
                transaction_id=tx.id,
                order_id=order.id,
                amount_kurus=order.total_kurus,
                currency=order.currency,
                method_code=method.code,
                callback_url=callback_url,
                conversation_id=conversation_id,
                customer=customer or {},
                items=items,
            ))
        except Exception:  # noqa: BLE001
            _logger.exception("payment init crashed")
            tx.mark_failed(error_code="adapter_crash",
                           error_message="adapter raised")
            return {"error": "adapter_crash"}

        if not result.ok:
            tx.mark_failed(
                error_code=result.error_code or "init_failed",
                error_message=result.error_message or "",
                raw_response=json.dumps(result.raw) if result.raw else None,
            )
            order.payment_state = "failed"
            return {"error": result.error_code or "init_failed"}

        tx.write({
            "provider_ref": result.provider_ref,
            "threeds_redirect_url": result.threeds_redirect_url,
            "raw_response": json.dumps(result.raw) if result.raw else None,
        })
        order.payment_state = "pending"

        return {
            "mode": "online",
            "order_id": order.id,
            "transaction_id": tx.id,
            "redirect_url": result.threeds_redirect_url,
            "return_url": (
                f"{base.rstrip('/')}/order/{order.id}"
            ),
        }

    # ------------------------------------------------------ callback ----
    @http.route(
        "/hashtap/payment/callback/<string:provider_code>",
        type="http", auth="public", methods=["GET", "POST"], csrf=False,
    )
    def callback(self, provider_code, **params):
        token = params.get("token")
        if not token:
            return _json({"error": "missing_token"}, status=400)

        tx = request.env["hashtap.payment.transaction"].sudo().search(
            [("callback_token", "=", token)], limit=1,
        )
        if not tx or tx.provider_id.code != provider_code:
            return _json({"error": "transaction_not_found"}, status=404)

        # Idempotency: zaten captured/failed ise terminal durumu dön.
        if tx.state in ("captured", "failed", "refunded"):
            return self._callback_redirect(tx)

        adapter = get_adapter(tx.provider_id)
        try:
            result = adapter.handle_callback({
                **params,
                "conversation_id": tx.conversation_id,
                "provider_ref": tx.provider_ref,
            })
        except Exception:  # noqa: BLE001
            _logger.exception("payment callback crashed")
            tx.mark_failed(error_code="adapter_crash",
                           error_message="adapter raised")
            return self._callback_redirect(tx)

        if result.ok and result.captured:
            tx.mark_captured(
                provider_ref=result.provider_ref or tx.provider_ref,
                raw_response=json.dumps(result.raw) if result.raw else None,
            )
        else:
            tx.mark_failed(
                error_code=result.error_code or "declined",
                error_message=result.error_message or "",
                raw_response=json.dumps(result.raw) if result.raw else None,
            )
        return self._callback_redirect(tx)

    def _callback_redirect(self, tx):
        base = request.env["ir.config_parameter"].sudo().get_param(
            "hashtap.pwa_base_url", request.httprequest.host_url.rstrip("/"),
        )
        target = f"{base.rstrip('/')}/order/{tx.order_id.id}"
        return request.redirect(target, local=False)

    # ------------------------------------------------------- webhook ----
    @http.route(
        "/hashtap/payment/webhook/<string:provider_code>",
        type="http", auth="public", methods=["POST"], csrf=False,
    )
    def webhook(self, provider_code, **_kw):
        raw = request.httprequest.get_data(cache=False, as_text=False) or b""
        provider = request.env["hashtap.payment.provider"].sudo().search(
            [("code", "=", provider_code), ("active", "=", True)], limit=1,
        )
        if not provider:
            return _json({"error": "provider_not_found"}, status=404)

        adapter = get_adapter(provider)
        headers = {k: v for k, v in request.httprequest.headers.items()}
        if not adapter.verify_webhook(raw, headers):
            _logger.warning("webhook signature invalid for %s", provider_code)
            return _json({"error": "invalid_signature"}, status=401)

        try:
            result = adapter.parse_webhook(raw, headers)
        except Exception:  # noqa: BLE001
            _logger.exception("webhook parse crashed")
            return _json({"error": "bad_payload"}, status=400)

        if not result.provider_ref:
            return _json({"error": "missing_provider_ref"}, status=400)

        tx = request.env["hashtap.payment.transaction"].sudo().search(
            [("provider_id", "=", provider.id),
             ("provider_ref", "=", result.provider_ref)],
            limit=1,
        )
        if not tx:
            # Bazı sağlayıcılar webhook'u callback'ten önce gönderebilir.
            # conversation_id üzerinden dene.
            if result.conversation_id:
                tx = request.env["hashtap.payment.transaction"].sudo().search(
                    [("conversation_id", "=", result.conversation_id)], limit=1,
                )
        if not tx:
            return _json({"error": "transaction_not_found"}, status=404)

        if tx.state == "captured" and result.captured:
            # Idempotent: aynı capture iki kez.
            return _json({"status": "ok", "already": True})

        if result.captured:
            tx.mark_captured(
                provider_ref=result.provider_ref,
                raw_response=json.dumps(result.raw) if result.raw else None,
            )
        else:
            tx.mark_failed(
                error_code=result.error_code or "declined",
                error_message=result.error_message or "",
                raw_response=json.dumps(result.raw) if result.raw else None,
            )
        return _json({"status": "ok"})

    # ----------------------------------------------- mock simulator ----
    @http.route(
        "/hashtap/payment/mock/simulator",
        type="http", auth="public", methods=["GET"], csrf=False,
    )
    def mock_simulator(self, token=None, amount_kurus="0", **_kw):
        """Demo 3DS sayfası — yalnızca Mock provider için.

        iyzico/fatih gibi gerçek sağlayıcılar kendi hosted 3DS formunu
        gösterir. Mock'ta o akışı taklit etmek için bu sayfa devreye
        giriyor: kullanıcı "Onayla" → callback?result=success,
        "Reddet" → callback?result=fail.
        """
        if not token:
            return _json({"error": "missing_token"}, status=400)
        tx = request.env["hashtap.payment.transaction"].sudo().search(
            [("callback_token", "=", token)], limit=1,
        )
        if not tx or tx.provider_id.code != "mock":
            return _json({"error": "transaction_not_found"}, status=404)
        try:
            amount_try = int(amount_kurus or 0) / 100
        except (TypeError, ValueError):
            amount_try = 0
        order_ref = tx.order_id.name or f"#{tx.order_id.id}"
        html = f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Mock 3DS · HashTap</title>
<style>
  html,body{{margin:0;background:#f5f2eb;font-family:'Georgia',serif;color:#292524;}}
  .wrap{{max-width:420px;margin:0 auto;padding:48px 24px;}}
  .tag{{font-size:10px;letter-spacing:.25em;text-transform:uppercase;color:#a8a29e;text-align:center;}}
  h1{{font-style:italic;font-size:2rem;text-align:center;margin:.5rem 0 1rem;}}
  .rule{{width:40px;height:1px;background:#d6d3d1;margin:0 auto 2rem;}}
  .row{{display:flex;justify-content:space-between;border-top:2px solid #1c1917;padding-top:12px;margin:1.5rem 0;}}
  .row span:first-child{{font-size:11px;letter-spacing:.25em;text-transform:uppercase;color:#78716c;}}
  .row span:last-child{{font-size:1.75rem;}}
  .note{{font-style:italic;text-align:center;color:#78716c;margin:1.5rem 0;font-size:.9rem;}}
  form{{margin:0;}}
  .btn{{display:block;width:100%;padding:14px;font-size:1.1rem;font-style:italic;border:0;cursor:pointer;margin-bottom:12px;}}
  .btn-ok{{background:#1c1917;color:#fff;}}
  .btn-ok:hover{{background:#292524;}}
  .btn-no{{background:transparent;color:#991b1b;border:1px solid #d6d3d1;}}
  .btn-no:hover{{border-color:#991b1b;}}
  .foot{{text-align:center;font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:#a8a29e;margin-top:2rem;}}
</style>
</head>
<body>
  <div class="wrap">
    <p class="tag">Mock 3DS Simülatörü</p>
    <h1>Kart Onayı</h1>
    <div class="rule"></div>
    <p class="note">Bu sayfa yalnızca geliştirme içindir. Gerçek bir ödeme gerçekleşmez.</p>
    <div class="row"><span>Sipariş</span><span>{order_ref}</span></div>
    <div class="row"><span>Tutar</span><span>{amount_try:,.2f} ₺</span></div>
    <form method="get" action="/hashtap/payment/callback/mock">
      <input type="hidden" name="token" value="{token}" />
      <input type="hidden" name="result" value="success" />
      <button class="btn btn-ok" type="submit">Onayla</button>
    </form>
    <form method="get" action="/hashtap/payment/callback/mock">
      <input type="hidden" name="token" value="{token}" />
      <input type="hidden" name="result" value="fail" />
      <button class="btn btn-no" type="submit">Reddet</button>
    </form>
    <p class="foot">HashTap · Dev Mode</p>
  </div>
</body>
</html>"""
        return request.make_response(html, headers=[
            ("Content-Type", "text/html; charset=utf-8"),
            ("Cache-Control", "no-store"),
        ])

    # --------------------------------------------------------- status ---
    @http.route(
        "/hashtap/payment/transaction/<int:tx_id>",
        type="http", auth="public", methods=["GET"], csrf=False,
    )
    def transaction_status(self, tx_id, **_kw):
        tx = request.env["hashtap.payment.transaction"].sudo().browse(tx_id).exists()
        if not tx:
            return _json({"error": "transaction_not_found"}, status=404)
        return _json({
            "id": tx.id,
            "state": tx.state,
            "order_id": tx.order_id.id,
            "amount_kurus": tx.amount_kurus,
            "currency": tx.currency,
            "method_code": tx.method_code,
            "redirect_url": tx.threeds_redirect_url or "",
            "error_code": tx.error_code or "",
        })
