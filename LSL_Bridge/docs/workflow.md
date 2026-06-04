# LSL Bridge Workflow

## Summary

This document covers starting `LSL_Bridge`, verifying stream publication, and confirming expected output locations.

`LSL_Bridge` should be started after target firmware is emitting `D2` frames and after `RS485_GUI` is running if the reference stream is needed. The minimum expected live outputs are `HandgripTarget` and `HandgripComponentEvents`. `HandgripReference` appears when RS485 GUI IPC is active.

## Prerequisites

| Requirement                       | Validation                                                                          |
| --------------------------------- | ----------------------------------------------------------------------------------- |
| Python environment installed      | `uv sync` completed from repo root                                                  |
| Target firmware running           | Serial monitor shows `D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>` |
| Target serial port known          | Prefer `/dev/serial/by-id/...`; fallback: `/dev/ttyUSB*` or `/dev/ttyACM*`          |
| Reference GUI running (if needed) | `RS485_GUI` publishes `rs485.measurement.v1` over ZeroMQ                            |
| Bridge config exists              | `LSL_Bridge/conf/config.yaml`                                                       |

## 1 — Review configuration

Before starting, confirm `LSL_Bridge/conf/config.yaml` has the correct:

- `serial.port` — target Arduino serial path,
- `rs485_ipc.enabled` — `true` if reference stream is needed,
- `csv.target.enabled` / `csv.reference.enabled` — if CSV logging is needed.

See [LSL_Bridge/docs/configuration.md](configuration.md).

## 2 — Start the bridge

### With configured serial port

```bash
cd LSL_Bridge
uv run lsl-bridge
```

### With serial port override

```bash
cd LSL_Bridge
uv run lsl-bridge serial.port=/dev/ttyUSB_TARGET
```

Stable Linux path (preferred):

```bash
uv run lsl-bridge serial.port=/dev/serial/by-id/<arduino-target-id>
```

### Target-only (no reference stream)

```bash
cd LSL_Bridge
uv run lsl-bridge rs485_ipc.enabled=false streams.reference.enabled=false
```

### Debug logging

```bash
cd LSL_Bridge
uv run lsl-bridge logging=debug
```

## 3 — Validate streams

A successful start produces:

- bridge startup log,
- `HandgripComponentEvents` outlet created,
- `HandgripTarget` outlet created once valid `D2` frames arrive,
- `HandgripReference` outlet created when RS485 GUI IPC is active.

Expected stream names:

| Stream                    | When expected                                        |
| ------------------------- | ---------------------------------------------------- |
| `HandgripTarget`          | Always, once valid `D2` frames arrive                |
| `HandgripReference`       | When `RS485_GUI` is running and publishing valid IPC |
| `HandgripComponentEvents` | When `component_events.enabled=true`                 |

## 4 — Output locations

| Output        | Default path                                     |
| ------------- | ------------------------------------------------ |
| Bridge log    | `LSL_Bridge/logs/lsl_bridge.log`                 |
| Target CSV    | `LSL_Bridge/data/target_handgrip_samples_v2.csv` |
| Reference CSV | `LSL_Bridge/data/reference_rs485_samples_v2.csv` |
| LSL streams   | Live LSL network                                 |

## Stop conditions

Stop and troubleshoot if:

- target serial port cannot be opened,
- serial monitor shows no `D2` frames,
- `HandgripTarget` never appears,
- reference is expected but `HandgripReference` never appears,
- `reference_ipc_malformed` events repeat continuously,
- target sequence gaps or timestamp re-anchors occur continuously.

## Troubleshooting links

- [LSL_Bridge/docs/timestamping.md](timestamping.md)
- [LSL_Bridge/docs/stream-contracts.md](stream-contracts.md)
- [LSL_Bridge/docs/configuration.md](configuration.md)
- [Handgrip_Firmware/docs/serial-protocol.md](../../Handgrip_Firmware/docs/serial-protocol.md)
- [RS485_GUI/docs/ipc-schema.md](../../RS485_GUI/docs/ipc-schema.md)
- [docs/troubleshooting/lsl-streams.md](../../docs/troubleshooting/lsl-streams.md)
