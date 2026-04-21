# HashTap — Yol Haritası

Bu doküman fazları ve her fazın çıktı kriterlerini kayıt altına alır. Takvim tarihleri değil, **hafta sayıları** kullanılır; başlangıç "W1" = koda başlanan ilk hafta.

Her faz için üç bölüm: **hedef, çıktı kriterleri, riskler**. Bir fazın çıktı kriterleri karşılanmadan bir sonrakine geçilmez.

> **Anlık durum → `docs/STATUS.md`.** ROADMAP planı; STATUS gerçeği
> anlatır. Faz bitti işareti ✅ burada göstermelik tutulur; asıl
> güncellik STATUS'tadır.

## Faz 0 — İskele (W0, bitti)

Bu dokümantasyon hazırlanırken tamamlandı. `/home/hashtag/hashtap/` altında monorepo iskelesi, TS/Node tarafında `customer-pwa` + gateway API hazır. Odoo-öncesi plana göre yazıldı; dokümantasyon faz'ı bittikten sonra gateway ve PWA sadeleştirilecek.

## Faz 1 — Odoo temeli + `hashtap_pos` iskelesi (W1–W3) ✅

**Hedef:** Lokal bir Odoo 17 CE instance'ı ayakta, `hashtap_pos` modülü yüklü, "HashTap" markasıyla giriş ekranı görünüyor.

### İş paketleri

| İş | Tahmin |
|---|---|
| `infra/odoo/` altında docker-compose (Odoo + Postgres + Redis) | 2 gün |
| `hashtap_pos` modülü iskelesi (`__manifest__.py`, boş controller, menü kaydı) | 1 gün |
| `hashtap_theme` modülü (logo, renk, login ekranı white-label) | 3 gün |
| `pos_restaurant` modülünü incele, notlarını `docs/POS_RESTAURANT_NOTES.md`'ye düş | 2 gün |
| Developer setup dokümanı güncelle (`DEV_SETUP.md`'yi kod çalıştırılarak doğrula) | 1 gün |

### Çıktı kriterleri
- [ ] `docker compose -f infra/odoo/docker-compose.yml up` ile Odoo `localhost:8069`'da.
- [ ] Yeni veritabanı oluşturma ekranında "HashTap" logosu var, "Odoo" kelimesi görünmüyor.
- [ ] `hashtap_pos` modülü yüklenince Odoo menüsünde "HashTap POS" üst menüsü geliyor (altı boş olabilir).
- [ ] `hashtap_pos` için kabul edilir bir test iskeleti var (bir dummy unit test yeşil).

### Riskler
- Odoo theme sistemi 17'de değişmiş olabilir; beklenenden daha karmaşık.
- Docker image'lar (odoo:17) platformlarda (ARM64) farklı davranabilir — pilot ekip M1 Mac + Linux ARM çalıştırıyor.

## Faz 2 — Menü & masa veri modeli (W4–W5) ✅

**Hedef:** `hashtap_pos` içinde menü ve masa modelleri tanımlı, Odoo panelinden yönetilebilir. REST endpoint'i üzerinden `customer-pwa` menü çekebiliyor.

### İş paketleri

| İş | Tahmin |
|---|---|
| `hashtap.menu.category`, `hashtap.menu.item`, `hashtap.menu.modifier` modelleri | 2 gün |
| `pos_restaurant`'ın `restaurant.table` modelini extend et (QR slug, masa tipi) | 1 gün |
| Odoo panelinde menü editörü view'ları (form + tree + kanban) | 3 gün |
| i18n alanları (TR + EN birlikte tek formda) | 2 gün |
| Public REST endpoint: `GET /hashtap/menu/<tenant_slug>/<table_slug>` | 2 gün |
| `customer-pwa` MenuPage'i bu endpoint'ten doldur | 2 gün |

### Çıktı kriterleri
- [ ] Odoo panelinde menü ekleyip TR+EN içerikleri girebiliyorum.
- [ ] Bir masaya QR URL'si üretilebiliyor (`hashtap_pos` helper ile).
- [ ] `customer-pwa` menüyü gerçek Odoo'dan çekiyor, iki dilde gösteriyor.
- [ ] Integration test: menü endpoint'i tenant izolasyonuna uyuyor (başka kiracı menüsünü dönmüyor).

### Riskler
- Odoo i18n modeli "translations table" ile çalışır; tek formda iki dili birlikte düzenletmek custom view gerektirebilir.
- Public endpoint auth'suz; rate-limit gerekli (MVP sonrası nginx seviyesi, MVP'de controller'da).

## Faz 3 — Sipariş akışı (W6–W7) ✅

**Hedef:** Müşteri PWA'dan sepet oluşturup sipariş gönderiyor; Odoo'da bir `pos.order` açılıyor; restoran panelinde görünüyor.

### İş paketleri

| İş | Tahmin |
|---|---|
| `POST /hashtap/order` — sepet → `pos.order` (draft) çevirisi | 3 gün |
| Sepet validation (fiyat sunucu tarafında yeniden hesaplanır, PWA gönderdiğine güvenmeyiz) | 1 gün |
| `pos.order` state extension: `hashtap_paid`, `hashtap_kitchen_sent` alanları | 2 gün |
| Restoran panelinde "QR siparişleri" view'ı (Odoo native) | 2 gün |
| Customer PWA sipariş durumu sayfası (polling) | 2 gün |

### Çıktı kriterleri
- [ ] PWA'dan sipariş gönderildiğinde Odoo panelinde anında görünüyor.
- [ ] Panel "hazırlanıyor / hazır" durum değişikliği PWA'ya polling ile yansıyor.
- [ ] Aynı masaya aynı anda 2 sipariş gelirse iki ayrı `pos.order` oluşuyor (çakışma yok).
- [ ] Integration test: fiyat manipülasyonu (PWA'dan yanlış fiyat gönderilirse) sunucu reddediyor.

### Riskler
- Odoo'nun `pos.order` workflow'u opinionated; bizim "paid but not in kitchen" ara durumumuz standart Odoo akışına uymuyor → custom field + custom button.
- Polling yerine WebSocket/longpoll isteği çıkabilir — faz içinde karar, MVP için polling yeter.

## Faz 4 — iyzico ödeme (W8–W9) ✅ (mock + stub)

**Hedef:** Müşteri 3DS'le ödüyor, sipariş `paid` oluyor, restoran banka hesabına para akıyor (test ortamı).

### İş paketleri

| İş | Tahmin |
|---|---|
| iyzico sandbox hesabı + subMerchant kurulumu | 1 gün |
| `hashtap_pos.payment` — 3DS başlatma endpoint'i | 2 gün |
| 3DS callback + idempotency + siparişi `paid` yap | 2 gün |
| Webhook güvenliği (HMAC doğrulaması) | 1 gün |
| Apple Pay / Google Pay desteği (iyzico üzerinden) | 3 gün |
| Hata durumları: ödeme başarısız, timeout, duplicate callback | 2 gün |

### Çıktı kriterleri
- [ ] Sandbox'ta uçtan uca ödeme akışı çalışıyor.
- [ ] Callback imzası doğrulanmadan sipariş `paid` olmuyor (testle doğrulanmış).
- [ ] Aynı callback iki kez gelirse sipariş iki kez `paid` olmuyor.
- [ ] subMerchant hesabına test parası "yatmış" görünüyor.

### Riskler
- Apple Pay domain verification ve merchant kurulumu zaman alır; iş paketi 3 günden taşabilir.
- iyzico facilitator sözleşmesi için hukuki ön-adım gerekebilir (prod için; sandbox'ta değil).

## Faz 5 — e-Arşiv (W10–W11) ✅ (mock, Foriba iskelet)

**Hedef:** Sipariş ödendiğinde otomatik fiş kesiliyor; kesilemezse sipariş mutfağa **gönderilmiyor** (fail-close).

### İş paketleri

| İş | Tahmin |
|---|---|
| Sağlayıcı seçimi (Foriba vs Uyumsoft vs Logo) + test hesabı | 1 gün |
| `efatura_adapter` modülü: sağlayıcı-bağımsız arayüz | 2 gün |
| Sipariş `paid` → fiş kesme job'u (Odoo queue_job veya cron) | 3 gün |
| Fail-close: fiş başarısızsa sipariş durumu `paid_no_receipt`, mutfak tetiklenmez, panelde alarm | 2 gün |
| Müşteriye PWA'da PDF/QR fiş gösterimi | 2 gün |

### Çıktı kriterleri
- [ ] Test ortamında ödeme → fiş kesme → PWA'da fiş görünme akışı yeşil.
- [ ] Fiş sağlayıcı kasıtlı olarak düşürüldüğünde sipariş mutfağa gitmiyor, restoran paneline alarm düşüyor.
- [ ] Fiş yeniden kesildiğinde akış normale dönüyor.

### Riskler
- GİB'in e-Arşiv test ortamı pratikte istikrarsız; lokal mock tabanlı test iskelesi kur.
- Fail-close politikası pilot müşterinin hoşuna gitmeyebilir ("ödeme aldım, niye mutfağa gitmiyor?") — müşteri eğitimi gerekli.

## Faz 6a — KDS (Kitchen Display) ✅

**Hedef:** Mutfak için tam ekran, HashTap markalı canlı sipariş paneli.
Pilot restoranda tablet/TV üzerinde çalışır. Detay: `docs/KDS.md`.

### İş paketleri (yapıldı)

| İş | Çıktı |
|---|---|
| `hashtap.order` state eksenine `preparing` ve `kitchen_fired_at/ready_at` alanları | `models/hashtap_order.py` |
| `GET /hashtap/kds` sayfası + polling endpoint'i | `controllers/kds.py` |
| 3-kolon UI (Yeni / Hazırlanıyor / Hazır), dark theme, touch buttons | `static/src/css/kds.css` |
| 3sn polling + yeni sipariş beep'i + geri al | `static/src/js/kds.js` |
| Odoo menü link'i ("HashTap → Operasyon → Mutfak Ekranı") | `views/hashtap_kds_menu.xml` |

### Çıktı kriterleri (karşılandı)
- [x] Mutfağa düşen sipariş 3sn içinde KDS'te "Yeni" kolonunda görünüyor.
- [x] "Başla / Hazır / Servis edildi" butonlarıyla durum ilerliyor, KDS kartı kolonlar arası kayıyor.
- [x] Servis edilen sipariş KDS'ten düşüyor.
- [x] Bekleme süresine göre renk uyarısı (normal / 10dk / 20dk+).

### Gelecek iyileştirmeler (pilot bağımlı)
- Çoklu istasyon (soğuk/sıcak mutfak ayrı KDS).
- Longpolling (`bus.bus`) — 50+ masa/dk yükünde.
- Restorana göre süre eşiği (res.config.settings).

## Faz 6b — Print-bridge (pilot tetiklemeli) ⏳

**Hedef:** Termal (ESC/POS) yazıcıya fiziki fiş çıkışı. Pi veya local
agent köprü.

**Ne zaman başlatılır:** Pilot restoranda termal yazıcı kullanılacağı
kesinleştiğinde. Mutfak akışı şu an KDS ile tam çalışıyor; yazıcı
operasyonel tercih meselesi.

### İş paketleri

| İş | Tahmin |
|---|---|
| Print-bridge WS protokolü: Odoo'dan print-bridge'e event emitting | 2 gün |
| Print-bridge tarafında event al → ESC/POS yazıcıya bas | 2 gün |
| "Basıldı" onayının Odoo'ya dönüşü, retry mantığı | 2 gün |
| Local queue + offline dayanıklılık | 1 gün |

### Çıktı kriterleri
- [ ] Test masasında yazıcıdan gerçek fiş çıkıyor.
- [ ] Yazıcı offline'ken sipariş kuyrukta bekliyor; online olunca basılıyor.
- [ ] İki baskı önlemi: aynı siparişin fişi iki kez basılmıyor.

### Riskler
- Pi tarafında ağ kesintisi senaryoları restoranlarda yaygın — local queue dayanıklı olmalı.
- Termal yazıcı markaları uyum farkları (Epson TM-T20, Star TSP100...). Öncelikle pilotun aldığı modele odaklan.

## Faz 7.5 — `hashtap_theme` doldurma (white-label pass 1) ✅

**Hedef:** Restoran sahibi / personeli Odoo arayüzüne bakarken "HashTap
kullanıyorum" desin; ilk vuruşu CSS ile yap, XML inheritance'ı sadece
whitelist'in izin verdiği noktalarda kullan. Detay: `docs/WHITE_LABEL.md`.

### Yapıldı
- SCSS palet ve backend overrides (navbar, buton, form, odoo.com
  link'lerini gizle).
- Login / signup / reset şifre ekranları: cream arka plan, HashTap
  logosu CSS background-image ile, tagline `::before` ile.
- Tarayıcı sekme başlığı "HashTap".
- Odoo 17 view inheritance whitelist (sadece `@id/@name/@class/@string`)
  tuzağı tecrübe edildi ve dokümante edildi (WHITE_LABEL §4.1).

### Kalan white-label işi (Faz 8/9 içinde)
- App switcher ve `ir.ui.menu` temizliği (Discuss / Website gibi
  gereksiz root menüler gizlenmeli).
- PDF şablonları (fiş / fatura) — `report.internal.layout` override.
- Sistem mail şablonları.
- 404/500 hata sayfaları.
- Help → "HashTap Hakkında".

## Faz 7 — POS adapter (Segment B) (W13–W14)

**Hedef:** Kendi ERP'mizi istemeyen müşteri için SambaPOS veya Adisyo'ya bağlı mod çalışıyor.

### İş paketleri

| İş | Tahmin |
|---|---|
| SambaPOS Graph API adapter | 4 gün |
| Adisyo REST adapter | 3 gün |
| Adapter mode'unda `hashtap_pos` hangi modülleri kapatıyor dokümante et | 1 gün |
| İki pilotta test (bir SambaPOS'lu, bir Adisyo'lu) | 3 gün |

### Çıktı kriterleri
- [ ] SambaPOS'lu test restoranında sipariş HashTap → SambaPOS'a gidiyor, mutfak fişi SambaPOS'tan çıkıyor.
- [ ] Adisyo'da aynısı yeşil.

### Riskler
- SambaPOS API erişimi için lisans/anlaşma — pazarlama tarafı hızlı yürütmeli.

## Faz 8 — Multi-tenant provisioning (W15–W16)

**Hedef:** Yeni restoran otomatik açılıyor. Subdomain, DB, varsayılan ayarlar otomatik.

### İş paketleri

| İş | Tahmin |
|---|---|
| Tenant lifecycle servisi (TS, `apps/api` içinde) | 4 gün |
| Odoo DB otomatik oluşturma + `hashtap_pos` + `hashtap_theme` modül kurulumu | 2 gün |
| DNS wildcard + nginx subdomain routing | 2 gün |
| Admin UI (iç): tenant listele, suspend, offboard | 2 gün |

### Çıktı kriterleri
- [ ] Tek bir admin komutu ile 60 dakikanın altında yeni kiracı açılıyor.
- [ ] `sirket.example.com` DNS + SSL otomatik yapılandırılıyor.
- [ ] Suspend edilen kiracıya trafik düşüyor ama veri silinmiyor.

### Riskler
- DNS/SSL otomasyonu (cert-manager / acme-dns) prod'da kurulum zorluğu çıkarabilir.

## Faz 9 — Pilot hazırlık (W17–W18)

**Hedef:** Gerçek bir restoranda pilot için her şey hazır. Eğitim materyali, destek süreci, geri bildirim kanalı.

### İş paketleri

| İş | Tahmin |
|---|---|
| Pilot restoran menüsünü sisteme gir | 2 gün |
| Ekip eğitimi (sahip + garson + mutfak) | 1 gün |
| Uptime monitoring (Prometheus / Grafana basit setup) | 3 gün |
| Destek prosedürü, telefon numarası, günlük raporlama | 2 gün |
| Canary flags: gün içinde %10 siparişle başla, genişlet | 2 gün |

### Çıktı kriterleri
- [ ] Pilot restoran sahibi "sistem hazır" diyor.
- [ ] Destek hattı canlı, ilk 72 saatte bizden biri on-call.

## Faz 10 — Pilot (W19–W22)

**Hedef:** 4 hafta canlı pilot, MVP başarı kriterleri karşılanıyor.

İş paketleri: gözlem, bug fix, müşteri eğitimi. Yeni özellik yok.

### Çıktı kriterleri
- PRODUCT.md §8 kriterleri.

## Faz 11+ (hedefler, zamanlama yok)

- Çoklu konsept / zincir desteği.
- Yemeksepeti / Getir entegrasyonu.
- Sadakat programı.
- Dinamik fiyatlama (happy hour vb).
- AI menü önerisi.

## Özet çizelgesi

| Faz | Hafta | Başlık | Durum |
|---|---|---|---|
| 0 | W0 | İskele + doküman | ✅ |
| 1 | W1–W3 | Odoo + `hashtap_pos` iskele | ✅ |
| 2 | W4–W5 | Menü & masa modeli | ✅ |
| 3 | W6–W7 | Sipariş akışı | ✅ |
| 4 | W8–W9 | iyzico (mock + stub) | ✅ |
| 5 | W10–W11 | e-Arşiv (mock + Foriba iskelet) | ✅ |
| 6a | W12 | KDS (Kitchen Display) | ✅ |
| 7.5 | W12 | `hashtap_theme` doldurma (pass 1) | ✅ |
| 6b | pilot tetikli | Print-bridge (ESC/POS) | ⏳ |
| 7 | W13–W14 | POS adapter (Segment B) | ⏳ partnership bağımlı |
| 8 | W15–W16 | Multi-tenant provisioning | ⏳ |
| 9 | W17–W18 | Pilot hazırlık | ⏳ |
| 10 | W19–W22 | Pilot | ⏳ |

Toplam tahmini yol: **~22 hafta**. Bu bir çalışan bir buçuk mühendis varsayımı; ekip büyürse sıkışır, tek başına çalışırsak %40 gevşek tutulmalı.

Anlık yapılmış / sıradaki ince liste: `docs/STATUS.md`.
