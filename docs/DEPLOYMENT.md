# Prod Deployment

Bu doküman HashTap'in prod altyapısının hedef topolojisini ve deploy pratiklerini anlatır. MVP pilot için minimum kurulum ve ölçeklendirme yolunu ayrı başlıklar olarak tutar.

## 1. Hosting tercihi

### 1.1 Bulut sağlayıcısı
**MVP için Hetzner Cloud.** Gerekçe:
- Fiyat/performans oranı Avrupa'da iyi.
- İstanbul DC'si yok ama Almanya/Finlandiya DC'leri KVKK perspektifinden "Avrupa içi" — uyum sağlanır (Türkiye'ye taşıma gerekirse Telekom bulut geçişi ileride).
- Docker/K8s'e dostane.

**Alternatifler:**
- Türk Telekom Bulut: KVKK için kesin garanti ama fiyat ve UX Hetzner kadar olgun değil.
- AWS / GCP: Güçlü ama maliyet MVP için overkill.

### 1.2 Veri konumu (KVKK)
- MVP için Almanya (Hetzner FSN1) kabul edilebilir — KVKK yurt dışı aktarımı için açık rıza + sözleşmesel güvence yazılır.
- Pilot sonrası (büyüyünce) Türkiye DC'si geçişi değerlendirilir.

## 2. Topoloji

### 2.1 MVP (pilot) — tek-bölge, tek-cluster

```
                  Internet
                     │
              ┌──────▼──────┐
              │  Cloudflare │  (DNS + DDoS + CDN cache)
              └──────┬──────┘
                     │
              ┌──────▼──────┐
              │  Load bal.  │  Hetzner LB
              │  (TLS)      │
              └──────┬──────┘
                     │
           ┌─────────┼──────────────┐
           ▼         ▼              ▼
      gateway    gateway         odoo worker
      (1 node)   (1 node)        (2 nodes, pool)
                                    │
                                    ▼
                              Postgres primary
                              (1 instance, DB-per-tenant)
                                    │
                                    ▼
                              Postgres replica (read-only + backup source)
```

- **Gateway:** 2 instance, arka arkaya load balance.
- **Odoo worker pool:** 2 instance; her biri aynı DB havuzunu görür, DB router subdomain'e göre seçer.
- **Postgres:** Primary + replica (streaming replication). Replica sadece backup kaynağı ve acil failover için.
- **Redis:** 1 instance (queue_job backend + rate limit + session cache).
- **Nesne depolama:** Hetzner S3-uyumlu bucket (menü fotoğrafı, fiş PDF, yedek).

### 2.2 Ölçekleme yolu

- **50 → 200 kiracı:** Odoo worker pool'unu 4-6'ya çıkar. Postgres'i daha büyük instance'a (vertical scaling).
- **200 → 500:** Postgres'i primary + 2 replica. Gateway instance sayısı 4+. Odoo worker'ları kiracı tiyerine göre böl.
- **500+:** Coğrafi shard. İstanbul bölgesi ve Ege bölgesi ayrı Postgres cluster'larında.

## 3. Orkestrasyon

**MVP: Docker Compose + systemd.** Gerçek K8s overkill.

`/opt/hashtap/` altında:
- `docker-compose.prod.yml` — servis tanımları.
- `.env.prod` — secret'lar (root 600, vault'tan senkron).
- systemd unit'i `hashtap.service` — compose'u yönetir.

**Ölçek geldiğinde (>100 kiracı):** Kubernetes'e geç. K3s/k8s lite → managed k8s (Hetzner / AWS EKS). Geçiş 1-2 ay iş, o zamana kadar compose yeterli.

## 4. Servisler

### 4.1 Gateway container
- Image: `hashtap/gateway:<git-sha>`.
- Port: 3000 (internal).
- Healthcheck: `GET /health`.
- Env: `DATABASE_URL`, `REDIS_URL`, `IYZICO_*`, `ODOO_INTERNAL_URL`, `JWT_SECRET`.

### 4.2 Odoo container
- Image: `hashtap/odoo:17-<git-sha>` — resmi `odoo:17` imajı üzerine `odoo-addons/` mount.
- Port: 8069 (longpoll 8072).
- Env: `HOST`, `PORT`, `USER`, `PASSWORD`, `ADMIN_PASSWD`, `ADDONS_PATH`.
- Volume: `/var/lib/odoo` (filestore).

### 4.3 Postgres
- Yönetilen olursa en iyisi (Hetzner managed PG gelirse veya Aiven). Self-hosted başlangıçta kabul.
- Tuning: `shared_buffers=2GB`, `work_mem=32MB`, `max_connections=200`.

### 4.4 Redis
- `maxmemory 1gb`, `maxmemory-policy allkeys-lru`.
- queue_job / rate limit için persistence gerekli: AOF on.

### 4.5 Nginx / Caddy
- TLS sonlandırıcı + subdomain router.
- Caddy tercihli: otomatik ACME TLS, basit config.
- `*.example.com` → `sirket.example.com` için gateway; `r.example.com` için gateway; admin tarafı IP whitelist.

## 5. TLS ve sertifika

- Wildcard: `*.example.com` — Let's Encrypt DNS-01 challenge (Cloudflare API ile).
- Yenileme: cert-manager / Caddy otomatik, 60 günde bir.
- Fallback: SAN sertifikası per-tenant (wildcard limiti 100 SAN; MVP'de gereksiz).

## 6. DNS

- `example.com` — marketing sitesi (statik, CDN).
- `*.example.com` — wildcard, LB IP'sine.
- `r.example.com` — LB IP'sine (gateway).
- `admin.example.com` — LB IP'sine ama nginx seviyesinde IP whitelist.
- `api.example.com` — internal/dev için, prod'da kapalı.

MX kayıtları: gelen e-posta için (`support@example.com`).

## 7. Secret yönetimi

- **MVP:** `.env.prod` dosyası sunucuda, 600 izinli. Dosya `git-crypt` veya benzeri ile şifreli repoya.
- **İleri:** HashiCorp Vault veya AWS Secrets Manager. Rotasyon + audit.

Secret'lar:
- iyzico API key/secret (master HashTap merchant).
- iyzico per-tenant subMerchantKey (Odoo'nun `ir.config_parameter` — encrypted at rest).
- Postgres admin şifresi.
- Odoo master password.
- e-Arşiv sağlayıcı API key.
- HashTap JWT secret.
- SMTP kimliği.

## 8. CI/CD

### 8.1 CI (GitHub Actions)
- PR'da: lint, typecheck, Odoo modül testleri, gateway unit, PWA unit.
- Main'e merge: Docker image build + registry push.

### 8.2 CD
- **Staging:** Auto-deploy main'den. Her merge canlı.
- **Prod:** Manuel trigger (GitHub Actions button). Blue-green.

### 8.3 Deploy akışı
1. CI yeşil → image registry'ye push.
2. Staging'e auto-deploy → smoke test.
3. Prod deploy onayı (insan) → deploy script.
4. Script:
   - Yeni image ile "blue" stack ayağa kaldır.
   - Smoke healthcheck.
   - LB'yi blue'ya yönlendir.
   - "Green" (eski) stack'i 10 dakika tut (rollback için), sonra kapat.

### 8.4 Odoo modül migration
- Yeni sürümde DB schema değişikliği varsa:
  - Pilot kiracıda önce.
  - Her kiracı için `odoo -d <tenant_db> -u hashtap_pos --stop-after-init` (bakım penceresinde).
  - Bakım penceresi: Türkiye saati sabah 04:00–06:00 (restoranlar kapalı).
- **Otomasyon:** `scripts/upgrade_tenants.sh` her gece max 10 kiracı günceller (rolling).

## 9. Monitoring

### 9.1 Uptime
- UptimeRobot veya BetterStack: her 1dk `GET /health` ping → e-posta/Slack alarm.

### 9.2 Log
- Loki + Grafana, veya basitçe `journalctl` + log rotation.
- Level: INFO prod'da; DEBUG açılabilir kısa süre.
- Kişisel veri log'lanmaz (kart, TCKN, telefon hash'i).

### 9.3 Metrik
- Prometheus + Grafana.
- Temel metrikler:
  - `http_request_duration_seconds` (gateway).
  - `pos_order_state{state=}` (Odoo üzerinden — custom exporter).
  - `iyzico_callback_latency_seconds`.
  - `earsiv_receipt_result{result=}` (başarılı/başarısız).
  - `tenant_count`, `tenant_active`.

### 9.4 Alarm
- PagerDuty yerine başlangıçta basitçe Slack webhook.
- Kritik alarmlar:
  - Gateway hata oranı > %1 (5 dk).
  - Odoo down (ping fail 3 dk).
  - Postgres replication lag > 30s.
  - e-Arşiv fail rate > %10 (son 30 dk).
  - Disk doluluk > %80.

## 10. Yedekleme

- Postgres: pgBackRest, S3'e.
  - Full: haftalık pazar 03:00.
  - Incremental: günlük 03:00.
  - WAL: continuous archive (15 dk cadence).
- Filestore: `restic` ile günlük S3'e.
- Retention: 30 gün günlük, 12 ay haftalık, 7 yıl aylık (e-Arşiv 10 yıl zorunluluğu için).
- Restore testi: ayda 1 kez staging'de.

## 11. İncident response

- On-call rotasyon: HashTap ekibinden 1 kişi, 24/7 (MVP sırasında 1 kişiyim, 24/7 değil — pilot restoranla beklenti hizala).
- Runbook: `docs/RUNBOOK.md` (bu dosya faz 9'da yazılır).
- Post-mortem kültürü: her incident sonrası ertesi gün yazılı analiz.

## 12. Günlük operasyon kontrolü

Basit checklist, her sabah:
- [ ] Dün sipariş adedi, önceki haftalarla karşılaştırma.
- [ ] iyzico settlement dosyası geldi mi.
- [ ] e-Arşiv fail rate < %1.
- [ ] Disk > %20 boş.
- [ ] Son yedek tarihi.
- [ ] Yeni alarm veya incident.

## 13. Kapasite planı

**MVP (1 pilot, ~500 sipariş/gün):**
- Gateway: 2 × CX21 (2 vCPU, 4GB RAM) = ~€10/ay.
- Odoo: 2 × CX31 (2 vCPU, 8GB RAM) = ~€20/ay.
- Postgres: 1 × CX41 (4 vCPU, 16GB RAM) = ~€20/ay.
- Redis: 1 × CX11 = ~€4/ay.
- LB + BW: ~€10/ay.
- S3: ~€5/ay.
- **Toplam: ~€70/ay + kart komisyonu (iyzico) + e-Arşiv komisyonu.**

**20 kiracı, ~10k sipariş/gün:** ~€300/ay.

## 14. Açık konular

- Türk Telekom bulutuna geçiş takvimi.
- K8s'e geçiş eşiği (kiracı sayısı, ekip büyüklüğü).
- DR (disaster recovery): ikinci bölge replikası — MVP sonrası.
- Blue-green yerine canary: %10 trafiği yeni sürüme — ölçek büyüdüğünde.
