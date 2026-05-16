# LSL Viewer Documentation

## Summary

- `LSL_Viewer` is the browser-based visualization component for live LSL streams and CSV/XDF replay.
- It is an observer/diagnostic tool: it must not redefine acquisition, calibration, or stream semantics.
- It displays `HandgripTarget`, `HandgripReference`, time-series panels, XY correlation, timing diagnostics, and optional calibration marker overlays.
- Display downsampling and XY alignment are **viewer-local** operations. They do not modify LSL streams, replay files, or calibration data.

## Audience

| Reader | Use this page to... |
| --- | --- |
| Operator | Start the viewer and validate expected plots before calibration. |
| Calibration operator | Check target/reference behavior and XY correlation without changing data semantics. |
| Maintainer | Find configuration, architecture, and development references. |
| Student developer | Learn where to add plots, controls, channel labels, or replay behavior safely. |

## Component boundary

`LSL_Viewer` consumes data from:

- live LSL streams published by `LSL_Bridge`,
- CSV replay files from bridge/calibration outputs,
- XDF replay files when `pyxdf` is installed,
- optional calibration marker event files.

It does **not** own:

- firmware serial parsing,
- RS485 acquisition,
- LSL stream publication,
- calibration model fitting,
- persistent DSP/filter deployment.

## Documentation map

| Document | Purpose |
| --- | --- |
| [`quickstart.md`](quickstart.md) | Run the live viewer and validate expected plots. |
| [`configuration.md`](configuration.md) | Full `conf/config.yaml` reference. |
| [`xy-correlation.md`](xy-correlation.md) | XY plot behavior, alignment policy, lag troubleshooting. |
| [`live-csv-xdf-modes.md`](live-csv-xdf-modes.md) | Live mode, live validation mode, CSV replay, XDF replay. |
| [`architecture.md`](architecture.md) | Stream buffers, UI refresh, plotting model, marker overlays. |
| [`development.md`](development.md) | Add plots, signals, toggles, replay behavior, and tests. |

## Related system docs

| System doc | Why it matters |
| --- | --- |
| [`../../docs/workflows/full-live-viewer-quickstart.md`](../../docs/workflows/full-live-viewer-quickstart.md) | Full process order: `RS485_GUI` → `LSL_Bridge` → `LSL_Viewer`. |
| [`../../docs/architecture/stream-contracts.md`](../../docs/architecture/stream-contracts.md) | Canonical target/reference/event stream contracts. |
| [`../../docs/architecture/timestamping-and-synchronization.md`](../../docs/architecture/timestamping-and-synchronization.md) | Timing assumptions and lag diagnosis. |
| [`../../docs/workflows/handgrip-calibration.md`](../../docs/workflows/handgrip-calibration.md) | How viewer validation fits into calibration. |
| [`../../docs/troubleshooting/viewer-lag-or-xy-delay.md`](../../docs/troubleshooting/viewer-lag-or-xy-delay.md) | Symptom-first lag troubleshooting once created. |

## Expected runtime streams

| Stream | Producer | Viewer role |
| --- | --- | --- |
| `HandgripTarget` | `LSL_Bridge` | Target raw count, filtered/current units, device timing. |
| `HandgripReference` | `LSL_Bridge` | Reference force and reference timing. |
| `HandgripCalibrationMarkers` / events file | `Handgrip_Calibration` | Optional marker overlays during replay/analysis. |

## Validation checklist

- [ ] `README.md` links to this component docs index.
- [ ] `quickstart.md` explains live viewer startup and expected plots.
- [ ] `configuration.md` documents all top-level `conf/config.yaml` sections.
- [ ] `xy-correlation.md` clearly states that XY alignment is display-only.
- [ ] `live-csv-xdf-modes.md` distinguishes live and replay behavior.
- [ ] `architecture.md` identifies buffer/UI/plotting boundaries.
- [ ] `development.md` names relevant source files and tests.
