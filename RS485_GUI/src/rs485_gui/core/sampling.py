"""Thread-safe sampling-rate statistics and display downsampling utilities.

``SamplingStats`` is used by ``AppState`` to track:
  - full-rate acquisition timing (before GUI throttling)
  - display/render timing (after GUI throttling)

``downsample_points_for_render`` reduces the number of (t, y) points sent to
Plotly, using numpy vectorisation when available and a pure-Python fallback
otherwise.

Dependency chain: none (no internal imports)
"""
from __future__ import annotations

import logging
import math
import statistics
import threading
from collections import deque
from dataclasses import dataclass, field

LOGGER = logging.getLogger(__name__)

try:
    import numpy as np  # type: ignore[import]
except Exception:
    np = None  # type: ignore[assignment]


@dataclass
## @brief Represents the SamplingStats component.
class SamplingStats:
    """Rolling window of inter-frame intervals with outlier rejection.

    All public methods are thread-safe.
    """

    window_dts_s: deque[float] = field(default_factory=lambda: deque(maxlen=128))
    received_samples: int = 0
    dropped_samples_max_rate: int = 0
    last_processed_ts: float | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    ## @brief Reset window.
    #
    #  @param self Parameter description.
    #  @param window_size Parameter description.
    def reset_window(self, window_size: int) -> None:
        """Clear the rolling inter-frame window; preserve total counters."""
        with self._lock:
            self.window_dts_s = deque(maxlen=max(2, int(window_size)))
            self.last_processed_ts = None

    ## @brief Reset all.
    #
    #  @param self Parameter description.
    #  @param window_size Parameter description.
    def reset_all(self, window_size: int) -> None:
        """Clear both the rolling window and the total counters."""
        with self._lock:
            self.window_dts_s = deque(maxlen=max(2, int(window_size)))
            self.received_samples = 0
            self.dropped_samples_max_rate = 0
            self.last_processed_ts = None

    ## @brief Record received samples.
    #
    #  @param self Parameter description.
    #  @param count Parameter description.
    def record_received_samples(self, count: int) -> None:
        with self._lock:
            self.received_samples += int(count)

    ## @brief Add dropped samples.
    #
    #  @param self Parameter description.
    #  @param count Parameter description.
    def add_dropped_samples(self, count: int) -> None:
        with self._lock:
            self.dropped_samples_max_rate += int(count)

    ## @brief Get last processed ts.
    #
    #  @param self Parameter description.
    #  @return Retrieved value for this request.
    def get_last_processed_ts(self) -> float | None:
        with self._lock:
            return self.last_processed_ts

    ## @brief Record processed frame.
    #
    #  @param self Parameter description.
    #  @param host_ts Parameter description.
    def record_processed_frame(self, host_ts: float) -> None:
        with self._lock:
            if self.last_processed_ts is not None:
                dt = host_ts - self.last_processed_ts
                if dt > 0:
                    self.window_dts_s.append(dt)
            self.last_processed_ts = host_ts

    ## @brief Snapshot.
    #
    #  @param self Parameter description.
    #  @param outlier_low_ratio Parameter description.
    #  @param outlier_high_ratio Parameter description.
    #  @param outlier_min_samples Parameter description.
    #  @return Result produced by this function.
    def snapshot(
        self,
        *,
        outlier_low_ratio: float = 0.25,
        outlier_high_ratio: float = 4.0,
        outlier_min_samples: int = 16,
    ) -> tuple[float | None, float | None, int, int, int]:
        """Return ``(mean_hz, std_hz, window_count, received, dropped)``."""
        with self._lock:
            dts = [dt for dt in self.window_dts_s if dt > 0]
            received = self.received_samples
            dropped = self.dropped_samples_max_rate

        if not dts:
            return None, None, 0, received, dropped

        working_dts = dts
        if len(dts) >= max(3, int(outlier_min_samples)):
            median_dt = statistics.median(dts)
            if median_dt > 0:
                low_bound = median_dt * max(0.0, float(outlier_low_ratio))
                high_bound = median_dt * max(1.0, float(outlier_high_ratio))
                filtered = [dt for dt in dts if low_bound <= dt <= high_bound]
                if len(filtered) >= max(3, int(len(dts) * 0.5)):
                    working_dts = filtered

        mean_dt = sum(working_dts) / len(working_dts)
        if mean_dt <= 0:
            return None, None, len(working_dts), received, dropped

        mean_hz = 1.0 / mean_dt
        if len(working_dts) < 2:
            std_hz = 0.0
        else:
            rates_hz = [1.0 / dt for dt in working_dts]
            variance = sum((r - mean_hz) ** 2 for r in rates_hz) / len(rates_hz)
            std_hz = math.sqrt(variance)

        return mean_hz, std_hz, len(working_dts), received, dropped


# ---------------------------------------------------------------------------
# Display downsampling
# ---------------------------------------------------------------------------

def downsample_points_for_render(
    points: list[tuple[float, float]],
    factor: int,
    max_points: int,
) -> list[tuple[float, float]]:
    """Reduce *(t, y)* points for Plotly rendering.

    Applies stride downsampling (``factor``) then caps at ``max_points``.
    Always preserves the last point so the plot edge is never stale.
    Uses numpy when available; falls back to pure Python.
    """
    if not points:
        return points
    factor = max(1, int(factor))

    if np is not None:
        arr = np.asarray(points, dtype=np.float64)
        if arr.ndim != 2 or arr.shape[1] != 2:
            return points
        last_idx = arr.shape[0] - 1
        if factor > 1:
            idx = np.arange(0, arr.shape[0], factor, dtype=np.int64)
            if idx.size == 0 or idx[-1] != last_idx:
                idx = np.append(idx, last_idx)
            arr = arr[idx]
            last_idx = arr.shape[0] - 1
        if max_points > 0 and arr.shape[0] > max_points:
            stride = max(1, math.ceil(arr.shape[0] / max_points))
            idx = np.arange(0, arr.shape[0], stride, dtype=np.int64)
            if idx.size == 0 or idx[-1] != last_idx:
                idx = np.append(idx, last_idx)
            arr = arr[idx]
        return [(float(x), float(y)) for x, y in arr]

    original_last = points[-1]
    if factor > 1:
        points = points[::factor]
        if points[-1] != original_last:
            points.append(original_last)
    if max_points > 0 and len(points) > max_points:
        stride = max(1, math.ceil(len(points) / max_points))
        points = points[::stride]
        if points[-1] != original_last:
            points.append(original_last)
    return points
