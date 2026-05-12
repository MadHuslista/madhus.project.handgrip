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
                                time then advance via device-clock deltas.
                                A bounded drift guard compares the predicted
                                timestamp against host-arrival time and
                                re-anchors when the device-derived clock drifts
                                too far from real time.  This preserves native
                                cadence for normal jitter while preventing the
                                live XY viewer from accumulating seconds of
                                apparent reference lag.
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
        self._max_anchor_drift_s = float(
            cfg.target_timestamping.get("max_anchor_drift_s", 0.0)
        )
        self._monotonic_epsilon_s = float(
            cfg.target_timestamping.get("monotonic_epsilon_s", 1e-9)
        )
        self._anchor_device_us: int | None = None
        self._anchor_lsl_s: float | None = None
        self._last_device_us: int | None = None
        self._last_resolved_lsl_s: float | None = None
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
            return self._monotonic_lsl(float(arrival_lsl_time))

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
            return self._monotonic_lsl(float(arrival_lsl_time))

        if self._last_device_us is not None:
            delta_s = (sample.device_clock_us - self._last_device_us) / 1_000_000.0

            if sample.device_clock_us < self._last_device_us and self._reset_on_nonmonotonic:
                self._reset_anchor(
                    sample.device_clock_us,
                    arrival_lsl_time,
                    reason="nonmonotonic_device_clock",
                )
                return self._monotonic_lsl(float(arrival_lsl_time))

            if delta_s > self._max_gap_s:
                self._reset_anchor(
                    sample.device_clock_us,
                    arrival_lsl_time,
                    reason="device_clock_gap",
                    gap_s=delta_s,
                )
                return self._monotonic_lsl(float(arrival_lsl_time))

        self._last_device_us = sample.device_clock_us
        predicted_lsl_s = self._anchor_lsl_s + (
            sample.device_clock_us - self._anchor_device_us
        ) / 1_000_000.0

        # Firmware clocks are useful for cadence, but they are not guaranteed to
        # be metrology-grade clocks.  If the anchored device-clock prediction
        # walks away from the actual host arrival time, the LSL timestamp tail
        # becomes stale.  The time-series plots can still look live, but the XY
        # plot pairs the latest target sample with an old reference value because
        # reference->target interpolation uses these timestamps.  Re-anchoring
        # bounds that live-display and synchronization error.
        if self._max_anchor_drift_s > 0:
            drift_s = float(arrival_lsl_time) - float(predicted_lsl_s)
            if abs(drift_s) > self._max_anchor_drift_s:
                self._reset_anchor(
                    sample.device_clock_us,
                    arrival_lsl_time,
                    reason="device_clock_anchor_drift",
                    drift_s=drift_s,
                    threshold_s=self._max_anchor_drift_s,
                )
                predicted_lsl_s = float(arrival_lsl_time)

        return self._monotonic_lsl(float(predicted_lsl_s))

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

    def _monotonic_lsl(self, candidate_lsl_s: float) -> float:
        """Return a non-decreasing LSL timestamp.

        LSL accepts explicit timestamps, but downstream consumers should never
        receive a backward jump.  This guard is intentionally tiny: it does not
        smooth or resample; it only prevents pathological non-monotonic output
        after a re-anchor or host-clock jitter event.
        """
        if self._last_resolved_lsl_s is not None:
            min_next = self._last_resolved_lsl_s + max(0.0, self._monotonic_epsilon_s)
            if candidate_lsl_s < min_next:
                candidate_lsl_s = min_next
        self._last_resolved_lsl_s = float(candidate_lsl_s)
        return float(candidate_lsl_s)
