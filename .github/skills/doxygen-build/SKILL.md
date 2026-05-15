---
name: doxygen-build
description: 'Run and validate Doxygen builds. Use when: /doxygen-build is invoked; generating docs from Doxyfile; triaging Doxygen warnings; checking Graphviz/dot readiness; validating Doxyfile settings; producing build health summary for CI or local quality gates.'
argument-hint: '[path/to/Doxyfile] [--strict] [--allow-known] [--html-only]'
disable-model-invocation: true
---

# Doxygen Build Skill

## When to Use

Triggered only by the `/doxygen-build` command. Never activate for any other request.

Use this skill to run Doxygen, detect and classify warnings, validate build prerequisites, and produce a quality-gate summary without modifying source code comments.

Optional arguments accepted in the command:
- `/doxygen-build` — run default Doxyfile at repo root
- `/doxygen-build path/to/Doxyfile` — run a specific config
- `/doxygen-build --strict` — fail if any warning remains
- `/doxygen-build --allow-known` — tolerate warnings listed as accepted in shared memories
- `/doxygen-build --html-only` — verify HTML path and skip non-HTML expectation checks

---

## Procedure

### Step 1 — Resolve Build Config

- Locate `Doxyfile` in repo root unless a path is provided.
- If missing, inform user and propose bootstrapping from `../doxygen-document/references/Doxyfile.template`.
- Read the effective config and extract key values: `INPUT`, `FILE_PATTERNS`, `EXCLUDE_PATTERNS`, `OUTPUT_DIRECTORY`, `GENERATE_HTML`, `HAVE_DOT`, `OPTIMIZE_OUTPUT_JAVA`, `PYTHON_DOCSTRING`.

### Step 2 — Load Shared Memory Contract

Read `../doxygen-shared/memories.md` and collect:
- Expected Doxyfile conventions
- Known accepted warning patterns (if any)
- Current exclusions and path decisions
- Prior build/toolchain findings

### Step 3 — Preflight Checks

- Verify `doxygen` binary exists.
- If `HAVE_DOT = YES`, verify `dot` exists.
- Validate `INPUT` paths resolve.
- Validate language expectations:
  - Python projects should have `OPTIMIZE_OUTPUT_JAVA = YES`
  - `PYTHON_DOCSTRING = NO` when `##` style is required

### Step 4 — Run Build

- Execute Doxygen with the resolved Doxyfile.
- Capture stdout/stderr.
- Parse warning lines and group by category:
  - undocumented parameter / return
  - unresolved references
  - parsing/preprocessing issues
  - missing include/graph tool issues
  - config issues

See `./references/build-checks.md` for parsing and severity guidance.

### Step 5 — Quality Gate

Apply the gate mode:

- Default mode: fail on high-severity warnings; report medium/low.
- `--strict`: fail on any warning.
- `--allow-known`: warnings matching accepted patterns in shared memory are downgraded to informational.

### Step 6 — Persist Learning

Append validated learnings to `../doxygen-shared/memories.md`:
- newly confirmed acceptable warning patterns
- corrected Doxyfile expectations
- environment prerequisites discovered (e.g., missing `dot`)

Each memory must include:
- `what`, `why`, `how`, `when`, `created_at`, `updated_at`, `source_skill`

### Step 7 — Deliver Build Report

Return:
- build status (pass/fail)
- Doxygen version and config path used
- warning summary by category and count
- top actionable fixes (file + reason)
- known-accepted warnings applied (if `--allow-known`)
- output path sanity (`OUTPUT_DIRECTORY`, `HTML_OUTPUT`)

---

## Validation Checklist

| Check            | Pass Condition                                   |
| ---------------- | ------------------------------------------------ |
| Config found     | Doxyfile exists and is readable                  |
| Tooling ready    | `doxygen` found; `dot` found when required       |
| Inputs valid     | `INPUT` entries resolve and match expected scope |
| Build complete   | Doxygen exits successfully                       |
| Warning gate     | Meets selected gate mode                         |
| Output available | Expected HTML output path exists                 |

---

## Collaboration Contract with doxygen-document

- `doxygen-document` is the primary writer for style and documentation-convention memories.
- `doxygen-build` is the primary writer for build/warning triage memories.
- Both skills read and write `../doxygen-shared/memories.md`.
- Neither skill silently edits `Doxyfile` unless explicitly requested.
