"""Integration tests for rs485_gui.io.logger.SignalFileLogger."""

from __future__ import annotations

import json

import pytest
from omegaconf import OmegaConf

from rs485_gui.io.logger import SignalFileLogger
from rs485_gui.models import MeasurementFrame


def _make_cfg(tmp_path, write_mode="overwrite"):
    return OmegaConf.create(
        {
            "logger": {
                "enabled": True,
                "directory": str(tmp_path / "logs"),
                "write_mode": write_mode,
                "raw_signal_filename": "raw.ndjson",
                "interpreted_signal_filename": "interp.ndjson",
                "gui_signal_filename": "gui.csv",
                "event_log_filename": "events.log",
                "flush_every_n_batches": 1,
                "flush_interval_s": 0.0,
            },
            "ui": {
                "default_plot_signal_key": "net_value",
                "plot_signal_key": "net_value",
            },
        }
    )


def _make_frame(net_value=10.0):
    return MeasurementFrame(
        host_ts=1000.0,
        host_ts_iso="2024-01-01T00:00:00.000",
        mode="active_send",
        raw_transport={"response_hex": "aa bb cc"},
        interpreted={
            "net_value": net_value,
            "gross_value": net_value + 1.0,
            "reference_force_N": net_value,
            "reference_clock_s": 1000.0,
            "reference_status": 0,
        },
        session_id="test-session",
    )


class TestSignalFileLogger:
    def test_open_creates_files(self, tmp_path):
        cfg = _make_cfg(tmp_path)
        logger = SignalFileLogger(cfg)
        logger.open()
        log_dir = tmp_path / "logs"
        assert (log_dir / "raw.ndjson").exists()
        assert (log_dir / "interp.ndjson").exists()
        assert (log_dir / "gui.csv").exists()
        assert (log_dir / "events.log").exists()
        logger.close()

    def test_write_frame_creates_ndjson_lines(self, tmp_path):
        cfg = _make_cfg(tmp_path)
        logger = SignalFileLogger(cfg)
        logger.open()
        logger.write_frame(_make_frame(net_value=42.0))
        logger.close()
        lines = (tmp_path / "logs" / "raw.ndjson").read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["mode"] == "active_send"

    def test_write_frames_batch(self, tmp_path):
        cfg = _make_cfg(tmp_path)
        logger = SignalFileLogger(cfg)
        logger.open()
        frames = [_make_frame(net_value=float(i)) for i in range(5)]
        logger.write_frames(frames)
        logger.close()
        lines = (tmp_path / "logs" / "interp.ndjson").read_text().strip().splitlines()
        assert len(lines) == 5

    def test_csv_header_written_on_overwrite(self, tmp_path):
        cfg = _make_cfg(tmp_path)
        logger = SignalFileLogger(cfg)
        logger.open()
        logger.close()
        csv_text = (tmp_path / "logs" / "gui.csv").read_text()
        assert "reference_force_N" in csv_text

    def test_write_event(self, tmp_path):
        cfg = _make_cfg(tmp_path)
        logger = SignalFileLogger(cfg)
        logger.open()
        logger.write_event("test event message")
        logger.close()
        content = (tmp_path / "logs" / "events.log").read_text()
        assert "test event message" in content

    def test_disabled_logger_creates_no_files(self, tmp_path):
        cfg = _make_cfg(tmp_path)
        cfg.logger.enabled = False
        logger = SignalFileLogger(cfg)
        logger.open()
        logger.write_frame(_make_frame())
        logger.close()
        log_dir = tmp_path / "logs"
        assert not log_dir.exists()

    def test_write_before_open_raises(self, tmp_path):
        cfg = _make_cfg(tmp_path)
        logger = SignalFileLogger(cfg)
        with pytest.raises(RuntimeError, match="before open"):
            logger.write_frames([_make_frame()])
