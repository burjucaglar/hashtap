# HashTap — Çok Kiracılı Mimari

Bu doküman HashTap'in birden fazla restoranı tek platformda nasıl koştuğunu tanımlar. Modele, provisioning akışına, lifecycle'a, veri izolasyonuna, yükseltme stratejisine değinir.

İlgili karar: `adr/0006-db-per-tenant.md`.

## 1. Model: DB-per-tenant

Her restoran = ayrı bir Postgres DB. Her DB = ayrı bir Odoo "database". Odoo CE bu modeli native destekler (multi-database feature). Odoo Online (SaaS.com) kendisi de aynı modelde çalışır; binlerce kiracıyı kaldırdığı kanıtlı.

### Neden bu model
- **Güçlü izolasyon:** Kiracı A'nın SQL'i B'nin verisine erişemez — schema seviyesinde değil, DB seviyesinde ayrık.
- **Odoo opinionated:** Odoo'nun multi-company feature'ı var ama bir DB içinde N şirket anlamına gelir — bu bir restoran grubunun birden fazla şubesi için uygundur, ama bir SaaS platformunun N müşterisi için uygun değildir (kod seviyesinde "leak" riskleri, performans karşılaştırmaları, yedek/upgrade riskleri birleşir).
- **KVKK / GDPR uyumu:** Kiracı "verimi sil" derse `DROP DATABASE` — basit, denetlenebilir.
- **Yedek/restore:** Kiracı-başı yedek kolay.
- **Performans kirliliği:** Bir kiracının yoğun sorgusu diğerini etkilemez (worker seviyesinde izolasyon bir üst kat).

### Alternatifleri neden reddettik
- **Tek DB, tenant_id sütunu:** Odoo core'una invaziv değişiklik gerektirir (schema'daki her tabloda). Core'a dokunmama kuralımızla (ADR-0005) çelişir.
- **Schema-per-tenant (Postgres):** Orta yol, ama Odoo schema geçişi desteklemiyor; yine core değişikliği.

### Dezavantajlar (kabul ettiğimiz)
- 1000+ kiracıda operasyonel karmaşıklık (yedek, upgrade orkestrasyonu).
- "Global query" yazmak (tüm kiracıların toplu raporu) kolay değil — BI/DWH ayrı yazılır.
- Worker pool bellek kullanımı daha yüksek.

MVP'de 10–50 kiracı hedefliyoruz. Bu ölçekte DB-per-tenant'ın dezavantajları marjinal.

## 2. Topoloji

```
                   ┌────────────────┐
                   │  DNS wildcard  │  *.example.com → load balancer
                   │  + ACME TLS    │
                   └────────┬───────┘
                            │
                   ┌────────▼───────┐
                   │  Nginx / Caddy │
                   │  (TLS sonlandır)
                   │  (subdomain → gateway veya odoo)
                   └────────┬───────┘
                            │
           ┌────────────────┼────────────────┐
           ▼                                 ▼
   ┌───────────────┐              ┌───────────────────────┐
   │  Gateway API  │              │  Odoo router          │
   │  (TS/Fastify) │              │  (Odoo'nun nginx.conf)│
   │  r.example.com │              │  <tenant>.example.com  │
   └───────┬───────┘              └────────────┬──────────┘
           │                                   │
           │ tenant registry                   │ Odoo native routing
           │ (gateway'in DB'si)                │ (db_filter)
           ▼                                   ▼
  ┌────────────────┐                  ┌──────────────────┐
  │ gateway_db     │                  │  Odoo workers    │
  │ (küçük Postgres│                  │  (container pool)│
  │  — tenant list)│                  └─────────┬────────┘
  └────────────────┘                            │
                                                │ DB-bazlı
                                                ▼
                                    ┌─────────────────────┐
                                    │ Postgres cluster    │
                                    │  tenant_abc (DB)    │
                                    │  tenant_def (DB)    │
                                    │  tenant_xyz (DB)    │
                                    └─────────────────────┘
```

### Subdomain ayrımı
- `sirket.example.com` → restoran paneli (Odoo web client, white-label).
- `r.example.com/<tenant_slug>/<table_slug>` → müşteri PWA (tek domain, path'te tenant).

Müşteri PWA'nın tek domain'de toplanmasının sebebi: cache, service worker, ve "bir restoran bir subdomain kapatır" riskini azaltma.

### Odoo worker'ların kiracıya atanması
- **MVP:** Odoo worker pool'u var, Odoo `db_filter` ayarı gelen HTTP subdomain'ine bakıp doğru DB'ye yönlendiriyor. Tek worker pool → N DB.
- **Ölçekleme:** Kiracı başına dedicated worker gerekebilir (komşu gürültüsünden izole etmek için). O zaman kiracıyı "large" diye işaretleyip ayrı pool'a al. Faz 8+ konusu.

## 3. Tenant lifecycle

### 3.1 Onboarding (yeni kiracı yaratma)

Yeni bir restoran kabul edildiğinde gateway'e `POST /admin/tenants` gelir:

```json
{
  "slug": "terakki",
  "display_name": "Terakki Karaburun",
  "admin_email": "owner@terakki.com",
  "language": "tr",
  "timezone": "Europe/Istanbul",
  "iyzico": {
    "sub_merchant_key": "xxx",
    "environment": "sandbox"
  },
  "plan": "mvp"
}
```

Gateway'in tenant-service'i sırayla:

1. **Slug doğrulama.** Rezerve kelimeler (`admin`, `r`, `api`, `www`, `mail`) yasak; uzunluk 3–32; karakter `[a-z0-9-]+`.
2. **Tenant registry'ye taslak kayıt.** Durum `provisioning`.
3. **Postgres DB oluştur.** `CREATE DATABASE tenant_<slug>` — kullanıcı ayrı olabilir (ileri aşama), MVP'de ortak superuser.
4. **Odoo DB init.** HTTP `POST /web/database/create` — master password ile. Parametreler: db_name, admin_email, admin_password (rastgele), lang, country=TR.
5. **Gerekli modülleri yükle.** `hashtap_pos`, `hashtap_theme`, `queue_job`, ilgili Odoo modülleri. CLI: `odoo -d tenant_<slug> -i hashtap_pos -i hashtap_theme --stop-after-init`.
6. **Başlangıç verisi.** Ülke=TR, para=TRY, dil=TR+EN, default allergen listesi, default KDV oranları.
7. **iyzico subMerchant** (iyzico sandbox'ta veya prod'da) — restoran adına, gateway iyzico'ya CRUD eder.
8. **DNS kaydı.** `sirket.example.com` CNAME → load balancer. Wildcard DNS varsa bu adım no-op.
9. **TLS sertifikası.** ACME cert-manager wildcard (`*.example.com`) varsa no-op; yoksa per-host SAN.
10. **Welcome e-posta.** Restoran sahibine giriş URL'i + geçici şifre.
11. **Tenant registry.** Durum `active`.

Bu adımların her biri idempotent. Bir adım hata verirse gateway `provisioning_failed` durumuna düşer, admin müdahalesi için ekrana gelir.

**Süre hedefi:** 60 dakikanın altı. Teorik olarak <5dk. Pratikte TLS ve iyzico kaynaklı gecikmeler.

### 3.2 Suspend (askıya alma)

Ödeme yapılmadı, şüpheli aktivite, kiracı talep etti:

- Gateway trafiği 403 ile keser — Odoo DB silinmez, veri korunur.
- Tenant durumu `suspended`.
- 30 gün sonra otomatik offboard (veya manuel karar).

### 3.3 Reactivate

- Tenant durumu `active`'e çekilir, trafik açılır.
- DB ve Odoo instance'ı olduğu gibi kaldığı için no-op.

### 3.4 Offboard (kalıcı silme)

- Kiracı talep etti veya suspend süresi doldu.
- KVKK için **veri ihracı** önce sunulur: Odoo'nun standart backup API'si (`/web/database/backup`) ile SQL dump + filestore.
- Onay → `DROP DATABASE tenant_<slug>`.
- Filestore (attachment'lar) temizlenir.
- Tenant registry'de `deleted` + audit log satırı.
- DNS/TLS temizlenir.

## 4. Tenant registry şeması

Gateway'in kendi küçük DB'si. Odoo DB'lerinden tamamen ayrı.

```sql
CREATE TABLE tenants (
  id UUID PRIMARY KEY,
  slug VARCHAR(32) UNIQUE NOT NULL,
  display_name VARCHAR(200) NOT NULL,
  status VARCHAR(20) NOT NULL,      -- provisioning/active/suspended/deleted
  odoo_db_name VARCHAR(64) NOT NULL,
  odoo_host VARCHAR(128) NOT NULL,  -- worker pool endpoint
  plan VARCHAR(20),
  timezone VARCHAR(64),
  created_at TIMESTAMPTZ,
  activated_at TIMESTAMPTZ,
  suspended_at TIMESTAMPTZ,
  deleted_at TIMESTAMPTZ
);

CREATE TABLE tenant_events (
  id SERIAL PRIMARY KEY,
  tenant_id UUID REFERENCES tenants(id),
  event_type VARCHAR(40),           -- provisioning_started, activated, suspended, ...
  payload JSONB,
  created_at TIMESTAMPTZ
);

CREATE TABLE tenant_admin_tokens (
  tenant_id UUID REFERENCES tenants(id),
  token_hash VARCHAR(64) PRIMARY KEY,
  scopes TEXT[],
  created_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ
);
```

Tenant registry'nin kendisi **tek DB'li** — kiracı-izolasyonuna tabi değil. Sadece HashTap ekibinin erişimi var.

## 5. Veri izolasyonunun doğrulanması

### 5.1 Test senaryoları (her release'te)
- Kiracı A'nın admin'i kiracı B'nin herhangi bir endpoint'ine istek atar → 403/404.
- Kiracı A'nın PWA'sı `Host: b.example.com` header spoof'u yaparsa gateway reddeder (çünkü slug path'ten geliyor ve registry'de tenant-host çifti doğrulanır).
- SQL injection testi: kiracı A'nın menü endpoint'ine `' OR 1=1 --` ile yönelir → ORM parametrize ettiği için no-op, yine de integration test'le doğrulanır.
- `pg_class` / system catalog erişimi: Odoo user role'ü PUBLIC schema dışında yetkisiz.

### 5.2 Periyodik denetim
- Her ay: rastgele 5 kiracı seçilip veri örnekleri eşleşme kontrolü yapılır (audit query).
- Odoo log'larında "AccessError" sayısı grafikte; ani yükseliş saldırı işareti.

## 6. Yedekleme

- **Postgres:** Günlük full + WAL continuous archive. pgBackRest veya barman. S3 uyumlu bucket'a.
- **Filestore:** Günlük rsync S3'e.
- **Retention:** 30 gün günlük, 12 ay haftalık, 7 yıl aylık (e-Arşiv gereği).
- **Restore testi:** Ayda bir rastgele kiracının bir önceki günkü yedeği staging'e restore edilir, sağlık kontrolü.

## 7. Sürüm yükseltme stratejisi

Odoo major (17 → 18) upgrade'i ciddi iştir.

### 7.1 Kiracılara kademeli
1. **Dev:** Yeni sürümle `hashtap_pos` derlenir, testler koşar.
2. **Staging:** Bir demo kiracı dump'ı restore edilir, upgrade edilir, E2E koşar.
3. **Pilot kiracı (varsa opt-in):** İlk gerçek kiracı sessiz gecelerde upgrade, 2 hafta gözlem.
4. **Batch:** Her gece X kiracı otomatik upgrade (staged migration).
5. **Tüm kiracılar:** Yeşil olunca.

### 7.2 Upgrade per kiracı
- Kiracıyı bakım moduna al (gateway 503'e düşürür).
- Yedek al.
- `odoo -d tenant_slug -u all --stop-after-init` koş.
- Sağlık kontrolü (smoke test): giriş olabiliyor mu, bir menü fetch ediyor mu.
- Bakım modundan çıkar.

### 7.3 Geri alma
- Yedekten restore + eski container image ile başlat. Max 10dk.

## 8. Ölçeklenme sınırları ve sonraki adımlar

- **~50 kiracı**: Tek worker pool, tek Postgres instance yeterli.
- **~200 kiracı**: Worker pool'u kiracı tiyerine göre bölmek (Small/Medium/Large). Postgres hâlâ tek cluster.
- **~1000 kiracı**: Coğrafi (İstanbul/Ege/Akdeniz) shard'lar; her shard'da ayrı Postgres + ayrı Odoo pool. Gateway registry hangi shard'ı tutuyor.
- **~5000 kiracı**: Büyük ihtimal Odoo'dan çıkıp farklı mimari. Bu dokümanın kapsamının dışı.

## 9. Açık riskler

- **Bir kiracının kötü niyetli Python eklentisi yüklemesi.** MVP'de kiracı kendi modül yükleyemiyor; sadece HashTap ekibi yükler. Bu feature gelirse sandbox gerekir.
- **Master password sızıntısı.** Odoo'nun master password'ü tüm DB'lere erişir. Güvenli saklanır (vault), rotate edilir.
- **Çok büyük kiracı.** Bir restoran günde 50.000 sipariş verirse DB'si devasa olur; shard içi ayrılması gerekir. Şu an hedef segmentte bu ölçek yok.
