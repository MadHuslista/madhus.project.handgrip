"""Unit tests for rs485_gui.core.sampling."""
from __future__ import annotations

import threading

import pytest

from rs485_gui.core.sampling import SamplingStats, downsample_points_for_render


class TestSamplingStats:
    def test_empty_snapshot(self):
        stats = SamplingStats()
        mean, std, count, received, dropped = stats.snapshot()
        assert mean is None
        assert std is None
        assert count == 0

    def test_single_interval(self):
        stats = SamplingStats()
        stats.record_processed_frame(0.0)
        stats.record_processed_frame(0.002)  # 500 Hz
        mean, std, count, _, _ = stats.snapshot()
        assert mean == pytest.approx(500.0, rel=0.01)

    def test_outlier_rejection(self):
        stats = SamplingStats()
        # Populate 20 normal samples at 500 Hz (dt=0.002)
        t = 0.0
        for _ in range(21):
            stats.record_processed_frame(t)
            t += 0.002
        # Add one extreme outlier
        stats.window_dts_s.append(10.0)
        mean, _, count, _, _ = stats.snapshot(
            outlier_low_ratio=0.25,
            outlier_high_ratio=4.0,
            outlier_min_samples=10,
        )
        assert mean == pytest.approx(500.0, rel=0.05)

    def test_reset_all_clears_counters(self):
        stats = SamplingStats()
        stats.record_received_samples(100)
        stats.add_dropped_samples(10)
        stats.reset_all(128)
        _, _, _, received, dropped = stats.snapshot()
        assert received == 0
        assert dropped == 0

    def test_thread_safety(self):
        stats = SamplingStats()
        errors = []

        def writer():
            try:
                for i in range(500):
                    stats.record_processed_frame(float(i) * 0.002)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(100):
                    stats.snapshot()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(3)] + \
                  [threading.Thread(target=reader) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == [], f'Thread safety errors: {errors}'


class TestDownsamplePointsForRender:
    def test_empty_returns_empty(self):
        assert downsample_points_for_render([], factor=2, max_points=100) == []

    def test_factor_one_no_change(self):
        pts = [(float(i), float(i)) for i in range(10)]
        result = downsample_points_for_render(pts, factor=1, max_points=0)
        assert result == pts

    def test_factor_two_halves_length(self):
        pts = [(float(i), float(i)) for i in range(100)]
        result = downsample_points_for_render(pts, factor=2, max_points=0)
        # last point always preserved
        assert result[-1] == pts[-1]
        assert len(result) <= 51

    def test_max_points_caps_output(self):
        pts = [(float(i), float(i)) for i in range(1000)]
        result = downsample_points_for_render(pts, factor=1, max_points=50)
        assert len(result) <= 51
        assert result[-1] == pts[-1]

    def test_last_point_always_preserved(self):
        pts = [(float(i), float(i) * 2) for i in range(100)]
        for factor in (1, 2, 5, 10):
            result = downsample_points_for_render(pts, factor=factor, max_points=10)
            assert result[-1] == pts[-1], f'Last point lost at factor={factor}'
