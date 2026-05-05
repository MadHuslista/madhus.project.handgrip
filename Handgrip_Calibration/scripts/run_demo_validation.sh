#!/usr/bin/env bash
set -euo pipefail

# Run this from the Handgrip_Calibration package root.
python -m handgrip_calibration.cli validate-config --config conf/default.yaml
python -m handgrip_calibration.cli demo-data --output ./demo_sessions
python -m handgrip_calibration.cli fit ./demo_sessions/demo_handgrip_session --config conf/default.yaml
python -m handgrip_calibration.cli report ./demo_sessions/demo_handgrip_session

echo "Demo validation complete: ./demo_sessions/demo_handgrip_session"
