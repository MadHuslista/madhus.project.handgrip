# LSL Viewer Development Guide

## Summary

- Keep acquisition semantics outside the viewer. The viewer observes and visualizes data; it should not redefine stream contracts.
- Add new plots through the chart/layout/update path, not by mutating source buffers.
- Add new signals by updating config labels, data extraction, types, chart options, and tests together.
- Add new toggles through config + state + panel callback + tests.

## Development entry points

| Task | Start with |
| --- | --- |
| Add a new plot | `src/lsl_viewer/viz/charts.py`, `src/lsl_viewer/viz/panels.py` |
| Add a new signal/channel | `conf/config.yaml`, `config.py`, `types.py`, `core/stream.py`, `core/replay.py` |
| Change XY behavior | `core/alignment.py`, `viz/charts.py`, `viz/state.py` |
| Add a keyboard/control toggle | `config.py`, `viz/panels.py`, `types.py`, tests |
| Add replay behavior | `core/replay.py`, `viz/app.py`, replay tests |
| Add marker behavior | `viz/markers.py`, `viz/charts.py`, marker integration tests |

## Add a new plot

### Files to edit

1. `src/lsl_viewer/viz/charts.py`
2. `src/lsl_viewer/viz/panels.py`
3. `src/lsl_viewer/types.py` if new handle/state fields are required
4. `tests/integration/test_charts.py`

### Workflow

1. Add chart options builder in `viz/charts.py`.
2. Add handle field to `ChartHandles`.
3. Bind chart element in `viz/panels.py`.
4. Populate series in `update_charts()`.
5. Add tests for empty window, full window, render budgeting, and clear behavior.

### Validation

```bash
cd LSL_Viewer
uv run pytest tests/integration/test_charts.py
```

## Add a new signal/channel

### Files to edit

1. `conf/config.yaml`
2. `src/lsl_viewer/config.py`
3. `src/lsl_viewer/types.py`
4. `src/lsl_viewer/core/stream.py`
5. `src/lsl_viewer/core/replay.py`
6. chart/update files if plotted
7. tests

### Rules

- Do not hard-code stream channel names inside plotting code.
- Keep channel labels in config.
- Keep live and replay paths consistent.
- Update root/component stream-contract docs if the channel is a shared contract.

### Validation

```bash
cd LSL_Viewer
uv run pytest tests/unit/test_replay_loaders.py
uv run pytest tests/integration/test_csv_replay.py
uv run pytest tests/integration/test_charts.py
```

## Add or change XY alignment behavior

### Files to edit

1. `src/lsl_viewer/core/alignment.py`
2. `src/lsl_viewer/config.py`
3. `LSL_Viewer/conf/config.yaml`
4. `src/lsl_viewer/viz/charts.py` if rendering changes
5. `tests/unit/test_alignment.py`
6. `tests/unit/test_state.py` if state changes

### Rules

- Alignment changes must remain display-only unless explicitly redesigned.
- Do not modify LSL buffers or replay arrays in place.
- Default mode should remain diagnostic (`raw_lsl`) unless the root timestamping contract changes.

### Validation

```bash
cd LSL_Viewer
uv run pytest tests/unit/test_alignment.py
uv run pytest tests/unit/test_state.py
uv run pytest tests/integration/test_charts.py
```

## Add a keyboard/control toggle

### Files to edit

1. `src/lsl_viewer/config.py`
2. `LSL_Viewer/conf/config.yaml`
3. `src/lsl_viewer/types.py` if state is required
4. `src/lsl_viewer/viz/panels.py`
5. `src/lsl_viewer/viz/charts.py` if the toggle changes rendering
6. tests

Current patterns:

| Control | Config | State/callback |
| --- | --- | --- |
| clear | `viewer.controls.clear_key` | `viz/panels.py` clear callback |
| pause | `viewer.controls.pause_key` | live/replay pause callback |
| XY lock | `viewer.xy_correlation.toggle_key` | `xy_lock_max_span` state |

## Add replay support

### CSV replay

Edit:

- `core/replay.py`,
- config path defaults,
- replay tests.

Test:

```bash
uv run pytest tests/integration/test_csv_replay.py
```

### XDF replay

Edit:

- `core/replay.py`,
- XDF stream/channel selection logic,
- dependency extras if package metadata changes.

Keep `dejitter_timestamps=False` unless there is a documented reason to alter XDF timestamps.

## Test matrix

| Test file | What it guards |
| --- | --- |
| `tests/unit/test_alignment.py` | XY interpolation, time shift, gap rejection, target signal choice. |
| `tests/unit/test_state.py` | Axis limits, XY max-span state, viewer state round-trip. |
| `tests/unit/test_timing.py` | Timing interval and clock validation metrics. |
| `tests/unit/test_replay_loaders.py` | Replay timebase/window helper behavior. |
| `tests/integration/test_charts.py` | ECharts options, render downsampling, clear/marker/XY updates. |
| `tests/integration/test_csv_replay.py` | CSV replay loading and required column behavior. |
| `tests/e2e/test_cli.py` | CLI/Hydra help, invalid modes, missing replay path errors. |

## Pre-merge checklist

- [ ] Config docs updated.
- [ ] Root stream-contract docs updated if a shared contract changed.
- [ ] Live and replay modes both handle the new behavior.
- [ ] Render downsampling still does not mutate source windows.
- [ ] Tests added or updated.
- [ ] Quickstart still runs with default config.
