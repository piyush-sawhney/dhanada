"""Dhanada base exception."""


class DhanadaError(Exception):
    """Base exception for all Dhanada application errors."""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return self.message
