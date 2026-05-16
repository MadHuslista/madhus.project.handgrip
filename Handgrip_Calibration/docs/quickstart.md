# Handgrip Calibration Quickstart

## Summary

- Use this document for the shortest safe operator path through calibration.
- The canonical primary protocol is `conf/protocol_static_reversible_staircase_v3.yaml`.
- Calibration requires both LSL streams: `HandgripTarget` and `HandgripReference`.
- Stop if preflight fails, if the force fixture slips, or if a captured session lacks target/reference data.

## Prerequisites

- Physical setup validated with PM58 and target handgrip in the same force path.
- Firmware emits D2 lines: `D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>`.
- `RS485_GUI` is running and publishes reference measurements.
- `LSL_Bridge` publishes `HandgripTarget` and `HandgripReference`.
- Optional but recommended: `LSL_Viewer` shows both streams and XY behavior is plausible.

## Commands

From the repository root, sync dependencies once:

```bash
uv sync
```

Then run calibration commands from the component directory:

```bash
cd Handgrip_Calibration
```

### 1 — Preflight

```bash
uv run handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml
```

Expected result:

- target stream discovered,
- reference stream discovered,
- required channels exist,
- protocol YAML validates,
- component config snapshots are resolvable.

Stop if preflight fails.

### 2 — Record primary protocol

```bash
uv run handgrip-cal record --config conf/protocol_static_reversible_staircase_v3.yaml
```

Expected result:

- operator prompts guide baseline/preload/holds,
- session folder is created under `data/calibration/<session_id>/`,
- target/reference samples and protocol events are written.

### 3 — Fit model candidates

```bash
uv run handgrip-cal fit data/calibration/<session_id> --config conf/protocol_static_reversible_staircase_v3.yaml
```

Expected result:

- accepted holds are reduced into a fitting dataset,
- candidate models are evaluated,
- selected model and diagnostics are written.

### 4 — Generate report

```bash
uv run handgrip-cal report data/calibration/<session_id> --config conf/protocol_static_reversible_staircase_v3.yaml
```

Expected result:

- report files are created in the session folder,
- model comparison and residual interpretation are available,
- deployment recommendation is explicit.

### 5 — Holdout validation

```bash
uv run handgrip-cal record --config conf/protocol_holdout_verification.yaml
uv run handgrip-cal validate-holdout data/calibration/<holdout_session_id> \
  --model data/calibration/<fit_session_id>/fit_result.json \
  --config conf/protocol_holdout_verification.yaml
uv run handgrip-cal report data/calibration/<holdout_session_id> --config conf/protocol_holdout_verification.yaml
```

Expected result:

- accepted model is tested on independent data,
- out-of-sample error is reported,
- deployment is accepted only if validation passes.

## Expected session location

```text
Handgrip_Calibration/data/calibration/<session_id>/
```

Expected artifact classes:

| Artifact class    | Purpose                                                                |
| ----------------- | ---------------------------------------------------------------------- |
| target samples    | Target stream samples from `HandgripTarget`.                           |
| reference samples | Reference stream samples from `HandgripReference`.                     |
| protocol events   | Baseline/hold/dynamic/holdout markers.                                 |
| copied configs    | Reproducibility snapshot for bridge/viewer/RS485/calibration settings. |
| fit artifacts     | Selected model, candidate comparison, residual metrics.                |
| reports           | Human-readable Markdown/HTML report and plots.                         |

## Stop conditions

Stop before fitting if:

- preflight cannot find both streams,
- target or reference sample file is missing,
- fixture slipped during holds,
- reference force is saturated/frozen/noisy,
- target raw count does not respond monotonically to force,
- accepted holds do not cover the intended operating range.

Stop before deployment if:

- selected model fails the residual threshold,
- residual plots show structured errors,
- holdout validation fails,
- dynamic validation reveals unacceptable lag/hysteresis,
- recommended constants cannot be traced back to `fit_result.json`.

## Next docs

- [`protocols.md`](protocols.md)
- [`recording.md`](recording.md)
- [`fitting-and-model-selection.md`](fitting-and-model-selection.md)
- [`reports-and-outputs.md`](reports-and-outputs.md)
- [`applying-calibration-results.md`](applying-calibration-results.md)
