import io
import re
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


def _score_text(text):
    """Calidad heurística del texto OCR: proporción de palabras con solo letras
    (>=2 letras, sin dígitos ni símbolos). Un motor con el idioma correcto
    puntúa ~1.0; uno equivocado que "adivina" suele puntuar bastante más bajo."""
    if not text:
        return 0.0
    words = re.findall(r"\w+", text, flags=re.UNICODE)
    if not words:
        return 0.0
    clean = sum(1 for w in words if len(w) >= 2 and all(ch.isalpha() for ch in w))
    return clean / len(words)


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
        self._engine_cache = {}
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

    def _profile_engine(self):
        ocr = self._init_winrt()
        return ocr.OcrEngine.try_create_from_user_profile_languages()

    def _create_engine(self, tag):
        """Crea un motor OCR para el tag dado (None si no hay pack instalado)."""
        if tag in self._engine_cache:
            return self._engine_cache[tag]
        ocr = self._init_winrt()
        import winrt.windows.globalization as g

        try:
            language = g.Language(tag)
            engine = ocr.OcrEngine.try_create_from_language(language)
        except Exception:
            engine = None
        if engine is not None:
            self._engine_cache[tag] = engine
        return engine

    def _get_engine(self):
        if self._engine is not None:
            return self._engine
        if self._lang and self._lang != "auto":
            engine = self._create_engine(self._lang)
            if engine is not None:
                self._engine = engine
                return engine
        engine = self._profile_engine()
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

    def _recognize_with(self, engine, pil_image):
        bitmap = self._pil_to_software_bitmap(pil_image.convert("RGB"))
        result = engine.recognize_async(bitmap).get()
        detected = None
        try:
            detected = engine.recognizer_language.language_tag
        except Exception:
            pass
        return OCRResult(text=(result.text or "").strip(), detected_lang=detected)

    def _recognize_auto(self, pil_image):
        """Prueba todos los idiomas OCR instalados y elige el resultado de mejor
        calidad (heurística de palabras limpias). Los idiomas del perfil de
        usuario van primero para favorecer el caso habitual es-ES/en-US."""
        ocr = self._init_winrt()
        try:
            tags = sorted(
                (l.language_tag for l in ocr.OcrEngine.available_recognizer_languages),
                key=lambda t: t.lower(),
            )
        except Exception:
            tags = []
        if not tags:
            engine = self._profile_engine()
            if engine is None:
                raise RuntimeError(
                    "No se encontró ningún motor de OCR de Windows. "
                    "Instala un idioma de OCR en Configuración > Hora e idioma > Idioma."
                )
            return self._recognize_with(engine, pil_image)

        profile_tag = None
        try:
            pe = self._profile_engine()
            profile_tag = pe.recognizer_language.language_tag.lower()
        except Exception:
            pass

        def _key(t):
            return (0 if t.lower() == profile_tag else 1, t.lower())

        best = None
        best_score = -1.0
        for tag in sorted(tags, key=_key):
            engine = self._create_engine(tag)
            if engine is None:
                continue
            res = self._recognize_with(engine, pil_image)
            score = _score_text(res.text)
            if score > best_score:
                best_score = score
                best = res
            if score >= 0.95:
                break
        if best is not None and best_score >= 0.5:
            return best
        engine = self._profile_engine()
        if engine is not None:
            return self._recognize_with(engine, pil_image)
        return best or OCRResult()

    def recognize(self, pil_image):
        from PIL import Image

        max_dim = self.max_image_dimension()
        w, h = pil_image.size
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            pil_image = pil_image.resize(
                (int(w * scale), int(h * scale)), Image.LANCZOS
            )

        if self._lang and self._lang != "auto":
            engine = self._get_engine()
            return self._recognize_with(engine, pil_image)
        return self._recognize_auto(pil_image)


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