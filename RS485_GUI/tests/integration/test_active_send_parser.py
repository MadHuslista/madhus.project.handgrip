"""Integration tests for the active-send binary frame parser."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from omegaconf import OmegaConf

from rs485_gui.core.codec import crc16_modbus
from rs485_gui.models import ActiveSendStats, SerialSettings
from rs485_gui.transport.active_send import ActiveSendBoardTransport


def _make_valid_frame(slave_id=1, function_code=3, register_count=11):
    data_bytes = bytes(register_count * 2)
    header = bytes([slave_id, function_code, register_count * 2])
    payload = header + data_bytes
    crc = crc16_modbus(payload).to_bytes(2, "little")
    return payload + crc


def _make_app_state():
    state = MagicMock()
    state.serial_cfg = SerialSettings(port="/dev/null", baudrate=460800)
    state.parse_profile = "modbus_rtu_response_11regs"
    state.active_send_stats = ActiveSendStats()
    state.get_session_id.return_value = ""
    state.build_board_profile_snapshot.return_value = {}
    state.cfg = OmegaConf.create(
        {
            "device": {
                "mode": "active_send",
                "slave_address": 1,
                "active_send_frequency_code": 8,
                "poll_interval_s": 0.001,
            },
            "active_send": {
                "timestamp_policy": "batch_end_anchored",
                "default_parser_profile": "modbus_rtu_response_11regs",
                "frame_slave_id": 1,
                "frame_function_code": 3,
                "frame_register_count": 11,
                "max_buffer_bytes": 8192,
                "read_chunk_bytes": 1024,
                "max_read_bytes_per_cycle": 8192,
                "read_timeout_s": 0.5,
                "delivery_window_s": 0.010,
                "max_frames_per_delivery": 16,
                "log_first_n_good_frames": 5,
                "log_summary_every_n_good_frames": 250,
                "log_bad_frame_hex_bytes": 64,
                "warning_emit_interval_s": 5.0,
                "detailed_warning_limit": 2,
                "recovery_enabled": True,
                "recovery_warning_threshold": 48,
                "recovery_min_interval_s": 1.0,
                "recovery_reset_input_buffer": True,
                "clock_reanchor_max_drift_s": 0.05,
                "log_monotonic_adjust_warn_s": 0.005,
                "max_chain_lead_s": 0.050,
                "measured_rate_enabled": True,
                "measured_rate_window_s": 2.0,
                "measured_rate_ewma_alpha": 0.25,
                "measured_rate_max_dev_frac": 0.01,
            },
        }
    )
    return state


def _make_transport_with_buffer(buffer_data: bytes):
    """Create transport with data pre-loaded in the binary buffer only.
    The mock serial returns empty bytes immediately so only buffered data is processed."""
    serial_mock = MagicMock()
    serial_mock.is_open = True
    serial_mock.read.return_value = b""  # no new serial data
    serial_mock.in_waiting = 0
    app_state = _make_app_state()
    transport = ActiveSendBoardTransport(app_state)
    transport.ser = serial_mock
    transport.binary_buffer.extend(buffer_data)
    return transport


class TestFrameExtraction:
    def test_single_valid_frame_decoded(self):
        transport = _make_transport_with_buffer(_make_valid_frame())
        raw_frames, _ = transport._read_modbus_response_frames_batch()
        assert len(raw_frames) == 1

    def test_two_valid_frames_decoded(self):
        transport = _make_transport_with_buffer(_make_valid_frame() * 2)
        raw_frames, _ = transport._read_modbus_response_frames_batch()
        assert len(raw_frames) == 2

    def test_corrupted_byte_discarded(self):
        garbage = bytes([0xDE])
        transport = _make_transport_with_buffer(garbage + _make_valid_frame())
        raw_frames, _ = transport._read_modbus_response_frames_batch()
        assert len(raw_frames) == 1
        assert transport.app_state.active_send_stats.discarded_bytes >= 1

    def test_crc_corrupt_frame_skipped_recovers_next(self):
        bad_frame = bytearray(_make_valid_frame())
        bad_frame[-1] ^= 0xFF  # corrupt CRC
        transport = _make_transport_with_buffer(bytes(bad_frame) + _make_valid_frame())
        raw_frames, _ = transport._read_modbus_response_frames_batch()
        assert len(raw_frames) == 1
        assert transport.app_state.active_send_stats.crc_failures >= 1

    def test_frame_registers_are_all_zero(self):
        transport = _make_transport_with_buffer(_make_valid_frame())
        raw_frames, _ = transport._read_modbus_response_frames_batch()
        from rs485_gui.core.codec import extract_registers_from_modbus_response

        regs = extract_registers_from_modbus_response(raw_frames[0], 1, 3, 11)
        assert all(r == 0 for r in regs)


class TestMonotonicAdjustDiagnostics:
    def _decode(self, transport, n_frames):
        frames = [_make_valid_frame() for _ in range(n_frames)]
        return transport._decode_batch(frames, {"decoder": "test"})

    def test_first_batch_has_zero_adjust(self):
        transport = _make_transport_with_buffer(b"")
        decoded = self._decode(transport, 3)
        assert len(decoded) == 3
        stats = transport.app_state.active_send_stats
        assert stats.monotonic_adjust_events == 0
        assert stats.monotonic_adjust_total_s == 0.0
        for frame in decoded:
            assert frame.raw_transport["diagnostics"]["monotonic_adjust_s"] == 0.0
            assert "batch_end_lsl_ts" in frame.raw_transport["diagnostics"]
            assert "serial_in_waiting_at_decode" in frame.raw_transport["diagnostics"]

    def test_colliding_batches_record_adjust_magnitude(self):
        transport = _make_transport_with_buffer(b"")
        self._decode(transport, 4)
        # Immediately decoding a second batch makes its back-dated start collide
        # with the previous batch tail, forcing the monotonic guard to fire.
        decoded = self._decode(transport, 4)
        stats = transport.app_state.active_send_stats
        assert stats.monotonic_adjust_events == 1
        assert stats.monotonic_adjust_total_s > 0.0
        for frame in decoded:
            assert frame.raw_transport["diagnostics"]["monotonic_adjust_s"] > 0.0
            assert frame.raw_transport["diagnostics"]["monotonic_adjust_events"] == 1
            assert frame.interpreted["timestamp_source"].endswith("_monotonic_adjusted")

    def test_adjusted_timestamps_remain_monotonic(self):
        transport = _make_transport_with_buffer(b"")
        first = self._decode(transport, 4)
        second = self._decode(transport, 4)
        timestamps = [f.interpreted["host_lsl_ts"] for f in first + second]
        assert timestamps == sorted(timestamps)
        deltas = [b - a for a, b in zip(timestamps, timestamps[1:])]
        assert min(deltas) > 0


class _FakeClock:
    """Controllable stand-in for ``lsl_local_clock`` (a 0-arg callable)."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, s: float) -> None:
        self.now += s


_NOMINAL_DT = 1.0 / 500.0  # active_send_frequency_code 8 == 500 Hz
_EPSILON = 1e-4  # _CHAIN_SQUEEZE_EPSILON_S


class TestChainLeadRelax:
    """Bounded chain-lead relax (squeeze) under a controlled LSL clock.

    With the clock frozen, the EWMA window never elapses so dt stays nominal,
    keeping the squeeze arithmetic exact.  Measured-rate is also disabled to be
    explicit.
    """

    def _make_transport(self, max_chain_lead_s=0.050, measured_rate_enabled=False):
        transport = _make_transport_with_buffer(b"")
        transport.app_state.cfg.active_send.max_chain_lead_s = max_chain_lead_s
        transport.app_state.cfg.active_send.measured_rate_enabled = measured_rate_enabled
        return transport

    def _decode(self, transport, n_frames=16):
        frames = [_make_valid_frame() for _ in range(n_frames)]
        return transport._decode_batch(frames, {"decoder": "test"})

    def test_lead_over_threshold_triggers_squeeze(self):
        transport = self._make_transport()
        clock = _FakeClock()
        with patch("rs485_gui.transport.active_send.lsl_local_clock", clock):
            # Frozen clock: batches 2 and 3 forward-push (+0.032 lead each), so
            # batch 4 sees lead ~0.064 > 0.050 and squeezes.
            for _ in range(3):
                self._decode(transport, 16)
            assert transport.app_state.active_send_stats.chain_relax_events == 0
            decoded = self._decode(transport, 16)
        stats = transport.app_state.active_send_stats
        assert stats.chain_relax_events == 1
        assert all(
            f.interpreted["timestamp_source"].endswith("_chain_relaxed") for f in decoded
        )
        lsl = [f.interpreted["host_lsl_ts"] for f in decoded]
        deltas = [b - a for a, b in zip(lsl, lsl[1:])]
        assert all(d == pytest.approx(_EPSILON, rel=1e-6) for d in deltas)

    def test_squeeze_preserves_strict_monotonicity(self):
        transport = self._make_transport()
        clock = _FakeClock()
        all_lsl: list[float] = []
        all_unix: list[float] = []
        with patch("rs485_gui.transport.active_send.lsl_local_clock", clock):
            for _ in range(6):
                decoded = self._decode(transport, 16)
                all_lsl.extend(f.interpreted["host_lsl_ts"] for f in decoded)
                all_unix.extend(f.host_ts for f in decoded)
        assert transport.app_state.active_send_stats.chain_relax_events >= 1
        lsl_deltas = [b - a for a, b in zip(all_lsl, all_lsl[1:])]
        unix_deltas = [b - a for a, b in zip(all_unix, all_unix[1:])]
        assert min(lsl_deltas) > 0
        assert min(unix_deltas) > 0

    def test_lead_bleeds_below_threshold(self):
        transport = self._make_transport()
        clock = _FakeClock()
        with patch("rs485_gui.transport.active_send.lsl_local_clock", clock):
            # Build a chain well ahead of wall clock.
            for _ in range(4):
                self._decode(transport, 16)
            assert transport.app_state.active_send_stats.chain_relax_events >= 1
            # Now let wall clock advance faster than the squeezed chain tip; the
            # lead must bleed back under the threshold and relaxing must stop.
            relaxed_flags = []
            for _ in range(6):
                clock.advance(0.05)
                decoded = self._decode(transport, 16)
                relaxed_flags.append(
                    decoded[0].interpreted["timestamp_source"].endswith("_chain_relaxed")
                )
            lead = transport._last_assigned_sample_lsl_ts - clock.now
        assert lead <= 0.050
        assert relaxed_flags[-1] is False

    def test_chain_relax_stats_and_diagnostics(self):
        transport = self._make_transport()
        clock = _FakeClock()
        with patch("rs485_gui.transport.active_send.lsl_local_clock", clock):
            for _ in range(3):
                pre = self._decode(transport, 16)
            squeezed = self._decode(transport, 16)
        # Pre-squeeze batch carries the diagnostics but no relax.
        for f in pre:
            d = f.raw_transport["diagnostics"]
            assert d["chain_relax_s"] == 0.0
            assert "chain_lead_s" in d
            assert "effective_dt_s" in d
        stats = transport.app_state.active_send_stats
        assert stats.chain_relax_total_s == pytest.approx(16 * (_NOMINAL_DT - _EPSILON))
        for f in squeezed:
            d = f.raw_transport["diagnostics"]
            assert d["chain_relax_s"] > 0.0
            assert d["chain_lead_s"] > 0.050
            assert d["chain_relax_events"] == 1
            assert d["effective_dt_s"] == pytest.approx(_EPSILON, rel=1e-6)

    def test_subthreshold_collision_keeps_forward_push(self):
        transport = self._make_transport()
        clock = _FakeClock()
        with patch("rs485_gui.transport.active_send.lsl_local_clock", clock):
            self._decode(transport, 4)
            decoded = self._decode(transport, 4)
        stats = transport.app_state.active_send_stats
        assert stats.chain_relax_events == 0
        assert stats.monotonic_adjust_events == 1
        assert all(
            f.interpreted["timestamp_source"].endswith("_monotonic_adjusted") for f in decoded
        )

    def test_single_frame_batch_stays_monotonic_under_squeeze(self):
        transport = self._make_transport(max_chain_lead_s=0.001)
        clock = _FakeClock()
        all_lsl: list[float] = []
        with patch("rs485_gui.transport.active_send.lsl_local_clock", clock):
            for _ in range(8):
                decoded = self._decode(transport, 1)
                all_lsl.extend(f.interpreted["host_lsl_ts"] for f in decoded)
        assert transport.app_state.active_send_stats.chain_relax_events >= 1
        deltas = [b - a for a, b in zip(all_lsl, all_lsl[1:])]
        assert min(deltas) > 0


class TestTimestampLogThrottle:
    """Hot-path timestamp-adjust logging must be rate-limited."""

    def test_monotonic_adjust_warning_is_throttled(self, caplog):
        import logging as _logging

        transport = _make_transport_with_buffer(b"")
        # Never squeeze (so every collision is a monotonic adjust) and freeze the
        # measured-rate window so dt stays nominal.
        transport.app_state.cfg.active_send.max_chain_lead_s = 10.0
        transport.app_state.cfg.active_send.measured_rate_enabled = False
        clock = _FakeClock()
        with patch("rs485_gui.transport.active_send.lsl_local_clock", clock), caplog.at_level(
            _logging.WARNING, logger="rs485_gui.transport.active_send"
        ):
            for _ in range(30):
                frames = [_make_valid_frame() for _ in range(16)]
                transport._decode_batch(frames, {"decoder": "test"})
        stats = transport.app_state.active_send_stats
        warn_lines = [r for r in caplog.records if "monotonic timestamp adjust" in r.getMessage()]
        assert stats.monotonic_adjust_events >= 20  # many collisions occurred
        assert len(warn_lines) <= 2  # but logging was collapsed
        assert stats.timestamp_log_suppressed > 0


class TestMeasuredRateDt:
    """EWMA measured-rate dt for batch_end_anchored back-dating."""

    def _make_transport(self, **overrides):
        transport = _make_transport_with_buffer(b"")
        for k, v in overrides.items():
            setattr(transport.app_state.cfg.active_send, k, v)
        return transport

    def _run_at_rate(self, transport, clock, rate_hz, n_frames=16, n_batches=80):
        per_batch_s = n_frames / rate_hz
        with patch("rs485_gui.transport.active_send.lsl_local_clock", clock):
            for _ in range(n_batches):
                frames = [_make_valid_frame() for _ in range(n_frames)]
                transport._decode_batch(frames, {"decoder": "test"})
                clock.advance(per_batch_s)

    def test_measured_dt_tracks_real_rate(self):
        # Board runs slightly slow (499 Hz); dt should converge toward 1/499,
        # which is inside the +/-1% clamp of nominal 1/500.
        transport = self._make_transport(measured_rate_window_s=2.0)
        clock = _FakeClock()
        self._run_at_rate(transport, clock, rate_hz=499.0)
        assert transport._measured_dt_s is not None
        assert transport._measured_dt_s == pytest.approx(1.0 / 499.0, rel=1e-6)

    def test_measured_dt_is_clamped(self):
        # Absurdly slow cadence (400 Hz) must clamp to nominal * (1 + max_dev).
        transport = self._make_transport(measured_rate_window_s=2.0, measured_rate_max_dev_frac=0.01)
        clock = _FakeClock()
        self._run_at_rate(transport, clock, rate_hz=400.0, n_batches=60)
        assert transport._measured_dt_s == pytest.approx(_NOMINAL_DT * 1.01, rel=1e-9)

    def test_measured_rate_disabled_keeps_nominal(self):
        transport = self._make_transport(measured_rate_enabled=False)
        clock = _FakeClock()
        self._run_at_rate(transport, clock, rate_hz=499.0)
        assert transport._measured_dt_s is None
