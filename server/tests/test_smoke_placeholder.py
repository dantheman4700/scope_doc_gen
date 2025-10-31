"""Placeholder for Supabase smoke tests.

This file exists to remind us to automate the manual smoke checklist once we have
time to wire Supabase credentials into CI. For now the test is skipped to avoid
false positives.
"""

import pytest


@pytest.mark.skip(reason="Supabase smoke test not yet automated")
def test_supabase_smoke_placeholder() -> None:
    """Placeholder smoke test covering Supabase end-to-end flow."""


