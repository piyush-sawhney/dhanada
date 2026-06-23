"""PAN (Permanent Account Number) validation and normalization."""

import re

PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


def normalize_pan(pan: str) -> str:
    """Normalize a PAN string (uppercase, strip whitespace)."""
    return pan.upper().strip()


def validate_pan(pan: str) -> bool:
    """Validate a PAN number format: AAAAA1234A (5 letters, 4 digits, 1 letter)."""
    return bool(PAN_PATTERN.match(normalize_pan(pan)))
