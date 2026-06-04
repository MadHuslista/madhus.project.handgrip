#!/usr/bin/env bash
set -euo pipefail

DOCS_ONLY=0
if [[ "${1:-}" == "--docs-only" ]]; then
  DOCS_ONLY=1
fi

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

warn() {
  echo "WARN: $*" >&2
}

# Required current firmware schema.
rg "D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>" README.md docs Handgrip_Firmware LSL_Bridge >/dev/null \
  || fail "D2 schema not found in canonical protocol docs"

# Required stream and IPC contracts.
rg "HandgripTarget" README.md docs LSL_Bridge LSL_Viewer Handgrip_Calibration >/dev/null \
  || fail "HandgripTarget contract missing"
rg "HandgripReference" README.md docs LSL_Bridge LSL_Viewer Handgrip_Calibration >/dev/null \
  || fail "HandgripReference contract missing"
rg "HandgripComponentEvents" README.md docs LSL_Bridge LSL_Viewer Handgrip_Calibration >/dev/null \
  || fail "HandgripComponentEvents contract missing"
rg "HandgripCalibrationMarkers" README.md docs LSL_Viewer Handgrip_Calibration >/dev/null \
  || fail "HandgripCalibrationMarkers contract missing"
rg "rs485.measurement.v1" README.md docs RS485_GUI LSL_Bridge >/dev/null \
  || fail "rs485.measurement.v1 IPC contract missing"

# Canonical RS485 config path.
rg "RS485_GUI/config/config\.yaml" README.md docs Handgrip_Calibration >/dev/null \
  || fail "canonical RS485_GUI/config/config.yaml path not found"

# Strict config check when full source is present.
if [[ -d Handgrip_Calibration/conf ]]; then
  if rg "\.\./RS485_GUI/config\.yaml" Handgrip_Calibration/conf; then
    fail "stale ../RS485_GUI/config.yaml path found in calibration config files"
  fi
fi

# Report legacy/stale mentions for review, but do not fail when they are clearly labelled.
echo "\nReview legacy firmware schema mentions, if any:"
rg "D,<seq>|value_gr" README.md docs Handgrip_Firmware --glob '!docs/archive/**' || true

echo "\nReview stale RS485 config-path mentions, if any:"
rg "\.\./RS485_GUI/config\.yaml|RS485_GUI/config\.yaml" README.md docs Handgrip_Calibration --glob '!docs/archive/**' || true

# Deprecated hardware guard: canonical docs must not link to deprecated materials.
if rg "\]\([^)]*(HX710B|hx710|stm32f103|Hacer%20bascula|Hacer bascula)[^)]*\)" README.md docs --glob '!docs/archive/**'; then
  fail "canonical docs link to deprecated HX710B/old MCU material"
fi

echo "\nReview deprecated hardware term mentions, if any:"
rg "HX710B|stm32f103|Hacer bascula" README.md docs --glob '!docs/archive/**' || true

if [[ "$DOCS_ONLY" == "0" ]]; then
  for p in \
    platformio.ini \
    Handgrip_Firmware/Core/Inc/config.h \
    RS485_GUI/config/config.yaml \
    LSL_Bridge/conf/config.yaml \
    LSL_Viewer/conf/config.yaml \
    Handgrip_Calibration/conf/protocol_static_reversible_staircase_v3.yaml
  do
    [[ -e "$p" ]] || fail "required full-repo path missing: $p"
  done
else
  echo "INFO: docs-only mode: skipped strict source/config existence checks"
fi

echo "CONTENT CONTRACT VALIDATION PASSED"
