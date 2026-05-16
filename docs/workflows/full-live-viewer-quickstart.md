# Full Live Viewer Quickstart

**Status:** Canonical operator quickstart  
**Audience:** Operators and student maintainers  
**Scope:** Start full live system: reference acquisition, LSL bridge, and viewer  
**Related docs:** [`docs/architecture/runtime-processes.md`](../architecture/runtime-processes.md), [`docs/architecture/stream-contracts.md`](../architecture/stream-contracts.md)

## Summary

This workflow starts the full live stack so the operator can see target and reference signals together in `LSL_Viewer`.

Start order:

1. `RS485_GUI`
2. `LSL_Bridge`
3. `LSL_Viewer`

## Prerequisites

- Physical setup validated.
- Firmware setup validated and D2 lines visible.
- Reference-only quickstart passes.
- Target serial port and RS485 serial port are known.
- Prior Phase 4 stream-contract docs are installed.

## Commands

### Terminal 1 — Reference acquisition

```bash
cd RS485_GUI
uv run rs485-gui serial.default_port=/dev/ttyUSB_RS485
```

### Terminal 2 — LSL bridge

```bash
cd LSL_Bridge
uv run lsl-bridge serial.port=/dev/ttyUSB_TARGET
```

### Terminal 3 — Viewer

```bash
cd LSL_Viewer
uv run lsl-viewer
```

Replace serial paths with stable `/dev/serial/by-id/...` paths when possible.

## Expected result

| Component    | Expected result                                        |
| ------------ | ------------------------------------------------------ |
| `RS485_GUI`  | Reference value updates and logs valid frames.         |
| `LSL_Bridge` | Publishes `HandgripTarget` and `HandgripReference`.    |
| `LSL_Viewer` | Shows target/reference time series and XY correlation. |

## Where outputs/logs appear

| Component    | Outputs                                                   |
| ------------ | --------------------------------------------------------- |
| `RS485_GUI`  | GUI, RS485 raw/interpreted logs, IPC publisher logs.      |
| `LSL_Bridge` | bridge logs, optional target/reference CSVs, LSL streams. |
| `LSL_Viewer` | browser view, optional viewer logs.                       |

## Stop conditions

Stop before calibration if:

- only one LSL stream appears,
- viewer shows frozen target or reference,
- force changes only one chain,
- XY plot delay grows over time,
- bridge logs continuous parser errors,
- preflight would fail stream discovery.

## Troubleshooting links

- [`docs/troubleshooting/lsl-streams.md`](../troubleshooting/lsl-streams.md)
- [`docs/troubleshooting/viewer-lag-or-xy-delay.md`](../troubleshooting/viewer-lag-or-xy-delay.md)
- [`docs/architecture/timestamping-and-synchronization.md`](../architecture/timestamping-and-synchronization.md)
- [`docs/workflows/handgrip-calibration.md`](handgrip-calibration.md)
