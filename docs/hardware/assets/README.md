# Hardware Image Asset Map

## Summary

This directory is the canonical image location for hardware documentation. Hardware Markdown files under `docs/hardware/` should reference images through relative paths such as `assets/rear-terminal-map_full-feature-selection.jpg`.

## Asset map

| File                                           | Shows                                                                                                                               | Used in                                                                                                                                                          | Notes                                                                                       |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `rear-terminal-map_full-feature-selection.jpg` | Rear terminal map of the full-feature acquisition board, including RS485, DI, sensor, analog output, relay, and AC input terminals. | [`docs/hardware/acquisition-board-reference.md`](../acquisition-board-reference.md), [`docs/hardware/pm58-wiring-and-bringup.md`](../pm58-wiring-and-bringup.md) | Canonical terminal map for wiring and safety validation.                                    |
| `ac-input-sticker_close-up.jpg`                | AC input sticker / label showing AC100-240V, L, and N.                                                                              | [`docs/hardware/pm58-wiring-and-bringup.md`](../pm58-wiring-and-bringup.md), [`docs/hardware/acquisition-board-reference.md`](../acquisition-board-reference.md) | Confirms the observed unit should be treated as the AC-powered board.                       |
| `front-panel_buttons_indicators.jpg`           | Front panel, buttons, indicators, and display.                                                                                      | [`docs/hardware/acquisition-board-reference.md`](../acquisition-board-reference.md), [`docs/hardware/pm58-wiring-and-bringup.md`](../pm58-wiring-and-bringup.md) | Used for menu navigation, calibration, zero/tare, and display-status explanations.          |
| `pm58-load-cell_label.jpg`                     | PM58 load-cell label.                                                                                                               | [`docs/hardware/pm58-wiring-and-bringup.md`](../pm58-wiring-and-bringup.md), [`docs/hardware/force-fixture.md`](../force-fixture.md)                             | Identifies the reference load cell model/range.                                             |
| `pm58-certificate_wire-colors.jpg`             | PM58 certificate and wire-color mapping.                                                                                            | [`docs/hardware/pm58-wiring-and-bringup.md`](../pm58-wiring-and-bringup.md)                                                                                      | Canonical source for EXC+/EXC-/SIG+/SIG- mapping.                                           |
| `rear-label_google-lens-translation.jpg`       | Translated rear label of the acquisition board.                                                                                     | [`docs/hardware/acquisition-board-reference.md`](../acquisition-board-reference.md), [`docs/hardware/pm58-wiring-and-bringup.md`](../pm58-wiring-and-bringup.md) | Helps non-Chinese readers cross-check terminal labels.                                      |
| `pm58_n_handgrip_setup.jpg`                    | PM58 load cell mechanically installed in series with the handgrip target.                                                           | [`docs/hardware/force-fixture.md`](../force-fixture.md)                                                                                                          | Requested fixture-stage image. If missing, keep the Markdown TODO in place until committed. |
| `acq_board_n_pm58_n_handgrip_setup.jpg`        | PM58 + handgrip mechanical setup connected to the acquisition board.                                                                | [`docs/hardware/force-fixture.md`](../force-fixture.md)                                                                                                          | Requested fixture-stage image. If missing, keep the Markdown TODO in place until committed. |
| `force_application_setup.jpg`                  | Screw-press controlled-force setup applying force through the PM58 + handgrip chain.                                                | [`docs/hardware/force-fixture.md`](../force-fixture.md)                                                                                                          | Requested fixture-stage image. If missing, keep the Markdown TODO in place until committed. |

## Naming convention

Use descriptive lowercase names with underscores or hyphens. Prefer names that explain the hardware relation rather than camera metadata, for example:

- Good: `force_application_setup.jpg`
- Avoid: `IMG_20260408_044544.jpg`

## Usage rule

Do not reference hardware images from `Documentation/assets/` in canonical docs. Migrate or copy them into this directory first, then reference them from `docs/hardware/*.md`.
