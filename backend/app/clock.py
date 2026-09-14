"""Injectable "today", so scoring never calls `date.today()` directly and
stays reproducible. `LISTING_SEARCH_REFERENCE_DATE=YYYY-MM-DD` pins it."""

from __future__ import annotations

import os
from datetime import date

REFERENCE_DATE_ENV = "LISTING_SEARCH_REFERENCE_DATE"


def today() -> date:
    """Reference date for days-on-market, honouring the env override."""
    override = os.environ.get(REFERENCE_DATE_ENV)
    if override:
        return date.fromisoformat(override)
    return date.today()
