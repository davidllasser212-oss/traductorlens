from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QHBoxLayout,
)

import os

from app.ui.theme import (
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT, FONT_UI,
)

_DEBUG_LOG = os.environ.get("TRADUCTOR_DEBUG")


def _dbg(msg):
    if _DEBUG_LOG:
        try:
            with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass


class TranslatePanel(QWidget):
    """Panel opaco inferior: muestra la traducción en vivo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TranslatePanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # badges superiores
        badge_row = QHBoxLayout()
        badge_row.setContentsMargins(14, 8, 14, 0)
        self.detected_badge = QLabel("detectando idioma…")
        self.detected_badge.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        badge_row.addWidget(self.detected_badge)
        badge_row.addStretch(1)
        self.target_badge = QLabel("")
        self.target_badge.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold;")
        badge_row.addWidget(self.target_badge)
        outer.addLayout(badge_row)

        # área de texto scrollable
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        self.text_label = QLabel("La traducción en vivo aparecerá aquí.\n"
                                 "Selecciona el área de la pantalla con el recuadro superior.")
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.text_label.setFont(QFont(FONT_UI, 12))
        self.text_label.setStyleSheet(
            f"color: {TEXT_PRIMARY}; background: transparent; padding: 12px; line-height: 150%;"
        )
        self.text_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.scroll.setWidget(self.text_label)
        outer.addWidget(self.scroll, 1)

        # footer
        footer = QHBoxLayout()
        footer.setContentsMargins(14, 6, 14, 8)
        self.footer = QLabel("En vivo · Google")
        self.footer.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px;")
        footer.addWidget(self.footer)
        footer.addStretch(1)
        outer.addLayout(footer)

    def set_translation(self, text, detected=None):
        _dbg(f"panel.set_translation text={text!r} detected={detected} size={self.size().toTuple()} visible={self.isVisible()}")
        if text:
            self.text_label.setText(text)
        else:
            self.text_label.setText(
                "Sin texto traducible en el área.\n"
                "Mueve la ventana para que el recuadro transparente de arriba "
                "quede sobre el texto que quieres traducir."
            )
        if detected:
            self.detected_badge.setText(f"detectado: {detected}")
        else:
            self.detected_badge.setText("detectando idioma…")

    def set_target_label(self, name):
        self.target_badge.setText(f"→ {name}")

    def set_status(self, state):
        if state == "error":
            self.footer.setText("error de red · reintentando…")
        elif state == "translating":
            self.footer.setText("traduciendo…")
        else:
            self.footer.setText("En vivo · Google")