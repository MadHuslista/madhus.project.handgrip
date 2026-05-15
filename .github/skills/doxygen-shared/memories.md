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
