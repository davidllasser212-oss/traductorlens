# TraductorLens

**Point at any text on your screen and read it in your language — live, with zero clicks.**

TraductorLens is a Windows overlay that translates on-screen text in real time. Move the transparent capture window over any text — in games, documents, apps, videos, or websites — and TraductorLens OCRs the area and shows the translation instantly, without you having to copy or paste anything.

## Features

- **Live, hands-free translation** — just position the lens over text; it keeps translating as the text changes.
- **Always-on-top overlay** — stays above any app without getting in the way (click-through mode).
- **Original text stays visible** — the capture window is transparent, so you always see the source under the lens while the translation appears right above it.
- **100+ target languages** — powered by Google Translate (gtx).
- **Automatic source detection** — uses Windows OCR to detect the language automatically.
- **Works everywhere** — games, PDFs, websites, terminals, chat apps… any on-screen text.
- **Single instance** — no duplicate windows, ever.
- **Portable** — a single `.exe`, no installation required.

## Download

Grab the latest `TraductorLens.exe` from the [Releases](https://github.com/davidllasser212-oss/traductorlens/releases) page.

### System requirements

- Windows 10 or 11 (64-bit)
- [OCR language packs](https://support.microsoft.com/en-us/windows/language-packs-for-windows-50971362-24c8-4d2f-88e0-9e3d2e8f6b3f) for the source language you want to recognize (Windows Settings → Time & Language → Language & Region → Add a language). At least one pack is required for OCR.

## How to use

1. Run `TraductorLens.exe`.
2. Move the floating window so the **transparent box** sits over the text you want to translate.
3. Read the translation at the top of the window — it updates automatically.
4. Double-click the window (or the 📌 pin) to toggle click-through so the overlay never blocks your clicks.
5. Drag the window by its title bar; resize it from the edges.

## Building from source

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app\main.py
```

To build the one-file executable:

```powershell
.\packaging\build.ps1
```

## How it works

- **OCR**: Windows.Media.Ocr (WinRT) — runs in a dedicated worker thread to avoid COM conflicts with Qt.
- **Capture**: `mss` grabs only the lens region (physical pixels, DPI-aware).
- **Translation**: Google Translate `gtx` endpoint with an LRU cache, debounce and retry/backoff.
- **UI**: PySide6 (Qt6), frameless, always-on-top, click-through via `WM_NCHITTEST`.

## License

MIT — see [LICENSE](LICENSE).

## Support the project

TraductorLens is free and open source. If it saves you time, consider a small donation:

**Ko-fi: https://ko-fi.com/davidllasser**
