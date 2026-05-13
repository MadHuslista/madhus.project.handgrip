"""Structured configuration for DSP algorithm parameters.

These dataclasses mirror ``conf/dsp/defaults.yaml`` and serve as the
single source of truth for all DSP tuning constants.  Any value defined
in the YAML that is not reflected here is *decorative only* and has no
runtime effect — the purpose of this module is to close that gap.

Default values are kept in sync with ``conf/dsp/defaults.yaml``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


# ---------------------------------------------------------------------------
# Welch PSD computation
# ---------------------------------------------------------------------------

@dataclass
class WelchConfig:
    """Parameters for scipy.signal.welch PSD estimation.

    Attributes
    ----------
    max_nperseg:
        Upper bound on the FFT segment length (samples).
    min_nperseg:
        Lower bound on the FFT segment length (samples).
    window:
        Window function name recognised by ``scipy.signal.welch``.
    """

    max_nperseg: int = 2048
    min_nperseg: int = 256
    window: str = "hann"

    def __post_init__(self) -> None:
        if self.min_nperseg < 2:
            raise ValueError("WelchConfig.min_nperseg must be >= 2")
        if self.max_nperseg < self.min_nperseg:
            raise ValueError("WelchConfig.max_nperseg must be >= min_nperseg")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "WelchConfig":
        allowed = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in allowed})


# ---------------------------------------------------------------------------
# Event detection
# ---------------------------------------------------------------------------

@dataclass
class EventDetectionConfig:
    """Parameters for grip-event detection in dynamic trials.

    Attributes
    ----------
    baseline_s:
        Duration of the initial window used to estimate the noise floor.
    threshold_sigma:
        Event-onset threshold expressed as multiples of the robust std above
        the baseline centre.
    min_duration_s:
        Discard candidate events shorter than this.
    merge_gap_s:
        Merge adjacent events separated by less than this gap.
    pad_s:
        Symmetric padding applied to each detected event boundary.
    tail_fraction:
        Fraction of the signal used to characterise the "tail" when suggesting
        the sensor ready-time (``suggest_ready_time``).
    """

    baseline_s: float = 2.0
    threshold_sigma: float = 5.0
    min_duration_s: float = 0.20
    merge_gap_s: float = 0.15
    pad_s: float = 0.25
    tail_fraction: float = 0.80

    def __post_init__(self) -> None:
        if not 0.0 < self.tail_fraction < 1.0:
            raise ValueError("EventDetectionConfig.tail_fraction must be in (0, 1)")
        if self.threshold_sigma <= 0:
            raise ValueError("EventDetectionConfig.threshold_sigma must be positive")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "EventDetectionConfig":
        allowed = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in allowed})


# ---------------------------------------------------------------------------
# PSD peak finder
# ---------------------------------------------------------------------------

@dataclass
class PsdPeaksConfig:
    """Parameters for the dominant-peak finder applied to Welch PSD spectra.

    Attributes
    ----------
    prominence_db:
        Minimum peak prominence in dB relative to surrounding noise to qualify
        as a reportable spectral peak.
    max_peaks:
        Maximum number of peaks to return (sorted by prominence, descending).
    """

    prominence_db: float = 3.0
    max_peaks: int = 8

    def __post_init__(self) -> None:
        if self.prominence_db < 0:
            raise ValueError("PsdPeaksConfig.prominence_db must be >= 0")
        if self.max_peaks < 1:
            raise ValueError("PsdPeaksConfig.max_peaks must be >= 1")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "PsdPeaksConfig":
        allowed = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in allowed})


# ---------------------------------------------------------------------------
# Plot output
# ---------------------------------------------------------------------------

@dataclass
class PlotConfig:
    """Parameters controlling figure output quality and dimensions.

    Attributes
    ----------
    dpi:
        Dots-per-inch for saved figures.
    figsize_wide:
        ``(width, height)`` in inches for wide time-series plots.
    figsize_square:
        ``(width, height)`` in inches for PSD / histogram comparison plots.
    """

    dpi: int = 150
    figsize_wide: tuple[float, float] = (12.0, 5.0)
    figsize_square: tuple[float, float] = (10.0, 5.0)

    def __post_init__(self) -> None:
        if self.dpi < 1:
            raise ValueError("PlotConfig.dpi must be >= 1")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "PlotConfig":
        kwargs: dict[str, Any] = {}
        for key in ("dpi",):
            if key in data:
                kwargs[key] = data[key]
        for key in ("figsize_wide", "figsize_square"):
            if key in data:
                raw = data[key]
                kwargs[key] = (float(raw[0]), float(raw[1]))
        return cls(**kwargs)


# ---------------------------------------------------------------------------
# Composite DSP config
# ---------------------------------------------------------------------------

@dataclass
class DSPConfig:
    """Top-level DSP configuration, combining all DSP sub-configs.

    Mirrors the structure of ``conf/dsp/defaults.yaml``.

    Example
    -------
    Construct from a Hydra/OmegaConf DictConfig after converting to a dict::

        from omegaconf import OmegaConf
        cfg = OmegaConf.to_container(hydra_cfg.dsp, resolve=True)
        dsp = DSPConfig.from_mapping(cfg)
    """

    welch: WelchConfig = field(default_factory=WelchConfig)
    event_detection: EventDetectionConfig = field(default_factory=EventDetectionConfig)
    psd_peaks: PsdPeaksConfig = field(default_factory=PsdPeaksConfig)
    plot: PlotConfig = field(default_factory=PlotConfig)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None = None) -> "DSPConfig":
        """Build a ``DSPConfig`` from a nested mapping (e.g. OmegaConf dict).

        Missing sub-keys fall back to dataclass defaults.
        """
        data = dict(data or {})
        welch = WelchConfig.from_mapping(data.get("welch") or {})
        event = EventDetectionConfig.from_mapping(data.get("event_detection") or {})
        peaks = PsdPeaksConfig.from_mapping(data.get("psd_peaks") or {})
        plot = PlotConfig.from_mapping(data.get("plot") or {})
        return cls(welch=welch, event_detection=event, psd_peaks=peaks, plot=plot)
