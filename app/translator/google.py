import time
import threading
import requests


class GoogleTranslator:
    """Traductor gratuito de Google (endpoint no oficial `client=gtx`).

    Sin API key, ~130+ idiomas, auto-detect con `sl=auto`.
    Con cadena de fallback y backoff exponencial ante 429/5xx.
    """

    ENDPOINTS = [
        "https://translate.googleapis.com/translate_a/single",
        "https://translate-pa.googleapis.com/v1/translateHtml",
    ]

    def __init__(self, timeout=8, max_backoff=60.0, min_interval=0.12):
        self.timeout = timeout
        self.max_backoff = max_backoff
        self.min_interval = min_interval
        self._next_ok_time = 0.0
        self._last_request = 0.0
        self._rate_lock = threading.Lock()
        self._session = requests.Session()
        self._cancel = threading.Event()

    def _wait_if_blocked(self):
        with self._rate_lock:
            wait = max(
                self._next_ok_time - time.monotonic(),
                self._last_request + self.min_interval - time.monotonic(),
            )
        if wait > 0:
            if self._cancel.wait(min(wait, self.max_backoff)):
                return False
        if self._cancel.is_set():
            return False
        with self._rate_lock:
            self._last_request = time.monotonic()
        return True

    def cancel(self):
        self._cancel.set()

    def reset(self):
        self._cancel.clear()

    def translate(self, text, src="auto", dst="es"):
        if not text or not text.strip():
            return ""
        if not self._wait_if_blocked():
            return ""
        text = text.strip()

        for idx, endpoint in enumerate(self.ENDPOINTS):
            try:
                if endpoint.endswith("/translate_a/single"):
                    out = self._call_single(endpoint, text, src, dst)
                else:
                    out = self._call_html(endpoint, text, src, dst)
                if out is not None:
                    self._next_ok_time = 0.0
                    return out
            except requests.HTTPError as e:
                code = getattr(e.response, "status_code", None)
                if code in (429, 500, 502, 503, 504):
                    backoff = (2 ** (idx + 1)) * (1 + len(text) / 4000)
                    retry_after = e.response.headers.get("Retry-After")
                    try:
                        backoff = max(backoff, float(retry_after)) if retry_after else backoff
                    except (TypeError, ValueError):
                        pass
                    self._next_ok_time = time.monotonic() + min(backoff, self.max_backoff)
                else:
                    raise
            except Exception:
                if idx == len(self.ENDPOINTS) - 1:
                    raise
        return ""

    def _call_single(self, endpoint, text, src, dst):
        params = {"client": "gtx", "sl": src, "tl": dst, "dt": "t", "q": text}
        r = self._session.get(endpoint, params=params, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        return "".join(seg[0] for seg in data[0] if seg and seg[0])

    def _call_html(self, endpoint, text, src, dst):
        payload = [[[text], src, dst, True], [1]]
        r = self._session.post(
            endpoint,
            params={"f": "translate"},
            json=payload,
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data and isinstance(data[0], list):
            chunks = data[0][0]
            if isinstance(chunks, list):
                return "".join(str(c) for c in chunks)
        return None
