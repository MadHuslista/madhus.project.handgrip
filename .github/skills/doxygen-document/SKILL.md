---
name: doxygen-document
description: 'Add Doxygen-compatible docstrings to Python and C source files. Use when: /doxygen-document is invoked; adding Doxygen comments; documenting undocumented functions, classes, enums, macros or files; preparing code for doxygen HTML generation; fixing missing @param, @return, @brief, or @file tags.'
argument-hint: '[path/to/dir or module name] [--only-missing] [skip C files] [skip Python files]'
disable-model-invocation: true
---

# Doxygen Document Skill

## When to Use

Triggered **only** by the `/doxygen-document` command. Never activate for any other request.

Adds Doxygen docstrings to undocumented or partially-documented entities in Python (`.py`) and C (`.h`, `.c`) source files so that running `doxygen` produces a complete HTML documentation webpage.

Optional arguments accepted in the command:
- `/doxygen-document Handgrip_Analysis/src/` — restrict scope to a path
- `/doxygen-document --only-missing` — skip entities that already have any docstring
- `/doxygen-document -module signal_processor` — restrict to a named module
- `/doxygen-document skip C files` — document Python only (or vice versa)

---

## Procedure

### Step 1 — Identify Scope

- If the user provided a path or module name, use that as the scope.
- Otherwise scan the workspace for source directories (`src/`, `Core/`, `**/*.py`, `**/*.h`, `**/*.c`).
- Present the discovered scope to the user and confirm before proceeding.

### Step 2 — Load Internal Memories

Read `./references/memories.md` to recall:
- Previously confirmed comment style choices
- Project-specific naming or exclusion rules
- Past user clarifications

### Step 3 — Scan for Documentation Gaps

For each file in scope, identify:
- Missing `@file` block (required for global symbols in C)
- Functions/methods/classes without any docstring
- Docstrings missing `@param` for one or more parameters
- Docstrings missing `@return` on non-void / non-`None` functions
- Undocumented enums, macros, structs, or typedefs

### Step 4 — Consult the Doxygen Manual (When Needed)

If a construct's correct format is ambiguous, consult:
- https://www.doxygen.nl/manual/docblocks.html — comment block formats
- https://www.doxygen.nl/manual/commands.html — special commands (@param, @return, etc.)

See also `./references/doxygen-format.md` for quick-reference examples.

### Step 5 — Save New Formatting Notes to Memory

Append useful rules discovered during the scan to `./references/memories.md`.  
Each entry must follow this schema (see `./references/memories.md`):

| Field        | Content |
|-------------|---------|
| `what`       | The rule or fact |
| `why`        | Why it is useful |
| `how`        | How/where to apply it |
| `when`       | The context in which it applies, or `always` |
| `created_at` | ISO timestamp |
| `updated_at` | ISO timestamp |

### Step 6 — Plan and Clarify

- Group all identified gaps by file and entity type.
- Flag any ambiguities that cannot be resolved from memories or the Doxygen manual (e.g. unclear parameter semantics, opaque return values).
- **Ask all ambiguous questions in a single batch** — do not ask one at a time.
- Save every user clarification as a new memory entry.

### Step 7 — Apply Documentation

Following the format rules in `./references/doxygen-format.md`:

- Add docstrings before each undocumented entity.
- Extend (do not replace) existing incomplete docstrings.
- **Never modify logic, variable names, or any non-comment code.**
- Preserve existing indentation and code style.

### Step 8 — Validate

Confirm all of the following:

| Check | Pass Condition |
|-------|---------------|
| 8.1 No logic modified | Diff shows only comment additions/extensions |
| 8.2 `@file` blocks | Every C file with global symbols has one |
| 8.3 Function coverage | All public functions: `@brief` + all `@param` + `@return` (if applicable) |
| 8.4 Class/struct coverage | All have `@brief` |
| 8.5 Doxyfile consistency | If a `Doxyfile` exists: `INPUT`, `FILE_PATTERNS`, `OPTIMIZE_OUTPUT_JAVA`, `EXTRACT_ALL` match the documented files — **report mismatches, do not silently edit** |

### Step 9 — Review and Maintain Memories

Review all entries in `./references/memories.md`:

| Status | Action |
|--------|--------|
| Accurate and relevant | Retain unchanged |
| Inaccurate or outdated | Update content + refresh `updated_at` |
| Relevant but previously wrong | Update content + refresh `updated_at` + add correction note |
| Irrelevant or unfixable | Remove the entry |

---

## Deliverable

1. Doxygen docstrings applied to all targeted entities — no non-comment code changed.
2. A brief summary:
   - Files processed
   - Entities documented (new) vs. extended (partial → complete)
   - Files/entities skipped and reason (e.g. auto-generated, third-party)
   - Doxyfile mismatches found (if applicable)
3. Updated `./references/memories.md`.

---

## Prior Clarifications

| Question | Answer |
|----------|--------|
| Which style for Python? | `##`-style Doxygen comments — supports `@param`, `@return`, etc. Do not use `"""`. |
| Which style for C? | Javadoc-style `/** ... */` blocks. |
| Modify the Doxyfile? | No — report inconsistencies only, unless the user explicitly asks to fix them. |
| Document auto-generated or third-party files? | No — skip and report. |
