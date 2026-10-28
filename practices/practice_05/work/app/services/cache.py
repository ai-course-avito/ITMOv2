from collections import OrderedDict
from threading import RLock
from typing import Any


class LRUCache:
    def __init__(self, capacity: int = 128) -> None:
        self.capacity = capacity
        self._values: OrderedDict[str, Any] = OrderedDict()
        self._lock = RLock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key not in self._values:
                return None
            self._values.move_to_end(key)
            return self._values[key]

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._values[key] = value
            self._values.move_to_end(key)
            while len(self._values) > self.capacity:
                self._values.popitem(last=False)
