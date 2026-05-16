# Architecture Documentation

## Summary

This folder contains system-level architecture docs for the Handgrip Suite.

## Documents

| Document                                                                     | Purpose                                                         |
| ---------------------------------------------------------------------------- | --------------------------------------------------------------- |
| [`dataflow.md`](dataflow.md)                                                 | End-to-end physical and software dataflow.                      |
| [`repository-layout.md`](repository-layout.md)                               | Repository organization and ownership boundaries.               |
| [`runtime-processes.md`](runtime-processes.md)                               | Runtime process order and responsibilities.                     |
| [`stream-contracts.md`](stream-contracts.md)                                 | Serial, IPC, LSL, marker, and session contracts.                |
| [`timestamping-and-synchronization.md`](timestamping-and-synchronization.md) | Host/device timestamping, drift, gaps, and viewer alignment.    |
| [`data-and-output-lifecycle.md`](data-and-output-lifecycle.md)               | Where data appears and how generated outputs should be treated. |

## Validation

Run:

```bash
python3 ../../scripts/validate_docs.py --repo-root ../..
```
