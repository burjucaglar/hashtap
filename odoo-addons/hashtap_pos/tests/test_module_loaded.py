from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged("-at_install", "post_install")
class TestModuleLoaded(TransactionCase):
    def test_module_is_installed(self):
        module = self.env["ir.module.module"].search(
            [("name", "=", "hashtap_pos")], limit=1
        )
        self.assertTrue(module, "hashtap_pos module record not found")
        self.assertEqual(module.state, "installed")
