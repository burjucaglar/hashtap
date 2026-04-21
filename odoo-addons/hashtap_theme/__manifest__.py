{
    "name": "HashTap Theme",
    "version": "17.0.1.0.0",
    "category": "Theme",
    "summary": "HashTap white-label: logo, renk, login, PDF layout, navbar override",
    "description": """
HashTap Theme
=============
Odoo 17 CE üzerinde HashTap markasını uygular. Sadece sunum — iş mantığı
``hashtap_pos`` modülünde. Detay: docs/WHITE_LABEL.md.
""",
    "author": "HashTap",
    "website": "https://example.com",
    "license": "LGPL-3",
    "depends": [
        "base",
        "web",
    ],
    "data": [
        "views/webclient_templates.xml",
        "views/login_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "hashtap_theme/static/src/scss/_variables.scss",
            "hashtap_theme/static/src/scss/overrides.scss",
        ],
        "web.assets_frontend": [
            "hashtap_theme/static/src/scss/_variables.scss",
            "hashtap_theme/static/src/scss/login.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
