"""Unit tests for lsl_bridge.core.filter.

All tests are pure — no I/O, no mocking required.  The filter classes
operate entirely on float inputs and outputs, making them trivial to test
in isolation.
"""

from __future__ import annotations

import math

import pytest

from lsl_bridge.core.filter import (
    DriftCorrector,
    FilterPipeline,
    FirstOrderLowPass,
    IdentityProcessor,
    SecondOrderBiquadLowPass,
    _build_filter_node,
)


# ---------------------------------------------------------------------------
# SecondOrderBiquadLowPass
# ---------------------------------------------------------------------------


class TestSecondOrderBiquadLowPass:
    def test_initialises_on_first_sample(self):
        f = SecondOrderBiquadLowPass(cutoff_hz=10.0, sample_rate_hz=100.0)
        y = f.process(5.0, 0.0)
        assert y == 5.0

    def test_dc_passthrough(self):
        """A constant DC signal should pass through unchanged once settled."""
        f = SecondOrderBiquadLowPass(cutoff_hz=10.0, sample_rate_hz=100.0)
        dt = 0.01
        y = 0.0
        for i in range(500):
            y = f.process(1.0, i * dt)
        assert abs(y - 1.0) < 1e-6

    def test_attenuates_high_frequency(self):
        """A signal well above the cutoff should be strongly attenuated."""
        f = SecondOrderBiquadLowPass(cutoff_hz=5.0, sample_rate_hz=1000.0)
        dt = 1.0 / 1000.0
        outputs = []
        for i in range(2000):
            t = i * dt
            value = math.sin(2 * math.pi * 200.0 * t)  # 200 Hz >> 5 Hz cutoff
            outputs.append(f.process(value, t))
        rms = math.sqrt(sum(o**2 for o in outputs[-500:]) / 500)
        assert rms < 0.05  # should be heavily attenuated

    def test_reset_on_large_gap(self):
        f = SecondOrderBiquadLowPass(cutoff_hz=10.0, sample_rate_hz=100.0, reset_on_gap_s=0.5)
        f.process(3.0, 0.0)
        y = f.process(7.0, 2.0)  # 2s gap > reset_on_gap_s=0.5
        assert y == 7.0

    def test_rejects_cutoff_above_nyquist(self):
        with pytest.raises(ValueError, match="Nyquist"):
            SecondOrderBiquadLowPass(cutoff_hz=60.0, sample_rate_hz=100.0)

    def test_rejects_nonpositive_cutoff(self):
        with pytest.raises(ValueError, match="cutoff_hz"):
            SecondOrderBiquadLowPass(cutoff_hz=0.0, sample_rate_hz=100.0)

    def test_rejects_nonpositive_sample_rate(self):
        with pytest.raises(ValueError, match="sample_rate_hz"):
            SecondOrderBiquadLowPass(cutoff_hz=10.0, sample_rate_hz=0.0)

    def test_rejects_nonpositive_q(self):
        with pytest.raises(ValueError, match="q must be"):
            SecondOrderBiquadLowPass(cutoff_hz=10.0, sample_rate_hz=100.0, q=0.0)


# ---------------------------------------------------------------------------
# FirstOrderLowPass
# ---------------------------------------------------------------------------


class TestFirstOrderLowPass:
    def test_initialises_on_first_sample(self):
        f = FirstOrderLowPass(cutoff_hz=5.0)
        y = f.process(3.0, 0.0)
        assert y == 3.0

    def test_dc_passthrough(self):
        f = FirstOrderLowPass(cutoff_hz=10.0)
        dt = 0.01
        y = 0.0
        for i in range(500):
            y = f.process(1.0, i * dt)
        assert abs(y - 1.0) < 1e-4

    def test_reset_on_large_gap(self):
        f = FirstOrderLowPass(cutoff_hz=10.0, reset_on_gap_s=0.5)
        f.process(1.0, 0.0)
        y = f.process(9.0, 2.0)  # large gap
        assert y == 9.0

    def test_rejects_nonpositive_cutoff(self):
        with pytest.raises(ValueError, match="cutoff_hz"):
            FirstOrderLowPass(cutoff_hz=-1.0)


# ---------------------------------------------------------------------------
# DriftCorrector
# ---------------------------------------------------------------------------


class TestDriftCorrector:
    def test_initialises_to_zero(self):
        dc = DriftCorrector()
        y = dc.process(5.0, 0.0)
        assert y == 0.0  # baseline set to first value; corrected = 0

    def test_removes_dc_offset(self):
        """After warmup the corrected output should be near zero for a DC signal."""
        dc = DriftCorrector(baseline_cutoff_hz=1.0, warmup_samples=5)
        dt = 0.01
        outputs = []
        for i in range(200):
            outputs.append(dc.process(10.0, i * dt))
        assert abs(outputs[-1]) < 0.1

    def test_reset_on_large_gap(self):
        dc = DriftCorrector(reset_on_gap_s=0.5)
        dc.process(5.0, 0.0)
        y = dc.process(5.0, 2.0)  # large gap resets
        assert y == 0.0

    def test_rejects_nonpositive_baseline_cutoff(self):
        with pytest.raises(ValueError, match="baseline_cutoff_hz"):
            DriftCorrector(baseline_cutoff_hz=0.0)


# ---------------------------------------------------------------------------
# IdentityProcessor
# ---------------------------------------------------------------------------


class TestIdentityProcessor:
    def test_passthrough(self):
        ip = IdentityProcessor()
        assert ip.process(42.0, 1.0) == 42.0
        assert ip.process(-3.14, 0.0) == -3.14


# ---------------------------------------------------------------------------
# FilterPipeline
# ---------------------------------------------------------------------------


class TestFilterPipeline:
    def test_empty_pipeline_is_identity(self):
        pipe = FilterPipeline([])
        assert pipe.process(7.0, 0.0) == 7.0

    def test_single_filter(self):
        pipe = FilterPipeline([IdentityProcessor()])
        assert pipe.process(5.0, 0.0) == 5.0

    def test_chained_filters_apply_in_order(self):
        """Verify pipeline applies filters left-to-right.

        Use a 1-pole filter initialised with 0 so the first call returns 0,
        then chain an identity to verify order is preserved.
        """
        f1 = FirstOrderLowPass(cutoff_hz=10.0)
        f2 = IdentityProcessor()
        pipe = FilterPipeline([f1, f2])
        y = pipe.process(1.0, 0.0)
        assert y == 1.0  # first call initialises f1 to input value

    def test_filters_property_returns_copy(self):
        f = IdentityProcessor()
        pipe = FilterPipeline([f])
        lst = pipe.filters
        lst.clear()
        assert len(pipe.filters) == 1  # original unaffected


# ---------------------------------------------------------------------------
# _build_filter_node factory
# ---------------------------------------------------------------------------


class TestBuildFilterNode:
    def _cfg(self, d: dict):
        from omegaconf import OmegaConf
        return OmegaConf.create(d)

    def test_builds_butterworth(self):
        cfg = self._cfg({"type": "butterworth_lowpass_2nd", "cutoff_hz": 10.0, "sample_rate_hz": 100.0})
        node = _build_filter_node(cfg)
        assert isinstance(node, SecondOrderBiquadLowPass)

    def test_builds_biquad_alias(self):
        cfg = self._cfg({"type": "biquad_lowpass", "cutoff_hz": 10.0, "sample_rate_hz": 100.0})
        node = _build_filter_node(cfg)
        assert isinstance(node, SecondOrderBiquadLowPass)

    def test_builds_lowpass_1pole(self):
        cfg = self._cfg({"type": "lowpass_1pole", "cutoff_hz": 5.0})
        node = _build_filter_node(cfg)
        assert isinstance(node, FirstOrderLowPass)

    def test_builds_drift_corrector(self):
        cfg = self._cfg({"type": "drift_corrector"})
        node = _build_filter_node(cfg)
        assert isinstance(node, DriftCorrector)

    def test_builds_identity(self):
        cfg = self._cfg({"type": "identity"})
        node = _build_filter_node(cfg)
        assert isinstance(node, IdentityProcessor)

    def test_raises_on_unknown_type(self):
        cfg = self._cfg({"type": "nonexistent_filter"})
        with pytest.raises(ValueError, match="Unsupported filter type"):
            _build_filter_node(cfg)
