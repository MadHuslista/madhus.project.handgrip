# LSL Bridge Documentation

## Summary

- **Purpose:** Bridge that converts target firmware serial data and reference IPC messages into Lab Streaming Layer streams.
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

- `LSL_Bridge` owns LSL publication for the system.
- Downstream tools should consume `HandgripTarget` and `HandgripReference` rather than directly coupling to serial/IPC sources.
- Stream names and channel schemas are cross-component contracts.

## Documentation map

| Document                                     | Purpose                                                           |
| -------------------------------------------- | ----------------------------------------------------------------- |
| [`quickstart.md`](quickstart.md)             | Start bridge, select serial port, and confirm LSL streams.        |
| [`configuration.md`](configuration.md)       | Full `conf/config.yaml` and logging-config reference.             |
| [`stream-contracts.md`](stream-contracts.md) | `HandgripTarget`, `HandgripReference`, and event stream schemas.  |
| [`timestamping.md`](timestamping.md)         | Host receive vs device-clock anchoring, gaps, and drift handling. |
| [`architecture.md`](architecture.md)         | Serial reader, IPC subscriber, outlets, CSV sinks, processors.    |
| [`development.md`](development.md)           | How to add channels, parsers, or processing stages safely.        |

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
