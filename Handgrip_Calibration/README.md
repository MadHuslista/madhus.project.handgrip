# Handgrip Calibration

## Summary

`Handgrip_Calibration` records calibration sessions, segments protocol events, fits target-to-reference force models, generates reports, and validates accepted models with holdout recordings.

The canonical primary calibration protocol is:

```text
conf/protocol_static_reversible_staircase_v3.yaml
```

Calibration should fit target raw counts against reference force:

```text
reference_force_N = f(target_raw_count)
```

Do not treat firmware `current_units` as the primary fitting input unless a workflow explicitly says it is validating already-deployed firmware constants.

## When to use this component

Use this component when you need to:

- run calibration preflight checks,
- record a protocol-guided calibration session,
- fit target raw counts to reference force,
- compare candidate calibration models,
- generate calibration reports,
- validate an accepted model with holdout data,
- export or recommend values for firmware/bridge/downstream use.

Do not use this component to:

- directly configure the acquisition-board menu,
- acquire RS485 data without `RS485_GUI`,
- publish target/reference LSL streams,
- perform general offline DSP/filter design.

## First command

From `Handgrip_Calibration/`, after the live stack is running:

```bash
uv run handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml
```

Record the primary protocol:

```bash
uv run handgrip-cal record --config conf/protocol_static_reversible_staircase_v3.yaml
```

## Expected result

Expected successful behavior:

- preflight discovers `HandgripTarget` and `HandgripReference`,
- required channels exist,
- protocol config validates,
- recording creates `data/calibration/<session_id>/`,
- session folder contains target/reference samples, events, quality logs, and config snapshots,
- fitting generates selected model artifacts,
- reporting generates human-readable calibration reports.

Stop if preflight cannot find both streams or if the physical force path has not been validated.

## Configuration

Primary config/protocol files:

| File                                                | Purpose                                                       |
| --------------------------------------------------- | ------------------------------------------------------------- |
| `conf/protocol_static_reversible_staircase_v3.yaml` | Canonical primary calibration protocol.                       |
| `conf/protocol_reference_verification.yaml`         | Reference-chain verification before main calibration.         |
| `conf/protocol_holdout_verification.yaml`           | Independent post-fit validation.                              |
| `conf/default.yaml` / `conf/config.yaml`            | Base/default calibration settings, depending on command path. |
| `conf/template.yaml`                                | Starting point for new protocol definitions.                  |

Important config-path rule:

```yaml
- ../RS485_GUI/config/config.yaml
```

Use the real RS485 GUI config path above for component config snapshots. Do not use the stale path `../RS485_GUI/config.yaml`.

Full configuration reference is planned at [`docs/configuration.md`](docs/configuration.md).

## Common workflows

| Goal                        | Document                                                                                                 |
| --------------------------- | -------------------------------------------------------------------------------------------------------- |
| Run end-to-end calibration  | [`../docs/workflows/handgrip-calibration.md`](../docs/workflows/handgrip-calibration.md)                 |
| Choose a protocol           | [`docs/protocols.md`](docs/protocols.md)                                                                 |
| Understand stream contracts | [`../docs/architecture/stream-contracts.md`](../docs/architecture/stream-contracts.md)                   |
| Validate physical fixture   | [`../docs/hardware/force-fixture.md`](../docs/hardware/force-fixture.md)                                 |
| Understand output lifecycle | [`../docs/architecture/data-and-output-lifecycle.md`](../docs/architecture/data-and-output-lifecycle.md) |

## Repository layout

```text
Handgrip_Calibration/
├── README.md
├── conf/
│   ├── protocol_static_reversible_staircase_v3.yaml
│   ├── protocol_reference_verification.yaml
│   ├── protocol_holdout_verification.yaml
│   └── ...
├── docs/
│   ├── index.md
│   └── protocols.md
├── src/
│   └── handgrip_calibration/
│       ├── cli.py
│       ├── recorder.py
│       ├── fitting.py
│       ├── validation.py
│       ├── protocol_analysis.py
│       └── report.py
├── data/
│   └── calibration/
└── tests/
```

## Tests

Run from `Handgrip_Calibration/` after dependencies are installed:

```bash
uv run pytest
```

Fast hardware-free validation pattern:

```bash
uv run handgrip-cal demo-data --output /tmp/hg_demo
uv run handgrip-cal fit /tmp/hg_demo/demo_handgrip_session --config conf/default.yaml
uv run handgrip-cal report /tmp/hg_demo/demo_handgrip_session
```

If your environment still uses module invocation, use:

```bash
python -m handgrip_calibration.cli --help
```

## Further docs

- [`docs/index.md`](docs/index.md) — calibration documentation map.
- [`docs/protocols.md`](docs/protocols.md) — canonical protocol suite and legacy labels.
- [`../docs/workflows/handgrip-calibration.md`](../docs/workflows/handgrip-calibration.md) — root operator workflow.
- [`../docs/architecture/stream-contracts.md`](../docs/architecture/stream-contracts.md) — root stream/data contracts.
- [`../docs/architecture/data-and-output-lifecycle.md`](../docs/architecture/data-and-output-lifecycle.md) — generated artifact lifecycle.
