"""e-Arşiv adapter kayıt defteri.

Provider kaydındaki `code` üzerinden uygun adapter sınıfını bulur.
Controller/service hiçbir zaman adapter sınıfını doğrudan import etmez
— get_adapter(provider) fonksiyonunu çağırır.
"""
from .foriba import ForibaEArsivAdapter
from .mock import MockEArsivAdapter


_REGISTRY = {
    "foriba": ForibaEArsivAdapter,
    "mock": MockEArsivAdapter,
    # "uyumsoft": UyumsoftEArsivAdapter,  # ileride
}


def register_adapter(code: str, cls):
    _REGISTRY[code] = cls


def get_adapter(provider):
    cls = _REGISTRY.get(provider.code)
    if not cls:
        raise KeyError(f"Desteklenmeyen e-Arşiv sağlayıcı: {provider.code}")
    return cls(provider)
