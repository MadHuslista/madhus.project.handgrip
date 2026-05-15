# @package handgrip_analysis.stages
# @brief Trial-aware stage analyzer registry.

"""Trial-aware stage analyzer registry."""
from __future__ import annotations

from importlib import import_module
from types import ModuleType

STAGE_MODULES = {
    "stage1": "handgrip_analysis.stages.stage1_warmup",
    "stage2": "handgrip_analysis.stages.stage2_noise",
    "stage3": "handgrip_analysis.stages.stage3_drift",
    "stage4": "handgrip_analysis.stages.stage4_dynamics",
    "stage5": "handgrip_analysis.stages.stage5_interference",
    "stage6": "handgrip_analysis.stages.stage6_filters",
    "stage6_design": "handgrip_analysis.stages.stage6_filters",
    "stage6_review": "handgrip_analysis.stages.stage6_filters",
}


# @brief Resolve and import the stage analyzer module for a stage key.
# @param stage Stage identifier string.
# @return Imported Python module implementing the stage analysis entry points.
# @throws ValueError Raised when the stage key is unsupported.
def get_stage_module(stage: str) -> ModuleType:
    try:
        path = STAGE_MODULES[stage]
    except KeyError as exc:
        raise ValueError(f"Unsupported analysis stage: {stage!r}") from exc
    return import_module(path)
