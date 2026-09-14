"""The campaign: ten stages in difficulty order.

STAGES is the running order. Each entry is a module exposing the same
four names (NAME, DIFFICULTY, TUNING, build()), so main.py advances a
stage by stepping an index through this list and never needs to know
anything about a particular map.

Stage 1 is the original single level the game shipped with; 2-10 scale
up through bigger floor plans, less braiding and harsher hazards (see
levels/tuning.py).
"""

from levels import (
    level_01, level_02, level_03, level_04, level_05,
    level_06, level_07, level_08, level_09, level_10,
)

STAGES = [
    level_01, level_02, level_03, level_04, level_05,
    level_06, level_07, level_08, level_09, level_10,
]

STAGE_COUNT = len(STAGES)


def get(index):
    """Stage module at 0-based index, clamped into range."""
    return STAGES[max(0, min(STAGE_COUNT - 1, index))]


def label(index):
    """'Stage 3/10 - Records Office', for the HUD and results panel."""
    stage = get(index)
    return f"Stage {index + 1}/{STAGE_COUNT} - {stage.NAME}"
