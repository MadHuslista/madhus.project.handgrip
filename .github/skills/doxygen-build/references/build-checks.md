# Doxygen Build Checks Reference

## Warning Severity Model

Classify warnings before gating:

- High:
  - configuration errors preventing expected output
  - parser/preprocessor failures causing missing symbols
  - missing required toolchain (`doxygen`, or `dot` when diagrams enabled)
- Medium:
  - unresolved references
  - malformed command usage (`@param` mismatch, invalid tags)
- Low:
  - incomplete docs (`@return` omitted where expected, minor formatting)

## Suggested Parsing Patterns

Typical warning line prefix includes `warning:`.

Group by regex-like buckets:
- `warning:.*argument.*(not found|not documented)`
- `warning:.*return.*(not documented|undocumented)`
- `warning:.*unable to resolve reference`
- `warning:.*(parse|parsing|preprocessing)`
- `warning:.*(dot|graphviz)`
- `warning:.*(tag|command).*`

## Gate Modes

- default:
  - fail on any high-severity warning
  - allow medium/low but report
- strict:
  - fail on any warning
- allow-known:
  - if warning text matches an accepted pattern in shared memories, downgrade to info

## Shared Memory Entries for Warning Triage

Store accepted warning patterns in the shared schema:

```
### [KNOWN WARNING PATTERN TITLE]
- **what**       : Regex-like warning pattern accepted for now.
- **why**        : Why this warning is currently acceptable.
- **how**        : How gate logic should treat it (downgrade to info).
- **when**       : Scope/conditions where acceptance applies.
- **created_at** : YYYY-MM-DDTHH:MM:SS
- **updated_at** : YYYY-MM-DDTHH:MM:SS
- **source_skill** : doxygen-build
```

## Output Sanity

Validate that:
- `OUTPUT_DIRECTORY` exists or is generated
- `HTML_OUTPUT` directory exists when `GENERATE_HTML = YES`
- build artifacts are newer than the Doxyfile timestamp (best-effort check)
