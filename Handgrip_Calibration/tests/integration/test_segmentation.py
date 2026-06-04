from pathlib import Path

from handgrip_calibration.config_schema import load_config
from handgrip_calibration.segmentation import segment_accepted_holds
from handgrip_calibration.synthetic import generate_demo_session


def test_segment_demo_session(tmp_path: Path) -> None:
    session = generate_demo_session(tmp_path)
    cfg = load_config(Path(__file__).parents[2] / "conf" / "default.yaml")
    dataset = segment_accepted_holds(session, cfg)
    assert len(dataset) == 13
    assert dataset["accepted_by_operator"].all()
    assert dataset["target_n_samples"].min() > 20



def test_segment_legacy_numbered_channels_resolves_raw_to_channel_2(tmp_path: Path) -> None:
    import json
    import pandas as pd
    import yaml

    session = tmp_path / "legacy_numbered_session"
    session.mkdir()
    target_rows = []
    ref_rows = []
    events = []
    t = 100.0
    for i, level in enumerate([0.0, 10.0, 10.0], start=1):
        trial = f"H{i:02d}"
        direction = "flat" if i == 1 else ("ascending" if i == 2 else "descending")
        events.extend(
            [
                {"event": "hold_start", "trial_id": trial, "target_force_N": level, "lsl_time": t, "payload": {"direction": direction, "repeat_index": 1, "level_index": i}},
                {"event": "stable_window_start", "trial_id": trial, "target_force_N": level, "lsl_time": t + 1.0},
                {"event": "hold_end", "trial_id": trial, "target_force_N": level, "lsl_time": t + 3.0},
                {"event": "trial_accept", "trial_id": trial, "target_force_N": level, "lsl_time": t + 3.1},
            ]
        )
        for j in range(30):
            ts = t + j * 0.1
            target_rows.append({"timestamp_lsl": ts, "channel_0": j, "channel_1": ts * 1e6, "channel_2": level * 1000 + j, "channel_3": 0, "channel_4": level * 1000 + j, "channel_5": 0})
        for j in range(100):
            ts = t + j * 0.03
            ref_rows.append({"timestamp_lsl": ts, "channel_0": j, "channel_1": ts, "channel_2": level, "channel_3": 0})
        t += 10.0
    pd.DataFrame(target_rows).to_csv(session / "target.csv", index=False)
    pd.DataFrame(ref_rows).to_csv(session / "reference.csv", index=False)
    with (session / "events.ndjson").open("w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")
    with (session / "session_manifest.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump({"streams": {"target": {}, "reference": {}}}, fh)

    cfg = load_config(Path(__file__).parents[2] / "conf" / "default.yaml")
    dataset = segment_accepted_holds(session, cfg)
    assert set(dataset["target_signal"]) == {"channel_2"}
    assert set(dataset["reference_signal"]) == {"channel_2"}
    assert dataset["target_raw_median"].abs().max() > 1000
    assert dataset["reference_force_median_N"].max() == 10.0


def test_direction_balanced_artifact_dataset(tmp_path: Path) -> None:
    import json
    import pandas as pd
    import yaml

    session = tmp_path / "artifact_session"
    session.mkdir()
    target_rows = []
    ref_rows = []
    events = []
    t = 1000.0
    trials = [
        ("H00", 0.0, "flat", 0.0, 0.0),
        ("H10A", 10.0, "ascending", 1000.0, 10.4),
        ("H10D", 10.0, "descending", 900.0, 9.6),
    ]
    for idx, (trial, level, direction, target_value, ref_value) in enumerate(trials, start=1):
        events.extend(
            [
                {"event": "hold_start", "trial_id": trial, "target_force_N": level, "lsl_time": t, "payload": {"direction": direction, "repeat_index": 1, "level_index": idx}},
                {"event": "stable_window_start", "trial_id": trial, "target_force_N": level, "lsl_time": t + 1.0},
                {"event": "hold_end", "trial_id": trial, "target_force_N": level, "lsl_time": t + 5.0},
                {"event": "trial_accept", "trial_id": trial, "target_force_N": level, "lsl_time": t + 5.1},
            ]
        )
        for j in range(60):
            ts = t + j * 0.1
            target_rows.append({"timestamp_lsl": ts, "channel_0": j, "channel_1": ts, "channel_2": target_value, "channel_3": 0, "channel_4": target_value, "channel_5": 0})
        for j in range(300):
            ts = t + j * 0.02
            ref_rows.append({"timestamp_lsl": ts, "channel_0": j, "channel_1": ts, "channel_2": ref_value, "channel_3": 0})
        t += 10.0
    pd.DataFrame(target_rows).to_csv(session / "target.csv", index=False)
    pd.DataFrame(ref_rows).to_csv(session / "reference.csv", index=False)
    with (session / "events.ndjson").open("w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")
    with (session / "session_manifest.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump({"streams": {"target": {}, "reference": {}}}, fh)

    cfg = load_config(Path(__file__).parents[2] / "conf" / "protocol_static_reversible_staircase_v3.yaml")
    dataset = segment_accepted_holds(session, cfg)
    ten = dataset[dataset["target_force_nominal_N"] == 10.0].iloc[0]
    assert ten["calibration_artifact_applied"]
    assert ten["target_raw_median"] == 950.0
    assert abs(ten["reference_force_median_N"] - 10.0) < 1e-9
    assert (session / "calibration_hold_dataset_raw.csv").exists()
    assert (session / "calibration_artifact_summary.csv").exists()
