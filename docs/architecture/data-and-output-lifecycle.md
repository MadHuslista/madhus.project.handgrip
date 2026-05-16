# Data and Output Lifecycle

**Status:** Canonical root architecture document  
**Audience:** Operators, maintainers, and future collaborators  
**Scope:** Where data appears, what is canonical, what is generated, and what should be archived  
**Related docs:** `docs/workflows/handgrip-calibration.md`, `docs/workflows/handgrip-analysis.md`

## Summary

- Live processes produce logs, IPC messages, LSL streams, and optionally CSV recordings.
- Calibration sessions produce reproducibility-critical data and reports under `Handgrip_Calibration/data/calibration/<session_id>/`.
- Analysis runs produce stage-specific reports, metrics, and plots under `Handgrip_Analysis/data/analysis_results/` or the configured output directory.
- Generated outputs are not canonical documentation unless curated under `docs/examples/`.
- Session folders should preserve config snapshots whenever possible.

## Output classes

| Output class             | Typical owner                 | Location                                              | Keep?                          | Notes                                   |
| ------------------------ | ----------------------------- | ----------------------------------------------------- | ------------------------------ | --------------------------------------- |
| Runtime logs             | GUI/bridge/viewer/calibration | component `logs/` or configured log path              | Keep for debug, not docs       | Rotate or archive after sessions.       |
| Live streams             | `LSL_Bridge`                  | LSL network/session                                   | Ephemeral unless recorded      | Used by viewer/calibration.             |
| Calibration session data | `Handgrip_Calibration`        | `Handgrip_Calibration/data/calibration/<session_id>/` | Yes                            | Scientific/reproducibility artifact.    |
| Calibration reports      | `Handgrip_Calibration`        | session folder                                        | Yes                            | Human-readable model/result summary.    |
| Analysis outputs         | `Handgrip_Analysis`           | configured analysis output folder                     | Yes if tied to a study/session | Do not confuse with maintained docs.    |
| Curated examples         | docs maintainers              | `docs/examples/`                                      | Yes                            | Small teaching examples only.           |
| Legacy generated outputs | prior runs                    | existing data/output folders                          | Case-by-case                   | Archive/delete based on handoff policy. |

## Calibration session lifecycle

```text
preflight
  └── verifies streams/configs

record
  ├── captures target/reference data
  ├── writes events/markers
  ├── snapshots configs
  └── creates session folder

fit
  ├── loads captured data
  ├── builds calibration dataset
  ├── evaluates candidate models
  └── writes model outputs

report
  ├── renders human-readable report
  ├── links plots/tables
  └── recommends calibration usage

holdout validation
  ├── records independent validation session
  └── evaluates accepted model on unseen data
```

## Expected calibration artifacts

Exact filenames may vary by implementation version, but a complete session should include these classes:

| Artifact class    | Purpose                                                  |
| ----------------- | -------------------------------------------------------- |
| target samples    | Target device stream data.                               |
| reference samples | Reference board stream data.                             |
| event markers     | Protocol stage boundaries and operator events.           |
| quality logs      | Preflight/live quality metrics if enabled.               |
| copied configs    | Provenance for bridge/viewer/RS485/calibration settings. |
| fit artifacts     | Model parameters, metrics, candidate comparison.         |
| report artifacts  | Markdown/HTML report and plots.                          |

## Analysis lifecycle

```text
input data / manifest
  └── selected calibration/session/CSV files

stage run
  ├── loads configured input
  ├── computes metrics/plots
  └── writes stage output

stage aggregation / report
  ├── compares results
  ├── summarizes findings
  └── emits recommendation artifacts
```

## Data management rules

1. Do not edit raw session data in place.
2. Preserve protocol config and component config snapshots with calibration sessions.
3. Treat generated reports as outputs, not source documentation.
4. Curate only small, stable examples under `docs/examples/`.
5. Use explicit session IDs in communications and reports.
6. When re-running analysis, write to a new output folder or make overwrite behavior explicit.

## Where to look first

| Need                       | Start here                                                           |
| -------------------------- | -------------------------------------------------------------------- |
| Find calibration data      | `Handgrip_Calibration/data/calibration/`                             |
| Find analysis reports      | `Handgrip_Analysis/data/analysis_results/` or configured output path |
| Find runtime GUI logs      | `RS485_GUI` configured logger output path                            |
| Find bridge CSV/debug logs | `LSL_Bridge` config/log output path                                  |
| Find curated examples      | `docs/examples/`                                                     |

## Validation checklist

- [ ] New calibration sessions include target and reference data.
- [ ] Config snapshots include `LSL_Bridge`, `LSL_Viewer`, and `RS485_GUI` configs.
- [ ] Reports state which session ID they describe.
- [ ] Analysis outputs are tied to manifests or source data paths.
- [ ] No generated output folder is presented as canonical documentation.
