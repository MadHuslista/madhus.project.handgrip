"""
Integration tests for lsl_bridge.io.csv_sinks.

Uses pytest's ``tmp_path`` fixture to write real CSV files without
requiring any LSL or serial runtime.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest
from lsl_bridge.io.csv_sinks import ReferenceCsvSink, TargetCsvSink, apply_timestamp_suffix
from lsl_bridge.types import ParsedTargetSample, ReferenceSample

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _target_sample(seq: int = 0) -> ParsedTargetSample:
    return ParsedTargetSample(
        sequence=seq,
        device_clock_us=seq * 10_000,
        target_raw_count=float(seq),
        target_current_units=float(seq) * 0.1,
        target_status=0,
        lsl_timestamp=float(seq) * 0.01,
        host_unix_time_ns=seq * 10_000_000,
        raw_line=f"D2,{seq},{seq * 10_000},{float(seq)},{float(seq) * 0.1},0",
    )


def _reference_sample(seq: int = 0) -> ReferenceSample:
    return ReferenceSample(
        sequence=seq,
        mode="continuous",
        signal_key="reference_force_N",
        reference_force_N=float(seq) * 0.5,
        reference_clock_s=float(seq) * 0.002,
        host_lsl_ts=float(seq) * 0.002,
        host_unix_ts=float(seq) * 0.002,
        received_lsl_ts=float(seq) * 0.002,
        clock_source="rs485_hw",
        unit_label="N",
        status=0,
        timestamp_source="host_lsl_ts",
        configured_frequency_hz=500.0,
        session_id=None,
    )


# ---------------------------------------------------------------------------
# TargetCsvSink
# ---------------------------------------------------------------------------


class TestTargetCsvSink:
    def test_creates_file_with_header(self, tmp_path: Path):
        path = tmp_path / "target.csv"
        sink = TargetCsvSink(path, write_mode="overwrite", flush_every_n_rows=1)
        sink.close()
        assert path.exists()
        rows = list(csv.DictReader(path.open()))
        assert len(rows) == 0  # only header written

    def test_header_matches_fieldnames(self, tmp_path: Path):
        path = tmp_path / "target.csv"
        sink = TargetCsvSink(path, write_mode="overwrite", flush_every_n_rows=1)
        sink.close()
        with path.open() as f:
            header = f.readline().strip().split(",")
        assert header == TargetCsvSink.FIELDNAMES

    def test_writes_sample_row(self, tmp_path: Path):
        path = tmp_path / "target.csv"
        sink = TargetCsvSink(path, write_mode="overwrite", flush_every_n_rows=1)
        sample = _target_sample(seq=7)
        sink.write(sample, filtered_units=0.5)
        sink.close()
        rows = list(csv.DictReader(path.open()))
        assert len(rows) == 1
        assert int(rows[0]["seq"]) == 7
        assert float(rows[0]["target_filtered_units"]) == 0.5

    def test_writes_multiple_rows(self, tmp_path: Path):
        path = tmp_path / "target.csv"
        sink = TargetCsvSink(path, write_mode="overwrite", flush_every_n_rows=1)
        for i in range(10):
            sink.write(_target_sample(i), filtered_units=float(i))
        sink.close()
        rows = list(csv.DictReader(path.open()))
        assert len(rows) == 10
        assert [int(r["seq"]) for r in rows] == list(range(10))

    def test_append_mode_preserves_existing_data(self, tmp_path: Path):
        path = tmp_path / "target.csv"
        # First write — 3 rows
        sink = TargetCsvSink(path, write_mode="overwrite", flush_every_n_rows=1)
        for i in range(3):
            sink.write(_target_sample(i), 0.0)
        sink.close()
        # Append — 2 more rows
        sink = TargetCsvSink(path, write_mode="append", flush_every_n_rows=1)
        for i in range(3, 5):
            sink.write(_target_sample(i), 0.0)
        sink.close()
        rows = list(csv.DictReader(path.open()))
        assert len(rows) == 5

    def test_creates_parent_directories(self, tmp_path: Path):
        path = tmp_path / "deep" / "nested" / "target.csv"
        sink = TargetCsvSink(path, write_mode="overwrite", flush_every_n_rows=1)
        sink.close()
        assert path.exists()

    def test_arrival_lsl_time_written_when_provided(self, tmp_path: Path):
        path = tmp_path / "target.csv"
        sink = TargetCsvSink(path, write_mode="overwrite", flush_every_n_rows=1)
        sink.write(_target_sample(seq=1), filtered_units=0.0, arrival_lsl_time_s=12.345678901)
        sink.close()
        rows = list(csv.DictReader(path.open()))
        assert float(rows[0]["arrival_lsl_time_s"]) == pytest.approx(12.345678901, abs=1e-9)

    def test_arrival_lsl_time_defaults_to_empty(self, tmp_path: Path):
        path = tmp_path / "target.csv"
        sink = TargetCsvSink(path, write_mode="overwrite", flush_every_n_rows=1)
        sink.write(_target_sample(seq=1), filtered_units=0.0)
        sink.close()
        rows = list(csv.DictReader(path.open()))
        assert rows[0]["arrival_lsl_time_s"] == ""

    def test_flush_interval_respected(self, tmp_path: Path):
        """Sink should not raise on high flush_every_n_rows values."""
        path = tmp_path / "target.csv"
        sink = TargetCsvSink(path, write_mode="overwrite", flush_every_n_rows=100)
        for i in range(50):
            sink.write(_target_sample(i), 0.0)
        sink.close()
        rows = list(csv.DictReader(path.open()))
        assert len(rows) == 50


# ---------------------------------------------------------------------------
# ReferenceCsvSink
# ---------------------------------------------------------------------------


class TestReferenceCsvSink:
    def test_creates_file_with_header(self, tmp_path: Path):
        path = tmp_path / "reference.csv"
        sink = ReferenceCsvSink(path, write_mode="overwrite", flush_every_n_rows=1)
        sink.close()
        assert path.exists()
        with path.open() as f:
            header = f.readline().strip().split(",")
        assert header == ReferenceCsvSink.FIELDNAMES

    def test_writes_sample_row(self, tmp_path: Path):
        path = tmp_path / "reference.csv"
        sink = ReferenceCsvSink(path, write_mode="overwrite", flush_every_n_rows=1)
        sample = _reference_sample(seq=3)
        sink.write(sample, lsl_timestamp_s=0.006)
        sink.close()
        rows = list(csv.DictReader(path.open()))
        assert len(rows) == 1
        assert int(rows[0]["seq"]) == 3
        assert float(rows[0]["lsl_timestamp_s"]) == pytest.approx(0.006, abs=1e-9)

    def test_nan_frequency_written_as_empty_string(self, tmp_path: Path):
        path = tmp_path / "reference.csv"
        sink = ReferenceCsvSink(path, write_mode="overwrite", flush_every_n_rows=1)
        # Build the sample directly with nan frequency (slots=True means no __dict__)
        sample = ReferenceSample(
            sequence=0,
            mode="continuous",
            signal_key="reference_force_N",
            reference_force_N=0.0,
            reference_clock_s=0.0,
            host_lsl_ts=0.0,
            host_unix_ts=0.0,
            received_lsl_ts=0.0,
            clock_source="rs485_hw",
            unit_label="N",
            status=0,
            timestamp_source="host_lsl_ts",
            configured_frequency_hz=math.nan,
        )
        sink.write(sample, 0.0)
        sink.close()
        rows = list(csv.DictReader(path.open()))
        assert rows[0]["configured_frequency_hz"] == ""

    def test_writes_multiple_rows(self, tmp_path: Path):
        path = tmp_path / "reference.csv"
        sink = ReferenceCsvSink(path, write_mode="overwrite", flush_every_n_rows=5)
        for i in range(20):
            sink.write(_reference_sample(i), float(i) * 0.002)
        sink.close()
        rows = list(csv.DictReader(path.open()))
        assert len(rows) == 20


# ---------------------------------------------------------------------------
# apply_timestamp_suffix
# ---------------------------------------------------------------------------


class TestApplyTimestampSuffix:
    def test_inserts_suffix_before_extension(self, tmp_path: Path):
        path = tmp_path / "target_handgrip_samples_v2.csv"
        result = apply_timestamp_suffix(path, "20260612_143022")
        assert result == tmp_path / "target_handgrip_samples_v2_20260612_143022.csv"


# ---------------------------------------------------------------------------
# write_mode="timestamped"
# ---------------------------------------------------------------------------


class TestTimestampedWriteMode:
    def test_timestamped_mode_writes_fresh_header(self, tmp_path: Path):
        path = tmp_path / "target_20260612_143022.csv"
        path.write_text("stale content\n")
        sink = TargetCsvSink(path, write_mode="timestamped", flush_every_n_rows=1)
        sink.close()
        with path.open() as f:
            header = f.readline().strip().split(",")
        assert header == TargetCsvSink.FIELDNAMES

    def test_invalid_write_mode_raises(self, tmp_path: Path):
        path = tmp_path / "target.csv"
        with pytest.raises(ValueError):
            TargetCsvSink(path, write_mode="bogus", flush_every_n_rows=1)
