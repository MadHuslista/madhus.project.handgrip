"""Operational event marker stream for the LSL Bridge.

``ComponentEventOutlet`` publishes a sparse LSL marker stream
(``HandgripComponentEvents``) that records component-level state
transitions: serial connects/disconnects, timestamp anchor resets, IPC
gaps, firmware metadata frames, and bridge start/stop.

This stream is intentionally **separate** from calibration trial markers.
The Handgrip_Calibration recorder owns trial markers; the bridge only
reports infrastructure events useful for post-hoc recording audits.

Each event is a single JSON string pushed as an irregular LSL string sample.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from omegaconf import DictConfig
from pylsl import IRREGULAR_RATE, StreamInfo, StreamOutlet, cf_string, local_clock

_log = logging.getLogger(__name__)


class ComponentEventOutlet:
    """Publishes structured JSON markers to a LSL string stream.

    Args:
        cfg: Full Hydra ``DictConfig``.  Uses ``component_events``.
    """

    def __init__(self, cfg: DictConfig) -> None:
        self.enabled = bool(cfg.component_events.enabled)
        self._outlet: StreamOutlet | None = None

        if not self.enabled:
            _log.info("ComponentEventOutlet disabled (component_events.enabled=false).")
            return

        schema = str(cfg.component_events.schema)
        info = StreamInfo(
            str(cfg.component_events.name),
            str(cfg.component_events.type),
            1,
            IRREGULAR_RATE,
            cf_string,
            str(cfg.component_events.source_id),
        )
        desc = info.desc()
        desc.append_child_value("schema", schema)
        desc.append_child_value("producer", "LSL_Bridge")
        self._outlet = StreamOutlet(info, chunk_size=1)
        self._schema = schema
        _log.info(
            "ComponentEventOutlet created: name=%s source_id=%s",
            cfg.component_events.name,
            cfg.component_events.source_id,
        )

    def emit(self, event: str, **payload: Any) -> None:
        """Push a JSON event marker to the LSL stream.

        If the outlet is disabled or not yet initialised, this is a no-op.

        Args:
            event:   Short event name (e.g. ``"bridge_start"``).
            **payload: Arbitrary key/value pairs serialised into the JSON body.
        """
        if self._outlet is None:
            return
        record = {
            "schema": self._schema,
            "producer": "LSL_Bridge",
            "event": event,
            "host_unix_ns": time.time_ns(),
            "lsl_ts": local_clock(),
            **payload,
        }
        self._outlet.push_sample(
            [json.dumps(record, separators=(",", ":"), ensure_ascii=False)],
            pushthrough=True,
        )
        _log.debug("ComponentEvent emitted: %s", event)
