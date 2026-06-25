# @package lsl_bridge.io.csv_sinks
#  @brief CSV persistence sinks for target and reference published samples.
##
"""
CSV sinks for persisting LSL-published samples to disk.

Both sinks write the exact sample vectors that are pushed to LSL so that
the CSV files serve as a faithful local record of what was streamed.

Each sink buffers writes and flushes every ``flush_every_n_rows`` rows to
limit I/O overhead without risking data loss on abrupt termination.

Typical usage::

    sink = TargetCsvSink(Path("./data/target.csv"), write_mode="overwrite", flush_every_n_rows=1)
    sink.write(sample, filtered_units)
    sink.close()
"""

from __future__ import annotations

import csv
import logging
import math
from pathlib import Path

from lsl_bridge.types import ParsedTargetSample, ReferenceSample

_log = logging.getLogger(__name__)

WRITE_MODES = ("timestamped", "append", "overwrite")


# @brief Insert a timestamp suffix before a path's file extension.
#  @param path Original file path.
#  @param timestamp Timestamp string to insert (e.g. "20260612_143022").
#  @return New path with "_<timestamp>" inserted before the suffix.
def apply_timestamp_suffix(path: Path, timestamp: str) -> Path:
    """Return ``path`` with ``_<timestamp>`` inserted before its extension."""
    return path.with_name(f"{path.stem}_{timestamp}{path.suffix}")


# @brief Persist published target samples into CSV rows.
class TargetCsvSink:
    """
    Writes the exact target samples published to LSL into a CSV file.

    Field order matches the LSL channel order for easy cross-referencing.

    Args:
        path:               Destination CSV file path.  Parent directories
                            are created automatically.  For ``write_mode="timestamped"``,
                            the caller is expected to have already inserted the
                            timestamp suffix into this path.
        write_mode:         One of ``"timestamped"``, ``"append"``, ``"overwrite"``.
                            ``"append"`` opens the file in append mode and only
                            writes a header if the file is empty; the other two
                            modes truncate and always write a fresh header.
        flush_every_n_rows: Flush the underlying file handle every N rows.

    """

    FIELDNAMES = [
        "host_unix_time_ns",
        "lsl_timestamp_s",
        "seq",
        "device_clock_us",
        "target_raw_count",
        "target_current_units",
        "target_filtered_units",
        "target_status",
        "raw_line",
        "arrival_lsl_time_s",
    ]

    # @brief Create and initialize target CSV writer state.
    #  @param path Output CSV file path.
    #  @param write_mode "timestamped", "append" or "overwrite".
    #  @param flush_every_n_rows Flush interval in rows.
    #  @return None.
    def __init__(self, path: Path, write_mode: str, flush_every_n_rows: int) -> None:
        if write_mode not in WRITE_MODES:
            raise ValueError(f"Invalid write_mode {write_mode!r}, expected one of {WRITE_MODES}")
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        append = write_mode == "append"
        self._fh = self._path.open("a" if append else "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=self.FIELDNAMES)
        if (not append) or self._path.stat().st_size == 0:
            self._writer.writeheader()
        self._flush_every_n_rows = max(1, int(flush_every_n_rows))
        self._rows_since_flush = 0
        _log.debug("TargetCsvSink opened: %s (write_mode=%s)", path, write_mode)

    # @brief Write one target sample row to disk buffer.
    #  @param sample Parsed target sample object.
    #  @param filtered_units Filtered target value published to LSL.
    #  @param arrival_lsl_time_s Raw LSL clock at serial byte arrival; nan when unknown.
    #  @return None.
    def write(
        self,
        sample: ParsedTargetSample,
        filtered_units: float,
        arrival_lsl_time_s: float = float("nan"),
    ) -> None:
        """Append one sample row to the CSV."""
        self._writer.writerow(
            {
                "host_unix_time_ns": sample.host_unix_time_ns,
                "lsl_timestamp_s": f"{sample.lsl_timestamp:.9f}",
                "seq": sample.sequence,
                "device_clock_us": sample.device_clock_us,
                "target_raw_count": repr(sample.target_raw_count),
                "target_current_units": repr(sample.target_current_units),
                "target_filtered_units": repr(filtered_units),
                "target_status": sample.target_status,
                "raw_line": sample.raw_line,
                "arrival_lsl_time_s": "" if math.isnan(arrival_lsl_time_s) else f"{arrival_lsl_time_s:.9f}",
            }
        )
        self._rows_since_flush += 1
        if self._rows_since_flush >= self._flush_every_n_rows:
            self._fh.flush()
            self._rows_since_flush = 0

    # @brief Flush and close target CSV handle.
    #  @return None.
    def close(self) -> None:
        """Flush and close the underlying file handle."""
        try:
            self._fh.flush()
        finally:
            self._fh.close()
        _log.debug("TargetCsvSink closed: %s", self._path)


# @brief Persist published reference samples into CSV rows.
class ReferenceCsvSink:
    """
    Writes canonical reference samples published to LSL into a CSV file.

    Args:
        path:               Destination CSV file path.
        write_mode:         One of ``"timestamped"``, ``"append"``, ``"overwrite"``.
        flush_every_n_rows: Flush interval in rows.

    """

    FIELDNAMES = [
        "host_unix_ts",
        "received_lsl_ts",
        "lsl_timestamp_s",
        "seq",
        "reference_clock_s",
        "reference_force_N",
        "reference_status",
        "rs485_mode",
        "rs485_signal_key",
        "rs485_clock_source",
        "unit_label",
        "timestamp_source",
        "configured_frequency_hz",
        "session_id",
    ]

    # @brief Create and initialize reference CSV writer state.
    #  @param path Output CSV file path.
    #  @param write_mode "timestamped", "append" or "overwrite".
    #  @param flush_every_n_rows Flush interval in rows.
    #  @return None.
    def __init__(self, path: Path, write_mode: str, flush_every_n_rows: int) -> None:
        if write_mode not in WRITE_MODES:
            raise ValueError(f"Invalid write_mode {write_mode!r}, expected one of {WRITE_MODES}")
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        append = write_mode == "append"
        self._fh = self._path.open("a" if append else "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=self.FIELDNAMES)
        if (not append) or self._path.stat().st_size == 0:
            self._writer.writeheader()
        self._flush_every_n_rows = max(1, int(flush_every_n_rows))
        self._rows_since_flush = 0
        _log.debug("ReferenceCsvSink opened: %s (write_mode=%s)", path, write_mode)

    # @brief Write one reference sample row to disk buffer.
    #  @param sample Parsed reference sample object.
    #  @param lsl_timestamp_s Publication timestamp used for this row.
    #  @return None.
    def write(self, sample: ReferenceSample, lsl_timestamp_s: float) -> None:
        """Append one sample row to the CSV."""
        self._writer.writerow(
            {
                "host_unix_ts": repr(sample.host_unix_ts),
                "received_lsl_ts": f"{sample.received_lsl_ts:.9f}",
                "lsl_timestamp_s": f"{lsl_timestamp_s:.9f}",
                "seq": sample.sequence,
                "reference_clock_s": repr(sample.reference_clock_s),
                "reference_force_N": repr(sample.reference_force_N),
                "reference_status": sample.status,
                "rs485_mode": sample.mode,
                "rs485_signal_key": sample.signal_key,
                "rs485_clock_source": sample.clock_source,
                "unit_label": sample.unit_label,
                "timestamp_source": sample.timestamp_source,
                "configured_frequency_hz": (
                    "" if not math.isfinite(sample.configured_frequency_hz) else repr(sample.configured_frequency_hz)
                ),
                "session_id": sample.session_id or "",
            }
        )
        self._rows_since_flush += 1
        if self._rows_since_flush >= self._flush_every_n_rows:
            self._fh.flush()
            self._rows_since_flush = 0

    # @brief Flush and close reference CSV handle.
    #  @return None.
    def close(self) -> None:
        """Flush and close the underlying file handle."""
        try:
            self._fh.flush()
        finally:
            self._fh.close()
        _log.debug("ReferenceCsvSink closed: %s", self._path)
