from odoo.tests import HttpCase, tagged


@tagged("-at_install", "post_install", "hashtap_menu")
class TestMenuEndpoint(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param(
            "hashtap.tenant_slug", "testco"
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "hashtap.pwa_base_url", "https://test.example.com"
        )

        cls.env["hashtap.order.line"].search([]).unlink()
        cls.env["hashtap.order"].search([]).unlink()
        cls.env["hashtap.menu.item"].search([]).unlink()
        cls.env["hashtap.menu.category"].search([]).unlink()

        product = cls.env["product.template"].create({
            "name": "Hummus",
            "list_price": 125.0,
            "type": "consu",
        })
        category = cls.env["hashtap.menu.category"].create({
            "name_tr": "Başlangıçlar",
            "name_en": "Starters",
            "sequence": 1,
        })
        cls.item = cls.env["hashtap.menu.item"].create({
            "product_tmpl_id": product.id,
            "category_id": category.id,
            "name_tr": "Humus",
            "name_en": "Hummus",
            "description_tr": "Klasik nohut ezmesi",
            "description_en": "Classic chickpea spread",
            "prep_time_minutes": 8,
        })

        floor = cls.env["restaurant.floor"].create({"name": "Test Floor"})
        cls.table = cls.env["restaurant.table"].create({
            "name": "Test T1",
            "floor_id": floor.id,
            "identifier": "T1",
        })

    def test_menu_endpoint_returns_expected_shape(self):
        self.assertTrue(self.table.hashtap_qr_slug, "Masa oluştururken slug üretilmeli")
        resp = self.url_open(
            f"/hashtap/menu/testco/{self.table.hashtap_qr_slug}"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()

        self.assertEqual(body["tenant"]["slug"], "testco")
        self.assertEqual(body["table"]["slug"], self.table.hashtap_qr_slug)

        self.assertEqual(len(body["categories"]), 1)
        cat = body["categories"][0]
        self.assertEqual(cat["name"]["tr"], "Başlangıçlar")
        self.assertEqual(cat["name"]["en"], "Starters")

        self.assertEqual(len(cat["items"]), 1)
        item = cat["items"][0]
        self.assertEqual(item["name"]["tr"], "Humus")
        self.assertEqual(item["name"]["en"], "Hummus")
        self.assertEqual(item["price_kurus"], 12500)
        self.assertEqual(item["prep_time_minutes"], 8)
        self.assertEqual(item["description"]["tr"], "Klasik nohut ezmesi")

    def test_unknown_tenant_returns_404(self):
        resp = self.url_open(
            f"/hashtap/menu/wrongco/{self.table.hashtap_qr_slug}"
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["error"], "tenant_not_found")

    def test_unknown_table_returns_404(self):
        resp = self.url_open("/hashtap/menu/testco/nonexistent99")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["error"], "table_not_found")

    def test_disabled_table_returns_404(self):
        self.table.hashtap_enabled = False
        resp = self.url_open(
            f"/hashtap/menu/testco/{self.table.hashtap_qr_slug}"
        )
        self.assertEqual(resp.status_code, 404)
