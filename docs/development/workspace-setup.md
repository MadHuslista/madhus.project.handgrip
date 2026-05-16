# Workspace Setup

## Summary

This document explains the minimal repository-level setup expected before running validation, workflows, or tests.

## Python environment

From the repository root:

```bash
uv sync
```

Run tests:

```bash
uv run pytest
```

The workspace uses local editable component packages. Prefer running commands from the repo root unless a component workflow explicitly says to `cd` into the component directory.

## Firmware environment

Firmware is configured through the root `platformio.ini`.

Typical commands:

```bash
platformio run
platformio run --target upload
platformio device monitor --baud 115200
```

## Documentation validation

After applying documentation patches:

```bash
python3 scripts/validate_docs.py --repo-root .
bash scripts/validate_content_contracts.sh
bash scripts/validate_handoff_workflows.sh
```

For documentation-only snapshots:

```bash
python3 scripts/validate_docs.py --repo-root . --docs-only
bash scripts/validate_content_contracts.sh --docs-only
bash scripts/validate_handoff_workflows.sh --docs-only
```
