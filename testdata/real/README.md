# Real OCR Corpus

Add screenshots or downloaded reference images below a directory named with
the corpus code, for example:

```text
testdata/real/hi/hindi-news-01.png
testdata/real/ru/russian-ui-01.png
testdata/real/zh-CN/chinese-page-01.png
```

The filename is free-form. The parent directory must match a code in
`tools/ocr_corpus.py`. Keep a `sources.csv` beside each image set with the
source URL, title, license, and retrieval date. Google Images may be used to
find samples, but prefer the original public page or Wikimedia Commons URL
for the recorded source and distribution rights.

Run the real-image pass with:

```powershell
python tools\ocr_100_test.py --real-only --out testdata\reports\ocr-real.json
```
