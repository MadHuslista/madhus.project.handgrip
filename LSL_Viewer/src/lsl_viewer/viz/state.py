"""Pure axis-limit helpers and ViewerState re-exports.

The ``compute_axis_limits`` function is extracted from the original
``viz/figure.py`` where it lived as a private helper.  Placing it here
keeps it importable by ``viz/charts.py`` without carrying a Matplotlib
dependency, and keeps it testable in isolation.
"""
from __future__ import annotations

import math

import numpy as np


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


def update_xy_max_span(
    state_span: dict[str, float],
    x: np.ndarray,
    y: np.ndarray,
    margin_ratio: float = 0.05,
) -> dict[str, float]:
    """Expand the stored XY axis span to include the current data.

    Pure function: returns a new dict without mutating ``state_span``.
    The caller is responsible for writing the result back to
    :attr:`~lsl_viewer.types.ViewerState.xy_max_span`.
    """
    limits = compute_axis_limits(x, y, margin_ratio=margin_ratio)
    if limits is None:
        return dict(state_span)
    xmin, xmax, ymin, ymax = limits
    return {
        "xmin": min(state_span.get("xmin", xmin), xmin),
        "xmax": max(state_span.get("xmax", xmax), xmax),
        "ymin": min(state_span.get("ymin", ymin), ymin),
        "ymax": max(state_span.get("ymax", ymax), ymax),
    }
