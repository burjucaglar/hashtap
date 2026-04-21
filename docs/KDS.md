# KDS — Kitchen Display System

Restoran mutfağının her an açık tuttuğu tablet/TV ekranı. Gelen siparişleri
canlı gösterir; personel tek dokunuşla "hazırlanıyor / hazır / servis edildi"
olarak ilerletir. Roadmap'te **Faz 6a** (Faz 6'nın KDS bacağı); fiziki
yazıcı köprüsü **Faz 6b** olarak pilot restoran seçildiğinde yapılacak.

## 1. Neden ayrı bir ekran

Odoo'nun kendi backend'i (`/web`) restoran sahibi / müdür için uygundur ama
mutfakta çalışmaz:

- Çok küçük yazı, çok derin tıklama ağacı.
- Form-tree-kanban UI'ı "akan sipariş" akışına uygun değil.
- Odoo login oturumu her 30-60dk'da çökebilir — mutfak tabletinde o an
  sessizce siparişi kaçırır.
- Branding: müşterinin (restoran sahibinin) "Odoo kullanıyorum" hissi
  almaması; kendi yazılımıysa kendi yazılımı gibi görünmeli.

Bu yüzden KDS ayrı bir sayfa: `/hashtap/kds`. Odoo auth'unu kullanır ama
tam ekran, touch-optimized, dark theme bir uygulamaya benzer.

## 2. Rota haritası

| Rota | Tip | Auth | Ne yapar |
|---|---|---|---|
| `GET  /hashtap/kds` | `http` | `user` | Ana HTML sayfası (QWeb template). `<!DOCTYPE html>` controller'da eklenir (QWeb XML parser DOCTYPE'ı template içinde kabul etmiyor). |
| `POST /hashtap/kds/orders.json` | `json` | `user` | Aktif siparişleri döner. Polling endpoint'i. |
| `POST /hashtap/kds/order/<id>/advance` | `json` | `user` | Bir sonraki duruma ilerlet: `kitchen_sent → preparing → ready → served`. |
| `POST /hashtap/kds/order/<id>/recall` | `json` | `user` | Geri al: `ready → preparing` veya `preparing → kitchen_sent`. Yanlış tıklama kurtarması. |

Dosya: `odoo-addons/hashtap_pos/controllers/kds.py`.

## 3. Sipariş durumu ve KDS kolonu

KDS üç kolondan oluşur:

| Kolon | `hashtap.order.state` |
|---|---|
| **Yeni** | `kitchen_sent` |
| **Hazırlanıyor** | `preparing` |
| **Hazır** | `ready` |

`served` state'i KDS'den düşer. `placed` / `paid` / `cancelled` state'ler
zaten mutfakla ilgili değildir; KDS'e hiç gelmezler.

Eksen bilgisi:

- `HASHTAP_ORDER_STATE` (`odoo-addons/hashtap_pos/models/hashtap_order.py`)
- `KDS_ACTIVE_STATES = ("kitchen_sent", "preparing", "ready")`
- `_KDS_COLUMN` eşlemesi `controllers/kds.py` içinde.

Polling endpoint'i `order="kitchen_fired_at asc, id asc"` ile sıralar —
mutfağa önce düşen sipariş önce gösterilir.

## 4. Zamanlama alanları

Sipariş modelinde iki zaman damgası KDS için kritiktir:

| Alan | Nereden set edilir |
|---|---|
| `kitchen_fired_at` | `action_mark_kitchen_sent()` / `_fire_kitchen()` — sipariş mutfağa ilk düştüğü an. |
| `ready_at` | `action_mark_ready()` — sipariş "hazır" işaretlendiği an. |

KDS bu iki alandan "ne kadar süredir bekliyor" sayısını hesaplar ve
siparişi süreye göre renklendirir:

- `<10dk` normal.
- `10–20dk` uyarı (sarı border).
- `>20dk` tehlike (kırmızı pulse animation).

Süre eşiği `static/src/js/kds.js` içinde; pilotta restorana göre
ayarlanabilir (faz 10'da `res.config.settings` alanı).

## 5. Operatör akışı (tek siparişin yolculuğu)

```
Müşteri ödedi               → state=paid, earsiv_state=issued
Sistem mutfağa düşürdü      → state=kitchen_sent, kitchen_fired_at set
  ↳ KDS "Yeni" kolonunda görünür, sesli beep
Aşçı "Başla" bastı          → state=preparing
  ↳ Kart "Hazırlanıyor" kolonuna kayar
Aşçı "Hazır" bastı          → state=ready, ready_at set
  ↳ Kart "Hazır" kolonuna kayar, garsona sinyal
Garson "Servis et" bastı    → state=served
  ↳ Kart KDS'den düşer
```

Yanlış tıklama kurtarması: "Geri al" butonu önceki duruma döner
(`ready → preparing → kitchen_sent`). `cancelled` KDS içinden tetiklenmez
— bu iş sorumluluğu yönetici panelinde.

## 6. Polling + canlılık

- Ön yüz 3 saniyede bir `/hashtap/kds/orders.json`'u çağırır (vanilla JS,
  framework yok).
- Yeni sipariş geldiğinde (id'ler arasında yeni id varsa) kısa bir
  WebAudio beep çalar — mutfakta ortam gürültülü, görsel uyarı yetersiz.
- Bağlantı koparsa sağ üstteki durum noktası kırmızıya döner. Oturum
  düştüğünde sayfa 401 alır; kullanıcıya bariz bir "yeniden giriş yap"
  yönlendirmesi (faz 10'da — şimdilik otomatik reload).

WebSocket değil polling: Odoo'nun longpolling altyapısı (`bus.bus`) var
ama operasyonel karmaşıklık pilot aşamasına kadar gereksiz. 3sn polling
restoran için çok yeterli (ortalama sipariş aralığı dakikalarca).

## 7. Erişim ve kimlik

- `auth="user"` — Odoo internal user login gerekli.
- Mutfak tableti ayrı bir kullanıcı (`kitchen@restoran.local`) ile
  sürekli login kalır.
- Bu kullanıcı `hashtap.group_kitchen` grubunda olur (faz 8'de rol/izin
  ince ayarı). Şu anda internal user rolü yeterli; sipariş iptali gibi
  tehlikeli aksiyonları KDS kendisi offer etmiyor.

## 8. Branding

Tam ekran, dark theme, HashTap paleti:

- Arka plan: `#1f1b2e` (hashtap-ink).
- Aksan: `#ff7a00` (hashtap-accent).
- Font: sistem font, ama büyük (headers 28px, sipariş kartları 20px).
- Logo: sol üstte "HashTap Mutfak" yazısı.

CSS: `odoo-addons/hashtap_pos/static/src/css/kds.css` — backend
`hashtap_theme` asset bundle'ının dışında, KDS sayfasına doğrudan
`<link rel="stylesheet">` ile yüklenir (KDS `web.assets_backend`
yüklemek istemiyor — tam ekran bağımsız app).

## 9. Açık iyileştirmeler

- **Pas sesi çeşitleri** (yeni, hazır, gecikmiş için ayrı ses).
- **Çoklu istasyon** (soğuk / sıcak mutfak farklı KDS'lere düşer). Sipariş
  kaleminde `preparation_station` alanı ekleyip polling'i filtreleyerek
  yapılır.
- **İstatistik rozeti** (bugün toplam servis, ortalama hazırlık süresi).
- **Longpolling'e geçiş** — 50+ masa/dakika senaryosunda polling yükü
  görünmeye başlarsa Odoo `bus.bus`'ı devreye alınır.

Bu iyileştirmeler pilot geri bildirimine göre önceliklendirilir (faz 10).
