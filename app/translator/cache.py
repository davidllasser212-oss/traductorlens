import hashlib
import json
import os
import threading


class TranslationCache:
    """Caché LRU simple con persistencia JSON en %LOCALAPPDATA%."""

    CACHE_VERSION = "v2"

    def __init__(self, path, capacity=500):
        self.path = path
        self.capacity = capacity
        self._lock = threading.Lock()
        self._data = {}
        self._load()

    def _key(self, text, src, dst):
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"{self.CACHE_VERSION}:{src}->{dst}:{h}"

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception:
            self._data = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False)
            os.replace(tmp, self.path)
        except Exception:
            pass

    def get(self, text, src, dst):
        with self._lock:
            key = self._key(text, src, dst)
            value = self._data.get(key)
            if value is not None:
                self._data.pop(key)
                self._data[key] = value
            return value

    def put(self, text, src, dst, translation):
        if not text or not translation:
            return
        with self._lock:
            key = self._key(text, src, dst)
            self._data[key] = translation
            if len(self._data) > self.capacity:
                # elimina las claves más antiguas (orden de inserción en dict)
                for k in list(self._data.keys())[: len(self._data) - self.capacity]:
                    del self._data[k]
        self._save()

    def delete(self, text, src, dst):
        with self._lock:
            self._data.pop(self._key(text, src, dst), None)
        self._save()
