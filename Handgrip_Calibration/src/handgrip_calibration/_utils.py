"""Internal utilities shared across handgrip_calibration modules.

All helpers here are pure functions with no side effects.
"""

from __future__ import annotations

import math

import numpy as np


def finite_or_none(value: float | int | None) -> float | int | None:
    """Return *value* if finite, otherwise ``None``.

    Handles numpy scalars transparently so JSON serialisation does not
    receive ``nan`` / ``inf`` values that would break strict parsers.
    """
    if value is None:
        return None
    if isinstance(value, (int, np.integer)):
        return int(value)
    value = float(value)
    return value if math.isfinite(value) else None
