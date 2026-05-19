# Configuration Reference Index

## Summary

Configuration is distributed by component. Each component owns its configuration files and its configuration documentation. Cross-component changes (stream names, serial schemas, channel labels, calibration semantics) require end-to-end validation.

## Configuration map

| Component            | Config path                                                     | Detailed reference                                                                             |
| -------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Acquisition board    | Physical front-panel menu                                       | [docs/hardware/acquisition-board-reference.md](../hardware/acquisition-board-reference.md)     |
| Firmware             | `Handgrip_Firmware/Core/Inc/config.h`, `platformio.ini`         | [Handgrip_Firmware/docs/configuration.md](../../Handgrip_Firmware/docs/configuration.md)       |
| RS485 GUI            | `RS485_GUI/config/config.yaml`                                  | [RS485_GUI/docs/configuration.md](../../RS485_GUI/docs/configuration.md)                       |
| LSL Bridge           | `LSL_Bridge/conf/config.yaml`, `LSL_Bridge/conf/logging/*.yaml` | [LSL_Bridge/docs/configuration.md](../../LSL_Bridge/docs/configuration.md)                     |
| LSL Viewer           | `LSL_Viewer/conf/config.yaml`                                   | [LSL_Viewer/docs/configuration.md](../../LSL_Viewer/docs/configuration.md)                     |
| Handgrip Calibration | `Handgrip_Calibration/conf/*.yaml`                              | [Handgrip_Calibration/docs/configuration.md](../../Handgrip_Calibration/docs/configuration.md) |
| Handgrip Analysis    | `Handgrip_Analysis/conf/**/*.yaml`                              | [Handgrip_Analysis/docs/configuration.md](../../Handgrip_Analysis/docs/configuration.md)       |

## Safe-edit priority

| Edit type                              | Risk       | Validation required                                                      |
| -------------------------------------- | ---------- | ------------------------------------------------------------------------ |
| UI display-only settings               | Low        | Run the app and verify the display                                       |
| Log/output locations                   | Low/Medium | Confirm files are written                                                |
| Serial ports                           | Medium     | Confirm device identity and live data before calibration                 |
| Stream/channel labels                  | High       | Update bridge, viewer, calibration, stream contracts, and tests together |
| Firmware D2 schema                     | High       | Cross-component migration: parser, stream, viewer, calibration, reports  |
| Acquisition-board calibration settings | High       | Reference-only verification and documented evidence                      |
| Calibration model/protocol settings    | High       | Preflight, record, fit, report, holdout validation                       |
| DSP/filter deployment settings         | High       | Stage 6 evidence plus live/replay validation                             |
