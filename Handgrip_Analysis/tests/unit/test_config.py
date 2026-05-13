"""
Unit tests for handgrip_analysis.config structured configurations.

All tests are pure dataclass construction — no I/O, no Hydra runtime.
"""

from __future__ import annotations

import pytest
from handgrip_analysis.config import (
    AppConfig,
    DSPConfig,
    EventDetectionConfig,
    LoggingConfig,
    PlotConfig,
    PsdPeaksConfig,
    WelchConfig,
)
from handgrip_analysis.config.schema import Stage6ScoringConfig

# ---------------------------------------------------------------------------
# WelchConfig
# ---------------------------------------------------------------------------


class TestWelchConfig:
    def test_defaults(self):
        cfg = WelchConfig()
        assert cfg.max_nperseg == 2048
        assert cfg.min_nperseg == 256
        assert cfg.window == "hann"

    def test_from_mapping_partial(self):
        cfg = WelchConfig.from_mapping({"max_nperseg": 1024})
        assert cfg.max_nperseg == 1024
        assert cfg.min_nperseg == 256  # default preserved

    def test_from_mapping_full(self):
        cfg = WelchConfig.from_mapping({"max_nperseg": 512, "min_nperseg": 128, "window": "hamming"})
        assert cfg.max_nperseg == 512
        assert cfg.min_nperseg == 128
        assert cfg.window == "hamming"

    def test_from_mapping_ignores_unknown_keys(self):
        cfg = WelchConfig.from_mapping({"max_nperseg": 512, "unknown_key": 99})
        assert cfg.max_nperseg == 512

    def test_validation_min_nperseg_too_small(self):
        with pytest.raises(ValueError, match="min_nperseg"):
            WelchConfig(min_nperseg=1)

    def test_validation_max_less_than_min(self):
        with pytest.raises(ValueError, match="max_nperseg"):
            WelchConfig(max_nperseg=128, min_nperseg=256)


# ---------------------------------------------------------------------------
# EventDetectionConfig
# ---------------------------------------------------------------------------

class TestEventDetectionConfig:
    def test_defaults(self):
        cfg = EventDetectionConfig()
        assert cfg.baseline_s == pytest.approx(2.0)
        assert cfg.threshold_sigma == pytest.approx(5.0)
        assert cfg.min_duration_s == pytest.approx(0.20)
        assert cfg.merge_gap_s == pytest.approx(0.15)
        assert cfg.pad_s == pytest.approx(0.25)
        assert cfg.tail_fraction == pytest.approx(0.80)

    def test_from_mapping_partial(self):
        cfg = EventDetectionConfig.from_mapping({"threshold_sigma": 3.0})
        assert cfg.threshold_sigma == pytest.approx(3.0)
        assert cfg.baseline_s == pytest.approx(2.0)  # default

    def test_validation_tail_fraction_out_of_range(self):
        with pytest.raises(ValueError, match="tail_fraction"):
            EventDetectionConfig(tail_fraction=1.5)

    def test_validation_tail_fraction_zero(self):
        with pytest.raises(ValueError, match="tail_fraction"):
            EventDetectionConfig(tail_fraction=0.0)

    def test_validation_threshold_sigma_negative(self):
        with pytest.raises(ValueError, match="threshold_sigma"):
            EventDetectionConfig(threshold_sigma=-1.0)


# ---------------------------------------------------------------------------
# PsdPeaksConfig
# ---------------------------------------------------------------------------

class TestPsdPeaksConfig:
    def test_defaults(self):
        cfg = PsdPeaksConfig()
        assert cfg.prominence_db == pytest.approx(3.0)
        assert cfg.max_peaks == 8

    def test_from_mapping(self):
        cfg = PsdPeaksConfig.from_mapping({"prominence_db": 6.0, "max_peaks": 4})
        assert cfg.prominence_db == pytest.approx(6.0)
        assert cfg.max_peaks == 4

    def test_validation_negative_prominence(self):
        with pytest.raises(ValueError, match="prominence_db"):
            PsdPeaksConfig(prominence_db=-1.0)

    def test_validation_zero_max_peaks(self):
        with pytest.raises(ValueError, match="max_peaks"):
            PsdPeaksConfig(max_peaks=0)


# ---------------------------------------------------------------------------
# PlotConfig
# ---------------------------------------------------------------------------

class TestPlotConfig:
    def test_defaults(self):
        cfg = PlotConfig()
        assert cfg.dpi == 150
        assert cfg.figsize_wide == pytest.approx((12.0, 5.0))
        assert cfg.figsize_square == pytest.approx((10.0, 5.0))

    def test_from_mapping_list_input(self):
        cfg = PlotConfig.from_mapping({"figsize_wide": [14, 6], "dpi": 200})
        assert cfg.figsize_wide == pytest.approx((14.0, 6.0))
        assert cfg.dpi == 200

    def test_validation_dpi_zero(self):
        with pytest.raises(ValueError, match="dpi"):
            PlotConfig(dpi=0)


# ---------------------------------------------------------------------------
# DSPConfig
# ---------------------------------------------------------------------------

class TestDSPConfig:
    def test_defaults(self):
        cfg = DSPConfig()
        assert isinstance(cfg.welch, WelchConfig)
        assert isinstance(cfg.event_detection, EventDetectionConfig)
        assert isinstance(cfg.psd_peaks, PsdPeaksConfig)
        assert isinstance(cfg.plot, PlotConfig)

    def test_from_mapping_nested(self):
        cfg = DSPConfig.from_mapping({
            "welch": {"max_nperseg": 1024, "window": "blackman"},
            "psd_peaks": {"max_peaks": 4},
        })
        assert cfg.welch.max_nperseg == 1024
        assert cfg.welch.window == "blackman"
        assert cfg.psd_peaks.max_peaks == 4
        assert cfg.event_detection.baseline_s == pytest.approx(2.0)  # default

    def test_from_mapping_empty(self):
        cfg = DSPConfig.from_mapping({})
        assert cfg.welch.max_nperseg == 2048  # defaults survive


# ---------------------------------------------------------------------------
# LoggingConfig
# ---------------------------------------------------------------------------

class TestLoggingConfig:
    def test_defaults(self):
        cfg = LoggingConfig()
        assert cfg.level == "INFO"
        assert cfg.file is None

    def test_from_mapping_with_file(self):
        cfg = LoggingConfig.from_mapping({"level": "DEBUG", "file": "/tmp/out.log"})
        assert cfg.level == "DEBUG"
        assert cfg.file == "/tmp/out.log"

    def test_validation_invalid_level(self):
        with pytest.raises(ValueError, match="level"):
            LoggingConfig(level="VERBOSE")


# ---------------------------------------------------------------------------
# Stage6ScoringConfig
# ---------------------------------------------------------------------------

class TestStage6ScoringConfig:
    def test_defaults(self):
        cfg = Stage6ScoringConfig()
        assert cfg.review_weight == pytest.approx(0.7)
        assert cfg.design_weight == pytest.approx(0.3)

    def test_weights_sum_to_one(self):
        cfg = Stage6ScoringConfig(review_weight=0.6, design_weight=0.4)
        assert cfg.review_weight + cfg.design_weight == pytest.approx(1.0)

    def test_validation_weights_not_sum_to_one(self):
        with pytest.raises(ValueError, match="sum to 1.0"):
            Stage6ScoringConfig(review_weight=0.5, design_weight=0.4)

    def test_from_mapping(self):
        cfg = Stage6ScoringConfig.from_mapping({"review_weight": 0.8, "design_weight": 0.2})
        assert cfg.review_weight == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# AppConfig
# ---------------------------------------------------------------------------

class TestAppConfig:
    def test_defaults(self):
        cfg = AppConfig()
        assert isinstance(cfg.dsp, DSPConfig)
        assert isinstance(cfg.logging, LoggingConfig)
        assert isinstance(cfg.stage6_scoring, Stage6ScoringConfig)

    def test_from_mapping_nested(self):
        cfg = AppConfig.from_mapping({
            "dsp": {"welch": {"max_nperseg": 512}},
            "logging": {"level": "DEBUG"},
            "stage6_scoring": {"review_weight": 0.6, "design_weight": 0.4},
        })
        assert cfg.dsp.welch.max_nperseg == 512
        assert cfg.logging.level == "DEBUG"
        assert cfg.stage6_scoring.review_weight == pytest.approx(0.6)

    def test_from_mapping_none(self):
        cfg = AppConfig.from_mapping(None)
        assert cfg.dsp.welch.max_nperseg == 2048
