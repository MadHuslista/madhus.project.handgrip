# Full Live Viewer Quickstart

## Summary

This workflow starts the full live stack so the operator can see target and reference signals together in `LSL_Viewer`.

Start order:

1. `RS485_GUI`
2. `LSL_Bridge`
3. `LSL_Viewer`

## Prerequisites

- Physical setup validated.
- Firmware setup validated and D2 lines visible.
- Reference-only workflow passes.
- Target serial port and RS485 serial port are known.

## Commands

### Terminal 1 — Reference acquisition

```bash
cd RS485_GUI
uv run rs485-gui serial.default_port=/dev/ttyUSB_RS485
```

After GUI opens, click "Connect" to start acquisition and IPC publishing.   

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

## Related docs
- [docs/architecture/stream-contracts.md](../architecture/stream-contracts.md)


## Troubleshooting links

- [docs/troubleshooting/lsl-streams.md](../troubleshooting/lsl-streams.md)
- [docs/troubleshooting/viewer-lag-or-xy-delay.md](../troubleshooting/viewer-lag-or-xy-delay.md)
- [docs/architecture/timestamping-and-synchronization.md](../architecture/timestamping-and-synchronization.md)
- [docs/workflows/handgrip-calibration.md](handgrip-calibration.md)
