import json

from odoo.tests import HttpCase, tagged


@tagged("-at_install", "post_install", "hashtap_earsiv")
class TestEArsivFlow(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env["ir.config_parameter"].sudo()
        icp.set_param("hashtap.tenant_slug", "testco")
        icp.set_param("hashtap.pwa_base_url", "https://test.example.com")

        cls.env["hashtap.earsiv.receipt"].search([]).unlink()
        cls.env["hashtap.earsiv.provider"].search([]).unlink()
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
            "name_tr": "Ana", "name_en": "Main",
        })
        cls.item = cls.env["hashtap.menu.item"].create({
            "product_tmpl_id": product.id,
            "category_id": cat.id,
            "name_tr": "Burger", "name_en": "Burger",
        })
        floor = cls.env["restaurant.floor"].create({"name": "F"})
        cls.table = cls.env["restaurant.table"].create({
            "name": "E1", "floor_id": floor.id, "identifier": "E1",
        })

        cls.mock_pay = cls.env["hashtap.payment.provider"].create({
            "name": "Mock (pay)",
            "code": "mock",
            "sandbox": True,
            "webhook_secret": "testsecret",
        })
        cls.card_method = cls.env["hashtap.payment.method"].create({
            "name": "Kart",
            "code": "card",
            "provider_id": cls.mock_pay.id,
        })

        cls.env.company.vat = "1234567890"
        cls.earsiv_provider = cls.env["hashtap.earsiv.provider"].create({
            "name": "Mock e-Arşiv",
            "code": "mock",
            "sandbox": True,
            "seller_vkn": "1234567890",
            "mock_fail_rate": 0,
        })

    # ------------------------------------------------------------ helpers
    def _create_and_pay(self):
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
        order = resp.json()["result"]["order"]
        init = self.url_open(
            "/hashtap/payment/init",
            data=json.dumps({
                "jsonrpc": "2.0",
                "params": {
                    "order_id": order["id"],
                    "method_code": "card",
                    "return_base_url": "https://pwa.test",
                },
            }),
            headers={"Content-Type": "application/json"},
        ).json()["result"]
        tx = self.env["hashtap.payment.transaction"].browse(init["transaction_id"])
        self.url_open(
            f"/hashtap/payment/callback/mock?token={tx.callback_token}",
            allow_redirects=False,
        )
        return self.env["hashtap.order"].browse(order["id"])

    # ------------------------------------------------------------- happy path
    def test_payment_capture_issues_receipt_and_fires_kitchen(self):
        order = self._create_and_pay()
        order.invalidate_recordset()
        self.assertEqual(order.payment_state, "paid")
        self.assertEqual(order.earsiv_state, "issued")
        self.assertTrue(order.earsiv_receipt_id)
        self.assertTrue(order.earsiv_receipt_id.ettn)
        self.assertEqual(order.state, "kitchen_sent")
        self.assertFalse(order.is_earsiv_blocked)

    # ------------------------------------------------------------- fail-close
    def test_receipt_failure_blocks_kitchen(self):
        self.earsiv_provider.mock_fail_rate = 100
        order = self._create_and_pay()
        order.invalidate_recordset()
        self.assertEqual(order.payment_state, "paid")
        self.assertEqual(order.earsiv_state, "failed")
        self.assertEqual(order.state, "paid")  # mutfağa gitmedi
        self.assertTrue(order.is_earsiv_blocked)

    def test_manual_kitchen_send_blocked_when_receipt_failed(self):
        from odoo.exceptions import ValidationError
        self.earsiv_provider.mock_fail_rate = 100
        order = self._create_and_pay()
        order.invalidate_recordset()
        with self.assertRaises(ValidationError):
            order.action_mark_kitchen_sent()

    # ------------------------------------------------------------- retry
    def test_retry_after_failure_fires_kitchen(self):
        self.earsiv_provider.mock_fail_rate = 100
        order = self._create_and_pay()
        order.invalidate_recordset()
        self.assertEqual(order.earsiv_state, "failed")

        self.earsiv_provider.mock_fail_rate = 0
        order.action_retry_earsiv()
        order.invalidate_recordset()
        self.assertEqual(order.earsiv_state, "issued")
        self.assertEqual(order.state, "kitchen_sent")

    # ------------------------------------------------------------- no provider
    def test_no_provider_marks_failed(self):
        self.earsiv_provider.active = False
        order = self._create_and_pay()
        order.invalidate_recordset()
        self.assertEqual(order.earsiv_state, "failed")
        self.assertEqual(order.state, "paid")
        self.assertTrue(order.is_earsiv_blocked)

    # ------------------------------------------------------------- opt-out
    def test_require_receipt_false_skips_earsiv(self):
        resp = self.url_open(
            "/hashtap/order",
            data=json.dumps({
                "jsonrpc": "2.0",
                "params": {
                    "tenant_slug": "testco",
                    "table_slug": self.table.hashtap_qr_slug,
                    "items": [{"item_id": self.item.id, "quantity": 1}],
                },
            }),
            headers={"Content-Type": "application/json"},
        )
        order_id = resp.json()["result"]["order"]["id"]
        order = self.env["hashtap.order"].browse(order_id)
        order.require_receipt = False

        init = self.url_open(
            "/hashtap/payment/init",
            data=json.dumps({
                "jsonrpc": "2.0",
                "params": {"order_id": order_id, "method_code": "card"},
            }),
            headers={"Content-Type": "application/json"},
        ).json()["result"]
        tx = self.env["hashtap.payment.transaction"].browse(init["transaction_id"])
        self.url_open(
            f"/hashtap/payment/callback/mock?token={tx.callback_token}",
            allow_redirects=False,
        )
        order.invalidate_recordset()
        self.assertEqual(order.payment_state, "paid")
        self.assertEqual(order.earsiv_state, "not_required")
        self.assertEqual(order.state, "kitchen_sent")
        self.assertFalse(order.earsiv_receipt_id)
