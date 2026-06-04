# Doxygen Skills — Shared Memories

This file is the shared knowledge contract between:
- `../doxygen-document/SKILL.md` (writer + reader)
- `../doxygen-build/SKILL.md` (reader + appender)

Use it to persist conventions, exclusions, expected Doxyfile settings, and validated warning triage decisions.

---

## Memory Schema

```
### [SHORT TITLE]
- **what**       : The piece of information or rule.
- **why**        : Why it is useful.
- **how**        : How and where to apply it.
- **when**       : The context where it is valid (or "always").
- **created_at** : YYYY-MM-DDTHH:MM:SS
- **updated_at** : YYYY-MM-DDTHH:MM:SS
- **source_skill** : doxygen-document | doxygen-build
```

---

## Entries

### Python comment style: use ## not """
- **what**       : Python docstrings should use `##`-style Doxygen comments, not `"""` triple-quoted strings.
- **why**        : Triple-quoted `"""` strings are shown verbatim by Doxygen and do not support special commands like `@param` or `@return` unless `PYTHON_DOCSTRING = NO` is set. `##`-style comments always support all Doxygen commands.
- **how**        : Replace any `"""` docstrings with `##` comment blocks. Use `## @brief`, `## @param`, `## @return`, etc.
- **when**       : Always, for all Python files in this project.
- **created_at** : 2026-05-15T00:00:00
- **updated_at** : 2026-05-15T00:00:00
- **source_skill** : doxygen-document

### C comment style: Javadoc /** */
- **what**       : C and C header files should use Javadoc-style `/** ... */` block comments.
- **why**        : Qt-style `/*! */` is also valid, but Javadoc `/** */` is more universally recognized and consistent with common IDE tooling and CI checks.
- **how**        : Use `/** @brief ... */` blocks before each function, struct, enum, macro, and file header.
- **when**       : Always, for all C/H files in this project.
- **created_at** : 2026-05-15T00:00:00
- **updated_at** : 2026-05-15T00:00:00
- **source_skill** : doxygen-document

### Doxyfile: report mismatches, do not auto-edit
- **what**       : Skills must not silently modify the Doxyfile.
- **why**        : The Doxyfile controls the entire documentation build; unexpected changes can break output or CI pipelines.
- **how**        : If a mismatch is found, report it and propose exact edits; apply only with explicit user instruction.
- **when**       : Always, unless explicitly instructed to edit Doxyfile.
- **created_at** : 2026-05-15T00:00:00
- **updated_at** : 2026-05-15T00:00:00
- **source_skill** : doxygen-document

### Auto-generated and third-party files: skip
- **what**       : Auto-generated files and third-party code should be excluded from documentation edits.
- **why**        : Generated code is overwritten and third-party code should not be modified.
- **how**        : Exclude path patterns like `build/`, `vendor/`, `third_party/`, `generated/`, `.pio/`, `.venv/` and report skipped paths.
- **when**       : Always.
- **created_at** : 2026-05-15T00:00:00
- **updated_at** : 2026-05-15T00:00:00
- **source_skill** : doxygen-document

### Nested Python functions require same-indent Doxygen comments
- **what**       : Nested Python functions should be documented with `##` blocks at the exact same indentation level as the nested `def`.
- **why**        : Correct indentation keeps the comment attached to the intended nested callable in generated Doxygen output.
- **how**        : For callback factories and closure patterns, insert `## @brief` and relevant `@param`/`@return` lines immediately above each nested function with matching indentation.
- **when**       : When documenting nested functions in UI callbacks or closure-heavy modules.
- **created_at** : 2026-05-15T00:00:00
- **updated_at** : 2026-05-15T00:00:00
- **source_skill** : doxygen-document

### Public Python APIs should include explicit @param/@return tags
- **what**       : Public functions, methods, and properties should include explicit `@param` and `@return` tags even when type hints are present.
- **why**        : Type hints improve static analysis, but Doxygen output completeness and consistency still depends on explicit argument and return documentation.
- **how**        : Add `## @brief` plus one `@param` line per argument; include `@return` for non-`None` return values and property getters.
- **when**       : Always, during Python API documentation passes.
- **created_at** : 2026-05-15T00:00:00
- **updated_at** : 2026-05-15T00:00:00
- **source_skill** : doxygen-document

### Python module headers should include @package plus @brief
- **what**       : Each Python module should start with `## @package ...` and a `@brief` summary, even when a module-level triple-quoted description already exists.
- **why**        : Explicit package headers improve Doxygen module indexing consistency and avoid relying on parser behavior for plain Python docstrings.
- **how**        : Add a two-line `##` block directly above the module docstring at file top (`## @package ...` and `#  @brief ...`).
- **when**       : Always, when documenting Python modules for Doxygen output.
- **created_at** : 2026-05-15T12:00:00
- **updated_at** : 2026-05-15T12:00:00
- **source_skill** : doxygen-document

### Exhaustive passes include private helper functions
- **what**       : When the user requests exhaustive coverage, underscore-prefixed Python helpers should be documented too.
- **why**        : Internal helper behavior is part of generated technical docs for maintainers and reviewers.
- **how**        : Add `## @brief` and matching `@param`/`@return` tags for private helper callables exactly as for public APIs.
- **when**       : When the user explicitly asks to include private entities.
- **created_at** : 2026-05-15T12:30:00
- **updated_at** : 2026-05-15T12:30:00
- **source_skill** : doxygen-document

### Dataclass field documentation uses class-level @param tags
- **what**       : Dataclass field intent should be documented with class-level `@param` tags for each field.
- **why**        : Field-level semantics are otherwise easy to miss in generated module pages.
- **how**        : Add a class `## @brief` followed by one `@param` line per dataclass attribute.
- **when**       : Always for dataclasses during Doxygen documentation passes.
- **created_at** : 2026-05-15T12:30:00
- **updated_at** : 2026-05-15T12:30:00
- **source_skill** : doxygen-document

### C++ templates: document @tparam and inline methods in headers
- **what**       : Header-only C++ template classes should include `@tparam` on the class block and full method docs where methods are defined inline.
- **why**        : Template APIs are frequently implemented entirely in headers; without inline method docs Doxygen output is incomplete for public interfaces.
- **how**        : Add `/** @brief ... @tparam T ... */` before the template class and include `@param`/`@return` tags on public inline methods in the same header.
- **when**       : Always, when documenting C++ template classes in `.h`/`.hpp` files.
- **created_at** : 2026-05-15T13:00:00
- **updated_at** : 2026-05-15T13:00:00
- **source_skill** : doxygen-document

### Build triage baseline: config and markup warnings dominate
- **what**       : Current baseline build on Linux (Doxygen 1.9.8) completes successfully with 45 warnings, concentrated in group-title mismatches, unsupported xml/html tags, unknown command usage, and one obsolete Doxyfile tag.
- **why**        : Establishes that the present gate risk is warning hygiene rather than missing tooling or failed parsing, so remediation should prioritize comment/tag normalization.
- **how**        : In `/doxygen-build` triage, prioritize fixing `<br>` group title mismatches in firmware files, escaping/rewriting literal angle-bracket tokens (for example `<channel>`), replacing `@hydra` with escaped text, and replacing obsolete `CLASS_DIAGRAMS` config usage.
- **when**       : Valid for default Doxyfile builds in this repository unless warning totals/categories materially change.
- **created_at** : 2026-05-15T07:56:24-04:00
- **updated_at** : 2026-05-15T07:56:24-04:00
- **source_skill** : doxygen-build

### Strict build cleanup pattern for declaration/definition duplicates
- **what**       : Strict clean build (0 warnings) achieved by normalizing group markers, escaping literal angle-bracket tokens and @-prefixed text, removing obsolete CLASS_DIAGRAMS, and hiding forward prototypes from Doxygen with `@cond ... @endcond` so only definitions are indexed.
- **why**        : Prevents false-positive `no matching file member found` and multi-group assignment warnings in C++ files with separate declarations and definitions.
- **how**        : Use `@ingroup` section markers instead of repeated `@addtogroup` redefinitions, keep implementation section banners as plain comments, and wrap prototype-only declarations in a Doxygen cond block when they duplicate documented definitions.
- **when**       : Apply when Doxygen emits duplicate-member or no-matching-member warnings in firmware C/C++ modules during strict runs.
- **created_at** : 2026-05-15T08:09:33-04:00
- **updated_at** : 2026-05-15T08:09:33-04:00
- **source_skill** : doxygen-build
