# HashTap — Mimari (Revize: Odoo-tabanlı)

Bu doküman projenin teknik büyük resmini kayıt altına alır. Faz 0'da TS/Node-çekirdekli bir mimari çizilmişti; ürün stratejisi değişti (Odoo 17 CE üstüne `hashtap_pos` modülü). Bu belge yeni mimariyi anlatır; eski mimarinin kalıntıları (`apps/api`, `customer-pwa`) nasıl yeni role evrildiklerini de belirtir.

İlgili ADR'ler:
- `adr/0004-odoo-base.md` — Odoo seçim gerekçesi
- `adr/0005-module-not-fork.md` — neden core fork değil
- `adr/0006-db-per-tenant.md` — kiracı izolasyonu
- `adr/0007-white-label-strategy.md` — marka gizleme
- `adr/0008-customer-pwa-stays-ts.md` — PWA neden Odoo içinde değil
- `adr/0009-restaurant-dashboard-odoo-native.md` — panel neden Odoo'nun kendi arayüzü
- `adr/0010-v17-lts.md` — sürüm seçimi

## 1. Büyük resim

```
                            ┌─────────────────────────┐
                            │  Müşteri telefonu       │
                            │  (Customer PWA — React) │
                            └───────────┬─────────────┘
                                        │ HTTPS, public
                                        ▼
                            ┌─────────────────────────┐
                            │  HashTap API Gateway    │
                            │  (TS / Fastify)         │
                            │                         │
                            │  - Auth (session)       │
                            │  - Rate limit           │
                            │  - iyzico 3DS orchestr. │
                            │  - Tenant routing       │
                            └───────────┬─────────────┘
                                        │ JSON-RPC / REST
                                        ▼
          ┌─────────────────────────────────────────────────────┐
          │  Per-tenant Odoo 17 CE instance                     │
          │                                                     │
          │  ┌─────────────────────────────────────────────┐    │
          │  │ hashtap_pos  (bizim modülümüz, LGPL)        │    │
          │  │  - Public controllers (menu, order, pay)    │    │
          │  │  - Custom data models (menu, qr, modifier)  │    │
          │  │  - iyzico + e-Arşiv adapter                 │    │
          │  │  - POS adapter yönlendirmesi (Segment B)    │    │
          │  └─────────────────────────────────────────────┘    │
          │                                                     │
          │  ┌─────────────────────────────────────────────┐    │
          │  │ hashtap_theme  (white-label)                │    │
          │  └─────────────────────────────────────────────┘    │
          │                                                     │
          │  ┌─────────────────────────────────────────────┐    │
          │  │ Odoo stock modülleri:                       │    │
          │  │  - pos_restaurant (masa, KDS)               │    │
          │  │  - point_of_sale                            │    │
          │  │  - account, stock, mrp (reçete/düşüm)       │    │
          │  │  - web                                      │    │
          │  └─────────────────────────────────────────────┘    │
          │                                                     │
          │  PostgreSQL (DB-per-tenant)                         │
          └──────────────┬──────────────────────────────────────┘
                         │
      ┌──────────────────┼──────────────────┬────────────────────┐
      ▼                  ▼                  ▼                    ▼
┌───────────┐     ┌────────────┐    ┌────────────────┐   ┌─────────────┐
│  iyzico   │     │  e-Arşiv   │    │  Print Bridge  │   │  Harici POS │
│  (3DS +   │     │  sağlayıcı │    │  (Pi + ESC/POS)│   │  (Segment B)│
│  subMerch)│     │            │    │                │   │             │
└───────────┘     └────────────┘    └────────────────┘   └─────────────┘
```

## 2. Bileşenler ve sorumluluklar

### 2.1 Customer PWA (`apps/customer-pwa/`)
- **Dil/teknik:** TypeScript, React 18, Vite, `vite-plugin-pwa`.
- **Sorumluluğu:** QR akışı — menü gösterimi, sepet, ödeme başlatma, sipariş durumu.
- **Kapsam dışı:** Ürün mantığı (fiyat hesabı), auth mantığı, persistence. Tamamen görüntüleme ve UX.
- **Nasıl konuşuyor:** HashTap API Gateway'e REST. Odoo'ya doğrudan konuşmuyor — izolasyon ve rate-limit için gateway mecbur.
- **Neden Odoo içinde değil:** ADR-0008.

### 2.2 HashTap API Gateway (`apps/api/`)
- **Dil/teknik:** TypeScript, Fastify, Postgres (gateway'in kendi küçük DB'si — tenant registry için), Redis (rate limit, iyzico state).
- **Sorumluluğu:**
  - Public internet'in tek giriş kapısı.
  - `r.example.com` (müşteri) ve `sirket.example.com` (restoran paneli) trafiğini doğru Odoo instance'ına yönlendirme.
  - Rate limiting (tenant başı, IP başı).
  - iyzico 3DS akışının orkestrasyonu: PWA'nın görmemesi gereken secret'lar gateway'de.
  - Webhook alıcı: iyzico callback, e-Arşiv callback.
  - Auth: müşteri oturumları (QR'den türetilmiş kısa-ömürlü token), admin JWT'leri.
- **Kapsam dışı:** İş mantığı yok. "Thin BFF" — data massage et, auth/rate-limit katmanı, Odoo'ya yönlendir.
- **Eski plandan fark:** Faz 0'da `apps/api` siparişin beynini içeriyordu; şimdi Odoo aldı, gateway hafifledi.

### 2.3 Odoo instance (per-tenant)
- **Sürüm:** 17 LTS (CE).
- **Çalışma modeli:** Her kiracı için ayrı Odoo worker + ayrı Postgres DB. Aynı filestore/attachment dizini paylaşılmaz.
- **Sorumluluğu:**
  - Tüm iş mantığı: sipariş, menü, stok, muhasebe, raporlama.
  - Restoran paneli kullanıcı arayüzü (Odoo native, white-label).
  - `hashtap_pos` modülü aracılığıyla HashTap-spesifik akışlar.
- **Dokunmadığımız:** Odoo core. Tüm özelleştirme modül katmanında. ADR-0005.

### 2.4 `hashtap_pos` modülü
- **Dil:** Python (Odoo modülü).
- **Lisans:** LGPLv3 (Odoo CE ile uyumlu).
- **Sorumluluğu:**
  - Public HTTP controller'lar: `/hashtap/menu/<tenant>/<table>`, `/hashtap/order`, `/hashtap/payment/3ds/start`, `/hashtap/payment/3ds/callback`.
  - Custom modeller: `hashtap.menu.item` (i18n alanlarıyla), `hashtap.table.qr`, `hashtap.modifier.group`, vb.
  - iyzico adapter (subMerchant CRUD, ödeme başlatma, callback doğrulama).
  - e-Arşiv adapter (fail-close politika uygulayan).
  - Dış POS adapter yönlendirmesi (Segment B kiracıları için Odoo modüllerini devre dışı bırakıp adapter'ı aktive eden anahtar).
- **Detaylı iç yapı:** `MODULE_DESIGN.md`.

### 2.5 `hashtap_theme` modülü
- **Sorumluluğu:** Tüm white-label uygulaması. ADR-0007.
  - Logo, renk paleti, login ekranı, app switcher, e-posta şablonları.
  - "Odoo" markasının görünmediği her yerde HashTap'in görünmesi.
- **Neden ayrı modül:** `hashtap_pos` iş mantığı, `hashtap_theme` sunum. Ayrık tutmak hem değişiklik hızını yükseltir hem de ileride "HashTap POS whitelabel-edilmiş bir üçüncü marka olarak satılsın" senaryosunda yeniden temalamaya izin verir.

### 2.6 Print Bridge (`apps/print-bridge/`)
- **Dil/teknik:** Node.js, WebSocket client, `node-thermal-printer`.
- **Donanım:** Raspberry Pi + ESC/POS yazıcı.
- **Sorumluluğu:** Odoo'dan event geldiğinde yazıcıya fiş basmak. Kiracının fiziksel mutfağında koşan küçük ajan.
- **Nasıl konuşuyor:** Gateway üzerinden değil, doğrudan Odoo'nun websocket endpoint'ine (veya gateway'in pass-through WS ucuna — faz 6'da karar). Kiracı-özel token ile.

### 2.7 Harici POS adapter'lar (`packages/pos-adapters/`)
- Segment B müşterileri için. Kiracı "kendi POS'uma bağlı kal" derse, Odoo'nun iç sipariş akışı kapanır ve siparişler doğrudan bu adapter üzerinden dışarıdaki POS'a gider.
- Adapter'lar `hashtap_pos` içindeki Python köprüsü aracılığıyla çağrılır (HTTP mikroservis veya subprocess).

## 3. Kiracı izolasyonu

**Model:** DB-per-tenant. Detay: ADR-0006 + `MULTI_TENANCY.md`.

Özet:
- Her kiracı için bir Postgres DB (`tenant_abc123`).
- Her kiracı için bir Odoo worker container'ı veya aynı worker pool'undan seçilen bir instance, DB-bazlı route.
- Gateway'in kendi DB'sinde sadece tenant registry (slug → DB/host mapping) + auth.
- Müşteri PWA ve restoran paneli subdomain ile ayrılır: `sirket.example.com`.
- Veri sızıntısı saldırı yüzeyi: sadece gateway'in routing kodu + Odoo'nun DB seçim mantığı. Kiracı kodu hiçbir yerde başka kiracı DB'sine erişemez.

## 4. Veri akışları (mutlu yol)

### 4.1 Menü çekme
1. PWA: `GET r.example.com/v1/menu/<tenant_slug>/<table_slug>`
2. Gateway: tenant registry'den Odoo host bul → forward.
3. Odoo (`hashtap_pos`): menü sorgula, i18n ile döndür.
4. Gateway: cache (Redis, 60s), PWA'ya dön.

### 4.2 Sipariş + ödeme
1. PWA: `POST /v1/order` (sepet içeriği).
2. Gateway → Odoo: `POST /hashtap/order`. Odoo fiyatı **sunucu tarafında** yeniden hesaplar (PWA'ya güven yok).
3. Odoo: `pos.order` draft oluştur, `order_id` dön.
4. PWA: `POST /v1/payment/3ds/start` (order_id ile).
5. Gateway → iyzico: 3DS session başlat (subMerchant ID = kiracı).
6. iyzico redirect → PWA → banka → iyzico callback → Gateway.
7. Gateway: imza doğrula, idempotency kontrolü, Odoo'ya `POST /hashtap/payment/3ds/callback`.
8. Odoo (`hashtap_pos`):
   a. Sipariş `paid` işaretle.
   b. **e-Arşiv kes** (sync). Fail ise → sipariş `paid_no_receipt`, alarm düşür, mutfağa **gitme**.
   c. Başarılıysa → mutfak event'i yay (print-bridge veya `pos_restaurant` KDS).
9. PWA: durum polling → "hazırlanıyor".

### 4.3 Tenant provisioning (faz 8)
1. Admin: `POST gateway-admin/tenants` (restoran bilgileri, iyzico onboarding data).
2. Gateway tenant service:
   a. Yeni Postgres DB oluştur (`tenant_xyz`).
   b. Odoo instance'ına DB oluşturma komutu gönder.
   c. `hashtap_pos` + `hashtap_theme` + gerekli Odoo modüllerini yükle.
   d. Default admin kullanıcı oluştur, şifreyi e-postayla gönder.
   e. DNS kayıt ekle (`sirket.example.com`).
   f. SSL sertifikası al (cert-manager / Let's Encrypt).
   g. Tenant registry'ye kayıt düş.

## 5. Hata modları ve davranış

| Senaryo | Davranış |
|---|---|
| iyzico down | Ödeme başlatılamaz, PWA kullanıcıya "geçici hata" gösterir. Sipariş `created` kalır. |
| iyzico callback hiç gelmez | Gateway 5dk sonra iyzico API'sine sorgu atar (`retrievePayment`). Hâlâ pending ise sipariş otomatik iptal olur. |
| e-Arşiv down | Sipariş `paid`, fakat `paid_no_receipt`. Mutfağa gitmez. Panel alarm basar. Fiş sağlayıcı gelince otomatik retry, başarılı olunca mutfak tetiklenir. |
| Odoo worker crash | Gateway healthcheck'te fark eder, kiracıyı "bakım modu"na alır, PWA'ya 503 döner. Diğer kiracıları etkilemez. |
| Print Bridge offline | Odoo'da event kuyrukta bekler (`queue_job`). Bridge bağlanınca basar. |
| Müşteri PWA offline | Sepet IndexedDB'de; bağlantı gelince senkronize. Ödeme offline olmaz (bilinçli). |

## 6. Teknik kısıtlar ve kurallar

1. **Odoo core'una dokunma.** Tüm değişiklik modül katmanında. Monkey-patch de core değişikliği sayılır — zorunlu kalmadıkça yapma, yaparken gerekçesini ADR ile belgele.
2. **Sunucu tarafı tek gerçek kaynağıdır.** PWA'dan gelen fiyat, KDV, toplam — hiçbirine güvenme. Odoo'da yeniden hesapla.
3. **Para birimi.** Gateway ve PWA katmanında `Kurus` (integer). Odoo kendi para sistemini kullanır (decimal); sınırda dönüştür. ADR-0003 hâlâ geçerli ama kapsamı daraldı.
4. **Çok dilliyi baştan düşün.** TR zorunlu, EN zorunlu. Modül kodunda tüm kullanıcı-yüzlü string'ler `_()` içinde.
5. **Idempotency.** iyzico callback, e-Arşiv retry, print event — hepsi bir `correlation_id` ile idempotent. Aynı event iki kez gelirse iki kez işlenmesin.
6. **Fail-close for tax.** e-Arşiv başarısız → mutfak tetiklenmez. Ticari baskı olsa da bu kuralı esnetmiyoruz.

## 7. Eski mimariden evrim

Faz 0'da yazılan TS kodu ile ne olacağı:

| Eski bileşen | Yeni durum |
|---|---|
| `apps/api` Fastify bootstrap, route stub'ları | Kalır, ama sipariş mantığı silinir; thin BFF'e dönüşür |
| `apps/api` Drizzle şeması (tenants, concepts, tables, menu, orders) | Silinir; sipariş/menü Odoo'da, tenant registry gateway'in küçük DB'sinde kalır |
| `apps/api` order lifecycle state machine | Silinir; Odoo'nun `pos.order` state'i yönetir |
| `packages/shared` zod şemaları | Gateway ↔ PWA için kullanılmaya devam |
| `packages/pos-adapters` | Segment B için kalır, ama çağrılma noktası değişir (gateway değil Odoo köprüsü) |
| `packages/payment` | Silinir; iyzico entegrasyonu `hashtap_pos` Python tarafında |
| `packages/efatura` | Silinir; e-Arşiv `hashtap_pos` Python tarafında |
| `apps/restaurant-dashboard` | **Silinir** — ADR-0009 gereği panel Odoo native olacak |
| `apps/customer-pwa` | Kalır, API adresi değişir |
| `apps/print-bridge` | Kalır, protokol Odoo'ya göre güncellenir |

Temizlik faz 1'in başında yapılır; dokümanlar tamamlandıktan hemen sonra.

## 8. Gelecek düşünceler (faz 3+)

- Çoklu kiracının aynı Odoo worker pool'unu paylaşması (DB-per-tenant + pool-per-region) — ölçeklenme.
- WebSocket/SSE ile polling yerine push (sipariş durumu).
- OpenTelemetry ile tenant-etiketli trace.
- Canary deploy: yeni `hashtap_pos` sürümü önce %5 kiracıda.
