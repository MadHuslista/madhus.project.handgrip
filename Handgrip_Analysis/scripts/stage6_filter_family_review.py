#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(ROOT / 'src'))

from handgrip_review.common import (
    apply_filter,
    best_event_metrics,
    dominant_psd_peaks,
    ensure_dir,
    load_capture,
    load_filter_specs,
    save_json,
    welch_psd,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Review filter families across rest + dynamic captures')
    p.add_argument('--rest-input', required=True)
    p.add_argument('--dynamic-inputs', nargs='+', required=True)
    p.add_argument('--config', required=True)
    p.add_argument('--outdir', required=True)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    outdir = ensure_dir(args.outdir)

    t_rest, y_rest, fs_rest, _ = load_capture(args.rest_input)
    f_rest, p_rest = welch_psd(y_rest, fs_rest)
    peaks = dominant_psd_peaks(f_rest, p_rest)
    peaks.to_csv(outdir / 'rest_psd_peaks.csv', index=False)

    raw_dynamic = {}
    for path in args.dynamic_inputs:
        t, y, fs, _ = load_capture(path)
        raw_dynamic[path] = (t, y, fs, best_event_metrics(y, t, fs))

    rows = []
    specs = load_filter_specs(args.config)
    for spec in specs:
        name = spec['name']
        y_rest_f = apply_filter(y_rest, fs_rest, spec)
        f_f, p_f = welch_psd(y_rest_f, fs_rest)
        hf_mask = (f_f >= 30.0) & (f_f <= 49.0)
        row = {
            'filter': name,
            'rest_std': float(pd.Series(y_rest_f).std()),
            'rest_peak_to_peak': float(y_rest_f.max() - y_rest_f.min()),
            'rest_hf_30_49_sum': float(p_f[hf_mask].sum()) if hf_mask.any() else float('nan'),
        }
        peak_errs = []
        rise_errs = []
        time_errs = []
        slope_devs = []
        for path, (t, y, fs, raw_m) in raw_dynamic.items():
            filt_m = best_event_metrics(apply_filter(y, fs, spec), t, fs)
            label = Path(path).stem
            row[f'{label}_peak_error'] = filt_m['peak_value'] - raw_m['peak_value']
            row[f'{label}_peak_time_shift_s'] = filt_m['peak_time_s'] - raw_m['peak_time_s']
            row[f'{label}_rise_shift_s'] = filt_m['rise_10_90_s'] - raw_m['rise_10_90_s']
            row[f'{label}_max_dfdt_ratio'] = filt_m['max_dfdt'] / raw_m['max_dfdt'] if raw_m['max_dfdt'] else float('nan')
            peak_errs.append(abs(row[f'{label}_peak_error']) / max(abs(raw_m['peak_value']), 1.0))
            rise_errs.append(abs(row[f'{label}_rise_shift_s']) / max(abs(raw_m['rise_10_90_s']), 1e-6))
            time_errs.append(abs(row[f'{label}_peak_time_shift_s']) / 0.1)
            slope_devs.append(abs(1.0 - row[f'{label}_max_dfdt_ratio']))
        row['mean_peak_relative_error'] = float(pd.Series(peak_errs).mean())
        row['mean_rise_relative_error'] = float(pd.Series(rise_errs).mean())
        row['mean_peak_time_shift_norm'] = float(pd.Series(time_errs).mean())
        row['mean_dfdt_deviation'] = float(pd.Series(slope_devs).mean())
        rows.append(row)

    df = pd.DataFrame(rows)
    raw_rest_std = float(pd.Series(y_rest).std())
    df['rest_std_norm'] = df['rest_std'] / raw_rest_std
    # weighted score prioritizes waveform fidelity, then stationary denoising
    df['composite_score'] = (
        0.25 * df['rest_std_norm']
        + 0.35 * df['mean_peak_relative_error']
        + 0.10 * df['mean_rise_relative_error']
        + 0.10 * df['mean_peak_time_shift_norm']
        + 0.20 * df['mean_dfdt_deviation']
    )
    df = df.sort_values('composite_score', ascending=True)
    df.to_csv(outdir / 'filter_family_assessment.csv', index=False)
    save_json(outdir / 'summary.json', {
        'rest_input': str(Path(args.rest_input).resolve()),
        'dynamic_inputs': [str(Path(p).resolve()) for p in args.dynamic_inputs],
        'n_candidates': len(specs),
        'rest_psd_top_peaks_hz': peaks['frequency_hz'].tolist() if not peaks.empty else [],
        'top_ranked_filter': str(df.iloc[0]['filter']) if not df.empty else None,
    })

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.bar(df['filter'], df['composite_score'])
    ax.set_title('Composite filter score (lower is better)')
    ax.set_ylabel('Score')
    ax.set_xlabel('Candidate')
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, axis='y')
    fig.tight_layout()
    fig.savefig(outdir / 'composite_score.png', dpi=150)
    plt.close(fig)

    fig2, ax2 = plt.subplots(figsize=(10, 5))
    ax2.semilogy(f_rest, p_rest, label='raw rest', linewidth=1.1)
    top_names = df['filter'].head(min(4, len(df))).tolist()
    spec_map = {s['name']: s for s in specs}
    for name in top_names:
        y_f = apply_filter(y_rest, fs_rest, spec_map[name])
        f_f, p_f = welch_psd(y_f, fs_rest)
        ax2.semilogy(f_f, p_f, label=name)
    ax2.set_title('Rest PSD — raw vs top-ranked candidates')
    ax2.set_xlabel('Frequency [Hz]')
    ax2.set_ylabel('PSD [counts^2/Hz]')
    ax2.grid(True)
    ax2.legend(fontsize=8)
    fig2.tight_layout()
    fig2.savefig(outdir / 'rest_psd_top_candidates.png', dpi=150)
    plt.close(fig2)


if __name__ == '__main__':
    main()
