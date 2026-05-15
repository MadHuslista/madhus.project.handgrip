"""Static-staircase protocol generation.

This file converts the YAML protocol into explicit trial descriptors. The
recorder uses these descriptors to prompt the operator and emit consistent
markers. The offline segmenter then uses those markers to select accepted holds.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config_schema import ProtocolConfig


@dataclass(frozen=True)
class Trial:
    """One planned static hold."""

    trial_id: str
    repeat_index: int
    level_index: int
    target_force_N: float
    direction: str


def generate_static_trials(protocol: ProtocolConfig) -> list[Trial]:
    # @brief Generate static staircase trial descriptors.
    #  @param protocol Protocol configuration defining levels and repeats.
    #  @return Ordered list of trial descriptors with inferred direction labels.
    """Generate staircase trials from the configured force levels.

    Direction is inferred locally from neighboring levels and is used later for
    hysteresis diagnostics.
    """

    trials: list[Trial] = []
    for repeat in range(1, protocol.repeats + 1):
        for idx, level in enumerate(protocol.levels_N, start=1):
            previous = protocol.levels_N[idx - 2] if idx > 1 else level
            if level > previous:
                direction = "ascending"
            elif level < previous:
                direction = "descending"
            else:
                direction = "flat"
            trial_id = f"R{repeat:02d}_H{idx:02d}_{level:g}N".replace(".", "p")
            trials.append(Trial(trial_id, repeat, idx, float(level), direction))
    return trials
