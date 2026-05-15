# Handgrip Calibration Documentation

## Summary

- **Purpose:** Calibration workflow for recording sessions, segmenting static holds, fitting models, generating reports, and validating exports.
- This page is the component-level documentation map.
- Start here when you know this component is the one you need, then follow the specific workflow/configuration/architecture links.
- Some linked files are created in later phases of the documentation refactor; this index defines the intended stable navigation structure.

## Audience

| Reader                | Use this page to...                                                            |
| --------------------- | ------------------------------------------------------------------------------ |
| Operator              | Find the minimal run/validation workflow for this component.                   |
| Maintainer            | Find configuration and architecture references before editing code.            |
| Student developer     | Learn where behavior lives and which tests/validation steps should be updated. |
| External collaborator | Understand this component's boundary within the full Handgrip Suite.           |

## Component contract

- The intended primary protocol is `conf/protocol_static_reversible_staircase_v3.yaml` unless a maintainer explicitly changes the default.
- Calibration should preserve raw target counts and reference force data for auditability.
- Config snapshots are part of reproducibility; verify component config paths before relying on session archives.

## Documentation map

| Document                                                             | Purpose                                                                 |
| -------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| [`quickstart.md`](quickstart.md)                                     | Minimal operator path for a calibration run.                            |
| [`protocols.md`](protocols.md)                                       | Protocol suite, primary v3 protocol, holdout validation, legacy labels. |
| [`configuration.md`](configuration.md)                               | Full calibration config and protocol YAML reference.                    |
| [`recording.md`](recording.md)                                       | LSL stream requirements, session IDs, CSVs, events, quality telemetry.  |
| [`fitting-and-model-selection.md`](fitting-and-model-selection.md)   | Candidate models, metrics, likelihoods, residuals, selection logic.     |
| [`reports-and-outputs.md`](reports-and-outputs.md)                   | Report files, plots, JSON exports, and interpretation map.              |
| [`applying-calibration-results.md`](applying-calibration-results.md) | Which fit values to use and where to validate them.                     |
| [`architecture.md`](architecture.md)                                 | CLI and module structure: preflight, record, fit, report, validate.     |
| [`development.md`](development.md)                                   | How to add protocols, models, report sections, and tests.               |

## Related system docs

| System doc                                                                                   | Why it matters                                        |
| -------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| [`../../docs/start-here.md`](../../docs/start-here.md)                                       | High-level introduction to the full suite.            |
| [`../../docs/system-overview.md`](../../docs/system-overview.md)                             | Physical/software/dataflow map.                       |
| [`../../docs/architecture/stream-contracts.md`](../../docs/architecture/stream-contracts.md) | Cross-component stream and IPC contracts.             |
| [`../../docs/configuration/index.md`](../../docs/configuration/index.md)                     | Configuration ownership and cross-component settings. |
| [`../../docs/troubleshooting/index.md`](../../docs/troubleshooting/index.md)                 | Symptom-first debugging entry point.                  |

## Validation checklist for this docs index

- [ ] The README links to this `docs/index.md`.
- [ ] Every linked component doc exists by the end of the relevant documentation phase.
- [ ] Component-specific docs link back to root system contracts where applicable.
- [ ] Configuration docs include default, type/range, impact, safe-edit guidance, and failure modes.
- [ ] Development docs identify files to edit, tests to update, and validation gates.
