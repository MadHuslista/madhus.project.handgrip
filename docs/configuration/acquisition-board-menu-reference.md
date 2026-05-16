# Acquisition Board Menu Reference

**Status:** Canonical root hardware/configuration reference  
**Device:** High-speed acquisition instrument used with the PM58 reference load cell  
**Primary readable source:** `docs/hardware/acquisition-board-reference.md`  
**Design rationale source:** `Documentation/dual_device_calibration_configuration_report.md`  
**Fallback references:** acquisition-board PDFs under `docs/hardware/references/acquisition-board/`

## Summary

This document captures the acquisition-board menu items that matter for the Handgrip calibration reference chain. The priority is reproducible calibration, not generic weighing-indicator operation.

## Menu overview

| Menu code | Display label | Default | Recommended calibration value | Range / options | Effect | Risk | Source reference |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `C1.SyS` | System settings block | factory/config dependent | Use values below | `100.*` system parameters | Sampling, gain, filters, display units, display behavior. | Wrong system profile can hide drift or reduce reference quality. | Reorganized manual §10; dual-device report §A. |
| `100.SP` | Internal sampling | varies | `640 Hz` | board-supported sampling rates | Internal ADC/acquisition rate. | Too low loses timing detail; too high may increase noise/transport stress. | dual-device report A. |
| `101.GA` | ADC gain | varies | `128B` | board-supported gains | Matches PM58 mV/V range to ADC resolution. | Wrong gain can saturate or reduce resolution. | dual-device report A. |
| `102.ME` | Median filter | varies | `3` | supported median lengths | Suppresses impulse outliers. | Too high adds lag or hides transient behavior. | dual-device report A. |
| `103.rV` | Average filter | varies | `5` | supported average lengths | Smooths reference signal modestly. | Too high adds lag/smoothing. | dual-device report A. |
| `104.ds` | Lower display item | varies | Unit / measurement unit | display item options | Operator display convenience. | Low calibration impact. | dual-device report summary. |
| `105.uN` | Unit | varies | `N` | supported engineering units | Makes reference force physically consistent with calibration reports. | Unit mismatch causes conversion/report errors. | dual-device report A. |
| `106.bi` | Decimal point | varies | `1` | decimal positions | Display granularity, window interpretation. | Too fine makes stability/zero windows unrealistic. | dual-device report A. |
| `107.dV` | Graduation value | varies | `1` | supported divisions | Display increment. | Display interpretation mismatch. | dual-device report A. |
| `108.ro` | Maximum weighing/range | varies | `900.0 N` | up to sensor/board range | Defines operating cap. | Unsafe or saturated range if too low/high. | dual-device report A. |
| `109.di` | DI input function | varies | `NoNE` | zero/tare/peak functions etc. | Prevents remote accidental commands. | Stray input can silently zero/tare during calibration. | dual-device report A. |
| `110.MZ` | Peak threshold | varies | `5.0 N` | positive force threshold | Peak display update threshold. | Noise-driven peak refresh if too low. | dual-device report A. |
| `111.MN` | Peak interval | varies | `0.10 s` | supported seconds | Peak update cadence. | Too slow for repeated short squeezes. | dual-device report A. |
| `113.uP` | Display refresh | varies | `0.05 s` | supported seconds | Human display responsiveness. | Operator confusion if sluggish; not data-path sampling. | dual-device report A. |
| `114.bp` | Backup | varies | `YES after validation` | `YES` / no backup | Persists known-good profile. | Backing up unvalidated profile locks in errors. | dual-device report A. |
| `C2.CAL` | Calibration block | factory/config dependent | Use known-load calibration as primary | `201.*`–`209.*` | Reference board calibration quality. | Bad reference calibration corrupts target fit. | Reorganized manual §11; dual-device report §B. |
| `201.Mo` | Calibration mode | varies | `Load` | load / datasheet modes | Selects calibration method. | Datasheet-only mode is lower quality unless no loads available. | dual-device report B. |
| `202.WE` | Calibration load | setup dependent | Largest traceable load in intended operating range | safe traceable load | Sets/span-calibrates reference. | Poor load point reduces span accuracy. | dual-device report B. |
| `203.rA` | Datasheet backup range | varies | `980.7 N` | sensor range | Backup range for datasheet mode. | Wrong backup range gives bad disaster recovery. | dual-device report B. |
| `204.SE` | Datasheet sensitivity | varies | `1.504 mV/V` | sensor certificate value | Backup sensitivity. | Wrong sensitivity biases reference. | dual-device report B. |
| `205.rE` | Excitation | varies | `5.000 V` | board excitation options | Load-cell excitation reference. | Wrong excitation in datasheet mode biases scaling. | dual-device report B. |
| `206.rV` | Span trim | varies | `1.000` | trim factor | Fine span compensation. | Ad hoc trim hides real fixture/reference problems. | dual-device report B. |
| `207.mE` | Multipoint enable | varies | `0 initially` | off/on | Enables multipoint correction. | Premature complexity and hard-to-audit reference correction. | dual-device report B. |
| `208.mC` | Multipoint count | varies | unused initially | count if multipoint enabled | Multipoint point count. | Badly placed points can worsen calibration. | dual-device report B. |
| `209.Mr` | Multipoint range | varies | unused initially | range settings | Multipoint range. | Misapplied range correction. | dual-device report B. |
| `C4.AdV` | Advanced functions | factory/config dependent | Disable hidden correction features unless explicitly validated | `400.*`–`413.*` | Creep, zero masking, tracking, stability logic. | Hidden correction can distort calibration data. | Reorganized manual §13; dual-device report §C. |
| `400.CV` | Creep tracking | varies | `0` | off/on or numeric option | Hidden slow correction. | Hides real drift during calibration. | dual-device report C. |
| `401.dZ` | Display zero range mask | varies | `0` | range value | Cosmetic zero masking. | Hides real offset. | dual-device report C. |
| `402.tV` | Dynamic tracking | varies | `0` | off/on | Vendor dynamic correction. | Can distort force trace. | dual-device report C. |
| `403.tC` | Dynamic tracking coefficient/refresh | varies | `0.2` if feature context requires; otherwise keep inactive | supported values | Dynamic tracking behavior. | Misleading final settled jumps if enabled incorrectly. | dual-device report C. |
| `404.SV` | Stable weight switch | varies | `0` | off/on | Stable-only display behavior. | Hides evolving signal. | dual-device report C. |
| `405.Zr` | Zero range | varies | `5.0 N` | range value | Limits manual zero region. | Too wide lets real load be zeroed away. | dual-device report C. |
| `406.PZ` | Power-on zero enable | varies | `0` | off/on | Startup auto-zero. | Silent baseline shift at startup. | dual-device report C. |
| `409.AZ` | Auto-zero | varies | `0` | off/on | Runtime auto-zero. | Hidden drift correction during session. | dual-device report C. |
| `410.At` | Auto-zero time | varies | inactive | supported time values | Auto-zero timing. | Same as above if enabled. | dual-device report C. |
| `411.Ar` | Auto-zero range | varies | inactive | range value | Auto-zero range. | Same as above if enabled. | dual-device report C. |
| `412.Wr` | Stability range | varies | diagnostic only | range value | Stability detection. | Can gate/interpret holds incorrectly. | dual-device report C. |
| `413.Wt` | Stability time | varies | diagnostic only | time value | Stability detection. | Can gate/interpret holds incorrectly. | dual-device report C. |
| `C5.CoM` | RS485 communication block | factory/config dependent | Use values below | `500.*` communication parameters | Serial address, baud, framing, Active-Send. | Wrong settings break host acquisition. | Reorganized manual §14; dual-device report §D. |
| `500.Ar` | Address | varies | `1` | 1–247 typical Modbus range | Device address. | Host polls wrong address. | dual-device report D. |
| `501.br` | Baud | varies | `460800` | board-supported baud rates | RS485 transport speed. | Garbled/no data if host mismatch. | dual-device report D. |
| `502.Vb` | Parity | varies | `none` | none/even/odd options | Serial framing. | Host mismatch prevents reading. | dual-device report D. |
| `503.so` | Stop bits | varies | `1` | 1/2 where supported | Serial framing. | Host mismatch prevents reading. | dual-device report D. |
| `504.AS` | RS485 mode | varies | `1` Active-Send | `0` Modbus polling, `1` Active-Send | Reference streaming mode. | Active-Send parser stress; Modbus lower timing performance. | dual-device report D. |
| `505.AF` | Active-Send rate | varies | `500 Hz` | board-supported rates | Reference output rate. | Too high overloads parser; too low loses timing detail. | dual-device report D. |
| `C6.aNa` | Analog output | factory/config dependent | Not in calibration path | analog modes | PLC/analog output only. | Irrelevant settings can distract from digital path. | Reorganized manual §15. |
| `C7.LOC` | Password | factory/config dependent | Optional lock after validation | password settings | Prevents accidental changes. | Lost password or unprotected config drift. | Reorganized manual §16. |
| `C8.FAC` | Factory calibration | factory | Do not modify | factory-only | Factory trim/calibration. | Can permanently corrupt board calibration without traceable equipment. | Reorganized manual §17; dual-device report G. |
| `C9.iNF` | Information | read-only | Read only | version/info | Device info. | None unless misinterpreted as setting. | Reorganized manual §18. |

## Commissioning sequence

1. Configure `C1.SyS` system settings.
2. Configure `C2.CAL` reference calibration.
3. Disable/limit hidden correction under `C4.AdV`.
4. Configure RS485 under `C5.CoM`.
5. Verify reference-only acquisition in `RS485_GUI`.
6. Backup settings only after validation.
