# Handoff Workflow Validation

## Summary

- This checklist validates that the documented workflows are executable by a new operator before handoff.
- It combines software checks, hardware checks, and interpretation gates.
- Use this after Phase 11 documentation validation has passed.
- The goal is not to prove the system is perfect; the goal is to prove the handoff recipient can follow the docs from hardware setup to analysis output.

## Handoff validation scope

| Area | Validation target |
| --- | --- |
| Firmware | Serial monitor emits `M2` and `D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>` frames. |
| RS485 GUI | Reference-force data arrives from the acquisition board. |
| LSL Bridge | `HandgripTarget`, `HandgripReference`, and `HandgripComponentEvents` are published or logged as expected. |
| LSL Viewer | Target/reference time series and XY correlation render correctly. |
| Calibration | Preflight, smoke recording, fit, and report complete. |
| Analysis | Smoke-stage or Stage 6 analysis completes and writes expected output. |

## Software validation

Run from the repository root:

```bash
uv sync
uv run pytest
```

If the full test suite is too slow for a handoff rehearsal, record which test subset was used and why.

Suggested focused test subsets:

```bash
uv run pytest LSL_Bridge/tests/unit/test_parser.py
uv run pytest LSL_Bridge/tests/unit/test_timestamping.py
uv run pytest RS485_GUI/tests/integration/test_active_send_parser.py
uv run pytest LSL_Viewer/tests/unit/test_alignment.py
uv run pytest Handgrip_Calibration/tests
uv run pytest Handgrip_Analysis/tests
```

## Hardware workflow validation

### Gate 1 — Firmware serial monitor shows D2 frames

Command:

```bash
platformio device monitor --baud 115200
```

Pass condition:

- `M2` appears after reset.
- Data lines follow `D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>`.
- `seq` increases.
- `raw_count` changes under force.

### Gate 2 — RS485 GUI receives reference force

Command:

```bash
cd RS485_GUI
uv run rs485-gui
```

Pass condition:

- GUI opens.
- Reference value changes under force.
- Logs show valid frames.

### Gate 3 — LSL bridge publishes both streams

Command:

```bash
cd LSL_Bridge
uv run lsl-bridge
```

Pass condition:

- `HandgripTarget` is published.
- `HandgripReference` is published.
- Parser warnings are not continuous.

### Gate 4 — Viewer displays target/reference and XY plot

Command:

```bash
cd LSL_Viewer
uv run lsl-viewer
```

Pass condition:

- target time series updates,
- reference time series updates,
- XY correlation responds to force changes,
- no progressive reference lag is visible during smoke validation.

### Gate 5 — Calibration preflight passes

Command:

```bash
cd Handgrip_Calibration
uv run handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml
```

Pass condition:

- target stream found,
- reference stream found,
- required channels found,
- component config snapshot paths are valid.

### Gate 6 — Smoke calibration recording completes

Command:

```bash
uv run handgrip-cal record --config conf/protocol_fast_smoke_test.yaml
```

Pass condition:

- session directory created,
- target/reference files present,
- event/marker file present,
- no missing stream errors.

### Gate 7 — Calibration fit/report complete

Command pattern:

```bash
uv run handgrip-cal fit data/calibration/<session_id> --config conf/protocol_fast_smoke_test.yaml
uv run handgrip-cal report data/calibration/<session_id> --config conf/protocol_fast_smoke_test.yaml
```

Pass condition:

- fit result generated,
- report generated,
- report identifies model/metrics/residuals.

### Gate 8 — Analysis smoke test completes

Command pattern:

```bash
cd Handgrip_Analysis
uv run ha-stage --help
```

Then run the shortest documented smoke stage available in the current analysis docs/config.

Pass condition:

- output directory created,
- metrics/report artifact generated,
- no missing-manifest or missing-column failure.

## Handoff worksheet

| Gate | Pass/fail | Evidence path / screenshot | Notes |
| --- | --- | --- | --- |
| Firmware D2 serial |  |  |  |
| RS485 reference force |  |  |  |
| LSL bridge streams |  |  |  |
| Viewer plots |  |  |  |
| Calibration preflight |  |  |  |
| Smoke recording |  |  |  |
| Fit/report |  |  |  |
| Analysis smoke |  |  |  |

## Final acceptance condition

A handoff candidate passes when a student operator can complete Gates 1–8 using the documentation without undocumented assistance.
