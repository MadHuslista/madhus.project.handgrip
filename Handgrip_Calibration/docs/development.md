# Handgrip Calibration Development Guide

## Summary

- Add behavior through protocols/configs first when possible; edit source code only when the existing configuration model cannot express the need.
- Any change to protocol markers, fit model outputs, or stream/channel assumptions is cross-component and must update docs/tests.
- New protocols, models, and report sections should include validation gates and example/session-level tests.

## Add a new protocol

### Files to edit

1. Copy `conf/template.yaml` to `conf/protocol_<name>.yaml`.
2. Add protocol purpose/status to [`docs/protocols.md`](protocols.md).
3. Add operator instructions if it is production-facing.
4. Add config reference notes to `docs/configuration.md` if it introduces new fields.

### Required decisions

| Decision                                      | Document it in                                                                   |
| --------------------------------------------- | -------------------------------------------------------------------------------- |
| production vs diagnostic vs smoke             | [`protocols.md`](protocols.md)                                                   |
| primary fitting vs holdout vs validation-only | [`protocols.md`](protocols.md)                                                   |
| force levels and repeats                      | protocol YAML + operator doc                                                     |
| quality gates                                 | protocol YAML + [`configuration.md`](configuration.md)                           |
| expected outputs                              | [`reports-and-outputs.md`](reports-and-outputs.md) if new artifact class appears |

### Validation

```bash
uv run handgrip-cal preflight --config conf/protocol_<name>.yaml
uv run handgrip-cal record --config conf/protocol_<name>.yaml --dry-run
```

## Add a model candidate

### Files to edit

- fitting/model source file,
- config schema or candidate list,
- [`docs/fitting-and-model-selection.md`](fitting-and-model-selection.md),
- report rendering if new metrics/plots are produced,
- tests for model behavior and selection policy.

### Required model metadata

| Metadata              | Purpose                                                  |
| --------------------- | -------------------------------------------------------- |
| model name            | Stable config/report identifier.                         |
| deployable flag       | Whether it can be selected as primary.                   |
| monotonicity behavior | Whether it can violate physical monotonic force mapping. |
| parameters            | Report/deployment values.                                |
| metrics               | Selection and interpretation.                            |
| failure modes         | What bad data pattern it diagnoses.                      |

### Validation

- synthetic known mapping,
- noisy/outlier mapping,
- monotonicity check,
- candidate ranking behavior,
- report rendering.

## Add a report section

### Files to edit

- report renderer/template,
- plot/table generator if needed,
- `docs/reports-and-outputs.md`,
- tests or golden-output checks.

### Required report-section contract

| Field           | Requirement                             |
| --------------- | --------------------------------------- |
| input artifacts | Explicit source files.                  |
| output artifact | Stable filename/section title.          |
| interpretation  | What the reader should conclude.        |
| failure state   | What it means if the section is absent. |

## Add a captured artifact

If a new recording artifact is added, update:

1. [`docs/recording.md`](recording.md),
2. `docs/reports-and-outputs.md`,
3. tests that validate session completeness.

## Change stream/channel assumptions

This is a cross-component change. Update:

- [`../../docs/architecture/stream-contracts.md`](../../docs/architecture/stream-contracts.md),
- [`LSL_Bridge/docs/stream-contracts.md`](../../LSL_Bridge/docs/stream-contracts.md),
- [`LSL_Viewer/docs/configuration.md`](../../LSL_Viewer/docs/configuration.md),
- [`Handgrip_Calibration/docs/recording.md`](recording.md),
- protocol YAML channel mappings,
- stream discovery/preflight tests.

## Test checklist

Run the smallest relevant set first:

```bash
cd Handgrip_Calibration
uv run pytest
```

Recommended categories:

| Change        | Test focus                                                       |
| ------------- | ---------------------------------------------------------------- |
| protocol YAML | config parsing, preflight, dry-run recording.                    |
| recorder      | session folder structure, stream/channel mapping, event writing. |
| model         | synthetic fit, metrics, selection, serialization.                |
| report        | generated sections, plots, JSON/Markdown outputs.                |
| holdout       | independent validation metrics and pass/fail behavior.           |

## Development stop conditions

Do not merge if:

- a new protocol lacks docs,
- a new model lacks metrics and report interpretation,
- a stream/channel change is not reflected in root stream contracts,
- generated outputs cannot be traced to source sessions,
- tests pass only with live hardware and no hardware-free path exists.
