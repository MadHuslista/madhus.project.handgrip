# Handgrip Suite Documentation

## Navigation map

| Section                                               | Purpose                                                                     |
| ----------------------------------------------------- | --------------------------------------------------------------------------- |
| [docs/system-overview.md](system-overview.md)         | What the suite does, hardware chains, dataflow, configs, and where to start |
| [docs/workflows/](workflows/)                         | Step-by-step multi-component workflows                                      |
| [docs/hardware/](hardware/)                           | Physical setup, PM58, acquisition board, wiring references                  |
| [docs/configuration/index.md](configuration/index.md) | Where each component's config lives                                         |
| [docs/architecture/](architecture/)                   | Dataflow, stream contracts, runtime processes, timestamping                 |
| [docs/development/](development/)                     | Source layout, extension patterns, workspace setup                          |
| [docs/troubleshooting/](troubleshooting/)             | Symptom-first debugging                                                     |
| [docs/examples/](examples/)                           | Curated example outputs                                                     |

## Component documentation

Each component has its own `docs/` folder with the full details for that component.

| Component              | Purpose                                           | Entry point                                                                 |
| ---------------------- | ------------------------------------------------- | --------------------------------------------------------------------------- |
| `Handgrip_Firmware`    | Arduino Nano + HX711 firmware                     | [Handgrip_Firmware/docs/index.md](../Handgrip_Firmware/docs/index.md)       |
| `RS485_GUI`            | Reference acquisition-board GUI and IPC publisher | [RS485_GUI/docs/index.md](../RS485_GUI/docs/index.md)                       |
| `LSL_Bridge`           | Target/reference LSL stream publisher             | [LSL_Bridge/docs/index.md](../LSL_Bridge/docs/index.md)                     |
| `LSL_Viewer`           | Live/CSV/XDF visualization                        | [LSL_Viewer/docs/index.md](../LSL_Viewer/docs/index.md)                     |
| `Handgrip_Calibration` | Calibration protocols, fitting, reports           | [Handgrip_Calibration/docs/index.md](../Handgrip_Calibration/docs/index.md) |
| `Handgrip_Analysis`    | Offline signal analysis and filter design         | [Handgrip_Analysis/docs/index.md](../Handgrip_Analysis/docs/index.md)       |
