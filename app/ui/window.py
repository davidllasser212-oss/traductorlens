import ctypes
import ctypes.wintypes as wt
import os

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QColor, QPainter, QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QApplication

from app.ui.header import HeaderBar
from app.ui.header_state import load_languages
from app.ui.lens_panel import LensPanel
from app.ui.translate_panel import TranslatePanel
from app.ui.theme import (
    MIN_W, MIN_H, SHADOW_MARGIN, BG_PANEL,
)

_DEBUG_LOG = os.environ.get("TRADUCTOR_DEBUG")


def _dbg(msg):
    if _DEBUG_LOG:
        try:
            with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

WM_NCHITTEST = 0x0084
HTCLIENT = 1
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17
HTTRANSPARENT = -1


class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self._click_through = bool(config.get("click_through", True))

        flags = (
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(MIN_W, MIN_H)

        self._hwnd = None

        geom = config.get("window", {})
        self.setGeometry(
            int(geom.get("x", 300)),
            int(geom.get("y", 200)),
            int(geom.get("width", 460)),
            int(geom.get("height", 520)),
        )

        # layout
        central = QWidget(self)
        self.vbox = QVBoxLayout(central)
        self.vbox.setContentsMargins(
            SHADOW_MARGIN, SHADOW_MARGIN, SHADOW_MARGIN, SHADOW_MARGIN
        )
        self.vbox.setSpacing(0)

        self.header = HeaderBar(
            ocr_langs=[],  # se llena al iniciar OCR
            target_langs=load_languages(),
            source_lang=config.get("source_lang", "auto"),
            target_lang=config.get("target_lang", "es"),
        )
        self.lens = LensPanel(central)
        self.panel = TranslatePanel(central)

        self.vbox.addWidget(self.header)
        self.vbox.addWidget(self.panel)
        self.vbox.addWidget(self.lens, 1)

        self.setCentralWidget(central)

        self.header.languages_changed.connect(self._on_langs)
        self.header.close_requested.connect(self.quit_app)
        self.header.minimize_requested.connect(self.hide)
        self.header.pin_btn.clicked.connect(self.toggle_click_through)
        self.header.support_requested.connect(self.open_support)
        self.lens.double_clicked.connect(self.toggle_click_through)

        self.pipeline = None
        self._apply_click_through(self._click_through)
        self._update_pin_button()

    def showEvent(self, event):
        super().showEvent(event)
        if self._hwnd is None:
            self._hwnd = int(self.winId())

    # ---------- hook de pipeline ----------

    def attach_pipeline(self, pipeline):
        self.pipeline = pipeline
        pipeline.on_status = self.on_pipeline_status
        pipeline.on_text = self.on_pipeline_text

    def set_ocr_languages(self, langs):
        from app.ui.header_state import native_name

        self.header.ocr_langs = langs or []
        self.header.src_combo.blockSignals(True)
        self.header.src_combo.clear()
        self.header.src_combo.addItem("Detectar idioma", "auto")
        for tag in sorted(load_languages()):
            self.header.src_combo.addItem(native_name(tag), tag)
        self.header.src_combo.set_tag(self.config.get("source_lang", "auto"))
        self.header.src_combo.blockSignals(False)

    # ---------- señales de la UI ----------

    def _on_langs(self, src, dst):
        if self.pipeline:
            self.pipeline.set_languages(src, dst)
        self.config.set("source_lang", src)
        self.config.set("target_lang", dst)
        self.panel.set_target_label(self.header.target_name())

    def toggle_click_through(self):
        self._click_through = not self._click_through
        self._update_pin_button()
        self.config.set("click_through", self._click_through)

    def _apply_click_through(self, enabled):
        # el click-through del lente se resuelve en _hit_test via HTTRANSPARENT
        self.lens.setAttribute(Qt.WA_TransparentForMouseEvents, enabled)

    def _update_pin_button(self):
        self.header.pin_btn.setChecked(not self._click_through)

    # ---------- estado desde pipeline ----------

    def on_pipeline_status(self, state):
        QApplication.instance().postEvent(self, _StatusEvent(state))

    def on_pipeline_text(self, translated, detected):
        QApplication.instance().postEvent(self, _TextEvent(translated, detected))

    def event(self, event):
        if isinstance(event, _StatusEvent):
            self.header.set_status(event.state)
            self.lens.set_status(event.state)
            self.panel.set_status(event.state)
            return True
        if isinstance(event, _TextEvent):
            _dbg(f"window.event TEXT {event.text!r} detected={event.detected}")
            self.panel.set_translation(event.text, event.detected)
            return True
        return super().event(event)

    # ---------- WM_NCHITTEST (resize / click-through) ----------
    # El arrastre se hace en Qt (startSystemMove), no via HTCAPTION.

    def nativeEvent(self, eventType, message):
        try:
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_NCHITTEST:
                pt = msg.pt
                windll_user32 = ctypes.windll.user32
                client = ctypes.wintypes.POINT(int(pt.x), int(pt.y))
                windll_user32.ScreenToClient(self._hwnd, ctypes.byref(client))
                result = self._hit_test(int(client.x), int(client.y))
                if result is not None:
                    return True, result
        except Exception:
            pass
        return super().nativeEvent(eventType, message)

    def _hit_test(self, x, y):
        w, h = self.width(), self.height()
        m = SHADOW_MARGIN

        # zona de resize = margen exterior (incluye la sombra)
        top = y <= m
        bottom = y >= h - m
        left = x <= m
        right = x >= w - m

        if top and left:
            return HTTOPLEFT
        if top and right:
            return HTTOPRIGHT
        if bottom and left:
            return HTBOTTOMLEFT
        if bottom and right:
            return HTBOTTOMRIGHT
        if left:
            return HTLEFT
        if right:
            return HTRIGHT
        if top:
            return HTTOP
        if bottom:
            return HTBOTTOM

        # header (título + idiomas) = client (drag via startSystemMove)
        header_bottom = m + self.header.height()
        if m < y <= header_bottom:
            return HTCLIENT

        # panel de traducción (arriba del lente) = client
        panel_bottom = header_bottom + self.panel.height()
        if header_bottom < y <= panel_bottom:
            return HTCLIENT

        # lente = click-through (si está activado) o client
        if panel_bottom < y <= h - m:
            return HTTRANSPARENT if self._click_through else HTCLIENT

    def resizeEvent(self, event):
        super().resizeEvent(event)
        try:
            self.panel.text_label.setMinimumWidth(self.panel.scroll.width() - 30)
        except Exception:
            pass
        self._save_window()

    def paintEvent(self, event):
        # Fondo 100% opaco: se rellena el borde exterior (14px) con BG_PANEL.
        # El interior bajo el lente NO se pinta aquí para que el hueco cian
        # del lente conserve su transparencia real hacia la pantalla.
        painter = QPainter(self)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(BG_PANEL))
        m = SHADOW_MARGIN
        w, h = self.width(), self.height()
        # franjas superior, inferior, izquierda y derecha
        painter.drawRect(0, 0, w, m)
        painter.drawRect(0, h - m, w, m)
        painter.drawRect(0, m, m, h - 2 * m)
        painter.drawRect(w - m, m, m, h - 2 * m)
        painter.end()
        super().paintEvent(event)

    def show_active(self):
        """Muestra la ventana, la des-minimiza y le da foco (barra de tareas)."""
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()

    def moveEvent(self, event):
        super().moveEvent(event)
        self._save_window()

    def _save_window(self):
        self.config.set("window", {
            "x": self.x(), "y": self.y(),
            "width": self.width(), "height": self.height(),
        })

    def closeEvent(self, event):
        self._save_window()
        if self.pipeline:
            self.pipeline.stop()
        super().closeEvent(event)

    def open_support(self):
        url = self.config.get("support_url", "https://www.paypal.me/")
        QDesktopServices.openUrl(QUrl(url))

    def quit_app(self):
        self._save_window()
        if self.pipeline:
            self.pipeline.stop()
        QApplication.instance().quit()


class _StatusEvent(QEvent):
    def __init__(self, state):
        super().__init__(QEvent.Type(QEvent.User + 1))
        self.state = state


class _TextEvent(QEvent):
    def __init__(self, text, detected):
        super().__init__(QEvent.Type(QEvent.User + 2))
        self.text = text
        self.detected = detected