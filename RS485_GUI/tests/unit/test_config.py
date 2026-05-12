"""Unit tests for rs485_gui.config.loader."""
from __future__ import annotations

import logging

import pytest
from omegaconf import OmegaConf

# Point loader at the real config file
from rs485_gui.config.loader import configure_logging, load_app_config


class TestLoadAppConfig:
    def test_loads_without_overrides(self):
        cfg = load_app_config(argv=[])
        assert cfg.ui.port == 8088
        assert cfg.device.mode in {'active_send', 'modbus_rtu'}

    def test_dotlist_override_applied(self):
        cfg = load_app_config(argv=['ui.port=9999'])
        assert cfg.ui.port == 9999

    def test_hydra_flags_ignored(self):
        # Should not raise
        cfg = load_app_config(argv=['hydra.run.dir=.', 'ui.port=8088'])
        assert cfg.ui.port == 8088

    def test_help_raises_system_exit(self):
        with pytest.raises(SystemExit):
            load_app_config(argv=['--help'])


class TestConfigureLogging:
    def setup_method(self):
        # Reset root logger handlers and the idempotency sentinel before each test
        import rs485_gui.config.loader as _loader
        _loader._LOGGING_CONFIGURED = False
        root = logging.getLogger()
        root.handlers.clear()

    def test_adds_stream_handler(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = OmegaConf.create({
            'app': {'log_level': 'INFO'},
            'logger': {
                'debug_log_to_file': False,
                'directory': str(tmp_path / 'logs'),
                'debug_log_filename': 'debug.log',
                'write_mode': 'overwrite',
            },
        })
        configure_logging(cfg)
        root = logging.getLogger()
        assert any(isinstance(h, logging.StreamHandler) for h in root.handlers)

    def test_idempotent_second_call(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = OmegaConf.create({
            'app': {'log_level': 'INFO'},
            'logger': {
                'debug_log_to_file': False,
                'directory': str(tmp_path / 'logs'),
                'debug_log_filename': 'debug.log',
                'write_mode': 'overwrite',
            },
        })
        configure_logging(cfg)
        n_handlers = len(logging.getLogger().handlers)
        configure_logging(cfg)  # second call must be a no-op
        assert len(logging.getLogger().handlers) == n_handlers

    def test_file_handler_created_when_enabled(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        log_dir = tmp_path / 'logs'
        cfg = OmegaConf.create({
            'app': {'log_level': 'DEBUG'},
            'logger': {
                'debug_log_to_file': True,
                'directory': str(log_dir),
                'debug_log_filename': 'test.log',
                'write_mode': 'overwrite',
            },
        })
        configure_logging(cfg)
        assert any(isinstance(h, logging.FileHandler) for h in logging.getLogger().handlers)
        assert (log_dir / 'test.log').exists()
