"""Mock (dev) ödeme sağlayıcısı + online metotları ekler.

Çalıştırma:
    docker compose exec -T odoo odoo shell -d hashtap \
        --db_host=odoo-db --db_user=odoo --db_password=odoo --no-http \
        < odoo-addons/hashtap_pos/scripts/seed_payment_mock.py

Idempotent: Mock provider ve bağlı metotlar zaten varsa güncellenir.
Gerçek iyzico devreye alındığında bu kayıtlar aynı arayüzden silinip
yerine iyzico provider tanımlanır; PWA/akış kodunda hiçbir değişiklik
gerekmez.
"""
Provider = env["hashtap.payment.provider"]
Method = env["hashtap.payment.method"]

provider = Provider.search([("code", "=", "mock")], limit=1)
if not provider:
    provider = Provider.create({
        "name": "Mock (dev)",
        "code": "mock",
        "sandbox": True,
        "webhook_secret": "devsecret",
    })
else:
    provider.write({
        "active": True,
        "sandbox": True,
        "webhook_secret": provider.webhook_secret or "devsecret",
    })

online_methods = [
    ("card", "Kredi / Banka Kartı"),
    ("apple_pay", "Apple Pay"),
    ("google_pay", "Google Pay"),
]

for code, label in online_methods:
    m = Method.search([("code", "=", code)], limit=1)
    if not m:
        Method.create({
            "name": label,
            "code": code,
            "provider_id": provider.id,
            "active": True,
        })
    else:
        m.write({
            "provider_id": provider.id,
            "active": True,
        })

env.cr.commit()

print("=" * 60)
print("Mock ödeme altyapısı hazır.")
print(f"  Provider: {provider.name} (code={provider.code}, sandbox={provider.sandbox})")
print("  Aktif metotlar:")
for m in Method.search([("active", "=", True)], order="sequence,id"):
    prov = m.provider_id.name if m.provider_id else "-"
    print(f"    - {m.code:<15} → {m.name}  (provider: {prov})")
print("=" * 60)
print("PWA'dan test: Kart metodunu seç → Mock 3DS simülatörü açılır.")
print("=" * 60)
