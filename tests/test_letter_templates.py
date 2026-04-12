"""
Tests for letter_templates service.

Tests:
- render_letter RU with full context
- render_letter RU with missing fields (graceful — empty string, no error)
- render_letter EN produces English output
- Subject template renders with SKUs
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.letter_templates import (
    LETTER_TEMPLATE_RU,
    LETTER_TEMPLATE_EN,
    SUBJECT_TEMPLATE_RU,
    SUBJECT_TEMPLATE_EN,
    render_letter,
)


class TestLetterTemplateConstants:
    """Tests for template constants."""

    def test_ru_template_has_required_placeholders(self):
        """Russian template must contain all required placeholders."""
        required = [
            "{greeting}",
            "{items_list}",
            "{delivery_country}",
            "{incoterms}",
            "{currency}",
            "{sender_name}",
            "{sender_email}",
            "{sender_phone}",
        ]
        for placeholder in required:
            assert placeholder in LETTER_TEMPLATE_RU, (
                f"Missing placeholder {placeholder} in LETTER_TEMPLATE_RU"
            )

    def test_en_template_has_required_placeholders(self):
        """English template must contain all required placeholders."""
        required = [
            "{greeting}",
            "{items_list}",
            "{delivery_country}",
            "{incoterms}",
            "{currency}",
            "{sender_name}",
            "{sender_email}",
            "{sender_phone}",
        ]
        for placeholder in required:
            assert placeholder in LETTER_TEMPLATE_EN, (
                f"Missing placeholder {placeholder} in LETTER_TEMPLATE_EN"
            )

    def test_ru_subject_template_has_skus_placeholder(self):
        """Russian subject template must contain {skus} placeholder."""
        assert "{skus}" in SUBJECT_TEMPLATE_RU

    def test_en_subject_template_has_skus_placeholder(self):
        """English subject template must contain {skus} placeholder."""
        assert "{skus}" in SUBJECT_TEMPLATE_EN


class TestRenderLetterRu:
    """Tests for render_letter with Russian template."""

    def test_render_with_full_context(self):
        """render_letter RU with full context fills all placeholders."""
        context = {
            "greeting": "Иван Петрович",
            "items_list": "- Подшипник SKF 6205\n- Ремень Gates K060923",
            "delivery_country": "Россия",
            "incoterms": "EXW",
            "currency": "USD",
            "sender_name": "Мария Сидорова",
            "sender_email": "maria@kvota.ru",
            "sender_phone": "+7 999 123-45-67",
            "skus": "SKF 6205, Gates K060923",
        }

        subject, body = render_letter("ru", context)

        assert "Иван Петрович" in body
        assert "Подшипник SKF 6205" in body
        assert "Россия" in body
        assert "EXW" in body
        assert "USD" in body
        assert "Мария Сидорова" in body
        assert "maria@kvota.ru" in body
        assert "+7 999 123-45-67" in body
        assert subject  # subject is non-empty

    def test_render_with_missing_fields_graceful(self):
        """render_letter RU with missing fields uses empty strings, no error."""
        context = {
            "greeting": "поставщик",
        }

        subject, body = render_letter("ru", context)

        assert "поставщик" in body
        # Missing placeholders should be empty strings, not raise
        assert "{items_list}" not in body
        assert "{delivery_country}" not in body
        assert "{currency}" not in body

    def test_render_with_empty_context(self):
        """render_letter RU with empty context produces a valid string."""
        subject, body = render_letter("ru", {})

        assert isinstance(subject, str)
        assert isinstance(body, str)
        # No raw placeholders should remain
        assert "{greeting}" not in body
        assert "{items_list}" not in body

    def test_subject_contains_skus(self):
        """Subject template renders with SKUs."""
        context = {
            "skus": "SKF 6205, Gates K060923",
        }

        subject, body = render_letter("ru", context)

        assert "SKF 6205" in subject
        assert "Gates K060923" in subject


class TestRenderLetterEn:
    """Tests for render_letter with English template."""

    def test_render_en_produces_english_output(self):
        """render_letter EN produces English text."""
        context = {
            "greeting": "Mr. Johnson",
            "items_list": "- Bearing SKF 6205\n- Belt Gates K060923",
            "delivery_country": "Russia",
            "incoterms": "EXW",
            "currency": "USD",
            "sender_name": "Maria Sidorova",
            "sender_email": "maria@kvota.ru",
            "sender_phone": "+7 999 123-45-67",
            "skus": "SKF 6205, Gates K060923",
        }

        subject, body = render_letter("en", context)

        assert "Mr. Johnson" in body
        assert "Russia" in body
        assert "EXW" in body
        assert "Maria Sidorova" in body
        assert subject  # non-empty

    def test_render_en_with_missing_fields(self):
        """render_letter EN with missing fields uses empty strings."""
        subject, body = render_letter("en", {"greeting": "Supplier"})

        assert "Supplier" in body
        assert "{items_list}" not in body

    def test_render_en_full_context_produces_complete_letter(self):
        """EN template renders the full business letter with all sections."""
        context = {
            "greeting": "Mr. Chen",
            "items_list": "- Ball Bearing SKF 6205 (qty 100)\n- V-Belt Gates K060923 (qty 50)",
            "delivery_country": "Russia",
            "incoterms": "FOB Shanghai",
            "currency": "USD",
            "sender_name": "Maria Sidorova",
            "sender_email": "maria@kvota.ru",
            "sender_phone": "+7 999 123-45-67",
            "skus": "SKF 6205, Gates K060923",
        }

        subject, body = render_letter("en", context)

        # Opening
        assert body.startswith("Dear Mr. Chen,")
        # Body paragraphs
        assert "Please consider providing a quotation" in body
        assert "Ball Bearing SKF 6205" in body
        assert "V-Belt Gates K060923" in body
        # Logistics section
        assert "Delivery terms: FOB Shanghai" in body
        assert "Delivery destination: Russia" in body
        assert "Currency: USD" in body
        # Closing
        assert "Detailed specification is attached." in body
        assert "Please send us your prices and delivery times." in body
        assert "Best regards," in body
        assert "Maria Sidorova" in body
        assert "maria@kvota.ru" in body
        assert "+7 999 123-45-67" in body
        # No unsubstituted placeholders
        assert "{" not in body
        assert "}" not in body

    def test_render_en_uses_dear_supplier_fallback(self):
        """When caller passes 'Supplier' as greeting (fallback for missing contact name),
        EN template renders 'Dear Supplier,'."""
        subject, body = render_letter("en", {"greeting": "Supplier"})

        assert "Dear Supplier," in body

    def test_render_en_subject_contains_skus(self):
        """EN subject template renders with SKU references."""
        context = {
            "skus": "SKF 6205, Gates K060923, FAG 22220",
        }

        subject, _ = render_letter("en", context)

        assert "SKF 6205" in subject
        assert "Gates K060923" in subject
        assert "FAG 22220" in subject
        # English wording
        assert "Request for quotation" in subject

    def test_render_returns_tuple(self):
        """render_letter always returns a (subject, body) tuple."""
        result = render_letter("en", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)


class TestRenderLetterEdgeCases:
    """Edge case tests for render_letter."""

    def test_unknown_language_defaults_to_ru(self):
        """Unknown language falls back to Russian template."""
        context = {"greeting": "Тест"}
        subject_ru, body_ru = render_letter("ru", context)
        subject_unknown, body_unknown = render_letter("xx", context)

        # Should default to RU
        assert body_unknown == body_ru

    def test_context_with_extra_keys_ignored(self):
        """Extra keys in context that are not in template are ignored."""
        context = {
            "greeting": "Test",
            "nonexistent_key": "should not cause error",
        }
        subject, body = render_letter("ru", context)
        assert "Test" in body
