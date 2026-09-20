"""Fire + smoke hazard: spreads from an ignition point over time.

Fire spreads by flood fill one ring per spread tick, so the BFS distance
from the ignition point to the exit is (close to) the number of ticks it
takes to reach the exit. We use that to pick a spread interval that lands
the fire at the exit roughly FIRE_TARGET_SECONDS_TO_EXIT seconds after
ignition regardless of maze size, instead of hardcoding a rate that only
works for one map. (With a braided maze the flood front can take a
slightly shorter loop, so the fire may reach the exit a little early --
close enough for a pacing knob.)

Fire doesn't block movement (see tilemap.is_walkable, which this only
reads from, never writes to) -- it's a hazard layered on top of the floor,
not a new kind of wall. Two things read back out of this system:

  * damage_rect(rect)      -- health drain/sec for anything standing in it
  * tile_cost(cell)        -- routing surcharge so the AI's A* avoids it
  * smoke_density(cell/px) -- 0..1 smoke thickness; callers use it to slow
                              movement and shrink the view

Smoke is derived from the fire each spread tick: burning tiles are full
smoke, the ring of floor tiles around them is thinner smoke. The old
drifting-particle layer is kept purely for looks on top of that.
"""

import math
import random

import pygame

from settings import (
    FIRE_TARGET_SECONDS_TO_EXIT, FIRE_COLOR, FIRE_ALPHA, FIRE_TILE_COST,
    FIRE_SCORCH_COLOR, FIRE_FLAME_COLORS, HEALTH_DRAIN_PER_SECOND,
    SMOKE_COLOR, SMOKE_SPAWN_RATE, SMOKE_MAX_PARTICLES,
    SMOKE_MIN_LIFETIME, SMOKE_MAX_LIFETIME, SMOKE_RISE_SPEED,
    SMOKE_DRIFT_SPEED, SMOKE_MIN_RADIUS, SMOKE_MAX_RADIUS, SMOKE_MAX_ALPHA,
    SMOKE_SPREAD_FALLOFF, SMOKE_TILE_COST, SMOKE_HAZE_COLOR, SMOKE_HAZE_MAX_ALPHA,
)
from pathfinding import bfs_distances as _bfs_distances, NEIGHBOR_STEPS

MIN_SPREAD_INTERVAL = 0.15


class FireSystem:
    def __init__(self, tilemap, seconds_to_exit=None, exclude_cells=(),
                 spread_interval=None):
        """seconds_to_exit overrides FIRE_TARGET_SECONDS_TO_EXIT for this
        stage (see levels.tuning.StageTuning); None keeps the default.

        exclude_cells are cells the fire must not start on or beside --
        in practice the locked door's key. Igniting on the key made some
        of the bigger stages unwinnable: the key is a mandatory fetch, so
        a fire sitting on it forced both rescuers to walk through flame
        with no alternative, and the AI died there every single run."""
        self.tilemap = tilemap
        self.seconds_to_exit = (FIRE_TARGET_SECONDS_TO_EXIT
                                if seconds_to_exit is None else seconds_to_exit)

        dist_from_exit = _bfs_distances(tilemap, tilemap.exit_cell)
        dist_from_spawn = _bfs_distances(tilemap, tilemap.spawn_cell)
        spawn_to_exit = max(1, dist_from_exit.get(tilemap.spawn_cell, 1))

        # "Farthest from the exit" alone isn't enough to guarantee runway --
        # in a maze that runs corner-to-corner, the cell farthest from the
        # exit tends to be the cell *closest* to spawn, which would ignite
        # right on top of the player. Require some minimum graph distance
        # from spawn too, so the fire always starts somewhere Pete actually
        # has to walk toward rather than starting in his lap.
        min_spawn_distance = max(3, spawn_to_exit // 4)
        banned = set(exclude_cells)
        for col, row in tuple(banned):       # also spare their neighbours
            banned.update({(col + 1, row), (col - 1, row),
                           (col, row + 1), (col, row - 1)})
        candidates = [
            c for c in dist_from_exit
            if c != tilemap.spawn_cell and c not in banned
            and dist_from_spawn.get(c, 0) >= min_spawn_distance
        ]
        if not candidates:
            candidates = [c for c in dist_from_exit if c != tilemap.spawn_cell] or list(dist_from_exit.keys())
        self.ignition_cell = max(candidates, key=lambda c: dist_from_exit[c])

        distance_to_exit = max(1, dist_from_exit[self.ignition_cell])
        # An explicit per-ring interval wins over the rate derived from
        # the exit budget -- see levels.tuning.StageTuning for why the
        # campaign sets it directly.
        derived = self.seconds_to_exit / distance_to_exit
        self.spread_interval = max(
            MIN_SPREAD_INTERVAL,
            derived if spread_interval is None else spread_interval,
        )
        # rough estimate of when the flame front reaches the exit tile,
        # for the HUD countdown. Braiding / debris can shift it a little.
        self._time_to_exit = distance_to_exit * self.spread_interval
        self.elapsed = 0.0

        self.burning = {self.ignition_cell}
        self._frontier = {self.ignition_cell}
        self._timer = 0.0
        self._anim_t = 0.0
        self._smoke_field = {}
        self._rebuild_smoke_field()

        self._tile_overlay = pygame.Surface(
            (tilemap.tile_size, tilemap.tile_size), pygame.SRCALPHA
        )
        self._tile_overlay.fill((*FIRE_COLOR, FIRE_ALPHA))
        self._scorch_overlay = pygame.Surface(
            (tilemap.tile_size, tilemap.tile_size), pygame.SRCALPHA
        )
        self._scorch_overlay.fill((*FIRE_SCORCH_COLOR, 150))
        self._haze_overlay = pygame.Surface(
            (tilemap.tile_size, tilemap.tile_size), pygame.SRCALPHA
        )

        # Decorative drifting particles -- never touch self.burning,
        # damage_rect() or collision, so they can't affect gameplay.
        self._smoke = []  # list of dicts: x, y, age, lifetime, radius, sway_phase

    # ------------------------------------------------------------------ spread
    @property
    def exit_on_fire(self):
        return self.tilemap.exit_cell in self.burning

    @property
    def seconds_to_exit_fire(self):
        """Estimated seconds until the flame front reaches the exit tile
        (0 once it has). For the HUD countdown."""
        if self.exit_on_fire:
            return 0.0
        return max(0.0, self._time_to_exit - self.elapsed)

    @property
    def seconds_to_exit_total(self):
        """The countdown's starting value: the estimate at the moment the fire
        started. seconds_to_exit_fire / this is how far through it we are
        (the HUD's draining bar)."""
        return self._time_to_exit

    def update(self, dt):
        self._anim_t += dt
        self.elapsed += dt
        if self._frontier:
            self._timer += dt
            changed = False
            while self._timer >= self.spread_interval and self._frontier:
                self._timer -= self.spread_interval
                new_frontier = set()
                for col, row in self._frontier:
                    for dc, dr in NEIGHBOR_STEPS:
                        nxt = (col + dc, row + dr)
                        if nxt in self.burning:
                            continue
                        # fire can't jump a wall, but it *can* burn a tile
                        # that debris later blocked -- it checks the raw
                        # grid, not is_walkable
                        if self.tilemap.tile_at(*nxt) != "#":
                            self.burning.add(nxt)
                            new_frontier.add(nxt)
                            changed = True
                self._frontier = new_frontier
            if changed:
                self._rebuild_smoke_field()

        self._update_smoke(dt)

    def _rebuild_smoke_field(self):
        field = {}
        for cell in self.burning:
            field[cell] = 1.0
        for col, row in self.burning:
            for dc, dr in NEIGHBOR_STEPS:
                nxt = (col + dc, row + dr)
                if self.tilemap.tile_at(*nxt) == "#":
                    continue
                field[nxt] = max(field.get(nxt, 0.0), SMOKE_SPREAD_FALLOFF)
        self._smoke_field = field

    # ------------------------------------------------------------------ queries
    def damage_rect(self, rect):
        """Health lost per second for a body occupying `rect` (fire only)."""
        for cell in self.tilemap.tiles_overlapping(rect):
            if cell in self.burning:
                return HEALTH_DRAIN_PER_SECOND
        return 0.0

    def is_rect_burning(self, rect):
        return any(cell in self.burning for cell in self.tilemap.tiles_overlapping(rect))

    def tile_cost(self, cell):
        """A* surcharge for entering `cell`: full for fire, a lighter
        nudge for smoke, so the AI treats 'through the fire' as a last
        resort and 'through the haze' as merely unpleasant."""
        c = 0.0
        if cell in self.burning:
            c += FIRE_TILE_COST
        c += SMOKE_TILE_COST * self._smoke_field.get(cell, 0.0)
        return c

    def smoke_density(self, cell):
        return self._smoke_field.get(cell, 0.0)

    def smoke_density_px(self, x, y):
        ts = self.tilemap.tile_size
        return self._smoke_field.get((int(x // ts), int(y // ts)), 0.0)

    # ------------------------------------------------------------------ smoke fx
    def _update_smoke(self, dt):
        ts = self.tilemap.tile_size
        if len(self._smoke) < SMOKE_MAX_PARTICLES:
            spawn_chance = SMOKE_SPAWN_RATE * dt
            for col, row in self.burning:
                if len(self._smoke) >= SMOKE_MAX_PARTICLES:
                    break
                if random.random() < spawn_chance:
                    self._smoke.append({
                        "x": col * ts + ts / 2 + random.uniform(-ts * 0.2, ts * 0.2),
                        "y": row * ts + ts / 2,
                        "age": 0.0,
                        "lifetime": random.uniform(SMOKE_MIN_LIFETIME, SMOKE_MAX_LIFETIME),
                        "radius": random.uniform(SMOKE_MIN_RADIUS, SMOKE_MAX_RADIUS),
                        "sway_phase": random.uniform(0, math.tau),
                    })

        alive = []
        for p in self._smoke:
            p["age"] += dt
            if p["age"] >= p["lifetime"]:
                continue
            p["y"] -= SMOKE_RISE_SPEED * dt
            p["x"] += math.sin(p["age"] * 2.0 + p["sway_phase"]) * SMOKE_DRIFT_SPEED * dt
            alive.append(p)
        self._smoke = alive

    def _draw_flames(self, surface, x, y, ts, phase):
        """A few flickering flame tongues per burning tile."""
        t = self._anim_t * 6.0 + phase
        base_y = y + ts - 4
        for i, cx_frac in enumerate((0.5, 0.32, 0.68)):
            wobble = math.sin(t + i * 2.1)
            cx = x + ts * cx_frac + wobble * 3
            h = ts * (0.42 + 0.14 * math.sin(t * 1.3 + i)) - i * 3
            w = ts * 0.26
            for j, colr in enumerate(FIRE_FLAME_COLORS):
                k = 1.0 - j * 0.32
                pygame.draw.polygon(surface, colr, [
                    (cx - w * k, base_y),
                    (cx + w * k, base_y),
                    (cx + wobble * 2, base_y - h * k),
                ])

    def draw(self, surface, camera_offset):
        ox, oy = camera_offset
        ts = self.tilemap.tile_size
        sw, sh = surface.get_size()

        def on_screen(x, y):
            return -ts < x < sw and -ts < y < sh

        # functional smoke haze -- drawn so the player can see the thing
        # that's slowing them / shrinking their view
        for cell, density in self._smoke_field.items():
            if cell in self.burning:
                continue
            x, y = cell[0] * ts - ox, cell[1] * ts - oy
            if not on_screen(x, y):
                continue
            self._haze_overlay.fill((*SMOKE_HAZE_COLOR, int(SMOKE_HAZE_MAX_ALPHA * density)))
            surface.blit(self._haze_overlay, (x, y))

        for col, row in self.burning:
            x, y = col * ts - ox, row * ts - oy
            if not on_screen(x, y):
                continue
            # scorched base + fire tint, then flickering flames on top so a
            # burning tile actually reads as fire rather than a red wash
            surface.blit(self._scorch_overlay, (x, y))
            surface.blit(self._tile_overlay, (x, y))
            self._draw_flames(surface, x, y, ts, col * 13 + row * 7)

        for p in self._smoke:
            life_frac = p["age"] / p["lifetime"]
            radius = p["radius"] * (0.7 + 0.6 * life_frac)
            alpha = max(0, round(SMOKE_MAX_ALPHA * (1.0 - life_frac)))
            if alpha <= 0:
                continue
            size = max(1, round(radius * 2))
            particle_surface = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.circle(
                particle_surface, (*SMOKE_COLOR, alpha), (size / 2, size / 2), radius
            )
            surface.blit(particle_surface, (p["x"] - ox - radius, p["y"] - oy - radius))
