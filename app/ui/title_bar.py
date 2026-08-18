from PySide6.QtCore import Qt, Signal, QSize, QPoint
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton

from app.ui.theme import APP_NAME, TITLE_H


class TitleBar(QWidget):
    minimize_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(TITLE_H)
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(8)

        self.icon = QLabel()
        icon = QIcon(str(self._icon_path()))
        pix = icon.pixmap(QSize(16, 16))
        self.icon.setPixmap(pix)
        self.icon.setFixedSize(20, 20)
        self.icon.setAlignment(Qt.AlignCenter)

        self.title = QLabel(APP_NAME)
        self.title.setObjectName("TitleLabel")

        self.min_btn = QPushButton("–")
        self.min_btn.setObjectName("MinButton")
        self.min_btn.setToolTip("Minimizar a bandeja")
        self.min_btn.setCursor(Qt.PointingHandCursor)

        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("CloseButton")
        self.close_btn.setToolTip("Salir")
        self.close_btn.setCursor(Qt.PointingHandCursor)

        layout.addWidget(self.icon)
        layout.addWidget(self.title)
        layout.addStretch(1)
        layout.addWidget(self.min_btn)
        layout.addWidget(self.close_btn)

        self.min_btn.clicked.connect(self.minimize_requested)
        self.close_btn.clicked.connect(self.close_requested)

    def _icon_path(self):
        import sys
        from pathlib import Path

        if getattr(sys, "frozen", False):
            base = Path(sys._MEIPASS)
        else:
            base = Path(__file__).resolve().parent.parent.parent
        for p in (base / "assets" / "icon.ico", Path("assets/icon.ico")):
            if p.exists():
                return p
        return base / "assets" / "icon.ico"

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            win = self.window()
            if win and win.windowHandle():
                win.windowHandle().startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)