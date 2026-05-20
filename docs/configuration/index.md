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

