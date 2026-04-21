# e-Arşiv Entegrasyonu

Bu doküman HashTap'in her ödenmiş siparişten sonra e-Arşiv fişini nasıl kestiğini, fail-close politikasını, sağlayıcı seçimini ve yaşam döngüsünü tanımlar.

## 1. Neden önemli

Türkiye'de perakende satışta her siparişe fiş kesmek yasal zorunluluk. Eski ÖKC (yazar kasa) dünyasından e-Arşiv (elektronik fiş) dünyasına geçiş sürüyor; 2026 itibarıyla belirli cirolarda elektronik mecburi.

**HashTap'in rolü:** Ödeme alındığında otomatik, insan müdahalesi olmadan fiş keser. Kesilmezse **sipariş mutfağa gitmez** (fail-close). Bu kural ticari itiraza rağmen esnetilmez.

## 2. Fail-close politikası

### Kuralın özü
Sipariş `paid` olduysa ama fişi kesilmediyse, sistem otomatik olarak siparişi mutfağa göndermez. Müşteri ödemiş, restoran parayı almış — ama yasal belgesi olmayan bir servis vermek vergi riski ve denetim sorunudur.

### Davranış
- Ödeme başarılı → sipariş `paid`.
- Fiş kesme (sync veya kısa retry'la) → başarılıysa sipariş `kitchen_fired`, mutfak tetiklenir.
- Fiş kesilmezse → sipariş durumu `paid_no_receipt`, restoran paneline kritik alarm, müşteri PWA'sında "fişiniz hazırlanıyor" yazar (mutfak tetiklenmez).
- Fiş yeniden kesilebilirse (retry başarılı) → sipariş `kitchen_fired`, mutfak normal akış.

### Müşteri eğitimi
Pilot restoranda sahibi bu davranıştan rahatsız olabilir ("ödeme aldım, niye pişmiyor?"). Onboarding'de açıkça anlatılır: e-Arşiv sağlayıcıda arıza olduğunda, vergi cezası riski nedeniyle otomatik durdurulur. Genellikle bu durum 1-2 dakika sürer (retry).

### İstisna?
Yok. Bu kuralı esnetmek için somut bir senaryo ortaya çıkarsa yazılı ADR gerekir.

## 3. Sağlayıcı seçimi

Türkiye'de e-Arşiv özel entegrasyon sağlayıcıları:

| Sağlayıcı | Artıları | Eksileri |
|---|---|---|
| **Foriba** | Pazarda en yaygın, API olgun, SaaS deneyimi çok | Fiyat orta-yüksek |
| **Uyumsoft** | Yerel, teknik destek Türkçe ve hızlı | API eski tarafta, XML-ağırlıklı |
| **Logo eFatura** | ERP entegrasyonu geniş | API karmaşık, onboarding yavaş |
| **İDEASOFT / Kolaysoft** | Daha küçük ama modern REST | Büyük ölçekte referans az |

**MVP için öneri: Foriba.** Yaygınlık, dokümantasyon kalitesi, ve subMerchant benzeri "partner API"si HashTap'e uygun.

**Stratejik:** `services/earsiv_client.py` sağlayıcı-bağımsız arayüz; ileride Uyumsoft veya başka bir sağlayıcıya geçiş core kod değişikliği gerektirmez.

## 4. Fiş kesme akışı

```
pos.order.paid event
       │
       ▼
queue_job: hashtap.issue_earsiv_receipt(order_id)
       │
       ▼
earsiv_client.issue_receipt(order)
       │
       ├─ provider API call (sync, 10s timeout)
       │
       ├─ success → ReceiptResult(ettn, pdf_url, qr_content)
       │           ├─ hashtap.earsiv.receipt kaydı oluştur (state='issued')
       │           ├─ pos.order.hashtap_receipt_id güncelle
       │           └─ event: hashtap_pos.receipt_issued
       │                        │
       │                        └─► queue_job: hashtap.notify_kitchen(order_id)
       │
       └─ failure → ReceiptResult(error, retryable=True/False)
                   ├─ hashtap.earsiv.receipt kaydı (state='failed', last_error)
                   ├─ retryable ise: queue_job exponential backoff (1dk, 5dk, 15dk, 30dk, 1h)
                   ├─ retryable değilse: manuel müdahale alarmı
                   └─ mutfağa TETİKLEME YOK (fail-close)
```

## 5. Sağlayıcı-bağımsız arayüz

```python
# services/earsiv_client.py

class ReceiptData:
    ettn: str
    pdf_url: str
    qr_content: str
    issued_at: datetime
    provider_response: dict

class ReceiptError:
    code: str          # "INVALID_VAT", "PROVIDER_DOWN", "AUTH_FAILED", ...
    message: str
    retryable: bool
    raw_response: dict

class EArsivClient(Protocol):
    def issue_receipt(self, order: PosOrder) -> ReceiptData | ReceiptError: ...
    def cancel_receipt(self, ettn: str, reason: str) -> None: ...
    def retrieve_receipt(self, ettn: str) -> ReceiptData: ...

class ForibaClient(EArsivClient):
    # REST + JSON implementasyonu
    ...

class UyumsoftClient(EArsivClient):
    # SOAP + XML implementasyonu
    ...

class MockClient(EArsivClient):
    # Dev/test için; local mock server; yapılandırılabilir fail rate
    ...
```

## 6. Veri dönüşümü

Odoo'nun `pos.order` modeli → e-Arşiv fiş XML/JSON şeması:

| Odoo alan | e-Arşiv alan |
|---|---|
| `pos.order.name` (sequence) | `faturaNumarasi` |
| `pos.order.date_order` | `faturaTarihi` |
| `pos.order.lines.name` | `malHizmet.ad` |
| `pos.order.lines.qty` | `malHizmet.miktar` |
| `pos.order.lines.price_unit` | `malHizmet.birimFiyat` |
| `pos.order.lines.price_subtotal` | `malHizmet.matrah` |
| `pos.order.lines.tax_ids` | `malHizmet.kdvOrani` |
| `pos.order.amount_total` | `toplamTutar` |
| `res.company.vat` | `saticiVknTckn` |
| `hashtap.customer_contact.vkn` (varsa) | `aliciVknTckn` (aksi halde "11111111111") |

**Alıcı bilgileri:** Müşteri bilinmiyorsa (QR siparişleri çoğu) "müstahsil/genel alıcı" formatı kullanılır; T.C. kimlik no alanı "11111111111" (11 karakter 1) olur. Bu GİB tarafından kabul edilir.

## 7. KDV dağıtımı

Bir sipariş birden fazla KDV oranı içerebilir (yemek %10, içecek %20, alkollü %20).

Odoo'nun kendi `account.tax` mekanizması her satırda hangi oranın uygulandığını belirler. Fiş XML'inde kalem bazında KDV oranı gönderilir — "aggregate" değil, "itemized". e-Arşiv GİB formatı itemized olarak zaten tanımlar.

## 8. Özel durumlar

### 8.1 İade
- Müşteri siparişi iptal ettirdi ve ödeme iade edildi.
- HashTap `pos.order.hashtap_state = 'refunded'`.
- `earsiv_client.cancel_receipt(ettn, reason)` → iade fişi keser.
- İade fişi de Odoo'da kayıt altında.

### 8.2 Çok büyük sipariş (limit üstü)
- e-Arşiv'in üst limiti var (şu an 13.000 TL, güncellenebilir — GİB kararı). Limit üstünde e-Fatura zorunlu.
- MVP'de ≥13.000 TL sipariş çok nadir (restoran ortalama sepet 150–500 TL). Gelirse: manuel alarm, operasyon ekibi e-Fatura düzenler.

### 8.3 Yabancı müşteri
- Turist ödediğinde e-Arşiv kesilir ama "aliciVknTckn" yine "11111111111". KDV iadesi talep ederse manuel süreç (MVP dışı).

### 8.4 Şirket müşterisi (B2B)
- "Fatura istiyorum" butonu — müşteri VKN/TCKN girer.
- HashTap kayıt alanları kullanılır; e-Arşiv fişi alıcı bilgileriyle kesilir.
- MVP'de opsiyonel olarak mevcut, varsayılan kapalı.

## 9. Arşivleme ve yasal süre

- **Saklama süresi:** e-Arşiv fişleri 10 yıl saklanmak zorunda (VUK).
- **Birincil saklama:** sağlayıcı (Foriba) kendi sisteminde saklar, GİB'e iletir.
- **İkincil (HashTap):** fiş PDF'i ve QR içeriği `hashtap.earsiv.receipt` kaydında — Postgres blob veya attachment.
- **Yedek:** Tenant yedekleri kapsamında (`MULTI_TENANCY.md` §6).

## 10. Güvenlik

- **API key saklama:** Odoo `ir.config_parameter`'da encrypted.
- **Fiş PDF'leri:** müşteri PWA'sına indirilebilir linkle sunulur (order'ın `access_token`'ı ile gated). Public internet erişilemez.
- **Kişisel veri:** KVKK kapsamında. Fiş saklama süresi (10 yıl) KVKK'nın sonsuz saklamama zorunluluğu ile çelişmez — vergi mevzuatı üstünlüğü vardır (KVKK 5.2.d).

## 11. Test

- **Sağlayıcı sandbox:** Foriba sandbox hesabı. Mock fiş kesme.
- **Chaos test:** Sağlayıcı API kasıtlı olarak %50 fail olacak şekilde mock. Retry mekanizması doğrulanır.
- **Fail-close doğrulama:** bir test siparişi → e-Arşiv mock'u 503 dönsün → sipariş `paid_no_receipt`'te kalıyor, mutfak tetiklenmiyor, alarm yükseliyor.
- **Retry doğrulama:** Aynı test → mock normale dönünce → retry başarılı → sipariş `kitchen_fired`, mutfak tetikleniyor.

## 12. Açık sorular

- Foriba vs Uyumsoft pricing tablosu — pilot başlamadan karşılaştırılmalı.
- GİB e-Arşiv v2.0 geçişi (yakın tarihli değişiklikler varsa) bu dokümanda atlanmış olabilir — implementasyon başlarken en güncel GİB kılavuzu okunur.
- e-Arşiv iptali (cancel) sağlayıcı tarafında kaç saate kadar mümkün — Foriba dokümantasyonu kontrol edilmeli.
- Perakende ÖKC'si olan restoranlarda HashTap'in e-Arşiv'le ilişkisi: bazı restoranlar hâlâ ÖKC kullanıyor; ÖKC ve e-Arşiv aynı siparişe iki fiş kesmemeli (mükerrer). Pilot müşteride ÖKC var mı, baştan sorulmalı.

## 13. Uygulama notu — adapter pattern (Faz 5 çıktısı)

Kod `odoo-addons/hashtap_pos/adapters/earsiv/` altında:

```
adapters/earsiv/
├── base.py        # BaseEarsivAdapter, IssueReceiptRequest/Result
├── registry.py    # get_adapter(code) → adapter instance
├── mock.py        # dev/test; başarı + başarısızlık simülasyonu
└── foriba.py      # Foriba sağlayıcısı (prod hedef)
```

- Sipariş `paid` olunca `hashtap.order.models.hashtap_order` içinden
  `get_earsiv_adapter(provider_code)` çağrılır; sağlayıcı bağımlılığı
  model kodundan dışarıda kalır.
- Seçim: kiracıda seed edilen `hashtap.earsiv.provider` kaydının `code`
  alanı. Dev ortamda `mock`, prod'da `foriba`.
- **Fail-close uygulaması:** `hashtap.order.is_earsiv_blocked` computed
  alanı (`require_receipt=True AND earsiv_state != "issued"`) mutfağa
  gönderme aksiyonunda kontrol edilir. True ise `ValidationError`.
- **Orthogonal state axes:** `state` (sipariş yaşam döngüsü),
  `payment_state` (ödeme), `earsiv_state` (fiş) üç bağımsız eksen —
  `DATA_MODEL.md` §2.7'deki tek-eksenli state akışının güncel hali.

Sağlayıcı seed scripti: `odoo-addons/hashtap_pos/scripts/seed_earsiv_mock.py`.
