# Doxygen Document Skill — Internal Memories

This file stores knowledge accumulated across runs of the `/doxygen-document` skill.
Each entry documents a rule, convention, or clarification that improves future documentation passes.

---

## Memory Schema

```
### [SHORT TITLE]
- **what**       : The piece of information or rule.
- **why**        : Why it is useful.
- **how**        : How and where to apply it.
- **when**       : The circumstances in which it applies (or "always").
- **created_at** : YYYY-MM-DDTHH:MM:SS
- **updated_at** : YYYY-MM-DDTHH:MM:SS
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

### C comment style: Javadoc /** */
- **what**       : C and C header files should use Javadoc-style `/** ... */` block comments.
- **why**        : Qt-style `/*! */` is also valid, but Javadoc `/** */` is more universally recognised and consistent with CLion, VS Code IntelliSense, and most CI tools.
- **how**        : Use `/** @brief ... */` blocks before each function, struct, enum, macro, and file header.
- **when**       : Always, for all C/H files in this project.
- **created_at** : 2026-05-15T00:00:00
- **updated_at** : 2026-05-15T00:00:00

### Doxyfile: report mismatches, do not auto-edit
- **what**       : The skill must not silently modify the Doxyfile.
- **why**        : The Doxyfile controls the entire documentation build; unexpected changes can break the HTML output or CI pipelines.
- **how**        : If a mismatch is found (e.g. `OPTIMIZE_OUTPUT_JAVA = NO` while Python files exist), report it in the summary and suggest the fix without applying it.
- **when**       : Always, unless the user explicitly asks the skill to update the Doxyfile.
- **created_at** : 2026-05-15T00:00:00
- **updated_at** : 2026-05-15T00:00:00

### Auto-generated and third-party files: skip
- **what**       : Files that are auto-generated or belong to third-party libraries should not be documented.
- **why**        : Documenting generated code is wasteful (it will be overwritten) and third-party code should not be modified.
- **how**        : Identify such files by path patterns (e.g. `build/`, `vendor/`, `third_party/`, `generated/`, PlatformIO `.pio/`) and skip them. List all skipped files in the run summary.
- **when**       : Always.
- **created_at** : 2026-05-15T00:00:00
- **updated_at** : 2026-05-15T00:00:00
