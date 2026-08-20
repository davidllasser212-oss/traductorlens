import io
import os
import sys
import threading
import unicodedata

from PIL import Image

_thread_local = threading.local()


def _ocr_debug(message):
    path = os.environ.get("TRADUCTOR_OCR_DEBUG") or os.environ.get("TRADUCTOR_DEBUG")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(message + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helpers de diagnóstico para tools/ (NO usados por el motor de la app).
# Se mantienen para que tools/multilingual_acceptance.py y tools/ocr_100_test.py
# sigan importando sin cambios.
# ---------------------------------------------------------------------------

_LANG_TO_TESS = {
    "am": "amh", "az": "aze", "be": "bel", "bg": "bul", "bn": "ben",
    "ca": "cat", "ceb": "ceb", "co": "cos", "cy": "cym", "eo": "epo",
    "eu": "eus", "fa": "fas", "fy": "fry", "gd": "gla", "gl": "glg",
    "gu": "guj", "ha": "hau", "haw": "haw", "he": "heb", "hi": "hin",
    "hmn": "hmn", "ht": "hat", "hy": "hye", "id": "ind", "ig": "ibo",
    "is": "isl", "jw": "jav", "ka": "kat", "kk": "kaz", "km": "khm",
    "kn": "kan", "ku": "kur", "ky": "kir", "la": "lat", "lb": "ltz",
    "lo": "lao", "mg": "mlg", "mi": "mri", "mk": "mkd", "ml": "mal",
    "mn": "mon", "mr": "mar", "ms": "msa", "mt": "mlt", "my": "mya",
    "ne": "nep", "no": "nor", "ny": "nya", "or": "ori", "pa": "pan",
    "ps": "pus", "rw": "kin", "sd": "snd", "si": "sin", "sm": "smo",
    "sn": "sna", "so": "som", "sq": "sqi", "st": "sot", "su": "sun",
    "sw": "swa", "ta": "tam", "te": "tel", "tg": "tgk", "th": "tha",
    "tk": "tuk", "tl": "tgl", "tt": "tat", "ug": "uig", "uk": "ukr",
    "ur": "urd", "uz": "uzb", "vi": "vie", "xh": "xho", "yi": "yid",
    "yo": "yor", "zu": "zul",
    "ko": "kor", "el": "ell",
    "af": "afr", "ar": "ara", "bs": "bos", "cs": "ces",
    "da": "dan", "de": "deu", "en": "eng", "es": "spa", "et": "est",
    "fi": "fin", "fr": "fra", "ga": "gle", "hr": "hrv",
    "hu": "hun", "it": "ita", "ja": "jpn", "lt": "lit",
    "lv": "lav", "nl": "nld", "pl": "pol", "pt": "por",
    "ro": "ron", "ru": "rus", "sk": "slk", "sl": "slv",
    "sr": "srp", "sv": "swe", "tr": "tur",
    "ti": "tir", "oc": "oci", "ckb": "fas",
    "so": "eng", "xh": "eng", "zu": "eng", "ig": "eng", "ha": "eng",
    "mg": "eng", "qu": "eng", "gn": "eng", "yrl": "eng", "nah": "eng",
    "sc": "eng", "rm": "eng", "ku": "eng", "tl": "eng", "tk": "eng",
}

_TESS_TAG_OVERRIDES = {
    "zh-cn": "chi_sim",
    "zh-sg": "chi_sim",
    "zh-tw": "chi_tra",
    "zh-hk": "chi_tra",
    "zh-mo": "chi_tra",
    "pt-br": "por",
    "pt-pt": "por",
    "no": "nor",
    "nb": "nor",
    "nn": "nor",
    "sr-latn": "eng",
}

_tesseract_ready = False
_tesseract_error = None


def _tess_base_dir():
    if getattr(sys, "_MEIPASS", None):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _resolve_tesseract():
    if os.environ.get("TESSERACT_PATH"):
        return os.environ["TESSERACT_PATH"]
    base = _tess_base_dir()
    for cand in (
        os.path.join(base, "tesseract", "tesseract.exe"),
        os.path.join(base, "bin", "tesseract.exe"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    ):
        if os.path.isfile(cand):
            return cand
    return "tesseract"


def _tessdata_dir():
    base = _tess_base_dir()
    for cand in (
        os.path.join(base, "tessdata"),
        os.path.join(base, "assets", "tessdata"),
    ):
        if os.path.isdir(cand):
            return cand
    return None


def _init_tesseract():
    global _tesseract_ready, _tesseract_error
    if _tesseract_ready:
        return True
    try:
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = _resolve_tesseract()
        td = _tessdata_dir()
        if td:
            os.environ.setdefault("TESSDATA_PREFIX", td)
        _tesseract_ready = True
        return True
    except Exception as e:
        _tesseract_error = e
        return False


def _script_ratio(text, rng):
    """Proporción de caracteres (no espacios) dentro del rango unicode dado."""
    if not text:
        return 0.0
    n = good = 0
    lo, hi = rng
    for ch in text:
        if ch.isspace():
            continue
        n += 1
        cp = ord(ch)
        if lo <= cp <= hi:
            good += 1
    return good / max(1, n)


def _tess_code(lang):
    key = (lang or "").lower()
    if key in _TESS_TAG_OVERRIDES:
        return _TESS_TAG_OVERRIDES[key]
    return _LANG_TO_TESS.get(key.split("-")[0])


def _tess_image_data(pil_image, codes, include_lines=False):
    """Ejecuta Tesseract devolviendo (texto, confianza media). Solo diagnóstico."""
    import pytesseract
    import statistics

    try:
        data = pytesseract.image_to_data(
            pil_image.convert("RGB"),
            lang="+".join(codes),
            config="--psm 6",
            output_type=pytesseract.Output.DICT,
        )
    except Exception:
        return "", 0.0
    confs = [
        float(c)
        for c, t in zip(data["conf"], data["text"])
        if t and t.strip() and c != "-1"
    ]
    mean = statistics.mean(confs) if confs else 0.0
    if include_lines:
        grouped = {}
        for block, paragraph, line, text in zip(
            data["block_num"], data["par_num"], data["line_num"], data["text"]
        ):
            if text and text.strip():
                key = (int(block), int(paragraph), int(line))
                grouped.setdefault(key, []).append(text.strip())
        lines = [" ".join(words) for words in grouped.values()]
        return "".join(data["text"]), mean, lines
    text = "".join(data["text"])
    return text, mean


# ---------------------------------------------------------------------------
# Motor de reconocimiento: únicamente Windows OCR (rápido, sin Tesseract).
# ---------------------------------------------------------------------------

_CYRILLIC_HOMOGLYPHS = set("ABEKMHOPCTXIVY")

_FAMILY_ALIASES = {
    "latin": "latin",
    "cyr": "cyrillic",
    "cyrillic": "cyrillic",
    "arab": "arabic",
    "arabic": "arabic",
    "cjk": "cjk",
    "hangul": "hangul",
    "greek": "greek",
}


def _script_family_of_name(name):
    """Familia de script para un tag de idioma de Windows OCR."""
    name = (name or "").lower()
    if name in _FAMILY_ALIASES:
        return _FAMILY_ALIASES[name]
    if name in ("thai", "tha", "th", "th-th", "lao", "lo", "myanmar", "my",
                "khmer", "km"):
        return "indochinese"
    if name in (
        "devanagari", "bengali", "tamil", "telugu", "kannada",
        "malayalam", "gujarati", "gurmukhi", "oriya", "sinhala",
    ):
        return "indic"
    if any(x in name for x in ("zh", "ja", "ko")):
        return "cjk"
    if any(x in name for x in ("ru", "sr", "uk", "bg", "be")):
        return "cyrillic"
    if any(x in name for x in ("ar", "fa", "ur")):
        return "arabic"
    if "he" in name or name in ("heb",):
        return "hebrew"
    if name.split("-")[0] in (
        "hi", "mr", "ne", "bn", "pa", "gu", "or", "ta", "te", "kn",
        "ml", "si",
    ):
        return "indic"
    if name.split("-")[0] in ("th", "lo", "my", "km"):
        return "indochinese"
    if name.split("-")[0] in ("am", "ti"):
        return "ethiopic"
    if name in ("el", "ell", "grc", "greek"):
        return "greek"
    return "latin"


def _script_of(tag):
    """Familia de alfabeto esperada para un tag de motor OCR."""
    t = (tag or "").lower()
    lang = t.split("-")[0]
    if "zh" in t or "ja" in t or "ko" in t:
        return "cjk"
    if "ru" in t or "sr" in t or "uk" in t or "bg" in t:
        return "cyr"
    if "ar" in t or "fa" in t or "ur" in t:
        return "arab"
    if "he" in t:
        return "hebrew"
    if lang in ("hi", "mr", "ne"):
        return "devanagari"
    if lang == "bn":
        return "bengali"
    if lang == "pa":
        return "gurmukhi"
    if lang == "gu":
        return "gujarati"
    if lang == "or":
        return "oriya"
    if lang == "ta":
        return "tamil"
    if lang == "te":
        return "telugu"
    if lang == "kn":
        return "kannada"
    if lang == "ml":
        return "malayalam"
    if lang == "si":
        return "sinhala"
    if lang == "th":
        return "thai"
    if lang == "lo":
        return "lao"
    if lang == "my":
        return "myanmar"
    if lang == "ka":
        return "georgian"
    if lang == "hy":
        return "armenian"
    if lang == "am":
        return "ethiopic"
    if lang == "ti":
        return "ethiopic"
    if lang == "km":
        return "khmer"
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
    ranges = {
        "devanagari": (0x0900, 0x097F),
        "bengali": (0x0980, 0x09FF),
        "gurmukhi": (0x0A00, 0x0A7F),
        "gujarati": (0x0A80, 0x0AFF),
        "oriya": (0x0B00, 0x0B7F),
        "tamil": (0x0B80, 0x0BFF),
        "telugu": (0x0C00, 0x0C7F),
        "kannada": (0x0C80, 0x0CFF),
        "malayalam": (0x0D00, 0x0D7F),
        "sinhala": (0x0D80, 0x0DFF),
        "thai": (0x0E00, 0x0E7F),
        "lao": (0x0E80, 0x0EFF),
        "georgian": (0x10A0, 0x10FF),
        "ethiopic": (0x1200, 0x137F),
        "myanmar": (0x1000, 0x109F),
        "khmer": (0x1780, 0x17FF),
        "armenian": (0x0530, 0x058F),
        "hebrew": (0x0590, 0x05FF),
        "greek": (0x0370, 0x03FF),
    }
    if want in ranges:
        lo, hi = ranges[want]
        return lo <= cp <= hi
    return (cp < 128 and ch.isalpha()) or 0x00C0 <= cp <= 0x024F


def _score_text(text, tag):
    """Calidad heurística del texto OCR según el alfabeto esperado del motor."""
    if not text:
        return 0.0
    want = _script_of(tag)
    n = good = 0
    for ch in text:
        if ch.isspace() or ch.isdigit():
            continue
        if not (ch.isalpha() or unicodedata.category(ch) == "Mn"):
            continue
        n += 1
        if _in_script(ch, want):
            good += 1
    return good / max(1, n)


def _garbled_latin(text):
    """Detecta latín "latinizado": ASCII mayormente en mayúsculas con muchos
    homoglifos cirílicos (p. ej. 'IIPVlBiT CBiT' leyendo ucraniano con en-US)."""
    upper = sum(1 for ch in text if ch.isupper())
    total = sum(1 for ch in text if ch.isalpha())
    if total < 4 or upper / max(1, total) < 0.5:
        return False
    homos = sum(1 for ch in text if ch in _CYRILLIC_HOMOGLYPHS)
    return homos / max(1, total) >= 0.35


def _init_winrt():
    import winrt.runtime

    if not getattr(_thread_local, "winrt_apartment", False):
        winrt.runtime.init_apartment(winrt.runtime.ApartmentType.MULTI_THREADED)
        _thread_local.winrt_apartment = True
    import winrt.windows.media.ocr
    return winrt.windows.media.ocr


class OCRResult:
    def __init__(self, text="", detected_lang=None, lines=None):
        self.text = text
        self.detected_lang = detected_lang
        self.lines = lines if lines is not None else ([text] if text else [])

    def __bool__(self):
        return bool(self.text)


class OcrEngine:
    """Motor de OCR basado únicamente en Windows OCR (rápido, sin Tesseract).

    En modo "auto" barre todos los motores OCR de Windows instalados y devuelve
    el de mejor calidad por frame, detectando al instante el cambio de idioma
    (latín, ruso, chino, árabe, etc. según los packs instalados).
    """

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
        return None

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

    def _fit_image(self, pil_image):
        max_dim = self.max_image_dimension()
        w, h = pil_image.size
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            pil_image = pil_image.resize(
                (int(w * scale), int(h * scale)), Image.LANCZOS
            )
        return pil_image

    def _recognize_with(self, engine, pil_image):
        bitmap = self._pil_to_software_bitmap(pil_image.convert("RGB"))
        result = engine.recognize_async(bitmap).get()
        detected = None
        try:
            detected = engine.recognizer_language.language_tag
        except Exception:
            pass
        lines = []
        try:
            lines = [
                line.text.strip()
                for line in result.lines
                if line.text and line.text.strip()
            ]
        except Exception:
            pass
        return OCRResult(
            text=(result.text or "").strip(),
            detected_lang=detected,
            lines=lines,
        )

    def _auto_windows_scan(self, pil_image):
        """Barrido de todos los motores OCR de Windows, con ranking por
        (score de script, longitud) excluyendo latín latinizado.

        Devuelve (best, best_key, best_nonlatin, best_nonlatin_key, non_latin,
        available_families)."""
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
            res = self._recognize_with(engine, pil_image)
            return res, (1.0, 1), res, (1.0, 1), False, set()

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

        results = []
        for tag in sorted(tags, key=_key):
            engine = self._create_engine(tag)
            if engine is None:
                continue
            res = self._recognize_with(engine, pil_image)
            score = _score_text(res.text, tag)
            ln = _chars_len(res.text)
            results.append((tag, res, score, ln, _garbled_latin(res.text)))

        best = None
        best_key = (-1.0, -1)
        best_nonlatin = None
        best_nonlatin_key = (-1.0, -1)
        non_latin = False
        available_families = {
            _script_family_of_name(tag)
            for tag in tags
            if self._create_engine(tag) is not None
        }
        for tag, res, score, ln, garbled in results:
            if res is None or ln < 1:
                continue
            fam = _script_family_of_name(tag)
            if not garbled and (score, ln) > best_key:
                best_key = (score, ln)
                best = res
            if fam != "latin" and not garbled and (score, ln) > best_nonlatin_key:
                best_nonlatin_key = (score, ln)
                best_nonlatin = res
            if fam != "latin" and not garbled and score >= 0.6 and ln >= 4:
                non_latin = True

        _ocr_debug(
            "windows="
            + repr([(tag, round(score, 3), ln, res.detected_lang) for tag, res, score, ln, _ in results])
            + " available_families="
            + repr(sorted(available_families))
            + " best="
            + repr((best.detected_lang, best_key) if best else None)
        )

        return (
            best,
            best_key,
            best_nonlatin,
            best_nonlatin_key,
            non_latin,
            available_families,
        )

    def recognize(self, pil_image):
        pil_image = self._fit_image(pil_image)
        if self._lang and self._lang != "auto":
            engine = self._get_engine()
            if engine is not None:
                return self._recognize_with(engine, pil_image)
            return OCRResult()
        best, best_key, best_nonlatin, best_nonlatin_key, _nl, _families = self._auto_windows_scan(pil_image)
        if best is not None and best_key[0] >= 0.5 and best_key[1] >= 1:
            best_fam = _script_family_of_name(best.detected_lang)
            if (
                best_fam == "latin"
                and best_nonlatin is not None
                and best_nonlatin_key[0] >= best_key[0] - 0.1
            ):
                return best_nonlatin
            return best
        engine = self._profile_engine()
        if engine is not None:
            return self._recognize_with(engine, pil_image)
        return best or OCRResult()

    def recognize_quick(self, pil_image):
        return self.recognize(pil_image)


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