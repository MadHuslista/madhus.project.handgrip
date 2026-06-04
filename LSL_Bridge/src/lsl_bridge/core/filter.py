# @package lsl_bridge.core.filter
#  @brief Signal-filter primitives and config-driven processor assembly.
##
"""
Signal processing filters for the LSL Bridge target stream.

This module provides a small library of stateful digital filters and a
Hydra-config-driven factory (``build_processor``) that assembles them into
a ``FilterPipeline``.

Filter classes are pure in the sense that their only mutable state is the
internal filter history; they perform no I/O.  This makes them easy to unit-
test without any mocking.

Supported filter types (``processing.filters[*].type`` in config):
  * ``butterworth_lowpass_2nd`` / ``biquad_lowpass`` — 2nd-order Butterworth IIR
  * ``lowpass_1pole`` — 1st-order RC IIR (simpler, lower CPU cost)

Backward-compatible aliases accepted by the factory:
  * ``butter_lowpass`` — accepted only as an order-2 low-pass
  * ``one_pole_lowpass`` — alias for ``lowpass_1pole``
  * ``drift_corrector`` — adaptive baseline subtraction
  * ``identity`` — pass-through (useful for testing pipeline wiring)

.. note::
    ``lowpass_1pole`` and ``drift_corrector`` are not used in the default
    ``conf/config.yaml`` but are retained for optional filter chains in
    downstream configurations.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Protocol

from omegaconf import DictConfig

_log = logging.getLogger(__name__)

SUPPORTED_PRODUCTION_FILTER_TYPES: frozenset[str] = frozenset(
    {
        "identity",
        "butterworth_lowpass_2nd",
        "biquad_lowpass",
        "butter_lowpass",
        "lowpass_1pole",
        "one_pole_lowpass",
        "drift_corrector",
    }
)


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


# @brief Protocol for processing one value at a given sample time.
class SampleProcessor(Protocol):
    # @brief Process one scalar sample.
    #  @param value Input sample value.
    #  @param sample_time_s Processing time in seconds.
    #  @return Processed sample value.
    def process(self, value: float, sample_time_s: float) -> float: ...


# @brief Filter-node protocol used by FilterPipeline.
class FilterNode(Protocol):
    # @brief Process one scalar sample.
    #  @param value Input sample value.
    #  @param sample_time_s Processing time in seconds.
    #  @return Processed sample value.
    def process(self, value: float, sample_time_s: float) -> float: ...


# ---------------------------------------------------------------------------
# Filter implementations
# ---------------------------------------------------------------------------


@dataclass(slots=True)
# @brief First-order low-pass filter implementation.
class FirstOrderLowPass:
    """
    1-pole RC IIR low-pass filter.

    .. note::
        Not used in the default configuration; retained for optional filter
        chains.  Prefer ``SecondOrderBiquadLowPass`` for Butterworth response.
    """

    cutoff_hz: float
    reset_on_gap_s: float = 1.0
    min_dt_s: float = 1e-6

    _tau: float = field(init=False)
    _last_time_s: float | None = field(init=False, default=None)
    _y: float | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.cutoff_hz <= 0.0:
            raise ValueError(f"cutoff_hz must be > 0. Received {self.cutoff_hz}")
        self._tau = 1.0 / (2.0 * math.pi * self.cutoff_hz)

    def process(self, value: float, sample_time_s: float) -> float:
        if self._y is None or self._last_time_s is None:
            self._y = value
            self._last_time_s = sample_time_s
            return value

        dt = max(self.min_dt_s, sample_time_s - self._last_time_s)
        if dt > self.reset_on_gap_s:
            _log.warning(
                "Low-pass filter state reset after large gap: dt=%.6fs > %.6fs",
                dt,
                self.reset_on_gap_s,
            )
            self._y = value
            self._last_time_s = sample_time_s
            return value

        alpha = dt / (self._tau + dt)
        self._y = self._y + alpha * (value - self._y)
        self._last_time_s = sample_time_s
        return self._y


@dataclass(slots=True)
# @brief Second-order Butterworth biquad low-pass filter.
class SecondOrderBiquadLowPass:
    """
    2nd-order Butterworth biquad IIR low-pass filter.

    Coefficients are pre-computed at construction time using the bilinear
    transform so that ``process()`` is a lightweight multiply-accumulate loop
    with no trigonometry at runtime.
    """

    cutoff_hz: float
    sample_rate_hz: float
    q: float = 1.0 / math.sqrt(2.0)
    reset_on_gap_s: float = 1.0
    min_dt_s: float = 1e-6

    _b0: float = field(init=False)
    _b1: float = field(init=False)
    _b2: float = field(init=False)
    _a1: float = field(init=False)
    _a2: float = field(init=False)
    _last_time_s: float | None = field(init=False, default=None)
    _x1: float = field(init=False, default=0.0)
    _x2: float = field(init=False, default=0.0)
    _y1: float = field(init=False, default=0.0)
    _y2: float = field(init=False, default=0.0)
    _initialized: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        if self.cutoff_hz <= 0.0:
            raise ValueError(f"cutoff_hz must be > 0. Received {self.cutoff_hz}")
        if self.sample_rate_hz <= 0.0:
            raise ValueError(f"sample_rate_hz must be > 0. Received {self.sample_rate_hz}")
        nyquist_hz = 0.5 * self.sample_rate_hz
        if self.cutoff_hz >= nyquist_hz:
            raise ValueError(
                "cutoff_hz must be strictly below Nyquist. "
                f"Received cutoff_hz={self.cutoff_hz} sample_rate_hz={self.sample_rate_hz}"
            )
        if self.q <= 0.0:
            raise ValueError(f"q must be > 0. Received {self.q}")

        omega = 2.0 * math.pi * self.cutoff_hz / self.sample_rate_hz
        cos_omega = math.cos(omega)
        sin_omega = math.sin(omega)
        alpha = sin_omega / (2.0 * self.q)

        b0 = (1.0 - cos_omega) / 2.0
        b1 = 1.0 - cos_omega
        b2 = (1.0 - cos_omega) / 2.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_omega
        a2 = 1.0 - alpha

        self._b0 = b0 / a0
        self._b1 = b1 / a0
        self._b2 = b2 / a0
        self._a1 = a1 / a0
        self._a2 = a2 / a0

    def _reset_state(self, value: float, sample_time_s: float) -> float:
        self._last_time_s = sample_time_s
        self._x1 = value
        self._x2 = value
        self._y1 = value
        self._y2 = value
        self._initialized = True
        return value

    def process(self, value: float, sample_time_s: float) -> float:
        if not self._initialized or self._last_time_s is None:
            return self._reset_state(value, sample_time_s)

        dt = max(self.min_dt_s, sample_time_s - self._last_time_s)
        if dt > self.reset_on_gap_s:
            _log.warning(
                "Second-order low-pass state reset after large gap: dt=%.6fs > %.6fs",
                dt,
                self.reset_on_gap_s,
            )
            return self._reset_state(value, sample_time_s)

        y = self._b0 * value + self._b1 * self._x1 + self._b2 * self._x2 - self._a1 * self._y1 - self._a2 * self._y2

        self._x2 = self._x1
        self._x1 = value
        self._y2 = self._y1
        self._y1 = y
        self._last_time_s = sample_time_s
        return y


@dataclass(slots=True)
# @brief Adaptive baseline drift correction filter.
class DriftCorrector:
    """
    Adaptive baseline drift corrector.

    Tracks a slowly-evolving baseline using a 1-pole IIR that only updates
    when the signal is near rest or changing slowly.  The output is the
    input minus the estimated baseline.

    .. note::
        Not used in the default configuration; retained for optional filter
        chains.
    """

    baseline_cutoff_hz: float = 0.02
    rest_band: float = 5.0
    stable_slope_threshold_per_s: float = 5.0
    warmup_samples: int = 20
    reset_on_gap_s: float = 1.0
    min_dt_s: float = 1e-6

    _tau: float = field(init=False)
    _baseline: float | None = field(init=False, default=None)
    _last_time_s: float | None = field(init=False, default=None)
    _last_input: float | None = field(init=False, default=None)
    _sample_count: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        if self.baseline_cutoff_hz <= 0.0:
            raise ValueError(f"baseline_cutoff_hz must be > 0. Received {self.baseline_cutoff_hz}")
        if self.rest_band < 0.0:
            raise ValueError(f"rest_band must be >= 0. Received {self.rest_band}")
        if self.stable_slope_threshold_per_s < 0.0:
            raise ValueError(f"stable_slope_threshold_per_s must be >= 0. Received {self.stable_slope_threshold_per_s}")
        if self.warmup_samples < 0:
            raise ValueError(f"warmup_samples must be >= 0. Received {self.warmup_samples}")
        self._tau = 1.0 / (2.0 * math.pi * self.baseline_cutoff_hz)

    def process(self, value: float, sample_time_s: float) -> float:
        if self._baseline is None or self._last_time_s is None or self._last_input is None:
            self._baseline = value
            self._last_time_s = sample_time_s
            self._last_input = value
            self._sample_count = 1
            return 0.0

        dt = max(self.min_dt_s, sample_time_s - self._last_time_s)
        if dt > self.reset_on_gap_s:
            _log.warning(
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

        if self._sample_count < self.warmup_samples or near_rest or stable:
            alpha = dt / (self._tau + dt)
            self._baseline = self._baseline + alpha * (value - self._baseline)

        corrected = value - self._baseline
        self._last_input = value
        self._last_time_s = sample_time_s
        self._sample_count += 1
        return corrected


# ---------------------------------------------------------------------------
# Pipeline and adapter
# ---------------------------------------------------------------------------


# @brief Identity processor that forwards values unchanged.
class IdentityProcessor:
    """Pass-through processor; useful for testing pipeline wiring."""

    # @brief Return the unmodified input value.
    #  @param value Input sample value.
    #  @param sample_time_s Processing time in seconds.
    #  @return Input sample value.
    def process(self, value: float, sample_time_s: float) -> float:
        _ = sample_time_s
        return value


# @brief Left-to-right chain of filter nodes.
class FilterPipeline:
    """Ordered chain of FilterNode instances applied left-to-right."""

    def __init__(self, filters: list[FilterNode]) -> None:
        self._filters = filters

    # @brief Process one sample through all configured filter nodes.
    #  @param value Input sample value.
    #  @param sample_time_s Processing time in seconds.
    #  @return Filtered output value.
    def process(self, value: float, sample_time_s: float) -> float:
        y = value
        for f in self._filters:
            y = f.process(y, sample_time_s)
        return y

    @property
    # @brief Snapshot list of currently configured filter nodes.
    #  @return Copy of filter-node sequence.
    def filters(self) -> list[FilterNode]:
        return list(self._filters)


# @brief Adapter exposing configured filter pipeline via Processor contract.
class ProcessorAdapter:
    """Assembles a ``FilterPipeline`` from a Hydra ``DictConfig``."""

    def __init__(self, cfg: DictConfig) -> None:
        filters_cfg = list(cfg.filters) if cfg.get("filters") is not None else []
        self._pipeline = FilterPipeline([_build_filter_node(f_cfg) for f_cfg in filters_cfg])

    # @brief Process one sample through the configured pipeline.
    #  @param value Input sample value.
    #  @param sample_time_s Processing time in seconds.
    #  @return Filtered output value.
    def process(self, value: float, sample_time_s: float) -> float:
        return self._pipeline.process(value, sample_time_s)

    @property
    # @brief Expose current filter-node list.
    #  @return Copy of configured filter nodes.
    def filters(self) -> list[FilterNode]:
        return self._pipeline.filters


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


# @brief Build a single filter node from one config stanza.
#  @param filter_cfg Hydra filter configuration object.
#  @return Concrete FilterNode instance.
def _build_filter_node(filter_cfg: DictConfig) -> FilterNode:
    """Instantiate a single filter node from its config stanza."""
    filter_type = str(filter_cfg.type)

    if filter_type == "one_pole_lowpass":
        filter_type = "lowpass_1pole"

    if filter_type == "butter_lowpass":
        order = int(filter_cfg.get("order", 2))
        if order != 2:
            raise ValueError("butter_lowpass compatibility alias only supports order=2")
        filter_type = "butterworth_lowpass_2nd"

    if filter_type == "lowpass_1pole":
        return FirstOrderLowPass(
            cutoff_hz=float(filter_cfg.cutoff_hz),
            reset_on_gap_s=float(filter_cfg.get("reset_on_gap_s", 1.0)),
            min_dt_s=float(filter_cfg.get("min_dt_s", 1e-6)),
        )

    if filter_type in {"biquad_lowpass", "butterworth_lowpass_2nd"}:
        q = float(filter_cfg.get("q", 1.0 / math.sqrt(2.0)))
        return SecondOrderBiquadLowPass(
            cutoff_hz=float(filter_cfg.cutoff_hz),
            sample_rate_hz=float(filter_cfg.sample_rate_hz),
            q=q,
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

    raise ValueError(f"Unsupported filter type: {filter_type!r}")


# @brief Build configured processor adapter and log resulting chain.
#  @param cfg Processing subtree from Hydra configuration.
#  @return ProcessorAdapter ready for per-sample processing.
def build_processor(cfg: DictConfig) -> ProcessorAdapter:
    """
    Public factory called by ``core/processing.py`` via importlib.

    Args:
        cfg: The ``processing`` sub-tree of the Hydra config.

    Returns:
        A ``ProcessorAdapter`` whose ``process(value, sample_time_s)`` method
        applies the configured filter chain.

    """
    processor = ProcessorAdapter(cfg)
    _log.info(
        "Initialized processor with filter chain: %s",
        ", ".join(type(f).__name__ for f in processor.filters) or "<empty>",
    )
    return processor
