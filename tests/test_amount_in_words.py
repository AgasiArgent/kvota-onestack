"""Tests for amount_in_words_russian currency formatting."""
import pytest
from services.export_data_mapper import amount_in_words_russian


class TestAmountInWordsUSD:
    def test_usd_plural(self):
        result = amount_in_words_russian(4580.77, "USD")
        assert "долларов США" in result
        assert "центов" in result

    def test_usd_singular(self):
        result = amount_in_words_russian(1.01, "USD")
        assert "доллар США" in result
        assert "цент" in result

    def test_usd_few(self):
        result = amount_in_words_russian(2.02, "USD")
        assert "доллара США" in result
        assert "цента" in result

    def test_usd_teens(self):
        result = amount_in_words_russian(11.11, "USD")
        assert "долларов США" in result
        assert "центов" in result


class TestAmountInWordsEUR:
    def test_eur_plural(self):
        result = amount_in_words_russian(100.50, "EUR")
        assert "евро" in result
        assert "евроцентов" in result

    def test_eur_singular(self):
        result = amount_in_words_russian(1.01, "EUR")
        assert "евро" in result
        assert result.endswith("евроцент")


class TestAmountInWordsCNY:
    def test_cny_plural(self):
        result = amount_in_words_russian(500.00, "CNY")
        assert "юаней" in result

    def test_cny_singular(self):
        result = amount_in_words_russian(1.00, "CNY")
        assert "юань" in result


class TestAmountInWordsTRY:
    def test_try_plural(self):
        result = amount_in_words_russian(100.00, "TRY")
        assert "турецких лир" in result

    def test_try_singular(self):
        result = amount_in_words_russian(1.00, "TRY")
        assert "турецкая лира" in result

    def test_try_few(self):
        result = amount_in_words_russian(3.00, "TRY")
        assert "турецкие лиры" in result


class TestAmountInWordsRUB:
    def test_rub_unchanged(self):
        result = amount_in_words_russian(1000.00, "RUB")
        assert "рублей" in result
        assert "копеек" in result

    def test_rub_default(self):
        """Default currency is RUB."""
        result = amount_in_words_russian(1000.00)
        assert "рублей" in result


class TestAmountInWordsUnknownCurrency:
    def test_unknown_falls_back_to_rub(self):
        result = amount_in_words_russian(5.00, "GBP")
        assert "рублей" in result
