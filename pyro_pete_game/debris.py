"""Collapsing debris: the ceiling gives way as the run goes on.

Every DEBRIS_COLLAPSE_INTERVAL seconds a random floor tile is chosen to
collapse. It first shows cracks/dust for DEBRIS_WARN_SECONDS (a chance to
not be standing there), then becomes permanent rubble -- added to
tilemap.dynamic_blocked so it blocks movement and every pathfinder treats
it as a wall from then on.

A candidate tile is rejected if collapsing it would disconnect spawn, the
exit or any victim from the rest of the map, or if someone is standing on
it. So a run is never made unwinnable -- but the AI agent (and the player)
can and will have their planned route cut off mid-run and have to find
another way, which is the point: it turns a one-shot plan into
plan / act / re-plan.

Not seeded -- collapses are meant to vary run to run.
"""

import random

from settings import (
    DEBRIS_COLLAPSE_INTERVAL, DEBRIS_MAX_TILES, DEBRIS_MIN_SPAWN_DISTANCE,
    DEBRIS_WARN_SECONDS,
)
from pathfinding import bfs_distances

FLOOR = "."


class DebrisSystem:
    def __init__(self, tilemap, protected_cells_fn, occupied_cells_fn,
                 interval=None, max_tiles=None):
        """protected_cells_fn() -> iterable of cells that must stay
        connected (spawn, exit, every victim's cell).
        occupied_cells_fn() -> cells a rescuer is standing on right now."""
        self.tilemap = tilemap
        # Per-stage overrides (levels.tuning.StageTuning); None = settings.
        self.interval = DEBRIS_COLLAPSE_INTERVAL if interval is None else interval
        self.max_tiles = DEBRIS_MAX_TILES if max_tiles is None else max_tiles
        self._protected = protected_cells_fn
        self._occupied = occupied_cells_fn
        self.debris = set()            # collapsed, impassable
        self._pending = None           # (cell, time_left) currently cracking
        self._timer = 0.0
        # last collapse (for a brief screen shake / sound hook in main)
        self.just_collapsed = None

    # ------------------------------------------------------------------
    def update(self, dt):
        self.just_collapsed = None

        if self._pending is not None:
            cell, t_left = self._pending
            t_left -= dt
            if t_left <= 0:
                # only actually drop it if nobody wandered onto it while it
                # was cracking, and it's still safe to remove
                if cell not in self._occupied() and self._safe_to_block(cell):
                    self.tilemap.block_cell(cell, "debris")
                    self.debris.add(cell)
                    self.just_collapsed = cell
                self._pending = None
            else:
                self._pending = (cell, t_left)
            return

        if len(self.debris) >= self.max_tiles:
            return

        self._timer += dt
        if self._timer >= self.interval:
            self._timer -= self.interval
            cell = self._pick_collapse_cell()
            if cell is not None:
                self._pending = (cell, DEBRIS_WARN_SECONDS)

    # ------------------------------------------------------------------
    def _pick_collapse_cell(self):
        tm = self.tilemap
        occupied = set(self._occupied())
        protected = set(self._protected())
        candidates = [
            (c, r)
            for r in range(tm.rows) for c in range(tm.cols)
            if tm.grid[r][c] == FLOOR
            and (c, r) not in self.debris
            and (c, r) not in occupied
            and (c, r) not in protected
            and (c, r) not in tm.dynamic_blocked
        ]
        random.shuffle(candidates)
        for cell in candidates:
            if self._far_enough(cell) and self._safe_to_block(cell):
                return cell
        return None

    def _far_enough(self, cell):
        c, r = cell
        sc, sr = self.tilemap.spawn_cell
        return abs(c - sc) + abs(r - sr) >= DEBRIS_MIN_SPAWN_DISTANCE

    def _safe_to_block(self, cell):
        """Would blocking `cell` keep every protected cell reachable from
        spawn? Temporarily block it, run one BFS, restore."""
        tm = self.tilemap
        already = cell in tm.dynamic_blocked
        tm.block_cell(cell, "debris")
        try:
            reach = bfs_distances(tm, tm.spawn_cell)
            return all(p in reach for p in self._protected())
        finally:
            if not already:
                tm.unblock_cell(cell)

    # ------------------------------------------------------------------
    @property
    def pending_cell(self):
        return None if self._pending is None else self._pending[0]

    @property
    def pending_frac(self):
        """0 -> just started cracking, 1 -> about to drop."""
        if self._pending is None:
            return 0.0
        return 1.0 - self._pending[1] / DEBRIS_WARN_SECONDS
