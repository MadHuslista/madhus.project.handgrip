"""Unit tests for scripts/calibration_preflight.py pure evaluators.

The script is not a package module; import it by path (like operators run it).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "calibration_preflight.py"
_spec = importlib.util.spec_from_file_location("calibration_preflight", _SCRIPT)
cp = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
# Register before exec so @dataclass can resolve string annotations (PEP 563).
sys.modules[_spec.name] = cp
_spec.loader.exec_module(cp)


def _good_gui_cfg():
    return {
        "logger": {"enabled": True, "async_logging": True},
        "ipc": {"enabled": True, "async_publish": True},
        "active_send": {"timestamp_policy": "batch_end_anchored", "max_chain_lead_s": 0.05},
        "device": {"active_send_frequency_code": 8},
    }


class TestConfigChecks:
    def test_gui_config_all_pass(self):
        checks = cp.evaluate_gui_config(_good_gui_cfg())
        assert all(c.status == "PASS" for c in checks), [c for c in checks if c.status != "PASS"]

    def test_gui_config_flags_async_off(self):
        cfg = _good_gui_cfg()
        cfg["ipc"]["async_publish"] = False
        statuses = {c.name: c.status for c in cp.evaluate_gui_config(cfg)}
        assert statuses["GUI ipc.async_publish"] == "FAIL"

    def test_gui_config_missing_file(self):
        checks = cp.evaluate_gui_config(None)
        assert checks[0].status == "FAIL"

    def test_bridge_drift_threshold(self):
        def cfg(drift):
            return {"target_timestamping":
                    {"policy": "device_clock_anchor", "max_anchor_drift_s": drift}}
        ok = {c.name: c.status for c in cp.evaluate_bridge_config(cfg(0.020))}
        warn = {c.name: c.status for c in cp.evaluate_bridge_config(cfg(0.050))}
        assert ok["Bridge max_anchor_drift_s"] == "PASS"
        assert warn["Bridge max_anchor_drift_s"] == "WARN"

    def test_viewer_diagnostics_evidence_based(self):
        cfg = {"diagnostics": {"enabled": False},
               "viewer": {"xy_correlation": {"time_alignment": {}}}}
        # Session captured overrides the config default.
        captured = {c.name: c.status
                    for c in cp.evaluate_viewer_config(cfg, session_captured=True)}
        none = {c.name: c.status
                for c in cp.evaluate_viewer_config(cfg, session_captured=False)}
        assert captured["Viewer diagnostics"] == "PASS"
        assert none["Viewer diagnostics"] == "FAIL"

    def test_gui_log_freshness(self):
        full = {"chain_relax_s", "effective_dt_s", "serial_in_waiting_at_decode",
                "monotonic_adjust_s"}
        old = {"monotonic_adjust_s", "batch_end_lsl_ts"}
        assert cp.evaluate_gui_log_freshness(full).status == "PASS"
        assert cp.evaluate_gui_log_freshness(old).status == "FAIL"
        assert cp.evaluate_gui_log_freshness(None).status == "WARN"


class TestIssueEvaluators:
    def test_ratchet_present_when_future_stamped(self):
        assert cp.evaluate_ratchet(-180.0, 0.999, 0.0, 196.0).status == "PRESENT"

    def test_ratchet_absent_when_age_positive(self):
        assert cp.evaluate_ratchet(19.0, 0.96, 0.03, 37.0).status == "ABSENT"

    def test_throughput_deficit_present(self):
        assert cp.evaluate_throughput(233.0, 500.0, [0, 200, 400, 800, 1200]).status == "PRESENT"

    def test_throughput_ok(self):
        assert cp.evaluate_throughput(500.0, 500.0, [0, 0, 0, 0, 0]).status == "ABSENT"

    def test_jitter_present_on_large_spread(self):
        assert cp.evaluate_jitter(200.0, 800.0, 90.0).status == "PRESENT"

    def test_jitter_absent_when_tight(self):
        assert cp.evaluate_jitter(189.0, 1782.0, 32.0).status == "ABSENT"

    def test_jitter_unknown_without_data(self):
        assert cp.evaluate_jitter(None, None, None).status == "UNKNOWN"

    def test_relay_offset_stable(self):
        assert cp.evaluate_relay_offset(-123.0, 32.0, -122.0).status == "PASS"

    def test_relay_offset_unstable(self):
        assert cp.evaluate_relay_offset(-123.0, 120.0, -122.0).status == "WARN"


class TestRecommendation:
    def test_blocked_on_preflight_fail(self):
        rec = cp.recommend_reference_shift_s(
            -123.2, 32.0, jitter_present=False, preflight_failed=True)
        assert rec.status == "BLOCKED" and rec.shift_s is None

    def test_tune_first_on_jitter(self):
        rec = cp.recommend_reference_shift_s(
            -123.2, 90.0, jitter_present=True, preflight_failed=False)
        assert rec.status == "TUNE_FIRST"

    def test_ready_shift_equals_published_lag_sign(self):
        # Reference is stamped later (lag negative); shift must be negative and equal
        # the lag so ref_t + shift == target_t.
        rec = cp.recommend_reference_shift_s(
            -123.2, 32.0, jitter_present=False, preflight_failed=False)
        assert rec.status == "READY"
        assert rec.shift_s == -0.1232
        assert rec.residual_ms == 16.0

    def test_blocked_without_onsets(self):
        rec = cp.recommend_reference_shift_s(
            None, None, jitter_present=False, preflight_failed=False)
        assert rec.status == "BLOCKED"


class TestOnsetSignEndToEnd:
    def test_shift_cancels_synthetic_offset(self):
        # Build a target step and an identical reference step delayed by +0.12 s.
        t = np.arange(0.0, 6.0, 0.002)
        step = np.where(t >= 3.0, 1.0, 0.0)
        ton = cp.detect_step_onsets(t, step)
        ron = cp.detect_step_onsets(t + 0.12, step)  # reference stamped 120 ms later
        pairs = cp.pair_onsets(ton, ron)
        assert pairs, "expected a paired onset"
        lag_ms = pairs[0]["lag_s"] * 1e3
        assert lag_ms < -100  # reference later => negative lag
        rec = cp.recommend_reference_shift_s(
            lag_ms, 5.0, jitter_present=False, preflight_failed=False)
        # Applying the recommended shift to the reference onset should meet the target.
        assert abs((ron[0]["onset_s"] + rec.shift_s) - ton[0]["onset_s"]) < 0.01
