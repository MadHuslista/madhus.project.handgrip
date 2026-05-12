"""LSL Bridge — Handgrip system publisher (schema v2).

Publishes two native LSL streams consumed by Handgrip_Calibration:
  * HandgripTarget   — Arduino/HX711 D2 frames (irregular, ~93-100 Hz)
  * HandgripReference — RS485 acquisition board IPC frames (regular, 500 Hz)

Entry points:
  python -m lsl_bridge
  lsl-bridge   (if installed via pyproject.toml scripts)
"""

__version__ = "2.0.0"
