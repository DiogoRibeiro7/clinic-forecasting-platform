"""Shared test configuration.

Several optional model libraries (torch, lightgbm, xgboost, prophet) each
bundle their own OpenMP runtime. On Windows, co-loading them in one process
can abort with a duplicate-libiomp error. Allowing the duplicate load is the
documented, low-risk workaround and is a no-op where the conflict does not
occur (e.g. Linux CI). This must run before any heavy library is imported,
so it lives at conftest import time.
"""

from __future__ import annotations

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
