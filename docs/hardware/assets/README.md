# Hardware Image Asset Map

## Summary

This directory is the canonical image location for hardware documentation. Hardware Markdown files under `docs/hardware/` should reference images through relative paths such as `assets/acquisition-board-rear-terminal-map-full-feature.jpg`.

Images are named by **hardware role + visible content**, not by capture timestamp. Filenames use lowercase kebab-case so links are stable and readable in GitHub.

## Operator image set

| File | Shows | Primary use |
| --- | --- | --- |
| `acquisition-board-rear-terminal-map-full-feature.jpg` | Rear terminal map for the full-feature acquisition board. | Terminal identification for power, RS485, analog output, DI, and PM58 sensor wiring. |
| `acquisition-board-ac-input-label-100-240vac.jpg` | AC input label showing `AC100-240V`, `L`, and `N`. | Confirms the exact board variant before applying mains power. |
| `acquisition-board-front-panel-buttons-indicators.jpg` | Front display, four keys, status LEDs, and indicators. | Menu navigation, zero/calibration actions, display validation. |
| `acquisition-board-front-panel-startup-force-reading.jpg` | Front panel powered with a live reading during bench use. | First power-on / live-response visual reference. |
| `acquisition-board-rear-label-google-lens-translation.jpg` | Phone-captured translated rear label. | Human-readable cross-check when the printed rear label is hard to interpret. |
| `pm58-load-cell-model-label.jpg` | PM58 load-cell model and range label. | Confirms model identity and nominal 100 kg range. |
| `pm58-load-cell-certificate-overview.jpg` | PM58 product certificate overview. | Certificate-level identification and range/sensitivity context. |
| `pm58-load-cell-certificate-wire-colors.jpg` | PM58 certificate with visible wire-color mapping. | Confirms `EXC+ red`, `EXC- black`, `SIG+ green`, `SIG- white`, shield/drain. |
| `force-fixture-pm58-handgrip-series-overhead.jpg` | PM58 and handgrip target mechanically arranged in series. | Fixture stage 1: shared mechanical force path. |
| `force-fixture-pm58-handgrip-acquisition-board-overview.jpg` | PM58 + handgrip fixture with acquisition board present. | Fixture stage 2: mechanical path plus reference electronics. |
| `force-fixture-screw-press-pm58-handgrip-closeup.jpg` | Screw press applying controlled force through PM58 + handgrip. | Fixture stage 3: controlled-force contact and alignment. |
| `force-fixture-full-bench-screw-press-acquisition-board.jpg` | Full bench view with screw press, PM58, handgrip, and acquisition board. | Overall calibration bench layout and cable routing. |
| `handgrip-internal-load-cell-distal-side.jpg` | Internal handgrip load cell and wire routing on the distal side. | Target-device mechanical/electrical inspection. |
| `handgrip-internal-load-cell-proximal-side.jpg` | Internal handgrip load cell and wire routing on the proximal side. | Target-device mechanical/electrical inspection. |
| `hx711-sensor-to-adc-module-wiring.jpg` | Sensor wiring landing on the HX711 ADC module. | Target analog front-end wiring reference. |
| `hx711-adc-module-to-arduino-wiring.jpg` | HX711 ADC module wiring routed toward Arduino Nano. | Target ADC-to-MCU wiring reference. |
| `hx711-adc-chip-closeup.jpg` | HX711 chip / ADC module part-number close-up. | ADC module identification. |
| `arduino-nano-pinout-closeup.jpg` | Arduino Nano close-up showing board and pin labels. | MCU board identification and pinout reference. |
| `arduino-nano-mounted-wiring-view.jpg` | Arduino Nano mounted inside the handgrip wiring cavity. | Target firmware hardware context and installed wiring reference. |

## Duplicate / retained reference asset

| File | Shows | Note |
| --- | --- | --- |
| [`force-fixture-pm58-handgrip-series-overhead-duplicate.jpg`](force-fixture-pm58-handgrip-series-overhead-duplicate.jpg) | Same PM58 + handgrip series view as [`force-fixture-pm58-handgrip-series-overhead.jpg`](force-fixture-pm58-handgrip-series-overhead.jpg). | Exact duplicate retained only so the original asset count is preserved; operator docs use the canonical non-duplicate filename. |

## Rendering guidance

- In operator-facing Markdown, prefer compact image tables with clear captions instead of repeating the same large photo in every step.
- Use images near the top of the workflow as a visual reference set, then refer to them by figure number in the step-by-step sections.
- For GitHub rendering, use relative paths (`assets/<file>.jpg`) and avoid absolute repository URLs.
- For plain Markdown rendering, keep the caption text outside the image `alt` field so the caption remains visible even when image sizing HTML is ignored.
