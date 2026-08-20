"""Acceptance checks for direct text and one mixed-language screenshot."""

import argparse
import json
import os
import sys
import threading
import time
from difflib import SequenceMatcher
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ocr.engine import OcrEngine, _tess_code, _tessdata_dir  # noqa: E402
from app.translator.google import GoogleTranslator  # noqa: E402
from tools.ocr_corpus import CASES  # noqa: E402


EXPECTED_SPANISH = "Hola, ¿cómo estás?"


def _font_for(code, size):
    root = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    base = code.split("-")[0].lower()
    if base in {"zh", "ja"}:
        candidates = ["simsun.ttc", "YuGothR.ttc", "arial.ttf"]
    elif base == "ko":
        candidates = ["malgun.ttf", "arial.ttf"]
    elif base in {"hi", "mr", "ne", "bn", "pa", "gu", "ta", "te", "kn", "ml", "si"}:
        candidates = ["Nirmala.ttc", "arial.ttf"]
    elif base in {"ar", "fa", "ps", "ur", "he", "am", "ti"}:
        candidates = ["arial.ttf", "ebrima.ttf", "Nirmala.ttc"]
    else:
        candidates = ["arial.ttf", "segoeui.ttf"]
    for name in candidates:
        path = root / name
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size=size, index=0)
            except Exception:
                pass
    return ImageFont.load_default()


_FONT_MAP = {
    "ar": "Segoe UI", "fa": "Segoe UI", "ps": "Arial", "ur": "Arial", "ckb": "Segoe UI",
    "he": "Segoe UI", "yi": "Segoe UI",
    "th": "Leelawadee UI", "lo": "Lao UI", "km": "Khmer UI", "my": "Myanmar Text",
    "am": "Ebrima", "ti": "Ebrima",
    "ka": "Sylfaen", "hy": "Sylfaen",
    "hi": "Nirmala UI", "mr": "Nirmala UI", "ne": "Nirmala UI", "bn": "Nirmala UI",
    "pa": "Nirmala UI", "gu": "Nirmala UI", "or": "Nirmala UI", "ta": "Nirmala UI",
    "te": "Nirmala UI", "kn": "Nirmala UI", "ml": "Nirmala UI", "si": "Nirmala UI",
    "zh": "Microsoft YaHei", "ja": "Yu Gothic", "ko": "Malgun Gothic",
    "el": "Segoe UI", "ru": "Segoe UI", "uk": "Segoe UI", "bg": "Segoe UI",
    "sr": "Segoe UI", "mn": "Segoe UI", "kk": "Segoe UI", "ky": "Segoe UI",
    "tg": "Segoe UI", "tk": "Segoe UI", "az": "Segoe UI", "uz": "Segoe UI",
}
_RTL_CODES = {"ar", "fa", "ps", "ur", "ckb", "he", "yi"}
_QT_APP = None
_QT_COUNTER = 0


def _qt_app():
    global _QT_APP
    if _QT_APP is None:
        from PySide6.QtWidgets import QApplication
        _QT_APP = QApplication.instance() or QApplication([])
    return _QT_APP


def _qrender_to_pil(text, family, rtl=False, size=25):
    global _QT_COUNTER
    from PySide6.QtGui import QImage, QPainter, QFont, QTextOption, QFontMetrics
    from PySide6.QtCore import Qt, QRectF
    _qt_app()
    font = QFont(family)
    font.setPixelSize(size)
    metrics = QFontMetrics(font)
    width = metrics.horizontalAdvance(text) + 20
    height = metrics.height() + 16
    img = QImage(max(1, width), max(1, height), QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.white)
    painter = QPainter(img)
    painter.setFont(font)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    option = QTextOption()
    option.setTextDirection(
        Qt.LayoutDirection.RightToLeft if rtl else Qt.LayoutDirection.LeftToRight
    )
    painter.drawText(QRectF(10, 8, width - 20, height - 16), text, option)
    painter.end()
    _QT_COUNTER += 1
    tmp = os.path.join(
        os.environ.get("TEMP", os.environ.get("TMP", ".")),
        f"_qt_render_{os.getpid()}_{_QT_COUNTER}.bmp",
    )
    img.save(tmp, "BMP")
    try:
        return Image.open(tmp).convert("RGB")
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _font_family(code):
    base = code.split("-")[0].lower()
    return _FONT_MAP.get(base, "Segoe UI")


def _render_line(case, size=25, padding=8):
    code, _label, text = case
    return _qrender_to_pil(
        text, _font_family(code), rtl=code.split("-")[0].lower() in _RTL_CODES,
        size=size,
    )


def _render_all(cases):
    images = [
        _render_line(case, size=25)
        for case in cases
    ]
    width = max(image.width for image in images) + 24
    height = sum(image.height for image in images) + 8 * (len(images) + 1)
    canvas = Image.new("RGB", (max(1, width), max(1, height)), "white")
    y = 8
    for image in images:
        canvas.paste(image, (12, y))
        y += image.height + 8
    return canvas


def _normal(value):
    return "".join(ch.casefold() for ch in value if ch.isalnum())


def _translation_ok(value):
    score = SequenceMatcher(None, _normal(EXPECTED_SPANISH), _normal(value)).ratio()
    return score >= 0.45, score


def _direct(cases, translate):
    rows = []
    for code, label, text in cases:
        row = {"code": code, "label": label, "source": text}
        if translate is None:
            row["status"] = "not_run"
            rows.append(row)
            continue
        started = time.perf_counter()
        try:
            result = translate.translate(text, src=code, dst="es")
            valid, score = _translation_ok(result)
            row.update(
                translation=result,
                similarity=round(score, 3),
                seconds=round(time.perf_counter() - started, 3),
                status="ok" if valid else "invalid",
            )
        except Exception as exc:
            row.update(status="error", error=f"{type(exc).__name__}: {exc}")
        rows.append(row)
    return rows


def _run_mta(fn):
    """Ejecuta una función en un hilo con apartment MTA para Windows OCR.
    El hilo principal queda para Qt (QPainter usa STA en Windows)."""
    box = {}

    def worker():
        try:
            import winrt.runtime
            winrt.runtime.init_apartment(winrt.runtime.ApartmentType.MULTI_THREADED)
        except Exception:
            pass
        box["result"] = fn()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join()
    return box.get("result")


def _image(cases):
    image = _render_all(cases)
    started = time.perf_counter()
    result = _run_mta(lambda: OcrEngine("auto").recognize(image))
    seconds = time.perf_counter() - started
    rows = []
    recognized = []
    if result is not None:
        recognized = result.lines or result.text.splitlines()
    for index, expected in enumerate(cases):
        actual = recognized[index] if index < len(recognized) else ""
        score = SequenceMatcher(None, _normal(expected[2]), _normal(actual)).ratio()
        rows.append({
            "index": index,
            "code": expected[0],
            "expected": expected[2],
            "text": actual,
            "similarity": round(score, 3),
            "status": "ok" if score >= 0.55 else "invalid",
        })
    return {
        "seconds": round(seconds, 3),
        "recognized_lines": len(recognized),
        "expected_lines": len(cases),
        "detected": result.detected_lang,
        "rows": rows,
    }


def _lines(cases):
    images = [_render_line(case) for case in cases]

    def run():
        engine = OcrEngine("auto")
        results = []
        started = time.perf_counter()
        for image in images:
            results.append(engine.recognize(image))
        return results, time.perf_counter() - started

    results, seconds = _run_mta(run)
    rows = []
    for index, case in enumerate(cases):
        result = results[index]
        actual = result.text.strip() if result is not None else ""
        score = SequenceMatcher(None, _normal(case[2]), _normal(actual)).ratio()
        rows.append({
            "index": index,
            "code": case[0],
            "expected": case[2],
            "text": actual,
            "similarity": round(score, 3),
            "status": "ok" if score >= 0.55 else "invalid",
            "detected": result.detected_lang if result is not None else None,
        })
    return {"seconds": round(seconds, 3), "cases": len(cases), "rows": rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("--image", action="store_true")
    parser.add_argument("--lines", action="store_true")
    parser.add_argument("--translate", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    cases = CASES[: args.limit] if args.limit else CASES
    if not args.direct and not args.image and not args.lines:
        args.direct = args.image = True
    translator = GoogleTranslator(min_interval=0.25) if args.translate else None
    report = {
        "cases": len(cases),
        "models": {code: _tess_code(code) for code, _, _ in cases},
        "tessdata": str(_tessdata_dir()),
    }
    if args.direct:
        report["direct"] = _direct(cases, translator)
    if args.lines:
        report["lines"] = _lines(cases)
    if args.image:
        report["image"] = _image(cases)
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
