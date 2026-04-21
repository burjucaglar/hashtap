# HashTap — Durum Panosu

Bu doküman projede fiziksel olarak ne yapıldığı / neyin geride kaldığı
açısından tek referans noktasıdır. Diğer dokümanlar (ROADMAP, DATA_MODEL,
MODULE_DESIGN...) tasarım niyetini ve hedefini anlatır; **bu sayfa
gerçeği anlatır**. Yeni iş biter bitmez bu sayfa güncellenir.

Son güncelleme: 2026-04-21.

## 1. Faz durumu — özet

| Faz | Başlık | Durum | Not |
|---|---|---|---|
| 0 | İskele + doküman | ✅ | `docs/` doldu, monorepo ayağa kalktı. |
| 1 | Odoo temeli + `hashtap_pos` iskelesi | ✅ | `infra/odoo/docker-compose.yml`, temel model + view, menu root. |
| 2 | Menü & masa veri modeli | ✅ | `hashtap.menu.category / menu.item / modifier.group / modifier`, QR slug'lı `restaurant.table`, public menu endpoint. |
| 3 | Sipariş akışı | ✅ | `hashtap.order` + `hashtap.order.line`, `POST /hashtap/order`, durum polling. |
| 4 | iyzico ödeme (sandbox) | ✅ | Payment adapter pattern, `mock` + `iyzico` adaptörleri, 3DS callback + idempotency. |
| 5 | e-Arşiv (mock + Foriba iskeleti) | ✅ | earsiv adapter pattern, `mock` + `foriba` (iskelet), **fail-close** uygulandı. |
| **6a** | **KDS (Kitchen Display)** | ✅ | `/hashtap/kds` tam ekran, 3 kolon, polling, beep. |
| 6b | Print-bridge (Pi + ESC/POS) | ⏳ | Pilot restoran seçildiğinde başlar. |
| **7.5** | **hashtap_theme doldur (white-label pass)** | ✅ | Login CSS-branded, backend navbar + buton overrides, "Powered by Odoo" gizli. |
| 7 | POS adapter (SambaPOS / Adisyo) | ⏳ | Segment B — partnership ve pilot müşteri gerekli. |
| 8 | Multi-tenant provisioning | ⏳ | Tenant lifecycle, DB per tenant, DNS + SSL otomasyonu. |
| 9 | Pilot hazırlık | ⏳ | Pilot restoran menü yüklemesi, eğitim, uptime monitoring, destek süreci. |
| 10 | Pilot (4 hafta canlı) | ⏳ | Canary + gözlem. |

Notlar:

- **Faz 6a ve 7.5 ROADMAP.md §6/§7 içindeki bölümlere karşılık gelir**; 6a,
  "Alternatif: Odoo'nun `pos_restaurant` KDS'sini white-label et" maddesinin
  yerine custom HashTap KDS'i seçildiği için yeniden kapsamlandı. 7.5
  roadmap'teki "hashtap_theme" iş paketinin (faz 1'de iskelet bırakılmıştı)
  doldurulmasıdır.
- **Faz 4 (iyzico)** prod 3DS için iyzico master merchant sözleşmesine
  bağlı. Mock adapter ile uçtan uca akış çalışıyor; gerçek 3DS sandbox
  testi devam ediyor.

## 2. Kodda neler var

### 2.1 `odoo-addons/hashtap_pos/` — ana iş modülü

- **Modeller:** `hashtap.order`, `hashtap.order.line`,
  `hashtap.menu.category/item`, `hashtap.modifier.group/modifier`,
  `hashtap.table` (`restaurant.table` extend), `hashtap.payment.provider`,
  `hashtap.payment.transaction`, `hashtap.earsiv.provider`,
  `hashtap.earsiv.receipt`.
- **Controllerlar:**
  - `controllers/menu.py` — `GET /hashtap/menu/<table_slug>`
  - `controllers/order.py` — `POST /hashtap/order`, sipariş sorgulama
  - `controllers/payment.py` — init + callback
  - `controllers/kds.py` — `/hashtap/kds` + polling
- **Adaptörler:**
  - `adapters/` (payment): `base.py`, `mock.py`, `iyzico.py`, `registry.py`
  - `adapters/earsiv/`: `base.py`, `mock.py`, `foriba.py`, `registry.py`
- **Orthogonal state axes** (DATA_MODEL.md §2.7'de tek eksenli taslaktan
  sapma — gerçek uygulama):
  - `state` — sipariş yaşam döngüsü: `placed / paid / kitchen_sent /
    preparing / ready / served / cancelled`.
  - `payment_state` — ödeme: `unpaid / pending / paid / failed / refunded`.
  - `earsiv_state` — fiş: `not_required / pending / issued / failed`.
- **Fail-close:** `is_earsiv_blocked` computed alanı; True ise mutfak
  aksiyonları `ValidationError` atar.

### 2.2 `odoo-addons/hashtap_theme/` — white-label

- Sadece CSS + minimal XML (Odoo 17 inheritance whitelist kısıtı nedeniyle).
- SCSS bundle'lar: backend (`assets_backend`) + login/public
  (`assets_frontend`).
- Detay: `docs/WHITE_LABEL.md` §4.

### 2.3 `apps/customer-pwa/` + `apps/gateway/`

Faz 0 iskelet hali. Odoo controllerları doğrudan PWA ile konuşabiliyor
(gateway opsiyonel; şu anda bypass).

### 2.4 `infra/odoo/`

- `docker-compose.yml` (Odoo + Postgres + Redis + Adminer + Mailpit).
- `Dockerfile`: `odoo:17` + `iyzipay` pip paketi.

## 3. Bilinen açıklar (tutulan borç)

### Bilinçli geciktirilen
- Gerçek iyzico 3DS sandbox testleri (master merchant onayı gerekli).
- Foriba gerçek sandbox entegrasyonu (sözleşme yapılmadı; adapter iskeleti
  hazır).
- KDS longpolling / bus.bus geçişi (pilot yükü görülene kadar gereksiz).
- Çoklu istasyon KDS (soğuk / sıcak mutfak).
- PDF fiş / mail şablonu branding (faz 9).
- `pos.order` köprüsü: ödeme sonrası `hashtap.order` → `pos.order` yazımı
  opsiyonel; muhasebe için şart, pilot restoran ihtiyaç duyarsa
  tetiklenecek.

### Pilot öncesi yapılması gereken
- Faz 6b (Pi print-bridge) — mutfakta termal yazıcı kullanacak restoranlar
  için.
- Faz 8 — tenant lifecycle (tek komutla yeni kiracı). Şu an manuel DB +
  module install.
- Faz 9 — pilot hazırlık checklistleri.

## 4. Son büyük değişiklikler (değişiklik günlüğü)

| Tarih | Değişiklik | PR/commit notu |
|---|---|---|
| 2026-04-21 | KDS bug fix: `modifier.mapped("name")` → `name_tr` | `hashtap_pos/controllers/kds.py:40` |
| 2026-04-21 | Faz 6a KDS: controller + QWeb + CSS + JS | `controllers/kds.py`, `views/hashtap_kds_*`, `static/src/{css,js}/kds.*` |
| 2026-04-21 | Faz 7.5: `hashtap_theme` SCSS doldurma, login CSS branding | `hashtap_theme/static/src/scss/{_variables, overrides, login}.scss` |
| 2026-04-20 | Faz 5: e-Arşiv adapter + fail-close | `adapters/earsiv/*`, `is_earsiv_blocked` |
| 2026-04-19 | Faz 5 deploy fix: `attrs=` → `invisible=` (Odoo 17 API) | `views/hashtap_earsiv_views.xml` |
| 2026-04-19 | iyzico stub URL bug fix: `?stub=1` → `&stub=1` | `adapters/iyzico.py` |

## 5. Bu sayfayı nasıl güncelleriz

- Bir faz bittiğinde §1 tablosunda `⏳ → ✅`.
- Yeni ara-faz eklenirse (6a / 7.5 gibi) tabloya satır eklenir, ROADMAP.md
  referanslanır.
- Yeni modül / controller / büyük model eklendiğinde §2'ye eklenir.
- Büyük bug fix veya kritik deploy zorluğu §4'e eklenir — "şu tuzağa düştük"
  bilgisi bir sonraki fazlarda hatırlatıcı olur.
