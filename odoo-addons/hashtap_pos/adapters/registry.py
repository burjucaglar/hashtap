"""Provider code → adapter class eşleşmesi.

Yeni sağlayıcı eklemek için:
    from .base import BasePaymentAdapter
    class StripeAdapter(BasePaymentAdapter): code = "stripe"; ...
    register_adapter("stripe", StripeAdapter)
"""
from typing import Dict, Type

from .base import BasePaymentAdapter
from .iyzico import IyzicoAdapter
from .mock import MockAdapter

_REGISTRY: Dict[str, Type[BasePaymentAdapter]] = {
    "iyzico": IyzicoAdapter,
    "mock": MockAdapter,
}


def register_adapter(code: str, cls: Type[BasePaymentAdapter]) -> None:
    _REGISTRY[code] = cls


def get_adapter(provider) -> BasePaymentAdapter:
    cls = _REGISTRY.get(provider.code)
    if cls is None:
        raise ValueError(f"Unknown payment provider: {provider.code}")
    return cls(provider)
