# Changelog

## 1.1.0 - 2026-08-19

- Added adaptive quick/full OCR processing for the live translation pipeline.
- Added bundled Tesseract OCR with multilingual traineddata.
- Improved automatic script ranking for Latin, Cyrillic, Arabic, CJK, and Indic scripts.
- Fixed Hindi detection when Windows OCR returns false Russian, Latin, or Tigrinya candidates.
- Added a 100-language OCR corpus and synthetic/real-image test harness.
- Added optional OCR candidate diagnostics through `TRADUCTOR_OCR_DEBUG`.
