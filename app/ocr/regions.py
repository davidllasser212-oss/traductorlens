import ctypes
import ctypes.wintypes as wt
import os

import mss
from PIL import Image

_DEBUG_SAVE = os.environ.get("TRADUCTOR_DEBUG_CAPTURE")


def window_rect_hwnd(hwnd):
    """Rectángulo físico de la ventana (GetWindowRect) en píxeles físicos."""
    rect = wt.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return (rect.left, rect.top, rect.right, rect.bottom)


def set_process_dpi_awareness():
    """PER_MONITOR_AWARE_V2 antes de crear la GUI."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


class LensCapture:
    """Captura el contenido de la pantalla bajo el lente (solo la mitad superior,
    excluyendo header y panel de traducción)."""

    def __init__(self, window):
        self.window = window
        self._sct = mss.mss()

    def _lens_rect(self):
        """Rect físico del hueco transparente del lente en coordenadas de pantalla."""
        from app.ui.theme import LENS_PAD

        hwnd = getattr(self.window, "_hwnd", None)
        if not hwnd:
            return None
        l, t, r, b = window_rect_hwnd(hwnd)
        dpr = self.window.devicePixelRatio()

        lens = self.window.lens
        hole = lens.hole_rect()
        # hueco en coordenadas de ventana (lens es hijo directo del central en 0,0)
        hole_x = lens.x() + hole.x()
        hole_y = lens.y() + hole.y()
        return {
            "left": int(l + hole_x * dpr),
            "top": int(t + hole_y * dpr),
            "width": int(hole.width() * dpr),
            "height": int(hole.height() * dpr),
        }

    def capture(self):
        try:
            monitor = self._lens_rect()
            if not monitor or monitor["width"] < 8 or monitor["height"] < 8:
                return None
            shot = self._sct.grab(monitor)
            img = shot.rgb
            im = Image.frombytes("RGB", (shot.width, shot.height), img)
            if _DEBUG_SAVE:
                im.save(_DEBUG_SAVE)
            return im
        except Exception:
            return None

    def close(self):
        try:
            self._sct.close()
        except Exception:
            pass