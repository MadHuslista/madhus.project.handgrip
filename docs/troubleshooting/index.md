# Troubleshooting Index

## Summary

Troubleshooting is symptom-first. Start with the symptom you see, validate the owner component, then follow the linked workflow or component doc.

## Symptom map

| Symptom                                                             | Start here                                               |
| ------------------------------------------------------------------- | -------------------------------------------------------- |
| No board display, wrong load sign, unstable reading, overload       | [docs/troubleshooting/hardware-and-wiring.md](hardware-and-wiring.md)       |
| No serial port, wrong A/B, baud mismatch, no Active-Send frames     | [docs/troubleshooting/serial-and-rs485.md](serial-and-rs485.md)             |
| Streams not visible, wrong names, stale outlets                     | [docs/troubleshooting/lsl-streams.md](lsl-streams.md)                       |
| XY delay, reference lag, display-only shift vs real timestamp issue | [docs/troubleshooting/viewer-lag-or-xy-delay.md](viewer-lag-or-xy-delay.md) |
| Missing target/reference CSV, failed preflight, bad session ID      | [docs/troubleshooting/calibration-recording.md](calibration-recording.md)   |
| Manifest errors, missing stage outputs, invalid filter candidates   | [docs/troubleshooting/analysis-pipeline.md](analysis-pipeline.md)           |

## General rule

Validate hardware and stream contracts before editing implementation code.
