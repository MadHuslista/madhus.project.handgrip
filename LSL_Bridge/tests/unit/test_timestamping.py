"""
Unit tests for lsl_bridge.core.timestamping.

Both resolvers are pure state machines with no I/O, tested with synthetic
``ParsedTargetSample`` objects.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from lsl_bridge.core.timestamping import SampleTimeResolver, TargetTimestampResolver
from lsl_bridge.types import ParsedTargetSample
from omegaconf import OmegaConf

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample(seq: int = 0, device_clock_us: int = 0, lsl_ts: float = 0.0) -> ParsedTargetSample:
    return ParsedTargetSample(
        sequence=seq,
        device_clock_us=device_clock_us,
        target_raw_count=0.0,
        target_current_units=0.0,
        target_status=0,
        lsl_timestamp=lsl_ts,
        host_unix_time_ns=0,
        raw_line="",
    )


def _cfg_processing(source: str = "device_clock_us") -> object:
    return OmegaConf.create({"processing": {"timestamp_source": source}})


def _cfg_timestamping(
    policy: str = "device_clock_anchor",
    max_gap_s: float = 1.0,
    reset_on_nonmonotonic: bool = True,
    max_anchor_drift_s: float = 0.0,
    monotonic_epsilon_s: float = 1e-9,
) -> object:
    return OmegaConf.create(
        {
            "target_timestamping": {
                "policy": policy,
                "max_gap_s": max_gap_s,
                "reset_on_nonmonotonic": reset_on_nonmonotonic,
                "max_anchor_drift_s": max_anchor_drift_s,
                "monotonic_epsilon_s": monotonic_epsilon_s,
            }
        }
    )


# ---------------------------------------------------------------------------
# SampleTimeResolver
# ---------------------------------------------------------------------------


class TestSampleTimeResolver:
    def test_lsl_source_returns_lsl_timestamp(self):
        r = SampleTimeResolver(_cfg_processing("lsl"))
        s = _sample(lsl_ts=42.5)
        assert r.resolve(s) == 42.5

    def test_device_clock_first_sample_is_zero(self):
        r = SampleTimeResolver(_cfg_processing("device_clock_us"))
        s = _sample(device_clock_us=1_000_000)
        assert r.resolve(s) == 0.0

    def test_device_clock_accumulates_delta(self):
        r = SampleTimeResolver(_cfg_processing("device_clock_us"))
        r.resolve(_sample(device_clock_us=1_000_000))
        t = r.resolve(_sample(device_clock_us=1_010_000))  # +10 ms
        assert abs(t - 0.01) < 1e-9

    def test_device_clock_multiple_steps(self):
        r = SampleTimeResolver(_cfg_processing("device_clock_us"))
        r.resolve(_sample(device_clock_us=0))
        r.resolve(_sample(device_clock_us=10_000))  # +10 ms
        t = r.resolve(_sample(device_clock_us=20_000))  # +20 ms total
        assert abs(t - 0.02) < 1e-9

    def test_negative_delta_does_not_go_backwards(self):
        """Non-monotonic device clock should not decrease accumulated time."""
        r = SampleTimeResolver(_cfg_processing("device_clock_us"))
        r.resolve(_sample(device_clock_us=1_000_000))
        t_before = r.resolve(_sample(device_clock_us=1_010_000))
        t_after = r.resolve(_sample(device_clock_us=1_000_000))  # wrap-back
        assert t_after >= t_before  # time must not go backwards

    def test_unsupported_source_raises(self):
        r = SampleTimeResolver(_cfg_processing("invalid_source"))
        with pytest.raises(ValueError, match="Unsupported"):
            r.resolve(_sample())


# ---------------------------------------------------------------------------
# TargetTimestampResolver
# ---------------------------------------------------------------------------


class TestTargetTimestampResolver:
    def _make(self, **kwargs) -> tuple[TargetTimestampResolver, MagicMock]:
        events = MagicMock()
        resolver = TargetTimestampResolver(_cfg_timestamping(**kwargs), events)
        return resolver, events

    # host_receive policy

    def test_host_receive_returns_arrival_time(self):
        r, _ = self._make(policy="host_receive")
        s = _sample(device_clock_us=1_000)
        assert r.resolve(s, arrival_lsl_time=5.0) == 5.0

    # device_clock_anchor policy — initial anchor

    def test_first_sample_returns_arrival_time(self):
        r, events = self._make(policy="device_clock_anchor")
        s = _sample(device_clock_us=500_000)
        result = r.resolve(s, arrival_lsl_time=10.0)
        assert result == 10.0
        events.emit.assert_called_once()
        assert events.emit.call_args[0][0] == "target_timestamp_anchor_reset"

    def test_anchor_advances_by_device_clock_delta(self):
        r, _ = self._make(policy="device_clock_anchor")
        r.resolve(_sample(device_clock_us=0), arrival_lsl_time=100.0)  # anchor at t=100
        ts = r.resolve(_sample(device_clock_us=10_000), arrival_lsl_time=100.011)
        assert abs(ts - 100.01) < 1e-6  # 10_000 µs = 0.01 s

    def test_anchor_reanchors_when_device_clock_drifts_from_host_time(self):
        r, events = self._make(policy="device_clock_anchor", max_anchor_drift_s=0.05)
        r.resolve(_sample(device_clock_us=0), arrival_lsl_time=100.0)
        events.emit.reset_mock()

        # Device clock predicts 100.010 s, but the sample arrived at 100.080 s.
        # Without the drift guard, the live XY plot would pair this fresh target
        # sample with a reference value from ~70 ms in the past.
        ts = r.resolve(_sample(device_clock_us=10_000), arrival_lsl_time=100.080)

        assert abs(ts - 100.080) < 1e-9
        events.emit.assert_called_once()
        assert events.emit.call_args[1]["reason"] == "device_clock_anchor_drift"
        assert abs(events.emit.call_args[1]["drift_s"] - 0.070) < 1e-9

    def test_host_receive_policy_never_moves_timestamps_backwards(self):
        r, _ = self._make(policy="host_receive", monotonic_epsilon_s=1e-6)
        assert r.resolve(_sample(device_clock_us=0), arrival_lsl_time=10.0) == 10.0
        ts = r.resolve(_sample(device_clock_us=10_000), arrival_lsl_time=9.5)
        assert abs(ts - 10.000001) < 1e-9

    # Nonmonotonic reset

    def test_nonmonotonic_clock_triggers_reset(self):
        r, events = self._make(policy="device_clock_anchor", reset_on_nonmonotonic=True)
        r.resolve(_sample(device_clock_us=100_000), arrival_lsl_time=1.0)
        events.emit.reset_mock()
        result = r.resolve(_sample(device_clock_us=50_000), arrival_lsl_time=1.5)
        assert result == 1.5  # re-anchored to arrival
        events.emit.assert_called_once()

    def test_nonmonotonic_no_reset_when_disabled(self):
        r, events = self._make(
            policy="device_clock_anchor",
            reset_on_nonmonotonic=False,
        )
        r.resolve(_sample(device_clock_us=100_000), arrival_lsl_time=1.0)
        events.emit.reset_mock()
        # Should NOT reset — just continue with negative delta ignored
        r.resolve(_sample(device_clock_us=50_000), arrival_lsl_time=1.5)
        events.emit.assert_not_called()

    # Gap reset

    def test_large_gap_triggers_reset(self):
        r, events = self._make(policy="device_clock_anchor", max_gap_s=0.5)
        r.resolve(_sample(device_clock_us=0), arrival_lsl_time=1.0)
        events.emit.reset_mock()
        # 2-second gap in device clock
        result = r.resolve(_sample(device_clock_us=2_000_000), arrival_lsl_time=3.0)
        assert result == 3.0  # re-anchored
        events.emit.assert_called_once()
        call_kwargs = events.emit.call_args[1]
        assert call_kwargs.get("reason") == "device_clock_gap"

    # Unsupported policy

    def test_unsupported_policy_raises(self):
        r, _ = self._make(policy="unsupported_policy")
        with pytest.raises(ValueError, match="Only target_timestamping.policy"):
            r.resolve(_sample(), arrival_lsl_time=0.0)
