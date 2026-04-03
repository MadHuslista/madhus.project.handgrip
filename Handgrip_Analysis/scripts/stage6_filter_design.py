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
    ensure_dir,
    load_capture,
    load_filter_specs,
    save_json,
    welch_psd,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Enhanced stage 6 candidate benchmark for one calibration signal')
    p.add_argument('--input', required=True, help='Dynamic calibration signal to benchmark')
    p.add_argument('--rest-input', default=None, help='Optional rest capture used to quantify stationary noise impact')
    p.add_argument('--config', required=True, help='Candidate filter YAML')
    p.add_argument('--outdir', required=True)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    outdir = ensure_dir(args.outdir)
    t, y, fs, _ = load_capture(args.input)
    raw_metrics = best_event_metrics(y, t, fs)

    rest = None
    if args.rest_input:
        t_rest, y_rest, fs_rest, _ = load_capture(args.rest_input)
        rest = (t_rest, y_rest, fs_rest)

    rows = []
    specs = load_filter_specs(args.config)

    fig_time, ax_time = plt.subplots(figsize=(12, 5))
    ax_time.plot(t, y, label='raw', linewidth=1.1)
    fig_psd, ax_psd = plt.subplots(figsize=(10, 5))
    f_raw, p_raw = welch_psd(y, fs)
    if f_raw.size:
        ax_psd.semilogy(f_raw, p_raw, label='raw', linewidth=1.1)

    for spec in specs:
        name = spec['name']
        y_f = apply_filter(y, fs, spec)
        m = best_event_metrics(y_f, t, fs)
        row = {
            'filter': name,
            'n_events': m['n_events'],
            'peak_value': m['peak_value'],
            'peak_error_vs_raw': m['peak_value'] - raw_metrics['peak_value'],
            'peak_time_shift_s': m['peak_time_s'] - raw_metrics['peak_time_s'],
            'rise_10_90_shift_s': m['rise_10_90_s'] - raw_metrics['rise_10_90_s'],
            'max_dfdt_ratio_vs_raw': m['max_dfdt'] / raw_metrics['max_dfdt'] if raw_metrics['max_dfdt'] else float('nan'),
            'plateau_std_last20pct': m['plateau_std_last20pct'],
        }
        if rest is not None:
            _, y_rest, fs_rest = rest
            y_rest_f = apply_filter(y_rest, fs_rest, spec)
            row['rest_std'] = float(pd.Series(y_rest_f).std())
            f_rest, p_rest = welch_psd(y_rest_f, fs_rest)
            mask = (f_rest >= 30.0) & (f_rest <= 49.0)
            row['rest_bandpower_30_49_hz'] = float(pd.Series(p_rest[mask]).sum()) if mask.any() else float('nan')
        rows.append(row)
        ax_time.plot(t, y_f, label=name, alpha=0.8)
        f_f, p_f = welch_psd(y_f, fs)
        if f_f.size:
            ax_psd.semilogy(f_f, p_f, label=name, alpha=0.8)

    df = pd.DataFrame(rows)
    # sort to make low-distortion candidates easy to inspect
    sort_cols = ['peak_time_shift_s', 'rise_10_90_shift_s', 'peak_error_vs_raw']
    df = df.reindex(df['peak_error_vs_raw'].abs().sort_values().index)
    df.to_csv(outdir / 'filter_comparison.csv', index=False)
    save_json(outdir / 'summary.json', {
        'input': str(Path(args.input).resolve()),
        'rest_input': str(Path(args.rest_input).resolve()) if args.rest_input else None,
        'fs_hz': fs,
        'selected_event_raw_metrics': raw_metrics,
        'n_candidates': len(specs),
    })

    ax_time.set_title('Stage 6 dynamic overlay — selected calibration signal')
    ax_time.set_xlabel('Time [s]')
    ax_time.set_ylabel('Raw counts')
    ax_time.grid(True)
    ax_time.legend(fontsize=8, loc='best')
    fig_time.tight_layout()
    fig_time.savefig(outdir / 'time_overlay.png', dpi=150)
    plt.close(fig_time)

    ax_psd.set_title('Stage 6 dynamic PSD comparison')
    ax_psd.set_xlabel('Frequency [Hz]')
    ax_psd.set_ylabel('PSD [counts^2/Hz]')
    ax_psd.grid(True)
    ax_psd.legend(fontsize=8, loc='best')
    fig_psd.tight_layout()
    fig_psd.savefig(outdir / 'psd_overlay.png', dpi=150)
    plt.close(fig_psd)


if __name__ == '__main__':
    main()
