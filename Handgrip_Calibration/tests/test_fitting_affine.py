from pathlib import Path

from handgrip_calibration.config_schema import load_config
from handgrip_calibration.fitting import fit_session
from handgrip_calibration.synthetic import generate_demo_session


def test_affine_fit_on_synthetic_session(tmp_path: Path) -> None:
    session = generate_demo_session(tmp_path)
    cfg = load_config(Path(__file__).parents[1] / "conf" / "default.yaml")
    _, result = fit_session(session, cfg)
    assert result.metrics.n_points >= 10
    assert abs(result.force_N_a - 0.0125) < 0.001
    assert abs(result.force_N_b + 125.0) < 10.0
