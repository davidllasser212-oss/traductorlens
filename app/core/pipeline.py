import hashlib
import os
import threading
import time

from PIL import Image

from app.ocr.engine import OcrEngine
from app.translator.google import GoogleTranslator
from app.translator.cache import TranslationCache
from app.translator.formatting import (
    protect_format,
    restore_format,
    translation_is_usable,
)

_DEBUG_LOG = os.environ.get("TRADUCTOR_DEBUG")


def _dbg(msg):
    if _DEBUG_LOG:
        try:
            with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass


class Pipeline:
    """Worker thread: captura del lente -> pre-filtro hash -> OCR -> debounce -> traducción.

    Los resultados se notifican al GUI mediante callbacks (thread-safe con Qt signals).
    """

    def __init__(self, capture_fn, poll_interval_ms=800, cache_path=None):
        self.capture_fn = capture_fn
        self.poll = poll_interval_ms / 1000.0
        self.cache = TranslationCache(cache_path) if cache_path else None
        self._stop = threading.Event()
        self._thread = None

        self.ocr = OcrEngine("auto")
        self.translator = GoogleTranslator()
        self.source_lang = "auto"
        self.target_lang = "es"

        self.on_status = None   # callable(state: str)
        self.on_text = None     # callable(translated: str, detected: str|None)

        self._full_text = None
        self._translated_text = None
        self._translated_hash = None
        self._retry_translation_at = 0.0

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.translator.reset()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self.translator.cancel()
        if self._thread:
            self._thread.join(timeout=3)

    def set_languages(self, source, target):
        self.source_lang = source
        self.target_lang = target
        self._full_text = None
        self._translated_text = None
        self._translated_hash = None
        self._retry_translation_at = 0.0
        if source == "auto":
            self.ocr.set_language("auto")
        else:
            self.ocr.set_language(source)

    def set_poll_interval(self, ms):
        self.poll = max(150, ms) / 1000.0

    def _status(self, state):
        if self.on_status:
            try:
                self.on_status(state)
            except Exception:
                pass

    def _emit(self, translation, detected):
        if self.on_text:
            try:
                self.on_text(translation, detected)
            except Exception:
                pass

    def _frame_hash(self, img):
        small = img.convert("L").resize((max(1, img.width // 8), max(1, img.height // 8)))
        return hashlib.md5(small.tobytes()).hexdigest()

    def _translate_formatted(self, text):
        if "\n" in text:
            translated_lines = []
            for line in text.split("\n"):
                if not line.strip():
                    translated_lines.append("")
                    continue
                line_protected, line_state = protect_format(line)
                line_translation = self.translator.translate(
                    line_protected, src=self.source_lang, dst=self.target_lang
                )
                line_restored = restore_format(line_translation, line_state)
                if line_restored is None or not translation_is_usable(
                    line, line_restored, self.source_lang, self.target_lang
                ):
                    return None
                if (
                    self.source_lang != "auto"
                    and self.source_lang != self.target_lang
                    and line_restored.strip() == line.strip()
                ):
                    return None
                translated_lines.append(line_restored)
            return "\n".join(translated_lines)

        protected, state = protect_format(text)
        translated = self.translator.translate(
            protected, src=self.source_lang, dst=self.target_lang
        )
        restored = restore_format(translated, state)
        if restored is not None and translation_is_usable(
            text, restored, self.source_lang, self.target_lang
        ):
            if (
                self.source_lang != "auto"
                and self.source_lang != self.target_lang
                and restored.strip() == text.strip()
            ):
                return None
            return restored
        return None

    def _run(self):
        self._status("idle")
        while not self._stop.is_set():
            try:
                frame = self.capture_fn()
                if frame is None:
                    _dbg("capture=None")
                    time.sleep(self.poll)
                    continue

                h = self._frame_hash(frame)
                if self._translated_hash == h:
                    time.sleep(self.poll)
                    continue

                self._status("recognizing")
                quick = None
                try:
                    quick = self.ocr.recognize_quick(frame)
                except Exception as e:
                    _dbg(f"quick OCR exception: {type(e).__name__}: {e}")
                qtext = (quick.text or "") if quick else ""

                if not qtext:
                    if self._full_text:
                        self._full_text = None
                        self._translated_text = None
                        self._translated_hash = None
                        self._emit("", quick.detected_lang if quick else None)
                    self._status("idle")
                    time.sleep(self.poll)
                    continue

                if qtext == self._full_text:
                    if self._translated_text != self._full_text:
                        if time.monotonic() >= self._retry_translation_at:
                            pass
                        else:
                            self._status("idle")
                            time.sleep(self.poll)
                            continue
                    else:
                        self._status("idle")
                        time.sleep(self.poll)
                        continue

                result = None
                try:
                    result = self.ocr.recognize(frame)
                except Exception as e:
                    _dbg(f"OCR exception: {type(e).__name__}: {e}")
                if result is None or not result.text:
                    if self._full_text:
                        self._full_text = None
                        self._translated_text = None
                        self._translated_hash = None
                        self._emit("", result.detected_lang if result else None)
                    self._status("idle")
                    time.sleep(self.poll)
                    continue

                text = result.text
                detected = result.detected_lang
                _dbg(f"frame={frame.size} mean={sum(frame.convert('L').getdata()) // max(1, frame.width * frame.height)} text={text!r} detected={detected}")

                if text == self._full_text and self._translated_text == text:
                    self._status("idle")
                    time.sleep(self.poll)
                    continue
                self._full_text = text

                self._status("translating")
                translation = None
                if self.cache is not None:
                    translation = self.cache.get(text, self.source_lang, self.target_lang)
                    if translation and not translation_is_usable(
                        text, translation, self.source_lang, self.target_lang
                    ):
                        self.cache.delete(text, self.source_lang, self.target_lang)
                        translation = None
                if translation is None:
                    try:
                        translation = self._translate_formatted(text)
                    except Exception as e:
                        _dbg(f"translation exception: {type(e).__name__}: {e}")
                        translation = None
                    if self.cache is not None and translation:
                        self.cache.put(text, self.source_lang, self.target_lang, translation)
                if not translation:
                    self._emit(text, detected)
                    self._retry_translation_at = time.monotonic() + 3.0
                    self._status("error")
                    time.sleep(self.poll)
                    continue
                self._translated_text = text
                self._retry_translation_at = 0.0
                self._emit(translation, detected)
                self._status("ok")
                self._translated_hash = h
            except Exception:
                self._status("error")
            time.sleep(self.poll)
