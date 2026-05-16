# LSL Streams Troubleshooting

**Status:** Canonical symptom-first troubleshooting doc  
**Symptoms covered:** Streams not visible, wrong names, stale outlets  
**Related docs:** `docs/architecture/stream-contracts.md`, `LSL_Bridge/docs/stream-contracts.md`, `docs/workflows/full-live-viewer-quickstart.md`

## Summary

Use this guide when `LSL_Viewer` or `Handgrip_Calibration` cannot find `HandgripTarget`, `HandgripReference`, marker streams, or component event streams.

## Symptom: streams not visible

### Likely causes

| Cause                    | Check                 | Fix                                                       |
| ------------------------ | --------------------- | --------------------------------------------------------- |
| `LSL_Bridge` not running | Terminal/logs         | Start bridge after upstream producers.                    |
| Target serial missing    | Bridge target logs    | Validate firmware D2 output.                              |
| Reference IPC missing    | Bridge reference logs | Start `RS485_GUI` and confirm IPC topic.                  |
| Firewall/network issue   | LSL discovery tools   | Keep processes on same host/network; check firewall.      |
| Wrong stream names       | Configs/docs differ   | Align names with `docs/architecture/stream-contracts.md`. |

## Symptom: wrong stream names

Canonical names:

| Stream                       | Producer               |
| ---------------------------- | ---------------------- |
| `HandgripTarget`             | `LSL_Bridge`           |
| `HandgripReference`          | `LSL_Bridge`           |
| `HandgripComponentEvents`    | `LSL_Bridge`           |
| `HandgripCalibrationMarkers` | `Handgrip_Calibration` |

If a component uses different names, update all relevant configs or document the intentional migration.

## Symptom: stale outlets

### Signs

- Viewer sees a stream that is no longer updating.
- Multiple streams with same name appear.
- Calibration attaches to an old stream.

### Fix

1. Stop viewer and calibration clients.
2. Stop `LSL_Bridge`.
3. Stop `RS485_GUI` if reference stream is involved.
4. Restart in canonical order:

```bash
cd RS485_GUI && uv run rs485-gui
cd ../LSL_Bridge && uv run lsl-bridge
cd ../LSL_Viewer && uv run lsl-viewer
```

5. Re-run calibration preflight.

## Validation commands

```bash
rg 'HandgripTarget|HandgripReference|HandgripComponentEvents|HandgripCalibrationMarkers' docs LSL_Bridge LSL_Viewer Handgrip_Calibration
rg 'rs485.measurement.v1' docs RS485_GUI LSL_Bridge
```

## Stop conditions

Stop before recording if:

- only one of target/reference streams exists,
- target stream updates but reference stream is frozen,
- stream names do not match calibration config,
- stale duplicate streams are visible,
- preflight resolves streams inconsistently across repeated runs.
