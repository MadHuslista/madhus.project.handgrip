"""Unit tests for rs485_gui.core.signals."""
from __future__ import annotations

import pytest
from omegaconf import OmegaConf

from rs485_gui.core.signals import (
    SIGNAL_DEFINITIONS,
    extract_signal_value,
    get_plot_signal_key,
    get_plot_signal_options,
)
from rs485_gui.models import MeasurementFrame


def _make_frame(**interpreted_extra):
    interpreted = {'net_value': 42.0, 'gross_value': 43.0, **interpreted_extra}
    return MeasurementFrame(
        host_ts=1000.0,
        host_ts_iso='2024-01-01T00:00:00.000',
        mode='active_send',
        raw_transport={},
        interpreted=interpreted,
    )


def _make_cfg(plot_signal_key='net_value'):
    return OmegaConf.create({'ui': {'default_plot_signal_key': plot_signal_key, 'plot_signal_key': plot_signal_key}})


class TestExtractSignalValue:
    def test_present_numeric(self):
        frame = _make_frame()
        assert extract_signal_value(frame, 'net_value') == pytest.approx(42.0)

    def test_missing_key_returns_none(self):
        frame = _make_frame()
        assert extract_signal_value(frame, 'nonexistent') is None

    def test_non_numeric_returns_none(self):
        frame = _make_frame(bad_key='not_a_number')
        assert extract_signal_value(frame, 'bad_key') is None


class TestGetPlotSignalKey:
    def test_default(self):
        cfg = _make_cfg('net_value')
        assert get_plot_signal_key(cfg) == 'net_value'

    def test_override(self):
        cfg = _make_cfg('gross_value')
        assert get_plot_signal_key(cfg) == 'gross_value'


class TestSignalDefinitions:
    def test_all_required_keys_present(self):
        required = {'label', 'description', 'unit_hint', 'source'}
        for key, meta in SIGNAL_DEFINITIONS.items():
            missing = required - set(meta.keys())
            assert not missing, f'{key} missing fields: {missing}'

    def test_net_value_defined(self):
        assert 'net_value' in SIGNAL_DEFINITIONS

    def test_options_dict(self):
        opts = get_plot_signal_options()
        assert 'net_value' in opts
        assert isinstance(opts['net_value'], str)
