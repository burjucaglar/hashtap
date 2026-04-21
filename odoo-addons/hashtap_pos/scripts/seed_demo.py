"""Faz 2 smoke testi için demo restoran kurgusu.

Çalıştırma:
    docker compose exec -T odoo odoo shell -d hashtap \
        --db_host=odoo-db --db_user=odoo --db_password=odoo --no-http \
        < odoo-addons/hashtap_pos/scripts/seed_demo.py

Idempotent: tekrar çalıştırınca önce mevcut HashTap verisini temizler.
"""
env["ir.config_parameter"].sudo().set_param("hashtap.tenant_slug", "testco")
env["ir.config_parameter"].sudo().set_param(
    "hashtap.pwa_base_url", "http://localhost:5173"
)

env["hashtap.menu.item"].search([]).unlink()
env["hashtap.menu.category"].search([]).unlink()
env["hashtap.modifier.group"].search([]).unlink()
env["hashtap.allergen"].search([]).unlink()

company = env.company
company.name = "Anadolu Sofrası"

allergens = {
    code: env["hashtap.allergen"].create({
        "code": code, "name_tr": tr, "name_en": en,
    })
    for code, tr, en in [
        ("gluten", "Gluten", "Gluten"),
        ("dairy", "Süt ürünleri", "Dairy"),
        ("nuts", "Sert kabuklu", "Nuts"),
        ("sesame", "Susam", "Sesame"),
        ("egg", "Yumurta", "Egg"),
    ]
}

pisirme = env["hashtap.modifier.group"].create({
    "name_tr": "Pişirme Tercihi",
    "name_en": "Cooking Preference",
    "min_select": 1,
    "max_select": 1,
    "modifier_ids": [
        (0, 0, {"name_tr": "Az", "name_en": "Rare", "price_delta": 0}),
        (0, 0, {"name_tr": "Orta", "name_en": "Medium", "price_delta": 0}),
        (0, 0, {"name_tr": "İyi pişmiş", "name_en": "Well done", "price_delta": 0}),
    ],
})

eklemeler = env["hashtap.modifier.group"].create({
    "name_tr": "Ek Malzeme",
    "name_en": "Extras",
    "min_select": 0,
    "max_select": 3,
    "modifier_ids": [
        (0, 0, {"name_tr": "Ekstra kaşar", "name_en": "Extra cheese", "price_delta": 25}),
        (0, 0, {"name_tr": "Avokado", "name_en": "Avocado", "price_delta": 40}),
        (0, 0, {"name_tr": "Mantar", "name_en": "Mushrooms", "price_delta": 20}),
    ],
})

pide_hamuru = env["hashtap.modifier.group"].create({
    "name_tr": "Hamur",
    "name_en": "Dough",
    "min_select": 1,
    "max_select": 1,
    "modifier_ids": [
        (0, 0, {"name_tr": "İnce", "name_en": "Thin", "price_delta": 0}),
        (0, 0, {"name_tr": "Kalın", "name_en": "Thick", "price_delta": 0}),
    ],
})

cat_baslangic = env["hashtap.menu.category"].create({
    "name_tr": "Başlangıçlar",
    "name_en": "Starters",
    "sequence": 10,
})
cat_ana = env["hashtap.menu.category"].create({
    "name_tr": "Ana Yemekler",
    "name_en": "Mains",
    "sequence": 20,
})
cat_pide = env["hashtap.menu.category"].create({
    "name_tr": "Pideler",
    "name_en": "Pides",
    "sequence": 30,
})
cat_tatli = env["hashtap.menu.category"].create({
    "name_tr": "Tatlılar",
    "name_en": "Desserts",
    "sequence": 40,
})
cat_icecek = env["hashtap.menu.category"].create({
    "name_tr": "İçecekler",
    "name_en": "Drinks",
    "sequence": 50,
})

def _make_product(name, price):
    return env["product.template"].create({
        "name": name,
        "list_price": price,
        "type": "consu",
    })

items = [
    # (kategori, name_tr, name_en, desc_tr, fiyat, prep, featured, allergens, mod_groups, dietary)
    (cat_baslangic, "Humus", "Hummus", "Tahinli nohut ezmesi, zeytinyağı ve kimyonla",
     85.0, 5, False, ["gluten", "sesame"], [], "vegetarian"),
    (cat_baslangic, "Haydari", "Haydari (yogurt dip)",
     "Süzme yoğurt, kekik ve sarımsakla",
     75.0, 4, False, ["dairy"], [], "vegetarian"),
    (cat_baslangic, "Sigara Böreği", "Cheese Rolls",
     "Beyaz peynirli, çıtır yufka",
     90.0, 8, True, ["gluten", "dairy", "egg"], [], "vegetarian"),

    (cat_ana, "Adana Kebap", "Adana Kebab",
     "Elde kıyılmış kuzu, közde pişmiş biber ile",
     280.0, 18, True, [], [pisirme.id, eklemeler.id], "halal"),
    (cat_ana, "Izgara Köfte", "Grilled Meatballs",
     "Dana kıyma, közde sebze garnitür",
     240.0, 15, False, ["gluten"], [pisirme.id], "halal"),
    (cat_ana, "Sebzeli Güveç", "Vegetable Casserole",
     "Mevsim sebzeleri, fırında",
     180.0, 20, False, [], [], "vegan"),

    (cat_pide, "Kaşarlı Pide", "Cheese Pide",
     "Bol kaşarlı, el açması",
     180.0, 12, False, ["gluten", "dairy", "egg"], [pide_hamuru.id], "vegetarian"),
    (cat_pide, "Kıymalı Pide", "Ground Meat Pide",
     "Dana kıyma, sivri biber",
     210.0, 14, True, ["gluten", "egg"], [pide_hamuru.id], "halal"),

    (cat_tatli, "Künefe", "Künefe",
     "Kadayıf, lor peyniri, tereyağı ve şerbet",
     160.0, 10, True, ["gluten", "dairy", "nuts"], [], "vegetarian"),
    (cat_tatli, "Sütlaç", "Rice Pudding",
     "Fırında pişmiş, tarçınla",
     95.0, 3, False, ["dairy"], [], "vegetarian"),

    (cat_icecek, "Ayran", "Ayran",
     "Ev yapımı, tuzlu yoğurt içeceği",
     35.0, 1, False, ["dairy"], [], "vegetarian"),
    (cat_icecek, "Türk Kahvesi", "Turkish Coffee",
     "Orta şekerli, cezvede",
     60.0, 4, False, [], [], "vegan"),
    (cat_icecek, "Taze Sıkma Portakal", "Fresh Orange Juice",
     "Günün portakalı",
     55.0, 2, False, [], [], "vegan"),
]

for cat, name_tr, name_en, desc_tr, price, prep, featured, allergen_codes, mod_ids, dietary in items:
    product = _make_product(name_tr, price)
    env["hashtap.menu.item"].create({
        "product_tmpl_id": product.id,
        "category_id": cat.id,
        "name_tr": name_tr,
        "name_en": name_en,
        "description_tr": desc_tr,
        "description_en": "",
        "prep_time_minutes": prep,
        "is_featured": featured,
        "dietary_tag": dietary,
        "allergen_ids": [(6, 0, [allergens[c].id for c in allergen_codes])],
        "modifier_group_ids": [(6, 0, mod_ids)],
    })

floor = env["restaurant.floor"].search([("name", "=", "HashTap Demo")], limit=1)
if not floor:
    floor = env["restaurant.floor"].create({"name": "HashTap Demo"})

demo_table = env["restaurant.table"].search(
    [("floor_id", "=", floor.id), ("name", "=", "M1")], limit=1
)
if not demo_table:
    demo_table = env["restaurant.table"].create({
        "name": "M1",
        "floor_id": floor.id,
    })

env.cr.commit()

print("=" * 60)
print("Demo verisi hazır.")
print(f"  Tenant: testco  ({company.name})")
print(f"  Masa slug: {demo_table.hashtap_qr_slug}")
print(f"  PWA URL: http://localhost:5173/r/testco/t/{demo_table.hashtap_qr_slug}")
print(f"  API URL: http://localhost:8069/hashtap/menu/testco/{demo_table.hashtap_qr_slug}")
print("=" * 60)
