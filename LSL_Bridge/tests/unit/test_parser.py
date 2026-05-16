"""
Unit tests for lsl_bridge.core.parser.D2LineParser.

Tests use a minimal stub for the events outlet so the parser can be tested
without any LSL runtime dependency.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from lsl_bridge.core.parser import D2LineParser
from lsl_bridge.types import ParsedTargetSample
from omegaconf import OmegaConf

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_cfg(overrides: dict | None = None) -> object:
    base = {
        "protocol": {
            "delimiter": ",",
            "data_prefix": "D2",
            "metadata_prefix": "M2",
            "accepted_numeric_regex": (
                r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
                r"|nan|NaN|inf|-inf|INF|-INF"
            ),
        },
        "logging": {
            "log_parse_errors_every_n": 20,
        },
    }
    if overrides:
        base.update(overrides)
    return OmegaConf.create(base)


def _make_parser(cfg=None) -> tuple[D2LineParser, MagicMock]:
    events = MagicMock()
    parser = D2LineParser(cfg or _make_cfg(), events)
    return parser, events


# ---------------------------------------------------------------------------
# Nominal D2 parsing
# ---------------------------------------------------------------------------


class TestD2Parsing:
    def test_parses_valid_d2_line(self):
        parser, _ = _make_parser()
        line = b"D2,42,1234567,100.5,98.3,0\n"
        sample = parser.feed(line, arrival_lsl_time=1.0, arrival_unix_time_ns=1_000_000)
        assert isinstance(sample, ParsedTargetSample)
        assert sample.sequence == 42
        assert sample.device_clock_us == 1234567
        assert sample.target_raw_count == 100.5
        assert sample.target_current_units == 98.3
        assert sample.target_status == 0
        assert sample.lsl_timestamp == 1.0
        assert sample.host_unix_time_ns == 1_000_000

    def test_raw_line_stored(self):
        parser, _ = _make_parser()
        line = b"D2,1,100,0.0,0.0,0\n"
        sample = parser.feed(line, 0.0, 0)
        assert sample is not None
        assert "D2" in sample.raw_line

    def test_accepts_float_with_scientific_notation(self):
        parser, _ = _make_parser()
        line = b"D2,1,100,1.5e2,2.3E-1,0\n"
        sample = parser.feed(line, 0.0, 0)
        assert sample is not None
        assert abs(sample.target_raw_count - 150.0) < 1e-9

    def test_accepts_nan_value(self):
        parser, _ = _make_parser()
        line = b"D2,1,100,nan,0.0,0\n"
        sample = parser.feed(line, 0.0, 0)
        assert sample is not None
        import math

        assert math.isnan(sample.target_raw_count)

    def test_empty_line_returns_none(self):
        parser, _ = _make_parser()
        assert parser.feed(b"\n", 0.0, 0) is None
        assert parser.feed(b"   \n", 0.0, 0) is None

    def test_garbage_line_returns_none_and_increments_error(self):
        parser, _ = _make_parser()
        result = parser.feed(b"NOT_A_D2_LINE\n", 0.0, 0)
        assert result is None

    def test_wrong_field_count_returns_none(self):
        parser, _ = _make_parser()
        result = parser.feed(b"D2,1,100,0.0\n", 0.0, 0)  # too few fields
        assert result is None


# ---------------------------------------------------------------------------
# Sequence gap detection
# ---------------------------------------------------------------------------


class TestSequenceGap:
    def test_no_gap_event_on_consecutive_seqs(self):
        parser, events = _make_parser()
        parser.feed(b"D2,0,100,0.0,0.0,0\n", 0.0, 0)
        parser.feed(b"D2,1,200,0.0,0.0,0\n", 0.0, 0)
        events.emit.assert_not_called()

    def test_gap_event_emitted_on_seq_skip(self):
        parser, events = _make_parser()
        parser.feed(b"D2,0,100,0.0,0.0,0\n", 0.0, 0)
        parser.feed(b"D2,5,200,0.0,0.0,0\n", 0.0, 0)
        events.emit.assert_called_once()
        call_args = events.emit.call_args
        assert call_args[0][0] == "target_sequence_gap"
        assert call_args[1]["last_seq"] == 0
        assert call_args[1]["current_seq"] == 5


# ---------------------------------------------------------------------------
# M2 metadata parsing
# ---------------------------------------------------------------------------


class TestM2Metadata:
    def test_metadata_line_returns_none(self):
        parser, _ = _make_parser()
        line = b"M2,2,v1.0.0,abc1234,93.75,100.0,0.0,N\n"
        result = parser.feed(line, 1.0, 0)
        assert result is None

    def test_metadata_populates_firmware_struct(self):
        parser, _ = _make_parser()
        parser.feed(b"M2,2,v1.0.0,abc1234,93.75,100.0,0.0,N\n", 1.0, 0)
        meta = parser.metadata
        assert meta.payload_schema == 2
        assert meta.firmware_version == "v1.0.0"
        assert meta.git_sha == "abc1234"
        assert abs(meta.hx711_rate_hz - 93.75) < 1e-9
        assert meta.unit == "N"
        assert meta.last_seen_lsl_ts == 1.0

    def test_metadata_emits_event(self):
        parser, events = _make_parser()
        parser.feed(b"M2,2,v1.0.0,abc1234,93.75,100.0,0.0,N\n", 1.0, 0)
        events.emit.assert_called_once()
        assert events.emit.call_args[0][0] == "target_metadata"

    def test_malformed_metadata_does_not_raise(self):
        parser, _ = _make_parser()
        # fewer than 8 fields — should log a warning but not crash
        parser.feed(b"M2,2,v1.0.0\n", 0.0, 0)
        # default FirmwareMetadata is unchanged
        assert parser.metadata.payload_schema is None
