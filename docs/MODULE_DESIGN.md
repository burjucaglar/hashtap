# `hashtap_pos` Modül Tasarımı

Bu doküman Odoo 17 üstüne yazacağımız `hashtap_pos` modülünün iç yapısını tanımlar. Okunabilmesi için Odoo modül sisteminin temel kavramlarına (model, view, controller, manifest, hook) aşina olunduğu varsayılır; aşina değilseniz `DEV_SETUP.md` başlayış için yeterli.

> **Güncel uygulama 2026-04-21.** Aşağıdaki yapı planlama dokümanıdır;
> gerçek modüldeki bazı kararlar değişti. En önemli sapmalar:
>
> - **`pos.order` extend yerine ayrı `hashtap.order` modeli.** QR sipariş
>   akışını Odoo'nun kasa akışından ayrı tutmak iş mantığını
>   sadeleştirdi. `pos.order` köprüsü opsiyonel (§8.1, ileride).
> - **Orthogonal state axes:** `state` / `payment_state` / `earsiv_state`
>   üç bağımsız eksen (DATA_MODEL.md §2.7'de tek eksen önerilmişti).
> - **`services/` yerine `adapters/` dizini** — ödeme ve e-Arşiv
>   sağlayıcıları adapter pattern ile izole. `services/` dizini şu anda
>   çoğunlukla boş; saf iş mantığı yardımcıları buraya taşınacak.
> - **KDS:** `controllers/kds.py` + `views/hashtap_kds_*` — detay
>   `docs/KDS.md`.
> - **`queue_job` henüz dahil değil;** Faz 5 e-Arşiv retry'ları senkron +
>   Odoo cron ile çözüldü. Yüke göre ileride eklenir.
>
> Tam anlık liste: `docs/STATUS.md`.

## 1. Amaç ve sınırlar

**Amaç:**
- Odoo'nun mevcut restoran modüllerini (`point_of_sale`, `pos_restaurant`) **genişletmek** (override etmek değil), HashTap'e özgü akışları eklemek.
- Public HTTP API'yi (müşteri PWA'nın konuştuğu uçları) bu modül içinde tutmak.
- iyzico ve e-Arşiv entegrasyonlarını modül içinde izole etmek.

**Sınırlar:**
- Odoo core dosyalarına dokunma. Kaçınılmaz noktalarda monkey-patch ile çöz ve ADR aç.
- `hashtap_theme` ile iş bölümü: bu modülde görsel tema değişikliği yok. Sadece iş mantığı, data modelleri, controller'lar.
- Segment B (harici POS) mantığı bu modülde barınır ama harici POS'a konuşan kod `packages/pos-adapters/` altındaki Node servisine HTTP ile gider. Python'da POS SDK kullanmıyoruz.

## 2. Dizin yapısı

Repo'da lokasyon: `odoo-addons/hashtap_pos/`.

```
odoo-addons/
└── hashtap_pos/
    ├── __init__.py
    ├── __manifest__.py
    ├── controllers/
    │   ├── __init__.py
    │   ├── main.py                  # route register'ı, ortak yardımcılar
    │   ├── menu.py                  # GET /hashtap/menu/...
    │   ├── order.py                 # POST /hashtap/order
    │   └── payment.py               # 3DS start + callback
    ├── models/
    │   ├── __init__.py
    │   ├── hashtap_menu_category.py
    │   ├── hashtap_menu_item.py
    │   ├── hashtap_modifier_group.py
    │   ├── hashtap_modifier.py
    │   ├── hashtap_table_qr.py      # restaurant.table extend + QR slug
    │   ├── pos_order.py             # Odoo pos.order'ı extend (paid, paid_no_receipt)
    │   ├── iyzico_transaction.py    # ödeme logu
    │   └── earsiv_receipt.py        # fiş logu
    ├── services/                    # saf Python iş mantığı, ORM'den bağımsız test edilebilir
    │   ├── __init__.py
    │   ├── pricing.py               # sepet → toplam, KDV dağıtımı
    │   ├── iyzico_client.py         # iyzico REST wrapper
    │   └── earsiv_client.py         # Foriba/Uyumsoft adapter
    ├── views/
    │   ├── hashtap_menu_views.xml
    │   ├── hashtap_table_views.xml
    │   ├── pos_order_views.xml      # mevcut view'a ek button/field
    │   ├── menu_root.xml            # "HashTap POS" üst menü
    │   └── settings_views.xml       # res.config.settings extend
    ├── security/
    │   ├── ir.model.access.csv
    │   ├── hashtap_security.xml     # kullanıcı grupları
    │   └── record_rules.xml         # kayıt bazı erişim kuralları
    ├── data/
    │   ├── ir_cron.xml              # iyzico callback timeout cron'u
    │   └── queue_job_function.xml   # async job tanımları
    ├── wizards/
    │   └── tenant_setup_wizard.py   # ilk kurulum sihirbazı
    ├── tests/
    │   ├── __init__.py
    │   ├── test_menu.py
    │   ├── test_order_flow.py
    │   ├── test_iyzico_callback.py
    │   └── test_earsiv_failclose.py
    └── static/
        └── description/
            ├── icon.png
            └── index.html           # modül tanıtım sayfası (iç kullanım)
```

## 3. `__manifest__.py`

```python
{
    "name": "HashTap POS",
    "version": "17.0.1.0.0",
    "category": "Point of Sale",
    "summary": "QR sipariş, mobil ödeme ve restoran operasyonu için HashTap genişletmesi",
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
        "queue_job",  # OCA — async job için
    ],
    "data": [
        "security/hashtap_security.xml",
        "security/ir.model.access.csv",
        "security/record_rules.xml",
        "data/ir_cron.xml",
        "data/queue_job_function.xml",
        "views/menu_root.xml",
        "views/hashtap_menu_views.xml",
        "views/hashtap_table_views.xml",
        "views/pos_order_views.xml",
        "views/settings_views.xml",
    ],
    "external_dependencies": {
        "python": ["requests", "cryptography"],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
```

## 4. Veri modelleri — kısa liste

Detaylı alan seviyesinde tanım `DATA_MODEL.md` içinde. Burada modül içi özet:

| Model | Odoo karşılığı | Ne ekliyoruz |
|---|---|---|
| `hashtap.menu.category` | yeni | QR menü için kategoriler; `pos.category`'den ayrı tutmak, çünkü HashTap menüsü sunum odaklı (foto, i18n), POS menüsü operasyon odaklı (hızlı erişim, klavye) |
| `hashtap.menu.item` | yeni; `product.template`'a FK | QR menü kalemi. Fiyat `product.template.list_price`'tan alınır (tek kaynak), üstüne HashTap'in eklediği alan: fotoğraf, TR+EN açıklama, teşhir sırası, modifier grupları |
| `hashtap.modifier.group` | yeni | "Ekstra", "Seçenek", "Soslar" — min/max seçim kuralı |
| `hashtap.modifier` | yeni; fiyat delta'lı | Grup içindeki tekil seçenek |
| `restaurant.table` (extend) | var | `hashtap_qr_slug`, `hashtap_qr_url` alanları |
| `pos.order` (extend) | var | `hashtap_state`, `hashtap_payment_provider`, `hashtap_receipt_id`, `hashtap_correlation_id` |
| `hashtap.iyzico.transaction` | yeni | Ödeme logu, imza, idempotency key |
| `hashtap.earsiv.receipt` | yeni | Fiş logu, sağlayıcı yanıtı |
| `res.config.settings` (extend) | var | iyzico merchant id, e-Arşiv sağlayıcı seçimi, HashTap'e özgü ayarlar |

## 5. Controller tasarımı

Tüm public uçlar `auth='public'`, rate limit nginx + gateway tarafında. Her uç JSON-in / JSON-out; Odoo'nun `/web/dataset/call_kw` konvansiyonunu kullanmıyoruz (dış dünya için çok Odoo-spesifik).

### 5.1 `GET /hashtap/menu/<tenant_slug>/<table_slug>`

```python
@http.route('/hashtap/menu/<string:tenant_slug>/<string:table_slug>',
            type='json', auth='public', methods=['GET'], csrf=False)
def get_menu(self, tenant_slug, table_slug):
    # 1. tenant doğrula (gateway zaten yönlendirdi; yine de DB izolasyonunun namazını kıl)
    # 2. table_slug'dan restaurant.table bul
    # 3. menu ağacını çek: category -> item -> modifier_group -> modifier
    # 4. Kurus cinsinden fiyat + KDV oranı
    # 5. dil parametresi request header'dan (Accept-Language) ya da query'den
```

**Çıktı şeması:** `DATA_MODEL.md` §3.1.

### 5.2 `POST /hashtap/order`

```python
@http.route('/hashtap/order', type='json', auth='public', methods=['POST'], csrf=False)
def create_order(self, tenant_slug, table_slug, cart, customer_hint=None):
    # 1. Sepeti validate et (her item hâlâ mevcut mu, her modifier geçerli mi)
    # 2. Fiyatı SUNUCU tarafında yeniden hesapla
    # 3. pos.order oluştur (state='draft', hashtap_state='pending_payment')
    # 4. 3DS için ödeme session'ı hazırla (henüz iyzico'ya gitme; callback için correlation_id üret)
    # 5. Dön: { order_id, payment_session_token, total, currency }
```

### 5.3 `POST /hashtap/payment/3ds/start`

```python
# gateway'den gelir, PWA'dan değil
@http.route('/hashtap/payment/3ds/start', type='json', auth='public', methods=['POST'], csrf=False)
def payment_3ds_start(self, order_id, payment_session_token, card_hint):
    # 1. Session token doğrula (kısa ömürlü, HMAC)
    # 2. iyzico'ya 3DS init çağrısı (services.iyzico_client)
    # 3. iyzico'nun döndürdüğü htmlContent'i (3DS redirect sayfası) PWA'ya dön
```

### 5.4 `POST /hashtap/payment/3ds/callback`

```python
# iyzico'dan gelir (gateway üzerinden, imza doğrulanarak iletilir)
@http.route('/hashtap/payment/3ds/callback', type='json', auth='public', methods=['POST'], csrf=False)
def payment_3ds_callback(self, payload, signature):
    # 1. İmzayı doğrula
    # 2. Idempotency kontrolü (correlation_id tekrarı)
    # 3. hashtap.iyzico.transaction kaydı oluştur
    # 4. Başarılıysa:
    #    a. pos.order 'paid' yap
    #    b. e-Arşiv kesmek için queue job at
    # 5. Başarısızsa:
    #    a. pos.order 'cancelled' yap, alarm düşür
```

### 5.5 `GET /hashtap/order/<order_id>/status`

```python
# PWA polling için
@http.route('/hashtap/order/<string:order_id>/status', type='json', auth='public', methods=['GET'], csrf=False)
def get_order_status(self, order_id):
    # access token doğrula (sipariş oluştururken PWA'ya verilir)
    # pos.order'dan hashtap_state + fiş URL (varsa) dön
```

## 6. Servis katmanı

### 6.1 `services/pricing.py`
- Saf Python, ORM bağımsız.
- Sepet → toplam; modifier fiyat deltaları; KDV oranı başına dağıtım.
- Kurus (int) ile çalışır; Odoo'ya yazarken float'a dönüştürür.
- Unit test'i DB'ye ihtiyaç duymadan koşar.

### 6.2 `services/iyzico_client.py`
- iyzico REST API wrapper (resmi SDK kullanmıyoruz — Python SDK bakımsız).
- Public fonksiyonlar:
  - `create_sub_merchant(payload) -> sub_merchant_id`
  - `init_3ds(order, sub_merchant_id) -> htmlContent + conversation_id`
  - `retrieve_payment(conversation_id) -> payment_status` (callback gelmezse kullanılır)
  - `verify_callback_signature(payload, signature) -> bool`
- Retry + backoff içinde.

### 6.3 `services/earsiv_client.py`
- Sağlayıcı-bağımsız arayüz: `issue_receipt(order) -> ReceiptResult`.
- Concrete implementasyonlar: `ForibaClient`, `UyumsoftClient`, `LogoClient`.
- Config'ten seçilen sağlayıcıyı döndüren factory.

## 7. Güvenlik modeli

### 7.1 Gruplar (res.groups)
- `hashtap.group_manager` — restoran sahibi/müdür, her şeye erişim.
- `hashtap.group_staff` — garson/kasiyer, sipariş görüntüleme ve güncelleme.
- `hashtap.group_kitchen` — mutfak, sadece "hazırlanıyor / hazır" güncellemesi.
- `hashtap.group_readonly_analytics` — muhasebeci/dışarıdan bakan, sadece raporlar.

Her grup hem Odoo'nun kendi model access'lerini hem `hashtap_pos`'un kayıt kurallarını kalıtır.

### 7.2 Record rules
- `pos.order` kuralları: kullanıcı sadece kendi şubesi/konseptinin siparişlerini görür.
- `hashtap.menu.item`: yazma yetkisi sadece manager + kitchen chef grubu (menü yönetimi).

### 7.3 Public controller güvenliği
- Her public uç tenant_slug içerir; kullanıcı başka tenant'a geçemez (gateway doğrular ama biz de kontrol ederiz).
- Sepet üzerinde fiyat manipülasyonu imkansız (§5.2 kuralı).
- `order_access_token` PWA'ya sipariş oluştururken verilir; sipariş durumu sorgusu için zorunlu.

## 8. Hook noktaları

### 8.1 Odoo'dan extend ettiklerimiz
- `pos.order._order_fields()` — `hashtap_state` alanı için.
- `pos.order._process_order()` — sipariş iş akışına girerken HashTap mantığımızı çağır.
- `restaurant.table` — QR slug alanı ve hesaplama.

### 8.2 HashTap'in kendi hook'ları
- `hashtap_pos.order_paid` Odoo event bus — diğer modüller (ileride sadakat, rapor) dinleyebilir.
- `hashtap_pos.receipt_issued` — e-Arşiv başarılı olduğunda yayımlanır.
- `hashtap_pos.kitchen_fire` — sipariş mutfağa gönderildiğinde (print-bridge veya KDS burayı dinler).

## 9. Async jobs (`queue_job`)

OCA'nın `queue_job` modülünü kullanıyoruz. Job'lar:
- `hashtap.issue_earsiv_receipt(order_id)` — ödeme sonrası fiş kesme.
- `hashtap.notify_kitchen(order_id)` — print-bridge ve KDS'e event.
- `hashtap.iyzico_retrieve_on_timeout(conversation_id)` — callback gelmezse.

Her job idempotent: aynı order_id ikinci kez tetiklenirse no-op.

## 10. Test stratejisi

- **Unit:** `services/` altındaki saf Python fonksiyonlar (pricing özellikle).
- **Integration (Odoo TransactionCase):** model + controller seviyesi, gerçek DB ile.
- **E2E:** PWA → gateway → Odoo → (mock iyzico/e-arşiv) → asserts. Bu `apps/customer-pwa/e2e/` altında Playwright ile, gateway'i mock Odoo'ya yönlendiren docker-compose profiliyle.

Kapsam hedefi: servis katmanı %90+, controller %70+, ORM extension'ları koverable oranında.

## 11. Eklenmemiş konular (bilerek)

- **Çoklu şirket:** Odoo'nun `res.company` ayrımı var; HashTap'in "çoklu konsept" modeli bunun üstüne oturacak ama MVP'de tek şirket. Faz 7+ konusu.
- **Sadakat / kampanya:** MVP dışı.
- **Rezervasyon:** Modülde yer yok; gelecek modül.
- **Mobil kasiyer uygulaması:** Odoo'nun POS client'ı kullanılabilir; HashTap'in ayrı bir mobil "kasa" uygulaması MVP'de yok.
