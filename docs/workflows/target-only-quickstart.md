# Target-Only Quickstart

## Summary

Use this workflow when you only need to validate the handgrip target path: firmware serial output → `LSL_Bridge` → `HandgripTarget` LSL stream.

## Prerequisites

- Firmware uploaded.
- Serial monitor shows D2 frames.
- Target Arduino serial port identified.
- `LSL_Bridge` installed and runnable.

## Commands

From the repository root or from `LSL_Bridge/`, depending on your environment setup:

```bash
cd LSL_Bridge
uv run lsl-bridge serial.port=/dev/ttyUSB_TARGET
```
Replace `/dev/ttyUSB_TARGET` with the Arduino target path. Prefer `/dev/serial/by-id/...` when available.

## Expected result

- Bridge logs show successful target serial connection.
- D2 frames are parsed without continuous errors.
- LSL outlet `HandgripTarget` is published.
- Applying force changes the target stream.

## Related docs
- [Handgrip_Firmware/docs/workflow.md](../../Handgrip_Firmware/docs/workflow.md)
- [Handgrip_Firmware/docs/serial-protocol.md](../../Handgrip_Firmware/docs/serial-protocol.md)


## Troubleshooting links

- [docs/troubleshooting/serial-and-rs485.md](../troubleshooting/serial-and-rs485.md)
- [docs/troubleshooting/lsl-streams.md](../troubleshooting/lsl-streams.md)
- [docs/architecture/stream-contracts.md](../architecture/stream-contracts.md)
