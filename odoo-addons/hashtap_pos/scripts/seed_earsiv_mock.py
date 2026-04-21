"""Mock e-Arşiv sağlayıcısını kurar — dev/test için.

Çalıştırma:
    docker compose exec -T odoo odoo shell -d hashtap \
        --db_host=odoo-db --db_user=odoo --db_password=odoo --no-http \
        < odoo-addons/hashtap_pos/scripts/seed_earsiv_mock.py

Idempotent: Mock provider zaten varsa günceller. Gerçek Foriba provider'ına
geçerken:
  - Mock'u pasifleştir
  - Foriba provider oluştur (code=foriba, api_key + api_password + seller_vkn)
  - Kod değişikliği gerekmez.
"""
Provider = env["hashtap.earsiv.provider"]

provider = Provider.search([("code", "=", "mock")], limit=1)
if not provider:
    provider = Provider.create({
        "name": "Mock e-Arşiv (dev)",
        "code": "mock",
        "sandbox": True,
        "mock_fail_rate": 0,
        "seller_vkn": env.company.vat or "1234567890",
    })
else:
    provider.write({
        "active": True,
        "sandbox": True,
        "seller_vkn": provider.seller_vkn or (env.company.vat or "1234567890"),
    })

env.cr.commit()

print("=" * 60)
print("Mock e-Arşiv altyapısı hazır.")
print(f"  Provider: {provider.name} (code={provider.code})")
print(f"  Fail rate: %{provider.mock_fail_rate}")
print(f"  Satıcı VKN: {provider.seller_vkn}")
print("=" * 60)
print("Test senaryoları:")
print("  - Normal akış: fail_rate=0 → her sipariş fiş keser, mutfağa gider.")
print("  - Chaos testi: Odoo admin'den provider'ı aç → mock_fail_rate=50")
print("    yap → siparişlerin yarısı fail-close'da kalır, 'Fişi Yeniden")
print("    Dene' butonuyla kurtarılır.")
print("=" * 60)
