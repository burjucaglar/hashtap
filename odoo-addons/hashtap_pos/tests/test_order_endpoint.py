import json

from odoo.tests import HttpCase, tagged


@tagged("-at_install", "post_install", "hashtap_order")
class TestOrderEndpoint(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env["ir.config_parameter"].sudo()
        icp.set_param("hashtap.tenant_slug", "testco")
        icp.set_param("hashtap.pwa_base_url", "https://test.example.com")

        cls.env["hashtap.order.line"].search([]).unlink()
        cls.env["hashtap.order"].search([]).unlink()
        cls.env["hashtap.menu.item"].search([]).unlink()
        cls.env["hashtap.menu.category"].search([]).unlink()
        cls.env["hashtap.modifier"].search([]).unlink()
        cls.env["hashtap.modifier.group"].search([]).unlink()

        product_a = cls.env["product.template"].create({
            "name": "Pide", "list_price": 180.0, "type": "consu",
        })
        product_b = cls.env["product.template"].create({
            "name": "Ayran", "list_price": 35.0, "type": "consu",
        })
        cat = cls.env["hashtap.menu.category"].create({
            "name_tr": "Anayemek", "name_en": "Main",
        })
        cls.mod_group = cls.env["hashtap.modifier.group"].create({
            "name_tr": "Ekstra", "name_en": "Extra",
            "min_select": 0, "max_select": 2,
            "modifier_ids": [
                (0, 0, {"name_tr": "Kaşar", "name_en": "Cheese", "price_delta": 20}),
                (0, 0, {"name_tr": "Sucuk", "name_en": "Sausage", "price_delta": 30}),
            ],
        })
        cls.item_pide = cls.env["hashtap.menu.item"].create({
            "product_tmpl_id": product_a.id,
            "category_id": cat.id,
            "name_tr": "Pide", "name_en": "Pide",
            "modifier_group_ids": [(6, 0, [cls.mod_group.id])],
        })
        cls.item_ayran = cls.env["hashtap.menu.item"].create({
            "product_tmpl_id": product_b.id,
            "category_id": cat.id,
            "name_tr": "Ayran", "name_en": "Ayran",
        })

        floor = cls.env["restaurant.floor"].create({"name": "F"})
        cls.table = cls.env["restaurant.table"].create({
            "name": "T", "floor_id": floor.id, "identifier": "T",
        })

    def _post(self, payload):
        return self.url_open(
            "/hashtap/order",
            data=json.dumps({"jsonrpc": "2.0", "params": payload}),
            headers={"Content-Type": "application/json"},
        )

    def test_happy_path_server_computes_price(self):
        resp = self._post({
            "tenant_slug": "testco",
            "table_slug": self.table.hashtap_qr_slug,
            "items": [
                {"item_id": self.item_pide.id, "quantity": 2},
                {"item_id": self.item_ayran.id, "quantity": 3},
            ],
        })
        self.assertEqual(resp.status_code, 200)
        body = resp.json()["result"]
        self.assertIn("order", body)
        order = body["order"]
        # 2*18000 + 3*3500 = 36000 + 10500 = 46500
        self.assertEqual(order["subtotal_kurus"], 46500)
        self.assertEqual(order["total_kurus"], 46500)
        self.assertEqual(order["state"], "placed")
        self.assertEqual(len(order["lines"]), 2)

    def test_modifier_price_added(self):
        mod_ids = self.mod_group.modifier_ids.ids
        resp = self._post({
            "tenant_slug": "testco",
            "table_slug": self.table.hashtap_qr_slug,
            "items": [{
                "item_id": self.item_pide.id,
                "quantity": 1,
                "modifier_ids": mod_ids,  # +20 + +30 = +50
            }],
        })
        body = resp.json()["result"]
        self.assertIn("order", body)
        # 1 * (18000 + 5000) = 23000
        self.assertEqual(body["order"]["total_kurus"], 23000)

    def test_client_price_is_ignored(self):
        resp = self._post({
            "tenant_slug": "testco",
            "table_slug": self.table.hashtap_qr_slug,
            "items": [{
                "item_id": self.item_ayran.id,
                "quantity": 1,
                "unit_price_kurus": 1,  # PWA "hile" denemesi
            }],
        })
        body = resp.json()["result"]
        # Server yine de kendi fiyatını koyar: 3500
        self.assertEqual(body["order"]["total_kurus"], 3500)

    def test_unknown_tenant(self):
        resp = self._post({
            "tenant_slug": "wrongco",
            "table_slug": self.table.hashtap_qr_slug,
            "items": [{"item_id": self.item_ayran.id, "quantity": 1}],
        })
        self.assertEqual(resp.json()["result"], {"error": "tenant_not_found"})

    def test_unknown_item(self):
        resp = self._post({
            "tenant_slug": "testco",
            "table_slug": self.table.hashtap_qr_slug,
            "items": [{"item_id": 99999, "quantity": 1}],
        })
        self.assertEqual(resp.json()["result"]["error"], "item_not_found")

    def test_empty_cart(self):
        resp = self._post({
            "tenant_slug": "testco",
            "table_slug": self.table.hashtap_qr_slug,
            "items": [],
        })
        self.assertEqual(resp.json()["result"]["error"], "empty_cart")

    def test_modifier_from_wrong_group_rejected(self):
        resp = self._post({
            "tenant_slug": "testco",
            "table_slug": self.table.hashtap_qr_slug,
            "items": [{
                "item_id": self.item_ayran.id,  # ayran'ın modifieri yok
                "quantity": 1,
                "modifier_ids": [self.mod_group.modifier_ids[0].id],
            }],
        })
        self.assertEqual(resp.json()["result"]["error"], "modifier_not_allowed")

    def test_concurrent_orders_get_separate_ids(self):
        slug = self.table.hashtap_qr_slug
        a = self._post({
            "tenant_slug": "testco", "table_slug": slug,
            "items": [{"item_id": self.item_ayran.id, "quantity": 1}],
        }).json()["result"]["order"]
        b = self._post({
            "tenant_slug": "testco", "table_slug": slug,
            "items": [{"item_id": self.item_ayran.id, "quantity": 2}],
        }).json()["result"]["order"]
        self.assertNotEqual(a["id"], b["id"])
        self.assertNotEqual(a["reference"], b["reference"])

    def test_get_order_status(self):
        posted = self._post({
            "tenant_slug": "testco",
            "table_slug": self.table.hashtap_qr_slug,
            "items": [{"item_id": self.item_ayran.id, "quantity": 1}],
        }).json()["result"]["order"]
        resp = self.url_open(f"/hashtap/order/{posted['id']}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["order"]["id"], posted["id"])

    def test_get_unknown_order_404(self):
        resp = self.url_open("/hashtap/order/999999")
        self.assertEqual(resp.status_code, 404)
