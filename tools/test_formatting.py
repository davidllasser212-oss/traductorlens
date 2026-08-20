import unittest

from app.translator.formatting import (
    extract_numeric_tokens,
    format_is_valid,
    protect_format,
    restore_format,
    translation_is_usable,
)
from app.core.pipeline import Pipeline


class FormattingTests(unittest.TestCase):
    def test_restores_numbers_and_lines_in_order(self):
        source = "Fecha 08/03/2026 - 14:30\nID AB-123 v1.0.2: 25%\n\nRepetido 2024 2024"
        protected, state = protect_format(source)
        restored = restore_format(protected, state)
        self.assertEqual(restored, source)
        self.assertTrue(format_is_valid(source, restored))

    def test_rejects_missing_or_reordered_markers(self):
        source = "A 2024\nB 2025"
        protected, state = protect_format(source)
        self.assertIsNone(restore_format(protected.replace("__FMTNUM_A__", ""), state))
        reordered = protected.replace("__FMTNUM_A__", "__TMP__", 1)
        reordered = reordered.replace("__FMTNUM_B__", "__FMTNUM_A__", 1)
        reordered = reordered.replace("__TMP__", "__FMTNUM_B__", 1)
        self.assertIsNone(restore_format(reordered, state))

    def test_line_fallback_validation(self):
        self.assertTrue(format_is_valid("a 1\nb 2", "a 1\nb 2"))
        self.assertFalse(format_is_valid("a 1\nb 2", "a 1 b 2"))
        self.assertFalse(format_is_valid("a 1", "a 2"))

    def test_pipeline_rejects_translator_that_drops_markers(self):
        pipeline = Pipeline(lambda: None)

        class BadTranslator:
            def translate(self, text, src="auto", dst="es"):
                return "texto traducido"

        pipeline.translator = BadTranslator()
        self.assertIsNone(pipeline._translate_formatted("ID AB-123\nTotal 25%"))

    def test_cjk_number_followed_by_cjk_char_is_protected(self):
        source = "2026年 中俄联合科考"
        self.assertEqual(extract_numeric_tokens(source), ["2026"])
        protected, state = protect_format(source)
        self.assertEqual(state.numeric_tokens, ["2026"])
        self.assertIn("__FMTNUM_A__", protected)
        self.assertEqual(restore_format(protected, state), source)

    def test_cyrillic_number_is_protected(self):
        source = "в 2026 году"
        self.assertEqual(extract_numeric_tokens(source), ["2026"])
        protected, state = protect_format(source)
        self.assertEqual(state.numeric_tokens, ["2026"])
        self.assertEqual(restore_format(protected, state), source)

    def test_arabic_indic_digit_is_protected(self):
        for source in ("٥٪", "رقم ٥"):
            self.assertEqual(extract_numeric_tokens(source), ["٥"])
            protected, state = protect_format(source)
            self.assertEqual(state.numeric_tokens, ["٥"])
            self.assertEqual(restore_format(protected, state), source)

    def test_ascii_word_boundaries(self):
        self.assertEqual(extract_numeric_tokens("abc2026"), ["abc2026"])
        self.assertEqual(extract_numeric_tokens("2026abc"), [])
        self.assertEqual(extract_numeric_tokens("3D"), [])
        self.assertEqual(extract_numeric_tokens("v2"), ["v2"])
        self.assertEqual(extract_numeric_tokens("50%"), ["50%"])
        self.assertEqual(extract_numeric_tokens("1.5"), ["1.5"])

    def test_cjk_number_tokens_match_across_translation(self):
        source = "2026年 中俄联合科考"
        translated = "Expedición conjunta chino-rusa 2026"
        self.assertEqual(extract_numeric_tokens(source), ["2026"])
        self.assertTrue(format_is_valid(source, translated))
        self.assertTrue(translation_is_usable(source, translated))

    def test_punctuation_only_line_kept_in_multiline_fallback(self):
        pipeline = Pipeline(lambda: None)

        class PunctDroppingTranslator:
            def translate(self, text, src="auto", dst="es"):
                if set(text.strip()) <= set("-—…"):
                    return ""
                return "texto traducido"

        pipeline.translator = PunctDroppingTranslator()
        result = pipeline._translate_formatted("Título\n---\nCuerpo")
        self.assertEqual(result, "texto traducido\n---\ntexto traducido")

    def test_passthrough_rejected_even_in_auto(self):
        pipeline = Pipeline(lambda: None)

        class PassthroughTranslator:
            def translate(self, text, src="auto", dst="es"):
                return text

        pipeline.translator = PassthroughTranslator()
        self.assertIsNone(pipeline._translate_formatted("Привет, как ты?", detected="ru"))
        self.assertEqual(
            pipeline._translate_formatted("¿Cómo estás?", detected="es"),
            "¿Cómo estás?",
        )


if __name__ == "__main__":
    unittest.main()
