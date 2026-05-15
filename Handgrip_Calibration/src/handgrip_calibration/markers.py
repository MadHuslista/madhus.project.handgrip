"""Calibration marker events and optional LSL marker outlet."""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .config_schema import MarkerConfig
from .export import append_ndjson

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class MarkerEvent:
    """A single calibration event.

    Marker events are intentionally simple JSON-compatible records. They are
    written to `events.ndjson` and, when pylsl is available, emitted as strings
    on an LSL marker stream so XDF recordings can retain the same segmentation
    information as the calibration module.
    """

    event: str
    session_id: str
    trial_id: str | None = None
    target_force_N: float | None = None
    phase: str | None = None
    reason: str | None = None
    operator_note: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    schema: str = "handgrip_marker.v1"
    marker_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    host_time_unix: float = field(default_factory=time.time)
    lsl_time: float | None = None

    def to_dict(self) -> dict[str, Any]:
        # @brief Convert marker event to JSON-ready dictionary.
        #  @param self Marker event instance.
        #  @return Dictionary without empty optional fields.
        """Return a JSON-compatible dictionary without empty optional fields."""

        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None and v != {}}

    def to_lsl_string(self) -> str:
        """Serialize the marker as compact JSON for LSL marker streams."""

        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))


class MarkerOutlet:
    """Optional LSL outlet for calibration markers.

    The class imports pylsl lazily. This keeps offline fitting/reporting usable on
    machines that do not have LSL installed.
    """

    def __init__(self, config: MarkerConfig, *, session_id: str) -> None:
        self.config = config
        self.session_id = session_id
        self._outlet = None
        self._local_clock = None
        if not config.emit_lsl:
            return
        try:
            from pylsl import IRREGULAR_RATE, StreamInfo, StreamOutlet, cf_string, local_clock
        except Exception as exc:  # pragma: no cover - depends on optional pylsl
            raise RuntimeError(
                "pylsl is required for marker LSL emission. Install with: "
                "python -m pip install -e '.[lsl]' or set markers.emit_lsl=false"
            ) from exc
        info = StreamInfo(
            name=config.stream_name,
            type=config.stream_type,
            channel_count=1,
            nominal_srate=IRREGULAR_RATE,
            channel_format=cf_string,
            source_id=f"{config.source_id_prefix}-{session_id}",
        )
        desc = info.desc()
        desc.append_child_value("schema", "handgrip_marker.v1")
        desc.append_child_value("session_id", session_id)
        desc.append_child_value("purpose", "calibration segmentation and operator annotations")
        self._outlet = StreamOutlet(info)
        self._local_clock = local_clock

    def push(self, event: MarkerEvent) -> MarkerEvent:
        """Push *event* to LSL and return the event with the actual LSL time."""

        if self._outlet is None:
            return event
        lsl_now = float(self._local_clock())
        event = MarkerEvent(**{**event.to_dict(), "lsl_time": lsl_now})
        self._outlet.push_sample([event.to_lsl_string()], timestamp=lsl_now)
        return event


class MarkerLogger:
    """Write markers to disk and optionally mirror them to LSL."""

    def __init__(self, path: str | Path, config: MarkerConfig, *, session_id: str) -> None:
        self.path = Path(path)
        self.config = config
        self.session_id = session_id
        self.outlet = MarkerOutlet(config, session_id=session_id) if config.emit_lsl else None

    def emit(self, event: str, **kwargs: Any) -> MarkerEvent:
        """Create, emit, and persist a marker event."""

        marker = MarkerEvent(event=event, session_id=self.session_id, **kwargs)
        log.debug("Marker: %s (trial=%s, force=%.4g N)", event, kwargs.get("trial_id"), kwargs.get("target_force_N") or 0.0)
        if self.outlet is not None:
            marker = self.outlet.push(marker)
        if self.config.write_ndjson:
            append_ndjson(self.path, [marker.to_dict()])
        return marker
