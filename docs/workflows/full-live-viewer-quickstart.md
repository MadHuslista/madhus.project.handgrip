# Full Live Viewer Quickstart

## Summary

This workflow starts the full live stack so the operator can see target and reference signals together in `LSL_Viewer`.

Start order:

1. `RS485_GUI`
2. `LSL_Bridge`
3. `LSL_Viewer`

## Prerequisites

- Physical setup validated. See [docs/workflows/physical-setup.md](physical-setup.md).
- Firmware setup validated and D2 lines visible. See [Handgrip_Firmware/docs/workflow.md](../../Handgrip_Firmware/docs/workflow.md).
- Reference-only workflow passes. See [docs/workflows/reference-only-quickstart.md](reference-only-quickstart.md).
- Target serial port and RS485 serial port are known. See [docs/workflows/target-only-quickstart.md](target-only-quickstart.md).

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

## Reference alignment (run before trusting XY / calibration)

The reference stream is stamped at GUI read time and lags the directly-connected target by a stable relay offset. Whenever the physical or runtime setup changes (cabling, ports, host, baud, sample rates), run the calibration preflight first and update `manual_reference_shift_s` before trusting the XY plot or recording calibration data:

```bash

# 1. enable `diagnostics.enabled=true` in the viewer config, 
# 2. restart the three terminals to capture diagnostics logs, then:

# 3. run the preflight script against the short diagnostics capture
cd Handgrip_Calibration
uv run python scripts/calibration_preflight.py \
  --viewer-session ../diagnostics/<ts> \
  --bridge-target-csv ../LSL_Bridge/data/target_*.csv \
  --bridge-reference-csv ../LSL_Bridge/data/reference_*.csv \
  --gui-ndjson ../RS485_GUI/logs/raw_signal.ndjson
```

See [docs/troubleshooting/viewer-lag-or-xy-delay.md](../troubleshooting/viewer-lag-or-xy-delay.md) and [docs/architecture/timestamping-and-synchronization.md](../architecture/timestamping-and-synchronization.md).

## Related docs
- [docs/architecture/stream-contracts.md](../architecture/stream-contracts.md)


## Troubleshooting links

- [docs/troubleshooting/lsl-streams.md](../troubleshooting/lsl-streams.md)
- [docs/troubleshooting/viewer-lag-or-xy-delay.md](../troubleshooting/viewer-lag-or-xy-delay.md)
- [docs/architecture/timestamping-and-synchronization.md](../architecture/timestamping-and-synchronization.md)
- [docs/workflows/handgrip-calibration.md](handgrip-calibration.md)
