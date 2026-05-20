# Handgrip Analysis Workflow

## Summary

This document covers the complete analysis workflow: recording and exporting source data, organizing input files, creating and updating manifests, running analysis stages, and applying filter recommendations.

Analysis operates exclusively on saved files. It must not be run until calibration sessions or curated CSV exports exist.

## Prerequisites

- At least calibration sessions recorded and available. See [Handgrip_Calibration/docs/workflow.md](../../Handgrip_Calibration/docs/workflow.md).
- Python dependencies installed: `uv sync` from repo root.
- Config files present under `Handgrip_Analysis/conf/`.

---

## Phase 1 — Prepare input data

### 1.1 Record source sessions

Source data for analysis comes from `Handgrip_Calibration` recording sessions. Run each protocol type you need:

| Analysis purpose                  | Protocol to record                                                   |
| --------------------------------- | -------------------------------------------------------------------- |
| Startup/warm-up (Stage 1)         | Any protocol run from a cold start                                   |
| Static noise (Stage 2)            | Record a static rest hold after warm-up                              |
| Loaded drift/creep (Stage 3)      | Record a sustained constant-load hold                                |
| Real grip dynamics (Stage 4)      | Record fast-max, ramp-hold, and sustained-hold squeeze trials        |
| Interference comparison (Stage 5) | Record under multiple conditions (different positions, environments) |
| Filter design (Stage 6)           | Reuses Stage 2 and Stage 4 outputs                                   |

Each session produces files under:

```text
Handgrip_Calibration/data/calibration/<session_id>/
```

### 1.2 Export signals to analysis input directory

After recording, identify the target signal CSV files from each session. Copy or symlink them into the analysis input directory:

```text
Handgrip_Analysis/data/calibration_signals/
```

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

The channel column used in analysis is typically `raw` (the raw ADC count column from the calibration session output). Confirm the column names in your exported CSVs match what your manifest specifies.

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
| `channel`        | yes      | Column name in the CSV to use as the signal              |
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

| Stage   | Purpose                           | Key output                           |
| ------- | --------------------------------- | ------------------------------------ |
| Stage 1 | Startup and warm-up behavior      | Stabilization metrics and plots      |
| Stage 2 | Static rest noise                 | Noise metrics, PSD, bandpower        |
| Stage 3 | Loaded drift and creep            | Drift slopes, hold stability         |
| Stage 4 | Real grip dynamics                | Rise/peak/release dynamics           |
| Stage 5 | Interference/condition comparison | Condition comparison report          |
| Stage 6 | Filter candidate benchmark        | Rankings, recommendation YAML/report |

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
