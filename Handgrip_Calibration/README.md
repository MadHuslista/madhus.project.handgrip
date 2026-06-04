# Handgrip Calibration

## Summary

`Handgrip_Calibration` records calibration sessions, segments protocol events, fits target-to-reference force models, generates reports, and validates accepted models with holdout recordings.

The canonical primary calibration protocol is:

```text
conf/protocol_static_reversible_staircase_v3.yaml
```

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

Full configuration reference is planned at [Handgrip_Calibration/docs/configuration.md](docs/configuration.md).

## Documentation

Full reading guide, per-document map, and related cross-component docs: [Handgrip_Calibration/docs/index.md](docs/index.md).

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
