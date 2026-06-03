# Handgrip Calibration Development Guide

## Summary

- Add behavior through protocols/configs first when possible; edit source code only when the existing configuration model cannot express the need.
- Any change to protocol markers, fit model outputs, or stream/channel assumptions is cross-component and must update docs/tests.
- New protocols, models, and report sections should include validation gates and example/session-level tests.

## Add a new protocol

### Files to edit

| File                                                                                         | Purpose                                                       |
| -------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `Handgrip_Calibration/conf/protocol_<name>.yaml`                                             | New protocol definition.                                      |
| [Handgrip_Calibration/docs/protocols.md](protocols.md)                                       | Add protocol status and intended use.                         |
| [Handgrip_Calibration/docs/configuration.md](configuration.md)                               | Document any new config keys/sections.                        |
| [Handgrip_Calibration/docs/recording.md](recording.md)                                       | Update capture/session expectations if outputs change.        |
| [Handgrip_Calibration/docs/reports-and-outputs.md](reports-and-outputs.md)                   | Document new report/output artifacts.                         |
| [docs/workflows/handgrip-calibration.md](../../docs/workflows/handgrip-calibration.md)       | Update only if protocol becomes operator-facing or canonical. |
| tests under `Handgrip_Calibration/tests/`                                                    | Validate config parsing, preflight, dry-run behavior.         |

### Data contracts affected

A protocol can affect:

- required LSL streams,
- required channels,
- event marker names,
- segment labels,
- hold/static/dynamic trial definitions,
- session folder output classes,
- fitting dataset construction,
- report sections,
- validation acceptance criteria.

It must not redefine the root calibration contract unless deliberately migrated:

```text
reference_force_N = f(target_raw_count)
```

### Tests to update

```bash
cd Handgrip_Calibration
uv run handgrip-cal preflight --config conf/protocol_<name>.yaml
uv run handgrip-cal record --config conf/protocol_<name>.yaml --dry-run
uv run pytest
```

If the protocol creates new event/segment names, update tests that validate:

- event emission,
- segment extraction,
- fit dataset construction,
- report rendering.

### Validation workflow

1. Copy `conf/template.yaml` or the nearest existing protocol.
2. Rename metadata fields and protocol ID.
3. Define force levels, repeats, stage timing, and operator prompts.
4. Verify `session.copy_component_configs` includes:

```yaml
- ../LSL_Bridge/conf/config.yaml
- ../LSL_Viewer/conf/config.yaml
- ../RS485_GUI/config/config.yaml
```

5. Run `preflight`.
6. Run `record --dry-run` if supported.
7. Run a short smoke recording.
8. Inspect session folder for target/reference/event/config artifacts.
9. Run fit/report only if the protocol is intended for fitting.
10. Document protocol status in [Handgrip_Calibration/docs/protocols.md](protocols.md).

### Common failure modes

| Failure                                      | Cause                                          | Fix                                                           |
| -------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------- |
| Preflight fails                              | Missing stream/channel requirement             | Update protocol stream section or upstream configs.           |
| Config snapshot missing                      | Wrong relative config path                     | Use `../RS485_GUI/config/config.yaml`, not stale path.        |
| Recording completes but fit fails            | Protocol events do not produce fit segments    | Update segmentation rules or mark protocol validation-only.   |
| Report lacks expected section                | Report renderer not aware of protocol artifact | Update report docs and renderer/tests.                        |
| Operator runs diagnostic protocol as primary | Protocol status unclear                        | Mark production/diagnostic/legacy explicitly.                 |
| Hold labels ambiguous                        | Event naming not stable                        | Define canonical marker names before recording real sessions. |

## Add a model candidate

### Files to edit

| File area                                                                                     | Purpose                                                       |
| --------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `Handgrip_Calibration/src/handgrip_calibration/...`                                           | Model implementation and fitting logic.                       |
| `Handgrip_Calibration/conf/*.yaml`                                                            | Candidate enable/disable flags and model-specific parameters. |
| [Handgrip_Calibration/docs/fitting-and-model-selection.md](fitting-and-model-selection.md)    | Model rationale, metrics, residual interpretation.            |
| [Handgrip_Calibration/docs/reports-and-outputs.md](reports-and-outputs.md)                    | New fit/report artifacts if any.                              |
| [Handgrip_Calibration/docs/applying-calibration-results.md](applying-calibration-results.md)  | Deployment guidance if model is deployable.                   |
| [Handgrip_Calibration/docs/configuration.md](configuration.md)                                | Config reference if config keys are user-facing.              |
| tests under `Handgrip_Calibration/tests/`                                                     | Synthetic, noisy, outlier, and report behavior tests.         |

### Data contracts affected

A new model can affect:

- fit result JSON schema,
- report metrics/tables,
- exported firmware constants,
- LSL bridge processing recommendations,
- holdout validation interpretation,
- analysis assumptions.

It must not change the input contract unless explicitly documented:

| Input               | Required role                 |
| ------------------- | ----------------------------- |
| `target_raw_count`  | Model input.                  |
| `reference_force_N` | Ground-truth output.          |
| protocol events     | Segmentation and hold labels. |
| config snapshots    | Reproducibility.              |

### Required model metadata

| Metadata              | Purpose                                                  |
| --------------------- | -------------------------------------------------------- |
| model name            | Stable config/report identifier.                         |
| deployable flag       | Whether it can be selected as primary.                   |
| monotonicity behavior | Whether it can violate physical monotonic force mapping. |
| parameters            | Report/deployment values.                                |
| metrics               | Selection and interpretation.                            |
| failure modes         | What bad data pattern it diagnoses.                      |

### Tests to update

```bash
cd Handgrip_Calibration
uv run pytest
```

Recommended model-specific tests:

| Test                    | Purpose                                                                     |
| ----------------------- | --------------------------------------------------------------------------- |
| synthetic exact mapping | Model recovers known parameters.                                            |
| noisy mapping           | Model is stable under measurement noise.                                    |
| outlier mapping         | Robust models behave as expected.                                           |
| monotonicity            | Force mapping does not violate physical assumptions unless diagnostic-only. |
| serialization           | Fit result JSON contains required fields.                                   |
| report rendering        | Model appears correctly in comparison tables.                               |
| holdout validation      | Model can be applied to independent data.                                   |

### Validation workflow

1. Define model purpose: deployable, diagnostic, or exploratory.
2. Implement model with explicit parameter names and units.
3. Add config entry to candidate list.
4. Add synthetic tests.
5. Run on a known calibration session.
6. Compare with baseline models.
7. Inspect residuals by force level and by ascending/descending holds.
8. Run holdout validation.
9. Update report interpretation and deployment docs.
10. Only then mark model as candidate for production selection.

### Common failure modes

| Failure                               | Cause                                      | Fix                                                     |
| ------------------------------------- | ------------------------------------------ | ------------------------------------------------------- |
| Model overfits fit session            | Too many parameters, no holdout discipline | Prefer simpler model or require holdout pass.           |
| Non-monotonic mapping                 | Polynomial/spline behavior unconstrained   | Add monotonic constraint or mark diagnostic-only.       |
| Cannot export to firmware             | Model not representable as scale/offset    | Document host-side deployment or non-deployable status. |
| Report selection unclear              | Missing metric or likelihood explanation   | Update model-selection report and docs.                 |
| Residuals improve but dynamics worsen | Filter/model hides lag/hysteresis          | Validate against dynamic/holdout protocols.             |
| Units ambiguous                       | Parameters not labelled                    | Add units to fit JSON and report tables.                |

## Add a report section

### Files to edit

- report renderer/template,
- plot/table generator if needed,
- [Handgrip_Calibration/docs/reports-and-outputs.md](reports-and-outputs.md),
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

1. [Handgrip_Calibration/docs/recording.md](recording.md),
2. [Handgrip_Calibration/docs/reports-and-outputs.md](reports-and-outputs.md),
3. tests that validate session completeness.

## Change stream/channel assumptions

This is a cross-component change. Update:

- [docs/architecture/stream-contracts.md](../../docs/architecture/stream-contracts.md),
- [LSL_Bridge/docs/stream-contracts.md](../../LSL_Bridge/docs/stream-contracts.md),
- [LSL_Viewer/docs/configuration.md](../../LSL_Viewer/docs/configuration.md),
- [Handgrip_Calibration/docs/recording.md](recording.md),
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
