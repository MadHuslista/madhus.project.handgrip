# Run from repository root: Handgrip_Analysis/
# Install once if needed:
# uv sync
# source .venv/bin/activate

# ============================================================
# One-call execution: all currently runnable manifest-driven stages
# ============================================================
ha-run-all manifest=data/manifests/analysis_stages_1_4_manifest.csv base_outdir=data/analysis_results stages=stage1,stage2,stage3,stage4 && \
ha-stage stage=stage6 manifest=data/manifests/stage6_filter_review_manifest.csv outdir=data/analysis_results/stage6 filter_config=conf/filters/candidates.yaml

# ============================================================
# Stage-by-stage execution using the full Stage 1-4 manifest
# ============================================================
ha-stage stage=stage1 manifest=data/manifests/analysis_stages_1_4_manifest.csv outdir=data/analysis_results/stage1
ha-stage stage=stage2 manifest=data/manifests/analysis_stages_1_4_manifest.csv outdir=data/analysis_results/stage2
ha-stage stage=stage3 manifest=data/manifests/analysis_stages_1_4_manifest.csv outdir=data/analysis_results/stage3
ha-stage stage=stage4 manifest=data/manifests/analysis_stages_1_4_manifest.csv outdir=data/analysis_results/stage4
ha-stage stage=stage6 manifest=data/manifests/stage6_filter_review_manifest.csv outdir=data/analysis_results/stage6 filter_config=conf/filters/candidates.yaml

# ============================================================
# Stage-by-stage execution using per-stage convenience manifests
# ============================================================
ha-stage stage=stage1 manifest=data/manifests/stage1_manifest.csv outdir=data/analysis_results/stage1
ha-stage stage=stage2 manifest=data/manifests/stage2_manifest.csv outdir=data/analysis_results/stage2
ha-stage stage=stage3 manifest=data/manifests/stage3_manifest.csv outdir=data/analysis_results/stage3
ha-stage stage=stage4 manifest=data/manifests/stage4_manifest.csv outdir=data/analysis_results/stage4
ha-stage stage=stage6 manifest=data/manifests/stage6_filter_review_manifest.csv outdir=data/analysis_results/stage6 filter_config=conf/filters/candidates.yaml

# ============================================================
# Optional condition-level Stage 4 execution
# ============================================================
ha-stage stage=stage4 condition=fast_max manifest=data/manifests/analysis_stages_1_4_manifest.csv outdir=data/analysis_results/stage4_fast_max
ha-stage stage=stage4 condition=ramp_hold manifest=data/manifests/analysis_stages_1_4_manifest.csv outdir=data/analysis_results/stage4_ramp_hold
ha-stage stage=stage4 condition=sustained_hold manifest=data/manifests/analysis_stages_1_4_manifest.csv outdir=data/analysis_results/stage4_sustained_hold

# ============================================================
# Optional condition-level Stage 6 execution
# ============================================================
ha-stage stage=stage6 condition=rest_after_warmup manifest=data/manifests/stage6_filter_review_manifest.csv outdir=data/analysis_results/stage6_rest_only filter_config=conf/filters/candidates.yaml
ha-stage stage=stage6 condition=fast_max manifest=data/manifests/stage6_filter_review_manifest.csv outdir=data/analysis_results/stage6_fast_max_only filter_config=conf/filters/candidates.yaml
ha-stage stage=stage6 condition=ramp_hold manifest=data/manifests/stage6_filter_review_manifest.csv outdir=data/analysis_results/stage6_ramp_hold_only filter_config=conf/filters/candidates.yaml
ha-stage stage=stage6 condition=sustained_hold manifest=data/manifests/stage6_filter_review_manifest.csv outdir=data/analysis_results/stage6_sustained_hold_only filter_config=conf/filters/candidates.yaml
