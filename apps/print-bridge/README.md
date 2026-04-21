# @hashtap/print-bridge

POS'u olmayan (veya entegrasyon için hazır olmayan) işletmelerde mutfak yazıcısını besleyen küçük Node ajanı. On-prem çalışır — Raspberry Pi gibi lokal bir cihaza kurulur.

## Ne yapar

Odoo `hashtap_pos` modülü sipariş `kitchen_fired` event'ini yayınlayınca ajan fişi ESC/POS üzerinden yazıcıya basar ve `order.printed` onayını geri gönderir. Segment A'daki (HashTap native, ama fiziksel KDS ekranı olmayan) restoranların default yazıcı çözümü.

Segment B (mevcut POS'u olan restoran) akışında adapter `pos_restaurant`'ın kendi yazıcısına düşürdüğü için print-bridge devre dışı kalabilir.

## Donanım

- Raspberry Pi 4 / Zero 2 W
- Ethernet veya Wi-Fi (lokal ağ, yazıcıya erişebilmeli)
- Epson TM-T20/T82 (veya ESC/POS uyumlu) termal yazıcı

## Env değişkenleri

```
HASHTAP_API_WS=wss://api.example.com/v1/print-bridge
PRINT_BRIDGE_TOKEN=<tenant token>
PRINTER_INTERFACE=tcp://192.168.1.100:9100
```

## Çalıştırma

```sh
npm install
npm run build
HASHTAP_API_WS=... PRINT_BRIDGE_TOKEN=... PRINTER_INTERFACE=... node dist/index.js
```

Prodüksiyonda `systemd` servisi olarak açılması önerilir.

## Durum

İskele. Odoo tarafında event kaynağı oluşunca protokol netleşecek (ROADMAP Faz 6). Yeniden bağlanma, offline kuyruk, sağlık metrikleri daha sonra eklenecek.
