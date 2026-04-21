from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("-at_install", "post_install")
class TestMenuModels(TransactionCase):
    def setUp(self):
        super().setUp()
        self.product = self.env["product.template"].create({
            "name": "Pide",
            "list_price": 180.0,
            "type": "consu",
        })
        self.category = self.env["hashtap.menu.category"].create({
            "name_tr": "Pideler",
            "name_en": "Pides",
        })

    def test_item_unique_product(self):
        from psycopg2 import IntegrityError
        from odoo.tools import mute_logger
        self.env["hashtap.menu.item"].create({
            "product_tmpl_id": self.product.id,
            "category_id": self.category.id,
            "name_tr": "Kaşarlı Pide",
            "name_en": "Cheese Pide",
        })
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.cr.savepoint():
                self.env["hashtap.menu.item"].create({
                    "product_tmpl_id": self.product.id,
                    "category_id": self.category.id,
                    "name_tr": "Duplicate",
                    "name_en": "Duplicate",
                })

    def test_item_rejects_service_product(self):
        service = self.env["product.template"].create({
            "name": "Servis",
            "type": "service",
            "list_price": 0,
        })
        with self.assertRaises(ValidationError):
            self.env["hashtap.menu.item"].create({
                "product_tmpl_id": service.id,
                "category_id": self.category.id,
                "name_tr": "X",
                "name_en": "X",
            })

    def test_category_time_window_constraint(self):
        with self.assertRaises(ValidationError):
            self.env["hashtap.menu.category"].create({
                "name_tr": "X",
                "name_en": "X",
                "available_from": 14.0,
                "available_to": 10.0,
            })

    def test_modifier_group_is_required_computed(self):
        g = self.env["hashtap.modifier.group"].create({
            "name_tr": "Soslar",
            "name_en": "Sauces",
            "min_select": 1,
            "max_select": 2,
        })
        self.assertTrue(g.is_required)
        g.min_select = 0
        self.assertFalse(g.is_required)

    def test_table_gets_unique_slug(self):
        floor = self.env["restaurant.floor"].create({"name": "F1"})
        t1 = self.env["restaurant.table"].create({
            "name": "A", "floor_id": floor.id, "identifier": "A",
        })
        t2 = self.env["restaurant.table"].create({
            "name": "B", "floor_id": floor.id, "identifier": "B",
        })
        self.assertTrue(t1.hashtap_qr_slug)
        self.assertTrue(t2.hashtap_qr_slug)
        self.assertNotEqual(t1.hashtap_qr_slug, t2.hashtap_qr_slug)
        self.assertEqual(len(t1.hashtap_qr_slug), 8)

    def test_table_qr_url_uses_config(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "hashtap.pwa_base_url", "https://r.test.com"
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "hashtap.tenant_slug", "demo"
        )
        floor = self.env["restaurant.floor"].create({"name": "F1"})
        t = self.env["restaurant.table"].create({
            "name": "C", "floor_id": floor.id, "identifier": "C",
        })
        self.assertEqual(
            t.hashtap_qr_url,
            f"https://r.test.com/r/demo/t/{t.hashtap_qr_slug}",
        )
