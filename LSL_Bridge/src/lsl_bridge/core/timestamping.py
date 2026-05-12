"""Timestamp resolution for the LSL Bridge target stream.

LSL timestamps are the synchronisation authority.  Device timestamps
(``device_clock_us``) are kept as diagnostic channels only.

Two resolvers are provided:

``SampleTimeResolver``
    Maps a ``ParsedTargetSample`` to a *filter-domain* time in seconds.
    Used to feed the signal-processing chain; not used for LSL timestamps.

``TargetTimestampResolver``
    Maps the device clock into the *LSL clock domain* using one of two
    policies selected by ``target_timestamping.policy`` in config:

    * ``host_receive``        — use the raw LSL arrival time (lower risk,
                                works even with poor firmware clock quality).
    * ``device_clock_anchor`` — anchor the first sample to the LSL arrival
                                time then advance via device-clock deltas
                                (preserves native cadence; recommended after
                                bench-validation of the firmware clock).
"""

from __future__ import annotations

import logging
from typing import Any

from omegaconf import DictConfig

from lsl_bridge.types import ParsedTargetSample

_log = logging.getLogger(__name__)


class SampleTimeResolver:
    """Resolve the filter-domain time for a target sample.

    The filter chain needs a monotonically increasing time in seconds.
    This resolver produces that time from either the LSL timestamp or
    from accumulated device-clock deltas, depending on
    ``processing.timestamp_source`` in config.

    Args:
        cfg: Full Hydra ``DictConfig``.  Uses ``processing.timestamp_source``.
    """

    def __init__(self, cfg: DictConfig) -> None:
        self._source = str(cfg.processing.timestamp_source)
        self._last_device_clock_us: int | None = None
        self._last_resolved_time_s: float = 0.0

    def resolve(self, sample: ParsedTargetSample) -> float:
        """Return the filter-domain time for *sample* in seconds."""
        if self._source == "lsl":
            return float(sample.lsl_timestamp)

        if self._source != "device_clock_us":
            raise ValueError(
                f"Unsupported processing.timestamp_source={self._source!r}. "
                "Expected 'lsl' or 'device_clock_us'."
            )

        if self._last_device_clock_us is None:
            self._last_device_clock_us = sample.device_clock_us
            self._last_resolved_time_s = 0.0
            return 0.0

        delta_us = sample.device_clock_us - self._last_device_clock_us
        if delta_us > 0:
            self._last_resolved_time_s += delta_us / 1_000_000.0
        self._last_device_clock_us = sample.device_clock_us
        return self._last_resolved_time_s


class TargetTimestampResolver:
    """Map device-clock values into the LSL clock domain.

    Args:
        cfg:    Full Hydra ``DictConfig``.  Uses ``target_timestamping``.
        events: ``ComponentEventOutlet`` for structured anchor-reset events.
    """

    def __init__(self, cfg: DictConfig, events: object) -> None:
        self._policy = str(cfg.target_timestamping.policy)
        self._max_gap_s = float(cfg.target_timestamping.max_gap_s)
        self._reset_on_nonmonotonic = bool(cfg.target_timestamping.reset_on_nonmonotonic)
        self._anchor_device_us: int | None = None
        self._anchor_lsl_s: float | None = None
        self._last_device_us: int | None = None
        self._events = events

    def resolve(self, sample: ParsedTargetSample, arrival_lsl_time: float) -> float:
        """Return the LSL timestamp to stamp *sample* with.

        Args:
            sample:           Parsed D2 sample (provides ``device_clock_us``).
            arrival_lsl_time: Raw LSL clock value at byte-arrival time.

        Returns:
            LSL timestamp (seconds, LSL epoch) to be used for this sample.
        """
        if self._policy == "host_receive":
            return arrival_lsl_time

        if self._policy != "device_clock_anchor":
            raise ValueError(
                "Only target_timestamping.policy=host_receive|device_clock_anchor "
                "is supported in schema v2"
            )

        if self._anchor_device_us is None or self._anchor_lsl_s is None:
            self._reset_anchor(
                sample.device_clock_us,
                arrival_lsl_time,
                reason="initial_anchor",
            )
            return arrival_lsl_time

        if self._last_device_us is not None:
            delta_s = (sample.device_clock_us - self._last_device_us) / 1_000_000.0

            if sample.device_clock_us < self._last_device_us and self._reset_on_nonmonotonic:
                self._reset_anchor(
                    sample.device_clock_us,
                    arrival_lsl_time,
                    reason="nonmonotonic_device_clock",
                )
                return arrival_lsl_time

            if delta_s > self._max_gap_s:
                self._reset_anchor(
                    sample.device_clock_us,
                    arrival_lsl_time,
                    reason="device_clock_gap",
                    gap_s=delta_s,
                )
                return arrival_lsl_time

        self._last_device_us = sample.device_clock_us
        return self._anchor_lsl_s + (
            sample.device_clock_us - self._anchor_device_us
        ) / 1_000_000.0

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _reset_anchor(
        self,
        device_clock_us: int,
        arrival_lsl_time: float,
        *,
        reason: str,
        **payload: Any,
    ) -> None:
        self._anchor_device_us = int(device_clock_us)
        self._anchor_lsl_s = float(arrival_lsl_time)
        self._last_device_us = int(device_clock_us)
        self._events.emit(
            "target_timestamp_anchor_reset",
            reason=reason,
            device_clock_us=device_clock_us,
            **payload,
        )
