"""Integration tests for the active-send binary frame parser."""
from __future__ import annotations

from unittest.mock import MagicMock

from omegaconf import OmegaConf

from rs485_gui.core.codec import crc16_modbus
from rs485_gui.models import ActiveSendStats, SerialSettings
from rs485_gui.transport.active_send import ActiveSendBoardTransport


def _make_valid_frame(slave_id=1, function_code=3, register_count=11):
    data_bytes = bytes(register_count * 2)
    header = bytes([slave_id, function_code, register_count * 2])
    payload = header + data_bytes
    crc = crc16_modbus(payload).to_bytes(2, 'little')
    return payload + crc


def _make_app_state():
    state = MagicMock()
    state.serial_cfg = SerialSettings(port='/dev/null', baudrate=460800)
    state.parse_profile = 'modbus_rtu_response_11regs'
    state.active_send_stats = ActiveSendStats()
    state.get_session_id.return_value = ''
    state.build_board_profile_snapshot.return_value = {}
    state.cfg = OmegaConf.create({
        'device': {'mode': 'active_send', 'slave_address': 1,
                   'active_send_frequency_code': 8, 'poll_interval_s': 0.001},
        'active_send': {
            'timestamp_policy': 'batch_end_anchored',
            'default_parser_profile': 'modbus_rtu_response_11regs',
            'frame_slave_id': 1, 'frame_function_code': 3, 'frame_register_count': 11,
            'max_buffer_bytes': 8192, 'read_chunk_bytes': 1024,
            'max_read_bytes_per_cycle': 8192, 'read_timeout_s': 0.5,
            'delivery_window_s': 0.010, 'max_frames_per_delivery': 16,
            'log_first_n_good_frames': 5, 'log_summary_every_n_good_frames': 250,
            'log_bad_frame_hex_bytes': 64, 'warning_emit_interval_s': 5.0,
            'detailed_warning_limit': 2, 'recovery_enabled': True,
            'recovery_warning_threshold': 48, 'recovery_min_interval_s': 1.0,
            'recovery_reset_input_buffer': True, 'clock_reanchor_max_drift_s': 0.05,
        },
    })
    return state


def _make_transport_with_buffer(buffer_data: bytes):
    """Create transport with data pre-loaded in the binary buffer only.
    The mock serial returns empty bytes immediately so only buffered data is processed."""
    serial_mock = MagicMock()
    serial_mock.is_open = True
    serial_mock.read.return_value = b''   # no new serial data
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
        bad_frame[-1] ^= 0xFF   # corrupt CRC
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
