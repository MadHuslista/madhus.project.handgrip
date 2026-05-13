import pandas as pd

from handgrip_calibration.quality import compute_window_quality, detect_sequence_gaps


def test_compute_window_quality() -> None:
    df = pd.DataFrame({"timestamp_lsl": [0.0, 0.01, 0.02, 0.03], "raw": [1.0, 1.1, 1.2, 1.3]})
    q = compute_window_quality(df, time_col="timestamp_lsl", value_col="raw")
    assert q.n_samples == 4
    assert q.monotonic
    assert q.sample_rate_hz == 100.0
    assert q.slope_per_s > 0


def test_detect_sequence_gaps() -> None:
    assert detect_sequence_gaps([1, 2, 3, 5]) == [(3, 3, 5)]
