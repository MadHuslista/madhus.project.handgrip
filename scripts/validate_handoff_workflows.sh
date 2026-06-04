#!/usr/bin/env bash
set -euo pipefail

DOCS_ONLY=0
if [[ "${1:-}" == "--docs-only" ]]; then
  DOCS_ONLY=1
fi

echo "# Handgrip Suite Handoff Workflow Validation"
echo

if [[ "$DOCS_ONLY" == "1" ]]; then
  echo "INFO: docs-only mode: printing workflow checklist and validating docs presence only."
else
  echo "INFO: strict/full-repo mode. Set RUN_HANDOFF_SOFTWARE=1 to run uv sync and pytest."
fi

# Required workflow docs.
for f in \
  docs/workflows/firmware-setup.md \
  docs/workflows/reference-only-quickstart.md \
  docs/workflows/full-live-viewer-quickstart.md \
  docs/workflows/handgrip-calibration.md \
  docs/workflows/handgrip-analysis.md \
  docs/maintenance/handoff-workflow-validation.md
  do
    test -f "$f"
    echo "OK: $f"
  done

if [[ "${RUN_HANDOFF_SOFTWARE:-0}" == "1" ]]; then
  uv sync
  uv run pytest
else
  echo "INFO: skipped software execution. To run: RUN_HANDOFF_SOFTWARE=1 bash scripts/validate_handoff_workflows.sh"
fi

cat <<'CHECKLIST'

Manual hardware/operator validation gates:

[ ] 1. Firmware serial monitor shows M2 metadata and D2 data frames.
[ ] 2. RS485 GUI receives reference force from the acquisition board.
[ ] 3. LSL bridge publishes HandgripTarget and HandgripReference.
[ ] 4. LSL viewer displays target/reference time series and XY plot.
[ ] 5. Calibration preflight passes with protocol_static_reversible_staircase_v3.yaml.
[ ] 6. One smoke-test calibration recording completes and creates a session folder.
[ ] 7. Calibration fit/report complete for the smoke session.
[ ] 8. Analysis smoke test completes and writes an output artifact.

Evidence to capture:

- serial monitor screenshot or log showing D2 lines,
- RS485 GUI screenshot/log showing reference force response,
- LSL bridge log showing target/reference stream publication,
- viewer screenshot showing target/reference/XY plot,
- calibration session ID,
- calibration report path,
- analysis output path.
CHECKLIST

echo "HANDOFF WORKFLOW CHECKLIST GENERATED"
