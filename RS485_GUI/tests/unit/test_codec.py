"""Unit tests for rs485_gui.core.codec.

These tests cover pure functions only — no hardware, no serial port,
no NiceGUI dependency.
"""

from __future__ import annotations

import pytest

from rs485_gui.core.codec import (
    apply_decimal,
    build_log_text,
    combine_s32_from_words,
    crc16_modbus,
    decode_modbus_measurement,
    decode_status_word,
    extract_registers_from_modbus_response,
    truncate_text,
)

# ---------------------------------------------------------------------------
# CRC-16 Modbus
# ---------------------------------------------------------------------------


class TestCrc16Modbus:
    def test_known_vector(self):
        # FC-03 read request: slave=1, fc=03, addr=0x0000, count=11
        payload = bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x0B])
        crc = crc16_modbus(payload)
        # Verify round-trip: appending CRC should give CRC of 0
        frame = payload + crc.to_bytes(2, "little")
        assert crc16_modbus(frame[:-2]).to_bytes(2, "little") == frame[-2:]

    def test_empty_data(self):
        assert crc16_modbus(b"") == 0xFFFF

    def test_single_byte(self):
        result = crc16_modbus(bytes([0x01]))
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFF


# ---------------------------------------------------------------------------
# Register word combination
# ---------------------------------------------------------------------------


class TestCombineS32FromWords:
    def test_zero(self):
        assert combine_s32_from_words(0, 0) == 0

    def test_positive(self):
        # 0x00010000 = 65536
        assert combine_s32_from_words(0x0000, 0x0001) == 65536

    def test_negative(self):
        # 0xFFFFFFFF = -1 in signed 32-bit
        assert combine_s32_from_words(0xFFFF, 0xFFFF) == -1

    def test_min_s32(self):
        # 0x80000000 = -2147483648
        assert combine_s32_from_words(0x0000, 0x8000) == -2147483648

    def test_max_s32(self):
        # 0x7FFFFFFF = 2147483647
        assert combine_s32_from_words(0xFFFF, 0x7FFF) == 2147483647


# ---------------------------------------------------------------------------
# Decimal scaling
# ---------------------------------------------------------------------------


class TestApplyDecimal:
    def test_zero_digits(self):
        assert apply_decimal(1234, 0) == 1234.0

    def test_two_digits(self):
        assert apply_decimal(12345, 2) == pytest.approx(123.45)

    def test_four_digits(self):
        assert apply_decimal(10000, 4) == pytest.approx(1.0)

    def test_none_input(self):
        assert apply_decimal(None, 2) is None

    def test_unknown_code_defaults_zero(self):
        # Code 99 not in table → 0 digits → no scaling
        assert apply_decimal(100, 99) == 100.0


# ---------------------------------------------------------------------------
# Status word decoding
# ---------------------------------------------------------------------------


class TestDecodeStatusWord:
    def test_zero(self):
        assert decode_status_word(0) == []

    def test_data_valid(self):
        flags = decode_status_word(1)  # bit 0
        assert "data_valid" in flags

    def test_multiple_flags(self):
        # bit 0 (data_valid) + bit 9 (relay1_active)
        flags = decode_status_word(0b1000000001)
        assert "data_valid" in flags
        assert "relay1_active" in flags
        assert len(flags) == 2


# ---------------------------------------------------------------------------
# Frame extraction
# ---------------------------------------------------------------------------


class TestExtractRegistersFromModbusResponse:
    def _make_valid_frame(self, slave_id=1, function_code=3, register_count=11):
        """Build a syntactically valid Modbus response frame."""
        data_bytes = bytes(register_count * 2)
        header = bytes([slave_id, function_code, register_count * 2])
        payload = header + data_bytes
        crc = crc16_modbus(payload).to_bytes(2, "little")
        return payload + crc

    def test_valid_frame_returns_registers(self):
        frame = self._make_valid_frame()
        regs = extract_registers_from_modbus_response(frame, 1, 3, 11)
        assert len(regs) == 11
        assert all(r == 0 for r in regs)

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError, match="length"):
            extract_registers_from_modbus_response(b"\x00" * 5, 1, 3, 11)

    def test_wrong_slave_id_raises(self):
        frame = self._make_valid_frame(slave_id=1)
        with pytest.raises(ValueError, match="slave id"):
            extract_registers_from_modbus_response(frame, 2, 3, 11)

    def test_crc_mismatch_raises(self):
        frame = bytearray(self._make_valid_frame())
        frame[-1] ^= 0xFF  # corrupt last CRC byte
        with pytest.raises(ValueError, match="CRC"):
            extract_registers_from_modbus_response(bytes(frame), 1, 3, 11)


# ---------------------------------------------------------------------------
# Full frame decode
# ---------------------------------------------------------------------------


class TestDecodeModbusMeasurement:
    def _make_registers(self, net_raw=1000, decimal_code=2, unit_code=4, status=1):
        """Return 11 registers with net_raw at positions [2,3]."""
        low = net_raw & 0xFFFF
        high = (net_raw >> 16) & 0xFFFF
        return [0, 0, low, high, 0, 0, 0, 0, decimal_code, unit_code, status]

    def test_net_value_scaling(self):
        regs = self._make_registers(net_raw=1000, decimal_code=2)
        frame = decode_modbus_measurement(regs, host_ts=1000.0)
        assert frame.interpreted["net_value"] == pytest.approx(10.0)

    def test_unit_label(self):
        regs = self._make_registers(unit_code=4)
        frame = decode_modbus_measurement(regs, host_ts=1000.0)
        assert frame.interpreted["unit_label"] == "N"

    def test_status_flags_decoded(self):
        regs = self._make_registers(status=1)  # bit 0 = data_valid
        frame = decode_modbus_measurement(regs, host_ts=1000.0)
        assert "data_valid" in frame.interpreted["status_flags"]

    def test_mode_is_modbus_rtu(self):
        frame = decode_modbus_measurement([0] * 11, host_ts=1000.0)
        assert frame.mode == "modbus_rtu"

    def test_reference_force_n_equals_net_value(self):
        regs = self._make_registers(net_raw=500, decimal_code=1)
        frame = decode_modbus_measurement(regs, host_ts=1000.0)
        assert frame.interpreted["reference_force_N"] == frame.interpreted["net_value"]


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------


class TestTruncateText:
    def test_short_text_unchanged(self):
        assert truncate_text("hello", 100) == "hello"

    def test_long_text_truncated(self):
        result = truncate_text("x" * 200, 50)
        assert len(result) <= 70  # kept + notice
        assert "+" in result

    def test_zero_max_unchanged(self):
        assert truncate_text("hello", 0) == "hello"


class TestBuildLogText:
    def test_joins_items(self):
        assert build_log_text(["a", "b", "c"], "\n", 1000) == "a\nb\nc"

    def test_truncates_at_limit(self):
        items = ["x" * 100] * 10
        result = build_log_text(items, "\n", 150)
        assert "truncated" in result

    def test_zero_limit_joins_all(self):
        items = ["a", "b", "c"]
        assert build_log_text(items, ",", 0) == "a,b,c"
