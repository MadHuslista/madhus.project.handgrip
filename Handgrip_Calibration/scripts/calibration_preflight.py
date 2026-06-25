# @file
# @brief Calibration preflight: validate the live-stack capture and measure XY sync.
##
# Run this BEFORE a calibration recording (and after ANY change to the physical or
# runtime setup — cabling, ports, host, baud, rates). It does three things:
#
#   Stage A  Capture preflight  — checks that GUI / Bridge / Viewer diagnostic &
#            logging config is set so the capture is analyzable, and that the GUI
#            logs were produced by the current binary (post-fix diagnostic fields).
#   Stage B  Issue-chain scan   — measures each issue from the resolved staircase
#            investigation (ratchet, throughput deficit, jitter) and, when those
#            are clear, the residual physical relay offset.
#   Stage C  Report             — explains every issue and value, then prints the
#            exact ``manual_reference_shift_s`` to paste into the viewer config.
#
# Why a shift at all: the RS485 Active-send frame carries no acquisition timestamp
# (codec sets rs485_clock = host_lsl_ts), so the reference is stamped at GUI read
# time and lags the directly-connected target by a stable relay offset. That offset
# is topology/host dependent and must be re-measured when the setup changes.
##
# Usage (from the Handgrip_Calibration repo directory):
#   uv run python scripts/calibration_preflight.py \
#       --viewer-session ../diagnostics/<ts> \
#       --bridge-target-csv ../LSL_Bridge/data/target_*.csv \
#       --bridge-reference-csv ../LSL_Bridge/data/reference_*.csv \
#       --gui-ndjson ../RS485_GUI/logs/raw_signal.ndjson
#
# Config files are auto-discovered relative to the repo root (derived from this
# script's location) and can be overridden with --config-{gui,bridge,viewer}.
# --strict makes any preflight FAIL set a non-zero exit code (gate a capture).

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

# --- step-onset detection tuning (validated on synthetic data) ---------------
STEP_MIN_REL_AMPLITUDE = 0.30  # fraction of robust signal span
STEP_EDGE_WINDOW_S = 0.25  # window over which a step must complete
STEP_MIN_SEPARATION_S = 1.0  # merge onsets closer than this
LEVEL_WINDOW_S = 0.5  # pre/post level estimation window
ONSET_PAIRING_TOLERANCE_S = 0.5  # max distance when pairing onsets across streams
XCORR_RATE_HZ = 500.0

# --- issue verdict thresholds ------------------------------------------------
RATCHET_FUTURE_AGE_MS = -50.0  # reference stamped >50ms in the future => ratchet
RATCHET_WARN_AGE_MS = -10.0
THROUGHPUT_RATE_FRAC = 0.95  # delivered rate below this fraction of board => deficit
THROUGHPUT_INWAIT_GROWTH = 500  # bytes; last-vs-first decile growth => backlog building
JITTER_SPREAD_MS = 50.0  # onset step-to-step spread above this => jitter present
JITTER_INWAIT_P95_BYTES = 1000  # ~37 frames; p95 above this => bursty reads
RELAY_STABLE_SPREAD_MS = 50.0  # published onset spread below this => offset is stable

# board active-send frequency code -> Hz (mirror RS485_GUI constants)
ACTIVE_SEND_FREQ_CODE_TO_VALUE = {0: 1, 1: 2, 2: 5, 3: 10, 4: 20, 5: 25, 6: 60, 7: 100, 8: 500, 9: 1000}

VIEWER_CONFIG_REL = "LSL_Viewer/conf/config.yaml"
GUI_CONFIG_REL = "RS485_GUI/config/config.yaml"
BRIDGE_CONFIG_REL = "LSL_Bridge/conf/config.yaml"


# ---------------------------------------------------------------------------
# Step detection (unchanged; relocated from analyze_xy_lag.py)
# ---------------------------------------------------------------------------


def detect_step_onsets(t: np.ndarray, y: np.ndarray) -> list[dict]:
    # @brief Detect fast step onsets via mid-level crossing of large transitions.
    # @param t Sample timestamps (seconds, any shared epoch).
    # @param y Signal values.
    # @return List of dicts: onset_s, direction, pre_level, post_level, amplitude.
    t = np.asarray(t, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    finite = np.isfinite(t) & np.isfinite(y)
    t, y = t[finite], y[finite]
    order = np.argsort(t)
    t, y = t[order], y[order]
    if t.size < 10:
        return []

    p5, p95 = np.percentile(y, [5, 95])
    span = p95 - p5
    if span <= 0:
        return []
    ynorm = (y - p5) / span

    # Change of the signal across a short forward-looking window.
    idx_fwd = np.searchsorted(t, t + STEP_EDGE_WINDOW_S, side="right") - 1
    idx_fwd = np.clip(idx_fwd, 0, t.size - 1)
    delta = ynorm[idx_fwd] - ynorm
    candidates = np.where(np.abs(delta) >= STEP_MIN_REL_AMPLITUDE)[0]
    if candidates.size == 0:
        return []

    # Group candidate indices into events separated by min separation.
    events: list[tuple[int, int]] = []
    start = candidates[0]
    prev = candidates[0]
    for i in candidates[1:]:
        if t[i] - t[prev] > STEP_MIN_SEPARATION_S:
            events.append((start, prev))
            start = i
        prev = i
    events.append((start, prev))

    onsets: list[dict] = []
    for lo, hi in events:
        t_lo, t_hi = t[lo], t[min(hi + 1, t.size - 1)] + STEP_EDGE_WINDOW_S
        pre_mask = (t >= t_lo - LEVEL_WINDOW_S) & (t < t_lo)
        post_mask = (t > t_hi) & (t <= t_hi + LEVEL_WINDOW_S)
        if not np.any(pre_mask) or not np.any(post_mask):
            continue
        pre_level = float(np.median(y[pre_mask]))
        post_level = float(np.median(y[post_mask]))
        amplitude = post_level - pre_level
        if abs(amplitude) < STEP_MIN_REL_AMPLITUDE * span:
            continue
        mid = pre_level + 0.5 * amplitude
        region = (t >= t_lo) & (t <= t_hi)
        rt, ry = t[region], y[region]
        crossed = ry >= mid if amplitude > 0 else ry <= mid
        if not np.any(crossed):
            continue
        onsets.append(
            {
                "onset_s": float(rt[np.argmax(crossed)]),
                "direction": "rise" if amplitude > 0 else "fall",
                "pre_level": pre_level,
                "post_level": post_level,
                "amplitude": amplitude,
            }
        )
    return onsets


def pair_onsets(target_onsets: list[dict], reference_onsets: list[dict]) -> list[dict]:
    # @brief Pair target/reference onsets by nearest time within tolerance.
    # @return List of dicts with both onsets and lag_s = target - reference.
    pairs: list[dict] = []
    used: set[int] = set()
    for ton in target_onsets:
        best_j, best_dt = None, math.inf
        for j, ron in enumerate(reference_onsets):
            if j in used or ron["direction"] != ton["direction"]:
                continue
            dt = abs(ton["onset_s"] - ron["onset_s"])
            if dt < best_dt:
                best_j, best_dt = j, dt
        if best_j is not None and best_dt <= ONSET_PAIRING_TOLERANCE_S:
            used.add(best_j)
            ron = reference_onsets[best_j]
            pairs.append(
                {
                    "direction": ton["direction"],
                    "target_onset_s": ton["onset_s"],
                    "reference_onset_s": ron["onset_s"],
                    "lag_s": ton["onset_s"] - ron["onset_s"],
                }
            )
    return pairs


def cross_correlation_lag_s(
    t_a: np.ndarray, y_a: np.ndarray, t_b: np.ndarray, y_b: np.ndarray
) -> float | None:
    # @brief Whole-recording lag estimate (a relative to b) via cross-correlation.
    # @return Lag in seconds (positive = a later than b), or None when not computable.
    t0 = max(np.nanmin(t_a), np.nanmin(t_b))
    t1 = min(np.nanmax(t_a), np.nanmax(t_b))
    if not (math.isfinite(t0) and math.isfinite(t1)) or t1 - t0 < 2.0:
        return None
    grid = np.arange(t0, t1, 1.0 / XCORR_RATE_HZ)
    a = np.interp(grid, t_a, y_a)
    b = np.interp(grid, t_b, y_b)
    a = (a - a.mean()) / (a.std() or 1.0)
    b = (b - b.mean()) / (b.std() or 1.0)
    corr = np.correlate(a, b, mode="full")
    lag_samples = int(np.argmax(corr)) - (grid.size - 1)
    return lag_samples / XCORR_RATE_HZ


# ---------------------------------------------------------------------------
# Verdict records
# ---------------------------------------------------------------------------

_SYMBOL = {"PASS": "[ OK ]", "WARN": "[WARN]", "FAIL": "[FAIL]",
           "ABSENT": "[ OK ]", "PRESENT": "[FAIL]", "UNKNOWN": "[ -- ]"}


@dataclass
class Check:
    name: str
    status: str  # PASS | WARN | FAIL
    detail: str
    remediation: str = ""


@dataclass
class Issue:
    name: str
    status: str  # ABSENT | PRESENT | WARN | UNKNOWN
    meaning: str
    detail: str
    remediation: str = ""


# ---------------------------------------------------------------------------
# Stage A: config / freshness validation (pure evaluators take plain dicts)
# ---------------------------------------------------------------------------


def _get(cfg: dict | None, *path, default=None):
    cur = cfg
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def evaluate_gui_config(cfg: dict | None) -> list[Check]:
    # @brief Validate RS485_GUI capture-relevant config.
    if cfg is None:
        return [Check("GUI config", "FAIL", "RS485_GUI/config/config.yaml not found",
                      "Pass --config-gui or run from the repo.")]
    checks: list[Check] = []

    def flag(name, ok, detail, fix):
        checks.append(Check(name, "PASS" if ok else "FAIL", detail, "" if ok else fix))

    flag("GUI logger.enabled", _get(cfg, "logger", "enabled") is True,
         f"logger.enabled={_get(cfg, 'logger', 'enabled')}", "Set logger.enabled=true to capture ndjson.")
    flag("GUI logger.async_logging", _get(cfg, "logger", "async_logging") is True,
         f"async_logging={_get(cfg, 'logger', 'async_logging')}",
         "Set logger.async_logging=true (keeps the serial loop from stalling).")
    flag("GUI ipc.enabled", _get(cfg, "ipc", "enabled") is True,
         f"ipc.enabled={_get(cfg, 'ipc', 'enabled')}", "Set ipc.enabled=true to publish to the bridge.")
    flag("GUI ipc.async_publish", _get(cfg, "ipc", "async_publish") is True,
         f"async_publish={_get(cfg, 'ipc', 'async_publish')}",
         "Set ipc.async_publish=true (reduces reference-path jitter).")
    policy = _get(cfg, "active_send", "timestamp_policy")
    flag("GUI active_send.timestamp_policy", policy == "batch_end_anchored",
         f"timestamp_policy={policy}", "Use batch_end_anchored (calibration-safe).")
    has_relax = _get(cfg, "active_send", "max_chain_lead_s") is not None
    flag("GUI chain-lead relax present", has_relax,
         f"max_chain_lead_s={_get(cfg, 'active_send', 'max_chain_lead_s')}",
         "Update RS485_GUI to the build with max_chain_lead_s (anti-ratchet).")
    code = _get(cfg, "device", "active_send_frequency_code")
    hz = ACTIVE_SEND_FREQ_CODE_TO_VALUE.get(int(code)) if code is not None else None
    checks.append(Check("GUI board rate", "PASS" if hz else "WARN",
                        f"active_send_frequency_code={code} -> {hz} Hz", ""))
    return checks


def evaluate_bridge_config(cfg: dict | None) -> list[Check]:
    # @brief Validate LSL_Bridge timestamping config.
    if cfg is None:
        return [Check("Bridge config", "FAIL", "LSL_Bridge/conf/config.yaml not found",
                      "Pass --config-bridge or run from the repo.")]
    checks: list[Check] = []
    policy = _get(cfg, "target_timestamping", "policy")
    checks.append(Check("Bridge target_timestamping.policy",
                        "PASS" if policy == "device_clock_anchor" else "WARN",
                        f"policy={policy}",
                        "" if policy == "device_clock_anchor" else "device_clock_anchor preserves cadence."))
    drift = _get(cfg, "target_timestamping", "max_anchor_drift_s")
    drift_ok = isinstance(drift, (int, float)) and drift <= 0.020
    checks.append(Check("Bridge max_anchor_drift_s",
                        "PASS" if drift_ok else "WARN",
                        f"max_anchor_drift_s={drift}",
                        "" if drift_ok else "Tighten to <=0.020 to bound target early-drift."))
    return checks


def evaluate_viewer_config(cfg: dict | None, session_captured: bool) -> list[Check]:
    # @brief Validate LSL_Viewer diagnostics (evidence-based) + report current alignment.
    if cfg is None:
        return [Check("Viewer config", "FAIL", "LSL_Viewer/conf/config.yaml not found",
                      "Pass --config-viewer or run from the repo.")]
    checks: list[Check] = []
    diag = _get(cfg, "diagnostics", "enabled")
    # The config default is intentionally false (operators override at launch with
    # diagnostics.enabled=true). The authoritative evidence is a captured session.
    if session_captured:
        checks.append(Check("Viewer diagnostics", "PASS",
                            "session recorded (metrics/sample CSVs present)", ""))
    elif diag is True:
        checks.append(Check("Viewer diagnostics", "PASS",
                            "diagnostics.enabled=true in config", ""))
    else:
        checks.append(Check("Viewer diagnostics", "FAIL",
                            "no session captured and diagnostics.enabled=false",
                            "Launch the viewer with diagnostics.enabled=true, or pass --viewer-session."))
    ta = _get(cfg, "viewer", "xy_correlation", "time_alignment") or {}
    checks.append(Check("Viewer time_alignment (current)", "PASS",
                        f"mode={ta.get('mode')} manual_reference_shift_s={ta.get('manual_reference_shift_s')}",
                        ""))
    return checks


def evaluate_gui_log_freshness(first_diag_keys: set[str] | None) -> Check:
    # @brief The GUI ndjson must carry post-fix diagnostic fields (current binary).
    required = {"chain_relax_s", "effective_dt_s", "serial_in_waiting_at_decode"}
    if first_diag_keys is None:
        return Check("GUI log freshness", "WARN", "no --gui-ndjson provided",
                     "Pass --gui-ndjson <raw_signal.ndjson> to verify the running binary.")
    missing = required - first_diag_keys
    if missing:
        return Check("GUI log freshness", "FAIL",
                     f"missing diagnostic fields: {sorted(missing)}",
                     "Capture used an OLD GUI binary. Rebuild/restart RS485_GUI from the current branch.")
    return Check("GUI log freshness", "PASS", "post-fix diagnostic fields present", "")


# ---------------------------------------------------------------------------
# Stage B: issue evaluators (pure; take scalars so they are unit-testable)
# ---------------------------------------------------------------------------


def evaluate_ratchet(stamp_age_median_ms: float, adjusted_frac: float,
                     relaxed_frac: float, chain_lead_median_ms: float | None) -> Issue:
    meaning = ("Reference LSL timestamps ratcheting into the future: the batch_end "
               "monotonic guard pushes stamps forward and never relaxes, so the "
               "reference step appears ~200 ms late.")
    lead = "n/a" if chain_lead_median_ms is None else f"{chain_lead_median_ms:+.1f} ms"
    detail = (f"stamp age (received-published) median={stamp_age_median_ms:+.1f} ms "
              f"(>=0 good); monotonic_adjusted={adjusted_frac*100:.1f}% "
              f"chain_relaxed={relaxed_frac*100:.1f}% chain_lead median={lead}")
    if stamp_age_median_ms <= RATCHET_FUTURE_AGE_MS:
        return Issue("Ratchet", "PRESENT", meaning, detail,
                     "RS485_GUI _decode_batch chain-lead squeeze/EWMA; ensure current binary.")
    status = "WARN" if stamp_age_median_ms <= RATCHET_WARN_AGE_MS else "ABSENT"
    return Issue("Ratchet", status, meaning, detail, "")


def evaluate_throughput(delivered_hz: float, board_hz: float,
                        in_waiting_decile_medians: list[float] | None) -> Issue:
    meaning = ("GUI cannot drain the serial port at the board rate, so frames back "
               "up and the reference stream is delivered progressively late.")
    frac = delivered_hz / board_hz if board_hz else 0.0
    trend = ""
    growing = False
    if in_waiting_decile_medians and len(in_waiting_decile_medians) >= 2:
        growing = (in_waiting_decile_medians[-1] - in_waiting_decile_medians[0]) > THROUGHPUT_INWAIT_GROWTH
        trend = f"; in_waiting decile medians={[round(x) for x in in_waiting_decile_medians]}"
    detail = f"delivered={delivered_hz:.0f} Hz vs board={board_hz:.0f} Hz ({frac*100:.0f}%){trend}"
    if frac < THROUGHPUT_RATE_FRAC or growing:
        return Issue("Throughput deficit", "PRESENT", meaning, detail,
                     "RS485_GUI async logging + async ZMQ publish + throttled hot-path logs.")
    return Issue("Throughput deficit", "ABSENT", meaning, detail, "")


def evaluate_jitter(in_waiting_p95: float | None, in_waiting_max: float | None,
                    onset_spread_ms: float | None) -> Issue:
    meaning = ("Bursty serial reads / worker stalls inject variable latency, so the "
               "reference offset is not constant and a single shift cannot fully align it.")
    parts = []
    if onset_spread_ms is not None:
        parts.append(f"onset spread={onset_spread_ms:.0f} ms")
    if in_waiting_p95 is not None:
        parts.append(f"in_waiting p95={in_waiting_p95:.0f}B max={in_waiting_max:.0f}B")
    detail = "; ".join(parts) if parts else "insufficient data"
    spread_bad = onset_spread_ms is not None and onset_spread_ms > JITTER_SPREAD_MS
    burst_bad = in_waiting_p95 is not None and in_waiting_p95 > JITTER_INWAIT_P95_BYTES
    if onset_spread_ms is None and in_waiting_p95 is None:
        return Issue("Jitter", "UNKNOWN", meaning, detail,
                     "Provide bridge CSVs and --gui-ndjson to assess jitter.")
    if spread_bad or burst_bad:
        return Issue("Jitter", "PRESENT", meaning, detail,
                     "Reduce worker stalls (async publish/logging); shrink delivery_window_s if needed.")
    return Issue("Jitter", "ABSENT", meaning, detail, "")


def evaluate_relay_offset(published_median_ms: float | None, published_spread_ms: float | None,
                          honest_median_ms: float | None) -> Issue:
    meaning = ("Stable physical relay latency: the reference hops board->RS485->GUI->"
               "ZMQ->bridge and is stamped at GUI read time (the frame carries no "
               "acquisition timestamp), so it lags the directly-connected target.")
    if published_median_ms is None:
        return Issue("Relay offset", "UNKNOWN", meaning, "no pairable step onsets",
                     "Record 3-5 fast force steps with quiet baselines.")
    honest = "n/a" if honest_median_ms is None else f"{honest_median_ms:+.1f} ms"
    spread = "n/a" if published_spread_ms is None else f"{published_spread_ms:.0f} ms"
    detail = (f"published onset lag median={published_median_ms:+.1f} ms "
              f"(spread={spread}); honest-clock lag={honest}")
    status = "PASS" if (published_spread_ms is not None and published_spread_ms < RELAY_STABLE_SPREAD_MS) else "WARN"
    return Issue("Relay offset", status, meaning, detail,
                 "Compensate with manual_reference_shift_s (see recommendation).")


@dataclass
class Recommendation:
    status: str  # READY | BLOCKED | TUNE_FIRST
    shift_s: float | None
    residual_ms: float | None
    message: str


def recommend_reference_shift_s(published_median_ms: float | None,
                                published_spread_ms: float | None,
                                jitter_present: bool, preflight_failed: bool) -> Recommendation:
    # @brief shift = published onset lag (target - reference). alignment.py adds the
    #        shift to ref_t and ref_t + shift must equal target_t, so
    #        shift = target_onset - reference_onset = lag (negative; moves the
    #        later-stamped reference earlier). Gated on a clean, stable capture.
    if preflight_failed:
        return Recommendation("BLOCKED", None, None,
                              "Fix the preflight FAILs first; the capture is not trustworthy.")
    if published_median_ms is None:
        return Recommendation("BLOCKED", None, None,
                              "No pairable step onsets; record 3-5 fast steps and retry.")
    if jitter_present:
        return Recommendation("TUNE_FIRST", None, None,
                              "Reduce jitter first (offset not stable); then re-measure the shift.")
    shift = round(published_median_ms / 1000.0, 4)
    residual = None if published_spread_ms is None else published_spread_ms / 2.0
    return Recommendation("READY", shift, residual,
                          "Stable offset measured; apply the shift below.")


# ---------------------------------------------------------------------------
# Loaders / extractors
# ---------------------------------------------------------------------------


def load_config(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return OmegaConf.to_container(OmegaConf.load(path), resolve=False)  # type: ignore[return-value]
    except Exception:
        return None


def load_viewer_session(session: Path) -> dict:
    # @brief Load metrics.jsonl and sample CSVs from a viewer session dir.
    out: dict = {}
    metrics_path = session / "metrics.jsonl"
    if metrics_path.exists():
        out["metrics"] = pd.DataFrame(
            json.loads(line) for line in metrics_path.read_text().splitlines() if line.strip()
        )
    for name, key in (("target_samples.csv", "target"), ("reference_samples.csv", "reference")):
        path = session / name
        if path.exists():
            out[key] = pd.read_csv(path)
    return out


def scan_gui_ndjson(path: Path) -> dict:
    # @brief Stream raw_signal.ndjson once; pull diagnostic series for the issue scan.
    # @return dict with first_diag_keys, in_waiting (np.ndarray), chain_lead_ms (np.ndarray).
    in_waiting: list[float] = []
    chain_lead: list[float] = []
    first_keys: set[str] | None = None
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            diag = (row.get("raw_transport") or {}).get("diagnostics") or {}
            if not diag:
                continue
            if first_keys is None:
                first_keys = set(diag.keys())
            if "serial_in_waiting_at_decode" in diag:
                in_waiting.append(float(diag["serial_in_waiting_at_decode"]))
            if "chain_lead_s" in diag:
                chain_lead.append(float(diag["chain_lead_s"]) * 1e3)
    return {
        "first_diag_keys": first_keys,
        "in_waiting": np.asarray(in_waiting, dtype=np.float64),
        "chain_lead_ms": np.asarray(chain_lead, dtype=np.float64),
    }


# ---------------------------------------------------------------------------
# Report printing (Stage C)
# ---------------------------------------------------------------------------


def _print_section(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def _print_check(c: Check) -> None:
    sym = _SYMBOL.get(c.status, "[ ?? ]")
    print(f"  {sym} {c.name}: {c.detail}")
    if c.remediation:
        print(f"         -> {c.remediation}")


def _print_issue(i: Issue) -> None:
    sym = _SYMBOL.get(i.status, "[ ?? ]")
    print(f"\n  {sym} {i.name} — {i.status}")
    print(f"     what it means : {i.meaning}")
    print(f"     measured      : {i.detail}")
    if i.remediation:
        print(f"     remediation   : {i.remediation}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calibration preflight: validate capture + measure XY sync.")
    parser.add_argument("--viewer-session", type=Path, help="LSL_Viewer diagnostics session dir")
    parser.add_argument("--bridge-target-csv", type=Path, help="LSL_Bridge target CSV")
    parser.add_argument("--bridge-reference-csv", type=Path, help="LSL_Bridge reference CSV")
    parser.add_argument("--gui-ndjson", type=Path, help="RS485_GUI raw_signal.ndjson (diagnostics)")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2],
                        help="Repo root for config auto-discovery (default: derived from script path)")
    parser.add_argument("--config-gui", type=Path)
    parser.add_argument("--config-bridge", type=Path)
    parser.add_argument("--config-viewer", type=Path)
    parser.add_argument("--strict", action="store_true",
                        help="Exit non-zero if any preflight check FAILs.")
    args = parser.parse_args(argv)

    gui_cfg = load_config(args.config_gui or args.repo_root / GUI_CONFIG_REL)
    bridge_cfg = load_config(args.config_bridge or args.repo_root / BRIDGE_CONFIG_REL)
    viewer_cfg = load_config(args.config_viewer or args.repo_root / VIEWER_CONFIG_REL)

    # GUI ndjson scan (freshness + diagnostic series)
    gui_scan = scan_gui_ndjson(args.gui_ndjson) if args.gui_ndjson and args.gui_ndjson.exists() else {}

    # Evidence that the viewer recorded a diagnostics session.
    session = load_viewer_session(args.viewer_session) if args.viewer_session else {}
    session_captured = bool(session.get("metrics") is not None or "target" in session or "reference" in session)

    # ---- Stage A: preflight ----
    _print_section("STAGE A — Capture preflight (config + log freshness)")
    checks = (evaluate_gui_config(gui_cfg) + [evaluate_gui_log_freshness(gui_scan.get("first_diag_keys"))]
              + evaluate_bridge_config(bridge_cfg) + evaluate_viewer_config(viewer_cfg, session_captured))
    for c in checks:
        _print_check(c)
    preflight_failed = any(c.status == "FAIL" for c in checks)

    board_hz = 500.0
    code = _get(gui_cfg, "device", "active_send_frequency_code")
    if code is not None:
        board_hz = float(ACTIVE_SEND_FREQ_CODE_TO_VALUE.get(int(code), 500))

    # ---- Stage B: issue scan ----
    _print_section("STAGE B — Issue-chain scan")
    issues: list[Issue] = []

    ref_df = pd.read_csv(args.bridge_reference_csv) if args.bridge_reference_csv else None
    tgt_df = pd.read_csv(args.bridge_target_csv) if args.bridge_target_csv else None

    # Ratchet
    if ref_df is not None and {"received_lsl_ts", "lsl_timestamp_s"} <= set(ref_df.columns):
        age_ms = (ref_df["received_lsl_ts"] - ref_df["lsl_timestamp_s"]) * 1e3
        src = ref_df["timestamp_source"].astype(str) if "timestamp_source" in ref_df else pd.Series([], dtype=str)
        n = max(1, len(src))
        adj = src.str.contains("_monotonic_adjusted").sum() / n if len(src) else 0.0
        rlx = src.str.contains("_chain_relaxed").sum() / n if len(src) else 0.0
        lead_med = float(np.median(gui_scan["chain_lead_ms"])) if gui_scan.get("chain_lead_ms", np.array([])).size else None
        issues.append(evaluate_ratchet(float(age_ms.median()), adj, rlx, lead_med))
    else:
        issues.append(Issue("Ratchet", "UNKNOWN", "needs bridge reference CSV",
                            "missing --bridge-reference-csv or received_lsl_ts column"))

    # Throughput
    inw = gui_scan.get("in_waiting", np.array([]))
    decile = [float(np.median(d)) for d in np.array_split(inw, 10)] if inw.size >= 10 else None
    if ref_df is not None and "received_lsl_ts" in ref_df:
        span = float(ref_df["received_lsl_ts"].iloc[-1] - ref_df["received_lsl_ts"].iloc[0])
        delivered = (len(ref_df) / span) if span > 0 else 0.0
        issues.append(evaluate_throughput(delivered, board_hz, decile))
    else:
        issues.append(Issue("Throughput deficit", "UNKNOWN", "needs bridge reference CSV", "n/a"))

    # Onsets (published + honest) for jitter spread + relay offset
    published_lags_ms: list[float] = []
    honest_lags_ms: list[float] = []
    if tgt_df is not None and ref_df is not None:
        if {"lsl_timestamp_s", "target_raw_count"} <= set(tgt_df.columns) and \
           {"lsl_timestamp_s", "reference_force_N"} <= set(ref_df.columns):
            ton = detect_step_onsets(tgt_df["lsl_timestamp_s"].to_numpy(float), tgt_df["target_raw_count"].to_numpy(float))
            ron = detect_step_onsets(ref_df["lsl_timestamp_s"].to_numpy(float), ref_df["reference_force_N"].to_numpy(float))
            published_lags_ms = [p["lag_s"] * 1e3 for p in pair_onsets(ton, ron)]
        if "arrival_lsl_time_s" in tgt_df and "received_lsl_ts" in ref_df:
            ton_h = detect_step_onsets(tgt_df["arrival_lsl_time_s"].to_numpy(float), tgt_df["target_raw_count"].to_numpy(float))
            ron_h = detect_step_onsets(ref_df["received_lsl_ts"].to_numpy(float), ref_df["reference_force_N"].to_numpy(float))
            honest_lags_ms = [p["lag_s"] * 1e3 for p in pair_onsets(ton_h, ron_h)]

    pub_median = float(np.median(published_lags_ms)) if published_lags_ms else None
    pub_spread = (max(published_lags_ms) - min(published_lags_ms)) if len(published_lags_ms) >= 2 else None
    honest_median = float(np.median(honest_lags_ms)) if honest_lags_ms else None
    inw_p95 = float(np.percentile(inw, 95)) if inw.size else None
    inw_max = float(inw.max()) if inw.size else None

    jitter = evaluate_jitter(inw_p95, inw_max, pub_spread)
    issues.append(jitter)
    issues.append(evaluate_relay_offset(pub_median, pub_spread, honest_median))

    for i in issues:
        _print_issue(i)

    # ---- Stage C: recommendation ----
    _print_section("STAGE C — Recommended configuration")
    rec = recommend_reference_shift_s(pub_median, pub_spread, jitter.status == "PRESENT", preflight_failed)
    if rec.status == "READY":
        print("\n  Reference relay offset is stable. Compensate it in the VIEWER config:\n")
        print(f"    file : {VIEWER_CONFIG_REL}")
        print("    key  : viewer.xy_correlation.time_alignment")
        print("    set  : mode: manual")
        print(f"           manual_reference_shift_s: {rec.shift_s}")
        if rec.residual_ms is not None:
            print(f"\n  Expected residual after the shift: ~+/-{rec.residual_ms:.0f} ms (half the onset spread).")
        print("\n  ** Re-run this preflight and re-measure the shift after ANY setup change")
        print("     (cabling, ports, host, baud, sample rates). The offset is physical. **")
    else:
        print(f"\n  {rec.status}: {rec.message}")

    print("\nNote: reference_clock_s is host-derived (GUI read time), not a device clock; "
          "the relay offset is a host-read-latency compensation, not acquisition truth.")

    if args.strict and preflight_failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
