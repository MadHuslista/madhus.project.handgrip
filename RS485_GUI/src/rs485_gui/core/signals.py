"""Signal key resolution, metadata, and value extraction helpers.

``SIGNAL_DEFINITIONS`` is the authoritative registry of signals that the
GUI can plot and that the IPC publisher can stream.  Each entry describes
the computation path so that operators can understand what they are seeing.

Dependency chain: models  (no I/O, no UI)
"""
from __future__ import annotations

import logging

from omegaconf import DictConfig

from rs485_gui.models import MeasurementFrame

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Signal registry
# ---------------------------------------------------------------------------

SIGNAL_DEFINITIONS: dict[str, dict[str, str]] = {
    'gross_value': {
        'label': 'gross_value',
        'description': (
            'Gross interpreted engineering value after applying the board decimal scaling.'
        ),
        'unit_hint': 'Board-selected engineering unit.',
        'source': 'gross_raw_value + decimal_code',
    },
    'net_value': {
        'label': 'net_value',
        'description': (
            'Net interpreted engineering value after tare/zero handling and decimal scaling.'
        ),
        'unit_hint': 'Board-selected engineering unit.',
        'source': 'net_raw_value + decimal_code',
    },
    'peak_value': {
        'label': 'peak_value',
        'description': 'Peak interpreted engineering value after decimal scaling.',
        'unit_hint': 'Board-selected engineering unit.',
        'source': 'peak_raw_value + decimal_code',
    },
    'gross_raw_value': {
        'label': 'gross_raw_value',
        'description': 'Raw signed 32-bit gross reading straight from the Modbus register pair.',
        'unit_hint': 'Raw ADC-domain board value; decimal scaling not applied.',
        'source': 'registers 40001/40002',
    },
    'net_raw_value': {
        'label': 'net_raw_value',
        'description': 'Raw signed 32-bit net reading straight from the Modbus register pair.',
        'unit_hint': 'Raw ADC-domain board value; decimal scaling not applied.',
        'source': 'registers 40003/40004',
    },
    'peak_raw_value': {
        'label': 'peak_raw_value',
        'description': 'Raw signed 32-bit peak reading straight from the Modbus register pair.',
        'unit_hint': 'Raw ADC-domain board value; decimal scaling not applied.',
        'source': 'registers 40005/40006',
    },
    'internal_code_raw_value': {
        'label': 'internal_code_raw_value',
        'description': 'Raw internal ADC code / internal measurement code exposed by the board.',
        'unit_hint': 'Internal board code; not an engineering unit.',
        'source': 'registers 40007/40008',
    },
    'raw_value': {
        'label': 'raw_value',
        'description': (
            'Compatibility alias for the primary raw plotted value. '
            'In Modbus decoding it maps to gross_raw_value.'
        ),
        'unit_hint': 'Depends on parser profile; often raw board integer.',
        'source': 'parser-dependent primary numeric output',
    },
}


# ---------------------------------------------------------------------------
# Signal key helpers
# ---------------------------------------------------------------------------

def get_plot_signal_key(cfg: DictConfig) -> str:
    """Return the currently configured signal key for plotting."""
    default_key = str(cfg.ui.default_plot_signal_key)
    return str(getattr(cfg.ui, 'plot_signal_key', default_key))


## @brief Get plot signal label.
#
#  @param cfg Parameter description.
#  @return Retrieved value for this request.
def get_plot_signal_label(cfg: DictConfig) -> str:
    """Return a human-readable label for the currently configured plot signal."""
    signal_key = get_plot_signal_key(cfg)
    meta = SIGNAL_DEFINITIONS.get(signal_key, {})
    return str(meta.get('label', signal_key))


## @brief Get plot signal options.
#
#  @return Retrieved value for this request.
def get_plot_signal_options() -> dict[str, str]:
    """Return a ``{key: label}`` dict suitable for a NiceGUI select widget."""
    return {key: meta.get('label', key) for key, meta in SIGNAL_DEFINITIONS.items()}


## @brief Extract signal value.
#
#  @param frame Parameter description.
#  @param signal_key Parameter description.
#  @return Result produced by this function.
def extract_signal_value(frame: MeasurementFrame, signal_key: str) -> float | None:
    """Extract a numeric signal value from *frame.interpreted*.

    Returns ``None`` if the key is absent or cannot be cast to float.
    """
    value = frame.interpreted.get(signal_key)
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


## @brief Extract plot value.
#
#  @param frame Parameter description.
#  @param cfg Parameter description.
#  @return Result produced by this function.
def extract_plot_value(frame: MeasurementFrame, cfg: DictConfig) -> float | None:
    """Convenience wrapper that extracts the currently configured plot signal."""
    return extract_signal_value(frame, get_plot_signal_key(cfg))


# ---------------------------------------------------------------------------
# Metadata display
# ---------------------------------------------------------------------------

def build_signal_metadata_text(
    latest_frame: MeasurementFrame | None,
    frame_history: list[MeasurementFrame],
    cfg: DictConfig,
) -> str:
    """Build the multi-line metadata string shown in the 'Selected signal info' panel."""
    signal_key = get_plot_signal_key(cfg)
    meta = SIGNAL_DEFINITIONS.get(
        signal_key,
        {
            'label': signal_key,
            'description': 'No metadata available.',
            'unit_hint': 'n/a',
            'source': signal_key,
        },
    )

    selected_values = [
        v for v in (extract_signal_value(f, signal_key) for f in frame_history)
        if v is not None
    ]
    if selected_values:
        value_range_line = (
            f'Visible range: min={min(selected_values):.6g}, max={max(selected_values):.6g}'
        )
    else:
        value_range_line = 'Visible range: n/a'

    lines = [
        f'Selected signal: {meta.get("label", signal_key)}',
        f'Description: {meta.get("description", "n/a")}',
        f'Calculation/source: {meta.get("source", signal_key)}',
        f'Unit hint: {meta.get("unit_hint", "n/a")}',
        value_range_line,
    ]

    if latest_frame is None:
        lines.append('Latest frame metadata: no samples received yet.')
        return '\n'.join(lines)

    interpreted = latest_frame.interpreted
    status_flags = interpreted.get('status_flags')
    if isinstance(status_flags, list):
        status_text = ', '.join(str(f) for f in status_flags) if status_flags else 'none'
    else:
        status_text = str(status_flags)

    lines.extend([
        'Latest frame metadata:',
        f'  decimal_code: {interpreted.get("decimal_code", "n/a")}'
        '  -> board decimal-point code used for engineering-value scaling',
        f'  unit_code: {interpreted.get("unit_code", "n/a")}'
        '  -> board engineering-unit code',
        f'  unit_label: {interpreted.get("unit_label", "n/a")}'
        '  -> decoded engineering unit label',
        f'  status_word: {interpreted.get("status_word", "n/a")}'
        '  -> raw board status bitfield',
        f'  status_flags: {status_text}'
        '  -> decoded status bits / relay / alarm states',
        f'  parsed_from: {interpreted.get("parsed_from", "n/a")}'
        '  -> decoder path used to build the plotted value',
        f'  timestamp_source: {interpreted.get("timestamp_source", "n/a")}'
        '  -> origin of the assigned sample timestamp',
        f'  timestamp_host_iso: {interpreted.get("timestamp_host_iso", "n/a")}'
        '  -> latest assigned host timestamp',
    ])
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------

def format_rate(value: float | None) -> str:
    """Format a Hz value for display, handling None / zero / unlimited."""
    if value is None:
        return 'n/a'
    if value <= 0:
        return 'unlimited'
    return f'{value:.3f} Hz'


## @brief Get target sampling rate hz.
#
#  @param cfg Parameter description.
#  @param mode Parameter description.
#  @return Retrieved value for this request.
def get_target_sampling_rate_hz(
    cfg: DictConfig, mode: str
) -> float | None:
    """Return the configured target acquisition rate in Hz for *mode*."""
    from rs485_gui.constants import ACTIVE_SEND_FREQ_CODE_TO_VALUE

    if mode == 'active_send':
        return float(
            ACTIVE_SEND_FREQ_CODE_TO_VALUE.get(int(cfg.device.active_send_frequency_code), 0)
            or 0
        )
    poll_interval_s = float(cfg.device.poll_interval_s or 0.0)
    if poll_interval_s <= 0:
        return None
    return 1.0 / poll_interval_s
