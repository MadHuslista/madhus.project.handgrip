# Documentation Validation

## Summary

- This document defines the Phase 11 validation workflow for documentation links, image links, referenced paths, content-contracts, and deprecated-material guards.
- Run the validation in **docs-only mode** for documentation snapshots and in **strict full-repo mode** before final handoff.
- The validation intentionally separates hard failures from warnings so archived/historical material does not block canonical documentation checks.
- The canonical contracts to protect are the D2 firmware schema, `HandgripTarget`, `HandgripReference`, `HandgripComponentEvents`, `HandgripCalibrationMarkers`, `rs485.measurement.v1`, and the canonical RS485 GUI config path.

## Validation modes

| Mode | Command | Use when | Behavior |
| --- | --- | --- | --- |
| Docs-only snapshot | `python3 scripts/validate_docs.py --docs-only` | You only have Markdown files and no full source/assets/config tree. | Missing source/config/image files become warnings unless the Markdown link itself points to a missing Markdown doc. |
| Strict full repo | `python3 scripts/validate_docs.py` | You have the full repository before handoff. | Markdown links, image links, required config/source paths, and content guards must pass. |
| Content contracts | `bash scripts/validate_content_contracts.sh` | You want fast `rg` contract checks. | Confirms D2, stream names, canonical RS485 path, and deprecated-material guards. |
| Workflow validation | `bash scripts/validate_handoff_workflows.sh` | You are preparing final handoff. | Runs or prints software/hardware workflow validation gates. |

## Step 11.1 — Link/path validation

The validator must check:

- Markdown links resolve in canonical docs.
- Image links resolve in strict mode.
- Referenced config/source files exist in strict mode.
- Command snippets reference known component entry points.
- Canonical docs do not link to deprecated HX710B / old MCU material.

Run:

```bash
python3 scripts/validate_docs.py --repo-root .
```

For a documentation-only snapshot:

```bash
python3 scripts/validate_docs.py --repo-root . --docs-only
```

### What counts as canonical documentation

By default, the validator checks:

- `README.md`
- `docs/` except `docs/archive/`
- component `README.md` files
- component `docs/` folders
- generated-output status `README.md` files when present

By default, it ignores:

- legacy `Documentation/`
- `docs/archive/`
- `.pytest_cache/`
- binary files
- generated plots/reports unless explicitly linked from canonical docs

## Step 11.2 — Content-contract checks

Run:

```bash
bash scripts/validate_content_contracts.sh
```

The checks include:

```bash
# Confirm D2 schema appears in canonical protocol docs.
rg "D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>" README.md docs Handgrip_Firmware LSL_Bridge

# Find stale RS485 GUI config path.
rg "\.\./RS485_GUI/config\.yaml|RS485_GUI/config\.yaml" .

# Confirm canonical path appears.
rg "RS485_GUI/config/config\.yaml" README.md docs Handgrip_Calibration

# Ensure deprecated docs are not linked in canonical docs.
rg "HX710B|stm32f103|Hacer bascula" README.md docs --glob '!docs/archive/**'
```

The shell script adds context-aware guards so negative examples such as “do not use stale path” are warnings/review items rather than automatic failures, while real source/config occurrences remain failures.

## Step 11.3 — Workflow validation

Before handoff, run once on the full repo:

```bash
uv sync
uv run pytest
```

Then validate the operator workflows on hardware:

1. Firmware serial monitor shows D2 frames.
2. RS485 GUI receives reference force.
3. LSL bridge publishes both streams.
4. LSL viewer displays target/reference and XY plot.
5. Calibration preflight passes.
6. One smoke-test calibration recording completes.
7. Calibration fit/report complete.
8. Analysis smoke test completes.

Use:

```bash
bash scripts/validate_handoff_workflows.sh
```

To run software commands automatically:

```bash
RUN_HANDOFF_SOFTWARE=1 bash scripts/validate_handoff_workflows.sh
```

## Failure triage

| Failure | Likely cause | Fix |
| --- | --- | --- |
| Missing Markdown link | A linked doc was planned but not created. | Create the missing doc or update the link. |
| Missing image link | Phase 3 assets not committed or docs-only snapshot. | Add image under `docs/hardware/assets/` or run docs-only mode. |
| Missing config file | Running against documentation-only snapshot or config path typo. | Use strict mode only on full repo; fix path if full repo. |
| Legacy D schema found | Stale documentation survived Phase 4/6.2. | Replace with D2 schema or mark as historical outside canonical docs. |
| Stale RS485 path found in configs | Phase 4 path fix not applied. | Replace `../RS485_GUI/config.yaml` with `../RS485_GUI/config/config.yaml`. |
| Deprecated HX710B/STM32F103 link found | Old hardware doc leaked into canonical docs. | Move link to archive or remove from canonical path. |

## Definition of done

- `python3 scripts/validate_docs.py` passes on the full repo.
- `bash scripts/validate_content_contracts.sh` passes on the full repo.
- `bash scripts/validate_handoff_workflows.sh` has been completed at least once with hardware.
- Any warnings left in docs-only mode are explicitly explained by missing source/assets in the snapshot.
