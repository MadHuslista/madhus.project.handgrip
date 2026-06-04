Based on the structure and rigor of .augment/requests/doc.md, create comprehensive technical documentation that can create:

1. LSL_Bridge/README.md
2. LSL_Viewer/README.md
3. RS485_GUI/README.md
4. Handgrip_Firmware/README.md
5. A global project README.md at repository root

Important: this request is to generate documentation content for those README files, not code changes in runtime modules.

-------------------

Create comprehensive, evidence-backed technical documentation for the four modules and the global system view.

## Epistemic Quality Requirements
- Highest epistemic quality possible: Known whenever supported by source code, config, manuals, or repository documents.
- No hallucinations, no invented behavior, no undocumented assumptions.
- Every non-trivial claim must be traceable to evidence in repository files.
- Review links and references embedded in code comments and READMEs when those links are used to justify technical claims.
- For each major section, explicitly tag statements as:
  - Known: directly evidenced in code/config/docs.
  - Inferred: logical conclusion from evidence; must include reasoning.
  - Unknown: cannot be confirmed; list what is missing.

## Scope
Use only evidence from:
- LSL_Bridge
- LSL_Viewer
- RS485_GUI
- Handgrip_Firmware
- Project files

## 1. Module-Level High-Level Architectures

### A) LSL_Bridge Architecture
Document:
- Purpose: bridge from serial and RS485 IPC inputs to native LSL streams plus CSV persistence.
- Inputs:
  - Target serial stream from firmware.
  - Reference IPC stream from RS485 GUI (ZMQ PUB/SUB).
- Outputs:
  - Target LSL stream with channel contract.
  - Reference LSL stream with channel contract.
  - Target CSV and reference CSV logs.
    - Detail how it handles the different sampling rate of both published streams.
- Data-flow mapping end-to-end:
  - Serial read -> parser mode resolution -> timestamp policy -> processing filter chain -> LSL push -> CSV write.
  - RS485 IPC decode -> timestamp selection -> reference LSL push -> reference CSV write.
- Parser contracts:
  - auto/tagged_csv/simple_csv/legacy_pair_lines
  - optional CRC16 behavior for tagged frames
- Timestamp architecture:
  - target_timestamping policy behavior
  - processing timestamp_source behavior
  - diagnostics channels vs synchronization authority

### B) LSL_Viewer Architecture
Document:
- Purpose: dual-stream real-time visualization and offline replay/validation.
- Inputs:
  - Live LSL target + reference streams.
  - Replay files (target CSV, reference CSV, XDF).
- Outputs:
  - Real-time plots and replay plots for target/reference/timing/correlation views.
- Mode semantics:
  - live
  - live_with_reference_validation
  - csv_replay
  - xdf_replay
- Data-flow mapping:
  - Source selection by mode -> channel label validation -> window extraction -> optional alignment/interpolation -> render loop.
- Time alignment and interpolation policy:
  - raw_lsl/tail_aligned_lsl/manual
  - max_reference_gap_s and extrapolation policy
  - what is display-only vs what alters persisted data (must be explicit)

### C) RS485_GUI Architecture
Document:
- Purpose: acquisition board operator GUI, RS485 transport handling, protocol decoding, logging, and IPC publisher role.
- Inputs:
  - Serial data from RS485 adapter in modbus_rtu or active_send mode.
  - Config values controlling parsing, rates, rendering, logging, and IPC behavior.
- Outputs:
  - GUI plots/log panes/event logs.
  - raw_signal/interpreted_signal/gui_signal files.
  - ZMQ IPC publication with documented payload schema.
- Data-flow mapping:
  - Serial receive -> mode-specific decoding -> interpreted frame -> UI/logging -> optional IPC publish.
- Protocol handling:
  - Modbus RTU read/write functions, register map decoding, CRC validation.
  - Active-send parser profiles and timestamp_policy behavior.
- Reliability controls:
  - backpressure policy, recovery controls, downsampling/display limits, file flush strategy.

### D) Handgrip_Firmware Architecture
Document:
- Purpose: deterministic HX711 acquisition on Arduino Nano with interrupt-driven sampling and serial framing for the bridge.
- Inputs:
  - HX711 load-cell samples (read readiness and units conversion path).
  - Compile-time config values (sampling period, calibration mode/factor/offset).
- Outputs:
  - Tagged serial lines in firmware output contract.
- Data-flow mapping:
  - Timer interrupt -> HX711 readiness check -> sample struct -> FIFO push -> main loop pop -> serial emit.
- Concurrency model:
  - ISR producer / loop consumer
  - FIFO overflow semantics and error signaling via sequence handling.

## 2. Cross-Module Global Architecture (Root README)
Produce a global README that explains the full acquisition and analysis chain:
- Handgrip_Firmware -> LSL_Bridge target stream
- RS485_GUI -> LSL_Bridge reference stream via ZMQ IPC
- LSL_Bridge -> LSL streams + CSV artifacts
- LSL_Viewer live/replay consumption model
- Optional LabRecorder/XDF role in the workflow

Include:
- End-to-end sequence diagrams for:
  - live acquisition
  - offline replay
- Stream/channel contracts and naming conventions
- Clock and synchronization model across modules
- Failure/recovery boundaries (serial disconnect, parser failures, IPC backpressure)

## 3. Low-Level Protocol Documentation Requirements

### Firmware -> Bridge Serial Protocol
Explain in low-level detail:
- Exact frame format emitted by firmware.
- Sequence counter semantics.
- Timestamp unit and monotonic assumptions.
- Bridge parser acceptance/rejection behavior.
- CRC16 path for tagged frames (when enabled), including seed and comparison behavior.

### RS485 Protocol Layer
Explain in low-level detail:
- Modbus RTU function usage and register ranges consumed.
- Register-pair decoding for signed 32-bit quantities.
- Decimal/unit/status code interpretation pipeline.
- Command register writes and command code semantics.

### RS485 GUI -> Bridge IPC Protocol
Explain in low-level detail:
- ZMQ topology, bind/connect/topic, message structure.
- Published payload fields and semantic meaning.
- Timestamp fields (host_lsl_ts, received_lsl_ts, rs485_clock, source tags) and selection logic downstream.

### LSL Contracts
Document both target and reference stream metadata:
- stream names, types, source_id behavior
- channel labels, units, channel order
- nominal rate semantics (irregular vs regular)

## 4. Mandatory Magic Numbers Inventory
For each module, identify and explain the semantic purpose of all important constants and hard-coded defaults.

At minimum include:
- Sampling/clock numbers (for example firmware sampling period, viewer refresh/window sizes, bridge gap thresholds).
- Parser and frame limits (line sizes, buffer sizes, batch sizes, max frame bytes, CRC and regex assumptions).
- Signal-processing defaults (cutoff frequencies, Q values, warmup, baseline/drift thresholds, reset-on-gap values).
- Communication values (baud maps, parity codes, stop-bit codes, active-send frequency code mappings, Modbus register indices, command codes, topic strings, HWM values).
- UI/logging performance controls (render downsampling, max plot points, flush intervals, retention counts).

For each magic number:
- Provide location (file + symbol or code context).
- Explain functional role.
- Explain impact if changed.
- State whether value is protocol-defined, hardware-limited, empirical, or project policy.

## 5. State Machines and Runtime Modes
Document explicit state/mode behavior across modules:
- Bridge parser mode selection and fallback.
- Viewer mode transitions and data source selection.
- RS485 GUI mode (modbus_rtu vs active_send), connection lifecycle, and recovery behavior.
- Firmware operational states implied by calibration mode, HX711 ready/not-ready, FIFO full/empty conditions.

## 6. Configuration and CLI Documentation
For each module README:
- Provide configuration key reference tables (key, type, default, meaning, constraints).
- Provide run commands from repository root and module folder when applicable.
- Provide override examples for high-impact parameters.
- Document prerequisites and optional dependencies (for example mne-lsl, pyxdf, pyzmq, pylsl, PlatformIO).

## 7. Validation and Reproducibility Requirements
Include a verification section in each README:
- How to confirm module startup success.
- What expected runtime logs/output look like.
- How to detect common misconfigurations.
- Minimal smoke-test checklist.

For the global README include:
- End-to-end bring-up checklist.
- Integration test checklist for live and replay paths.

## 8. Formatting Requirements
- Use clear section headers with ## and ###.
- Use tables for:
  - stream/channel schemas
  - register/command maps
  - mode/state definitions
  - magic-number inventories
  - config references
- Use bullet points for step-by-step workflows.
- Include compact code snippets where needed.
- Define technical terms on first use.
- Cross-reference related sections between module READMEs and the global README.

## 9. Output Package Requirements
Provide the output as five README-ready documents:
1. LSL_Bridge README content
2. LSL_Viewer README content
3. RS485_GUI README content
4. Handgrip_Firmware README content
5. Root/global README content

Each document must:
- Be complete and directly usable.
- Separate Known/Inferred/Unknown claims where ambiguity exists.
- Include an evidence appendix listing the repository files used to justify the claims.

===================
