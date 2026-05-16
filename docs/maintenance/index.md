# Maintenance Documentation

## Summary

- This folder contains documentation-maintenance, validation, and handoff-readiness procedures for the Handgrip Suite.
- Use these docs before handing the repository to another operator or maintainer.
- The validation tools support both a **documentation-only snapshot** mode and a **strict full-repository handoff** mode.

## Documents

| Document | Purpose |
| --- | --- |
| [`documentation-validation.md`](documentation-validation.md) | Link/path validation, image validation, config-path validation, content-contract checks, and expected scripts. |
| [`handoff-workflow-validation.md`](handoff-workflow-validation.md) | Final software and hardware workflow validation checklist before handoff. |

## Scripts

| Script | Purpose |
| --- | --- |
| [`../../scripts/validate_docs.py`](../../scripts/validate_docs.py) | Python validator for Markdown links/images, referenced paths, config paths, and canonical-doc deprecation guards. |
| [`../../scripts/validate_content_contracts.sh`](../../scripts/validate_content_contracts.sh) | `rg`-based content-contract checks for D2, RS485 config paths, stream names, and deprecated terms. |
| [`../../scripts/validate_handoff_workflows.sh`](../../scripts/validate_handoff_workflows.sh) | Handoff workflow validator/checklist for `uv sync`, tests, and hardware operator gates. |

## Recommended order

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
