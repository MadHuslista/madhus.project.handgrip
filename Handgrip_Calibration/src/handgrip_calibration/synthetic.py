"""Synthetic calibration-session generator for validation and demos."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from .export import append_ndjson, ensure_dir


def generate_demo_session(output_root: str | Path, *, seed: int = 42) -> Path:
    # @brief Generate a complete synthetic calibration session folder.
    #  @param output_root Root directory where the demo session is created.
    #  @param seed Random seed for reproducible synthetic signals.
    #  @return Path to the generated demo session directory.
    """Create a complete synthetic session folder.

    The generated data mimics the real architecture: a ~95 Hz irregular target
    stream, a 500 Hz reference stream, static staircase markers, and a linear
    relation between target raw counts and reference force.
    """

    rng = np.random.default_rng(seed)
    session_dir = ensure_dir(Path(output_root) / "demo_handgrip_session")
    ensure_dir(session_dir / "plots")

    levels = [0, 10, 20, 40, 60, 80, 100, 80, 60, 40, 20, 10, 0]
    hold_duration = 5.0
    stable_window = 3.0
    start_t = 1000.0
    t = start_t
    events: list[dict[str, Any]] = [
        {"schema": "handgrip_marker.v1", "event": "session_start", "session_id": "demo_handgrip_session", "host_time_unix": t, "lsl_time": t},
        {"schema": "handgrip_marker.v1", "event": "baseline_start", "session_id": "demo_handgrip_session", "host_time_unix": t, "lsl_time": t, "target_force_N": 0.0},
        {"schema": "handgrip_marker.v1", "event": "baseline_end", "session_id": "demo_handgrip_session", "host_time_unix": t + 5.0, "lsl_time": t + 5.0, "target_force_N": 0.0},
    ]
    t += 6.0

    ref_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    true_a = 0.0125
    true_b = -125.0
    # raw = (force - b) / a
    for idx, level in enumerate(levels, start=1):
        previous = levels[idx - 2] if idx > 1 else level
        direction = "ascending" if level > previous else "descending" if level < previous else "flat"
        trial_id = f"R01_H{idx:02d}_{level:g}N"
        hold_start = t
        stable_start = t + hold_duration - stable_window
        hold_end = t + hold_duration
        payload = {"trial_id": trial_id, "repeat_index": 1, "level_index": idx, "target_force_N": float(level), "direction": direction}
        events.append({"schema": "handgrip_marker.v1", "event": "hold_start", "session_id": "demo_handgrip_session", "trial_id": trial_id, "target_force_N": float(level), "phase": "static_hold", "payload": payload, "host_time_unix": hold_start, "lsl_time": hold_start})
        events.append({"schema": "handgrip_marker.v1", "event": "stable_window_start", "session_id": "demo_handgrip_session", "trial_id": trial_id, "target_force_N": float(level), "phase": "static_hold", "host_time_unix": stable_start, "lsl_time": stable_start})
        events.append({"schema": "handgrip_marker.v1", "event": "hold_end", "session_id": "demo_handgrip_session", "trial_id": trial_id, "target_force_N": float(level), "phase": "static_hold", "host_time_unix": hold_end, "lsl_time": hold_end})
        events.append({"schema": "handgrip_marker.v1", "event": "trial_accept", "session_id": "demo_handgrip_session", "trial_id": trial_id, "target_force_N": float(level), "host_time_unix": hold_end + 0.01, "lsl_time": hold_end + 0.01})
        ref_t = np.arange(hold_start, hold_end, 1.0 / 500.0)
        target_dt = rng.normal(loc=1.0 / 95.0, scale=0.0015, size=int(hold_duration * 100))
        target_t = hold_start + np.cumsum(target_dt)
        target_t = target_t[target_t < hold_end]
        # Small settling drift during first part of hold; stable window is much cleaner.
        ref_force = level + 0.08 * rng.normal(size=len(ref_t)) + 0.03 * np.sin((ref_t - hold_start) * 2.0)
        raw_center = (level - true_b) / true_a
        raw = raw_center + rng.normal(scale=15.0, size=len(target_t))
        for rt, rv in zip(ref_t, ref_force):
            ref_rows.append({"timestamp_lsl": rt, "raw": rv, "clock": (rt - start_t) * 1e6})
        for tt, rr in zip(target_t, raw):
            target_rows.append({"timestamp_lsl": tt, "raw": rr, "filtered": rr, "clock": (tt - start_t) * 1e6, "seq": len(target_rows)})
        t = hold_end + 1.0

    events.append({"schema": "handgrip_marker.v1", "event": "session_end", "session_id": "demo_handgrip_session", "host_time_unix": t, "lsl_time": t})

    pd.DataFrame(target_rows).to_csv(session_dir / "target.csv", index=False)
    pd.DataFrame(ref_rows).to_csv(session_dir / "reference.csv", index=False)
    append_ndjson(session_dir / "events.ndjson", events)
    manifest = {
        "schema": "handgrip_session_manifest.v1",
        "session": {"session_id": "demo_handgrip_session", "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ"), "operator": "synthetic", "purpose": "demo"},
        "streams": {
            "target": {"name": "synthetic_target", "channel_map": {"raw": ["raw"], "filtered": ["filtered"], "clock": ["clock"], "seq": ["seq"]}},
            "reference": {"name": "synthetic_reference", "channel_map": {"raw": ["raw"], "clock": ["clock"]}},
        },
        "extra": {"true_model": {"force_N": {"a": true_a, "b": true_b}}},
    }
    with (session_dir / "session_manifest.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(manifest, fh, sort_keys=False)
    return session_dir
