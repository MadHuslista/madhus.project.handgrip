"""Unit tests for the reference publisher's IPC age accumulators."""

from __future__ import annotations

import math

import pytest
from omegaconf import OmegaConf

from lsl_bridge.publishers.reference import RS485IpcReferencePublisher
from lsl_bridge.types import ReferenceSample


def _make_publisher() -> RS485IpcReferencePublisher:
    cfg = OmegaConf.create(
        {
            "rs485_ipc": {"enabled": False, "log_status_every_s": 5.0},
            "streams": {"reference": {"enabled": False}},
        }
    )
    return RS485IpcReferencePublisher(cfg, outlet=None, sink=None, events=None)


def _sample(host_lsl_ts: float, received_lsl_ts: float) -> ReferenceSample:
    return ReferenceSample(
        sequence=0,
        mode="continuous",
        signal_key="reference_force_N",
        reference_force_N=0.0,
        reference_clock_s=0.0,
        host_lsl_ts=host_lsl_ts,
        host_unix_ts=0.0,
        received_lsl_ts=received_lsl_ts,
        clock_source="rs485_hw",
        unit_label="N",
        status=0,
        timestamp_source="host_lsl_ts",
        configured_frequency_hz=500.0,
    )


class TestTrackSampleAge:
    def test_accumulates_min_mean_max(self):
        pub = _make_publisher()
        pub._track_sample_age(_sample(10.0, 10.010))
        pub._track_sample_age(_sample(11.0, 11.030))
        assert pub._age_count == 2
        assert pub._age_min_s == pytest.approx(0.010)
        assert pub._age_max_s == pytest.approx(0.030)
        assert pub._age_sum_s / pub._age_count == pytest.approx(0.020)

    def test_nonfinite_timestamps_ignored(self):
        pub = _make_publisher()
        pub._track_sample_age(_sample(math.nan, 10.0))
        pub._track_sample_age(_sample(10.0, math.inf))
        assert pub._age_count == 0

    def test_status_log_resets_accumulators(self, caplog):
        pub = _make_publisher()
        pub._track_sample_age(_sample(10.0, 10.010))
        pub._published_count = 1
        with caplog.at_level("INFO"):
            pub._log_status_if_due(_sample(10.0, 10.010), 10.0)
        assert "ipc_age_s[" in caplog.text
        assert pub._age_count == 0
        assert pub._age_min_s == math.inf
