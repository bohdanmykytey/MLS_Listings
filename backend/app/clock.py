"""Injectable "today".

Recency scoring needs a reference date. Reading `date.today()` inside the
formula would make every test time-dependent and every screenshot stale, so
the reference date is resolved once per request through this seam and passed
down explicitly.

`LISTING_SEARCH_REFERENCE_DATE=2026-09-12` pins it, which is how the test
suite and a reproducible demo get stable scores.
"""

from __future__ import annotations

import os
from datetime import date

REFERENCE_DATE_ENV = "LISTING_SEARCH_REFERENCE_DATE"


def today() -> date:
    override = os.environ.get(REFERENCE_DATE_ENV)
    if override:
        return date.fromisoformat(override)
    return date.today()
