# Contributing to Documentation

## Summary

This folder is reserved for documentation contribution rules and style guides.

## Contribution rules

Any documentation change that affects firmware schema, stream names, IPC topics, calibration protocol defaults, or config paths must also update:

1. Root architecture docs under `docs/architecture/`,
2. Affected component docs under `*/docs/`,
3. Any affected workflow docs under `docs/workflows/`.

## Validation scripts

| Script | Purpose |
| --- | --- |
| [scripts/validate_docs.py](../../scripts/validate_docs.py) | Link/path validation, image validation, config-path validation |
| [scripts/validate_content_contracts.sh](../../scripts/validate_content_contracts.sh) | Content-contract checks for D2 schema, stream names, RS485 config paths |
| [scripts/validate_handoff_workflows.sh](../../scripts/validate_handoff_workflows.sh) | Workflow validator: `uv sync`, tests, hardware operator gates |

Run from the repository root:

```bash
python3 scripts/validate_docs.py --repo-root .
bash scripts/validate_content_contracts.sh
```
