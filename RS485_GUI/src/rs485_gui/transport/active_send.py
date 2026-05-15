"""Active-send binary push-frame transport.

The board continuously emits Modbus-RTU-formatted response frames at a
configured rate (up to 500 Hz).  This transport reads and decodes those
frames from the serial buffer without issuing any Modbus requests.

Key design decisions (preserved from original):
- Binary buffer with look-ahead CRC-valid header search (avoids long false-lock
  cascades when header-looking bytes appear inside payloads).
- Recovery mechanism that discards stale buffered bytes and re-anchors timing
  after CRC/resync cascades.
- ``batch_end_anchored`` timestamp policy (calibration-safe default): each
  parsed batch is anchored to the current pylsl local_clock() and frame times
  are reconstructed only inside that batch.  This prevents ref_shift drift when
  the effective RS485 rate deviates from the configured 500 Hz.

Dependency chain: models, constants, core/codec, transport/base
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import serial

from rs485_gui.constants import ACTIVE_SEND_FREQ_CODE_TO_VALUE, ACTIVE_SEND_PARSER_PROFILE
from rs485_gui.core.codec import (
    crc16_modbus,
    decode_active_send_modbus_response,
    lsl_local_clock,
)
from rs485_gui.models import ActiveSendStats, MeasurementFrame
from rs485_gui.transport.base import BoardTransport

if TYPE_CHECKING:
    from rs485_gui.state import AppState

LOGGER = logging.getLogger(__name__)


## @brief Represents the ActiveSendBoardTransport component.
class ActiveSendBoardTransport(BoardTransport):
    """Receives and decodes binary active-send push frames from the board.

    Only the ``modbus_rtu_response_11regs`` profile is supported.
    ASCII/hex debug profiles were removed in the v0.2 refactor because they
    do not provide the 11-register force/status payload required for
    calibration QA.
    """

    ## @brief Init.
    #
    #  @param self Parameter description.
    #  @param app_state Parameter description.
    def __init__(self, app_state: AppState) -> None:
        self.app_state = app_state
        self.ser: serial.Serial | None = None
        self.binary_buffer = bytearray()
        self.header_length = 3
        self._last_assigned_sample_ts: float | None = None
        self._last_assigned_sample_lsl_ts: float | None = None
        self._force_timestamp_reanchor: bool = False

    # ------------------------------------------------------------------
    # BoardTransport interface
    # ------------------------------------------------------------------

    def connect(self) -> None:
        cfg = self.app_state.serial_cfg
        self.ser = serial.Serial(
            port=cfg.port,
            baudrate=cfg.baudrate,
            bytesize=cfg.bytesize,
            parity=cfg.parity,
            stopbits=cfg.stopbits,
            timeout=cfg.timeout,
        )
        self.binary_buffer.clear()
        self._last_assigned_sample_ts = None
        self._last_assigned_sample_lsl_ts = None
        self._force_timestamp_reanchor = False
        self.app_state.active_send_stats = ActiveSendStats()
        if self.ser is not None:
            self.ser.reset_input_buffer()

    ## @brief Disconnect.
    #
    #  @param self Parameter description.
    def disconnect(self) -> None:
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None
        self.binary_buffer.clear()
        self._last_assigned_sample_ts = None
        self._last_assigned_sample_lsl_ts = None
        self._force_timestamp_reanchor = False

    ## @brief Read frames.
    #
    #  @param self Parameter description.
    #  @return Result produced by this function.
    def read_frames(self) -> list[MeasurementFrame]:
        """Read one batch of active-send frames and return decoded frames.

        Raises :class:`TimeoutError` if no CRC-valid frame arrives within
        ``active_send.read_timeout_s``.
        """
        if self.app_state.parse_profile != ACTIVE_SEND_PARSER_PROFILE:
            raise RuntimeError(
                f'Only parser profile {ACTIVE_SEND_PARSER_PROFILE!r} is supported. '
                f'Got: {self.app_state.parse_profile!r}'
            )
        frame_bytes_batch, diagnostics = self._read_modbus_response_frames_batch()
        return self._decode_batch(frame_bytes_batch, diagnostics)

    ## @brief Send command.
    #
    #  @param self Parameter description.
    #  @param command_name Parameter description.
    def send_command(self, command_name: str) -> None:
        raise RuntimeError(
            'Board commands are only available in Modbus RTU mode (device.mode=modbus_rtu).'
        )

    # ------------------------------------------------------------------
    # Internal: byte-level frame extraction
    # ------------------------------------------------------------------

    def _maybe_recover_active_stream(self, reason: str) -> None:
        """Drop stale buffered bytes and re-anchor timing after a resync cascade."""
        stats = self.app_state.active_send_stats
        cfg = self.app_state.cfg.active_send
        if not cfg.recovery_enabled:
            return
        now = time.monotonic()
        min_interval_s = float(cfg.recovery_min_interval_s)
        warning_threshold = max(1, int(cfg.recovery_warning_threshold))
        if now - stats.last_recovery_monotonic < min_interval_s:
            return
        if (stats.warning_events_total - stats.last_recovery_warning_count) < warning_threshold:
            return

        pending = 0
        if self.ser is not None:
            try:
                pending = int(self.ser.in_waiting)
            except Exception:
                pending = 0

        dropped_buffer = len(self.binary_buffer)
        self.binary_buffer.clear()
        if self.ser is not None and cfg.recovery_reset_input_buffer:
            try:
                self.ser.reset_input_buffer()
            except Exception as exc:
                LOGGER.warning('Active-send recovery: could not reset serial buffer: %s', exc)

        self._force_timestamp_reanchor = True
        stats.recovery_events += 1
        stats.last_recovery_monotonic = now
        stats.last_recovery_warning_count = stats.warning_events_total
        stats.discarded_bytes += dropped_buffer + pending
        LOGGER.warning(
            'Active-send parser recovery #%d: reason=%s dropped_buffer=%d '
            'dropped_serial_pending=%d; timing will re-anchor on next valid batch',
            stats.recovery_events, reason, dropped_buffer, pending,
        )

    ## @brief Maybe log active warning.
    #
    #  @param self Parameter description.
    #  @param message Parameter description.
    def _maybe_log_active_warning(self, message: str) -> None:
        stats = self.app_state.active_send_stats
        cfg = self.app_state.cfg.active_send
        stats.warning_events_total += 1
        now = time.monotonic()
        detailed_limit = int(cfg.detailed_warning_limit)
        emit_interval_s = float(cfg.warning_emit_interval_s)
        if stats.warning_events_total <= detailed_limit:
            LOGGER.warning(message)
            stats.last_warning_emit_monotonic = now
            return
        if now - stats.last_warning_emit_monotonic >= emit_interval_s:
            LOGGER.warning(
                'Active-send backlog summary: parsed_ok=%d batches=%d crc_failures=%d '
                'resyncs=%d overflow_events=%d overflow_bytes=%d discarded=%d '
                'buffer_len=%d max_buffer=%d max_in_waiting=%d '
                'timestamp_reanchors=%d suppressed=%d',
                stats.frames_ok, stats.frames_delivered, stats.crc_failures,
                stats.header_resyncs, stats.buffer_overflow_events,
                stats.buffer_overflow_bytes, stats.discarded_bytes,
                len(self.binary_buffer), stats.max_buffer_len, stats.max_in_waiting,
                stats.timestamp_reanchors, stats.warning_suppressed,
            )
            stats.last_warning_emit_monotonic = now
            stats.warning_suppressed = 0
            self._maybe_recover_active_stream('warning_threshold')
            return
        stats.warning_suppressed += 1
        self._maybe_recover_active_stream('warning_threshold')

    ## @brief Update active watermarks.
    #
    #  @param self Parameter description.
    def _update_active_watermarks(self) -> None:
        stats = self.app_state.active_send_stats
        stats.max_buffer_len = max(stats.max_buffer_len, len(self.binary_buffer))
        if self.ser is not None:
            try:
                stats.max_in_waiting = max(stats.max_in_waiting, int(self.ser.in_waiting))
            except Exception:
                pass

    ## @brief Extract modbus response frames.
    #
    #  @param self Parameter description.
    #  @param header Parameter description.
    #  @param expected_len Parameter description.
    #  @param bad_hex_limit Parameter description.
    #  @param max_buffer_bytes Parameter description.
    #  @param max_frames Parameter description.
    #  @return Result produced by this function.
    def _extract_modbus_response_frames(
        self,
        *,
        header: bytes,
        expected_len: int,
        bad_hex_limit: int,
        max_buffer_bytes: int,
        max_frames: int,
    ) -> list[bytes]:
        """Extract CRC-valid Modbus-style active-send frames from the byte buffer.

        Uses a short look-ahead for the next CRC-valid header before deciding
        how much to discard — this avoids long false-lock cascades.
        """
        stats = self.app_state.active_send_stats
        frames: list[bytes] = []
        max_frames = max(1, int(max_frames))

        if len(self.binary_buffer) > max_buffer_bytes:
            overflow = len(self.binary_buffer) - max_buffer_bytes
            stats.discarded_bytes += overflow
            stats.buffer_overflow_events += 1
            stats.buffer_overflow_bytes += overflow
            del self.binary_buffer[:overflow]
            self._force_timestamp_reanchor = True
            self._maybe_log_active_warning(
                f'Active-send buffer overflow: discarded {overflow} bytes '
                f'to keep buffer <= {max_buffer_bytes}'
            )

        ## @brief Find next crc valid header.
        #
        #  @param start_pos Parameter description.
        #  @return Result produced by this function.
        def _find_next_crc_valid_header(start_pos: int = 0) -> int | None:
            pos = max(0, start_pos)
            while True:
                idx = self.binary_buffer.find(header, pos)
                if idx < 0 or len(self.binary_buffer) - idx < expected_len:
                    return None
                candidate = bytes(self.binary_buffer[idx:idx + expected_len])
                expected_crc = crc16_modbus(candidate[:-2]).to_bytes(2, byteorder='little')
                if candidate[-2:] == expected_crc:
                    return idx
                pos = idx + 1

        while len(frames) < max_frames:
            idx = self.binary_buffer.find(header)
            if idx < 0:
                if len(self.binary_buffer) > self.header_length - 1:
                    discard = len(self.binary_buffer) - (self.header_length - 1)
                    if discard > 0:
                        stats.discarded_bytes += discard
                        del self.binary_buffer[:discard]
                break

            if idx > 0:
                prefix = bytes(self.binary_buffer[:idx])
                preview = prefix[:bad_hex_limit].hex(' ')
                stats.discarded_bytes += idx
                stats.header_resyncs += 1
                self._force_timestamp_reanchor = True
                del self.binary_buffer[:idx]
                self._maybe_log_active_warning(
                    f'Active-send resync: discarded {idx} leading byte(s) '
                    f'before header {header.hex(" ")}; preview={preview}'
                )

            if len(self.binary_buffer) < expected_len:
                break

            candidate = bytes(self.binary_buffer[:expected_len])
            expected_crc = crc16_modbus(candidate[:-2]).to_bytes(2, byteorder='little')
            received_crc = candidate[-2:]
            if received_crc != expected_crc:
                stats.crc_failures += 1
                stats.last_bad_candidate_hex = candidate[:bad_hex_limit].hex(' ')
                self._force_timestamp_reanchor = True

                valid_idx = _find_next_crc_valid_header(1)
                if valid_idx is not None:
                    discard = valid_idx
                    del self.binary_buffer[:discard]
                    stats.discarded_bytes += discard
                    stats.header_resyncs += 1
                    self._maybe_log_active_warning(
                        f'Active-send CRC mismatch; skipped to next CRC-valid header '
                        f'#{stats.crc_failures}: got={received_crc.hex()} '
                        f'expected={expected_crc.hex()} skipped={discard} '
                        f'candidate_len={len(candidate)} '
                        f'preview={stats.last_bad_candidate_hex}'
                    )
                    continue

                del self.binary_buffer[0]
                stats.discarded_bytes += 1
                stats.header_resyncs += 1
                self._maybe_log_active_warning(
                    f'Active-send CRC mismatch #{stats.crc_failures}: '
                    f'got={received_crc.hex()} expected={expected_crc.hex()} '
                    f'candidate_len={len(candidate)} '
                    f'preview={stats.last_bad_candidate_hex}'
                )
                continue

            del self.binary_buffer[:expected_len]
            frames.append(candidate)
            self._update_active_watermarks()

        return frames

    ## @brief Read modbus response frames batch.
    #
    #  @param self Parameter description.
    #  @return Result produced by this function.
    def _read_modbus_response_frames_batch(self) -> tuple[list[bytes], dict[str, Any]]:
        """Read bytes from serial, extract CRC-valid frames, return batch + diagnostics."""
        if self.ser is None:
            raise RuntimeError('Transport not connected')

        cfg = self.app_state.cfg.active_send
        dev_cfg = self.app_state.cfg.device

        slave_id = int(cfg.frame_slave_id) or int(dev_cfg.slave_address)
        function_code = int(cfg.frame_function_code)
        register_count = int(cfg.frame_register_count)
        expected_byte_count = register_count * 2
        expected_len = 3 + expected_byte_count + 2
        header = bytes([slave_id, function_code, expected_byte_count])
        max_buffer_bytes = int(cfg.max_buffer_bytes)
        chunk_size = max(1, int(cfg.read_chunk_bytes))
        max_read_bytes = max(chunk_size, int(cfg.max_read_bytes_per_cycle))
        read_timeout_s = float(cfg.read_timeout_s)
        delivery_window_s = float(cfg.delivery_window_s)
        max_frames_per_delivery = max(1, int(cfg.max_frames_per_delivery))
        log_first_n_good = int(cfg.log_first_n_good_frames)
        log_summary_every_n = int(cfg.log_summary_every_n_good_frames)
        bad_hex_limit = int(cfg.log_bad_frame_hex_bytes)
        stats = self.app_state.active_send_stats

        frames_batch: list[bytes] = []
        batch_started_monotonic: float | None = None
        read_deadline = time.monotonic() + read_timeout_s

        # Consume already-buffered complete frames first
        if self.binary_buffer:
            buffered_frames = self._extract_modbus_response_frames(
                header=header, expected_len=expected_len,
                bad_hex_limit=bad_hex_limit, max_buffer_bytes=max_buffer_bytes,
                max_frames=max_frames_per_delivery,
            )
            if buffered_frames:
                frames_batch.extend(buffered_frames)
                batch_started_monotonic = time.monotonic()

        while time.monotonic() < read_deadline:
            if frames_batch and batch_started_monotonic is not None:
                if (time.monotonic() - batch_started_monotonic) >= delivery_window_s:
                    break
                if len(frames_batch) >= max_frames_per_delivery:
                    break

            try:
                pending = int(self.ser.in_waiting)
            except Exception:
                pending = 0

            read_size = min(max_read_bytes, pending) if pending > 0 else min(chunk_size, expected_len)
            read_size = max(1, int(read_size))
            chunk = self.ser.read(read_size)
            if not chunk:
                if frames_batch:
                    break
                continue

            if batch_started_monotonic is None:
                batch_started_monotonic = time.monotonic()

            stats.bytes_received += len(chunk)
            stats.chunks_received += 1
            self.binary_buffer.extend(chunk)
            self._update_active_watermarks()
            frames = self._extract_modbus_response_frames(
                header=header, expected_len=expected_len,
                bad_hex_limit=bad_hex_limit, max_buffer_bytes=max_buffer_bytes,
                max_frames=max_frames_per_delivery - len(frames_batch),
            )
            if frames:
                frames_batch.extend(frames)
                if len(frames_batch) >= max_frames_per_delivery:
                    break

        if not frames_batch:
            stats.timeouts += 1
            raise TimeoutError(
                f'Timed out waiting for active-send batch '
                f'(parsed_ok={stats.frames_ok}, batches={stats.frames_delivered}, '
                f'crc_failures={stats.crc_failures}, resyncs={stats.header_resyncs}, '
                f'discarded_bytes={stats.discarded_bytes}, '
                f'buffer_len={len(self.binary_buffer)}, '
                f'max_buffer={stats.max_buffer_len})'
            )

        stats.frames_ok += len(frames_batch)
        stats.frames_delivered += 1
        stats.last_good_frame_hex = frames_batch[-1].hex(' ')

        if stats.frames_delivered <= log_first_n_good:
            LOGGER.info(
                'Active-send delivered batch #%d: frames=%d first_len=%d '
                'last_len=%d last_hex=%s',
                stats.frames_delivered, len(frames_batch),
                len(frames_batch[0]), len(frames_batch[-1]),
                frames_batch[-1].hex(' '),
            )
        elif log_summary_every_n > 0 and (stats.frames_delivered % log_summary_every_n) == 0:
            LOGGER.info(
                'Active-send summary: parsed_ok=%d batches=%d bytes=%d crc_failures=%d '
                'resyncs=%d overflow_events=%d overflow_bytes=%d discarded=%d '
                'max_buffer=%d max_in_waiting=%d timestamp_reanchors=%d',
                stats.frames_ok, stats.frames_delivered, stats.bytes_received,
                stats.crc_failures, stats.header_resyncs,
                stats.buffer_overflow_events, stats.buffer_overflow_bytes,
                stats.discarded_bytes, stats.max_buffer_len, stats.max_in_waiting,
                stats.timestamp_reanchors,
            )

        diagnostics: dict[str, Any] = {
            'decoder': 'modbus_rtu_response_push_batch',
            'slave_id': slave_id, 'function_code': function_code,
            'register_count': register_count,
            'frames_ok': stats.frames_ok, 'batches_delivered': stats.frames_delivered,
            'frames_in_batch': len(frames_batch),
            'crc_failures': stats.crc_failures, 'header_resyncs': stats.header_resyncs,
            'discarded_bytes': stats.discarded_bytes,
            'bytes_received_total': stats.bytes_received,
            'chunks_received_total': stats.chunks_received,
            'buffer_len': len(self.binary_buffer),
            'max_buffer_len': stats.max_buffer_len,
            'max_in_waiting': stats.max_in_waiting,
            'timestamp_reanchors': stats.timestamp_reanchors,
            'timestamp_drift_reanchors': stats.timestamp_drift_reanchors,
            'timestamp_parser_reanchors': stats.timestamp_parser_reanchors,
            'recovery_events': stats.recovery_events,
            'delivery_window_s': delivery_window_s,
            'max_frames_per_delivery': max_frames_per_delivery,
        }
        return frames_batch, diagnostics

    # ------------------------------------------------------------------
    # Internal: timestamp reconstruction and frame decoding
    # ------------------------------------------------------------------

    def _decode_batch(
        self,
        frame_bytes_batch: list[bytes],
        diagnostics: dict[str, Any],
    ) -> list[MeasurementFrame]:
        cfg = self.app_state.cfg
        dev_cfg = cfg.device
        active_cfg = cfg.active_send

        slave_id = int(active_cfg.frame_slave_id) or int(dev_cfg.slave_address)
        function_code = int(active_cfg.frame_function_code)
        register_count = int(active_cfg.frame_register_count)
        freq_hz = ACTIVE_SEND_FREQ_CODE_TO_VALUE.get(
            int(dev_cfg.active_send_frequency_code), 0
        )
        batch_end_ts = time.time()
        batch_end_lsl_ts = lsl_local_clock()
        stats = self.app_state.active_send_stats

        timestamp_policy = str(active_cfg.timestamp_policy).strip().lower()
        frames: list[MeasurementFrame] = []

        if freq_hz > 0:
            dt = 1.0 / float(freq_hz)

            if timestamp_policy in {'batch_end_anchored', 'batch_end', 'anchored'}:
                batch_start_ts = batch_end_ts - dt * (len(frame_bytes_batch) - 1)
                batch_start_lsl_ts = batch_end_lsl_ts - dt * (len(frame_bytes_batch) - 1)
                timestamp_source = 'reconstructed_from_active_send_rate_batch_end_anchored'
                self._force_timestamp_reanchor = False

                # Guard against non-monotonic timestamps from backlog drainage
                if self._last_assigned_sample_lsl_ts is not None:
                    min_next_lsl_ts = self._last_assigned_sample_lsl_ts + dt
                    if batch_start_lsl_ts < min_next_lsl_ts:
                        adjust_s = min_next_lsl_ts - batch_start_lsl_ts
                        batch_start_lsl_ts += adjust_s
                        batch_start_ts += adjust_s
                        timestamp_source += '_monotonic_adjusted'

            elif timestamp_policy in {'continuous_rate', 'continuous'}:
                # DEPRECATED: use only when the RS485 device is proven to emit
                # at exactly configured_frequency_hz with no dropped samples.
                # Retained for backward compatibility; scheduled for removal in a
                # future major version.
                clock_reanchor_max_drift_s = float(active_cfg.clock_reanchor_max_drift_s)
                should_reanchor = (
                    self._last_assigned_sample_ts is None or self._force_timestamp_reanchor
                )
                if not should_reanchor and self._last_assigned_sample_lsl_ts is not None:
                    continuous_last = (
                        self._last_assigned_sample_lsl_ts + dt * len(frame_bytes_batch)
                    )
                    drift_s = batch_end_lsl_ts - continuous_last
                    if clock_reanchor_max_drift_s > 0 and abs(drift_s) > clock_reanchor_max_drift_s:
                        should_reanchor = True
                        stats.timestamp_drift_reanchors += 1
                        LOGGER.info(
                            'Active-send timestamp re-anchor due to drift: '
                            'drift=%.6fs threshold=%.6fs batch_size=%d',
                            drift_s, clock_reanchor_max_drift_s, len(frame_bytes_batch),
                        )
                if should_reanchor:
                    batch_start_ts = batch_end_ts - dt * (len(frame_bytes_batch) - 1)
                    batch_start_lsl_ts = batch_end_lsl_ts - dt * (len(frame_bytes_batch) - 1)
                    if self._last_assigned_sample_ts is None:
                        timestamp_source = 'reconstructed_from_active_send_rate_batch_start'
                    elif self._force_timestamp_reanchor:
                        timestamp_source = (
                            'reconstructed_from_active_send_rate_reanchored_after_parser_resync'
                        )
                        stats.timestamp_parser_reanchors += 1
                    else:
                        timestamp_source = (
                            'reconstructed_from_active_send_rate_reanchored_after_drift'
                        )
                    stats.timestamp_reanchors += 1
                    self._force_timestamp_reanchor = False
                else:
                    batch_start_ts = self._last_assigned_sample_ts + dt  # type: ignore[operator]
                    batch_start_lsl_ts = (
                        (self._last_assigned_sample_lsl_ts or batch_end_lsl_ts) + dt
                    )
                    timestamp_source = 'reconstructed_from_active_send_rate_continuous'

            elif timestamp_policy in {'host_receive', 'host'}:
                dt = 0.0
                batch_start_ts = batch_end_ts
                batch_start_lsl_ts = batch_end_lsl_ts
                timestamp_source = 'active_send_host_receive_lsl_clock'

            else:
                LOGGER.warning(
                    'Unsupported active_send.timestamp_policy=%r; using batch_end_anchored',
                    timestamp_policy,
                )
                batch_start_ts = batch_end_ts - dt * (len(frame_bytes_batch) - 1)
                batch_start_lsl_ts = batch_end_lsl_ts - dt * (len(frame_bytes_batch) - 1)
                timestamp_source = 'reconstructed_from_active_send_rate_batch_end_anchored'
                self._force_timestamp_reanchor = False
        else:
            dt = 0.0
            batch_start_ts = batch_end_ts
            batch_start_lsl_ts = batch_end_lsl_ts
            timestamp_source = 'host_batch_end_time'

        session_id = self.app_state.get_session_id()
        board_profile = self.app_state.build_board_profile_snapshot()

        for idx, frame_bytes in enumerate(frame_bytes_batch):
            host_ts = batch_start_ts + idx * dt if freq_hz > 0 else batch_end_ts
            host_lsl_ts = batch_start_lsl_ts + idx * dt if freq_hz > 0 else batch_end_lsl_ts
            frame_diag = dict(diagnostics)
            frame_diag.update({
                'batch_index': idx,
                'batch_size': len(frame_bytes_batch),
                'timestamp_source': timestamp_source,
                'configured_frequency_hz': freq_hz,
                'timestamp_reanchors': stats.timestamp_reanchors,
            })
            decoded = decode_active_send_modbus_response(
                frame=frame_bytes,
                host_ts=host_ts,
                host_lsl_ts=host_lsl_ts,
                slave_id=slave_id,
                function_code=function_code,
                register_count=register_count,
                diagnostics=frame_diag,
            )
            decoded.interpreted['timestamp_source'] = timestamp_source
            decoded.interpreted['configured_frequency_hz'] = freq_hz
            decoded.interpreted['reference_clock_s'] = decoded.interpreted.get('rs485_clock')
            decoded.interpreted['reference_force_N'] = decoded.interpreted.get(
                'net_value', decoded.interpreted.get('raw_value')
            )
            decoded.interpreted['reference_status'] = decoded.interpreted.get('status_word', 0)
            decoded.session_id = session_id
            decoded.board_profile = board_profile
            frames.append(decoded)

        if frames:
            self._last_assigned_sample_ts = frames[-1].host_ts
            self._last_assigned_sample_lsl_ts = float(
                frames[-1].interpreted.get('host_lsl_ts', batch_end_lsl_ts)
            )
        return frames
