from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Protocol

from omegaconf import DictConfig

LOGGER = logging.getLogger("handgrip_lsl_bridge.filter")


class SampleProcessor(Protocol):
    def process(self, value: float, sample_time_s: float) -> float:
        ...


class FilterNode(Protocol):
    def process(self, value: float, sample_time_s: float) -> float:
        ...


@dataclass(slots=True)
class FirstOrderLowPass:
    cutoff_hz: float
    reset_on_gap_s: float = 1.0
    min_dt_s: float = 1e-6

    def __post_init__(self) -> None:
        if self.cutoff_hz <= 0.0:
            raise ValueError(f"cutoff_hz must be > 0. Received {self.cutoff_hz}")
        self._tau = 1.0 / (2.0 * math.pi * self.cutoff_hz)
        self._last_time_s: float | None = None
        self._y: float | None = None

    def process(self, value: float, sample_time_s: float) -> float:
        if self._y is None or self._last_time_s is None:
            self._y = value
            self._last_time_s = sample_time_s
            return self._y

        dt = max(self.min_dt_s, sample_time_s - self._last_time_s)
        if dt > self.reset_on_gap_s:
            LOGGER.warning(
                "Low-pass filter state reset after large gap: dt=%.6fs > %.6fs",
                dt,
                self.reset_on_gap_s,
            )
            self._y = value
            self._last_time_s = sample_time_s
            return self._y

        alpha = dt / (self._tau + dt)
        self._y = self._y + alpha * (value - self._y)
        self._last_time_s = sample_time_s
        return self._y


@dataclass(slots=True)
class DriftCorrector:
    baseline_cutoff_hz: float = 0.02
    rest_band: float = 5.0
    stable_slope_threshold_per_s: float = 5.0
    warmup_samples: int = 20
    reset_on_gap_s: float = 1.0
    min_dt_s: float = 1e-6

    def __post_init__(self) -> None:
        if self.baseline_cutoff_hz <= 0.0:
            raise ValueError(
                f"baseline_cutoff_hz must be > 0. Received {self.baseline_cutoff_hz}"
            )
        if self.rest_band < 0.0:
            raise ValueError(f"rest_band must be >= 0. Received {self.rest_band}")
        if self.stable_slope_threshold_per_s < 0.0:
            raise ValueError(
                "stable_slope_threshold_per_s must be >= 0. "
                f"Received {self.stable_slope_threshold_per_s}"
            )
        self._tau = 1.0 / (2.0 * math.pi * self.baseline_cutoff_hz)
        self._baseline: float | None = None
        self._last_time_s: float | None = None
        self._last_input: float | None = None
        self._sample_count = 0

    def process(self, value: float, sample_time_s: float) -> float:
        if self._baseline is None or self._last_time_s is None or self._last_input is None:
            self._baseline = value
            self._last_time_s = sample_time_s
            self._last_input = value
            self._sample_count = 1
            return 0.0

        dt = max(self.min_dt_s, sample_time_s - self._last_time_s)
        if dt > self.reset_on_gap_s:
            LOGGER.warning(
                "Drift corrector state reset after large gap: dt=%.6fs > %.6fs",
                dt,
                self.reset_on_gap_s,
            )
            self._baseline = value
            self._last_time_s = sample_time_s
            self._last_input = value
            self._sample_count = 1
            return 0.0

        slope = abs(value - self._last_input) / dt
        near_rest = abs(value - self._baseline) <= self.rest_band
        stable = slope <= self.stable_slope_threshold_per_s

        # Update the baseline only when the signal is likely near rest / drift-dominated.
        if self._sample_count < self.warmup_samples or near_rest or stable:
            alpha = dt / (self._tau + dt)
            self._baseline = self._baseline + alpha * (value - self._baseline)

        corrected = value - self._baseline
        self._last_input = value
        self._last_time_s = sample_time_s
        self._sample_count += 1
        return corrected


class FilterPipeline:
    def __init__(self, filters: list[FilterNode]) -> None:
        self._filters = filters

    def process(self, value: float, sample_time_s: float) -> float:
        y = value
        for filter_node in self._filters:
            y = filter_node.process(y, sample_time_s)
        return y

    @property
    def filters(self) -> list[FilterNode]:
        return list(self._filters)


class IdentityProcessor:
    def process(self, value: float, sample_time_s: float) -> float:
        _ = sample_time_s
        return value



def _build_filter_node(filter_cfg: DictConfig) -> FilterNode:
    filter_type = str(filter_cfg.type)

    if filter_type == "lowpass_1pole":
        return FirstOrderLowPass(
            cutoff_hz=float(filter_cfg.cutoff_hz),
            reset_on_gap_s=float(filter_cfg.get("reset_on_gap_s", 1.0)),
            min_dt_s=float(filter_cfg.get("min_dt_s", 1e-6)),
        )

    if filter_type == "drift_corrector":
        return DriftCorrector(
            baseline_cutoff_hz=float(filter_cfg.get("baseline_cutoff_hz", 0.02)),
            rest_band=float(filter_cfg.get("rest_band", 5.0)),
            stable_slope_threshold_per_s=float(filter_cfg.get("stable_slope_threshold_per_s", 5.0)),
            warmup_samples=int(filter_cfg.get("warmup_samples", 20)),
            reset_on_gap_s=float(filter_cfg.get("reset_on_gap_s", 1.0)),
            min_dt_s=float(filter_cfg.get("min_dt_s", 1e-6)),
        )

    if filter_type == "identity":
        return IdentityProcessor()

    raise ValueError(f"Unsupported filter type: {filter_type}")


class ProcessorAdapter:
    def __init__(self, cfg: DictConfig) -> None:
        filters_cfg = list(cfg.filters) if cfg.get("filters") is not None else []
        self._pipeline = FilterPipeline([_build_filter_node(filter_cfg) for filter_cfg in filters_cfg])

    def process(self, value: float, sample_time_s: float) -> float:
        return self._pipeline.process(value, sample_time_s)

    @property
    def filters(self) -> list[FilterNode]:
        return self._pipeline.filters



def build_processor(cfg: DictConfig) -> ProcessorAdapter:
    processor = ProcessorAdapter(cfg)
    LOGGER.info(
        "Initialized placeholder processor with filter chain: %s",
        ", ".join(type(filter_node).__name__ for filter_node in processor.filters) or "<empty>",
    )
    return processor
