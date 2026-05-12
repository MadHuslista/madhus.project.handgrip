"""Protocol-level constants and lookup tables for the RS485 acquisition board.

All values here are pure data with no runtime dependencies.  Device-tunable
register addresses are also exposed as config keys (device.read_start_register,
device.read_register_count, device.command_register) so that alternate firmware
variants can be supported without code changes.  The values below remain as
authoritative defaults.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Register map defaults
# ---------------------------------------------------------------------------

#: First holding register to read in a poll cycle (Modbus address 0x0000 / PLC 40001).
READ_START_REGISTER: int = 0

#: Number of consecutive holding registers to read per poll.
READ_REGISTER_COUNT: int = 11

#: Register used to write board commands (0x000B / PLC 40012).
COMMAND_REGISTER: int = 11

# ---------------------------------------------------------------------------
# Baud-rate code → bps
# ---------------------------------------------------------------------------

BAUD_CODE_TO_VALUE: dict[int, int] = {
    1: 2400,
    2: 4800,
    3: 9600,
    4: 19200,
    5: 22800,
    6: 38400,
    7: 57600,
    8: 115200,
    9: 128000,
    10: 230400,
    11: 256000,
    12: 460800,
    13: 500000,
    14: 512000,
    15: 600000,
}

# ---------------------------------------------------------------------------
# Active-send frequency code → Hz
# ---------------------------------------------------------------------------

ACTIVE_SEND_FREQ_CODE_TO_VALUE: dict[int, int] = {
    0: 1,
    1: 2,
    2: 5,
    3: 10,
    4: 20,
    5: 25,
    6: 60,
    7: 100,
    8: 500,
    9: 1000,
}

# ---------------------------------------------------------------------------
# Parity code → pyserial parity character
# ---------------------------------------------------------------------------

PARITY_CODE_TO_VALUE: dict[int, str] = {
    0: 'N',
    1: 'E',
    2: 'O',
}

# ---------------------------------------------------------------------------
# Engineering-unit code → label string
# ---------------------------------------------------------------------------

UNIT_CODE_TO_LABEL: dict[int, str] = {
    0: 'none',
    1: 'g',
    2: 'kg',
    3: 't',
    4: 'N',
    5: 'pa',
    6: 'kPa',
    7: 'MPa',
    8: 'N·m',
    9: 'kN',
}

# ---------------------------------------------------------------------------
# Decimal-point code → number of fractional digits
# ---------------------------------------------------------------------------

DECIMAL_CODE_TO_DIGITS: dict[int, int] = {
    0: 0,
    1: 1,
    2: 2,
    3: 3,
    4: 4,
}

# ---------------------------------------------------------------------------
# Status-word bit index → flag label
# ---------------------------------------------------------------------------

STATUS_FLAGS: dict[int, str] = {
    0: 'data_valid',
    1: 'peak_detecting',
    2: 'rom_fault',
    3: 'adc_fault',
    4: 'adc_signal_too_large',
    5: 'gross_overload',
    6: 'power_on_zero_failed',
    7: 'tare_condition_not_met',
    8: 'zero_range_exceeded',
    9: 'relay1_active',
    10: 'relay2_active',
    11: 'relay3_active',
}

# ---------------------------------------------------------------------------
# Board command name → register value
# ---------------------------------------------------------------------------

COMMANDS: dict[str, int] = {
    'tare_temp': 1,
    'tare_save': 2,
    'cancel_tare': 3,
    'zero_temp': 4,
    'zero_save': 5,
    'clear_peak': 6,
    'calibration': 7,
    'factory_reset': 9,
}

# ---------------------------------------------------------------------------
# Command metadata for UI rendering
# ---------------------------------------------------------------------------

COMMAND_METADATA: list[dict[str, str]] = [
    {
        'name': 'tare_temp',
        'title': 'Temporary tare',
        'description': 'Applies tare without retaining it across power loss.',
        'manual_equivalent': 'tPEEL / long-press tare key',
    },
    {
        'name': 'tare_save',
        'title': 'Saved tare',
        'description': 'Applies tare and preserves it across power cycles.',
        'manual_equivalent': 'SPEEL',
    },
    {
        'name': 'cancel_tare',
        'title': 'Cancel tare',
        'description': 'Clears the currently stored tare value.',
        'manual_equivalent': 'CPEEL',
    },
    {
        'name': 'zero_temp',
        'title': 'Temporary zero',
        'description': 'Performs a temporary zero action without saving it after power loss.',
        'manual_equivalent': 'SZEro / long-press zero key',
    },
    {
        'name': 'zero_save',
        'title': 'Saved zero calibration',
        'description': 'Stores the current zero point persistently.',
        'manual_equivalent': 'CZEro / 200.ZE',
    },
    {
        'name': 'clear_peak',
        'title': 'Clear peak',
        'description': 'Clears the captured peak value.',
        'manual_equivalent': 'REMAX / long-press ENT',
    },
    {
        'name': 'calibration',
        'title': 'Enter calibration flow',
        'description': 'Triggers the calibration command pathway exposed by the board.',
        'manual_equivalent': 'C2.CAL / calibration interface',
    },
    {
        'name': 'factory_reset',
        'title': 'Factory reset',
        'description': 'Restores factory-default parameters on the instrument.',
        'manual_equivalent': '116.FA Restore factory settings',
    },
]

# ---------------------------------------------------------------------------
# Default port-hint substrings used to score COM ports during discovery
# ---------------------------------------------------------------------------

DEFAULT_PORT_HINTS: list[str] = [
    'USB',
    'RS485',
    'FTDI',
    'CH340',
    'CP210',
    'PL2303',
    'ttyUSB',
    'ttyACM',
]

# ---------------------------------------------------------------------------
# Supported active-send parser profile (only binary Modbus profile is active)
# ---------------------------------------------------------------------------

#: The sole supported active-send parser profile.  ASCII/hex profiles were
#: removed because they do not provide the 11-register payload required for
#: calibration QA (see refactor plan §6.1).
ACTIVE_SEND_PARSER_PROFILE: str = 'modbus_rtu_response_11regs'
