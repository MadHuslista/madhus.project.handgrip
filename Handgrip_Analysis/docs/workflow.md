# Handgrip Analysis Workflow

## Summary

This document covers the complete analysis workflow: recording and exporting source data, organizing input files, creating and updating manifests, running analysis stages, and applying filter recommendations.

Analysis operates exclusively on saved files. It must not be run until calibration sessions or curated CSV exports exist.

## Prerequisites

- Target CSV captures available: either direct `LSL_Bridge` recordings or `Handgrip_Calibration` session exports. See [Phase 1](#phase-1--prepare-input-data) below.
- `LSL_Bridge` running and producing valid `D2` frames before recording. See [LSL_Bridge/docs/workflow.md](../../LSL_Bridge/docs/workflow.md).
- Python dependencies installed: `uv sync` from repo root.
- Config files present under `Handgrip_Analysis/conf/`.

---

## Phase 1 — Prepare input data

### 1.1 Record source sessions

Analysis requires CSV files in the `LSL_Bridge` target stream format. Two recording paths produce compatible files:

**Direct `LSL_Bridge` recording** — suitable for all characterization stages without a calibration session:

Start `LSL_Bridge` with CSV sinks enabled, run the capture protocol, then copy and rename the output file. See [LSL_Bridge/docs/workflow.md](../../LSL_Bridge/docs/workflow.md) for bridge startup, configuration, and output locations.

**`Handgrip_Calibration` session** — required when calibrating sensor model parameters:

Run `handgrip-cal record` to produce a session folder containing `target.csv`. See [Handgrip_Calibration/docs/workflow.md](../../Handgrip_Calibration/docs/workflow.md).

Both paths produce CSV files with the required `target_raw_count` column. Full column reference: [LSL_Bridge/docs/stream-contracts.md](../../LSL_Bridge/docs/stream-contracts.md).

#### Bridge-side settings during characterization

Before recording any stage, confirm these settings in `LSL_Bridge/conf/config.yaml`:

- Prefer 80 SPS on the HX711 during characterization.
- Log the least-processed signal available.
- Keep both `target_raw_count` and `target_filtered_units` in the output CSV (`csv.target.enabled: true`).
- Do not change mechanics, cabling, or mounting between trials unless that change is the test condition.
- Record condition metadata externally (ambient temperature, protocol, power source).

#### Per-stage capture protocols

Capture protocols by stage (duration, load conditions, trial types), along with full purpose, input requirements, and interpretation: [Handgrip_Analysis/docs/stages.md](stages.md).

Stage 6 requires no new capture — it reuses Stage 2 and Stage 4 outputs.

Handgrip_Calibration session outputs are under:

```text
Handgrip_Calibration/data/calibration/<session_id>/
```

### 1.2 Export signals to analysis input directory

Copy one file per trial into the analysis input directory:

```text
Handgrip_Analysis/data/calibration_signals/
```

**From a direct `LSL_Bridge` recording:**

The bridge writes to a fixed path. After each trial capture, copy and rename the file before starting the next trial (the bridge overwrites it on restart):

```text
LSL_Bridge/data/target_handgrip_samples_v2.csv  →  copy and rename
```

**From a `Handgrip_Calibration` session:**

Each calibration session writes its captured target stream to:

```text
Handgrip_Calibration/data/calibration/<session_id>/target.csv
```

This is the `TargetCsvSink` output. See [LSL_Bridge/docs/stream-contracts.md](../../LSL_Bridge/docs/stream-contracts.md) for the column layout.

Recommended file naming convention:

```text
<YYYYMMDD>_<stage>_<condition>_trial<NN>.csv
```

Example:

```text
20260402_stage1_cold_start_trial01.csv
20260402_stage2_rest_after_warmup_trial01.csv
20260402_stage4_fast_max_trial01.csv
```

Keep the `target.csv` column layout when exporting. The manifest `channel` field is a logical selector, not a literal column name: `raw` maps to the `target_raw_count` column (the raw HX711 ADC count, and the calibration-authoritative signal) and `filtered` maps to `target_filtered_units` (see `Handgrip_Analysis/src/handgrip_analysis/io.py`). Analysis fails fast if `target_raw_count` is absent, so do not rename or drop that column.

### 1.3 Create or update the manifest

Manifests are CSV files that tell each analysis stage which files to load, how to label them, and how to group outputs.

Manifest location:

```text
Handgrip_Analysis/data/manifests/
```

Existing manifests (use as templates):

```text
all_runnable_manifest.csv         — all stages, all conditions
analysis_stages_1_4_manifest.csv  — stages 1–4 only
stage6_filter_review_manifest.csv — Stage 6 filter design inputs
```

Manifest columns:

| Column           | Required | Purpose                                                  |
| ---------------- | -------- | -------------------------------------------------------- |
| `stage`          | yes      | Stage this row applies to: `stage1`…`stage6`             |
| `condition`      | yes      | Human-readable condition label                           |
| `trial_type`     | yes      | Trial type classification                                |
| `trial_id`       | yes      | Trial identifier, e.g. `trial01`                         |
| `session_id`     | yes      | Session identifier for provenance                        |
| `path`           | yes      | Relative path to the CSV file from the manifest location |
| `channel`        | no       | Signal selector, defaults to `raw`: `raw` (→ `target_raw_count`) or `filtered` (→ `target_filtered_units`) |
| `load_nominal_n` | optional | Nominal force in Newtons, for loaded stages              |
| `include`        | yes      | `True` to include, `False` to exclude                    |
| `notes`          | optional | Any notes about the trial                                |

Path convention: paths in the manifest are relative to the manifest file location. For files in `data/calibration_signals/`, the path is:

```text
../calibration_signals/<filename>.csv
```

After adding new trials, verify the manifest by running a single stage with `--help` to confirm the manifest parses without errors.

---

## Phase 2 — Run analysis stages

### 2.1 Check available commands

```bash
cd Handgrip_Analysis
uv run ha-run-all --help
uv run ha-stage --help
```

### 2.2 Run all stages from a manifest

```bash
cd Handgrip_Analysis
uv run ha-run-all \
  manifest=data/manifests/all_runnable_manifest.csv \
  base_outdir=data/analysis_results/batch_run
```

### 2.3 Run a single stage

Generic shape:

```bash
cd Handgrip_Analysis
uv run ha-stage stage=<stage_name> \
  manifest=data/manifests/<manifest_file>.csv \
  outdir=data/analysis_results/<stage_name>
```

Stage 6 with filter config:

```bash
uv run ha-stage stage=stage6 \
  manifest=data/manifests/stage6_filter_review_manifest.csv \
  outdir=data/analysis_results/stage6 \
  filter_config=conf/filters/candidates.yaml
```

### 2.4 Stage purposes and outputs

Stage purposes, inputs, and key outputs by stage: [Handgrip_Analysis/docs/stages.md](stages.md).

Output locations:

```text
Handgrip_Analysis/data/analysis_results/<stage>/
```

---

## Phase 3 — Interpret and apply Stage 6 filter recommendation

Stage 6 answers: which filter candidate best balances noise reduction, lag, signal distortion, and implementation complexity?

When interpreting the Stage 6 report:

- prefer filters that improve signal quality without hiding important dynamics,
- do not choose a filter solely because it looks smoother,
- treat latency and phase behavior as calibration-relevant,
- preserve raw data whenever possible.

Apply the recommendation based on target:

| Recommendation target   | Action                                                                                  |
| ----------------------- | --------------------------------------------------------------------------------------- |
| `LSL_Bridge` processing | Update relevant processing config; validate live stream behavior                        |
| Viewer display only     | Update viewer config; do not change acquisition data path                               |
| Firmware                | Update firmware only if filter must exist on-device; re-validate serial and calibration |
| Analysis only           | Keep in analysis config/report; do not alter live acquisition                           |

After applying any filter recommendation, rerun a validation subset and compare raw vs filtered signal, lag/phase behavior, and calibration residuals.

---

## Stop conditions

Stop and fix inputs/configs if:

- manifest points to missing files,
- required columns are absent from a CSV,
- sampling rate is unknown for DSP stages,
- stage output is empty or missing candidate comparison,
- Stage 6 recommendation cannot be traced back to metrics,
- generated output unintentionally overwrites a prior run.

## Related documentation

- [Handgrip_Analysis/docs/stages.md](stages.md) — stage-by-stage purpose, input, and output details
- [Handgrip_Analysis/docs/configuration.md](configuration.md) — full config tree reference
- [Handgrip_Analysis/docs/filter-design.md](filter-design.md) — Stage 6 candidate review and interpretation
- [Handgrip_Analysis/docs/reports-and-outputs.md](reports-and-outputs.md) — output tree and report structure
- [Handgrip_Calibration/docs/workflow.md](../../Handgrip_Calibration/docs/workflow.md) — how to record source sessions
