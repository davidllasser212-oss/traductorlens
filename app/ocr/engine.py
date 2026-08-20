import io
import os
import sys
import threading
import unicodedata

from PIL import Image, ImageOps

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

_CYRILLIC_HOMOGLYPHS = set("ABEKMHOPCTXIVY")
_LATIN_LOW = (0x0041, 0x007A)

_TESS_GROUPS = [
    (["rus", "ukr", "bul", "bel", "mkd", "srp", "kaz", "kir", "tgk", "tat"], (0x0400, 0x04FF), "cyrillic"),
    (["chi_sim", "chi_tra", "jpn"], (0x3000, 0x9FFF), "cjk"),
    (["kor"], (0xAC00, 0xD7AF), "hangul"),
    (["ara", "fas", "urd", "pus"], (0x0600, 0x06FF), "arabic"),
    (["hin", "nep", "mar"], (0x0900, 0x097F), "devanagari"),
    (["tha"], (0x0E00, 0x0E7F), "thai"),
    (["heb"], (0x0590, 0x05FF), "hebrew"),
    (["ben"], (0x0980, 0x09FF), "bengali"),
    (["tam"], (0x0B80, 0x0BFF), "tamil"),
    (["tel"], (0x0C00, 0x0C7F), "telugu"),
    (["kan"], (0x0C80, 0x0CFF), "kannada"),
    (["mal"], (0x0D00, 0x0D7F), "malayalam"),
    (["guj"], (0x0A80, 0x0AFF), "gujarati"),
    (["pan"], (0x0A00, 0x0A7F), "gurmukhi"),
    (["ori"], (0x0B00, 0x0B7F), "oriya"),
    (["sin"], (0x0D80, 0x0DFF), "sinhala"),
    (["lao"], (0x0E80, 0x0EFF), "lao"),
    (["mya"], (0x1000, 0x109F), "myanmar"),
    (["kat"], (0x10A0, 0x10FF), "georgian"),
    (["hye"], (0x0530, 0x058F), "armenian"),
    (["amh"], (0x1200, 0x137F), "ethiopic"),
    (["khm"], (0x1780, 0x17FF), "khmer"),
    (["ara", "urd", "fas"], (0x0600, 0x06FF), "arabic"),
    (["ell"], (0x0370, 0x03FF), "greek"),
    (["kor"], (0xAC00, 0xD7AF), "hangul"),
    (["ukr", "bul", "bel", "mkd"], (0x0400, 0x04FF), "cyrillic"),
]

_INDIC_GROUPS = [
    (["hin"], (0x0900, 0x097F), "hi"),
    (["nep"], (0x0900, 0x097F), "ne"),
    (["mar"], (0x0900, 0x097F), "mr"),
]

_TESS_MISSING_SCRIPT_GROUPS = {
    "indic": _INDIC_GROUPS,
    "indochinese": [
        (["tha"], (0x0E00, 0x0E7F), "th"),
        (["lao"], (0x0E80, 0x0EFF), "lo"),
        (["mya"], (0x1000, 0x109F), "my"),
        (["khm"], (0x1780, 0x17FF), "km"),
    ],
    "hebrew": [(["heb"], (0x0590, 0x05FF), "he")],
    "greek": [(["ell"], (0x0370, 0x03FF), "el")],
    "armenian": [(["hye"], (0x0530, 0x058F), "hy")],
    "georgian": [(["kat"], (0x10A0, 0x10FF), "ka")],
    "ethiopic": [(["amh"], (0x1200, 0x137F), "am")],
}

_tesseract_ready = False
_tesseract_error = None
_last_tess_conf = [0.0]


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
        os.path.join(base, "vendor", "tesseract", "bin", "tesseract.exe"),
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

        command = _resolve_tesseract()
        pytesseract.pytesseract.tesseract_cmd = command
        td = _tessdata_dir()
        if td:
            os.environ.setdefault("TESSDATA_PREFIX", td)
        pytesseract.get_tesseract_version()
        _tesseract_ready = True
        return True
    except Exception as e:
        _tesseract_error = e
        return False


def _tess_image_to_string(pil_image, codes):
    import pytesseract

    try:
        return pytesseract.image_to_string(
            pil_image.convert("RGB"), lang="+".join(codes), config="--psm 6"
        )
    except Exception:
        return ""


def _tess_image_data(pil_image, codes, include_lines=False):
    """Ejecuta Tesseract devolviendo (texto, confianza media). La confianza
    media por carácter es el mejor discriminador entre el grupo de idiomas
    correcto y un grupo que "adivina" otro script: un modelo leyendo texto
    que no es el suyo produce basura con confianza baja."""
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
        return "\n".join(lines), mean, lines
    text = "".join(data["text"])
    return text, mean


def _tess_line_records(pil_image, codes, config="--psm 6"):
    import pytesseract

    data = None
    try:
        data = pytesseract.image_to_data(
            pil_image.convert("RGB"),
            lang="+".join(codes),
            config=config,
            output_type=pytesseract.Output.DICT,
        )
    except Exception:
        return []
    grouped = {}
    for index, text in enumerate(data["text"]):
        if not text or not text.strip() or data["conf"][index] == "-1":
            continue
        key = (
            int(data["block_num"][index]),
            int(data["par_num"][index]),
            int(data["line_num"][index]),
        )
        item = grouped.setdefault(key, {"words": [], "top": [], "left": [], "conf": []})
        item["words"].append(text.strip())
        item["top"].append(int(data["top"][index]))
        item["left"].append(int(data["left"][index]))
        item["conf"].append(float(data["conf"][index]))
    records = []
    for item in grouped.values():
        records.append(
            (
                min(item["top"]),
                min(item["left"]),
                " ".join(item["words"]),
                sum(item["conf"]) / len(item["conf"]),
            )
        )
    if records:
        return sorted(records)
    if config != "--psm 13":
        return _tess_line_records(pil_image, codes, config="--psm 13")
    return []


def _line_regions(pil_image):
    gray = pil_image.convert("L")
    width, height = gray.size
    pixels = gray.load()
    rows = []
    for y in range(height):
        ink = sum(1 for x in range(width) if pixels[x, y] < 200)
        if ink > max(2, width // 700):
            rows.append(y)
    if not rows:
        return []
    regions = []
    start = previous = rows[0]
    for y in rows[1:]:
        if y > previous + 10:
            regions.append((max(0, start - 3), min(height, previous + 4)))
            start = y
        previous = y
    regions.append((max(0, start - 3), min(height, previous + 4)))
    return regions


def _crop_line_ink(pil_image, top, bottom):
    """Recorta horizontalmente una banda de línea al bbox de su tinta,
    evitando que márgenes vacíos (p. ej. texto RTL o canvas anchos) degraden
    la lectura de Tesseract."""
    band = pil_image.crop((0, top, pil_image.width, bottom))
    gray = band.convert("L")
    width, height = gray.size
    pixels = gray.load()
    cols = [
        x
        for x in range(width)
        if sum(1 for y in range(height) if pixels[x, y] < 200) >= 2
    ]
    if not cols:
        return band
    pad = 4
    left = max(0, cols[0] - pad)
    right = min(pil_image.width, cols[-1] + pad + 1)
    return pil_image.crop((left, top, right, bottom))


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


def _text_quality(text):
    if not text:
        return 0.0
    n = good = 0
    for ch in text:
        if ch.isspace() or ch.isdigit():
            continue
        if not (ch.isalpha() or unicodedata.category(ch) == "Mn"):
            continue
        n += 1
        good += 1
    return good / max(1, n)


def _text_uniqueness(text):
    """Proporción de caracteres distintos entre los no-espacio. El texto real
    en cualquier idioma tiene variedad (0.5-0.9); un motor que "adivina" otro
    script tiende a repetir los mismos pocos caracteres."""
    ns = [c for c in text if not c.isspace()]
    if not ns:
        return 0.0
    return len(set(ns)) / len(ns)


def _digit_penalty(text):
    """Fracción de dígitos entre los caracteres no-espacio. Un texto real tiene
    pocos dígitos; un motor que "adivina" tiende a escupir muchos."""
    if not text:
        return 0.0
    n = d = 0
    for ch in text:
        if ch.isspace():
            continue
        n += 1
        if ch.isdigit():
            d += 1
    return d / max(1, n)


def _is_cjk_dominant(text):
    """Texto mayoritariamente CJK (Han, kana, hangul). En esos scripts las
    unidades son caracteres sueltos, no palabras, así que la penalización por
    tokens de una sola letra no aplica."""
    if not text:
        return False
    n = good = 0
    for ch in text:
        if ch.isspace():
            continue
        n += 1
        cp = ord(ch)
        if (
            (0x2E80 <= cp <= 0x9FFF)
            or (0xAC00 <= cp <= 0xD7AF)
            or (0x3040 <= cp <= 0x30FF)
        ):
            good += 1
    return n > 0 and good / n >= 0.6


def _ocr_quality_score(text):
    if not text:
        return 0.0
    words = [word for word in text.split() if word]
    one_char = sum(len(word) == 1 for word in words) / max(1, len(words))
    symbols = sum(
        not (ch.isalpha() or ch.isdigit() or ch.isspace())
        for ch in text
    ) / max(1, len(text))
    if _is_cjk_dominant(text):
        one_factor = 1.0
    else:
        one_factor = max(0.0, 1.0 - 0.65 * one_char)
    return _text_quality(text) * one_factor * max(
        0.0, 1.0 - 0.45 * symbols
    ) * max(0.0, 1.0 - _digit_penalty(text))


def _garbled_latin(text):
    """Detecta latín "latinizado": texto ASCII mayormente en mayúsculas con
    muchos homoglifos cirílicos (p. ej. 'IIPVlBiT CBiT' leyendo ucraniano
    con en-US). El texto real en español/inglés no es así."""
    upper = sum(1 for ch in text if ch.isupper())
    total = sum(1 for ch in text if ch.isalpha())
    if total < 4 or upper / max(1, total) < 0.5:
        return False
    homos = sum(1 for ch in text if ch in _CYRILLIC_HOMOGLYPHS)
    return homos / max(1, total) >= 0.35


def _ink_ratio(img):
    """Fracción de píxeles oscuros de la imagen (0..1). Sirve para saber si la
    región tiene contenido antes de gastar tiempo en Tesseract."""
    g = img.convert("L")
    g.thumbnail((160, 160))
    px = g.getdata()
    n = 0
    for v in px:
        if v < 128:
            n += 1
    return n / max(1, len(px))


def _is_exotic(cp):
    return (
        0x0530 <= cp <= 0x05FF
        or 0x0900 <= cp <= 0x0DFF
        or 0x0E00 <= cp <= 0x17FF
        or 0x1200 <= cp <= 0x137F
        or 0x1780 <= cp <= 0x17FF
        or 0x1E00 <= cp <= 0x1EFF
    )


def _tess_code(lang):
    key = (lang or "").lower()
    if key in _TESS_TAG_OVERRIDES:
        return _TESS_TAG_OVERRIDES[key]
    return _LANG_TO_TESS.get(key.split("-")[0])


_FAMILY_ALIASES = {
    "latin": "latin",
    "cyr": "cyrillic",
    "cyrillic": "cyrillic",
    "arab": "arabic",
    "arabic": "arabic",
    "cjk": "cjk",
    "hangul": "hangul",
    "greek": "greek",
    "armenian": "armenian",
    "georgian": "georgian",
    "ethiopic": "ethiopic",
    "hebrew": "hebrew",
    "indochinese": "indochinese",
    "indic": "indic",
}


def _script_family_of_name(name):
    """Familia de script para un nombre de grupo Tesseract o tag de Windows."""
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
    if name == "arabic" or name.split("-")[0] in ("ar", "fa", "ur"):
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
    if name.split("-")[0] in ("hy", "hye", "arm"):
        return "armenian"
    if name.split("-")[0] in ("ka", "kat", "ge"):
        return "georgian"
    if name in ("el", "ell", "grc", "greek"):
        return "greek"
    return "latin"


def _init_winrt():
    import winrt.runtime

    if not getattr(_thread_local, "winrt_apartment", False):
        try:
            winrt.runtime.init_apartment(winrt.runtime.ApartmentType.MULTI_THREADED)
        except OSError:
            try:
                winrt.runtime.init_apartment(
                    winrt.runtime.ApartmentType.SINGLE_THREADED
                )
            except OSError:
                pass
        _thread_local.winrt_apartment = True
    import winrt.windows.media.ocr
    return winrt.windows.media.ocr


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


def _line_script(text):
    counts = {}
    for ch in text or "":
        if ch.isspace() or ch.isdigit() or not ch.isalpha():
            continue
        cp = ord(ch)
        if 0x0400 <= cp <= 0x04FF:
            family = "cyrillic"
        elif 0x4E00 <= cp <= 0x9FFF or 0x3000 <= cp <= 0x30FF:
            family = "cjk"
        elif 0xAC00 <= cp <= 0xD7AF:
            family = "hangul"
        elif 0x0600 <= cp <= 0x06FF:
            family = "arabic"
        elif 0x0900 <= cp <= 0x0DFF:
            family = "indic"
        elif 0x1200 <= cp <= 0x137F:
            family = "ethiopic"
        elif 0x10A0 <= cp <= 0x10FF:
            family = "georgian"
        elif (0x0E00 <= cp <= 0x109F) or (0x1780 <= cp <= 0x17FF):
            family = "indochinese"
        elif 0x0370 <= cp <= 0x03FF:
            family = "greek"
        elif 0x0530 <= cp <= 0x058F:
            family = "armenian"
        elif 0x0590 <= cp <= 0x05FF:
            family = "hebrew"
        else:
            family = "latin"
        counts[family] = counts.get(family, 0) + 1
    return max(counts, key=counts.get) if counts else "latin"


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
    """Calidad heurística del texto OCR según el alfabeto esperado del motor.

    Puntúa la proporción de caracteres (no espacios, no dígitos) que caen en el
    script del tag. Un motor con el idioma correcto puntúa alto (~0.85+); uno
    equivocado que "adivina" puntúa mucho más bajo (chino leído como latino
    da ~0.0 para CJK). A diferencia de la versión por palabras, no se rompe con
    escrituras sin separadores tipo CJK. La puntuación es neutra: no penaliza."""
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


class OCRResult:
    def __init__(self, text="", detected_lang=None, lines=None, line_languages=None):
        self.text = text
        self.detected_lang = detected_lang
        self.lines = list(lines) if lines is not None else (
            text.splitlines() if text else []
        )
        self.line_languages = list(line_languages) if line_languages is not None else []

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
            return self._create_engine(self._lang)
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
        try:
            max_dim = self.max_image_dimension()
        except Exception:
            return pil_image
        w, h = pil_image.size
        if max(w, h) <= max_dim:
            return pil_image
        scale = max_dim / max(w, h)
        return pil_image.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)

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
            lines = [line.text.strip() for line in result.lines if line.text.strip()]
        except Exception:
            pass
        text = "\n".join(lines) if lines else (result.text or "").strip()
        return OCRResult(text=text, detected_lang=detected, lines=lines)

    def _auto_windows_scan(self, pil_image):
        """Barrido de todos los motores OCR de Windows (SIN Tesseract), con ranking
        por (score de script, longitud) excluyendo latín latinizado.

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
        usable_tags = []
        for tag in sorted(tags, key=_key):
            engine = self._create_engine(tag)
            if engine is None:
                continue
            usable_tags.append(tag)
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
            for tag in usable_tags
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

    def recognize_quick(self, pil_image):
        """Pasada corta: solo motores Windows, sin Tesseract. Sirve al pipeline
        para detectar de forma barata si el texto de la pantalla cambió."""
        pil_image = self._fit_image(pil_image)
        if self._lang and self._lang != "auto":
            engine = self._get_engine()
            if engine is not None:
                return self._recognize_with(engine, pil_image)
            return self._recognize_tesseract_lang(pil_image)
        best, best_key, _bn, _bnk, _nl, _families = self._auto_windows_scan(pil_image)
        if best is not None and best_key[0] >= 0.5 and best_key[1] >= 1:
            return best
        engine = self._profile_engine()
        if engine is not None:
            return self._recognize_with(engine, pil_image)
        return best or OCRResult()

    def _recognize_auto(self, pil_image):
        """Arbitra el barrido Windows con Tesseract solo cuando hay ambigüedad real:
        - resultado débil (score < 0.9) → verificar;
        - latín "basura" ganando con lectura no-latina presente → verificar;
        - Windows no leyó nada pero la imagen tiene contenido → verificar.

        En pantallas latinas normales devuelve el mejor Windows sin Tesseract
        (rápido)."""
        windows_image = self._fit_image(pil_image)
        best, best_key, best_nonlatin, best_nonlatin_key, non_latin, available_families = (
            self._auto_windows_scan(windows_image)
        )

        if best is not None and best_key[0] >= 0.5 and best_key[1] >= 1:
            best_fam = _script_family_of_name(best.detected_lang)
            need_tess = best_key[0] < 0.9 or (best_fam == "latin" and non_latin)
            mixed = None
            mixed_fam = ""
            if best.lines or best_fam != "latin":
                mixed = self._recognize_mixed_lines(pil_image, best.lines)
                if mixed is not None:
                    mixed_fam = _line_script(mixed.text)
            if mixed is not None and mixed.text.strip():
                multi_line = len(best.lines) > 1
                if (
                    multi_line
                    or mixed_fam != "latin"
                    or best_fam != "latin"
                    or best_key[0] < 0.9
                ):
                    return mixed
            if need_tess and (mixed is None or not mixed.text.strip()):
                if "indic" not in available_families:
                    indic_res, indic_eff = self._recognize_tesseract_groups(
                        pil_image, _INDIC_GROUPS, preprocess=True
                    )
                    if indic_res is not None and indic_eff >= 0.4:
                        _ocr_debug(
                            f"indic accepted lang={indic_res.detected_lang} eff={indic_eff:.3f}"
                        )
                        return indic_res
                    _ocr_debug(f"indic rejected eff={indic_eff:.3f}")
                for family, groups in _TESS_MISSING_SCRIPT_GROUPS.items():
                    if (
                        family == "indic"
                        or family in available_families
                    ):
                        continue
                    script_res, script_eff = self._recognize_tesseract_groups(
                        pil_image, groups
                    )
                    if script_res is not None and script_eff >= 0.25:
                        return script_res
                tess_res, tess_eff = self._recognize_tesseract_auto(pil_image)
                if tess_res is not None and tess_eff >= 0.25:
                    return tess_res
                if best_fam == "latin" and best_nonlatin and best_nonlatin_key[0] >= 0.7:
                    return best_nonlatin
            return best

        if _ink_ratio(pil_image) >= 0.002:
            mixed = self._recognize_mixed_lines(pil_image)
            if mixed is not None and mixed.text.strip():
                return mixed
            tess_res, tess_eff = self._recognize_tesseract_auto(pil_image)
            if tess_res is not None and tess_eff >= 0.25:
                return tess_res
        engine = self._profile_engine()
        if engine is not None:
            return self._recognize_with(engine, pil_image)
        return best or OCRResult()

    def _recognize_tesseract_auto(self, pil_image):
        return self._recognize_tesseract_groups(
            pil_image, _INDIC_GROUPS + _TESS_GROUPS
        )

    def _recognize_mixed_lines(self, pil_image, windows_lines=None):
        if not _init_tesseract():
            return None
        groups = [(["eng"], (0x0000, 0x024F), "latin")] + _TESS_GROUPS
        regions = _line_regions(pil_image)
        single_line = len(regions) == 1
        script_hints = []
        for top, bottom in regions:
            hint = ""
            if not single_line:
                try:
                    windows = self._auto_windows_scan(
                        self._fit_image(pil_image.crop((0, top, pil_image.width, bottom)))
                    )
                    windows_best = windows[0]
                    if windows_best is not None:
                        hint = _script_family_of_name(windows_best.detected_lang)
                        if hint == "latin":
                            hint = ""
                except Exception:
                    pass
            if hint:
                script_hints.append(hint)
                continue
            try:
                import pytesseract

                crop = pil_image.crop((0, top, pil_image.width, bottom))
                sample = Image.new("RGB", (crop.width, crop.height * 4), "white")
                for index in range(4):
                    sample.paste(crop, (0, index * crop.height))
                try:
                    output = pytesseract.image_to_osd(sample, config="--psm 0")
                except Exception:
                    script_hints.append("")
                    continue
                script = ""
                script_confidence = 0.0
                for line in output.splitlines():
                    if line.startswith("Script:"):
                        script = line.split(":", 1)[1].strip().lower()
                    elif line.startswith("Script confidence:"):
                        try:
                            script_confidence = float(line.split(":", 1)[1].strip())
                        except ValueError:
                            pass
                aliases = {
                    "han": "cjk", "japanese": "cjk", "korean": "hangul",
                    "latin": "latin", "cyrillic": "cyrillic", "arabic": "arabic",
                    "devanagari": "devanagari", "bengali": "bengali",
                    "gurmukhi": "gurmukhi", "gujarati": "gujarati",
                    "tamil": "tamil", "telugu": "telugu", "kannada": "kannada",
                    "malayalam": "malayalam", "sinhala": "sinhala", "thai": "thai",
                    "lao": "lao", "myanmar": "myanmar", "khmer": "khmer",
                    "georgian": "georgian", "armenian": "armenian", "hebrew": "hebrew",
                    "greek": "greek", "ethiopic": "ethiopic",
                }
                hint = aliases.get(script, "")
                if hint == "latin" or script_confidence < 8.0:
                    hint = ""
                script_hints.append(hint)
            except Exception:
                script_hints.append("")
        ordered = []
        for index, (top, bottom) in enumerate(regions):
            window_text = (
                windows_lines[index]
                if windows_lines and index < len(windows_lines)
                else ""
            )
            window_family = _line_script(window_text)
            window_quality = _text_quality(window_text)
            window_digits = _digit_penalty(window_text)
            script_hint = script_hints[index] if index < len(script_hints) else ""

            crop = (
                pil_image.crop((0, top, pil_image.width, bottom))
                if single_line
                else _crop_line_ink(pil_image, top, bottom)
            )
            candidates = []
            for codes, rng, name in groups:
                records = _tess_line_records(crop, codes, config="--psm 7")
                if not records:
                    continue
                _line_top, left, line, conf = records[0]
                if not line.strip():
                    continue
                script_ratio = _script_ratio(line, rng)
                script_family = _script_family_of_name(name)
                inferred_family = _line_script(line)
                score = (
                    script_ratio
                    * _ocr_quality_score(line)
                    * max(0.0, min(1.0, conf / 100.0))
                )
                if script_family != "latin" and inferred_family == "latin":
                    score *= 0.1
                elif script_family == "latin" and inferred_family != "latin":
                    score *= 0.4
                if (
                    script_family != "latin"
                    and inferred_family != "latin"
                    and inferred_family != script_family
                ):
                    score *= 0.4
                candidates.append(
                    (
                        top,
                        left,
                        line,
                        name,
                        score,
                        conf,
                        script_ratio,
                        script_family,
                        inferred_family,
                    )
                )
            if not candidates:
                ordered.append((top, 0, "", "", 0.0, 0.0, 0.0, "", ""))
                continue

            def candidate_score(item):
                score = item[4]
                family = item[7]
                inferred = item[8]
                ratio = item[6]
                if script_hint:
                    if family == script_hint or item[3] == script_hint:
                        score *= 2.5
                    elif inferred == script_hint:
                        score *= 1.4
                    else:
                        score *= 0.04
                if family != "latin" and inferred == "latin":
                    score *= 0.35
                if (
                    inferred not in ("latin", "cyrillic", "greek")
                    and ratio >= 0.85
                    and item[5] >= 50.0
                    and _text_uniqueness(item[2]) >= 0.4
                ):
                    score *= 1.6
                if (
                    family != "latin"
                    and ratio < 0.4
                    and item[5] < 65.0
                ):
                    score *= 0.4
                return score, item[5]

            winner = max(candidates, key=candidate_score)
            if winner[8] == "cyrillic":
                latin_candidates = [c for c in candidates if c[8] == "latin"]
                if latin_candidates:
                    latin_best = max(latin_candidates, key=candidate_score)
                    if candidate_score(latin_best)[0] * 1.2 >= candidate_score(winner)[0]:
                        winner = latin_best
            ordered.append(winner)
        lines = [item[2] for item in ordered]
        return OCRResult(
            text="\n".join(lines),
            lines=lines,
            line_languages=[item[3] for item in ordered],
        )

    def _recognize_tesseract_groups(self, pil_image, groups, preprocess=False):
        if not _init_tesseract():
            return None, 0.0
        best = None
        best_eff = 0.0
        best_len = 0
        images = [pil_image]
        if preprocess:
            gray = ImageOps.grayscale(pil_image)
            images = [
                gray,
                ImageOps.autocontrast(gray),
                gray.point(lambda p: 255 if p >= 150 else 0),
                gray.point(lambda p: 255 if p >= 190 else 0),
            ]
            if max(gray.size) < 900:
                images = [
                    image.resize((image.width * 2, image.height * 2), Image.LANCZOS)
                    for image in images
                ]

        for image in images:
            for codes, rng, name in groups:
                text, conf, lines = _tess_image_data(
                    image, codes, include_lines=True
                )
                text = (text or "").strip()
                if len(text) < 2:
                    continue
                uniq = _text_uniqueness(text)
                if conf < 40.0 or uniq < 0.5:
                    continue
                score = _script_ratio(text, rng)
                q = _text_quality(text)
                conf_norm = max(0.0, min(1.0, conf / 100.0))
                eff = (
                    score
                    * q
                    * conf_norm
                    * (0.3 + 0.7 * uniq)
                    * (1.0 - _digit_penalty(text))
                )
                ln = sum(1 for c in text if not c.isspace())
                if eff > best_eff or (eff == best_eff and ln > best_len):
                    best_eff = eff
                    best_len = ln
                    best = OCRResult(text=text, detected_lang=name, lines=lines)
                    _last_tess_conf[0] = conf
        if best is not None and best_eff >= 0.25 and best_len >= 1:
            return best, best_eff
        _last_tess_conf[0] = 0.0
        return None, 0.0

    def recognize(self, pil_image):
        if self._lang and self._lang != "auto":
            pil_image = self._fit_image(pil_image)
            engine = self._get_engine()
            if engine is not None:
                return self._recognize_with(engine, pil_image)
            return self._recognize_tesseract_lang(pil_image)
        return self._recognize_auto(pil_image)

    def _recognize_tesseract_lang(self, pil_image):
        code = _tess_code(self._lang)
        if not code:
            raise RuntimeError(
                f"No hay motor OCR para el idioma '{self._lang}' "
                "(ni Windows OCR ni Tesseract lo soportan)."
            )
        if not _init_tesseract():
            raise RuntimeError(
                f"El idioma '{self._lang}' requiere Tesseract OCR, "
                "que no está disponible."
            )
        text = _tess_image_to_string(pil_image, [code])
        return OCRResult(text=(text or "").strip(), detected_lang=code)


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
