"""Tests for CRM model — PAN validation and normalization."""

import pytest
from dhanada.crm.models import validate_pan, normalize_pan


class TestPANValidation:
    def test_valid_pan(self):
        assert validate_pan("ABCDE1234A") is True

    def test_valid_pan_lowercase(self):
        """Lowercase input should be normalized and valid."""
        assert validate_pan("abcde1234a") is True

    def test_valid_pan_with_spaces(self):
        assert validate_pan("  ABCDE1234A  ") is True

    def test_invalid_pan_short(self):
        assert validate_pan("ABC1234A") is False

    def test_invalid_pan_long(self):
        assert validate_pan("ABCDE12345A") is False

    def test_invalid_pan_wrong_format_digits_in_letters(self):
        assert validate_pan("12345ABCDA") is False

    def test_invalid_pan_last_char_digit(self):
        assert validate_pan("ABCDE12345") is False

    def test_invalid_pan_middle_digits_wrong(self):
        assert validate_pan("ABCDE12A4A") is False

    def test_invalid_pan_empty(self):
        assert validate_pan("") is False

    def test_invalid_pan_special_chars(self):
        assert validate_pan("ABCDE12@4A") is False


class TestPANNormalization:
    def test_normalize_uppercases(self):
        assert normalize_pan("abcde1234a") == "ABCDE1234A"

    def test_normalize_strips(self):
        assert normalize_pan("  ABCDE1234A  ") == "ABCDE1234A"