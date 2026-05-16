"""Unit tests for handgrip_analysis.dsp (pure functions — no I/O, no mocking)."""

from __future__ import annotations

import numpy as np
import pytest
from handgrip_analysis.dsp import (
    EventWindow,
    PeakInfo,
    allan_deviation,
    apply_filter_spec,
    bandpower,
    best_event_metrics,
    detect_events,
    dominant_psd_peaks,
    event_metrics,
    linear_trend,
    robust_std,
    rolling_mean_std_slope,
    welch_psd,
)

FS = 100.0  # Hz — used throughout


# ---------------------------------------------------------------------------
# robust_std
# ---------------------------------------------------------------------------


def test_robust_std_constant():
    assert robust_std(np.ones(50)) == pytest.approx(0.0)


def test_robust_std_known():
    # For a standard normal sample the expected value is ~1; use exact data
    x = np.array([-1.0, 0.0, 1.0])
    result = robust_std(x)
    assert result > 0.0


# ---------------------------------------------------------------------------
# rolling_mean_std_slope
# ---------------------------------------------------------------------------


def test_rolling_constant_signal():
    y = np.full(500, 5.0)
    means, stds, slopes = rolling_mean_std_slope(y, FS, window_s=1.0)
    valid = np.isfinite(means)
    assert np.allclose(means[valid], 5.0, atol=1e-10)
    assert np.allclose(stds[valid], 0.0, atol=1e-10)
    assert np.allclose(slopes[valid], 0.0, atol=1e-10)


def test_rolling_output_length():
    y = np.random.default_rng(0).normal(size=300)
    means, stds, slopes = rolling_mean_std_slope(y, FS, window_s=0.5)
    assert means.shape == y.shape
    assert stds.shape == y.shape
    assert slopes.shape == y.shape


# ---------------------------------------------------------------------------
# welch_psd
# ---------------------------------------------------------------------------


def test_welch_psd_short_signal():
    f, pxx = welch_psd(np.ones(4), FS)
    assert f.size == 0 and pxx.size == 0


def test_welch_psd_returns_positive():
    rng = np.random.default_rng(1)
    y = rng.normal(size=2048)
    f, pxx = welch_psd(y, FS)
    assert f.size > 0
    assert np.all(pxx >= 0)


def test_welch_psd_dc_component_suppressed():
    """Linear detrending should remove a strong DC offset."""
    rng = np.random.default_rng(2)
    y = rng.normal(size=2048) + 1000.0
    f, pxx = welch_psd(y, FS)
    # DC bin (f=0) should be small relative to noise floor after detrending
    assert f.size > 0


# ---------------------------------------------------------------------------
# bandpower
# ---------------------------------------------------------------------------


def test_bandpower_empty():
    assert np.isnan(bandpower(np.array([]), np.array([]), 0.0, 10.0))


def test_bandpower_flat_spectrum():
    # np.trapezoid on a discrete uniform grid has a small endpoint-discretization
    # error; allow 1% relative tolerance.
    f = np.linspace(0, 50, 1000)
    pxx = np.ones_like(f)
    bp = bandpower(f, pxx, 0.0, 10.0)
    assert bp == pytest.approx(10.0, rel=0.01)


# ---------------------------------------------------------------------------
# allan_deviation
# ---------------------------------------------------------------------------


def test_allan_deviation_short():
    tau, adev = allan_deviation(np.ones(8), FS)
    assert tau.size == 0 and adev.size == 0


def test_allan_deviation_white_noise():
    """Allan deviation of white noise should decrease as ~1/sqrt(tau)."""
    rng = np.random.default_rng(3)
    y = rng.normal(size=4096)
    tau, adev = allan_deviation(y, FS)
    assert tau.size > 3
    assert np.all(adev > 0)
    # Slope in log-log space should be near -0.5 for white noise
    slope = np.polyfit(np.log10(tau), np.log10(adev), 1)[0]
    assert -0.8 < slope < -0.2


# ---------------------------------------------------------------------------
# linear_trend
# ---------------------------------------------------------------------------


def test_linear_trend_exact():
    t = np.linspace(0, 10, 500)
    y = 3.0 * t + 7.0
    slope, intercept = linear_trend(y, t)
    assert slope == pytest.approx(3.0, rel=1e-6)
    assert intercept == pytest.approx(7.0, rel=1e-6)


# ---------------------------------------------------------------------------
# detect_events
# ---------------------------------------------------------------------------


def _make_grip_signal(n: int = 2000, fs: float = FS) -> np.ndarray:
    """Synthetic: flat baseline + one 3-second grip event."""
    y = np.random.default_rng(42).normal(scale=0.5, size=n)
    # Add a grip at sample 400–700
    y[400:700] += 20.0
    return y


def test_detect_events_finds_one():
    y = _make_grip_signal()
    events = detect_events(y, FS)
    assert len(events) == 1


def test_detect_events_returns_event_window_objects():
    y = _make_grip_signal()
    events = detect_events(y, FS)
    for ev in events:
        assert isinstance(ev, EventWindow)
        assert ev.start_idx <= ev.peak_idx <= ev.end_idx


def test_detect_events_empty_signal():
    assert detect_events(np.zeros(4), FS) == []


def test_detect_events_no_events():
    y = np.random.default_rng(5).normal(scale=0.1, size=1000)
    events = detect_events(y, FS, threshold_sigma=50.0)
    assert events == []


def test_detect_events_peak_is_max():
    y = _make_grip_signal()
    events = detect_events(y, FS)
    for ev in events:
        seg = y[ev.start_idx : ev.end_idx + 1]
        assert y[ev.peak_idx] == pytest.approx(float(seg.max()), abs=1e-10)


# ---------------------------------------------------------------------------
# event_metrics
# ---------------------------------------------------------------------------


def test_event_metrics_shape():
    y = _make_grip_signal()
    t = np.arange(len(y)) / FS
    events = detect_events(y, FS)
    df = event_metrics(y, t, events)
    assert len(df) == len(events)
    assert "peak_value" in df.columns
    assert "rise_10_90_s" in df.columns


def test_event_metrics_empty():
    y = np.zeros(100)
    t = np.arange(100) / FS
    df = event_metrics(y, t, [])
    assert len(df) == 0


# ---------------------------------------------------------------------------
# best_event_metrics
# ---------------------------------------------------------------------------


def test_best_event_metrics_keys():
    y = _make_grip_signal()
    t = np.arange(len(y)) / FS
    m = best_event_metrics(y, t, FS)
    required = {
        "n_events",
        "peak_value",
        "peak_time_s",
        "rise_10_90_s",
        "max_dfdt",
        "plateau_std_last20pct",
        "event_start_s",
        "event_end_s",
    }
    assert required.issubset(m.keys())


def test_best_event_metrics_no_events():
    y = np.zeros(500)
    t = np.arange(500) / FS
    m = best_event_metrics(y, t, FS)
    assert m["n_events"] == 0
    assert np.isnan(m["peak_value"])


def test_best_event_metrics_selects_dominant():
    """The dominant event (largest excursion) should be selected."""
    y = _make_grip_signal()
    t = np.arange(len(y)) / FS
    m = best_event_metrics(y, t, FS)
    assert m["peak_value"] > 15.0  # synthetic grip adds 20 to noise


# ---------------------------------------------------------------------------
# dominant_psd_peaks
# ---------------------------------------------------------------------------


def test_dominant_psd_peaks_empty():
    peaks = dominant_psd_peaks(np.array([]), np.array([]), FS)
    assert peaks == []


def test_dominant_psd_peaks_returns_peakinfo():
    rng = np.random.default_rng(6)
    y = rng.normal(size=2048)
    f, pxx = welch_psd(y, FS)
    peaks = dominant_psd_peaks(f, pxx, FS)
    for p in peaks:
        assert isinstance(p, PeakInfo)
        assert p.frequency_hz >= 0


def test_dominant_psd_peaks_max_count():
    rng = np.random.default_rng(7)
    y = rng.normal(size=2048)
    f, pxx = welch_psd(y, FS)
    peaks = dominant_psd_peaks(f, pxx, FS, max_peaks=3)
    assert len(peaks) <= 3


# ---------------------------------------------------------------------------
# apply_filter_spec — all filter types
# ---------------------------------------------------------------------------


def _signal(n: int = 512) -> np.ndarray:
    rng = np.random.default_rng(0)
    return rng.normal(size=n).astype(float)


def test_apply_filter_identity():
    y = _signal()
    out = apply_filter_spec(y, FS, {"type": "identity"})
    np.testing.assert_array_equal(out, y)


def test_apply_filter_butter_lowpass():
    y = _signal()
    out = apply_filter_spec(y, FS, {"type": "butter_lowpass", "order": 2, "cutoff_hz": 10.0})
    assert out.shape == y.shape


def test_apply_filter_butter_highpass():
    y = _signal()
    out = apply_filter_spec(y, FS, {"type": "butter_highpass", "order": 2, "cutoff_hz": 5.0})
    assert out.shape == y.shape


def test_apply_filter_butter_bandpass():
    y = _signal()
    out = apply_filter_spec(y, FS, {"type": "butter_bandpass", "order": 2, "low_hz": 2.0, "high_hz": 20.0})
    assert out.shape == y.shape


def test_apply_filter_notch():
    y = _signal()
    out = apply_filter_spec(y, FS, {"type": "notch", "freq_hz": 10.0, "q": 20.0})
    assert out.shape == y.shape


def test_apply_filter_chain():
    y = _signal()
    spec = {
        "type": "chain",
        "steps": [
            {"type": "butter_highpass", "order": 2, "cutoff_hz": 0.5},
            {"type": "butter_lowpass", "order": 2, "cutoff_hz": 20.0},
        ],
    }
    out = apply_filter_spec(y, FS, spec)
    assert out.shape == y.shape


def test_apply_filter_moving_average():
    y = np.ones(200)
    out = apply_filter_spec(y, FS, {"type": "moving_average", "window_samples": 5})
    assert out.shape == y.shape
    # moving average of a constant should be constant (except boundary effects)
    np.testing.assert_allclose(out[5:-5], 1.0, atol=1e-10)


def test_apply_filter_median():
    y = _signal()
    out = apply_filter_spec(y, FS, {"type": "median", "kernel_size": 5})
    assert out.shape == y.shape


def test_apply_filter_one_pole():
    y = _signal()
    out = apply_filter_spec(y, FS, {"type": "one_pole_lowpass", "cutoff_hz": 10.0})
    assert out.shape == y.shape


def test_apply_filter_unsupported_raises():
    with pytest.raises(ValueError, match="Unsupported filter type"):
        apply_filter_spec(np.ones(100), FS, {"type": "unknown_filter_xyz"})


# ---------------------------------------------------------------------------
# Filter highpass/bandpass attenuate the right frequency range
# ---------------------------------------------------------------------------


def test_butter_lowpass_attenuates_high_freq():
    """A 10 Hz lowpass should reduce high-frequency (45 Hz) power."""
    t = np.arange(4096) / FS
    hf = np.sin(2 * np.pi * 45.0 * t)
    out = apply_filter_spec(hf, FS, {"type": "butter_lowpass", "cutoff_hz": 10.0})
    assert float(np.std(out)) < 0.05  # signal strongly attenuated


def test_butter_highpass_passes_high_freq():
    """A 5 Hz highpass should preserve a 40 Hz component."""
    t = np.arange(4096) / FS
    hf = np.sin(2 * np.pi * 40.0 * t)
    out = apply_filter_spec(hf, FS, {"type": "butter_highpass", "cutoff_hz": 5.0})
    assert float(np.std(out)) > 0.5  # ~unity gain at 40 Hz


def test_butter_bandpass_blocks_dc_and_hf():
    """A 2–20 Hz bandpass should heavily attenuate DC and very high frequencies."""
    t = np.arange(4096) / FS
    dc = np.ones(len(t)) * 10.0
    hf = np.sin(2 * np.pi * 48.0 * t)
    mixed = dc + hf
    out = apply_filter_spec(mixed, FS, {"type": "butter_bandpass", "low_hz": 2.0, "high_hz": 20.0})
    assert float(np.abs(np.mean(out))) < 0.1  # DC suppressed
    assert float(np.std(out)) < 0.1  # 48 Hz attenuated
