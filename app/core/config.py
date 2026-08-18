import json
import os
import ctypes
from pathlib import Path

APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "TraductorLens"
CACHE_DIR = Path(os.environ.get("LOCALAPPDATA", APP_DIR)) / "TraductorLens"

DEFAULTS = {
    "window": {"x": 300, "y": 200, "width": 420, "height": 480},
    "source_lang": "auto",
    "target_lang": None,  # se resuelve al primer arranque
    "poll_interval_ms": 800,
    "click_through": True,
    "support_url": "https://www.paypal.me/",
}


def default_target_lang():
    try:
        import winrt.windows.globalization as g

        lang = g.Language.get_default_ui_text_language()
        return str(lang.language_tag).split("-")[0]
    except Exception:
        return "es"


class Config:
    def __init__(self, path=None):
        self.path = Path(path) if path else APP_DIR / "config.json"
        self._data = {}
        self.load()

    def load(self):
        data = {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        self._data = {**DEFAULTS, **data}
        if self._data.get("target_lang") in (None, ""):
            self._data["target_lang"] = default_target_lang()

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = str(self.path) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except Exception:
            pass

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self.save()