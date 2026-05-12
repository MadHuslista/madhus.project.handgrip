"""D2/M2 serial protocol parser for the Arduino/HX711 target device.

The target firmware speaks a simple ASCII CSV protocol over UART:

* **D2 data frames** — one sample per line::

    D2,<seq>,<device_clock_us>,<raw_count>,<current_units>,<status>

* **M2 metadata frames** — emitted once at firmware boot::

    M2,<payload_schema>,<firmware_version>,<git_sha>,<hx711_rate_hz>,
       <scale_factor>,<scale_offset>,<unit>

``D2LineParser`` validates data frames with a compiled regex, detects sequence
gaps, and delegates metadata frames to ``_parse_metadata``.  All configuration
(delimiter, prefix strings, numeric regex, error-log throttle) is driven by
the ``protocol`` and ``logging`` sub-trees of the Hydra config so there are
no magic literals in this module.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict

from omegaconf import DictConfig

from lsl_bridge.types import FirmwareMetadata, ParsedTargetSample

_log = logging.getLogger(__name__)


class D2LineParser:
    """Strict parser for the target firmware D2/M2 serial protocol.

    Args:
        cfg:    Full Hydra ``DictConfig``.  Uses ``protocol`` and
                ``logging`` sub-trees.
        events: ``ComponentEventOutlet`` used to emit structured events
                for sequence gaps and metadata frames.
    """

    def __init__(self, cfg: DictConfig, events: object) -> None:
        self._delimiter = str(cfg.protocol.delimiter)
        self._data_prefix = str(cfg.protocol.data_prefix)
        self._metadata_prefix = str(cfg.protocol.metadata_prefix)
        number = str(cfg.protocol.accepted_numeric_regex)
        d = re.escape(self._delimiter)
        self._data_re = re.compile(
            rf"^\s*{re.escape(self._data_prefix)}{d}"
            rf"(?P<seq>\d+){d}"
            rf"(?P<clock>\d+){d}"
            rf"(?P<raw>{number}){d}"
            rf"(?P<units>{number}){d}"
            rf"(?P<status>\d+)\s*$"
        )
        self._last_seq: int | None = None
        self._parse_errors: int = 0
        self._metadata = FirmwareMetadata()
        self._events = events
        self._log_parse_errors_every_n = max(1, int(cfg.logging.log_parse_errors_every_n))

    @property
    def metadata(self) -> FirmwareMetadata:
        """Most-recently received firmware metadata (or default if none seen)."""
        return self._metadata

    def feed(
        self,
        raw_line: bytes,
        arrival_lsl_time: float,
        arrival_unix_time_ns: int,
    ) -> ParsedTargetSample | None:
        """Parse one raw UART line.

        Args:
            raw_line:           Raw bytes from ``Serial.readline()``.
            arrival_lsl_time:   LSL clock value at byte-arrival time.
            arrival_unix_time_ns: ``time.time_ns()`` at byte-arrival time.

        Returns:
            A ``ParsedTargetSample`` if the line is a valid D2 frame,
            ``None`` for metadata frames, empty lines, or parse errors.
        """
        line = raw_line.decode("ascii", errors="replace").strip()
        if not line:
            return None

        if line.startswith(f"{self._metadata_prefix}{self._delimiter}"):
            self._parse_metadata(line, arrival_lsl_time)
            return None

        match = self._data_re.match(line)
        if not match:
            self._parse_errors += 1
            if (
                self._parse_errors == 1
                or self._parse_errors % self._log_parse_errors_every_n == 0
            ):
                _log.warning(
                    "Dropped non-D2 target line #%d: %r",
                    self._parse_errors,
                    line,
                )
            return None

        seq = int(match.group("seq"))
        if self._last_seq is not None and seq != self._last_seq + 1:
            self._events.emit(
                "target_sequence_gap",
                last_seq=self._last_seq,
                current_seq=seq,
            )
            _log.warning(
                "Target sequence discontinuity detected: last=%d current=%d",
                self._last_seq,
                seq,
            )
        self._last_seq = seq

        return ParsedTargetSample(
            sequence=seq,
            device_clock_us=int(match.group("clock")),
            target_raw_count=float(match.group("raw")),
            target_current_units=float(match.group("units")),
            target_status=int(match.group("status")),
            lsl_timestamp=arrival_lsl_time,
            host_unix_time_ns=arrival_unix_time_ns,
            raw_line=line,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_metadata(self, line: str, arrival_lsl_time: float) -> None:
        parts = line.split(self._delimiter)
        if len(parts) < 8:
            _log.warning("Malformed M2 metadata line: %r", line)
            return
        try:
            self._metadata = FirmwareMetadata(
                payload_schema=int(parts[1]),
                firmware_version=parts[2],
                git_sha=parts[3],
                hx711_rate_hz=float(parts[4]),
                scale_factor=float(parts[5]),
                scale_offset=float(parts[6]),
                unit=parts[7],
                last_seen_lsl_ts=arrival_lsl_time,
            )
        except ValueError as exc:
            _log.warning("Could not decode M2 metadata line %r: %s", line, exc)
            return
        self._events.emit("target_metadata", **asdict(self._metadata))
        _log.info("Target metadata received: %s", self._metadata)
