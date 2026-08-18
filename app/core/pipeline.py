import hashlib
import os
import threading
import time

from PIL import Image

from app.ocr.engine import OcrEngine
from app.translator.google import GoogleTranslator
from app.translator.cache import TranslationCache

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

        self._last_hash = None
        self._stable_text = None
        self._stable_count = 0
        self._translated_hash = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def set_languages(self, source, target):
        self.source_lang = source
        self.target_lang = target
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
        small = img.convert("L").resize((img.width // 8, img.height // 8))
        return hashlib.md5(small.tobytes()).hexdigest()

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
                if h == self._last_hash and self._stable_count == 0:
                    time.sleep(self.poll)
                    continue
                self._last_hash = h

                self._status("recognizing")
                try:
                    result = self.ocr.recognize(frame)
                except Exception as e:
                    _dbg(f"OCR exception: {type(e).__name__}: {e}")
                    result = None
                if result is None:
                    self._status("idle")
                    time.sleep(self.poll)
                    continue
                text = result.text
                detected = result.detected_lang
                _dbg(f"frame={frame.size} mean={sum(frame.convert('L').getdata()) // max(1, frame.width * frame.height)} text={text!r} detected={detected}")

                if not text:
                    self._stable_text = None
                    self._stable_count = 0
                    self._emit("", detected)
                    self._status("idle")
                    time.sleep(self.poll)
                    continue

                if text == self._stable_text:
                    self._stable_count += 1
                else:
                    self._stable_text = text
                    self._stable_count = 1

                if self._stable_count < 2:
                    self._status("idle")
                    time.sleep(self.poll)
                    continue

                self._status("translating")
                translation = None
                if self.cache is not None:
                    translation = self.cache.get(text, self.source_lang, self.target_lang)
                if translation is None:
                    translation = self.translator.translate(
                        text, src=self.source_lang, dst=self.target_lang
                    )
                    if self.cache is not None and translation:
                        self.cache.put(text, self.source_lang, self.target_lang, translation)
                self._emit(translation or "", detected)
                self._status("ok")
                self._translated_hash = h
            except Exception:
                self._status("error")
            time.sleep(self.poll)