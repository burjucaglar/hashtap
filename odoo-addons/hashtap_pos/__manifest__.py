{
    "name": "HashTap POS",
    "version": "17.0.1.0.0",
    "category": "Point of Sale",
    "summary": "QR sipariş, mobil ödeme ve restoran operasyonu için HashTap genişletmesi",
    "description": """
HashTap POS
===========
Odoo 17 üzerine QR menü + mobil ödeme + e-Arşiv akışını ekler.
Detay: docs/MODULE_DESIGN.md
""",
    "author": "HashTap",
    "website": "https://example.com",
    "license": "LGPL-3",
    "depends": [
        "base",
        "web",
        "point_of_sale",
        "pos_restaurant",
        "account",
        "stock",
        "hashtap_theme",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "data/payment_method_data.xml",
        "views/menu_root.xml",
        "views/hashtap_menu_views.xml",
        "views/hashtap_table_views.xml",
        "views/hashtap_order_views.xml",
        "views/hashtap_payment_views.xml",
        "views/hashtap_earsiv_views.xml",
        "views/hashtap_kds_templates.xml",
        "views/hashtap_kds_menu.xml",
    ],
    "external_dependencies": {
        "python": ["requests"],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}
