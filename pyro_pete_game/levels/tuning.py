"""Per-stage difficulty knobs.

The hazard systems each read their own constants out of settings.py,
which is right for a one-level game and wrong for a ten-stage campaign:
every stage would burn at the same rate and collapse on the same clock.
StageTuning is the override layer. A level module declares only what it
wants to differ; everything left as None falls back to the settings
value, so settings.py stays the single source of truth for the defaults
and stage 1 still plays exactly as it did before the campaign existed.

The fields map one-to-one onto constructor overrides on FireSystem,
SparkPanelSystem, DebrisSystem, LockedDoorSystem and RescueAgent -- see
HazardField.__init__, which is the only place that unpacks this.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class StageTuning:
    # --- fire ---
    # Seconds before the fire front is expected to reach the exit. Lower
    # is harsher: it is the stage's real time limit.
    fire_seconds_to_exit: Optional[float] = None

    # Seconds per ring of spread, overriding the rate derived from
    # fire_seconds_to_exit. This is the knob that actually controls how
    # fast the building fills, and on these maps it is the one that
    # matters. The derived rate is seconds_to_exit / ignition-to-exit
    # distance, so a stage whose fire starts a long way from the exit
    # gets a *faster* per-ring spread out of the same budget -- measured
    # headless, stage 2 burned out faster than stage 1 despite a longer
    # timer, because its ignition point sits 40 steps from the exit
    # rather than 28. Setting the interval directly makes the spread rate
    # comparable across stages of different shapes.
    fire_spread_interval: Optional[float] = None

    # --- spark panels ---
    panel_count: Optional[int] = None

    # --- ceiling collapse ---
    debris_interval: Optional[float] = None   # seconds between collapses
    debris_max_tiles: Optional[int] = None

    # --- locked door ---
    door_enabled: Optional[bool] = None

    # --- occupants to rescue ---
    victim_count: Optional[int] = None

    # --- the opponent ---
    # Multiplier on AGENT_SPEED. Above 1.0 the AI is a harder race; the
    # maze is also bigger on later stages, so this rises gently -- the
    # difficulty should come mostly from the building, not from an AI
    # that simply outruns Pete on raw speed.
    agent_speed_scale: float = 1.0


DEFAULT = StageTuning()
