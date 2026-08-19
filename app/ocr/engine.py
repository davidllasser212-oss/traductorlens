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


def _script_of(tag):
    """Familia de alfabeto esperada para un tag de motor OCR."""
    t = tag.lower()
    if "zh" in t or "ja" in t or "ko" in t:
        return "cjk"
    if "ru" in t or "sr" in t or "uk" in t or "bg" in t:
        return "cyr"
    if "ar" in t or "fa" in t or "ur" in t or "he" in t:
        return "arab"
    return "latin"


def _in_script(ch, want):
    cp = ord(ch)
    if want == "cjk":
        return (
            0x4E00 <= cp <= 0x9FFF
            or 0x3400 <= cp <= 0x4DBF
            or 0x3000 <= cp <= 0x303F
        )
    if want == "cyr":
        return 0x0400 <= cp <= 0x04FF
    if want == "arab":
        return 0x0600 <= cp <= 0x06FF
    return (cp < 128 and ch.isalpha()) or 0x00C0 <= cp <= 0x024F


def _score_text(text, tag):
    """Calidad heurística del texto OCR según el alfabeto esperado del motor.

    Puntúa la proporción de caracteres (no espacios, no dígitos) que caen en el
    script del tag. Un motor con el idioma correcto puntúa alto (~0.85+); uno
    equivocado que "adivina" puntúa mucho más bajo (chino leído como latino
    da ~0.0 para CJK). A diferencia de la versión por palabras, no se rompe con
    escrituras sin separadores tipo CJK."""
    if not text:
        return 0.0
    want = _script_of(tag)
    n = good = 0
    for ch in text:
        if ch.isspace() or ch.isdigit():
            continue
        n += 1
        if _in_script(ch, want):
            good += 1
    return good / max(1, n)


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
        """Prueba todos los idiomas OCR instalados y elige el mejor resultado.

        Ranking por (score de script, longitud de texto): el desempate por
        longitud evita falsos positivos cortos (p. ej. un motor árabe que
        "adivina" 2 caracteres con score 1.0 frente al chino correcto y más
        largo). Los idiomas del perfil de usuario van primero para el caso
        habitual es-ES/en-US."""
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

        def _chars_len(text):
            return sum(1 for ch in text if not ch.isspace())

        best = None
        best_score = -1.0
        best_len = -1
        for tag in sorted(tags, key=_key):
            engine = self._create_engine(tag)
            if engine is None:
                continue
            res = self._recognize_with(engine, pil_image)
            score = _score_text(res.text, tag)
            ln = _chars_len(res.text)
            if score > best_score or (score == best_score and ln > best_len):
                best_score = score
                best_len = ln
                best = res
            if score >= 0.95 and ln >= 6:
                break
        if best is not None and best_score >= 0.5 and best_len >= 1:
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