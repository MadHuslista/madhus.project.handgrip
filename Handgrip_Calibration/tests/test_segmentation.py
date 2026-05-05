from pathlib import Path

from handgrip_calibration.config_schema import load_config
from handgrip_calibration.segmentation import segment_accepted_holds
from handgrip_calibration.synthetic import generate_demo_session


def test_segment_demo_session(tmp_path: Path) -> None:
    session = generate_demo_session(tmp_path)
    cfg = load_config(Path(__file__).parents[1] / "conf" / "default.yaml")
    dataset = segment_accepted_holds(session, cfg)
    assert len(dataset) == 13
    assert dataset["accepted_by_operator"].all()
    assert dataset["target_n_samples"].min() > 20
