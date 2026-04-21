# HashTap — Veri Modeli

Bu doküman `hashtap_pos` modülünün tanımladığı ve genişlettiği veri modellerini alan seviyesinde tanımlar. Odoo ORM kavramları (`fields.Char`, `Many2one`, `One2many`, `Selection`) kullanılır.

> **Güncel uygulama 2026-04-21.** §2.7 "`pos.order` extension" taslağı
> yerine **ayrı bir `hashtap.order` modeli** kullanılıyor; QR akışını
> Odoo kasa akışından bağımsız tuttuk. Gerçek alan listesi:
>
> | Alan | Tip | Not |
> |---|---|---|
> | `state` | Selection | `placed / paid / kitchen_sent / preparing / ready / served / cancelled` — KDS orthogonal eksen. |
> | `payment_state` | Selection | `unpaid / pending / paid / failed / refunded`. |
> | `earsiv_state` | Selection | `not_required / pending / issued / failed`. |
> | `kitchen_fired_at`, `ready_at` | Datetime | KDS zamanlaması. |
> | `is_earsiv_blocked` | Boolean (computed) | Fail-close; True iken mutfak aksiyonu `ValidationError` atar. |
> | `pos_order_id` | Many2one pos.order | Opsiyonel köprü (muhasebe için gerektiğinde tetiklenir). |
>
> `hashtap.order.line` ayrı model — `item_name`, `quantity`,
> `unit_price_kurus`, `modifier_ids` (Many2many `hashtap.modifier`),
> `modifier_total_kurus`, `note`, `subtotal_kurus`.
>
> `hashtap.iyzico.transaction` → **`hashtap.payment.transaction`** olarak
> isimlendirildi (provider-agnostic; `hashtap.payment.provider` kaydı
> adapter code'unu tutar). e-Arşiv tarafında da `hashtap.earsiv.provider`
> kaydı sağlayıcı seçimini yapar. Detay: `docs/STATUS.md` §2.
>
> Aşağıdaki §2.7 ve §2.8 planlama dokümanıdır; uygulama güncel alanlar
> için yukarıdaki tabloya bakın.

## 1. Tasarım prensipleri

1. **Odoo'nun mevcut modellerini genişlet, kopyalama.** Ürün `product.template`'tır; HashTap'in menu item'ı `product.template`'a FK verir. Fiyatı `list_price`'tan alır.
2. **İş gerçeği (fiyat, KDV) Odoo'da, sunum (foto, i18n, açıklama) HashTap'te.** `MENU sync` için de aynı kural: POS'a bağlıyken POS iş gerçeği sahibi.
3. **Para birimi.** Odoo'nun kendi para alanları (`fields.Monetary`) kullanılır. Gateway'e dönüş sırasında Kurus'a çevrilir. (ADR-0003.)
4. **Soft delete.** Silme yerine `active=False`. Eski siparişlerin bağlı olduğu menü kalemleri kaybolmasın.
5. **Audit.** Odoo'nun `mail.thread` mixin'i ile tüm kritik değişiklikler chatter'a düşer. Ek audit tablosu yazmıyoruz.
6. **i18n.** TR + EN minimum. Odoo'nun translation sistemi yerine (bazı alanlar için) açık `_tr`, `_en` alanları kullanıyoruz — tek formda iki dili birlikte düzenletmeyi kolaylaştırmak için. Translations tablosu yine Odoo varsayılanı olarak çalışır.

## 2. Model kataloğu

### 2.1 `hashtap.menu.category`

QR menüsündeki üst başlık. `pos.category`'den bağımsız tutulur — POS kasiyer klavyesiyle QR menüsü sıralaması farklı olabilir.

| Alan | Tip | Açıklama |
|---|---|---|
| `name_tr` | `Char(required=True)` | "Başlangıçlar" |
| `name_en` | `Char(required=True)` | "Starters" |
| `sequence` | `Integer` | Görünüm sırası |
| `icon` | `Binary` | Opsiyonel kategori ikonu |
| `item_ids` | `One2many -> hashtap.menu.item.category_id` | İçerdiği kalemler |
| `company_id` | `Many2one res.company` | Çok-şirket desteği |
| `active` | `Boolean default=True` | Soft delete |
| `available_from` | `Float` | Gün saati başlangıç (brunch saat 10, vb) — NULL ise tüm gün |
| `available_to` | `Float` | Gün saati bitiş |

### 2.2 `hashtap.menu.item`

QR menüdeki her kalem. Bir `product.template`'a bağlanmak zorunda — iş gerçeği orada.

| Alan | Tip | Açıklama |
|---|---|---|
| `product_tmpl_id` | `Many2one product.template (required=True, ondelete='restrict')` | Fiyat, KDV, SKU buradan gelir |
| `category_id` | `Many2one hashtap.menu.category (required=True)` | |
| `name_tr` | `Char` | Menü adı TR (product'tan farklı olabilir; pazarlama adı) |
| `name_en` | `Char` | Menü adı EN |
| `description_tr` | `Text` | TR açıklama (örn "acı değildir, çıtırdır") |
| `description_en` | `Text` | EN açıklama |
| `image` | `Binary` | Ana menü fotoğrafı |
| `image_small` | `Binary (computed)` | Liste görünümü için küçük versiyon |
| `allergen_ids` | `Many2many hashtap.allergen` | Gluten, süt, fıstık... |
| `dietary_tags` | `Selection` | vegan/vejetaryen/helal |
| `prep_time_minutes` | `Integer` | Tahmini hazırlık (PWA'da gösterilir) |
| `is_featured` | `Boolean` | Kategorinin üstünde öne çıkar |
| `is_available_now` | `Boolean (computed, store=False)` | Hem `active` hem kategori saat aralığı |
| `sequence` | `Integer` | Kategori içi sıra |
| `modifier_group_ids` | `Many2many hashtap.modifier.group` | Hangi gruplar sunulacak |
| `price_display` | `Monetary (related=product_tmpl_id.list_price)` | Salt-okunur fiyat |
| `taxes_id` | `Many2many account.tax (related=product_tmpl_id.taxes_id)` | |
| `company_id` | `Many2one` | |
| `active` | `Boolean` | |

**Kısıtlar:**
- Aynı `product_tmpl_id` birden fazla `hashtap.menu.item`'a bağlanamaz (unique constraint).
- `product_tmpl_id.detailed_type` in `('product', 'consu')` olmalı — servis ürünü menüye konulmaz.

### 2.3 `hashtap.modifier.group`

"Ekstra malzemeler", "Seçenekler", "Soslar" gibi. Bir kaleme eklenir.

| Alan | Tip | Açıklama |
|---|---|---|
| `name_tr` | `Char` | "Ekstralar" |
| `name_en` | `Char` | "Extras" |
| `min_select` | `Integer default=0` | Minimum seçim |
| `max_select` | `Integer default=1` | Maksimum seçim (0 = sınırsız) |
| `is_required` | `Boolean` | `min_select > 0` ise True (computed) |
| `modifier_ids` | `One2many hashtap.modifier.group_id` | Seçenekler |
| `sequence` | `Integer` | |

### 2.4 `hashtap.modifier`

Grubun bir seçeneği.

| Alan | Tip | Açıklama |
|---|---|---|
| `group_id` | `Many2one hashtap.modifier.group (required=True, ondelete='cascade')` | |
| `name_tr` | `Char` | "Ekstra peynir" |
| `name_en` | `Char` | "Extra cheese" |
| `price_delta` | `Monetary` | Baz fiyatın üzerine/altına |
| `linked_product_id` | `Many2one product.product` | Stok düşümü için opsiyonel — seçilirse bu ürün de tüketilir |
| `sequence` | `Integer` | |

**Not:** `price_delta` negatif olabilir ("soğansız — 0.00 TL" için null/0). Stok düşümü için `linked_product_id` kullanılır; yoksa modifier sadece fiyat etkiler.

### 2.5 `hashtap.allergen`

| Alan | Tip | Açıklama |
|---|---|---|
| `name_tr`, `name_en` | `Char` | |
| `icon` | `Char` | Emoji/simge kodu (PWA'da gösterim) |

Seed data ile 14 AB allergen listesi yüklenir.

### 2.6 `restaurant.table` — extension

Odoo'nun `pos_restaurant` modülündeki `restaurant.table`'a alan ekliyoruz.

| Yeni alan | Tip | Açıklama |
|---|---|---|
| `hashtap_qr_slug` | `Char(size=32, index=True)` | URL-safe rastgele string; masa yaratılırken computed |
| `hashtap_qr_url` | `Char (computed)` | `https://r.example.com/<tenant>/<qr_slug>` |
| `hashtap_qr_image` | `Binary (computed)` | QR kodunun PNG'si |
| `hashtap_enabled` | `Boolean default=True` | QR akışını bu masa için kapatma |

`hashtap_qr_slug` slug ömrü: masa silinene kadar değişmez. Masa silinir ve geri gelirse yeni slug üretilir.

### 2.7 `pos.order` — extension

Odoo'nun `pos.order`'ı sipariş beynidir; HashTap'in ek durumlarını buraya alan olarak koyuyoruz.

| Yeni alan | Tip | Açıklama |
|---|---|---|
| `hashtap_state` | `Selection` | `pending_payment / paid / paid_no_receipt / kitchen_fired / ready / served / cancelled_by_customer / refunded` |
| `hashtap_source` | `Selection` | `qr / pos_terminal / staff_tablet` — hangi kanaldan |
| `hashtap_correlation_id` | `Char(size=64, index=True)` | Idempotency anahtarı |
| `hashtap_payment_txn_id` | `Many2one hashtap.iyzico.transaction` | |
| `hashtap_receipt_id` | `Many2one hashtap.earsiv.receipt` | |
| `hashtap_table_qr_id` | `Many2one restaurant.table` | QR'den gelen masa bağı |
| `hashtap_customer_contact` | `Char` | PWA'da opsiyonel girdi (SMS için) |

**Durum akışı:**

```
pending_payment ─┬─► paid ─────────┬─► kitchen_fired ─► ready ─► served
                 │                 │
                 │                 └─► paid_no_receipt (e-Arşiv fail; retry ile paid'a dönebilir)
                 │
                 └─► cancelled_by_customer (3DS iptal)

paid → refunded (iade)
```

Geçişler `hashtap_pos/services/order_lifecycle.py` içinde `assert_can_transition(from_state, to_state)` fonksiyonu ile korunur.

### 2.8 `hashtap.iyzico.transaction`

Her ödeme denemesi için bir kayıt. Geçmiş tutulur, silinmez.

| Alan | Tip | Açıklama |
|---|---|---|
| `pos_order_id` | `Many2one pos.order (required=True)` | |
| `correlation_id` | `Char (required=True, index=True, unique)` | Idempotency |
| `conversation_id` | `Char` | iyzico'nun kendi session id'si |
| `state` | `Selection` | `init / 3ds_started / paid / failed / timeout` |
| `amount` | `Monetary` | Kuruşlara değil Odoo monetary |
| `currency_id` | `Many2one res.currency` | |
| `sub_merchant_id` | `Char` | iyzico subMerchant (kiracı/restoran bazlı) |
| `iyzico_request` | `Text` | Son gönderilen JSON (debug için) |
| `iyzico_response` | `Text` | Son alınan JSON |
| `signature_verified` | `Boolean` | Callback imzası geçti mi |
| `card_last4` | `Char(4)` | İsteğe bağlı kullanıcıya gösterim için |
| `payment_method` | `Selection` | `card / apple_pay / google_pay` |
| `created_at` | `Datetime` | |
| `completed_at` | `Datetime` | |

**Kısıtlar:**
- `correlation_id` benzersiz. Callback idempotency'sinin kök noktası.
- PCI kapsamı: tam PAN ve CVV **saklanmaz**. Sadece last4 ve tokenize edilmiş referans.

### 2.9 `hashtap.earsiv.receipt`

Kesilen fiş kaydı.

| Alan | Tip | Açıklama |
|---|---|---|
| `pos_order_id` | `Many2one pos.order (required=True)` | |
| `provider` | `Selection` | `foriba / uyumsoft / logo / mock` |
| `ettn` | `Char` | e-Arşiv fiş numarası (sağlayıcı döner) |
| `issue_date` | `Datetime` | |
| `state` | `Selection` | `pending / issued / failed / cancelled` |
| `pdf_url` | `Char` | Sağlayıcının PDF linki (ya da cache'lenmiş local URL) |
| `qr_content` | `Char` | GİB QR verisi |
| `retry_count` | `Integer` | Kaçıncı deneme |
| `last_error` | `Text` | |
| `provider_request` | `Text` | |
| `provider_response` | `Text` | |

Fiş başarısız (state='failed') olduğunda otomatik `queue_job` yeniden dener (exponential backoff, max 5 deneme). 5 denemeden sonra manuel müdahale için panel alarmı.

### 2.10 `hashtap.allergen` (geçici not)

Listelendi §2.5'te.

### 2.11 `res.config.settings` — extension

Odoo'nun ayar ekranına HashTap bölümü ekliyoruz.

| Yeni alan | Tip |
|---|---|
| `hashtap_iyzico_api_key` | `Char (ir.config_parameter, encrypted)` |
| `hashtap_iyzico_secret` | `Char (encrypted)` |
| `hashtap_iyzico_sub_merchant_key` | `Char` |
| `hashtap_iyzico_environment` | `Selection sandbox/production` |
| `hashtap_earsiv_provider` | `Selection foriba/uyumsoft/logo/mock` |
| `hashtap_earsiv_api_key` | `Char (encrypted)` |
| `hashtap_pos_mode` | `Selection hashtap_native/adapter_sambapos/adapter_adisyo/adapter_local_agent` |
| `hashtap_adapter_url` | `Char` | Adapter servis URL'i (mode adapter_* ise) |
| `hashtap_print_bridge_token` | `Char (encrypted)` | Print-bridge için paylaşılan token |
| `hashtap_default_language` | `Selection tr/en` | |

## 3. Dış şemalar — API üzerinden çıkan/giren veri

### 3.1 Menü response (PWA'ya dönen)

```json
{
  "tenant": {
    "slug": "terakki",
    "name": "Terakki",
    "currency": "TRY",
    "language": "tr"
  },
  "table": {
    "slug": "t42",
    "label": "Masa 42"
  },
  "categories": [
    {
      "id": 12,
      "name": { "tr": "Başlangıçlar", "en": "Starters" },
      "sequence": 1,
      "items": [
        {
          "id": 103,
          "name": { "tr": "Humus", "en": "Hummus" },
          "description": { "tr": "...", "en": "..." },
          "image_url": "https://...",
          "price_kurus": 12500,
          "currency": "TRY",
          "vat_rate": 10,
          "allergens": ["gluten", "sesame"],
          "dietary": ["vegan"],
          "prep_time_minutes": 8,
          "is_featured": false,
          "modifier_groups": [
            {
              "id": 7,
              "name": { "tr": "Ekstralar", "en": "Extras" },
              "min_select": 0,
              "max_select": 2,
              "modifiers": [
                { "id": 31, "name": { "tr": "Ekstra zeytinyağı", "en": "Extra olive oil" }, "price_delta_kurus": 1000 }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

### 3.2 Sipariş request (PWA'dan gelen)

```json
{
  "tenant_slug": "terakki",
  "table_slug": "t42",
  "cart": [
    {
      "item_id": 103,
      "quantity": 2,
      "selected_modifiers": [31],
      "customer_note": "az tuzlu"
    }
  ],
  "customer_contact": {
    "phone": "+90..."    // opsiyonel, SMS bildirim için
  },
  "language": "tr"
}
```

### 3.3 Sipariş response

```json
{
  "order_id": "ORD-2026-000123",
  "access_token": "...",  // status polling için
  "total_kurus": 27000,
  "currency": "TRY",
  "vat_breakdown": [
    { "rate": 10, "amount_kurus": 2700 }
  ],
  "payment_session_token": "..."  // 3DS start'a geçerken
}
```

### 3.4 Sipariş durumu

```json
{
  "order_id": "ORD-2026-000123",
  "state": "kitchen_fired",
  "state_label": { "tr": "Mutfağa gönderildi", "en": "Sent to kitchen" },
  "estimated_ready_at": "2026-04-20T19:42:00Z",
  "receipt": {
    "issued": true,
    "pdf_url": "https://...",
    "qr_content": "..."
  }
}
```

## 4. Kimliklerin biçimi

- `order_id` (dış): `ORD-<yıl>-<6 haneli sequence>`. Odoo'nun `ir.sequence`'i.
- `correlation_id`: UUID4.
- `qr_slug`: 8 karakter base32 (32^8 ≈ 1 trilyon, çakışma pratikte yok).
- `ettn`: sağlayıcının döndürdüğü UUID'li string — kendi kimliğimiz değil.

## 5. Şema değişiklikleri ve migration

- Her prod sürümünde Odoo `-u hashtap_pos --update` migration çalıştırır.
- Veri migration gerektiren değişiklikler `hashtap_pos/migrations/17.0.<x>.<y>/pre-migrate.py` + `post-migrate.py` ile.
- Geriye uyumlu olmayan alan silme yasak; önce deprecate, bir sürüm sonra kaldır.

## 6. Eksik / bilinçli dışarıda bırakılanlar

- **Sadakat / puan sistemi** — MVP dışı; şimdilik `res.partner`'a özel alan yok.
- **Rezervasyon** — farklı modül.
- **Çoklu şirket/konsept hiyerarşisi** — MVP'de tek şirket. `res.company` kullanılıyor ama HashTap'in iç hiyerarşisi yok.
- **Tip (bahşiş)** — MVP'de sipariş üzerine eklenebilir bir alan olmayacak; faz 2'de `pos.order` üzerinde `hashtap_tip_amount` eklenir.

Eksiklikler burada kayıt altında; gereksinim geldiğinde bu dosya güncellenir.
