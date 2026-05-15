"""Pure axis-limit helpers and ViewerState re-exports.

The ``compute_axis_limits`` function is extracted from the original
``viz/figure.py`` where it lived as a private helper.  Placing it here
keeps it importable by ``viz/charts.py`` without carrying a Matplotlib
dependency, and keeps it testable in isolation.
"""
from __future__ import annotations

import math

import numpy as np


def floorf(x: float, n: int = 0) -> float:
    """Round down to a multiple of 10**(-n)."""
    factor = 10.0**n
    return math.floor(x * factor) / factor


def ceilf(x: float, n: int = 0) -> float:
    """Round up to a multiple of 10**(-n)."""
    factor = 10.0**n
    return math.ceil(x * factor) / factor


def compute_axis_limits(
    x: np.ndarray,
    y: np.ndarray,
    margin_ratio: float = 0.05,
) -> tuple[float, float, float, float] | None:
    """Compute (xmin, xmax, ymin, ymax) axis limits with a proportional margin.

    Pure function — no side effects.  Returns ``None`` when the arrays contain
    no finite values.

    Parameters
    ----------
    x, y:
        1-D float arrays.  Non-finite values are excluded.
    margin_ratio:
        Fraction of the data span added as padding on each side.

    Returns
    -------
    (xmin, xmax, ymin, ymax) or None.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    mask = np.isfinite(x) & np.isfinite(y)
    xf = x[mask]
    yf = y[mask]
    if xf.size == 0 or yf.size == 0:
        return None

    ymin = float(np.nanmin(yf))
    ymax = float(np.nanmax(yf))
    if math.isclose(ymin, ymax):
        span = max(1.0, abs(ymin) * 0.05)
        ymin -= span
        ymax += span
    else:
        margin = (ymax - ymin) * margin_ratio
        ymin -= margin
        ymax += margin

    xmin = float(np.nanmin(xf))
    xmax = float(np.nanmax(xf))
    if math.isclose(xmin, xmax):
        span = max(1.0, abs(xmin) * 0.05)
        xmin -= span
        xmax += span
    else:
        margin = (xmax - xmin) * margin_ratio
        xmin -= margin
        xmax += margin

    return xmin, xmax, ymin, ymax


def update_xy_span(
    state_span: dict[str, float],
    x: np.ndarray,
    y: np.ndarray,
    lock: bool,
    margin_ratio: float = 0.05,
) -> dict:
    """Expand the stored XY axis span to include the current data.

    Pure function: returns a new dict without mutating ``state_span``.
    The caller is responsible for writing the result back to
    :attr:`~lsl_viewer.types.ViewerState.xy_max_span`.
    """
    limits = compute_axis_limits(x, y, margin_ratio=margin_ratio)
    if limits is None:
        return dict(state_span)
    xmin, xmax, ymin, ymax = limits
    yaxis = state_span.get("yAxis", {})
    xaxis = state_span.get("xAxis", {})

    if lock:
        return {
            "yAxis": {
                "min": round(min(yaxis.get("min", ymin), ymin), 2),
                "max": round(max(yaxis.get("max", ymax), ymax), 2),
            },
            "xAxis": {
                "min": round(min(xaxis.get("min", xmin), xmin), 2),
                "max": round(max(xaxis.get("max", xmax), xmax), 2),
            },
        }
    return {
        "yAxis": {
            "min": floorf(ymin, n=2),
            "max": ceilf(ymax, n=2),
        },
        "xAxis": {
            "min": floorf(xmin, n=2),
            "max": ceilf(xmax, n=2),
        },
    }
