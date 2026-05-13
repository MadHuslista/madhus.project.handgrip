import json

from handgrip_calibration.markers import MarkerEvent


def test_marker_is_json_serializable() -> None:
    marker = MarkerEvent(event="hold_start", session_id="s1", trial_id="H01", target_force_N=10.0)
    encoded = marker.to_lsl_string()
    decoded = json.loads(encoded)
    assert decoded["schema"] == "handgrip_marker.v1"
    assert decoded["event"] == "hold_start"
    assert decoded["trial_id"] == "H01"
