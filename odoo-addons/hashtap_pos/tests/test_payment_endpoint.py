import json

from odoo.tests import HttpCase, tagged


@tagged("-at_install", "post_install", "hashtap_payment")
class TestPaymentEndpoint(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env["ir.config_parameter"].sudo()
        icp.set_param("hashtap.tenant_slug", "testco")
        icp.set_param("hashtap.pwa_base_url", "https://test.example.com")

        cls.env["hashtap.payment.transaction"].search([]).unlink()
        cls.env["hashtap.order.line"].search([]).unlink()
        cls.env["hashtap.order"].search([]).unlink()
        cls.env["hashtap.payment.method"].search([]).unlink()
        cls.env["hashtap.payment.provider"].search([]).unlink()
        cls.env["hashtap.menu.item"].search([]).unlink()
        cls.env["hashtap.menu.category"].search([]).unlink()

        product = cls.env["product.template"].create({
            "name": "Burger", "list_price": 250.0, "type": "consu",
        })
        cat = cls.env["hashtap.menu.category"].create({
            "name_tr": "Anayemek", "name_en": "Main",
        })
        cls.item = cls.env["hashtap.menu.item"].create({
            "product_tmpl_id": product.id,
            "category_id": cat.id,
            "name_tr": "Burger", "name_en": "Burger",
        })

        floor = cls.env["restaurant.floor"].create({"name": "F"})
        cls.table = cls.env["restaurant.table"].create({
            "name": "P1", "floor_id": floor.id, "identifier": "P1",
        })

        cls.mock_provider = cls.env["hashtap.payment.provider"].create({
            "name": "Mock (test)",
            "code": "mock",
            "sandbox": True,
            "webhook_secret": "testsecret",
        })
        cls.card_method = cls.env["hashtap.payment.method"].create({
            "name": "Kart",
            "code": "card",
            "provider_id": cls.mock_provider.id,
        })
        cls.counter_method = cls.env["hashtap.payment.method"].create({
            "name": "Kasada",
            "code": "pay_at_counter",
        })

    # ---------------------------------------------------------- helpers
    def _create_order(self):
        resp = self.url_open(
            "/hashtap/order",
            data=json.dumps({
                "jsonrpc": "2.0",
                "params": {
                    "tenant_slug": "testco",
                    "table_slug": self.table.hashtap_qr_slug,
                    "items": [{"item_id": self.item.id, "quantity": 2}],
                },
            }),
            headers={"Content-Type": "application/json"},
        )
        return resp.json()["result"]["order"]

    def _init(self, order_id, method_code):
        resp = self.url_open(
            "/hashtap/payment/init",
            data=json.dumps({
                "jsonrpc": "2.0",
                "params": {
                    "order_id": order_id,
                    "method_code": method_code,
                    "return_base_url": "https://pwa.test",
                },
            }),
            headers={"Content-Type": "application/json"},
        )
        return resp.json()["result"]

    # ---------------------------------------------------------- tests --
    def test_list_methods_returns_active(self):
        resp = self.url_open("/hashtap/payment/methods/testco?amount_kurus=5000")
        body = resp.json()
        codes = {m["code"] for m in body["methods"]}
        self.assertIn("card", codes)
        self.assertIn("pay_at_counter", codes)

    def test_list_methods_wrong_tenant(self):
        resp = self.url_open("/hashtap/payment/methods/unknown")
        self.assertEqual(resp.status_code, 404)

    def test_init_online_creates_pending_tx(self):
        order = self._create_order()
        result = self._init(order["id"], "card")
        self.assertEqual(result["mode"], "online")
        self.assertTrue(result["redirect_url"])
        tx = self.env["hashtap.payment.transaction"].browse(result["transaction_id"])
        self.assertEqual(tx.state, "pending")
        self.assertTrue(tx.provider_ref.startswith("MOCK-"))
        self.assertEqual(tx.order_id.payment_state, "pending")

    def test_init_offline_sets_pending_no_tx(self):
        order = self._create_order()
        result = self._init(order["id"], "pay_at_counter")
        self.assertEqual(result["mode"], "offline")
        order_rec = self.env["hashtap.order"].browse(order["id"])
        self.assertEqual(order_rec.payment_state, "pending")
        self.assertFalse(order_rec.payment_transaction_ids)

    def test_callback_captures_and_marks_paid(self):
        order = self._create_order()
        result = self._init(order["id"], "card")
        tx = self.env["hashtap.payment.transaction"].browse(result["transaction_id"])
        resp = self.url_open(
            f"/hashtap/payment/callback/mock?token={tx.callback_token}",
            allow_redirects=False,
        )
        self.assertIn(resp.status_code, (302, 303))
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "captured")
        self.assertEqual(tx.order_id.payment_state, "paid")
        self.assertEqual(tx.order_id.state, "paid")
        self.assertEqual(tx.order_id.paid_amount_kurus, tx.amount_kurus)

    def test_callback_idempotent(self):
        order = self._create_order()
        result = self._init(order["id"], "card")
        tx = self.env["hashtap.payment.transaction"].browse(result["transaction_id"])
        for _ in range(2):
            self.url_open(
                f"/hashtap/payment/callback/mock?token={tx.callback_token}",
                allow_redirects=False,
            )
        tx.invalidate_recordset()
        self.assertEqual(tx.state, "captured")
        # Order fiyatı iki kez paid_amount'a eklenmez
        self.assertEqual(tx.order_id.paid_amount_kurus, tx.amount_kurus)

    def test_callback_wrong_token_404(self):
        resp = self.url_open(
            "/hashtap/payment/callback/mock?token=nonexistent",
            allow_redirects=False,
        )
        self.assertEqual(resp.status_code, 404)

    def test_init_unknown_method_rejected(self):
        order = self._create_order()
        result = self._init(order["id"], "bitcoin")
        self.assertEqual(result["error"], "method_not_allowed")

    def test_init_already_paid_rejected(self):
        order = self._create_order()
        order_rec = self.env["hashtap.order"].browse(order["id"])
        order_rec.payment_state = "paid"
        result = self._init(order["id"], "card")
        self.assertEqual(result["error"], "already_paid")

    def test_webhook_invalid_signature_rejected(self):
        resp = self.url_open(
            "/hashtap/payment/webhook/mock",
            data=json.dumps({"provider_ref": "X"}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_offline_mark_paid_action(self):
        order = self._create_order()
        self._init(order["id"], "pay_at_counter")
        order_rec = self.env["hashtap.order"].browse(order["id"])
        order_rec.action_mark_paid_offline()
        self.assertEqual(order_rec.payment_state, "paid")
        self.assertEqual(order_rec.state, "paid")
