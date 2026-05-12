"""Integration test for core.replay.load_csv_replay.

Creates minimal fixture CSV files and verifies that load_csv_replay
produces the correct DualReplayData with the expected shape and content.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from omegaconf import OmegaConf


@pytest.fixture
def fixture_csv_dir(tmp_path: Path) -> Path:
    """Write minimal dual-stream CSVs to a temp directory."""
    n_target = 20
    n_reference = 100
    target_rate = 100.0
    reference_rate = 500.0

    target_ts = np.arange(n_target, dtype=np.float64) / target_rate
    ref_ts = np.arange(n_reference, dtype=np.float64) / reference_rate

    target_df = pd.DataFrame({
        "lsl_timestamp_s": target_ts,
        "device_clock_us": target_ts * 1e6,
        "target_raw_count": np.sin(target_ts),
        "target_filtered_units": np.sin(target_ts) * 0.9,
    })
    reference_df = pd.DataFrame({
        "lsl_timestamp_s": ref_ts,
        "reference_clock_s": ref_ts,
        "reference_force_N": np.cos(ref_ts) * 2.0,
    })

    target_path = tmp_path / "target_handgrip_samples_v2.csv"
    reference_path = tmp_path / "reference_rs485_samples_v2.csv"
    target_df.to_csv(target_path, index=False)
    reference_df.to_csv(reference_path, index=False)
    return tmp_path


@pytest.fixture
def cfg(fixture_csv_dir: Path):
    """Minimal Hydra-compatible DictConfig for csv_replay mode."""
    raw = {
        "mode": "csv_replay",
        "streams": {
            "target": {"expected_rate_hz": 100.0},
            "reference": {"expected_rate_hz": 500.0},
        },
        "channels": {
            "target": {
                "clock_label": "device_clock_us",
                "raw_label": "target_raw_count",
                "filtered_label": "target_filtered_units",
            },
            "reference": {
                "clock_label": "reference_clock_s",
                "raw_label": "reference_force_N",
            },
        },
        "viewer": {"expected_target_rate_hz": 100.0},
        "reference": {
            "target_csv_path": str(fixture_csv_dir / "target_handgrip_samples_v2.csv"),
            "reference_csv_path": str(
                fixture_csv_dir / "reference_rs485_samples_v2.csv"
            ),
        },
    }
    return OmegaConf.create(raw)


class TestLoadCsvReplay:
    def test_returns_dual_replay_data(self, cfg):
        from lsl_viewer.core.replay import load_csv_replay
        data = load_csv_replay(cfg)
        assert data.target_timestamps_s.size == 20
        assert data.reference_timestamps_s.size == 100

    def test_timestamps_start_at_zero(self, cfg):
        from lsl_viewer.core.replay import load_csv_replay
        data = load_csv_replay(cfg)
        assert math.isclose(float(data.target_timestamps_s[0]), 0.0, abs_tol=1e-9)

    def test_source_type_label(self, cfg):
        from lsl_viewer.core.replay import load_csv_replay
        data = load_csv_replay(cfg)
        assert data.source_type == "csv_replay_dual_native_v2"

    def test_raw_values_are_numeric(self, cfg):
        from lsl_viewer.core.replay import load_csv_replay
        data = load_csv_replay(cfg)
        assert np.all(np.isfinite(data.target_raw))
        assert np.all(np.isfinite(data.reference_raw))

    def test_missing_path_raises(self):
        from lsl_viewer.core.replay import load_csv_replay
        cfg_bad = OmegaConf.create({"reference": {"target_csv_path": None, "reference_csv_path": None}})
        with pytest.raises(RuntimeError, match="csv_replay requires"):
            load_csv_replay(cfg_bad)
