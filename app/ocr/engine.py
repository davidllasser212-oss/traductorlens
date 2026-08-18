import io
import threading

from PIL import Image

_thread_local = threading.local()


def _init_winrt():
    import winrt.runtime

    if not getattr(_thread_local, "winrt_apartment", False):
        winrt.runtime.init_apartment(winrt.runtime.ApartmentType.MULTI_THREADED)
        _thread_local.winrt_apartment = True
    import winrt.windows.media.ocr
    return winrt.windows.media.ocr


class OCRResult:
    def __init__(self, text="", detected_lang=None):
        self.text = text
        self.detected_lang = detected_lang

    def __bool__(self):
        return bool(self.text)


class OcrEngine:
    def __init__(self, source_lang="auto"):
        self._lock = threading.Lock()
        self._engine = None
        self._lang = None
        self.set_language(source_lang)

    def _init_winrt(self):
        return _init_winrt()

    def available_languages(self):
        ocr = self._init_winrt()
        try:
            return sorted(
                (l.language_tag for l in ocr.OcrEngine.available_recognizer_languages),
                key=lambda t: t.lower(),
            )
        except Exception:
            return []

    def max_image_dimension(self):
        ocr = self._init_winrt()
        return int(ocr.OcrEngine.max_image_dimension)

    def set_language(self, source_lang):
        with self._lock:
            self._lang = source_lang
            self._engine = None

    def _get_engine(self):
        if self._engine is not None:
            return self._engine
        ocr = self._init_winrt()
        if not self._lang or self._lang == "auto":
            engine = ocr.OcrEngine.try_create_from_user_profile_languages()
        else:
            import winrt.windows.globalization as g

            try:
                language = g.Language(self._lang)
                engine = ocr.OcrEngine.try_create_from_language(language)
            except Exception:
                engine = None
        if engine is None:
            engine = ocr.OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            raise RuntimeError(
                "No se encontró ningún motor de OCR de Windows. "
                "Instala un idioma de OCR en Configuración > Hora e idioma > Idioma."
            )
        self._engine = engine
        return engine

    def _pil_to_software_bitmap(self, pil_image):
        import winrt.windows.graphics.imaging as img
        import winrt.windows.storage.streams as ss

        buf = io.BytesIO()
        pil_image.save(buf, format="BMP")
        bs = ss.InMemoryRandomAccessStream()
        bs.write_async(buf.getvalue()).get()
        bs.seek(0)
        decoder = img.BitmapDecoder.create_async(bs).get()
        return decoder.get_software_bitmap_async().get()

    def recognize(self, pil_image):
        from PIL import Image

        engine = self._get_engine()
        max_dim = self.max_image_dimension()
        w, h = pil_image.size
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            pil_image = pil_image.resize(
                (int(w * scale), int(h * scale)), Image.LANCZOS
            )

        bitmap = self._pil_to_software_bitmap(pil_image.convert("RGB"))
        result = engine.recognize_async(bitmap).get()

        detected = None
        try:
            detected = engine.recognizer_language.language_tag
        except Exception:
            pass
        return OCRResult(text=(result.text or "").strip(), detected_lang=detected)


def available_ocr_languages(timeout=10):
    """Consulta los idiomas OCR instalados desde un thread dedicado
    (evita conflictos de apartment COM con el main thread de Qt)."""
    box = {}

    def _worker():
        try:
            box["langs"] = OcrEngine("auto").available_languages()
        except Exception as e:
            box["error"] = e

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout)
    return box.get("langs", []), box.get("error")