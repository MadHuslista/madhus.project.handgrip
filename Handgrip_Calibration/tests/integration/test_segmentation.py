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


def test_segment_legacy_numbered_channels_uses_configured_numeric_fallbacks(tmp_path: Path) -> None:
    """Legacy CSVs with only channel_* columns must not use channel_0 as raw."""

    import pandas as pd

    session = generate_demo_session(tmp_path)
    cfg = load_config(Path(__file__).parents[2] / "conf" / "default.yaml")

    target = pd.read_csv(session / "target.csv")
    target_legacy = pd.DataFrame(
        {
            "timestamp_lsl": target["timestamp_lsl"],
            "channel_0": target["seq"],
            "channel_1": target["clock"],
            "channel_2": target["raw"],
            "channel_3": target["filtered"],
            "channel_4": target["filtered"],
            "channel_5": 0,
        }
    )
    target_legacy.to_csv(session / "target.csv", index=False)

    reference = pd.read_csv(session / "reference.csv")
    reference_legacy = pd.DataFrame(
        {
            "timestamp_lsl": reference["timestamp_lsl"],
            "channel_0": range(len(reference)),
            "channel_1": reference["clock"],
            "channel_2": reference["raw"],
            "channel_3": 0,
        }
    )
    reference_legacy.to_csv(session / "reference.csv", index=False)

    dataset = segment_accepted_holds(session, cfg)

    assert len(dataset) == 13
    assert set(dataset["target_signal"]) == {"channel_2"}
    assert set(dataset["reference_signal"]) == {"channel_2"}
    assert dataset["reference_force_median_N"].abs().max() < 120
    assert dataset["target_raw_median"].abs().median() > 1000
