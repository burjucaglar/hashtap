FROM odoo:17

# iyzipay: hashtap_pos.adapters.iyzico için opsiyonel bağımlılık.
# Kurulu olması zarar vermez — IyzicoAdapter credential yoksa zaten
# stub'a düşer. Bu yüzden default imaja ekliyoruz ki canlıya geçerken
# sadece provider kaydına API key girmek yeterli olsun.
USER root
RUN pip3 install --no-cache-dir iyzipay==2.0.0
USER odoo
