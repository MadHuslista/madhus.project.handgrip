"""File logger for acquisition data.

Writes four files per session:
  - ``raw_signal.ndjson``         — raw transport bytes / register hex
  - ``interpreted_signal.ndjson`` — decoded engineering values
  - ``gui_signal.csv``            — flat CSV optimised for spreadsheet import
  - ``event.log``                 — operational event messages

All file I/O is serialised through a single lock; the worker thread calls
``write_frames()`` at full acquisition rate while the UI thread may
call ``write_event()`` at any time.

Dependency chain: models, core/signals  (no UI)
"""

from __future__ import annotations

import csv
import json
import logging
import queue
import threading
import time
from pathlib import Path
from typing import TextIO

from omegaconf import DictConfig

from rs485_gui.core.signals import extract_plot_value, get_plot_signal_key
from rs485_gui.models import MeasurementFrame

LOGGER = logging.getLogger(__name__)


# @brief Represents the SignalFileLogger component.
class SignalFileLogger:
    """Thread-safe writer for the four acquisition log files."""

    # @brief Init.
    #
    #  @param self Parameter description.
    #  @param cfg Parameter description.
    def __init__(self, cfg: DictConfig) -> None:
        self.cfg = cfg
        self.enabled = bool(cfg.logger.enabled)
        self.directory = Path(str(cfg.logger.directory)).expanduser()
        self.write_mode = str(cfg.logger.write_mode).lower()
        if self.write_mode not in {"append", "overwrite"}:
            raise ValueError(
                f'logger.write_mode must be "append" or "overwrite", got {self.write_mode!r}'
            )

        self.raw_path = self.directory / str(cfg.logger.raw_signal_filename)
        self.interpreted_path = self.directory / str(cfg.logger.interpreted_signal_filename)
        self.gui_path = self.directory / str(cfg.logger.gui_signal_filename)
        self.event_path = self.directory / str(cfg.logger.event_log_filename)

        self._raw_fp: TextIO | None = None
        self._interpreted_fp: TextIO | None = None
        self._gui_fp: TextIO | None = None
        self._event_fp: TextIO | None = None
        self._gui_writer: csv.writer | None = None
        self._lock = threading.Lock()
        self._write_batches_since_flush: int = 0
        self._last_flush_monotonic: float = time.monotonic()

        # Background-writer state: the acquisition worker enqueues frame batches
        # and a dedicated thread does the (CPU-heavy) json serialization + I/O,
        # so the serial read loop is never blocked by logging.
        self._async = bool(cfg.logger.get("async_logging", True))
        self._queue_maxsize = max(0, int(cfg.logger.get("queue_maxsize", 200000)))
        self._queue: queue.Queue[list[MeasurementFrame]] | None = None
        self._writer_thread: threading.Thread | None = None
        self._stop_writer = threading.Event()
        self.dropped_records: int = 0
        self._last_drop_warn_monotonic: float = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Open all log files.  Safe to call on reconnect; previous files are flushed first."""
        if not self.enabled:
            return

        # On reconnect, stop any previous writer thread before reopening files.
        self._shutdown_writer()

        self.directory.mkdir(parents=True, exist_ok=True)
        file_mode = "a" if self.write_mode == "append" else "w"

        self._raw_fp = self.raw_path.open(file_mode, encoding="utf-8", newline="")
        self._interpreted_fp = self.interpreted_path.open(file_mode, encoding="utf-8", newline="")

        gui_file_preexisting = self.gui_path.exists() and self.gui_path.stat().st_size > 0
        self._gui_fp = self.gui_path.open(file_mode, encoding="utf-8", newline="")
        self._event_fp = self.event_path.open(file_mode, encoding="utf-8", newline="")
        self._gui_writer = csv.writer(self._gui_fp)
        self._write_batches_since_flush = 0
        self._last_flush_monotonic = time.monotonic()

        if self.write_mode == "overwrite" or not gui_file_preexisting:
            self._gui_writer.writerow(
                [
                    "host_ts_epoch_s",
                    "host_ts_iso",
                    "session_id",
                    "mode",
                    "reference_force_N",
                    "reference_clock_s",
                    "reference_status",
                    "plot_signal_key",
                    "plot_value",
                ]
            )
            self._flush_unlocked()

        if self._async:
            self._queue = queue.Queue(maxsize=self._queue_maxsize)
            self._stop_writer.clear()
            self._writer_thread = threading.Thread(
                target=self._writer_loop, name="signal-log-writer", daemon=True
            )
            self._writer_thread.start()

    # @brief Drain and stop the background writer thread (if any).
    #
    #  @param self Parameter description.
    def _shutdown_writer(self) -> None:
        """Signal the writer thread to drain the queue and exit; join it.

        Must be called without holding ``self._lock`` (the writer acquires it).
        """
        thread = self._writer_thread
        if thread is None:
            return
        self._stop_writer.set()
        thread.join()
        self._writer_thread = None
        self._queue = None

    # @brief Background writer loop.
    #
    #  @param self Parameter description.
    def _writer_loop(self) -> None:
        """Drain queued frame batches to disk until stopped and the queue is empty."""
        q = self._queue
        assert q is not None
        while True:
            try:
                frames = q.get(timeout=0.1)
            except queue.Empty:
                if self._stop_writer.is_set():
                    return
                continue
            try:
                self._write_frames_sync(frames)
            except Exception:  # pragma: no cover — never let the writer thread die silently
                LOGGER.exception("Signal log writer failed on a batch")
            finally:
                q.task_done()

    # @brief Close.
    #
    #  @param self Parameter description.
    def close(self) -> None:
        """Flush and close all open log files."""
        # Drain + stop the writer thread before touching files (join needs the
        # lock free).
        self._shutdown_writer()
        with self._lock:
            self._flush_unlocked()
            for fp in (self._raw_fp, self._interpreted_fp, self._gui_fp, self._event_fp):
                if fp is not None and not fp.closed:
                    fp.flush()
                    fp.close()
            self._raw_fp = None
            self._interpreted_fp = None
            self._gui_fp = None
            self._event_fp = None
            self._gui_writer = None

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def write_frames(self, frames: list[MeasurementFrame]) -> None:
        """Enqueue a batch of frames for the background writer (or write inline).

        Called from the acquisition hot path: when async logging is enabled this
        only hands the batch to the writer thread so the serial read loop is not
        blocked by serialization/disk I/O.
        """
        if not self.enabled or not frames:
            return
        if self._raw_fp is None or self._interpreted_fp is None or self._gui_writer is None:
            raise RuntimeError("SignalFileLogger.write_frames called before open()")
        if self._async and self._queue is not None:
            try:
                self._queue.put_nowait(frames)
            except queue.Full:
                self.dropped_records += len(frames)
                now = time.monotonic()
                if now - self._last_drop_warn_monotonic >= 5.0:
                    LOGGER.warning(
                        "Signal log queue full (maxsize=%d); dropped %d records so far. "
                        "Disk cannot keep up with acquisition rate.",
                        self._queue_maxsize,
                        self.dropped_records,
                    )
                    self._last_drop_warn_monotonic = now
            return
        self._write_frames_sync(frames)

    def _write_frames_sync(self, frames: list[MeasurementFrame]) -> None:
        """Serialize and write a batch of frames to the NDJSON and CSV logs."""
        if not self.enabled or not frames:
            return
        with self._lock:
            if self._raw_fp is None or self._interpreted_fp is None or self._gui_writer is None:
                raise RuntimeError("SignalFileLogger._write_frames_sync called before open()")

            plot_signal_key = get_plot_signal_key(self.cfg)
            for frame in frames:
                raw_record = {
                    "host_ts_epoch_s": frame.host_ts,
                    "host_ts_iso": frame.host_ts_iso,
                    "session_id": frame.session_id,
                    "mode": frame.mode,
                    "raw_transport": frame.raw_transport,
                    "board_profile": frame.board_profile,
                }
                interpreted_record = {
                    "host_ts_epoch_s": frame.host_ts,
                    "host_ts_iso": frame.host_ts_iso,
                    "session_id": frame.session_id,
                    "mode": frame.mode,
                    "interpreted": frame.interpreted,
                    "board_profile": frame.board_profile,
                }
                self._raw_fp.write(json.dumps(raw_record, ensure_ascii=False) + "\n")
                self._interpreted_fp.write(
                    json.dumps(interpreted_record, ensure_ascii=False) + "\n"
                )
                plot_value = extract_plot_value(frame, self.cfg)
                self._gui_writer.writerow(
                    [
                        frame.host_ts,
                        frame.host_ts_iso,
                        frame.session_id,
                        frame.mode,
                        frame.interpreted.get("reference_force_N"),
                        frame.interpreted.get("reference_clock_s"),
                        frame.interpreted.get("reference_status"),
                        plot_signal_key,
                        plot_value,
                    ]
                )

            self._write_batches_since_flush += 1
            flush_every_n = max(1, int(self.cfg.logger.flush_every_n_batches))
            flush_interval_s = float(self.cfg.logger.flush_interval_s)
            should_flush = self._write_batches_since_flush >= flush_every_n
            if (
                flush_interval_s > 0
                and (time.monotonic() - self._last_flush_monotonic) >= flush_interval_s
            ):
                should_flush = True
            if should_flush:
                self._flush_unlocked()

    # @brief Write frame.
    #
    #  @param self Parameter description.
    #  @param frame Parameter description.
    def write_frame(self, frame: MeasurementFrame) -> None:
        """Write a single frame (convenience wrapper)."""
        self.write_frames([frame])

    # @brief Write event.
    #
    #  @param self Parameter description.
    #  @param line Parameter description.
    def write_event(self, line: str) -> None:
        """Append one event line to the event log."""
        if not self.enabled:
            return
        with self._lock:
            if self._event_fp is None:
                return
            self._event_fp.write(line + "\n")
            self._event_fp.flush()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _flush_unlocked(self) -> None:
        """Flush all open file handles.  Must be called with ``self._lock`` held."""
        for fp in (self._raw_fp, self._interpreted_fp, self._gui_fp, self._event_fp):
            if fp is not None and not fp.closed:
                fp.flush()
        self._write_batches_since_flush = 0
        self._last_flush_monotonic = time.monotonic()
