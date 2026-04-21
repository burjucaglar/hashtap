# infra/odoo — Odoo 17 dev stack

## İlk kurulum

```sh
docker compose up -d
# Odoo http://localhost:8069'da ayakta. DB seçim ekranı gelir.
```

## İlk DB oluştur

`demo` DB'si + `hashtap_pos` + `hashtap_theme` yüklü:

```sh
docker compose exec odoo odoo \
  -d demo \
  -i hashtap_pos,hashtap_theme \
  --stop-after-init \
  --without-demo=False
```

Sonra `docker compose restart odoo`, http://localhost:8069/web?db=demo.

## Modül değişikliği sonrası upgrade

```sh
docker compose exec odoo odoo -d demo -u hashtap_pos --stop-after-init
docker compose restart odoo
```

`--dev=all` ile Python/XML değişikliklerinde çoğu durumda restart gerekmez.

## MailHog (test mailleri)

- SMTP: `mailhog:1025`
- Web: http://localhost:8025

Odoo → Settings → General → Outgoing Email Servers: host `mailhog`, port `1025`.

## iyzico sandbox'a geçiş (yarın için)

Altyapı hazır; `iyzipay` SDK imaja kurulu, IyzicoAdapter akışa bağlı.
Yarın sadece:

1. https://sandbox-merchant.iyzipay.com/ → kayıt ol, SMS doğrula.
2. Panel → Ayarlar → API Anahtarları → Sandbox `API Key`, `Secret Key`, `Webhook Secret` al.
3. Local'de imajı build et (ilk sefer iyzipay kurulur):

   ```sh
   docker compose build odoo
   docker compose up -d
   ```

4. iyzico iskeletini kur:

   ```sh
   docker compose exec -T odoo odoo shell -d hashtap \
     --db_host=odoo-db --db_user=odoo --db_password=odoo --no-http \
     < ../../odoo-addons/hashtap_pos/scripts/seed_payment_iyzico.py
   ```

5. Odoo admin → **HashTap → Ayarlar → Ödeme → Sağlayıcılar → iyzico Sandbox**
   — API Key / Secret Key / Webhook Secret alanlarını doldur, kaydet.
6. PWA'da Kart'ı seç → artık iyzico'nun gerçek hosted 3DS sayfası açılır.
   Test kartları: https://dev.iyzipay.com/tr/test-kartlari

Mock'a dönmek istersen: admin'de iyzico provider'ı pasif yap, mock'u aktif et.

## Portlar

- 8069 → Odoo web
- 8072 → longpolling (bus, livechat)
- 5432 → Postgres (container içinde, dış mapping yok — çakışmasın diye)
- 8025 → MailHog UI
- 1025 → MailHog SMTP
