# Adding a New Calibration Protocol

## Summary

- Calibration protocols live under `Handgrip_Calibration/conf/` and define operator flow, stream requirements, outputs, and analysis assumptions.
- The current primary protocol is `conf/protocol_static_reversible_staircase_v3.yaml`.
- New protocols must be classified as production, validation, diagnostic, smoke-test, or legacy.
- Every protocol must preserve raw target counts, reference force, event markers, and config snapshots.

## Files to edit

| File                                                                                                         | Purpose                                                       |
| ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------- |
| `Handgrip_Calibration/conf/protocol_<name>.yaml`                                                             | New protocol definition.                                      |
| [Handgrip_Calibration/docs/protocols.md](../../Handgrip_Calibration/docs/protocols.md)                     | Add protocol status and intended use.                         |
| [Handgrip_Calibration/docs/configuration.md](../../Handgrip_Calibration/docs/configuration.md)             | Document any new config keys/sections.                        |
| [Handgrip_Calibration/docs/recording.md](../../Handgrip_Calibration/docs/recording.md)                     | Update capture/session expectations if outputs change.        |
| [Handgrip_Calibration/docs/reports-and-outputs.md](../../Handgrip_Calibration/docs/reports-and-outputs.md) | Document new report/output artifacts.                         |
| [docs/workflows/handgrip-calibration.md](../workflows/handgrip-calibration.md)                             | Update only if protocol becomes operator-facing or canonical. |
| tests under `Handgrip_Calibration/tests/`                                                                    | Validate config parsing, preflight, dry-run behavior.         |

## Data contracts affected

A protocol can affect:

- required LSL streams,
- required channels,
- event marker names,
- segment labels,
- hold/static/dynamic trial definitions,
- session folder output classes,
- fitting dataset construction,
- report sections,
- validation acceptance criteria.

It must not redefine the root calibration contract unless deliberately migrated:

```text
reference_force_N = f(target_raw_count)
```

## Tests to update

Recommended checks:

```bash
cd Handgrip_Calibration
uv run handgrip-cal preflight --config conf/protocol_<name>.yaml
uv run handgrip-cal record --config conf/protocol_<name>.yaml --dry-run
uv run pytest
```

If the protocol creates new event/segment names, update tests that validate:

- event emission,
- segment extraction,
- fit dataset construction,
- report rendering.

## Validation workflow

1. Copy `conf/template.yaml` or the nearest existing protocol.
2. Rename metadata fields and protocol ID.
3. Define force levels, repeats, stage timing, and operator prompts.
4. Verify `session.copy_component_configs` includes:

```yaml
- ../LSL_Bridge/conf/config.yaml
- ../LSL_Viewer/conf/config.yaml
- ../RS485_GUI/config/config.yaml
```

5. Run `preflight`.
6. Run `record --dry-run` if supported.
7. Run a short smoke recording.
8. Inspect session folder for target/reference/event/config artifacts.
9. Run fit/report only if the protocol is intended for fitting.
10. Document protocol status in [Handgrip_Calibration/docs/protocols.md](../../Handgrip_Calibration/docs/protocols.md).

## Common failure modes

| Failure                                      | Cause                                          | Fix                                                           |
| -------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------- |
| Preflight fails                              | Missing stream/channel requirement             | Update protocol stream section or upstream configs.           |
| Config snapshot missing                      | Wrong relative config path                     | Use `../RS485_GUI/config/config.yaml`, not stale path.        |
| Recording completes but fit fails            | Protocol events do not produce fit segments    | Update segmentation rules or mark protocol validation-only.   |
| Report lacks expected section                | Report renderer not aware of protocol artifact | Update report docs and renderer/tests.                        |
| Operator runs diagnostic protocol as primary | Protocol status unclear                        | Mark production/diagnostic/legacy explicitly.                 |
| Hold labels ambiguous                        | Event naming not stable                        | Define canonical marker names before recording real sessions. |
