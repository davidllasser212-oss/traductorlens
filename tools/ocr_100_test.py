"""Run the multilingual OCR corpus against Tesseract and real screenshots.

Synthetic images are rendered in memory by default. Real images are discovered
under testdata/real/<language-code> and may use any common image extension.
Reports are printed as JSON unless --out is supplied.
"""

import argparse
import json
import os
import sys
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ocr.engine import (  # noqa: E402
    _LANG_TO_TESS,
    _TESS_TAG_OVERRIDES,
    _script_ratio,
    _tess_code,
    _tess_image_data,
    _tessdata_dir,
    _init_tesseract,
    OcrEngine,
)
from tools.ocr_corpus import CASES  # noqa: E402


FONT_CANDIDATES = (
    r"C:\Windows\Fonts\Nirmala.ttc",
    r"C:\Windows\Fonts\Arial.ttf",
    r"C:\Windows\Fonts\SegoeUI.ttf",
    r"C:\Windows\Fonts\DejaVuSans.ttf",
)


def _font(size):
    for path in FONT_CANDIDATES:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size=size, index=0)
            except Exception:
                pass
    return ImageFont.load_default()


def _render(text):
    font = _font(42)
    box = font.getbbox(text)
    width = max(900, box[2] - box[0] + 80)
    height = max(130, box[3] - box[1] + 70)
    image = Image.new("RGB", (width, height), "white")
    ImageDraw.Draw(image).text((40, 30), text, fill="black", font=font)
    return image


def _model_codes(code):
    tess = _TESS_TAG_OVERRIDES.get(code.lower()) or _LANG_TO_TESS.get(code.split("-")[0])
    return [tess] if tess else []


def _script_range(code):
    ranges = {
        "hi": (0x0900, 0x097F), "mr": (0x0900, 0x097F), "ne": (0x0900, 0x097F),
        "bn": (0x0980, 0x09FF), "pa": (0x0A00, 0x0A7F), "gu": (0x0A80, 0x0AFF),
        "or": (0x0B00, 0x0B7F), "ta": (0x0B80, 0x0BFF), "te": (0x0C00, 0x0C7F),
        "kn": (0x0C80, 0x0CFF), "ml": (0x0D00, 0x0D7F), "si": (0x0D80, 0x0DFF),
        "th": (0x0E00, 0x0E7F), "lo": (0x0E80, 0x0EFF), "my": (0x1000, 0x109F),
        "ka": (0x10A0, 0x10FF), "am": (0x1200, 0x137F), "km": (0x1780, 0x17FF),
        "he": (0x0590, 0x05FF), "ar": (0x0600, 0x06FF), "fa": (0x0600, 0x06FF),
        "ur": (0x0600, 0x06FF), "el": (0x0370, 0x03FF), "hy": (0x0530, 0x058F),
        "ru": (0x0400, 0x04FF), "uk": (0x0400, 0x04FF), "bg": (0x0400, 0x04FF),
    }
    return ranges.get(code.split("-")[0])


def _normalized(text):
    text = unicodedata.normalize("NFKC", text or "").casefold()
    return "".join(ch for ch in text if not ch.isspace() and not unicodedata.category(ch).startswith("P"))


def _run_case(code, label, text):
    models = _model_codes(code)
    result = {"code": code, "label": label, "expected": text, "models": models}
    if not models:
        result["status"] = "no_tesseract_model"
        return result
    if not _init_tesseract():
        result["status"] = "tesseract_unavailable"
        return result
    image = _render(text)
    started = time.perf_counter()
    recognized, confidence = _tess_image_data(image, models)
    elapsed = time.perf_counter() - started
    result.update(
        text=recognized.strip(),
        confidence=round(confidence, 2),
        seconds=round(elapsed, 3),
        similarity=round(
            SequenceMatcher(None, _normalized(text), _normalized(recognized)).ratio(), 3
        ),
        script_score=round(_script_ratio(recognized, _script_range(code)), 3)
        if _script_range(code)
        else None,
        status="ok" if recognized.strip() else "empty",
    )
    return result


def _real_cases(real_root):
    extensions = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
    by_code = {code: (label, text) for code, label, text in CASES}
    for path in sorted(real_root.rglob("*")):
        if path.suffix.lower() not in extensions:
            continue
        code = path.parent.name
        label, expected = by_code.get(code, (code, ""))
        yield code, label, expected, path


def _run_auto_case(engine, code, label, text):
    image = _render(text)
    started = time.perf_counter()
    result = engine.recognize(image)
    return {
        "code": code,
        "label": label,
        "expected": text,
        "detected": result.detected_lang,
        "text": result.text,
        "similarity": round(
            SequenceMatcher(None, _normalized(text), _normalized(result.text)).ratio(), 3
        ),
        "seconds": round(time.perf_counter() - started, 3),
        "status": "ok" if result.text else "empty",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-dir", type=Path, default=ROOT / "testdata" / "real")
    parser.add_argument("--real-only", action="store_true")
    parser.add_argument("--synthetic-only", action="store_true")
    parser.add_argument("--auto", action="store_true", help="also run OcrEngine auto")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    report = {
        "corpus_size": len(CASES),
        "tessdata": str(_tessdata_dir()),
        "synthetic": [],
        "auto": [],
        "real": [],
    }
    if not args.real_only:
        cases = CASES[: args.limit] if args.limit else CASES
        report["synthetic"] = [_run_case(*case) for case in cases]
        if args.auto:
            engine = OcrEngine("auto")
            report["auto"] = [_run_auto_case(engine, *case) for case in cases]
    if not args.synthetic_only and args.real_dir.is_dir():
        for code, label, expected, path in _real_cases(args.real_dir):
            image = Image.open(path)
            models = _model_codes(code)
            started = time.perf_counter()
            text, confidence = _tess_image_data(image, models) if models else ("", 0.0)
            report["real"].append({
                "file": str(path.relative_to(ROOT)), "code": code, "label": label,
                "expected": expected, "models": models, "text": text.strip(),
                "confidence": round(confidence, 2),
                "similarity": round(
                    SequenceMatcher(None, _normalized(expected), _normalized(text)).ratio(), 3
                ) if expected else None,
                "seconds": round(time.perf_counter() - started, 3),
                "status": "ok" if text.strip() else ("no_tesseract_model" if not models else "empty"),
            })
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
