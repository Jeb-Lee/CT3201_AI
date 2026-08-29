"""One object that owns every hazard system and answers the two questions
the rest of the game actually asks:

    damage_per_second(rect) -> float      # health drain for a body here
    entry_cost(cell)        -> float      # A* surcharge for the AI
    move_multiplier(x, y)   -> 0..1       # smoke slowdown
    vision_multiplier(x, y) -> 0..1       # smoke closing in the view

Keeping the aggregation here means Player, RescueAgent and main.py don't
each need to know which hazards exist -- they take a HazardField and ask.
Adding a hazard later is: build it in __init__, add it to update()/draw(),
fold it into the query methods.
"""

import pygame

from settings import (
    SMOKE_SLOW_AT_FULL, SMOKE_VISION_AT_FULL, DEBRIS_WARN_COLOR,
    DEBRIS_PENDING_COST,
)
from hazards import FireSystem
from panels import SparkPanelSystem
from debris import DebrisSystem
from doors import LockedDoorSystem


class HazardField:
    def __init__(self, tilemap, seed, protected_cells_fn, occupied_cells_fn):
        self.tilemap = tilemap
        self.fire = FireSystem(tilemap)
        self.doors = LockedDoorSystem(tilemap, seed=seed)  # picks cells, unlocked
        self.panels = SparkPanelSystem(
            tilemap,
            exclude_cells=[self.fire.ignition_cell, *self.doors.reserved_cells()],
            seed=seed,
        )
        self.debris = DebrisSystem(tilemap, protected_cells_fn, occupied_cells_fn)

    def reserved_cells(self):
        """Everything victims should avoid spawning on."""
        return {self.fire.ignition_cell, *self.panels.panels, *self.doors.reserved_cells()}

    def activate_door(self):
        """Lock the door -- called after victims are placed so they can
        spawn on either side of it."""
        self.doors.activate()

    @property
    def ignition_cell(self):
        return self.fire.ignition_cell

    # ------------------------------------------------------------------ tick
    def update(self, dt):
        self.fire.update(dt)
        self.panels.update(dt)
        self.debris.update(dt)

    # ------------------------------------------------------------------ queries
    def damage_per_second(self, rect):
        return self.fire.damage_rect(rect) + self.panels.damage_rect(rect)

    def entry_cost(self, cell):
        """A* cost_fn: extra cost of stepping into `cell`. Debris and a
        locked door are handled by tilemap.is_walkable (they're in
        dynamic_blocked), so this only has to price the *passable*
        hazards -- fire, smoke, panels -- plus a heavy nudge away from a
        tile that's visibly cracking, so the AI doesn't route into a
        collapse it can already see coming."""
        c = self.fire.tile_cost(cell) + self.panels.tile_cost(cell)
        if cell == self.debris.pending_cell:
            c += DEBRIS_PENDING_COST
        return c

    def move_multiplier(self, x, y):
        density = self.fire.smoke_density_px(x, y)
        return 1.0 - (1.0 - SMOKE_SLOW_AT_FULL) * density

    def vision_multiplier(self, x, y):
        density = self.fire.smoke_density_px(x, y)
        return 1.0 - (1.0 - SMOKE_VISION_AT_FULL) * density

    # ------------------------------------------------------------------ draw
    def draw_ground(self, surface, camera_offset):
        """Hazards that sit on the floor, drawn before characters."""
        self.panels.draw(surface, camera_offset)
        self.fire.draw(surface, camera_offset)
        self.doors.draw(surface, camera_offset)
        self._draw_debris_warning(surface, camera_offset)

    def _draw_debris_warning(self, surface, camera_offset):
        cell = self.debris.pending_cell
        if cell is None:
            return
        ox, oy = camera_offset
        ts = self.tilemap.tile_size
        frac = self.debris.pending_frac
        x, y = cell[0] * ts - ox, cell[1] * ts - oy
        overlay = pygame.Surface((ts, ts), pygame.SRCALPHA)
        overlay.fill((*DEBRIS_WARN_COLOR, int(40 + 120 * frac)))
        surface.blit(overlay, (x, y))
        # crack lines that grow as it's about to give
        n = 2 + int(frac * 4)
        for i in range(n):
            fx = x + (i + 1) * ts / (n + 1)
            pygame.draw.line(surface, (60, 55, 48), (fx, y + 4), (fx - 8, y + ts - 4), 2)
