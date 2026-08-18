from PySide6.QtCore import Qt, QRect, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget

from app.ui.theme import (
    BG_PANEL, ACCENT, ERROR, AMBER, BLUE, LENS_PAD, LENS_CORNER,
)


class LensPanel(QWidget):
    """Lente: fondo opaco con un hueco transparente central (borde cian).
    Solo a través del hueco se ve y captura la pantalla; el resto queda cubierto."""

    double_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.status = "idle"

    def set_status(self, status):
        if status != self.status:
            self.status = status
            self.update()

    def _status_color(self):
        return {
            "idle": ACCENT,
            "recognizing": AMBER,
            "translating": BLUE,
            "ok": ACCENT,
            "error": ERROR,
        }.get(self.status, ACCENT)

    def hole_rect(self):
        """Rectángulo del hueco transparente en coordenadas locales."""
        r = self.rect()
        return QRect(
            r.x() + LENS_PAD,
            r.y() + LENS_PAD,
            r.width() - 2 * LENS_PAD,
            r.height() - 2 * LENS_PAD,
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            win = self.window()
            if win and win.windowHandle():
                win.windowHandle().startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit()
        event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # fondo opaco del área del lente (cubre la pantalla de alrededor)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(BG_PANEL))
        painter.drawRect(self.rect())

        # hueco transparente: se recorta para ver la pantalla
        hole = QRectF(self.hole_rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        painter.setBrush(Qt.black)
        painter.drawRoundedRect(hole, LENS_CORNER, LENS_CORNER)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        # borde cian del hueco (estado)
        pen = QPen(QColor(self._status_color()), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(hole, LENS_CORNER, LENS_CORNER)

        painter.end()
