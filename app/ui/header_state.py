import json
import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QObject

from app.ui.theme import ACCENT, TEXT_SECONDARY, HEADER_H


def load_languages():
    """Carga la lista de idiomas destino (nombre nativo) desde assets/languages.json."""
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "assets" / "languages.json",
        Path("assets/languages.json"),
    ]
    for p in candidates:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data
            except Exception:
                pass
    return {}


def native_name(lang_tag):
    """Devuelve el nombre nativo de un idioma dado su tag (p.ej. 'es' -> 'Español')."""
    langs = load_languages()
    return langs.get(lang_tag, lang_tag)


class HeaderState(QObject):
    """Estado compartido del header para comunicar cambios al pipeline."""

    languages_changed = Signal(str, str)   # (source, target)
    click_through_changed = Signal(bool)
    poll_changed = Signal(int)