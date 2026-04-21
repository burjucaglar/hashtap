# HashTap — White-Label Stratejisi

Bu doküman Odoo'nun markasının HashTap kullanıcılarına görünmemesi için uygulanan değişikliklerin tam listesini tanımlar. Kod değil, davranış ve override listesi. Uygulama `hashtap_theme` modülünde.

İlgili karar: `adr/0007-white-label-strategy.md`.

## 1. Hedef

Son kullanıcı (restoran sahibi, personeli) "HashTap POS kullanıyorum" der. "Odoo" kelimesi hiçbir ekranda, hiçbir e-postada, hiçbir hata mesajında görünmez. Kaynak dosyalarındaki copyright header'lar yerinde kalır (LGPL gerektiriyor) — geliştirici olmayan kimse onları görmez.

## 2. Hukuki çerçeve

- **Odoo Community LGPLv3.** Markanın kaldırılmasına izin verir (LGPL'de "branding lock" yoktur — Odoo Enterprise lisansında vardır, onu kullanmıyoruz).
- **Copyright header'lar** kaynak dosyalarda kalır. Bunu temizleyemeyiz.
- **"Powered by Odoo"** default footer'ı kaldırabiliriz; LGPL gerektirmiyor.
- **Odoo markası/logoları** tescil altındadır; modifiye edilmemiş dağıtımda kalır, bizim dağıtımımız modifiye edildiği için kullanmayabiliriz (kullanmayacağız).

## 3. Override listesi — kapsamlı

### 3.1 Login ekranı (`/web/login`)
- Logo: HashTap logosu.
- Arka plan: HashTap kurumsal görsel (koyu mavi + turuncu aksan).
- Başlık: "HashTap POS'a Giriş".
- "Powered by Odoo" footer: kaldır.
- "Sign in with Google" gibi SSO butonlarını ayarlardan toggle — MVP'de kapalı.

### 3.2 Veritabanı seçici (`/web/database/*`)
- Multi-DB seçici normalde burada görünür. Biz DB-per-tenant'la subdomain'den doğru DB'ye route ediyoruz; bu sayfa tamamen **gizli** olmalı (nginx'te engellenir + Odoo config `list_db=False`).
- Manager sayfası (`/web/database/manager`): master password ile erişilir; prod'da nginx'te IP whitelist. Müşterinin görmesine gerek yok.

### 3.3 App switcher (üst sol menü)
- Normalde "Discuss, CRM, Sales, Accounting..." ikonları.
- HashTap için: "HashTap POS", "Menü", "Stok", "Muhasebe", "Raporlar", "Ayarlar". Bu isimler Odoo modüllerinin kendisi değil; modüllerin görünen adları `ir.module.module`'de override edilir.
- HashTap'in sahibi olmadığı modüller (Discuss, Website vb) gizlenir — `ir.ui.menu`'den root'lar kaldırılır.

### 3.4 Üst bar (navbar)
- Odoo logosu yerine HashTap logosu.
- "Odoo Online", "Upgrade to Enterprise" gibi promosyon bağlantıları — CE'de zaten sınırlı, yine de `@api.model` override ile silinir.
- Kullanıcı menüsü: "Profilim, Oturumu Kapat" — "My Odoo.com Account" bağlantısı gizlenir.

### 3.5 E-posta şablonları
- Odoo'nun "Please update your browser..." gibi sistem mail'leri HashTap branded şablonlara override edilir.
- Varsayılan gönderen: `no-reply@example.com`.
- Footer: HashTap adresi, telefon, destek maili.

### 3.6 Hata sayfaları
- 404, 500 ekranları kendi tasarımımız. Odoo stack trace son kullanıcıya gösterilmez — `debug=False` zorunlu.

### 3.7 PDF şablonları
- Fatura, fiş, rapor PDF'lerinin header/footer'ı HashTap branded.
- `report.internal.layout` template'i override edilir.

### 3.8 Windows title / tab
- Tarayıcı sekmesi başlığı: "HashTap POS — [current view]" (şu an "Odoo — [view]" gibi).
- Favicon HashTap.

### 3.9 About page
- `Help > About Odoo` linki kaldırılır. Yerine "HashTap Hakkında" — sürüm, destek iletişim.

### 3.10 Loading splash
- Odoo'nun mor "loading" spinner'ı HashTap paletine alınır.

### 3.11 Debug mode
- Odoo developer mode (`?debug=1`) kullanıcıya görünür bir şey eklemiyor — teknik ekip kullanır. Değiştirmiyoruz.

### 3.12 Error dialogs (Odoo web client)
- `UserError`, `ValidationError` modal'larının "Odoo" başlığı → "HashTap" başlığı.

### 3.13 Mobil Odoo uygulaması
- Odoo resmi mobil uygulaması App Store/Play Store'da duruyor ve oradan login olunabiliyor. Biz "bu mobil uygulamayı kullanmayın" diyoruz; müşteri eğitiminde açık.
- Engelleyemeyiz (genel IP'den bağlanıyor). Bir uyarı: Odoo mobil login başarılı olsa bile görece sıkıcı bir arayüz sunar, restoran personeli kendiliğinden PWA'yı tercih edecek.

## 4. Modüldeki davranışın haritası

`hashtap_theme` içindeki dosyalar ve ne override ettikleri (güncel —
2026-04-21 itibarıyla):

```
hashtap_theme/
├── __manifest__.py                 # web.assets_backend + web.assets_frontend bundle
├── views/
│   ├── webclient_templates.xml     # <title> → "HashTap"
│   └── login_templates.xml         # (bilinçli boş — aşağıdaki 4.1'e bakın)
├── static/
│   └── src/
│       ├── scss/
│       │   ├── _variables.scss     # HashTap palet: $hashtap-accent=#ff7a00, ink, cream bg
│       │   ├── overrides.scss      # backend: navbar, buton, form, odoo.com link gizle
│       │   └── login.scss          # /web/login, /web/signup, /web/reset_password
│       └── img/
│           └── logo.svg            # login form background + menü ikonu
```

### 4.1 Odoo 17 view inheritance whitelist — önemli kısıt

Odoo 17 CE'de `<xpath expr="...">` ile inherit edilen view'larda xpath
selector'ı sadece `@id`, `@name`, `@class`, `@string` ve `position`
özniteliklerini kabul eder. Bu yüzden:

- **Favicon** (`<link rel=... href=...>`): `@rel`/`@href` whitelist'te yok.
  Xpath ile değiştirilemez. Çözüm: **şirket logosunu HashTap logosu yap**
  (Ayarlar → Şirketler) — Odoo favicon'u otomatik şirket logosundan türetir.
- **Login logosu** (`<img alt="Logo">`): `@alt` whitelist'te yok. Çözüm:
  login template'i inherit etmek yerine **CSS** ile logoyu enjekte et —
  `.oe_login_form { background-image: url(.../logo.svg) }` ile
  `login.scss`'de yapılıyor. Böylece XML inheritance hiç devreye girmiyor.
- **"Powered by Odoo" footer link'leri**: CSS ile `display: none`
  (`a[href*="odoo.com"]`) — whitelist kısıtı CSS'e uygulanmıyor, basit.

Özetle: **mümkün olduğunca CSS ile markala.** XML inheritance'ı sadece
whitelist'in izin verdiği noktalarda (title, menu gizleme) kullan.

## 5. Manuel kontrol listesi (test için)

Her major sürüm yükseltmesinden sonra aşağıdaki liste manuel koşulur. Otomasyon faz 3+ işi (Playwright snapshot test).

**Durum 2026-04-21:** `[x]` faz 7.5'te yapıldı, `[ ]` ileri fazlarda.

- [x] `/web/login` açıldı → HashTap logosu (CSS background) ve tagline, "Odoo" yok.
- [x] Tarayıcı sekme başlığı "HashTap" ile başlıyor.
- [x] Backend navbar HashTap mor + turuncu vurgu.
- [x] "Powered by Odoo" footer link'leri gizli.
- [ ] App switcher'da yalnızca HashTap modülleri (faz 8'de `ir.ui.menu` temizliği).
- [ ] PDF fiş HashTap branded (faz 9'da `report.internal.layout` override).
- [ ] Şifremi unuttum / sistem e-postaları HashTap branded (faz 8+).
- [ ] 404/500 sayfası HashTap branded (faz 9'da).
- [ ] Help menüsü → "HashTap Hakkında" (faz 8'de).
- [ ] Favicon HashTap (şirket logosu seed edilince otomatik).
- [ ] HTML kaynağı: `<meta generator content="Odoo">` etiketi yok.
- [ ] Hatalı URL → Odoo debug sayfasına değil, bizim 500'e düşüyor (`debug=False` + custom error handler).

## 6. Saklanmasında ısrar etmediğimiz yerler

- **Kaynak kodundaki copyright header'ları** — LGPL, kalır. Kimse görmez.
- **Odoo mobil uygulamasından login** — engellenemez. Eğitimde yönlendir.
- **İleri kullanıcı `?debug=1` ekleyip developer mode'u açarsa** görebilir. Son kullanıcı için endişe değil; developer mode'u kapalı tut.

## 7. Sürdürme

- Odoo major version upgrade'de (17 → 18) bu dokümanın §5'indeki kontrol listesi yeniden koşulur.
- Yeni modül eklendiğinde (örn faz 7'de OCA bir modül) o modülün brand'larını da temizle.
- Kullanıcı geri bildirimde "Odoo gördüm" derse — issue aç, yamala, kontrol listesine ekle.
