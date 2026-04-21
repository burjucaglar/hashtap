# iyzico Entegrasyonu

Bu doküman HashTap'in ödemeyi nasıl aldığını, parayı nasıl restoran hesabına akıttığını, 3DS akışını, webhook doğrulamayı ve hata senaryolarını tanımlar.

## 1. Model: Facilitator (subMerchant)

HashTap **aggregator değil, facilitator**. Yani para HashTap'in hesabından geçip restorana gitmez — iyzico subMerchant modeliyle para doğrudan restoranın banka hesabına yatar. HashTap bu akışın "teknolojik arabulucusu"dur.

Bu ayrımın önemi:
- **MASAK / BDDK lisansı gerekmiyor.** Ödeme kuruluşu / elektronik para kuruluşu olmuyoruz.
- **Mali risk düşük.** Chargeback, fraud, vergi — çoğu restoranın sorumluluğunda.
- **Ticari gelir:** iyzico'nun komisyonu üstüne restoran rızasıyla küçük bir HashTap payı (mesela %0.1–0.3 facilitator fee) — sözleşmeye bağlanmalı, hukuki doğrulama gerekiyor.

Detaylı ayrım için: `docs/PRODUCT.md` §5 + `adr/0004-odoo-base.md` dışındaki yasal tarafı tartışan ek ADR ileride açılabilir.

## 2. subMerchant onboarding

Her HashTap kiracısı iyzico tarafında bir subMerchant olur. Onboarding tenant provisioning'in parçası (`MULTI_TENANCY.md` §3.1).

### 2.1 Gerekli bilgiler
- **Restoranın yasal adı / ünvanı.**
- **Vergi numarası.**
- **IBAN.**
- **Adres, telefon, imza yetkilisi.**
- **Banka ve şube bilgileri.**

### 2.2 API çağrıları
- `POST /onboarding/submerchant/create` → subMerchantKey döner.
- `POST /onboarding/submerchant/update` → bilgi değişikliklerinde.
- `GET /onboarding/submerchant/retrieve` → mevcut durum.

iyzico'nun farklı subMerchant tipleri var: `PRIVATE_COMPANY`, `LIMITED_OR_JOINT_STOCK_COMPANY`, `PERSONAL`. Restoran tüzel kişiliği tipini belirler.

### 2.3 Sözleşme akışı
- Restoran HashTap'e kaydolurken iyzico'nun subMerchant sözleşmesini de dijital imzalar.
- HashTap onboarding flow'u bu adımı zorunlu tutar — iyzico sözleşmesi imzalanmadan kiracı `active`'e geçmez.
- Sözleşmenin detayı iyzico ile HashTap arasındaki master agreement'a bağlıdır (KYC delegation mümkün mü, vb).

### 2.4 HashTap ayarlarında saklanan
- `hashtap_iyzico_sub_merchant_key` (per-tenant, res.config.settings).
- API key ve secret **per-tenant değil, HashTap-wide.** HashTap iyzico'nun master merchant'ıdır; kiracılar subMerchant.

## 3. 3DS ödeme akışı (mutlu yol)

```
PWA          Gateway          Odoo (hashtap_pos)         iyzico          Banka
 │              │                     │                      │               │
 │  cart+pay──► │                     │                      │               │
 │              │  create order ────► │                      │               │
 │              │  (pos.order draft)  │                      │               │
 │              │ ◄──── order_id +    │                      │               │
 │              │       access_token  │                      │               │
 │  ◄───────────┤                     │                      │               │
 │              │                     │                      │               │
 │  3ds start ► │                     │                      │               │
 │              │  init 3ds ────────► │                      │               │
 │              │  (with kart bilgisi │                      │               │
 │              │   PWA'dan)          │                      │               │
 │              │                     │  create 3ds ──────► │               │
 │              │                     │                     │ authRequired → │
 │              │                     │ ◄──── htmlContent ──┤                │
 │              │ ◄── htmlContent ──  │                      │               │
 │ ◄── html ────┤                     │                      │               │
 │                                                                           │
 │  [PWA 3DS iframe/redirect]                                                │
 │ ──────────────────── bank 3ds challenge ────────────────────────────────► │
 │ ◄───────────────────── success ──────────────────────────────────────────┤
 │                                                                           │
 │                                                     iyzico callback       │
 │                             ◄───── POST /callback ──┤                    │
 │              │ ◄── callback ──────┤                                      │
 │              │ verify signature ► │                                      │
 │              │ mark paid ───────► │                                      │
 │              │                    │ issue e-Arşiv (queue) ───► ...       │
 │              │                    │ fire kitchen (queue)     ───► ...    │
 │              │ ◄──── OK ──────────┤                                      │
 │              │                                                           │
 │  poll status │                                                           │
 │              │ status: paid ─► ...                                       │
```

## 4. Controller'lar

### 4.1 Gateway → Odoo: `/hashtap/payment/3ds/start`

**Girdi:**
```json
{
  "order_id": "ORD-2026-000123",
  "payment_session_token": "...",
  "card": {
    "holder_name": "MEHMET A",
    "number": "5528790000000008",
    "expire_month": "12",
    "expire_year": "2030",
    "cvc": "123"
  },
  "buyer": {
    "name": "Mehmet",
    "surname": "Arslan",
    "email": "mehmet@example.com",
    "ip": "213.74.xxx.xxx"
  }
}
```

**PCI notu:** Kart bilgisi gateway'den Odoo'ya gidiyor — ikisi de kart verisine "dokunuyor". Bu, **PCI SAQ-A** kapsamından çıkar, **SAQ-A-EP**'ye girer.

**Daha güvenli alternatif:** iyzico'nun `iyzicoCheckoutForm` mekanizması — kart iyzico'ya **doğrudan** gider, HashTap sunucuları görmez. PCI SAQ-A'da kalır. MVP için bu tercih edilir.

**Karar:** MVP'de `iyzicoCheckoutForm` kullanılır. Yukarıdaki kart alanları PWA → iyzico arasında, hashtap sunucuları görmez. Controller sadece `payment_session_token` ve `order_id` alır, iyzico'dan form URL'i döndürür.

**Revise edilmiş girdi:**
```json
{
  "order_id": "ORD-2026-000123",
  "payment_session_token": "...",
  "buyer": { ... }   // kimlik, teslimat yok; iyzico zorunlu kılıyor
}
```

**Çıktı:**
```json
{
  "checkout_form_url": "https://sandbox-cpp.iyzipay.com/...",
  "conversation_id": "..."
}
```

PWA bu URL'e redirect eder. iyzico kendi ekranında kartı/Apple Pay'i toplar.

### 4.2 iyzico → Gateway → Odoo: `/hashtap/payment/3ds/callback`

iyzico ödemeyi bitirdikten sonra (başarılı/başarısız) ikisini de çağırır:
1. `callbackUrl` (sync, kullanıcı redirect'i).
2. `webhookUrl` (async, güvenilir onay).

HashTap ikisini de dinler; **asıl `paid` işaretleme webhook'tan gelir**. Callback sadece kullanıcıya "başarılı" sayfası göstermek içindir.

**Webhook doğrulama:**
1. iyzico'nun header'da verdiği `x-iyz-signature` HMAC.
2. Payload + api_secret ile yeniden HMAC hesapla, eşleşmezse 401.
3. `conversationId` DB'de aranır. Yoksa 404 (duplicate'ler için 200 dön, idempotent).

**İdempotency:**
- `hashtap.iyzico.transaction.correlation_id` unique.
- Aynı callback iki kez → ikinci sefer no-op (transaction zaten `paid`).
- Edge case: webhook ile callback yarışı → webhook kazanır, idempotent.

## 5. Apple Pay / Google Pay

iyzico'nun Checkout Form'u zaten Apple Pay & Google Pay butonlarını gösteriyor (iyzico merchant Apple Pay/Google Pay için iyzico tarafında etkinleştirilmişse).

### Apple Pay önkoşulları
- Apple Developer hesabı (HashTap adına).
- Merchant ID tanımla.
- Domain verification (PWA domain'i için `.well-known/apple-developer-merchantid-domain-association` dosyası — gateway'de host edilir).
- iyzico merchant panelinde Apple Pay sertifikası yüklü.

### Google Pay önkoşulları
- Google Pay & Wallet Console'dan onay.
- iyzico merchant panelinde aktif.

**MVP için zorunlu mu?** Evet (PRODUCT.md'de değer önerisi olarak söz verildi). Fakat Apple Pay domain verification 1-2 haftayı bulabilir — faz 4'te ayrıca buffer'lı.

## 6. Hata senaryoları

| Senaryo | HashTap davranışı |
|---|---|
| iyzico API 500 döner (create init) | PWA'ya "geçici hata" göster, sipariş `pending_payment` kalır, kullanıcı tekrar deneyebilir |
| iyzico API timeout | 10 saniye timeout, aynı davranış |
| Kart reddedildi | iyzico'nun reason code'u mesaja çevrilir ("bakiye yetersiz", "kart bloke"). Sipariş `pending_payment` kalır, kullanıcı farklı kart deneyebilir. |
| 3DS challenge kullanıcı tarafından iptal | PWA redirect'le "iptal ettin" sayfası. Sipariş `cancelled_by_customer`. |
| Webhook hiç gelmez (iyzico ağ) | Cron her 5 dakikada pending transaction'ları tarayıp `retrievePayment` çağrısı atar. 30 dakika sonra hâlâ pending ise sipariş `cancelled`. |
| Webhook imza geçersiz | 401 + alarm (potansiyel saldırı). |
| Webhook başarılı ama Odoo paid işaretlerken hata | Retry. Webhook'a 500 dönmeyin — iyzico 24 saat exponential backoff'la yeniden gönderir. 200 dönün, işi queue_job'a at, oradan tekrarlı dene. |
| Duplicate webhook | `correlation_id` unique olduğu için INSERT başarısız → idempotent. |
| Subscription/recurring | MVP'de yok. |
| Refund talebi | iyzico'nun `refund` endpoint'i + Odoo tarafında `pos.order.refund`. Faz 2+ konusu. |

## 7. Para akışı ve mutabakat

### 7.1 Settlement
iyzico subMerchant modunda settlement (restoran hesabına yatış):
- **Varsayılan:** T+2 iş günü.
- iyzico SFTP ile günlük settlement dosyası gönderir (CSV).
- HashTap bu dosyayı parse edip Odoo'ya bank statement olarak import eder — muhasebe mutabakatı için.

### 7.2 Komisyon
- iyzico'nun oranı (örn Visa %1.99 + 0.25 TL) subMerchant'a kesilir.
- Ek olarak HashTap facilitator fee (sözleşmeye bağlı) — iyzico'nun API'sinde `subMerchantFee` alanı ile tanımlanır; işlem başına otomatik HashTap hesabına gider.

### 7.3 Mutabakat
- Günlük cron: `pos.order` listesi vs iyzico settlement CSV'si → fark raporu.
- Fark varsa panel uyarısı.

## 8. Güvenlik

- **API key / secret saklama:** Odoo `ir.config_parameter` table'ına encrypted. Rotasyon yılda 1, iyzico merchant panelinden.
- **Webhook URL:** sadece iyzico IP aralığından kabul et (nginx whitelist).
- **HMAC secret:** webhook body değişmeden imzalanır; body-rewrite proxy yasak.
- **Log:** Kart PAN'ı / CVV / tam expiry loglanmaz. PCI DSS kuralı.

## 9. Test stratejisi

- **Sandbox kartlar:** iyzico test PAN'ları (`5528790000000008` 3DS zorunlu, vb).
- **Unit test:** `services/iyzico_client.py` wrapper'ı mock ile, imza doğrulama ayrı test.
- **Integration test:** sandbox'a gerçek istek → callback mock simulation.
- **E2E test:** Playwright ile PWA → iyzico sandbox → callback → sipariş `paid`.
- **Chaos test:** webhook imza değişikliği, duplicate webhook, aşırı gecikmeli webhook.

## 10. Açık sorular

- iyzico Apple Pay için HashTap'in master merchant'ı mı yoksa subMerchant Apple Pay mi? — iyzico satış ekibiyle netleşsin.
- Facilitator fee yasal çerçeve: Hukuki görüş alınmalı. MVP pilot aşamasında fee=0 ile başlamak seçeneği.
- Currency conversion: Turist kart kullanırsa TRY → EUR conversion iyzico'da otomatik mi? Araştırılmalı.

## 11. Uygulama notu — adapter pattern (Faz 4 çıktısı)

Kod `odoo-addons/hashtap_pos/adapters/` altında, sağlayıcı-bağımsız
arayüz:

```
adapters/
├── base.py        # BasePaymentAdapter, InitPaymentRequest/Result, CallbackResult
├── registry.py    # get_adapter(code) → adapter instance
├── mock.py        # dev/test için deterministik adapter (stub 3DS akışı)
└── iyzico.py      # gerçek iyzico entegrasyonu (iyzipay SDK ile)
```

- Controller (`controllers/payment.py`) her zaman `registry.get_adapter(...)`
  üzerinden konuşur; iyzico bağımlılığı sızmaz.
- Seçim `hashtap.payment.provider` modelindeki `code` alanıyla yapılır —
  varsayılan `mock`, prod kiracıda `iyzico`.
- Callback URL formatı: `/hashtap/payment/callback/<provider_code>?token=<provider_ref>`.
  Stub modunu tetikleyen `&stub=1` query parametresi sadece mock adapter'da
  anlamlıdır (bir bug'dan çıkardığımız ders: query string inşa ederken
  sabit `?` yerine koşullu `&/?` kullan).
