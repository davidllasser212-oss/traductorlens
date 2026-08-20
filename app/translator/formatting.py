import re
import unicodedata
from dataclasses import dataclass


_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:[A-Za-z]{1,4})?\d(?:[\d.,:/%+\-]*\d)?%?(?![A-Za-z0-9_])"
)
_ID_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]{1,10}[-_][A-Za-z0-9][A-Za-z0-9_-]*(?![A-Za-z0-9_])")
_MARKER_RE = re.compile(r"__FMT(?:NUM|BRK|PAR)_[A-Z]+__")


@dataclass
class FormatState:
    numeric_tokens: list
    line_breaks: list
    expected_newlines: int
    marker_order: list


def _marker(prefix, index):
    letters = ""
    value = index
    while True:
        letters = chr(65 + value % 26) + letters
        value = value // 26 - 1
        if value < 0:
            break
    return f"__FMT{prefix}_{letters}__"


def _format_matches(text):
    matches = list(_ID_RE.finditer(text or ""))
    for match in _NUMBER_RE.finditer(text or ""):
        if not any(
            existing.start() <= match.start() < existing.end()
            or match.start() <= existing.start() < match.end()
            for existing in matches
        ):
            matches.append(match)
    return sorted(matches, key=lambda match: match.start())


def extract_numeric_tokens(text):
    return [match.group(0) for match in _format_matches(text)]


def protect_format(text):
    text = text or ""
    numeric_tokens = []
    line_breaks = []
    pieces = []
    cursor = 0
    for match in _format_matches(text):
        pieces.append(text[cursor:match.start()])
        numeric_tokens.append(match.group(0))
        pieces.append(_marker("NUM", len(numeric_tokens) - 1))
        cursor = match.end()
    pieces.append(text[cursor:])
    protected = "".join(pieces)

    def replace_break(match):
        line_breaks.append(match.group(0))
        prefix = "PAR" if len(match.group(0)) > 1 else "BRK"
        return _marker(prefix, len(line_breaks) - 1)

    protected = re.sub(r"\n+", replace_break, protected)
    return protected, FormatState(
        numeric_tokens=numeric_tokens,
        line_breaks=line_breaks,
        expected_newlines=text.count("\n"),
        marker_order=_MARKER_RE.findall(protected),
    )


def restore_format(translated, state):
    translated = translated or ""
    positions = []
    for marker in state.marker_order:
        position = translated.find(marker)
        if position < 0:
            return None
        positions.append(position)
    if positions != sorted(positions):
        return None
    if len(_MARKER_RE.findall(translated)) != len(state.marker_order):
        return None

    restored = translated
    for index, token in enumerate(state.numeric_tokens):
        restored = restored.replace(_marker("NUM", index), token, 1)
    for index, break_value in enumerate(state.line_breaks):
        prefix = "PAR" if len(break_value) > 1 else "BRK"
        restored = restored.replace(_marker(prefix, index), break_value, 1)
    return restored


def _subsequence_preserved(source_tokens, translated_tokens):
    """Cada token del origen debe aparecer en la traducción en el mismo orden
    (la traducción puede generar tokens nuevos, p. ej. nombres propios)."""
    iterator = iter(translated_tokens)
    return all(any(token == item for item in iterator) for token in source_tokens)


def format_is_valid(source, translated):
    if not translated:
        return False
    source_tokens = extract_numeric_tokens(source)
    translated_tokens = extract_numeric_tokens(translated)
    if not _subsequence_preserved(source_tokens, translated_tokens):
        return False
    return source.count("\n") == translated.count("\n")


def translation_is_usable(source, translated, src="auto", dst="es", detected=None):
    if not format_is_valid(source, translated):
        return False
    if src != dst:
        def normalize(value):
            value = unicodedata.normalize("NFKC", value or "").casefold()
            return "".join(ch for ch in value if not ch.isspace())

        same_language = (
            src == "auto"
            and detected is not None
            and str(detected).split("-")[0].casefold() == str(dst).casefold()
        )
        if not same_language and normalize(source) == normalize(translated):
            return False
    return True
