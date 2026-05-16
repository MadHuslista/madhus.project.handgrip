# LSL Bridge Quickstart

## Summary

- Use this page to start `LSL_Bridge`, override the target serial port, and confirm the expected LSL streams.
- `LSL_Bridge` should be started after target firmware is emitting D2 frames and after `RS485_GUI` is running if the reference stream is needed.
- The minimum expected live outputs are `HandgripTarget` and `HandgripComponentEvents`; `HandgripReference` appears when RS485 GUI IPC is active and valid.

## Prerequisites

| Requirement                      | Validation                                                                           |
| -------------------------------- | ------------------------------------------------------------------------------------ |
| Python environment installed     | `uv sync` completed from repo root, or component dependencies installed.             |
| Target firmware is running       | Serial monitor shows `D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>`. |
| Target serial port known         | Prefer `/dev/serial/by-id/...`; fallback: `/dev/ttyUSB*` or `/dev/ttyACM*`.          |
| Reference GUI running, if needed | `RS485_GUI` publishes `rs485.measurement.v1` over ZeroMQ.                            |
| Bridge config exists             | `LSL_Bridge/conf/config.yaml`.                                                       |

## Commands

### Option A — Run with configured serial port

From `LSL_Bridge/`:

```bash
cd LSL_Bridge
uv run lsl-bridge
```

This uses the default from `conf/config.yaml`:

```yaml
serial:
  port: /dev/ttyUSB1
```

### Option B — Override target serial port

```bash
cd LSL_Bridge
uv run lsl-bridge serial.port=/dev/ttyUSB_TARGET
```

Recommended stable Linux path when available:

```bash
uv run lsl-bridge serial.port=/dev/serial/by-id/<arduino-target-id>
```

### Option C — Debug logging

```bash
cd LSL_Bridge
uv run lsl-bridge logging=debug
```

or:

```bash
uv run lsl-bridge logging.level=DEBUG
```

### Option D — Disable reference IPC for target-only validation

Use this only when validating the target chain without `RS485_GUI`:

```bash
cd LSL_Bridge
uv run lsl-bridge rs485_ipc.enabled=false streams.reference.enabled=false
```

## Expected result

A successful run should show:

- bridge startup log,
- `HandgripComponentEvents` outlet created,
- reference IPC subscriber connected if reference is enabled,
- target serial port opened,
- target serial settle completed,
- `M2` metadata received,
- `HandgripTarget` outlet created,
- target samples published,
- `HandgripReference` samples published when RS485 GUI is active.

Expected stream names:

| Stream                    | Producer                              | When expected                                         |
| ------------------------- | ------------------------------------- | ----------------------------------------------------- |
| `HandgripTarget`          | Bridge target serial loop             | Always, once valid D2 frames arrive.                  |
| `HandgripReference`       | Bridge RS485 IPC background publisher | When `RS485_GUI` is running and publishing valid IPC. |
| `HandgripComponentEvents` | Bridge event publisher                | When `component_events.enabled=true`.                 |

## Where outputs/logs appear

Default output paths from `conf/config.yaml`:

| Output        | Default path                                     | Notes                               |
| ------------- | ------------------------------------------------ | ----------------------------------- |
| Bridge log    | `LSL_Bridge/logs/lsl_bridge.log`                 | Controlled by `logging.file`.       |
| Target CSV    | `LSL_Bridge/data/target_handgrip_samples_v2.csv` | Enabled by `csv.target.enabled`.    |
| Reference CSV | `LSL_Bridge/data/reference_rs485_samples_v2.csv` | Enabled by `csv.reference.enabled`. |
| LSL streams   | Live LSL network                                 | Consumed by viewer/calibration.     |

## Stop conditions

Stop and troubleshoot if:

- target serial port cannot be opened,
- serial monitor shows no D2 frames,
- bridge logs continuous dropped non-D2 target lines,
- `HandgripTarget` never appears,
- reference is expected but `HandgripReference` never appears,
- `reference_ipc_malformed` events repeat continuously,
- target sequence gaps or timestamp re-anchors occur continuously.

## Troubleshooting links

- [`timestamping.md`](timestamping.md)
- [`stream-contracts.md`](stream-contracts.md)
- [`configuration.md`](configuration.md)
- [`../../Handgrip_Firmware/docs/serial-protocol.md`](../../Handgrip_Firmware/docs/serial-protocol.md)
- [`../../RS485_GUI/docs/ipc-schema.md`](../../RS485_GUI/docs/ipc-schema.md)
- [`../../docs/troubleshooting/lsl-streams.md`](../../docs/troubleshooting/lsl-streams.md)

## Quick validation commands

```bash
# Confirm contract names in docs/config.
rg "HandgripTarget|HandgripReference|HandgripComponentEvents|rs485.measurement.v1" LSL_Bridge docs

# Confirm D2 schema is documented.
rg "D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>" Handgrip_Firmware LSL_Bridge docs
```
