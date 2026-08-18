from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QLabel,
)

from app.ui.header_state import load_languages, native_name
from app.ui.title_bar import TitleBar
from app.ui.theme import HEADER_H, TEXT_SECONDARY


class LanguageCombo(QComboBox):
    def __init__(self, items=None, placeholder="", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setMinimumWidth(120)
        self.setMaximumWidth(190)
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        if items:
            for key, label in items:
                self.addItem(label, key)

    def current_tag(self):
        return self.currentData()

    def set_tag(self, tag):
        for i in range(self.count()):
            if self.itemData(i) == tag:
                self.setCurrentIndex(i)
                return


class HeaderBar(QWidget):
    languages_changed = Signal(str, str)  # (source, target)
    toggle_click_through = Signal()
    minimize_requested = Signal()
    close_requested = Signal()
    support_requested = Signal()

    def __init__(self, ocr_langs, target_langs, source_lang="auto", target_lang="es", parent=None):
        super().__init__(parent)
        self.setObjectName("HeaderBar")
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.ocr_langs = ocr_langs
        self.target_langs = target_langs

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # fila 1: barra de título estilo Windows 11 (drag)
        self.title_bar = TitleBar(self)
        outer.addWidget(self.title_bar)

        # fila 2: selección de idiomas
        lang_row = QWidget(self)
        lang_row.setFixedHeight(HEADER_H)
        layout = QHBoxLayout(lang_row)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # fuente
        src_items = [("auto", "Detectar idioma")]
        for tag in sorted(ocr_langs):
            src_items.append((tag, native_name(tag.split("-")[0])))
        self.src_combo = LanguageCombo(src_items, "Detectar idioma")
        self.src_combo.set_tag(source_lang)

        # botón swap
        self.swap_btn = QPushButton("⇄")
        self.swap_btn.setObjectName("SwapButton")
        self.swap_btn.setToolTip("Intercambiar idiomas")
        self.swap_btn.setCursor(Qt.PointingHandCursor)

        # destino
        dst_items = [(tag, name) for tag, name in target_langs.items()]
        self.dst_combo = LanguageCombo(dst_items, "Idioma destino")
        self.dst_combo.set_tag(target_lang)

        # indicador de estado
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 14px;")
        self.status_dot.setToolTip("Estado")

        # pin (click-through)
        self.pin_btn = QPushButton("📌")
        self.pin_btn.setToolTip("Fijar recuadro (click-through off)")
        self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.setCheckable(True)
        self.pin_btn.setChecked(False)

        # apoyo al proyecto
        self.support_btn = QPushButton("♥")
        self.support_btn.setToolTip("Support the project")
        self.support_btn.setCursor(Qt.PointingHandCursor)
        self.support_btn.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")

        layout.addWidget(self.src_combo)
        layout.addWidget(self.swap_btn)
        layout.addWidget(self.dst_combo)
        layout.addStretch(1)
        layout.addWidget(self.status_dot)
        layout.addWidget(self.support_btn)
        layout.addWidget(self.pin_btn)
        outer.addWidget(lang_row)

        self.src_combo.currentIndexChanged.connect(self._emit_langs)
        self.dst_combo.currentIndexChanged.connect(self._emit_langs)
        self.swap_btn.clicked.connect(self._swap)
        self.pin_btn.clicked.connect(lambda: self.toggle_click_through.emit())
        self.support_btn.clicked.connect(self.support_requested)
        self.title_bar.minimize_requested.connect(self.minimize_requested)
        self.title_bar.close_requested.connect(self.close_requested)

        self._last_src = self.src_combo.current_tag()
        self._last_dst = self.dst_combo.current_tag()

    def _emit_langs(self):
        src = self.src_combo.current_tag() or "auto"
        dst = self.dst_combo.current_tag() or "es"
        self._last_src = src
        self._last_dst = dst
        self.languages_changed.emit(src, dst)

    def _swap(self):
        src = self.src_combo.current_tag() or "auto"
        dst = self.dst_combo.current_tag() or "es"
        # intercambiar: destino -> fuente (si el destino es un idioma OCR disponible)
        if dst in self.ocr_langs or dst == "auto":
            self.src_combo.set_tag(dst)
        else:
            self.src_combo.set_tag("auto")
        self.dst_combo.set_tag(src)
        self._emit_langs()

    def set_status(self, state):
        color = {
            "idle": TEXT_SECONDARY,
            "recognizing": "#FFB84D",
            "translating": "#4DA3FF",
            "ok": "#00E5A0",
            "error": "#FF5C5C",
        }.get(state, TEXT_SECONDARY)
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 14px;")

    def target_name(self):
        return native_name(self.dst_combo.current_tag() or "es")