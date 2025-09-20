import time
from typing import Any, Optional, Dict, Tuple

class TTLCache:
    def __init__(self, default_ttl: float = 60.0, max_items: int = 512):
        self.default_ttl = default_ttl
        self.max_items = max_items
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        item = self._store.get(key)
        if not item: return None
        expires, value = item
        if time.time() > expires:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        if len(self._store) >= self.max_items:
            self._store.pop(next(iter(self._store)), None)
        self._store[key] = (time.time() + (ttl or self.default_ttl), value)

cache = TTLCache()
