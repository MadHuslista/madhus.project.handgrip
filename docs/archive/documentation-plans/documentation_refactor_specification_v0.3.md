# Documentation Refactor Specification v0.3 — Handgrip Suite

## Summary

- **This v0.3 specification supersedes v0.1 and v0.2** while preserving their approved direction: root `README.md` as the first entry point, root `docs/` for system-level documentation, and per-component `README.md` + `docs/` folders for implementation-level documentation.
- **The corrected ZIP validates the core architecture assumed by v0.2:** the suite is a multi-component source-layout Python/firmware workspace with `Handgrip_Firmware`, `RS485_GUI`, `LSL_Bridge`, `LSL_Viewer`, `Handgrip_Calibration`, and `Handgrip_Analysis`.
- **The v0.1 reader-persona and high-level-to-low-level pathway sections are promoted to governing design principles** for v0.3. The final docs must let a principal investigator understand purpose and safe operation quickly, while letting student maintainers progressively reach code/config/protocol internals.
- **Images are now first-class documentation assets.** Existing `Documentation/assets/` photos must be migrated into canonical hardware docs. The new setup images requested by Nicolás must be added and used in the physical/force-fixture pathway:
  - `pm58_n_handgrip_setup.jpg`
  - `acq_board_n_pm58_n_handgrip_setup.jpg`
  - `force_application_setup.jpg`
- **PDFs are classified into canonical references, fallback references, and deprecated material.** The acquisition-board PDFs, HX711 datasheet, provider-offer screencapture, reorganized board manual, and PM58 board manual remain useful. Old HX710B / old ADV / old MCU material must not appear in canonical documentation.
- **The prior critical D2 code issue is resolved in source but not in docs.** Source emits canonical `D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>`, but `Handgrip_Firmware/README.md` still documents legacy `D,<seq>,<timestamp_us>,<value_gr>`.
- **Two handoff-blocking documentation consistency issues remain:** calibration config snapshots still reference `../RS485_GUI/config.yaml` while the actual path is `RS485_GUI/config/config.yaml`, and CLI defaults still reference `protocol_static_staircase.yaml` while the README and example calibration output identify `protocol_static_reversible_staircase_v3.yaml` as primary.

## Recommended Action

### Priority 0 — Stabilize source-of-truth contracts before polishing prose

1. Fix stale firmware protocol docs from `D,<seq>,...` to `D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>`.
2. Fix or explicitly document the calibration config snapshot path mismatch from `../RS485_GUI/config.yaml` to `../RS485_GUI/config/config.yaml`.
3. Decide whether `protocol_static_reversible_staircase_v3.yaml` becomes the CLI default, or keep CLI default as legacy while marking v3 as the recommended operator workflow.
4. Add the three new setup photos to the repo before finalizing hardware docs:

### Priority 1 — Build the reader pathway

1. Create root `README.md` as the first screen for all audiences.
2. Create `docs/index.md` as the map from high-level workflows to component internals.
3. Create root workflow docs in this order:
   - physical setup,
   - firmware setup,
   - target-only quickstart,
   - full live-viewer quickstart,
   - calibration workflow,
   - analysis workflow.
4. Create each component `docs/index.md` and component-specific workflow/config/implementation docs.

### Priority 2 — Preserve references without polluting the operator pathway

1. Promote reorganized hardware manuals into `docs/hardware/`.
2. Keep source PDFs under `docs/hardware/references/` with explicit fallback-reference status.
3. Move deprecated HX710B / old ADV / old MCU material out of canonical docs, preferably under `docs/archive/deprecated/` or remove from the handoff package if source preservation is not required.
4. Add `docs/hardware/assets/README.md` mapping every image to where it is used and what it proves.

### Priority 3 — Make the docs maintainable by students

1. Add configuration reference tables for every config file.
2. Add “how to edit safely” docs for each library.
3. Add a Python source-layout primer targeted at research Python users who are new to industry-style packaging.
4. Add validation commands and checklist-based acceptance tests for the documentation itself.

## Epistemic Status

| Claim / Area                                                                      | Status | Basis / Next Step                                                                                                                                                                                |
| --------------------------------------------------------------------------------- | -----: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Corrected ZIP is readable and contains the full workspace structure               |  Known | The archive extracts cleanly and contains the six expected components plus root `pyproject.toml`, `platformio.ini`, `Binnacle.md`, and `Documentation/`.                                         |
| Root `README.md` is still missing                                                 |  Known | Root `pyproject.toml` references `README.md`, but no root `README.md` exists in the extracted tree.                                                                                              |
| Root `docs/` is still missing                                                     |  Known | The corrected ZIP uses legacy `Documentation/`, not root `docs/`.                                                                                                                                |
| Existing `Documentation/assets/` contains useful hardware photos                  |  Known | The ZIP includes photos for rear terminal map, AC input, front panel, PM58 label/certificate, Google Lens rear label, and old ADC/MCU images.                                                    |
| The three new setup photos requested in v0.3 are not present in the corrected ZIP |  Known | No filenames matching `pm58_n_handgrip_setup.jpg`, `acq_board_n_pm58_n_handgrip_setup.jpg`, or `force_application_setup.jpg` were found.                                                         |
| Acquisition-board PDFs and HX711 datasheet should be retained as references       |  Known | User explicitly requested this classification in v0.3 notes.                                                                                                                                     |
| HX710B / old ADV / old MCU material should be ignored/removed from canonical docs |  Known | User explicitly requested removal/ignore.                                                                                                                                                        |
| Firmware source emits canonical D2 payload                                        |  Known | `Handgrip_Firmware/Core/Src/main.cpp` emits `Serial.print("D2,")`; `config.h` documents D2 schema.                                                                                               |
| Firmware README is stale                                                          |  Known | `Handgrip_Firmware/README.md` still documents `D,<seq>,<timestamp_us>,<value_gr>`.                                                                                                               |
| Calibration config snapshot paths are wrong/brittle                               |  Known | `Handgrip_Calibration/conf/*.yaml` references `../RS485_GUI/config.yaml`, but actual config lives at `RS485_GUI/config/config.yaml`.                                                             |
| Canonical calibration protocol is not fully enforced                              |  Known | Calibration README names v3 as primary; CLI default still points to `protocol_static_staircase.yaml`; legacy workflow manual uses old protocol.                                                  |
| Whether outdated PDFs should be deleted or archived                               |  Could | Decide handoff policy: strict removal from deliverable vs historical archive outside canonical docs. Recommended: remove from canonical and optionally archive under `docs/archive/deprecated/`. |

---

# 1. Scope and Inputs for v0.3

## 1.1 Version lineage

This document treats the prior plans as follows:

| Plan                                              | Status        | Role in v0.3                                                                                                                                                                 |
| ------------------------------------------------- | ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `documentation_refactor_specification.md`         | Approved v0.1 | Source for original reader-persona design, high-level-to-low-level documentation pathway, full inventory style, broad gap list, templates, and first directory architecture. |
| `documentation_refactor_specification_updated.md` | Approved v0.2 | Source for corrected-ZIP validation, updated known issues, updated component inventory, and revised execution plan.                                                          |
| This document                                     | v0.3          | Standalone implementation specification that consolidates v0.1 + v0.2 and integrates the image/PDF/reference classification notes.                                           |

## 1.2 Repository reviewed

Corrected ZIP:

```text
madhus.project.handgrip.zip
```

Observed top-level tree:

```text
.
├── Binnacle.md
├── Documentation/
├── Handgrip_Analysis/
├── Handgrip_Calibration/
├── Handgrip_Firmware/
├── LSL_Bridge/
├── LSL_Viewer/
├── RS485_GUI/
├── platformio.ini
└── pyproject.toml
```

Important observed facts:

- `README.md` is missing at repository root.
- `docs/` is missing at repository root.
- `Documentation/` contains valuable historical/reference docs but is not organized as an operator-first documentation tree.
- Each component has a `README.md`, but no component has a complete `docs/` subtree.
- The workspace already uses modern Python source-layout packages for most Python components.
- Root `pyproject.toml` acts as a workspace/development aggregator and references the missing root `README.md`.

## 1.3 Components in scope

| Component              | Type                                         | Primary responsibility                                                                            | Documentation role                                                                               |
| ---------------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `Handgrip_Firmware`    | PlatformIO / Arduino firmware                | Read HX711 load-cell data and stream target handgrip data over UART                               | Firmware setup, build/upload, serial protocol, compile-time configuration, extension guide.      |
| `RS485_GUI`            | Python / NiceGUI / RS485 acquisition app     | Connect to acquisition board, acquire Modbus RTU or Active-Send data, plot/log/publish via ZeroMQ | Reference-board bring-up, live acquisition, IPC contract, logs, GUI config.                      |
| `LSL_Bridge`           | Python / LSL bridge                          | Publish `HandgripTarget`, `HandgripReference`, and event streams to Lab Streaming Layer           | Stream contracts, timestamping policy, target/reference ingestion, CSV logging.                  |
| `LSL_Viewer`           | Python / NiceGUI / LSL viewer                | Live visualize target/reference streams, XY correlation, CSV/XDF replay                           | Operator visualization workflow, troubleshooting visual lag, config options.                     |
| `Handgrip_Calibration` | Python / CLI calibration workflow            | Record calibration sessions, fit target-vs-reference models, generate reports                     | Calibration protocol, data capture, fitting, outputs, how to apply calibration results.          |
| `Handgrip_Analysis`    | Python / CLI analysis pipeline               | Multi-stage signal characterization and filter-design analysis                                    | Experimental analysis workflow, stage definitions, filter-design interpretation, output catalog. |
| `Documentation`        | Legacy documentation/source-reference folder | Contains historical reports, hardware manuals, PDFs, photos, generated plans                      | Must be split into canonical docs, references, and archive/deprecated material.                  |

---

# 2. Current System Understanding

## 2.1 System purpose

The Handgrip Suite is an end-to-end acquisition, visualization, calibration, and analysis system for a handgrip force-sensing setup. It combines:

1. a **target handgrip device** based on HX711 load-cell ADC readings streamed by Arduino firmware,
2. a **reference acquisition chain** based on a PM58 load cell connected to a high-speed RS485 acquisition board,
3. a **host-side acquisition GUI** for the RS485 board,
4. a **Lab Streaming Layer bridge** that publishes synchronized target/reference streams,
5. a **viewer** for live inspection and replay,
6. a **calibration workflow** for fitting target output to reference force,
7. an **analysis workflow** for signal-quality characterization and filter selection.

The documentation must support two operating modes:

- **Run the system correctly** for experiments and calibration.
- **Modify the system safely** when research needs evolve.

## 2.2 Physical and data chain

Canonical physical/data chain:

```text
[Handgrip mechanical fixture]
        │
        ├── Target path:
        │     load cell(s) → HX711 → Arduino Nano firmware → UART / USB serial
        │                                      │
        │                                      ▼
        │                              LSL_Bridge target input
        │
        └── Reference path:
              PM58 load cell → high-speed acquisition board → RS485 / USB-RS485
                                                  │
                                                  ▼
                                             RS485_GUI
                                                  │ ZeroMQ IPC
                                                  ▼
                                             LSL_Bridge reference input

LSL_Bridge → Lab Streaming Layer streams → LSL_Viewer / Handgrip_Calibration / recordings
```

## 2.3 Core contracts the documentation must protect

| Contract                     | Canonical value / rule                                                                               | Why it matters                                                                  |
| ---------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Firmware serial schema       | `D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>`                                       | LSL bridge parsing and calibration depend on exact field order.                 |
| Target LSL stream            | `HandgripTarget`, type `Force`, D2-derived channels                                                  | Calibration and viewer discover the target stream by name/type/schema.          |
| Reference LSL stream         | `HandgripReference`, type `Force`, RS485-derived channels                                            | Calibration fits target against this reference.                                 |
| RS485 GUI config path        | `RS485_GUI/config/config.yaml`                                                                       | Cross-component config snapshots and operator docs must point to the real file. |
| Reference IPC topic          | `rs485.measurement.v1`                                                                               | LSL bridge consumes the RS485 GUI output through this contract.                 |
| Primary calibration protocol | `Handgrip_Calibration/conf/protocol_static_reversible_staircase_v3.yaml` unless changed deliberately | Prevents students from running stale/less complete calibration workflows.       |
| Hardware reference docs      | Acquisition-board manuals, reorganized board manual, PM58 wiring manual, HX711 datasheet             | These are fallback facts for troubleshooting and extension.                     |
| Deprecated hardware docs     | HX710B / old ADV / old STM32F103 material                                                            | Must not confuse the current HX711/Arduino + RS485 board system.                |

---

# 3. Reader Personas and Documentation Pathway

This section is promoted from v0.1 and adapted for v0.3. It should guide every documentation file written during the overhaul.

## 3.1 Reader personas

### Persona A — Principal investigator / PhD user

**Profile:** Intensive Python user, strong research and neuroscience context, not necessarily trained in industry-standard Python packaging, source-layout architecture, or decoupled application design.

**Primary needs:**

- Understand what the whole suite does.
- Know how to run the system safely.
- Know what the calibration/analysis outputs mean scientifically.
- Know where students should look when extending the code.

**Best entry points:**

1. `README.md`
2. `docs/start-here.md`
3. `docs/system-overview.md`
4. `docs/workflows/full-live-viewer-quickstart.md`
5. `docs/workflows/handgrip-calibration.md`
6. `docs/workflows/handgrip-analysis.md`

**Documentation style for this persona:**

- Summary first.
- Explain acronyms on first use.
- Use diagrams and photos.
- Make scientific interpretation explicit.
- Avoid assuming packaging/architecture background.

### Persona B — Undergraduate student operator

**Profile:** Has time to learn. Needs to run acquisition, validate connections, launch apps in the correct order, capture data, and avoid damaging hardware or producing unusable sessions.

**Primary needs:**

- See what to connect physically.
- Know exact commands and order.
- Know what success looks like.
- Know where data appears.
- Know what to do when something fails.

**Best entry points:**

1. `README.md` → “I only need to run it”
2. `docs/workflows/physical-setup.md`
3. `docs/workflows/firmware-setup.md`
4. `docs/workflows/target-only-quickstart.md`
5. `docs/workflows/full-live-viewer-quickstart.md`
6. `docs/troubleshooting/index.md`

**Documentation style for this persona:**

- Checklist-based.
- Command blocks with expected output.
- “Stop if this fails” validation gates.
- Photos next to wiring instructions.
- Avoid long theoretical detours in workflow docs; link to deeper references.

### Persona C — Undergraduate maintainer/developer

**Profile:** Python-capable, may not know source-layout packaging, Hydra/OmegaConf, Lab Streaming Layer, ZeroMQ, NiceGUI, or decoupled architecture patterns.

**Primary needs:**

- Understand repo structure.
- Understand how each package is installed, tested, and run.
- Know where configuration lives.
- Know how data contracts flow across modules.
- Know safe extension patterns.

**Best entry points:**

1. `docs/development/python-project-structure-primer.md`
2. `docs/architecture/repository-layout.md`
3. `docs/architecture/dataflow.md`
4. `docs/architecture/stream-contracts.md`
5. Component `docs/index.md`
6. Component `docs/development.md` / `docs/architecture.md`

**Documentation style for this persona:**

- Explain source-layout architecture explicitly.
- Explain “configuration as data” and override precedence.
- Include code navigation maps.
- Include extension recipes.
- Include tests and validation commands.

### Persona D — Future external collaborator

**Profile:** May receive the repository without Nicolás present. Needs to rebuild context from docs alone.

**Primary needs:**

- Understand purpose and system boundaries.
- Know what is canonical vs historical.
- Know which manuals/specs are fallback references.
- Know current known issues and validation state.

**Best entry points:**

1. `README.md`
2. `docs/index.md`
3. `docs/system-overview.md`
4. `docs/references/index.md`
5. `docs/archive/index.md`

**Documentation style for this persona:**

- Explicit source-of-truth declarations.
- Archive notes on stale docs.
- Diagrams and contracts.
- “Known / Could / Cannot” epistemic status where uncertainty matters.

## 3.2 High-level-to-low-level pathway

The documentation should form a **progressive disclosure tree**:

```text
Root README
  ├── Start Here
  │     ├── What is this system?
  │     ├── What should I do first?
  │     └── Which workflow matches my task?
  │
  ├── System Overview
  │     ├── Physical setup
  │     ├── Dataflow
  │     ├── Components
  │     └── Key contracts
  │
  ├── Operator Workflows
  │     ├── Physical setup
  │     ├── Firmware setup
  │     ├── Target-only quickstart
  │     ├── Full live viewer quickstart
  │     ├── Calibration
  │     └── Analysis
  │
  ├── Component Docs
  │     ├── Component README
  │     ├── Component docs/index.md
  │     ├── Workflow docs
  │     ├── Config reference
  │     └── Implementation/extension docs
  │
  ├── References
  │     ├── Hardware manuals
  │     ├── Datasheets
  │     ├── Protocol contracts
  │     └── Source PDFs
  │
  └── Archive / Deprecated
        ├── Historical reports
        ├── Generated outputs
        └── Deprecated old hardware references
```

The pathway must avoid forcing a novice reader into code before they understand:

1. the purpose of the system,
2. the physical setup,
3. the runtime order,
4. what signals exist,
5. where outputs are written,
6. how configuration affects behavior,
7. how code modules connect.

## 3.3 Canonical reading sequence for handoff

### Track 1 — “I need to understand the system today”

1. `README.md`
2. `docs/start-here.md`
3. `docs/system-overview.md`
4. `docs/architecture/dataflow.md`
5. `docs/workflows/full-live-viewer-quickstart.md`

### Track 2 — “I need to run a calibration session”

1. `docs/workflows/physical-setup.md`
2. `docs/workflows/target-only-quickstart.md`
3. `docs/workflows/full-live-viewer-quickstart.md`
4. `docs/workflows/handgrip-calibration.md`
5. `Handgrip_Calibration/docs/index.md`
6. `Handgrip_Calibration/docs/protocols.md`

### Track 3 — “I need to run the analysis framework”

1. `docs/workflows/handgrip-analysis.md`
2. `Handgrip_Analysis/docs/index.md`
3. `Handgrip_Analysis/docs/stages.md`
4. `Handgrip_Analysis/docs/configuration.md`
5. `Handgrip_Analysis/docs/filter-design.md`

### Track 4 — “I need to modify or extend the code”

1. `docs/development/python-project-structure-primer.md`
2. `docs/architecture/repository-layout.md`
3. `docs/architecture/stream-contracts.md`
4. Relevant component `docs/architecture.md`
5. Relevant component `docs/development.md`
6. Relevant component tests.

---

# 4. v0.3 Validation of v0.1 and v0.2 Plan Points

## 4.1 Plan-level validation matrix

| Prior plan point                                                                        |            v0.3 status | Update / action                                                                                                  |
| --------------------------------------------------------------------------------------- | ---------------------: | ---------------------------------------------------------------------------------------------------------------- |
| Root `README.md` must be first entry point                                              |              Validated | Still missing. Keep as top priority.                                                                             |
| Root `docs/` should contain system-level docs                                           |              Validated | Still missing. Create from scratch; do not keep `Documentation/` as canonical root.                              |
| Each library/firmware should have its own `README.md`                                   |              Validated | Already exists for all components, but each README must become a landing page instead of full/detail dump.       |
| Each library/firmware should have `docs/index.md`                                       |              Validated | Still missing. Create for every component.                                                                       |
| Root `docs/` should cover system-level content not owned by a component                 |              Validated | Especially physical setup, end-to-end workflow, architecture, stream contracts, references, troubleshooting.     |
| Existing docs contain scattered valuable information                                    |              Validated | Legacy `Documentation/` contains manuals, reports, workflow docs, PDFs, photos, and generated plans.             |
| Generated outputs/logs should not be treated as maintained docs                         |              Validated | Analysis/calibration output reports should become examples or move to archive.                                   |
| Firmware source had possible D2 double-comma issue                                      |             Superseded | Corrected ZIP source emits strict D2 payload. Remove code-bug warning; keep stale-doc warning.                   |
| Firmware README schema drift                                                            |      Added / Validated | README still documents legacy `D,<seq>,...`; fix required.                                                       |
| Calibration config path mismatch                                                        |              Validated | `../RS485_GUI/config.yaml` remains in calibration config files; actual config is `RS485_GUI/config/config.yaml`. |
| Calibration protocol ambiguity                                                          |              Validated | README uses v3 as primary; CLI default and old workflow manual still use old static staircase.                   |
| v0.1 reader personas should guide documentation                                         |               Promoted | Integrated as Section 3 and made governing principle for v0.3.                                                   |
| Hardware docs should be promoted                                                        | Validated and expanded | Add explicit image/PDF policy and force-fixture docs.                                                            |
| Config references are missing                                                           |              Validated | Create global and component config references.                                                                   |
| Source-layout / industry-standard architecture should be explained for handoff audience | Validated and expanded | Add a dedicated research-to-industry Python primer.                                                              |

## 4.2 New v0.3 deltas from user notes

| Delta                                                                           | Impact                                                            | Required plan update                                                                                       |
| ------------------------------------------------------------------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Existing `assets/` photos are intended documentation material                   | The plan must not archive all photos blindly.                     | Create image usage map and migrate useful hardware photos into canonical docs.                             |
| New setup images are expected                                                   | Physical setup docs can become much clearer.                      | Reserve canonical paths and explicitly map each image to docs.                                             |
| Acquisition-board PDFs are fallback references                                  | Avoid over-editing or replacing source manuals.                   | Store source PDFs in references; use reorganized manual as readable canonical reference.                   |
| PM58 acquisition board manual should remain but be improved for reproducibility | It is both reference and operator material.                       | Promote into `docs/hardware/pm58-wiring-and-bringup.md` and clean structure.                               |
| Provider offer screencapture is fallback reference                              | Useful for procurement/general context but not operational truth. | Store under `docs/hardware/references/provider-offer/`.                                                    |
| HX711 datasheet is canonical reference                                          | Needed for target ADC behavior.                                   | Store under `docs/hardware/references/hx711_english.pdf` and cite in firmware/reference docs.              |
| HX710B / old ADV / STM32F103 PDFs are outdated                                  | Risk of confusing current architecture.                           | Remove from canonical docs; optionally archive under deprecated with explicit “not current system” banner. |

---

# 5. Existing Information Inventory

## 5.1 Inventory classification legend

| Field        | Values                                                                                                          |
| ------------ | --------------------------------------------------------------------------------------------------------------- |
| Relevance    | `Canonical`, `Relevant`, `Reference fallback`, `Example output`, `Deprecated`, `Remove from canonical`          |
| Detail level | `Entry`, `Workflow`, `Reference`, `Implementation`, `Config`, `Historical`, `Generated output`                  |
| Category     | `System`, `Hardware`, `Firmware`, `RS485`, `LSL`, `Calibration`, `Analysis`, `Architecture`, `Style`, `Archive` |

## 5.2 Inventory table

| ID        | Status                                 | Level                   | Category            | Location                                                                                                                  | Useful content                                                                                  | Related IDs                | v0.3 handling                                                                                                               |
| --------- | -------------------------------------- | ----------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | -------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| SYS-001   | Canonical source                       | Config / workspace      | System              | `pyproject.toml`                                                                                                          | Workspace dependencies, editable local packages, pytest config, missing root README declaration | SYS-002, DEV-001           | Document in `docs/development/workspace-setup.md`; ensure root README exists.                                               |
| SYS-002   | Historical / partial                   | Historical              | System              | `Binnacle.md`                                                                                                             | Early notes about load cells, HX710B/ADC discovery, initial reasoning                           | OLD-001, OLD-002           | Do not use as canonical; archive with status note if preserved.                                                             |
| STYLE-001 | Canonical style source                 | Style                   | Style               | external `report_writing_redaction_guide_for_agents.md`                                                                   | Summary-first, epistemic status, validation-oriented report style                               | ALL                        | Copy/adapt into `docs/contributing/report-writing-style.md`.                                                                |
| HW-001    | Canonical readable reference           | Reference               | Hardware            | `Documentation/high_speed_acquisition_instrument_reorganized_manual.md`                                                   | Best organized full acquisition-board manual; menu/config reference; safety; wiring; UI         | HW-002, HW-003, HW-005     | Promote to `docs/hardware/acquisition-board-reference.md`; keep mostly intact.                                              |
| HW-002    | Reference fallback                     | Reference               | Hardware            | `Documentation/Sc36bd8ca2a714cf581ed5b70b722a27cW.pdf`                                                                    | Original acquisition-board manual in Chinese with inline English                                | HW-001, HW-003             | Store under `docs/hardware/references/acquisition-board/original-chinese-inline-english.pdf`.                               |
| HW-003    | Reference fallback                     | Reference               | Hardware            | `Documentation/Sc36bd8ca2a714cf581ed5b70b722a27cW_en.pdf`                                                                 | Google-translated English acquisition-board manual                                              | HW-001, HW-002             | Store under `docs/hardware/references/acquisition-board/google-translated-english.pdf`.                                     |
| HW-004    | Reference fallback                     | Reference / procurement | Hardware            | `Documentation/screencapture-es-aliexpress-data-acquisition-device-item-1005009874603061-html-2026-04-08-04_30_50.pdf`    | Vendor offer / general product bundle context                                                   | HW-001, HW-005             | Store under `docs/hardware/references/provider-offer/`. Use only for provenance/procurement context.                        |
| HW-005    | Relevant / improve                     | Workflow + Reference    | Hardware            | `Documentation/pm58_acquisition_board_manual.md`                                                                          | PM58 load cell wiring, acquisition board wiring, bring-up                                       | HW-006, HW-007             | Rewrite/promote to `docs/hardware/pm58-wiring-and-bringup.md`. Improve organization/readability/reproducibility.            |
| HW-006    | Canonical assets                       | Visual reference        | Hardware            | `Documentation/assets/*.jpg` current useful photos                                                                        | Rear terminal map, AC input, front panel, PM58 label/certificate, rear label translation        | HW-005, IMG-001            | Migrate useful photos to `docs/hardware/assets/`; add usage map and alt text.                                               |
| IMG-001   | Required incoming assets               | Visual workflow         | Hardware / Fixture  | New images requested: `pm58_n_handgrip_setup.jpg`, `acq_board_n_pm58_n_handgrip_setup.jpg`, `force_application_setup.jpg` | Physical PM58/handgrip/acquisition-board/screw-press setup                                      | HW-005, WF-001, CAL-001    | Add to `docs/hardware/assets/`; use in `physical-setup.md`, `force-fixture.md`, calibration workflow.                       |
| HW-007    | Canonical reference                    | Datasheet               | Firmware / Hardware | `Documentation/hx711_english.pdf`                                                                                         | HX711 ADC datasheet                                                                             | FW-001, LSL-001            | Store under `docs/hardware/references/hx711/hx711_english.pdf`; link from firmware docs.                                    |
| OLD-001   | Deprecated                             | Old hardware            | Archive             | `Documentation/hx710b-ic-datasheet.pdf`                                                                                   | HX710B datasheet for older/non-current design                                                   | SYS-002                    | Remove from canonical; optionally archive under `docs/archive/deprecated/old-hx710b/`.                                      |
| OLD-002   | Deprecated                             | Old tutorial            | Archive             | `Documentation/Hacer bascula con Arduino y HX710B, balanza electronica o romana con HX710.pdf`                            | Old HX710B/Arduino scale tutorial                                                               | SYS-002                    | Remove from canonical; optionally archive with “not current system” banner.                                                 |
| OLD-003   | Deprecated                             | Old MCU datasheet       | Archive             | `Documentation/stm32f103xd_xe.pdf`                                                                                        | STM32F103 datasheet unrelated to current Arduino Nano + HX711 system                            | SYS-002                    | Remove from canonical; optionally archive with explicit deprecation.                                                        |
| COMM-001  | Relevant                               | Reference               | RS485 / Modbus      | `Documentation/Modbus_Protocol_Report.md`                                                                                 | RS485 vs Modbus explanation; Modbus RTU vs Active concept                                       | RS485-001, HW-001          | Rewrite into `docs/hardware/rs485-modbus-active-send.md`. Correct “Modbus Active” wording for this vendor board if needed.  |
| CAL-001   | Canonical design reference             | Reference / Config      | Calibration         | `Documentation/dual_device_calibration_configuration_report.md`                                                           | Recommended acquisition-board, target, synchronization, calibration settings                    | HW-001, CAL-002, CFG-001   | Promote content into `docs/workflows/handgrip-calibration.md` and `docs/configuration/acquisition-board-menu-reference.md`. |
| CAL-002   | Relevant but versioned/partially stale | Workflow                | Calibration         | `Documentation/handgrip_calibration_workflow_manual_v2.md`                                                                | Calibration workflow, D2 schema, troubleshooting, old command examples                          | CAL-003, FW-001            | Rewrite into v3 calibration workflow; remove stale old-protocol/default references.                                         |
| DOC-001   | Approved plan v0.1                     | Planning                | Documentation       | `Documentation/new_docs/documentation_refactor_specification.md` and `/mnt/data/documentation_refactor_specification.md`  | Original full documentation refactor plan; personas/pathways                                    | DOC-002                    | Archive under `docs/archive/documentation-plans/v0.1.md`.                                                                   |
| DOC-002   | Approved plan v0.2                     | Planning                | Documentation       | `/mnt/data/documentation_refactor_specification_updated.md`                                                               | Updated ZIP validation and revised plan                                                         | DOC-001                    | Archive under `docs/archive/documentation-plans/v0.2.md`.                                                                   |
| FW-001    | Relevant but stale                     | Entry / Workflow        | Firmware            | `Handgrip_Firmware/README.md`                                                                                             | PlatformIO setup, build/upload, config, serial monitor                                          | HW-007, LSL-001            | Update serial schema; convert into concise landing page; move detail into `Handgrip_Firmware/docs/`.                        |
| FW-002    | Canonical source                       | Implementation          | Firmware            | `Handgrip_Firmware/Core/Src/main.cpp`                                                                                     | HX711 readout, TimerOne acquisition, D2 serial emit                                             | FW-003, LSL-001            | Document in firmware architecture/protocol docs.                                                                            |
| FW-003    | Canonical source                       | Config                  | Firmware            | `Handgrip_Firmware/Core/Inc/config.h`                                                                                     | Sampling period, calibration mode, scale factor/offset, schema comment                          | FW-001                     | Create `Handgrip_Firmware/docs/configuration.md`.                                                                           |
| RS485-001 | Relevant                               | Entry / Architecture    | RS485 GUI           | `RS485_GUI/README.md`                                                                                                     | NiceGUI app purpose, Modbus RTU / Active-Send, ZMQ IPC, logging, architecture tree              | CFG-002, COMM-001          | Keep as landing page; expand component docs.                                                                                |
| CFG-002   | Canonical config                       | Config                  | RS485 GUI           | `RS485_GUI/config/config.yaml`                                                                                            | UI, logger, IPC, serial/transport, parsing, display downsampling                                | RS485-001, LSL-001         | Create `RS485_GUI/docs/configuration.md` and root `docs/configuration/rs485-gui.md`.                                        |
| LSL-001   | Relevant                               | Entry / Architecture    | LSL Bridge          | `LSL_Bridge/README.md`                                                                                                    | Target/reference stream names, config precedence, usage                                         | FW-001, RS485-001, CFG-003 | Keep landing page; move stream contracts to root architecture docs.                                                         |
| CFG-003   | Canonical config                       | Config                  | LSL Bridge          | `LSL_Bridge/conf/config.yaml`                                                                                             | Stream names, channel labels, timestamping, processing, CSV/logging                             | LSL-001                    | Create `LSL_Bridge/docs/configuration.md`.                                                                                  |
| VIEW-001  | Relevant                               | Entry / Workflow        | LSL Viewer          | `LSL_Viewer/README.md`                                                                                                    | Viewer v0.6 behavior, XY plot changes, modes                                                    | CFG-004, WF-004            | Keep landing page; add operator-focused viewer workflow.                                                                    |
| CFG-004   | Canonical config                       | Config                  | LSL Viewer          | `LSL_Viewer/conf/config.yaml`                                                                                             | Stream buffers, channel labels, viewer timings, XY correlation, style                           | VIEW-001                   | Create `LSL_Viewer/docs/configuration.md`.                                                                                  |
| CAL-003   | Relevant                               | Entry / Workflow        | Calibration         | `Handgrip_Calibration/README.md`                                                                                          | CLI workflow, protocol suite, primary v3 mention                                                | CFG-005, CAL-004           | Keep landing page; align CLI defaults/docs.                                                                                 |
| CFG-005   | Canonical config but needs path fix    | Config                  | Calibration         | `Handgrip_Calibration/conf/*.yaml`                                                                                        | Default workflow, protocol definitions, component config snapshot paths                         | CAL-003                    | Create `Handgrip_Calibration/docs/configuration.md`; fix paths.                                                             |
| CAL-004   | Example output                         | Generated output        | Calibration         | `Handgrip_Calibration/data/calibration/2026-05-13_055327_handgrip_cal/`                                                   | Example calibration report, plots, events, fitted outputs                                       | CAL-003                    | Move or copy to `docs/examples/calibration-session/` if useful; otherwise keep data/output separate.                        |
| ANA-001   | Relevant                               | Entry / Workflow        | Analysis            | `Handgrip_Analysis/README.md`                                                                                             | Analysis pipeline overview and commands                                                         | CFG-006, ANA-002           | Keep landing page; split stage docs into component docs.                                                                    |
| ANA-002   | Relevant                               | Reference               | Analysis            | `Handgrip_Analysis/README_filter_design_report.md`                                                                        | Filter design report / candidate strategy                                                       | ANA-001                    | Promote key parts to `Handgrip_Analysis/docs/filter-design.md`.                                                             |
| CFG-006   | Canonical config                       | Config                  | Analysis            | `Handgrip_Analysis/conf/**/*.yaml`                                                                                        | Stage config, DSP/filter candidates, IO, analysis policies                                      | ANA-001                    | Create `Handgrip_Analysis/docs/configuration.md`; optionally generated table.                                               |
| ANA-003   | Example output                         | Generated output        | Analysis            | `Handgrip_Analysis/data/analysis_results/**`                                                                              | Stage reports and figures from prior runs                                                       | ANA-001                    | Treat as examples/results, not maintained docs. Consider `docs/examples/analysis-output/`.                                  |
| DEV-001   | Relevant                               | Architecture            | Development         | `AGENT_PYTHON_GUIDELINES.md` and component source trees                                                                   | CLI/source-layout design principles, pure core/imperative shell ideas                           | SYS-001                    | Consolidate into `docs/development/python-project-structure-primer.md` and component development docs.                      |

---

# 6. Media and Reference Policy

## 6.1 Image policy

Images are not miscellaneous assets. They are evidence and operator aids.

Create:

```text
docs/hardware/assets/
├── README.md
├── rear-terminal-map_full-feature-selection.jpg
├── ac-input-sticker_close-up.jpg
├── front-panel_buttons_indicators.jpg
├── pm58-load-cell_label.jpg
├── pm58-certificate_wire-colors.jpg
├── rear-label_google-lens-translation.jpg
├── pm58_n_handgrip_setup.jpg
├── acq_board_n_pm58_n_handgrip_setup.jpg
└── force_application_setup.jpg
```

### Required image usage map

| Image                                          |            Status | Use in                                                                                                   | Purpose                                                             |
| ---------------------------------------------- | ----------------: | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `rear-terminal-map_full-feature-selection.jpg` |          Existing | `docs/workflows/physical-setup.md`, `docs/hardware/acquisition-board-reference.md`                       | Identify RS485, sensor, analog output, relay, AC power terminals.   |
| `ac-input-sticker_close-up.jpg`                |          Existing | `docs/workflows/physical-setup.md`                                                                       | Confirm AC100–240 V board power input and L/N labels.               |
| `front-panel_buttons_indicators.jpg`           |          Existing | `docs/hardware/acquisition-board-reference.md`, `docs/configuration/acquisition-board-menu-reference.md` | Explain display, keys, indicators, menu navigation.                 |
| `pm58-load-cell_label.jpg`                     |          Existing | `docs/hardware/pm58-wiring-and-bringup.md`                                                               | Identify PM58 model/range label.                                    |
| `pm58-certificate_wire-colors.jpg`             |          Existing | `docs/hardware/pm58-wiring-and-bringup.md`                                                               | Map PM58 wire colors and sensitivity.                               |
| `rear-label_google-lens-translation.jpg`       |          Existing | `docs/hardware/acquisition-board-reference.md`                                                           | Secondary visual confirmation of terminal labels.                   |
| `pm58_n_handgrip_setup.jpg`                    | Required incoming | `docs/hardware/force-fixture.md`, `docs/workflows/physical-setup.md`                                     | Show PM58 in series with handgrip.                                  |
| `acq_board_n_pm58_n_handgrip_setup.jpg`        | Required incoming | `docs/workflows/physical-setup.md`, `docs/workflows/full-live-viewer-quickstart.md`                      | Show PM58 + handgrip + acquisition-board connection.                |
| `force_application_setup.jpg`                  | Required incoming | `docs/hardware/force-fixture.md`, `docs/workflows/handgrip-calibration.md`                               | Show screw press controlled-force setup for calibration/validation. |

### Images to remove from canonical docs

The following current assets appear tied to older ADC/MCU exploration and should not be used in canonical docs unless a maintainer confirms they still describe current hardware:

```text
adc_module_to_arduino.jpeg
adc_part-number.jpeg
sensor_to_adc_module.jpeg
mcu_1.jpeg
mcu_2.jpeg
20260408_044544.jpg
20260421_105315.jpg
```

Recommended handling:

- **Canonical docs:** no references.
- **Archive:** optional under `docs/archive/deprecated/old-adv-mcu/assets/` with a clear banner.
- **Handoff package:** delete if the handoff package should contain only current-system docs.

## 6.2 PDF policy

### Keep as reference fallback

```text
docs/hardware/references/acquisition-board/
├── Sc36bd8ca2a714cf581ed5b70b722a27cW.pdf
├── Sc36bd8ca2a714cf581ed5b70b722a27cW_en.pdf
└── provider-offer-screencapture-2026-04-08.pdf

docs/hardware/references/hx711/
└── hx711_english.pdf
```

Rules:

- Do not rewrite the source PDFs.
- Do not make source PDFs the first reading path.
- Link to them only from reference docs.
- The readable canonical acquisition-board reference should be the reorganized Markdown manual, not the raw translated PDF.

### Remove from canonical documentation

```text
Documentation/Hacer bascula con Arduino y HX710B, balanza electronica o romana con HX710.pdf
Documentation/hx710b-ic-datasheet.pdf
Documentation/stm32f103xd_xe.pdf
```

Rules:

- No canonical doc should mention these unless explaining deprecated history.
- If retained, move to `docs/archive/deprecated/old-adv-mcu/` with an archive note:
  - “Not part of the current Handgrip Suite.”
  - “Do not use for current wiring, firmware, or calibration.”
  - “Preserved only for historical traceability.”

## 6.3 Markdown hardware reference policy

| Source doc                                                | v0.3 role                                                             | Target                                                                                                                                                      |
| --------------------------------------------------------- | --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `high_speed_acquisition_instrument_reorganized_manual.md` | Full acquisition-board reference fallback; keep content mostly intact | `docs/hardware/acquisition-board-reference.md`                                                                                                              |
| `pm58_acquisition_board_manual.md`                        | PM58 + acquisition-board wiring/operator guide; improve organization  | `docs/hardware/pm58-wiring-and-bringup.md`                                                                                                                  |
| `Modbus_Protocol_Report.md`                               | Conceptual RS485/Modbus background; convert to project-specific doc   | `docs/hardware/rs485-modbus-active-send.md`                                                                                                                 |
| `dual_device_calibration_configuration_report.md`         | Calibration configuration rationale                                   | Split into `docs/configuration/acquisition-board-menu-reference.md`, `docs/workflows/handgrip-calibration.md`, and `Handgrip_Calibration/docs/protocols.md` |

---

# 7. Proposed Final Directory Tree

## 7.1 Root-level final structure

```text
handgrip-suite/
├── README.md
├── pyproject.toml
├── platformio.ini
├── docs/
│   ├── index.md
│   ├── start-here.md
│   ├── system-overview.md
│   ├── architecture/
│   │   ├── index.md
│   │   ├── dataflow.md
│   │   ├── repository-layout.md
│   │   ├── runtime-processes.md
│   │   ├── stream-contracts.md
│   │   ├── timestamping-and-synchronization.md
│   │   └── data-and-output-lifecycle.md
│   ├── workflows/
│   │   ├── index.md
│   │   ├── physical-setup.md
│   │   ├── firmware-setup.md
│   │   ├── target-only-quickstart.md
│   │   ├── reference-only-quickstart.md
│   │   ├── full-live-viewer-quickstart.md
│   │   ├── handgrip-calibration.md
│   │   ├── handgrip-analysis.md
│   │   └── daily-operator-checklist.md
│   ├── hardware/
│   │   ├── index.md
│   │   ├── acquisition-board-reference.md
│   │   ├── acquisition-board-menu-reference.md
│   │   ├── pm58-wiring-and-bringup.md
│   │   ├── force-fixture.md
│   │   ├── rs485-modbus-active-send.md
│   │   ├── hx711-reference.md
│   │   ├── assets/
│   │   │   ├── README.md
│   │   │   ├── rear-terminal-map_full-feature-selection.jpg
│   │   │   ├── ac-input-sticker_close-up.jpg
│   │   │   ├── front-panel_buttons_indicators.jpg
│   │   │   ├── pm58-load-cell_label.jpg
│   │   │   ├── pm58-certificate_wire-colors.jpg
│   │   │   ├── rear-label_google-lens-translation.jpg
│   │   │   ├── pm58_n_handgrip_setup.jpg
│   │   │   ├── acq_board_n_pm58_n_handgrip_setup.jpg
│   │   │   └── force_application_setup.jpg
│   │   └── references/
│   │       ├── index.md
│   │       ├── acquisition-board/
│   │       │   ├── Sc36bd8ca2a714cf581ed5b70b722a27cW.pdf
│   │       │   ├── Sc36bd8ca2a714cf581ed5b70b722a27cW_en.pdf
│   │       │   └── provider-offer-screencapture-2026-04-08.pdf
│   │       └── hx711/
│   │           └── hx711_english.pdf
│   ├── configuration/
│   │   ├── index.md
│   │   ├── acquisition-board-menu-reference.md
│   │   ├── firmware.md
│   │   ├── rs485-gui.md
│   │   ├── lsl-bridge.md
│   │   ├── lsl-viewer.md
│   │   ├── handgrip-calibration.md
│   │   └── handgrip-analysis.md
│   ├── development/
│   │   ├── index.md
│   │   ├── workspace-setup.md
│   │   ├── python-project-structure-primer.md
│   │   ├── configuration-system-primer.md
│   │   ├── adding-a-new-protocol.md
│   │   ├── adding-a-new-stream-channel.md
│   │   ├── adding-a-new-calibration-model.md
│   │   └── testing-and-validation.md
│   ├── troubleshooting/
│   │   ├── index.md
│   │   ├── hardware-and-wiring.md
│   │   ├── serial-and-rs485.md
│   │   ├── lsl-streams.md
│   │   ├── viewer-lag-or-xy-delay.md
│   │   ├── calibration-recording.md
│   │   └── analysis-pipeline.md
│   ├── examples/
│   │   ├── index.md
│   │   ├── calibration-session/
│   │   │   ├── README.md
│   │   │   └── selected-report-excerpts.md
│   │   └── analysis-output/
│   │       ├── README.md
│   │       └── stage6-report-excerpts.md
│   ├── contributing/
│   │   ├── index.md
│   │   ├── documentation-style.md
│   │   ├── report-writing-style.md
│   │   └── documentation-maintenance-checklist.md
│   └── archive/
│       ├── index.md
│       ├── documentation-plans/
│       │   ├── v0.1.md
│       │   ├── v0.2.md
│       │   └── v0.3.md
│       ├── historical-notes/
│       │   └── Binnacle.md
│       └── deprecated/
│           └── old-adv-mcu/
│               ├── README.md
│               ├── hx710b-ic-datasheet.pdf
│               ├── Hacer bascula con Arduino y HX710B, balanza electronica o romana con HX710.pdf
│               └── stm32f103xd_xe.pdf
├── Handgrip_Firmware/
│   ├── README.md
│   ├── docs/
│   │   ├── index.md
│   │   ├── build-and-upload.md
│   │   ├── serial-protocol.md
│   │   ├── configuration.md
│   │   ├── architecture.md
│   │   └── troubleshooting.md
│   └── Core/
├── RS485_GUI/
│   ├── README.md
│   ├── docs/
│   │   ├── index.md
│   │   ├── quickstart.md
│   │   ├── configuration.md
│   │   ├── active-send-and-modbus.md
│   │   ├── ipc-schema.md
│   │   ├── logging-and-outputs.md
│   │   ├── architecture.md
│   │   └── development.md
│   └── src/
├── LSL_Bridge/
│   ├── README.md
│   ├── docs/
│   │   ├── index.md
│   │   ├── quickstart.md
│   │   ├── configuration.md
│   │   ├── stream-contracts.md
│   │   ├── timestamping.md
│   │   ├── architecture.md
│   │   └── development.md
│   └── src/
├── LSL_Viewer/
│   ├── README.md
│   ├── docs/
│   │   ├── index.md
│   │   ├── quickstart.md
│   │   ├── configuration.md
│   │   ├── xy-correlation.md
│   │   ├── live-csv-xdf-modes.md
│   │   ├── architecture.md
│   │   └── development.md
│   └── src/
├── Handgrip_Calibration/
│   ├── README.md
│   ├── docs/
│   │   ├── index.md
│   │   ├── quickstart.md
│   │   ├── protocols.md
│   │   ├── configuration.md
│   │   ├── recording.md
│   │   ├── fitting-and-model-selection.md
│   │   ├── reports-and-outputs.md
│   │   ├── applying-calibration-results.md
│   │   ├── architecture.md
│   │   └── development.md
│   └── src/
└── Handgrip_Analysis/
    ├── README.md
    ├── docs/
    │   ├── index.md
    │   ├── quickstart.md
    │   ├── stages.md
    │   ├── configuration.md
    │   ├── filter-design.md
    │   ├── reports-and-outputs.md
    │   ├── architecture.md
    │   └── development.md
    └── src/
```

## 7.2 What belongs at root vs component level

| Content                           | Root docs             | Component docs                                  |
| --------------------------------- | --------------------- | ----------------------------------------------- |
| “What is this system?”            | Yes                   | No                                              |
| Physical wiring and force fixture | Yes                   | Link only from components                       |
| End-to-end workflow               | Yes                   | Component steps linked from root workflow       |
| Stream contracts across apps      | Yes                   | Component-specific implementation details       |
| Configuration overview            | Yes                   | Full parameter-by-parameter component reference |
| Hardware manuals/PDF references   | Yes                   | Link only where relevant                        |
| How to run one module             | Summary only          | Yes                                             |
| How to edit one module            | Link only             | Yes                                             |
| Test strategy for one module      | Summary only          | Yes                                             |
| Generated example outputs         | Curated examples only | Link to examples/results                        |

---

# 8. Mapping From Inventory to New Locations

| Inventory IDs             | New canonical location                                                                                                                       | Action                                                                                  |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| SYS-001                   | `README.md`, `docs/development/workspace-setup.md`                                                                                           | Explain workspace install/test commands and editable local packages.                    |
| STYLE-001                 | `docs/contributing/report-writing-style.md`                                                                                                  | Copy/adapt the report writing guide into repo docs.                                     |
| HW-001                    | `docs/hardware/acquisition-board-reference.md`                                                                                               | Promote as the readable full reference. Keep broad config coverage.                     |
| HW-002, HW-003            | `docs/hardware/references/acquisition-board/`                                                                                                | Rename for clarity, keep as fallback PDFs.                                              |
| HW-004                    | `docs/hardware/references/acquisition-board/provider-offer-screencapture-2026-04-08.pdf`                                                     | Keep as procurement/vendor fallback only.                                               |
| HW-005                    | `docs/hardware/pm58-wiring-and-bringup.md`                                                                                                   | Rewrite for readability/reproducibility; link images inline.                            |
| HW-006, IMG-001           | `docs/hardware/assets/` + `docs/hardware/assets/README.md`                                                                                   | Migrate/copy useful photos; add missing incoming setup images; document use.            |
| HW-007                    | `docs/hardware/references/hx711/hx711_english.pdf`, `docs/hardware/hx711-reference.md`, `Handgrip_Firmware/docs/architecture.md`             | Keep datasheet and summarize relevant behavior.                                         |
| OLD-001, OLD-002, OLD-003 | `docs/archive/deprecated/old-adv-mcu/` or remove from package                                                                                | Remove from canonical docs. If archived, add warning banner.                            |
| COMM-001                  | `docs/hardware/rs485-modbus-active-send.md`, `RS485_GUI/docs/active-send-and-modbus.md`                                                      | Convert to project-specific communication explanation.                                  |
| CAL-001                   | `docs/workflows/handgrip-calibration.md`, `docs/configuration/acquisition-board-menu-reference.md`, `Handgrip_Calibration/docs/protocols.md` | Split recommendations into operator workflow and config reference.                      |
| CAL-002                   | `docs/workflows/handgrip-calibration.md`, `Handgrip_Calibration/docs/recording.md`, `Handgrip_Calibration/docs/troubleshooting.md`           | Rewrite around v3 protocol; remove stale examples.                                      |
| DOC-001, DOC-002          | `docs/archive/documentation-plans/`                                                                                                          | Preserve as approved history; v0.3 becomes current plan.                                |
| FW-001                    | `Handgrip_Firmware/README.md`, `Handgrip_Firmware/docs/*`                                                                                    | Update README schema; split build/protocol/config details.                              |
| FW-002, FW-003            | `Handgrip_Firmware/docs/serial-protocol.md`, `Handgrip_Firmware/docs/configuration.md`, `docs/architecture/stream-contracts.md`              | Document exact protocol and firmware config.                                            |
| RS485-001, CFG-002        | `RS485_GUI/README.md`, `RS485_GUI/docs/*`, `docs/configuration/rs485-gui.md`                                                                 | Split quickstart/config/IPС/logging details.                                            |
| LSL-001, CFG-003          | `LSL_Bridge/README.md`, `LSL_Bridge/docs/*`, `docs/architecture/stream-contracts.md`                                                         | Keep stream contract canonical.                                                         |
| VIEW-001, CFG-004         | `LSL_Viewer/README.md`, `LSL_Viewer/docs/*`                                                                                                  | Document live/replay/XY modes and config.                                               |
| CAL-003, CFG-005          | `Handgrip_Calibration/README.md`, `Handgrip_Calibration/docs/*`                                                                              | Canonicalize v3 and path fixes.                                                         |
| CAL-004                   | `docs/examples/calibration-session/`                                                                                                         | Curate only a small representative subset; avoid dumping raw session outputs into docs. |
| ANA-001, ANA-002, CFG-006 | `Handgrip_Analysis/README.md`, `Handgrip_Analysis/docs/*`                                                                                    | Split stage docs, filter design, config, outputs.                                       |
| ANA-003                   | `docs/examples/analysis-output/` or remain under `data/analysis_results/`                                                                    | Treat as generated output, not maintained docs.                                         |
| DEV-001                   | `docs/development/python-project-structure-primer.md`, component `docs/development.md`                                                       | Translate architecture concepts for research-python maintainers.                        |

---

# 9. Documentation Gaps That Break the Pathway

## Gap G-001 — Root entry point is missing

### What

No root `README.md` exists, despite root `pyproject.toml` referencing it.

### Impact

A new reader has no canonical first page. The handoff recipient is forced to infer the system from component READMEs and legacy docs.

### Fix

Create `README.md` with:

- one-screen summary,
- audience routes,
- system diagram,
- fastest safe quickstart,
- workflow map,
- component table,
- link to `docs/index.md`,
- current known issues.

## Gap G-002 — Root `docs/` is missing

### What

Current detailed docs live under legacy `Documentation/`, which mixes manuals, generated plans, PDFs, historical reports, images, and deprecated material.

### Impact

The documentation does not form a clean traversal tree.

### Fix

Create root `docs/` and migrate content by purpose:

- canonical docs,
- references,
- examples,
- archive/deprecated.

## Gap G-003 — Component `docs/` folders are missing

### What

Each component has a README but not a structured docs folder.

### Impact

READMEs either become too long or omit necessary detail.

### Fix

Each component gets:

```text
README.md
/docs/index.md
/docs/quickstart.md
/docs/configuration.md
/docs/architecture.md
/docs/development.md
```

plus component-specific docs.

## Gap G-004 — Image assets are not integrated into a visual workflow

### What

`Documentation/assets/` contains useful hardware photos, but docs do not have a canonical asset map. The new force-fixture images are requested but not present in the corrected ZIP.

### Impact

Operators may wire or stage hardware incorrectly, especially under handoff conditions.

### Fix

- Add `docs/hardware/assets/README.md`.
- Use images inline in physical setup, PM58 wiring, acquisition-board reference, and force-fixture docs.
- Add the three new setup images with stable filenames.

## Gap G-005 — PDF/source-reference status is unclear

### What

Raw manuals, translated manuals, vendor screencapture, datasheets, old HX710B docs, and old MCU docs are mixed together.

### Impact

A novice may treat outdated documents as current source of truth.

### Fix

Classify PDFs:

- **Reference fallback:** acquisition board, translated manual, provider offer, HX711 datasheet.
- **Deprecated/remove from canonical:** HX710B, old Arduino tutorial, STM32F103 datasheet.

## Gap G-006 — Firmware README documents stale serial schema

### What

Firmware source emits `D2`, but README still documents legacy `D,<seq>,<timestamp_us>,<value_gr>`.

### Impact

A maintainer may edit parser/bridge/calibration logic against the wrong schema.

### Fix

Update README and create `Handgrip_Firmware/docs/serial-protocol.md`.

## Gap G-007 — Calibration protocol default is inconsistent

### What

`Handgrip_Calibration/README.md` identifies `protocol_static_reversible_staircase_v3.yaml` as primary; CLI default and older workflow docs still use `protocol_static_staircase.yaml`.

### Impact

Operators can run the wrong protocol by default.

### Fix

Choose one:

- **Recommended:** make CLI default v3 and update docs.
- **Alternative:** keep CLI default old for compatibility but make every operator doc explicitly require `--config conf/protocol_static_reversible_staircase_v3.yaml`.

## Gap G-008 — Calibration component-config snapshot path is wrong/brittle

### What

Calibration configs reference `../RS485_GUI/config.yaml`, but actual file is `RS485_GUI/config/config.yaml`.

### Impact

Session config snapshots may miss or fail to copy the RS485 GUI config, hurting reproducibility.

### Fix

Update all `component_configs` paths and add validation checks.

## Gap G-009 — Configuration values are not fully documented

### What

Each config file has many operational parameters but no complete stable reference.

### Impact

Students can edit configs without knowing impact/range/failure modes.

### Fix

Create one config reference per component plus root config overview.

## Gap G-010 — Source-layout architecture is not explained to the target audience

### What

The repo uses industry-style Python package structures, editable installs, and decoupled layers. The intended handoff recipient may not be familiar with these conventions.

### Impact

A capable Python user may edit the wrong file, run from the wrong working directory, or misunderstand import/package behavior.

### Fix

Add `docs/development/python-project-structure-primer.md` and component development maps.

## Gap G-011 — Generated outputs are mixed with docs/source

### What

Analysis and calibration output reports are valuable examples but are not maintained documentation.

### Impact

Readers may confuse historical output with current instructions.

### Fix

Move curated excerpts to `docs/examples/`; keep raw outputs under data/output folders or archive.

---

# 10. Detailed Execution Plan

## Phase 0 — Prepare documentation branch and freeze source-of-truth decisions

### Step 0.1 — Create branch

- **Do:** Create a documentation refactor branch.
- **Command:**

```bash
git checkout -b docs/refactor-v0.3
```

- **Expected result:** All documentation changes are isolated.
- **Failure signal:** Existing uncommitted changes block checkout.
- **Next branch:** Commit/stash existing changes before continuing.

### Step 0.2 — Add v0.3 specification to archive

- **Do:** Save this plan as:

```text
docs/archive/documentation-plans/v0.3.md
```

- **Expected result:** Future maintainers can see why docs were reorganized.
- **Failure signal:** `docs/` does not exist yet.
- **Next branch:** Create skeleton first, then copy plan.

### Step 0.3 — Decide deprecated-source handling

- **Do:** Choose whether old HX710B/ADV/MCU PDFs are deleted from the handoff package or archived under `docs/archive/deprecated/old-adv-mcu/`.
- **Recommended default:** Archive with explicit warning if traceability matters; otherwise remove from deliverable.
- **Expected result:** No canonical docs link to outdated sources.

## Phase 1 — Create the documentation skeleton

### Step 1.1 — Create root docs folders

```bash
mkdir -p docs/{architecture,workflows,hardware/assets,hardware/references/acquisition-board,hardware/references/hx711,configuration,development,troubleshooting,examples/calibration-session,examples/analysis-output,contributing,archive/documentation-plans,archive/historical-notes,archive/deprecated/old-adv-mcu}
```

### Step 1.2 — Create component docs folders

```bash
for d in Handgrip_Firmware RS485_GUI LSL_Bridge LSL_Viewer Handgrip_Calibration Handgrip_Analysis; do
  mkdir -p "$d/docs"
done
```

### Step 1.3 — Add `index.md` files

- **Do:** Create `docs/index.md` and each component `docs/index.md`.
- **Expected result:** Every docs folder is navigable.
- **Minimum content:** purpose, who should read it, links to workflows/config/implementation.

## Phase 2 — Root entrypoint and reader pathway

### Step 2.1 — Create root `README.md`

Required structure:

```markdown
# Handgrip Suite

## Summary

## Who should read what

| I am... | Start here | Then read |
| ------- | ---------- | --------- |

## System at a glance

## Fastest safe quickstart

## Main workflows

## Components

## Installation and validation

## Documentation map

## Current known issues
```

### Step 2.2 — Create `docs/start-here.md`

- **Goal:** Friendly first conceptual page.
- **Must answer:**
  - What is the suite?
  - What hardware is involved?
  - Which app do I open first?
  - What is calibration vs analysis?
  - Which path should I follow?

### Step 2.3 — Create `docs/system-overview.md`

- **Goal:** One document that explains the system architecture without diving into code.
- **Must include:**
  - physical chain,
  - software processes,
  - stream/data contracts,
  - output locations,
  - where configs live,
  - “canonical vs archive” note.

## Phase 3 — Hardware, images, and PDFs

### Step 3.1 — Migrate useful images

- **Do:** Copy useful current images:

```bash
cp Documentation/assets/rear-terminal-map_full-feature-selection.jpg docs/hardware/assets/
cp Documentation/assets/ac-input-sticker_close-up.jpg docs/hardware/assets/
cp Documentation/assets/front-panel_buttons_indicators.jpg docs/hardware/assets/
cp Documentation/assets/pm58-load-cell_label.jpg docs/hardware/assets/
cp Documentation/assets/pm58-certificate_wire-colors.jpg docs/hardware/assets/
cp Documentation/assets/rear-label_google-lens-translation.jpg docs/hardware/assets/
```

- **Then add missing requested files:**

```text
docs/hardware/assets/pm58_n_handgrip_setup.jpg
docs/hardware/assets/acq_board_n_pm58_n_handgrip_setup.jpg
docs/hardware/assets/force_application_setup.jpg
```

- **Expected result:** Hardware docs can be illustrated from canonical asset paths.
- **Failure signal:** New setup images missing.
- **Next branch:** Add placeholders in docs with `TODO: add image` until the files are committed.

### Step 3.2 — Create image asset map

Create `docs/hardware/assets/README.md` with:

```markdown
# Hardware Image Asset Map

| File | Shows | Used in | Notes |
| ---- | ----- | ------- | ----- |
```

### Step 3.3 — Migrate PDFs

```bash
cp Documentation/Sc36bd8ca2a714cf581ed5b70b722a27cW.pdf docs/hardware/references/acquisition-board/
cp Documentation/Sc36bd8ca2a714cf581ed5b70b722a27cW_en.pdf docs/hardware/references/acquisition-board/
cp Documentation/screencapture-es-aliexpress-data-acquisition-device-item-1005009874603061-html-2026-04-08-04_30_50.pdf docs/hardware/references/acquisition-board/provider-offer-screencapture-2026-04-08.pdf
cp Documentation/hx711_english.pdf docs/hardware/references/hx711/
```

### Step 3.4 — Archive or remove outdated PDFs

Option A — archive:

```bash
mv Documentation/hx710b-ic-datasheet.pdf docs/archive/deprecated/old-adv-mcu/
mv "Documentation/Hacer bascula con Arduino y HX710B, balanza electronica o romana con HX710.pdf" docs/archive/deprecated/old-adv-mcu/
mv Documentation/stm32f103xd_xe.pdf docs/archive/deprecated/old-adv-mcu/
```

Option B — remove from handoff package:

```bash
git rm Documentation/hx710b-ic-datasheet.pdf
git rm "Documentation/Hacer bascula con Arduino y HX710B, balanza electronica o romana con HX710.pdf"
git rm Documentation/stm32f103xd_xe.pdf
```

### Step 3.5 — Promote hardware Markdown docs

- **From:** `Documentation/high_speed_acquisition_instrument_reorganized_manual.md`
- **To:** `docs/hardware/acquisition-board-reference.md`
- **Handling:** Keep mostly intact; add frontmatter/status block; update image links.

- **From:** `Documentation/pm58_acquisition_board_manual.md`
- **To:** `docs/hardware/pm58-wiring-and-bringup.md`
- **Handling:** Improve organization for readability/reproducibility; include validation steps; link PM58 and wiring photos.

### Step 3.6 — Create force fixture doc

Create `docs/hardware/force-fixture.md`.

Required sections:

```markdown
# PM58 + Handgrip Force Application Fixture

## Summary
## Safety and mechanical assumptions
## Fixture stages
### Stage 1 — PM58 in series with handgrip
### Stage 2 — PM58 + handgrip connected to acquisition board
### Stage 3 — Screw press controlled-force setup
## What each image proves
## How to validate force path before calibration
## Common mistakes
```

Use:

- `pm58_n_handgrip_setup.jpg`
- `acq_board_n_pm58_n_handgrip_setup.jpg`
- `force_application_setup.jpg`

## Phase 4 — Fix handoff-blocking inconsistencies

### Step 4.1 — Fix firmware README schema

- **Do:** Replace stale references:

```text
D,<seq>,<timestamp_us>,<value_gr>
```

with:

```text
D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>
```

- **Also document:**
  - `seq`: sample sequence number,
  - `timestamp_us`: device timestamp in microseconds,
  - `raw_count`: HX711 raw ADC count,
  - `current_units`: current scaled force/value according to firmware calibration,
  - `status`: bitfield/status.

### Step 4.2 — Create firmware protocol doc

Create `Handgrip_Firmware/docs/serial-protocol.md` and link it from:

- `Handgrip_Firmware/README.md`,
- `LSL_Bridge/docs/stream-contracts.md`,
- `docs/architecture/stream-contracts.md`.

### Step 4.3 — Fix calibration config snapshot paths

Update every calibration config that currently contains:

```yaml
- ../RS485_GUI/config.yaml
```

to:

```yaml
- ../RS485_GUI/config/config.yaml
```

Files to update:

```text
Handgrip_Calibration/conf/config.yaml
Handgrip_Calibration/conf/default.yaml
Handgrip_Calibration/conf/template.yaml
Handgrip_Calibration/conf/protocol_creep_zero_return.yaml
Handgrip_Calibration/conf/protocol_dynamic_validation.yaml
Handgrip_Calibration/conf/protocol_holdout_verification.yaml
Handgrip_Calibration/conf/protocol_low_force_refinement.yaml
Handgrip_Calibration/conf/protocol_reference_verification.yaml
Handgrip_Calibration/conf/protocol_static_reversible_staircase_v3.yaml
Handgrip_Calibration/conf/protocol_static_staircase.yaml
```

### Step 4.4 — Canonicalize calibration protocol default

Recommended source change:

- Change CLI default in `Handgrip_Calibration/src/handgrip_calibration/cli.py` from:

```text
conf/protocol_static_staircase.yaml
```

to:

```text
conf/protocol_static_reversible_staircase_v3.yaml
```

- Update CLI help examples.
- Mark `protocol_static_staircase.yaml` as legacy/basic baseline in docs.

If you do not want to change source behavior yet, then operator docs must always show explicit `--config conf/protocol_static_reversible_staircase_v3.yaml`.

## Phase 5 — Root architecture and workflow docs

### Step 5.1 — Create architecture docs

Create:

- `docs/architecture/dataflow.md`
- `docs/architecture/repository-layout.md`
- `docs/architecture/runtime-processes.md`
- `docs/architecture/stream-contracts.md`
- `docs/architecture/timestamping-and-synchronization.md`
- `docs/architecture/data-and-output-lifecycle.md`

Minimum required contracts in `stream-contracts.md`:

| Stream / channel          | Source                          | Consumer            | Notes                                   |
| ------------------------- | ------------------------------- | ------------------- | --------------------------------------- |
| `HandgripTarget`          | `LSL_Bridge` from firmware UART | Viewer, calibration | D2 payload derived.                     |
| `HandgripReference`       | `LSL_Bridge` from RS485 GUI IPC | Viewer, calibration | Reference force from acquisition board. |
| `HandgripComponentEvents` | `LSL_Bridge`                    | Diagnostics         | Connect/disconnect/gap markers.         |
| `rs485.measurement.v1`    | `RS485_GUI`                     | `LSL_Bridge`        | ZMQ IPC topic.                          |

### Step 5.2 — Create physical setup workflow

Create `docs/workflows/physical-setup.md`.

Required flow:

1. Identify hardware.
2. Wire PM58 to acquisition board.
3. Wire target handgrip / Arduino / HX711.
4. Wire RS485 adapter.
5. Apply power safely.
6. Validate acquisition-board display.
7. Validate host serial ports.
8. Validate force path with screw press.

### Step 5.3 — Create firmware setup workflow

Create `docs/workflows/firmware-setup.md`.

Required flow:

1. Install VS Code.
2. Install PlatformIO extension.
3. Open repo root, not only firmware subfolder.
4. Confirm `platformio.ini` and old Nano bootloader environment.
5. Build.
6. Upload.
7. Open serial monitor.
8. Verify D2 lines.

### Step 5.4 — Create quickstart workflows

Create:

- `docs/workflows/target-only-quickstart.md`
- `docs/workflows/reference-only-quickstart.md`
- `docs/workflows/full-live-viewer-quickstart.md`

Each workflow must include:

```markdown
## Summary
## Prerequisites
## Commands
## Expected result
## Where outputs/logs appear
## Stop conditions
## Troubleshooting links
```

### Step 5.5 — Create calibration workflow

Create `docs/workflows/handgrip-calibration.md`.

Must include:

1. physical setup with force fixture image links,
2. preflight,
3. recording,
4. where captured data appears,
5. fitting,
6. report generation,
7. how to interpret model comparison,
8. which fitted values to use,
9. where to put/apply calibration values,
10. validation after applying calibration.

Canonical command set:

```bash
uv sync
uv run handgrip-cal preflight --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal record --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal fit data/calibration/<session_id> --config conf/protocol_static_reversible_staircase_v3.yaml
uv run handgrip-cal report data/calibration/<session_id> --config conf/protocol_static_reversible_staircase_v3.yaml
```

Adjust if project-level invocation differs after validation.

### Step 5.6 — Create analysis workflow

Create `docs/workflows/handgrip-analysis.md`.

Must include:

1. required input data organization,
2. manifest requirements,
3. stage list,
4. commands to run all vs single stages,
5. output locations,
6. interpretation of Stage 6 filter design outputs,
7. what to do with selected filter recommendations.

## Phase 6 — Component documentation

### Step 6.1 — Refactor component READMEs

Each component README should become a landing page, not a full manual.

Template:

```markdown
# <Component Name>

## Summary

## When to use this component

## First command

## Expected result

## Configuration

## Common workflows

## Repository layout

## Tests

## Further docs
```

### Step 6.2 — Create `Handgrip_Firmware/docs/`

Required files:

| File                  | Must cover                                                            |
| --------------------- | --------------------------------------------------------------------- |
| `index.md`            | Firmware docs map.                                                    |
| `build-and-upload.md` | PlatformIO extension, root-open requirement, build/upload/monitor.    |
| `serial-protocol.md`  | D2 schema, field meanings, examples, parser contract.                 |
| `configuration.md`    | `config.h`, sampling, calibration mode, scale factor, offset.         |
| `architecture.md`     | TimerOne acquisition, FIFO, serial output, HX711 dependency.          |
| `troubleshooting.md`  | Upload errors, old bootloader, serial port permissions, no D2 output. |

### Step 6.3 — Create `RS485_GUI/docs/`

Required files:

| File                        | Must cover                                             |
| --------------------------- | ------------------------------------------------------ |
| `index.md`                  | Component docs map.                                    |
| `quickstart.md`             | Run GUI, connect board, expected UI/log output.        |
| `configuration.md`          | Full `config/config.yaml` reference.                   |
| `active-send-and-modbus.md` | Modbus RTU vs Active-Send in this board/app.           |
| `ipc-schema.md`             | ZMQ topics, payload aliases, session IDs.              |
| `logging-and-outputs.md`    | NDJSON/CSV/event logs and retention.                   |
| `architecture.md`           | Core/transport/io/ui/config layers.                    |
| `development.md`            | How to add parser fields, UI controls, logger outputs. |

### Step 6.4 — Create `LSL_Bridge/docs/`

Required files:

| File                  | Must cover                                               |
| --------------------- | -------------------------------------------------------- |
| `index.md`            | Component docs map.                                      |
| `quickstart.md`       | Start bridge, override serial port, expected streams.    |
| `configuration.md`    | Full `conf/config.yaml` reference.                       |
| `stream-contracts.md` | Target/reference/event stream schemas.                   |
| `timestamping.md`     | Host receive vs device clock anchor, drift and gaps.     |
| `architecture.md`     | Serial input, IPC input, outlets, CSV, processing.       |
| `development.md`      | Add channel, change parser, add processing stage safely. |

### Step 6.5 — Create `LSL_Viewer/docs/`

Required files:

| File                    | Must cover                                               |
| ----------------------- | -------------------------------------------------------- |
| `index.md`              | Component docs map.                                      |
| `quickstart.md`         | Live viewer run, expected plots.                         |
| `configuration.md`      | Full viewer config reference.                            |
| `xy-correlation.md`     | XY plot behavior, alignment policy, lag troubleshooting. |
| `live-csv-xdf-modes.md` | Live vs replay modes.                                    |
| `architecture.md`       | Stream buffers, UI refresh, plotting model.              |
| `development.md`        | Add plots/signals/toggles.                               |

### Step 6.6 — Create `Handgrip_Calibration/docs/`

Required files:

| File                              | Must cover                                           |
| --------------------------------- | ---------------------------------------------------- |
| `index.md`                        | Component docs map.                                  |
| `quickstart.md`                   | Operator workflow.                                   |
| `protocols.md`                    | Protocol suite; v3 primary; legacy labels.           |
| `configuration.md`                | Full config/protocol YAML reference.                 |
| `recording.md`                    | LSL inputs, captured files, session IDs.             |
| `fitting-and-model-selection.md`  | Model alternatives, metrics, likelihoods, residuals. |
| `reports-and-outputs.md`          | Report files, plots, tables.                         |
| `applying-calibration-results.md` | Which values to use and where.                       |
| `architecture.md`                 | CLI → preflight/record/fit/report modules.           |
| `development.md`                  | Add protocol/model/report section.                   |

### Step 6.7 — Create `Handgrip_Analysis/docs/`

Required files:

| File                     | Must cover                                           |
| ------------------------ | ---------------------------------------------------- |
| `index.md`               | Component docs map.                                  |
| `quickstart.md`          | Run all stages and individual stages.                |
| `stages.md`              | Stage 1–6 purpose/input/output.                      |
| `configuration.md`       | Full config tree reference.                          |
| `filter-design.md`       | Candidate review/design workflow and interpretation. |
| `reports-and-outputs.md` | Output tree, figures, reports.                       |
| `architecture.md`        | CLI/stages/config/io/report layers.                  |
| `development.md`         | Add stage, metric, filter family, report section.    |

## Phase 7 — Configuration references

### Step 7.1 — Create root config index

Create `docs/configuration/index.md` with a table:

| Component | Config path | Main purpose | Detailed reference |
| --------- | ----------- | ------------ | ------------------ |

### Step 7.2 — Create per-component config docs

Each config reference must use this table format:

| Key | Type | Default | Allowed range / values | Operational impact | When to change | Failure risk |
| --- | ---- | ------- | ---------------------- | ------------------ | -------------- | ------------ |

### Step 7.3 — Add acquisition-board menu reference

`docs/configuration/acquisition-board-menu-reference.md` must include:

- menu code,
- display label,
- default,
- recommended calibration value,
- range,
- effect,
- risk,
- source reference.

Base it on:

- `high_speed_acquisition_instrument_reorganized_manual.md`,
- `dual_device_calibration_configuration_report.md`,
- acquisition-board PDFs as fallback.

## Phase 8 — Examples and generated outputs

### Step 8.1 — Curate calibration example

- **Do:** Create `docs/examples/calibration-session/README.md`.
- **Use:** only selected excerpts from the existing session.
- **Avoid:** copying all generated plots/reports unless they are intentionally curated.

### Step 8.2 — Curate analysis example

- **Do:** Create `docs/examples/analysis-output/README.md`.
- **Use:** selected Stage 6 examples showing how to interpret filter design.

### Step 8.3 — Mark generated folders

Add README/status files to generated output directories where retained:

```markdown
# Generated Output Directory

This directory contains outputs produced by prior runs. It is not canonical documentation.
```

## Phase 9 — Development and extension docs

### Step 9.1 — Python project structure primer

Create `docs/development/python-project-structure-primer.md`.

Must explain:

- repo root vs component root,
- `src/` layout,
- editable installs,
- `pyproject.toml`,
- entry points,
- tests,
- configs,
- why not edit installed site-packages,
- how to run from repo root.

### Step 9.2 — Configuration-system primer

Create `docs/development/configuration-system-primer.md`.

Must explain:

- Hydra/OmegaConf dotlist overrides,
- config precedence,
- component-local configs,
- protocol configs,
- how to change safely,
- how to capture configs for reproducibility.

### Step 9.3 — Extension recipes

Create:

- `docs/development/adding-a-new-stream-channel.md`
- `docs/development/adding-a-new-protocol.md`
- `docs/development/adding-a-new-calibration-model.md`

Each recipe must include:

```markdown
## Summary
## Files to edit
## Data contracts affected
## Tests to update
## Validation workflow
## Common failure modes
```

## Phase 10 — Troubleshooting docs

Create symptom-first docs:

| File                                             | Symptoms                                                             |
| ------------------------------------------------ | -------------------------------------------------------------------- |
| `docs/troubleshooting/hardware-and-wiring.md`    | No board display, wrong load sign, unstable reading, overload.       |
| `docs/troubleshooting/serial-and-rs485.md`       | No serial port, wrong A/B, baud mismatch, no Active-Send frames.     |
| `docs/troubleshooting/lsl-streams.md`            | Streams not visible, wrong names, stale outlets.                     |
| `docs/troubleshooting/viewer-lag-or-xy-delay.md` | XY delay, reference lag, display-only shift vs real timestamp issue. |
| `docs/troubleshooting/calibration-recording.md`  | Missing target/reference CSV, failed preflight, bad session ID.      |
| `docs/troubleshooting/analysis-pipeline.md`      | Manifest errors, missing stage outputs, invalid filter candidates.   |

## Phase 11 — Documentation validation

### Step 11.1 — Link/path validation

Add a script or manual checklist to validate:

- all Markdown links resolve,
- all image links resolve,
- all referenced config files exist,
- all command snippets are still correct,
- no canonical docs link to deprecated HX710B/old MCU material.

### Step 11.2 — Content-contract grep checks

Suggested checks:

```bash
# Fail if canonical docs still mention legacy firmware schema.
rg "D,<seq>|value_gr" README.md docs Handgrip_Firmware || true

# Confirm D2 schema appears in canonical protocol docs.
rg "D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>" README.md docs Handgrip_Firmware LSL_Bridge

# Find stale RS485 GUI config path.
rg "\.\./RS485_GUI/config\.yaml|RS485_GUI/config\.yaml" .

# Confirm canonical path appears.
rg "RS485_GUI/config/config\.yaml" README.md docs Handgrip_Calibration

# Ensure deprecated docs are not linked in canonical docs.
rg "HX710B|stm32f103|Hacer bascula" README.md docs --glob '!docs/archive/**'
```

### Step 11.3 — Workflow validation

Before handoff, run at least once:

```bash
uv sync
uv run pytest
```

Then validate operator workflows on hardware:

1. firmware serial monitor shows D2 frames,
2. RS485 GUI receives reference force,
3. LSL bridge publishes both streams,
4. LSL viewer displays target/reference and XY plot,
5. calibration preflight passes,
6. one smoke-test calibration recording completes,
7. calibration fit/report complete,
8. analysis smoke test completes.

---

# 11. Configuration Documentation Requirements by Component

## 11.1 Firmware configuration

Source:

```text
Handgrip_Firmware/Core/Inc/config.h
platformio.ini
```

Must document:

- PlatformIO environment,
- upload/monitor ports,
- serial baud,
- sampling period,
- calibration mode,
- scale factor,
- offset,
- D2 protocol fields,
- how changes affect LSL bridge and calibration.

## 11.2 RS485 GUI configuration

Source:

```text
RS485_GUI/config/config.yaml
```

Must document:

- `session`,
- `app`,
- `ui`,
- `logger`,
- `ipc`,
- serial/default port,
- Modbus vs Active-Send mode,
- display downsampling vs acquisition/logging,
- file outputs,
- ZMQ publishing.

## 11.3 LSL Bridge configuration

Source:

```text
LSL_Bridge/conf/config.yaml
LSL_Bridge/conf/logging/*.yaml
```

Must document:

- target stream metadata,
- reference stream metadata,
- event stream,
- serial input,
- RS485 IPC input,
- timestamping policy,
- processing filters,
- CSV output,
- logging.

## 11.4 LSL Viewer configuration

Source:

```text
LSL_Viewer/conf/config.yaml
```

Must document:

- live/csv/xdf modes,
- stream names,
- buffer sizes,
- channel labels,
- XY correlation options,
- time alignment modes,
- plot sizes/styles,
- replay behavior.

## 11.5 Calibration configuration

Source:

```text
Handgrip_Calibration/conf/*.yaml
```

Must document:

- base/default config,
- protocol metadata,
- component config snapshots,
- LSL stream requirements,
- preflight checks,
- recording outputs,
- protocol event sequence,
- fit models,
- report settings,
- v3 protocol as primary.

## 11.6 Analysis configuration

Source:

```text
Handgrip_Analysis/conf/**/*.yaml
```

Must document:

- input manifest,
- output root,
- stage inclusion/exclusion,
- aggregation policy,
- stage 1–6 settings,
- DSP/filter candidates,
- validation split policy,
- figure/report outputs.

---

# 12. Root README Target Content

The root README should be concise but complete enough for a first-time user.

Recommended skeleton:

```markdown
# Handgrip Suite

## Summary

The Handgrip Suite captures, visualizes, calibrates, and analyzes handgrip force data using a target HX711/Arduino handgrip device and a PM58/acquisition-board reference chain.

## Start here

| Goal                  | Read this                                             |
| --------------------- | ----------------------------------------------------- |
| Understand the system | `docs/start-here.md`                                  |
| Connect the hardware  | `docs/workflows/physical-setup.md`                    |
| Upload firmware       | `docs/workflows/firmware-setup.md`                    |
| See live signals      | `docs/workflows/full-live-viewer-quickstart.md`       |
| Run calibration       | `docs/workflows/handgrip-calibration.md`              |
| Run analysis          | `docs/workflows/handgrip-analysis.md`                 |
| Modify code           | `docs/development/python-project-structure-primer.md` |

## System components

| Component | Purpose |
| --------- | ------- |

## Fast validation

## Documentation map

## Current known issues
```

---

# 13. Style Guide for Refactored Documentation

## 13.1 Global style rules

- Start with the answer.
- Use summary-first structure.
- Separate workflow docs from reference docs.
- Use explicit “Known / Could / Cannot” when uncertainty matters.
- Use exact paths and commands.
- Every workflow step must include expected result and failure signal.
- Every config key must explain impact and risk.
- Every archived/deprecated document must have a status banner.
- Never mix generated output with maintained instructions without labeling it.

## 13.2 Required metadata block for maintained docs

```markdown
# <Title>

## Summary

- <3–7 bullet summary>

## Audience

- <Who should read this>

## Status

| Field                  | Value                        |
| ---------------------- | ---------------------------- |
| Canonical              | Yes/No                       |
| Last validated against | <commit/date/session>        |
| Applies to             | <component/version/protocol> |
```

## 13.3 Workflow step format

```markdown
### Step N — <Action>

- **Do:** <Concrete action>
- **Command / file:** `<path_or_command>`
- **Expected result:** <Success signal>
- **Failure signal:** <What indicates a problem>
- **Next branch:** <What to do next>
```

## 13.4 Configuration reference format

```markdown
| Key | Type | Default | Allowed values | Operational impact | When to change | Failure risk |
| --- | ---- | ------- | -------------- | ------------------ | -------------- | ------------ |
```

## 13.5 Archive banner format

```markdown
> **Archive status:** Deprecated / historical.
> This file is not part of the current canonical Handgrip Suite workflow.
> Do not use it for current wiring, firmware, calibration, or analysis unless explicitly instructed.
```

---

# 14. Updated High-Priority Known Issues

| ID    | Issue                                                     | Severity | Current status             | Required action                                        |
| ----- | --------------------------------------------------------- | -------: | -------------------------- | ------------------------------------------------------ |
| KI-1  | Root `README.md` missing                                  |     High | Still true                 | Create root README.                                    |
| KI-2  | Root `docs/` missing                                      |     High | Still true                 | Create docs skeleton.                                  |
| KI-3  | Firmware README stale protocol                            |     High | Source fixed; README stale | Update firmware docs to D2 schema.                     |
| KI-4  | Calibration config snapshot path mismatch                 |     High | Still true                 | Change to `../RS485_GUI/config/config.yaml`.           |
| KI-5  | Calibration protocol default ambiguity                    |     High | Still true                 | Make v3 CLI default or enforce explicit v3 in docs.    |
| KI-6  | New setup images absent from ZIP                          |   Medium | Missing                    | Add three requested images to `docs/hardware/assets/`. |
| KI-7  | Deprecated HX710B/old MCU docs mixed with useful docs     |   Medium | Still present              | Remove from canonical; archive or delete.              |
| KI-8  | No complete config reference per component                |   Medium | Still true                 | Author config docs.                                    |
| KI-9  | Generated outputs mixed with maintained docs              |   Medium | Still true                 | Curate examples or mark as generated.                  |
| KI-10 | Source-layout not explained for research handoff audience |   Medium | Still true                 | Add development primer and component maps.             |

---

# 15. Validation Plan

## 15.1 Documentation acceptance checklist

| Check                                        | Method                                                              | Expected result                             | Failure meaning                              |
| -------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------- | -------------------------------------------- |
| Root README exists                           | `test -f README.md`                                                 | File exists and links to docs               | No canonical entry point.                    |
| Root docs index exists                       | `test -f docs/index.md`                                             | File exists                                 | Docs tree not navigable.                     |
| Component docs indexes exist                 | loop over components                                                | All `docs/index.md` exist                   | Component docs incomplete.                   |
| Useful images exist                          | `find docs/hardware/assets`                                         | All required images present                 | Hardware docs cannot be visual/reproducible. |
| New setup photos exist                       | `test -f` for three filenames                                       | All present                                 | Force-fixture docs incomplete.               |
| Acquisition-board PDFs preserved             | `find docs/hardware/references/acquisition-board`                   | Source PDFs present                         | Reference fallback missing.                  |
| HX711 datasheet preserved                    | `test -f docs/hardware/references/hx711/hx711_english.pdf`          | Present                                     | Firmware ADC reference missing.              |
| Deprecated docs not linked in canonical docs | `rg HX710B README.md docs --glob '!docs/archive/**'`                | No hits except explicit deprecation notes   | Old hardware may confuse users.              |
| Firmware D2 schema documented                | `rg "D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>"` | Hits in protocol docs                       | Parser contract not documented.              |
| Legacy D schema removed                      | `rg "D,<seq>                                                        | value_gr" README.md docs Handgrip_Firmware` | No stale hits                                | Firmware docs still misleading. |
| RS485 GUI config path fixed                  | `rg "../RS485_GUI/config.yaml" Handgrip_Calibration/conf`           | No hits                                     | Config snapshots may fail.                   |
| v3 calibration protocol canonical            | docs + CLI check                                                    | Docs and CLI agree                          | Operators may run wrong protocol.            |
| Workflow commands validated                  | Manual run                                                          | Commands work                               | Docs are aspirational, not operational.      |

## 15.2 Handoff dry-run validation sequence

Run this sequence as a student operator would:

1. Read root `README.md` only.
2. Follow `docs/workflows/physical-setup.md` and validate hardware visually.
3. Follow `docs/workflows/firmware-setup.md` and confirm D2 serial frames.
4. Follow `docs/workflows/reference-only-quickstart.md` and confirm RS485 GUI data.
5. Follow `docs/workflows/full-live-viewer-quickstart.md` and confirm both streams live.
6. Follow `docs/workflows/handgrip-calibration.md` with a smoke protocol or v3 protocol.
7. Follow `docs/workflows/handgrip-analysis.md` on known input data.
8. Ask a maintainer to modify one non-critical config and revert it using docs.

Acceptance condition:

- A student can complete steps 1–7 without Nicolás explaining undocumented assumptions.

---

# 16. Definition of Done

The documentation refactor is complete when:

1. Root `README.md` exists and is the obvious entry point.
2. Root `docs/index.md` exists and maps all reader pathways.
3. Every component has:
   - `README.md`,
   - `docs/index.md`,
   - quickstart/workflow doc,
   - configuration reference,
   - architecture/development doc.
4. Hardware docs use the canonical image assets, including the three new setup photos.
5. Acquisition-board PDFs, HX711 datasheet, and provider offer are preserved as fallback references.
6. HX710B / old ADV / old STM32F103 material is absent from canonical docs.
7. Firmware docs consistently use D2 schema.
8. Calibration docs and CLI defaults agree on the primary protocol, or docs explicitly force v3 with `--config`.
9. Calibration config snapshot paths point to real files.
10. Configuration values are documented with impact/range/failure risk.
11. Generated outputs are labeled as examples or kept outside maintained docs.
12. Link/path validation passes.
13. A student operator can follow the documented workflow from physical setup to live viewer and calibration without private context.

---

# Appendix A — Component README Template

````markdown
# <Component Name>

## Summary

- <What this component does>
- <When it is used>
- <Main inputs>
- <Main outputs>

## First command

```bash
<command>
```

## Expected result

<What the user should see.>

## Configuration

- Main config: `<path>`
- Full reference: `<docs/configuration.md>`

## Common workflows

| Goal | Doc |
| ---- | --- |

## Repository layout

```text
<tree>
```

## Tests

```bash
<test command>
```

## Further docs
````

# Appendix B — Configuration Reference Template

````markdown
# <Component> Configuration Reference

## Summary

## Status

| Field          | Value           |
| -------------- | --------------- |
| Config file    | `<path>`        |
| Last validated | `<date/commit>` |

## Override examples

```bash
<command key=value>
```

## Configuration table

| Key | Type | Default | Allowed values | Operational impact | When to change | Failure risk |
| --- | ---- | ------- | -------------- | ------------------ | -------------- | ------------ |
````

# Appendix C — Workflow Template

````markdown
# <Workflow Title>

## Summary

## Audience

## Prerequisites

## Step-by-step workflow

### Step 1 — <Action>

- **Do:**
- **Command / file:**
- **Expected result:**
- **Failure signal:**
- **Next branch:**

## Outputs

## Troubleshooting

## Validation checklist
````

# Appendix D — Archive Status Template

````markdown
# <Historical Document Title>

> **Archive status:** Deprecated / historical.
> This file is not part of the current canonical Handgrip Suite workflow.

## What is still useful

## What is outdated

## Migration notes

## Replacement canonical docs
````

# Appendix E — Glossary Seed

| Term              | Meaning                                                                                                      |
| ----------------- | ------------------------------------------------------------------------------------------------------------ |
| Acquisition board | External high-speed load-cell indicator/transmitter used as reference acquisition chain.                     |
| Active-Send       | Vendor board mode where measurement frames are pushed over RS485 rather than host-polled through Modbus RTU. |
| Calibration       | Process of fitting target handgrip readings against reference force values.                                  |
| Config snapshot   | Copy of component configs stored with a session to preserve reproducibility.                                 |
| D2 payload        | Current firmware serial schema: `D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>`.              |
| HX711             | 24-bit load-cell ADC used by the target handgrip device.                                                     |
| LSL               | Lab Streaming Layer, used for timestamped real-time data streams.                                            |
| PM58              | Reference load cell used with the acquisition board.                                                         |
| Source layout     | Python package structure where importable package code lives under `src/<package_name>/`.                    |
| ZeroMQ / ZMQ      | Messaging layer used by `RS485_GUI` to publish measurements to `LSL_Bridge`.                                 |

---

# Appendix F — Immediate Patch Checklist

Apply these before writing final prose:

```bash
# 1. Create docs skeleton.
mkdir -p docs/{architecture,workflows,hardware/assets,hardware/references/acquisition-board,hardware/references/hx711,configuration,development,troubleshooting,examples/calibration-session,examples/analysis-output,contributing,archive/documentation-plans,archive/historical-notes,archive/deprecated/old-adv-mcu}
for d in Handgrip_Firmware RS485_GUI LSL_Bridge LSL_Viewer Handgrip_Calibration Handgrip_Analysis; do mkdir -p "$d/docs"; done

# 2. Find stale firmware schema docs.
rg "D,<seq>|value_gr" Handgrip_Firmware README.md docs Documentation || true

# 3. Find stale RS485 GUI config paths.
rg "../RS485_GUI/config.yaml" Handgrip_Calibration/conf

# 4. Find old protocol defaults.
rg "protocol_static_staircase.yaml" Handgrip_Calibration Documentation docs || true

# 5. Find deprecated old hardware mentions in canonical docs after migration.
rg "HX710B|stm32f103|Hacer bascula" README.md docs --glob '!docs/archive/**' || true
```
