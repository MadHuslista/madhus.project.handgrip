"""Unit tests for core.timing — pure functions, zero mocking."""
from __future__ import annotations

import math

import numpy as np

from lsl_viewer.core.timing import (
    clock_interval_ms,
    clock_validation_metrics,
    lsl_interval_ms,
)


class TestLslIntervalMs:
    def test_empty_input_returns_nans(self):
        idx, dt, rate, mean = lsl_interval_ms(np.array([]))
        assert idx.size == 0
        assert dt.size == 0
        assert math.isnan(rate)
        assert math.isnan(mean)

    def test_single_sample_returns_nans(self):
        idx, dt, rate, mean = lsl_interval_ms(np.array([1.0]))
        assert idx.size == 0
        assert math.isnan(rate)

    def test_uniform_rate(self):
        # 10 samples at 100 Hz → dt = 10 ms, rate = 100 Hz
        ts = np.arange(10, dtype=np.float64) * 0.01
        idx, dt, rate, mean = lsl_interval_ms(ts)
        assert idx.size == 9
        assert np.allclose(dt, 10.0)
        assert math.isclose(rate, 100.0, rel_tol=1e-6)
        assert math.isclose(mean, 10.0, rel_tol=1e-6)

    def test_ignores_nan_samples(self):
        ts = np.array([0.0, np.nan, 0.02, 0.03], dtype=np.float64)
        idx, dt, rate, mean = lsl_interval_ms(ts)
        # finite: indices 0, 2, 3  → diffs 20 ms, 10 ms
        assert dt.size == 2
        assert math.isclose(mean, 15.0, rel_tol=1e-6)

    def test_non_positive_diffs_excluded(self):
        # Monotonically decreasing → all diffs negative → no valid output
        ts = np.array([0.03, 0.02, 0.01], dtype=np.float64)
        idx, dt, rate, mean = lsl_interval_ms(ts)
        assert dt.size == 0
        assert math.isnan(rate)


class TestClockIntervalMs:
    def test_microsecond_scale(self):
        # 5 samples at 1000 Hz in µs → dt = 1000 µs → 1 ms → rate = 1000 Hz
        clock = np.array([0, 1000, 2000, 3000, 4000], dtype=np.float64)
        idx, dt, rate, mean = clock_interval_ms(clock, scale_to_ms=1e-3)
        assert np.allclose(dt, 1.0)
        assert math.isclose(rate, 1000.0, rel_tol=1e-6)


class TestClockValidationMetrics:
    def _make_aligned(self, n: int = 50, rate_hz: float = 100.0):
        ts = np.arange(n, dtype=np.float64) / rate_hz
        clock = ts.copy()  # perfect agreement
        return ts, clock

    def test_perfect_agreement(self):
        ts, clock = self._make_aligned()
        m = clock_validation_metrics(ts, clock, clock_scale_to_s=1.0)
        assert math.isclose(m["lsl_rate_hz"], 100.0, rel_tol=1e-4)
        assert math.isclose(m["clock_rate_hz"], 100.0, rel_tol=1e-4)
        assert abs(m["median_dt_error_ms"]) < 1e-9
        assert abs(m["clock_vs_lsl_span_error_ms"]) < 1e-9
        assert abs(m["median_clock_minus_lsl_s"]) < 1e-12

    def test_too_few_samples_returns_nans(self):
        ts = np.array([0.0])
        m = clock_validation_metrics(ts, ts, clock_scale_to_s=1.0)
        assert all(math.isnan(v) for v in m.values())

    def test_microsecond_clock_scale(self):
        ts = np.arange(100, dtype=np.float64) / 500.0   # 500 Hz
        clock_us = ts * 1e6                               # same timestamps in µs
        m = clock_validation_metrics(ts, clock_us, clock_scale_to_s=1e-6)
        assert math.isclose(m["lsl_rate_hz"], 500.0, rel_tol=1e-4)
        assert abs(m["median_dt_error_ms"]) < 1e-6
