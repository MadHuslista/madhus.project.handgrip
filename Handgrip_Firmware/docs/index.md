# Handgrip Firmware Documentation

## Summary

- **Purpose:** Arduino Nano + HX711 firmware for the target handgrip device.
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

- Firmware emits target data consumed by `LSL_Bridge`.
- Current data schema should be documented as `D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>`.
- Firmware build is controlled from the root `platformio.ini`.
- Firmware calibration constants affect `current_units`; calibration fitting should still preserve raw-count traceability.

## Documentation map

| Document                                     | Purpose                                                                           |
| -------------------------------------------- | --------------------------------------------------------------------------------- |
| [`build-and-upload.md`](build-and-upload.md) | PlatformIO setup, build, upload, and serial monitor workflow.                     |
| [`serial-protocol.md`](serial-protocol.md)   | Current `M2`/`D2` serial schemas and field meanings.                              |
| [`configuration.md`](configuration.md)       | `config.h` and PlatformIO settings, including sampling and calibration constants. |
| [`architecture.md`](architecture.md)         | Firmware structure: HX711 acquisition, TimerOne sampling, FIFO, serial emission.  |
| [`troubleshooting.md`](troubleshooting.md)   | Upload, serial, sampling, and HX711 failure symptoms.                             |

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
