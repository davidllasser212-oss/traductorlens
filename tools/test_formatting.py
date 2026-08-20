import unittest

from app.translator.formatting import (
    format_is_valid,
    protect_format,
    restore_format,
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


if __name__ == "__main__":
    unittest.main()
