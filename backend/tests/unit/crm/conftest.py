"""Fixtures for CRM unit tests (require a database)."""

import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def _crm_db(
    _ensure_tables: None,
    _clean_tables: None,
) -> None:
    """Ensure database tables exist and are clean for each CRM unit test.

    ``_ensure_tables`` (session-scoped) creates schemas and tables once.
    ``_clean_tables`` (function-scoped) truncates all data before each test.
    """
