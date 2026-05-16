# Deprecated Old ADC / MCU References

> **Archive status:** Deprecated / historical.
> This folder is not part of the current canonical Handgrip Suite workflow.
> Do not use this material for current wiring, firmware, calibration, or analysis unless explicitly instructed by a maintainer.

## Summary

- This archive location is reserved for obsolete hardware/reference material discovered during the documentation refactor.
- Canonical documentation must not depend on HX710B, old ADV-board, or old STM32F103 material.
- Current canonical hardware assumptions are:
  - HX711-based target handgrip firmware,
  - PM58 reference load cell,
  - high-speed RS485 acquisition board,
  - Arduino/PlatformIO firmware workflow,
  - Python host-side RS485 GUI, LSL bridge, viewer, calibration, and analysis packages.

## Deprecated material policy

During the v0.3 documentation refactor, deprecated source material should be handled with the following policy:

| Material class                             | Canonical-doc status        | Preservation policy                                                                       |
| ------------------------------------------ | --------------------------- | ----------------------------------------------------------------------------------------- |
| HX710B datasheets/tutorials                | Deprecated                  | Archive here only if traceability is required; otherwise omit from final handoff package. |
| Old ADV-board material                     | Deprecated                  | Archive here only if traceability is required; otherwise omit from final handoff package. |
| Old STM32F103 MCU references               | Deprecated                  | Archive here only if traceability is required; otherwise omit from final handoff package. |
| Current HX711 datasheet                    | Relevant fallback reference | Keep under `docs/hardware/references/hx711/`.                                             |
| Current acquisition-board PDFs             | Relevant fallback reference | Keep under `docs/hardware/references/acquisition-board/`.                                 |
| Current PM58/acquisition-board wiring docs | Relevant maintained docs    | Promote into canonical `docs/hardware/`.                                                  |

## Canonical replacement paths

Use these current references instead of deprecated material:

| Topic                                  | Current replacement                                                                          |
| -------------------------------------- | -------------------------------------------------------------------------------------------- |
| Target ADC behavior                    | `docs/hardware/references/hx711/hx711_english.pdf` and `Handgrip_Firmware/docs/`             |
| Acquisition board wiring/configuration | `docs/hardware/acquisition-board-reference.md` and `docs/hardware/pm58-acquisition-board.md` |
| Full physical setup                    | `docs/workflows/physical-setup.md` and `docs/hardware/force-fixture-setup.md`                |
| Firmware setup                         | `docs/workflows/firmware-setup.md` and `Handgrip_Firmware/docs/firmware-setup.md`            |

## Validation rule

After the documentation migration, this command should return no canonical-doc hits, except explicit archive/deprecation notices:

```bash
rg "HX710B|stm32f103|Hacer bascula" README.md docs --glob '!docs/archive/**' || true
```

## Phase 0 decision

The Phase 0 decision is: **archive rather than delete by default** when historical traceability is useful, but keep all deprecated material out of canonical operator and developer pathways.
