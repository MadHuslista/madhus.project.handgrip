# LSL Bridge Development Guide

## Summary

- Treat stream schemas, channel order, IPC fields, and firmware parser behavior as cross-component contracts.
- Add or change channels through a migration path, not by editing one file only.
- Parser, timestamping, filter, and CSV changes all have targeted tests.
- Preserve raw target counts and reference force as calibration-authoritative signals.

## Development prerequisites

From `LSL_Bridge/`:

```bash
uv sync --extra dev
uv run pytest
```

If working from the repository root, ensure the workspace install still includes `lsl-bridge` as an editable local package.

## Add a target channel safely

### Files to edit

1. `LSL_Bridge/conf/config.yaml`
   - add channel under `streams.target.channels`.
2. `LSL_Bridge/src/lsl_bridge/types.py`
   - add field to `ParsedTargetSample` if the channel is parsed/source data.
3. `LSL_Bridge/src/lsl_bridge/core/parser.py`
   - update D2 regex and field extraction if firmware payload changes.
4. `LSL_Bridge/src/lsl_bridge/io/lsl_outlets.py`
   - ensure metadata and channel descriptions are correct.
5. `LSL_Bridge/src/lsl_bridge/app.py`
   - update `target_outlet.push_sample([...])` order.
6. `LSL_Bridge/src/lsl_bridge/io/csv_sinks.py`
   - update target CSV fieldnames and row output if persisted.
7. Docs/configs for consumers:
   - `docs/architecture/stream-contracts.md`,
   - `LSL_Bridge/docs/stream-contracts.md`,
   - `LSL_Viewer` config/docs,
   - `Handgrip_Calibration` config/docs.

### Tests to update

```bash
uv run pytest tests/unit/test_parser.py
uv run pytest tests/integration/test_csv_sinks.py
```

## Change parser behavior safely

Parser changes are high-risk because they affect the target stream contract.

Rules:

- Keep parsing strict unless there is a documented compatibility reason.
- Do not accept malformed D2 lines silently.
- Emit/log sequence gaps.
- Keep M2 metadata handling intact.
- Update firmware docs and root stream contracts with any schema change.

Required tests:

```bash
uv run pytest tests/unit/test_parser.py
```

Recommended static checks:

```bash
rg "D2,<seq>,<timestamp_us>,<raw_count>,<current_units>,<status>" README.md docs Handgrip_Firmware LSL_Bridge
```

## Add a reference IPC field safely

### Files to edit

1. `RS485_GUI` publisher schema and docs.
2. `LSL_Bridge/src/lsl_bridge/types.py` if the field becomes part of `ReferenceSample`.
3. `LSL_Bridge/src/lsl_bridge/publishers/reference.py` `_decode_record()`.
4. `LSL_Bridge/src/lsl_bridge/io/csv_sinks.py` if persisted.
5. `LSL_Bridge/conf/config.yaml` if it changes LSL stream channels.
6. Root and component stream-contract docs.

### Important rule

Do not reintroduce legacy aliases such as `rs485_raw`, `rs485_clock`, or `status_word` unless a compatibility mode is explicitly designed, documented, and tested.

## Add a processing stage safely

The current processor interface is:

```python
process(value: float, sample_time_s: float) -> float
```

Steps:

1. Add processor implementation or extend `lsl_bridge.core.filter`.
2. Update `processing` config.
3. Keep raw target channel unchanged.
4. Publish processed output as an additional/derived channel only after updating stream contracts.
5. Validate filter behavior with controlled test data.

Required tests:

```bash
uv run pytest tests/unit/test_filter.py
```

If timing behavior changes:

```bash
uv run pytest tests/unit/test_timestamping.py
```

## Change timestamping safely

Timestamping changes can affect viewer XY alignment and calibration segmentation.

Files to inspect/edit:

- `LSL_Bridge/src/lsl_bridge/core/timestamping.py`,
- `LSL_Bridge/conf/config.yaml` under `target_timestamping`,
- `LSL_Bridge/docs/timestamping.md`,
- root `docs/architecture/timestamping-and-synchronization.md`.

Required tests:

```bash
uv run pytest tests/unit/test_timestamping.py
```

Manual validation:

1. Run target-only quickstart.
2. Watch for `target_timestamp_reanchor` events.
3. Run full viewer quickstart.
4. Verify XY plot does not accumulate growing lag.
5. Capture a short calibration session and inspect saved timestamps.

## Add CSV fields safely

Files:

- `LSL_Bridge/src/lsl_bridge/io/csv_sinks.py`,
- `tests/integration/test_csv_sinks.py`,
- `LSL_Bridge/docs/stream-contracts.md`,
- `LSL_Bridge/docs/architecture.md`.

Required test:

```bash
uv run pytest tests/integration/test_csv_sinks.py
```

## Add UI/control behavior elsewhere

`LSL_Bridge` should not own UI. If a requested change is display-only:

- add it to `LSL_Viewer`, not `LSL_Bridge`,
- do not change stream contracts unless new data is needed,
- do not hide acquisition defects in a display transform.

## Release checklist for bridge changes

- [ ] Parser tests pass.
- [ ] Timestamping tests pass.
- [ ] Filter tests pass if processing changed.
- [ ] CSV integration tests pass if persistence changed.
- [ ] Root stream contracts updated.
- [ ] LSL Bridge component docs updated.
- [ ] Viewer/calibration configs updated if channels changed.
- [ ] Manual full-live workflow validated.
- [ ] Calibration preflight validates both streams.
