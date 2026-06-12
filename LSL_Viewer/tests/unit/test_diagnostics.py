"""Unit tests for diagnostics — XY staircase investigation recorder."""

from __future__ import annotations

import csv
import json
import math

import numpy as np
from omegaconf import OmegaConf

from lsl_viewer.diagnostics import (
    DiagnosticsRecorder,
    compute_tick_metrics,
    count_target_newer_than_reference_tail,
    select_new_rows,
)
from lsl_viewer.types import DualWindow, ReferenceWindow, TargetWindow, ViewerState


def _make_cfg(tmp_path, **overrides):
    diag = {
        "enabled": True,
        "output_dir": str(tmp_path / "diag"),
        "record_metrics": True,
        "record_raw_samples": True,
    }
    diag.update(overrides)
    return OmegaConf.create({"diagnostics": diag})


def _target(ts, raw=None):
    ts = np.asarray(ts, dtype=np.float64)
    raw = np.asarray(raw, dtype=np.float64) if raw is not None else np.zeros_like(ts)
    return TargetWindow(
        timestamps_s=ts,
        device_clock_us=np.arange(ts.size, dtype=np.float64),
        raw=raw,
        filtered=raw,
    )


def _reference(ts, raw=None):
    ts = np.asarray(ts, dtype=np.float64)
    raw = np.asarray(raw, dtype=np.float64) if raw is not None else np.zeros_like(ts)
    return ReferenceWindow(timestamps_s=ts, rs485_clock=ts.copy(), raw=raw)


class TestSelectNewRows:
    def test_all_rows_selected_when_no_history(self):
        mask = select_new_rows(np.array([1.0, 2.0, 3.0]), float("nan"))
        assert mask.tolist() == [True, True, True]

    def test_only_strictly_newer_rows_selected(self):
        mask = select_new_rows(np.array([1.0, 2.0, 3.0]), 2.0)
        assert mask.tolist() == [False, False, True]

    def test_nonfinite_rows_excluded(self):
        mask = select_new_rows(np.array([float("nan"), 2.0, float("inf")]), 1.0)
        assert mask.tolist() == [False, True, False]

    def test_empty_input(self):
        mask = select_new_rows(np.array([]), 1.0)
        assert mask.size == 0


class TestCountTargetNewerThanReferenceTail:
    def test_zero_when_windows_missing(self):
        assert count_target_newer_than_reference_tail(None, None, 0.0) == 0
        assert count_target_newer_than_reference_tail(_target([1.0]), None, 0.0) == 0

    def test_counts_target_samples_beyond_reference_tail(self):
        target = _target([1.0, 2.0, 3.0, 4.0])
        reference = _reference([0.0, 2.5])
        assert count_target_newer_than_reference_tail(target, reference, 0.0) == 2

    def test_shift_moves_the_reference_tail(self):
        target = _target([1.0, 2.0, 3.0, 4.0])
        reference = _reference([0.0, 2.5])
        assert count_target_newer_than_reference_tail(target, reference, 1.0) == 1
        assert count_target_newer_than_reference_tail(target, reference, -1.0) == 3


class TestComputeTickMetrics:
    def test_metrics_record_is_json_round_trippable(self):
        window = DualWindow(target=_target([1.0, 2.0]), reference=_reference([0.5, 1.5]))
        state = ViewerState()
        state.xy_pair_count = 2
        state.xy_t_min_s = 1.0
        state.xy_t_max_s = 2.0
        state.xy_alignment_mode = "raw_lsl"
        record = compute_tick_metrics(
            window,
            state,
            tick_index=7,
            wall_time_s=100.0,
            monotonic_s=50.0,
            lsl_local_clock_s=2.5,
            target_new_samples=3,
            reference_new_samples=11,
        )
        parsed = json.loads(json.dumps(record))
        assert parsed["tick_index"] == 7
        assert parsed["target_tail_s"] == 2.0
        assert parsed["reference_tail_s"] == 1.5
        assert parsed["tail_delta_s"] == 0.5
        assert parsed["target_new_samples"] == 3
        assert parsed["reference_new_samples"] == 11
        assert parsed["alignment_mode"] == "raw_lsl"
        assert parsed["xy_pair_count"] == 2
        assert parsed["target_dropped_newer_than_ref_tail"] == 1

    def test_nonfinite_values_serialized_as_null(self):
        window = DualWindow(target=None, reference=None)
        record = compute_tick_metrics(
            window,
            ViewerState(),
            tick_index=0,
            wall_time_s=0.0,
            monotonic_s=0.0,
            lsl_local_clock_s=None,
            target_new_samples=0,
            reference_new_samples=0,
        )
        parsed = json.loads(json.dumps(record))
        assert parsed["target_tail_s"] is None
        assert parsed["reference_tail_s"] is None
        assert parsed["lsl_local_clock_s"] is None
        assert parsed["target_window_n"] == 0


class TestDiagnosticsRecorder:
    def test_disabled_recorder_creates_no_files(self, tmp_path):
        cfg = _make_cfg(tmp_path, enabled=False)
        recorder = DiagnosticsRecorder(cfg)
        recorder.record_tick({"tick_index": 0})
        recorder.record_window(DualWindow(target=_target([1.0]), reference=None))
        recorder.close()
        assert not (tmp_path / "diag").exists()

    def test_enabled_recorder_writes_session_files(self, tmp_path):
        recorder = DiagnosticsRecorder(_make_cfg(tmp_path))
        recorder.record_tick({"tick_index": 0, "shift_s": 0.0})
        recorder.record_window(
            DualWindow(target=_target([1.0, 2.0], raw=[10.0, 20.0]), reference=_reference([0.5], raw=[5.0]))
        )
        recorder.close()
        session = recorder.session_dir
        assert session is not None and session.parent == tmp_path / "diag"
        lines = (session / "metrics.jsonl").read_text().splitlines()
        assert json.loads(lines[0])["tick_index"] == 0
        with (session / "target_samples.csv").open() as fh:
            rows = list(csv.reader(fh))
        assert rows[0] == ["lsl_timestamp_s", "device_clock_us", "raw", "filtered"]
        assert len(rows) == 3
        with (session / "reference_samples.csv").open() as fh:
            rows = list(csv.reader(fh))
        assert rows[0] == ["lsl_timestamp_s", "rs485_clock_s", "raw"]
        assert len(rows) == 2

    def test_overlapping_windows_are_deduplicated(self, tmp_path):
        recorder = DiagnosticsRecorder(_make_cfg(tmp_path))
        recorder.record_window(DualWindow(target=_target([1.0, 2.0]), reference=None))
        recorder.record_window(DualWindow(target=_target([1.0, 2.0, 3.0]), reference=None))
        recorder.record_window(DualWindow(target=_target([2.0, 3.0]), reference=None))
        recorder.close()
        with (recorder.session_dir / "target_samples.csv").open() as fh:
            rows = list(csv.reader(fh))
        timestamps = [float(r[0]) for r in rows[1:]]
        assert timestamps == [1.0, 2.0, 3.0]

    def test_metrics_lines_are_individually_parseable(self, tmp_path):
        recorder = DiagnosticsRecorder(_make_cfg(tmp_path, record_raw_samples=False))
        for i in range(3):
            recorder.record_tick({"tick_index": i, "value": float(i)})
        recorder.close()
        lines = (recorder.session_dir / "metrics.jsonl").read_text().splitlines()
        assert [json.loads(line)["tick_index"] for line in lines] == [0, 1, 2]
        assert not (recorder.session_dir / "target_samples.csv").exists()

    def test_io_failure_disables_recorder(self, tmp_path, monkeypatch):
        recorder = DiagnosticsRecorder(_make_cfg(tmp_path))
        recorder.record_tick({"tick_index": 0})

        def _boom(*args, **kwargs):
            raise OSError("disk gone")

        monkeypatch.setattr(recorder._metrics_fh, "write", _boom)
        recorder.record_tick({"tick_index": 1})
        assert recorder.enabled is False
        # Subsequent calls are inert, not raising
        recorder.record_tick({"tick_index": 2})
        recorder.record_window(DualWindow(target=_target([1.0]), reference=None))

    def test_nan_timestamps_never_become_high_water_mark(self, tmp_path):
        recorder = DiagnosticsRecorder(_make_cfg(tmp_path))
        recorder.record_window(DualWindow(target=_target([1.0, float("nan")]), reference=None))
        recorder.record_window(DualWindow(target=_target([2.0]), reference=None))
        recorder.close()
        with (recorder.session_dir / "target_samples.csv").open() as fh:
            rows = list(csv.reader(fh))
        timestamps = [float(r[0]) for r in rows[1:]]
        assert timestamps == [1.0, 2.0]
        assert all(math.isfinite(t) for t in timestamps)
