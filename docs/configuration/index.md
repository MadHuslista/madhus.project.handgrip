# Configuration Reference Index

**Status:** Canonical root configuration index  
**Audience:** Operators, maintainers, and student developers  
**Scope:** Where configuration lives, what each config controls, and where to find detailed references  
**Related docs:** `docs/architecture/repository-layout.md`, `docs/architecture/stream-contracts.md`, component `docs/configuration.md` files

## Summary

- This page maps every major configuration source in the Handgrip Suite.
- Root `docs/configuration/*.md` files provide cross-component, handoff-oriented references.
- Component `*/docs/configuration.md` files provide component-local operational details.
- Configuration changes that affect stream names, serial schemas, channel labels, or calibration semantics are cross-component changes and must be validated end to end.
- The acquisition board has a separate menu reference because it is configured from the physical instrument UI rather than from a YAML file.

## Configuration map

| Component | Config path | Main purpose | Detailed reference |
| --------- | ----------- | ------------ | ------------------ |
| Acquisition board | Physical front-panel menu: `C1.SyS`, `C2.CAL`, `C4.AdV`, `C5.CoM`, etc. | Reference board sampling, gain, filtering, calibration, RS485/Active-Send settings. | [`acquisition-board-menu-reference.md`](acquisition-board-menu-reference.md) |
| Firmware | `platformio.ini`, `Handgrip_Firmware/Core/Inc/config.h` | Arduino Nano environment, serial rate, D2 schema, sampling period, scale/offset constants. | [`firmware.md`](firmware.md), [`../../Handgrip_Firmware/docs/configuration.md`](../../Handgrip_Firmware/docs/configuration.md) |
| RS485 GUI | `RS485_GUI/config/config.yaml` | Reference-board serial connection, Active-Send/Modbus settings, logging, GUI display, ZMQ IPC. | [`rs485-gui.md`](rs485-gui.md), [`../../RS485_GUI/docs/configuration.md`](../../RS485_GUI/docs/configuration.md) |
| LSL Bridge | `LSL_Bridge/conf/config.yaml`, `LSL_Bridge/conf/logging/*.yaml` | Target serial parser, reference IPC subscriber, LSL streams, timestamping, CSV output, processing filters. | [`lsl-bridge.md`](lsl-bridge.md), [`../../LSL_Bridge/docs/configuration.md`](../../LSL_Bridge/docs/configuration.md) |
| LSL Viewer | `LSL_Viewer/conf/config.yaml` | Live/replay mode, stream discovery, channel labels, XY correlation, render/downsampling, server. | [`lsl-viewer.md`](lsl-viewer.md), [`../../LSL_Viewer/docs/configuration.md`](../../LSL_Viewer/docs/configuration.md) |
| Handgrip Calibration | `Handgrip_Calibration/conf/*.yaml` | Protocols, LSL stream requirements, recording, quality gates, model candidates, reports, holdout validation. | [`handgrip-calibration.md`](handgrip-calibration.md), [`../../Handgrip_Calibration/docs/configuration.md`](../../Handgrip_Calibration/docs/configuration.md) |
| Handgrip Analysis | `Handgrip_Analysis/conf/**/*.yaml` | Input manifests, stage settings, DSP assumptions, filter candidates, output/report behavior. | [`handgrip-analysis.md`](handgrip-analysis.md), [`../../Handgrip_Analysis/docs/configuration.md`](../../Handgrip_Analysis/docs/configuration.md) |

## Safe-edit priority

| Edit type | Risk | Validation required |
| --- | ---: | --- |
| UI display-only settings | Low | Run the relevant app and verify the display. |
| Log/output locations | Low/Medium | Confirm files are written and not overwriting important data. |
| Serial ports | Medium | Confirm device identity and live data before calibration. |
| Stream/channel labels | High | Update bridge, viewer, calibration, root stream contracts, and tests together. |
| Firmware D2 schema | High | Cross-component parser, stream, viewer, calibration, and report migration. |
| Acquisition-board calibration/menu settings | High | Reference-only verification and documented calibration evidence. |
| Calibration model/protocol settings | High | Preflight, record, fit, report, and holdout validation. |
| DSP/filter deployment settings | High | Stage 6 evidence plus live/replay validation. |

## Global validation commands

```bash
# Validate no stale RS485 config snapshot path remains.
if rg '\.\./RS485_GUI/config\.yaml' Handgrip_Calibration/conf docs; then
  echo 'ERROR: stale RS485 GUI config path found' >&2
  exit 1
fi

# Validate canonical RS485 GUI config path.
rg 'RS485_GUI/config/config\.yaml' docs Handgrip_Calibration

# Validate D2 firmware schema remains canonical.
rg 'D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>' docs Handgrip_Firmware LSL_Bridge

# Validate primary calibration protocol appears in docs.
rg 'protocol_static_reversible_staircase_v3.yaml' docs Handgrip_Calibration
```
