# Configuration System Primer

**Status:** Canonical development primer  
**Audience:** Student maintainers and developers editing YAML/configuration files  
**Scope:** Hydra/OmegaConf-style dotlist overrides, config precedence, component-local configs, protocol configs, safe change workflow, reproducibility snapshots  
**Related docs:** [`docs/configuration/index.md`](../configuration/index.md), component `docs/configuration.md` files

## Summary

- Most Python components are config-driven. Prefer changing YAML/config overrides before editing code.
- Many commands support Hydra/OmegaConf-style dotlist overrides such as `serial.port=/dev/ttyUSB0`.
- Config paths are usually relative to the component root unless a workflow explicitly says otherwise.
- Calibration protocols are YAML configs; they must preserve reproducibility through session config snapshots.
- Any config change that alters data contracts must be treated as a cross-component change.

## Hydra/OmegaConf dotlist overrides

A dotlist override is a CLI argument that updates a nested config field:

```bash
uv run lsl-bridge serial.port=/dev/ttyUSB0
```

Conceptually equivalent to editing:

```yaml
serial:
  port: /dev/ttyUSB0
```

Common examples:

```bash
uv run rs485-gui serial.default_port=/dev/ttyUSB_RS485
uv run lsl-bridge serial.port=/dev/ttyUSB_TARGET
uv run lsl-viewer viewer.server.port=8765
```

Dotlist overrides are good for temporary operator choices such as serial ports. Prefer YAML edits for stable defaults.

## Config precedence

Use this mental model unless a component doc says otherwise:

```text
base YAML config
  → selected protocol/config file
  → CLI dotlist overrides
  → runtime/operator actions
```

Practical implications:

- A CLI override can hide a bad YAML default during one run.
- A YAML edit can affect all future runs.
- A protocol config can override base calibration behavior.
- A runtime UI action may not be captured unless logs/config snapshots include it.

## Component-local configs

| Component              | Config root                           | Notes                                                                                     |
| ---------------------- | ------------------------------------- | ----------------------------------------------------------------------------------------- |
| `RS485_GUI`            | `RS485_GUI/config/config.yaml`        | Serial transport, parser profile, logging, GUI display, IPC publishing.                   |
| `LSL_Bridge`           | `LSL_Bridge/conf/config.yaml`         | Target serial, reference IPC, LSL outlets, timestamping, CSV sinks, processing.           |
| `LSL_Viewer`           | `LSL_Viewer/conf/config.yaml`         | Stream names, channel labels, live/replay modes, XY alignment, display-only downsampling. |
| `Handgrip_Calibration` | `Handgrip_Calibration/conf/*.yaml`    | Protocols, stream requirements, recording outputs, fitting/report settings.               |
| `Handgrip_Analysis`    | `Handgrip_Analysis/conf/**/*.yaml`    | Stage settings, manifests, filter candidates, output/report behavior.                     |
| `Handgrip_Firmware`    | `Handgrip_Firmware/Core/Inc/config.h` | Compile-time constants, D2 schema metadata, sampling period, scale/offset.                |

## Protocol configs

Calibration protocols are YAML files under:

```text
Handgrip_Calibration/conf/
```

Canonical primary protocol:

```text
conf/protocol_static_reversible_staircase_v3.yaml
```

Legacy/basic baseline protocol:

```text
conf/protocol_static_staircase.yaml
```

A protocol config defines the operator procedure, expected streams, recording outputs, fitting/report assumptions, and quality checks. Do not treat protocol configs as disposable examples; they are part of the experiment definition.

## How to change safely

Use this workflow:

1. Identify the component owner.
2. Read the component configuration doc.
3. Prefer a CLI override for a one-time test.
4. Promote to YAML only after the override has been validated.
5. Run the smallest relevant test or workflow.
6. Update docs if the default or contract changed.
7. Preserve config snapshots for calibration/research sessions.

Example: temporary serial-port override

```bash
cd LSL_Bridge
uv run lsl-bridge serial.port=/dev/serial/by-id/<target-device>
```

Example: stable serial-port default

1. Edit `LSL_Bridge/conf/config.yaml`.
2. Update [`LSL_Bridge/docs/configuration.md`](../../LSL_Bridge/docs/configuration.md) if the documented default changes.
3. Run target-only quickstart.

## How to capture configs for reproducibility

Calibration sessions should snapshot relevant component configs, especially:

```yaml
session:
  copy_component_configs:
    - ../LSL_Bridge/conf/config.yaml
    - ../LSL_Viewer/conf/config.yaml
    - ../RS485_GUI/config/config.yaml
```

The stale path below must not be used:

```yaml
- ../RS485_GUI/config.yaml
```

A complete session should preserve:

- calibration protocol config,
- bridge config,
- viewer config,
- RS485 GUI config,
- firmware metadata from M2 frames,
- report/fitting outputs.

## Cross-component config changes

Treat these as high risk:

| Change                                | Why high risk                             | Required docs/tests                                                  |
| ------------------------------------- | ----------------------------------------- | -------------------------------------------------------------------- |
| Stream name                           | Consumers may not discover streams        | root stream contracts, bridge/viewer/calibration configs, preflight. |
| Channel name/order                    | Calibration/viewer columns can break      | bridge docs, viewer docs, calibration docs, parser/channel tests.    |
| Firmware D2 field                     | Parser and reports can break              | firmware docs, bridge parser tests, root stream contracts.           |
| RS485 IPC topic                       | Bridge reference stream can disappear     | RS485 GUI docs, bridge config/docs, reference-only quickstart.       |
| Calibration protocol default          | Operators may run wrong workflow          | calibration docs, root workflow, CLI help, tests.                    |
| Analysis filter recommendation target | Live vs display-only behavior can diverge | analysis docs, bridge/viewer config docs, validation workflow.       |

## Validation commands

```bash
# Find stale RS485 config snapshot paths.
rg '\.\./RS485_GUI/config\.yaml' Handgrip_Calibration/conf docs || true

# Confirm canonical RS485 config path.
rg 'RS485_GUI/config/config\.yaml' Handgrip_Calibration/conf docs

# Confirm D2 schema docs.
rg 'D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>' README.md docs Handgrip_Firmware LSL_Bridge

# Confirm calibration primary protocol docs.
rg 'protocol_static_reversible_staircase_v3.yaml' docs Handgrip_Calibration
```

## Common mistakes

| Mistake                                                   | Symptom                                           | Fix                                                              |
| --------------------------------------------------------- | ------------------------------------------------- | ---------------------------------------------------------------- |
| Editing config from wrong working directory               | File-not-found or copied config snapshots missing | Run from documented component root or use repo-root-aware paths. |
| Using CLI overrides as hidden permanent state             | Another operator cannot reproduce behavior        | Promote validated overrides to YAML and docs.                    |
| Renaming a channel in one component only                  | Viewer/calibration cannot find data               | Update producer/consumer configs and stream contracts together.  |
| Treating display downsampling as acquisition downsampling | Saved data and plot behavior disagree             | Document whether setting is display-only or data-path affecting. |
| Forgetting config snapshots                               | Calibration report cannot explain conditions      | Fix `copy_component_configs` and rerun session.                  |
