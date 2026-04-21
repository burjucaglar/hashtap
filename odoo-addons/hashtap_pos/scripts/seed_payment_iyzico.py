"""iyzico sandbox provider iskeletini kurar.

Çalıştırma:
    docker compose exec -T odoo odoo shell -d hashtap \
        --db_host=odoo-db --db_user=odoo --db_password=odoo --no-http \
        < odoo-addons/hashtap_pos/scripts/seed_payment_iyzico.py

Yaptıkları (idempotent):
  1. Mock provider'ı pasifleştirir (varsa).
  2. "iyzico Sandbox" provider'ını (code=iyzico, sandbox=True) oluşturur
     — API Key / Secret / Webhook Secret boş kalır, admin panelden
     doldurulacak. Credential boşken IyzicoAdapter stub'a düşer, sistem
     kırılmaz.
  3. card / apple_pay / google_pay yöntemlerini iyzico provider'ına
     bağlar.

Yarın yapılacak:
  - Odoo admin → HashTap → Ayarlar → Ödeme → Sağlayıcılar
    → "iyzico Sandbox" kaydını aç
  - iyzico panel'inden aldığın API Key, Secret Key, Webhook Secret'ı
    girip kaydet.
"""
Provider = env["hashtap.payment.provider"]
Method = env["hashtap.payment.method"]

mock = Provider.search([("code", "=", "mock")], limit=1)
if mock:
    mock.active = False

iyz = Provider.search([("code", "=", "iyzico")], limit=1)
if not iyz:
    iyz = Provider.create({
        "name": "iyzico Sandbox",
        "code": "iyzico",
        "sandbox": True,
        "active": True,
        # api_key, api_secret, webhook_secret admin'den doldurulacak.
    })
else:
    iyz.write({"active": True, "sandbox": True})

for code in ("card", "apple_pay", "google_pay"):
    m = Method.search([("code", "=", code)], limit=1)
    if m:
        m.provider_id = iyz.id
        m.active = True

env.cr.commit()

has_keys = bool(iyz.api_key and iyz.api_secret)
print("=" * 60)
print("iyzico iskelet hazır.")
print(f"  Provider: {iyz.name} (code={iyz.code}, sandbox={iyz.sandbox})")
print(f"  Credential girildi mi? {'EVET' if has_keys else 'HAYIR — admin panelden gir'}")
print("  Bağlı metotlar:")
for m in Method.search([("provider_id", "=", iyz.id)]):
    print(f"    - {m.code:<15} → {m.name}")
if mock:
    print(f"  Mock provider: pasifleştirildi (code={mock.code}).")
print("=" * 60)
print("Odoo admin → HashTap → Ayarlar → Ödeme → Sağlayıcılar → iyzico Sandbox")
print("API Key / Secret Key / Webhook Secret alanlarını doldur, kaydet.")
print("Credential dolunca IyzicoAdapter otomatik gerçek API'yi çağırır.")
print("=" * 60)
