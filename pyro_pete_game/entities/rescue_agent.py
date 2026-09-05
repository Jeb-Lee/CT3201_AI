"""Autonomous AI-controlled rescue agent.

Runs alongside player-controlled Pete in the same maze, on the same rules:
it has health and takes hazard damage (entities matter for the human-vs-AI
comparison only if the AI can't just no-clip through fire), and it plans
with hazard-weighted A* (pathfinding.astar_path) over
HazardField.entry_cost, so it routes *around* fire / smoke / sparking
panels when a detour is cheaper and only bulls through when it isn't.

Because the world changes under it -- fire spreads, ceilings collapse, a
door unlocks when someone grabs the key -- it re-plans from its current
cell every AGENT_REPLAN_MIN_INTERVAL seconds rather than committing to one
route. `planned_route` is exposed so main.py can draw what the AI
currently intends.

It plans under **partial information**, like the player: it doesn't get a
map of victim locations -- it only "knows" a victim once it's come within
AGENT_VISION_TILES of one, and only knows the layout it has walked near.
So it can commit to exploring a direction, discover a victim (or a wall
of fire) that isn't where it hoped, and re-plan.

Goal selection:
  * nearest *known* idle victim by weighted distance (Dijkstra over the
    same cost function), i.e. nearest by effort, not by tile count
  * no known victim -> head for the nearest unexplored area
  * if a locked door stands between the agent and its goal and the key
    hasn't been collected, the key becomes the goal first
  * fully explored, nothing left to rescue -> head for the exit

It still doesn't mutate victim state itself -- pickup is the shared,
proximity-based path in main.py's _try_rescue, so whoever reaches a
victim first claims it.
"""

import math

import pygame

from settings import (
    AGENT_SPEED, AGENT_COLOR, AGENT_RADIUS, AGENT_REPLAN_MIN_INTERVAL,
    AGENT_ROUTE_COLOR, AGENT_ROUTE_ALPHA, AGENT_TRAIL_COLOR, AGENT_TRAIL_ALPHA,
    AGENT_VISION_TILES, HEALTH_MAX, TILE_SIZE,
)
from entities.victim import STATE_IDLE
from pathfinding import astar_path, weighted_distances

OUTLINE_COLOR = (255, 255, 255)
CORE_COLOR = (20, 20, 24)

# the agent is a little search-and-rescue drone -- geometric, so it's drawn
# from primitives (no sprite file): a dark body, four spinning rotors, and a
# pulsing scanner eye. Reads instantly as "this one is the AI".
_DRONE_BODY = (44, 52, 66)
_DRONE_ARM = (30, 34, 42)
_DRONE_ROTOR = (150, 190, 235)
_DRONE_EYE = (120, 235, 255)
_DRONE_DEAD = (86, 86, 92)


class RescueAgent:
    def __init__(self, tilemap, start_cell, hazard_field=None, stats=None):
        self.tilemap = tilemap
        self.hazards = hazard_field
        self.stats = stats
        self.x, self.y = tilemap.cell_center(*start_cell)
        self.current_cell = start_cell
        self.health = HEALTH_MAX

        self._waypoints = []       # pixel points still to walk
        self.planned_route = []    # cells, for drawing
        self._goal_cell = None
        self._replan_timer = 0.0
        self._finished = False
        self._route_surface = None  # lazily made once, reused every frame
        self._anim_t = 0.0
        self._heading = (0.0, 1.0)  # unit-ish vector, for the drone's nose

        # partial observability: the agent only knows a victim once it's
        # seen one, and only "knows" the map it has walked near
        self.explored = {start_cell}
        self.known_victims = set()   # victim objects it has spotted
        self.trail_cells = {start_cell}  # every cell it has actually walked

    # ------------------------------------------------------------------
    def get_rect(self, radius=AGENT_RADIUS):
        r = pygame.Rect(0, 0, radius * 2, radius * 2)
        r.center = (round(self.x), round(self.y))
        return r

    @property
    def is_dead(self):
        return self.health <= 0

    @property
    def done(self):
        """Nothing left to do -- reached the exit with no reachable idle
        victims, or dead."""
        return self._finished or self.is_dead

    def _cost_fn(self):
        if self.hazards is None:
            return None
        return self.hazards.entry_cost

    # ------------------------------------------------------------------ senses
    def _observe(self, victims):
        """Fold everything within AGENT_VISION_TILES into explored, and
        note any victim seen. No wall occlusion -- a plain radius, same
        model as the player's fog."""
        r = AGENT_VISION_TILES
        cc, cr = self.current_cell
        rr = int(r) + 1
        tm = self.tilemap
        for row in range(max(0, cr - rr), min(tm.rows, cr + rr + 1)):
            for col in range(max(0, cc - rr), min(tm.cols, cc + rr + 1)):
                if (col - cc) ** 2 + (row - cr) ** 2 <= r * r:
                    self.explored.add((col, row))
        for v in victims:
            vx, vy = v.x / TILE_SIZE, v.y / TILE_SIZE
            if (vx - (cc + 0.5)) ** 2 + (vy - (cr + 0.5)) ** 2 <= (r + 0.5) ** 2:
                self.known_victims.add(v)

    def _nearest_unexplored(self, dist):
        """Closest reachable cell (by weighted distance) that the agent
        hasn't seen yet -- its exploration target when it has no known
        victim to chase."""
        best, best_d = None, float("inf")
        for cell, d in dist.items():
            if cell in self.explored:
                continue
            # a frontier cell: unexplored but adjacent to something explored
            if any((cell[0] + dc, cell[1] + dr) in self.explored
                   for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                if d < best_d:
                    best, best_d = cell, d
        return best

    # ------------------------------------------------------------------ goal
    def _choose_goal_cell(self, victims):
        """Chase the nearest *known* idle victim by weighted distance. No
        known victim -> explore toward the nearest unseen area. Nothing
        left to explore -> the exit. A locked door on the way makes the
        key the real next goal."""
        cost_fn = self._cost_fn()
        dist = weighted_distances(self.tilemap, self.current_cell, cost_fn)

        idle = [v.cell for v in self.known_victims
                if v.state == STATE_IDLE and v.cell in dist]
        if idle:
            target = min(idle, key=lambda c: dist[c])
        else:
            target = self._nearest_unexplored(dist) or self.tilemap.exit_cell

        doors = self.hazards.doors if self.hazards else None
        if doors and doors.enabled and not doors.key_collected and doors.key_cell:
            if astar_path(self.tilemap, self.current_cell, target, cost_fn) is None:
                return doors.key_cell
        return target

    # ------------------------------------------------------------------ tick
    def update(self, dt, victims):
        self._anim_t += dt  # rotors keep spinning even when it's parked
        if self._finished or self.is_dead:
            return

        # hazard damage -- same drain the player takes
        if self.hazards is not None:
            dps = self.hazards.damage_per_second(self.get_rect())
            if dps:
                self.health = max(0.0, self.health - dps * dt)
                if self.stats:
                    self.stats.add_damage(dps * dt)
                if self.is_dead:
                    if self.stats:
                        self.stats.mark_death()
                    return

        self.current_cell = (
            int(self.x // self.tilemap.tile_size),
            int(self.y // self.tilemap.tile_size),
        )
        self.trail_cells.add(self.current_cell)
        self._observe(victims)

        self._replan_timer -= dt
        if self._replan_timer <= 0 or not self._waypoints:
            self._replan(victims)
            self._replan_timer = AGENT_REPLAN_MIN_INTERVAL

        if not self._waypoints:
            # standing still with no path: done only if it's at the exit,
            # knows of no idle victim, and has nothing left to explore
            at_exit = self.current_cell == self.tilemap.exit_cell
            no_known = not any(v.state == STATE_IDLE for v in self.known_victims)
            fully_mapped = self._nearest_unexplored(
                weighted_distances(self.tilemap, self.current_cell, self._cost_fn())
            ) is None
            if at_exit and no_known and fully_mapped:
                self._finished = True
            return

        self._advance_along_path(dt)

    def _replan(self, victims):
        goal = self._choose_goal_cell(victims)
        path = astar_path(self.tilemap, self.current_cell, goal, self._cost_fn())

        if path is None:
            # boxed in for the moment (debris mid-collapse, etc.) -- hold
            # position and try again next tick
            self._waypoints = []
            self.planned_route = [self.current_cell]
            return

        if goal != self._goal_cell and self.stats:
            self.stats.mark_goal_change()
        if self.planned_route and self.planned_route != path and self.stats:
            self.stats.mark_replan()

        self._goal_cell = goal
        self.planned_route = path
        self._waypoints = [self.tilemap.cell_center(c, r) for c, r in path[1:]]

    def _advance_along_path(self, dt):
        tx, ty = self._waypoints[0]
        dx, dy = tx - self.x, ty - self.y
        dist = (dx * dx + dy * dy) ** 0.5
        if dist > 0.01:
            self._heading = (dx / dist, dy / dist)

        speed = AGENT_SPEED
        if self.hazards is not None:
            speed *= self.hazards.move_multiplier(self.x, self.y)
        step = speed * dt

        if dist <= step or dist == 0:
            moved = dist
            self.x, self.y = tx, ty
            self._waypoints.pop(0)
        else:
            moved = step
            self.x += dx / dist * step
            self.y += dy / dist * step
        if self.stats:
            self.stats.add_distance(moved)

    # ------------------------------------------------------------------ draw
    def draw_route(self, surface, camera_offset):
        """Two layers, both on top of the fog so the AI's whole journey is
        visible: a faint grey wash on every cell it has actually walked
        (where it's been) and, brighter, the A* line it currently intends
        to follow (where it's going). Plan vs. actual, at a glance."""
        ox, oy = camera_offset
        ts = self.tilemap.tile_size
        sw, sh = surface.get_size()
        if self._route_surface is None or self._route_surface.get_size() != (sw, sh):
            self._route_surface = pygame.Surface((sw, sh), pygame.SRCALPHA)
        layer = self._route_surface
        layer.fill((0, 0, 0, 0))

        pad = 6
        for c, r in self.trail_cells:
            x, y = c * ts - ox, r * ts - oy
            if -ts < x < sw and -ts < y < sh:
                pygame.draw.rect(layer, (*AGENT_TRAIL_COLOR, AGENT_TRAIL_ALPHA),
                                 (x + pad, y + pad, ts - 2 * pad, ts - 2 * pad))

        if len(self.planned_route) >= 2:
            pts = [(c * ts + ts / 2 - ox, r * ts + ts / 2 - oy)
                   for c, r in self.planned_route]
            pygame.draw.lines(layer, (*AGENT_ROUTE_COLOR, AGENT_ROUTE_ALPHA), False, pts, 3)
            for p in pts[1:-1]:
                pygame.draw.circle(layer, (*AGENT_ROUTE_COLOR, AGENT_ROUTE_ALPHA), p, 2)

        surface.blit(layer, (0, 0))

    def draw(self, surface, camera_offset):
        ox, oy = camera_offset
        cx, cy = self.x - ox, self.y - oy
        S = 52  # drone canvas
        d = pygame.Surface((S, S), pygame.SRCALPHA)
        mid = S / 2
        t = self._anim_t

        if self.is_dead:
            # crashed: tilted body, dead rotors, no eye
            pygame.draw.circle(d, (0, 0, 0, 60), (mid, mid + 4), 14)
            body = pygame.Surface((26, 18), pygame.SRCALPHA)
            body.fill(_DRONE_DEAD)
            body = pygame.transform.rotate(body, 24)
            d.blit(body, body.get_rect(center=(mid, mid)))
            for ax, ay in ((-14, -10), (14, -10), (-14, 10), (14, 10)):
                pygame.draw.line(d, _DRONE_ARM, (mid, mid), (mid + ax, mid + ay), 3)
                pygame.draw.circle(d, _DRONE_DEAD, (mid + ax, mid + ay), 4)
            surface.blit(d, d.get_rect(center=(round(cx), round(cy))))
            return

        bob = math.sin(t * 4.0) * 2.0
        sh = pygame.Surface((34, 15), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 70), sh.get_rect())
        surface.blit(sh, sh.get_rect(center=(round(cx), round(cy) + 12)))

        cy_d = mid + bob
        spin = t * 40.0
        for i, (ax, ay) in enumerate(((-15, -12), (15, -12), (-15, 12), (15, 12))):
            rx, ry = mid + ax, cy_d + ay
            pygame.draw.line(d, _DRONE_ARM, (mid, cy_d), (rx, ry), 4)
            pygame.draw.circle(d, (*_DRONE_ROTOR, 55), (rx, ry), 9)
            a = spin + i * 1.7
            for k in range(2):
                bl = a + k * math.pi
                pygame.draw.line(d, (*_DRONE_ROTOR, 190),
                                 (rx - math.cos(bl) * 8, ry - math.sin(bl) * 8),
                                 (rx + math.cos(bl) * 8, ry + math.sin(bl) * 8), 2)

        # body
        pygame.draw.circle(d, _DRONE_BODY, (mid, cy_d), 10)
        pygame.draw.circle(d, OUTLINE_COLOR, (mid, cy_d), 10, 1)
        # nose: points where it's heading
        hx, hy = self._heading
        pygame.draw.line(d, _DRONE_EYE, (mid, cy_d),
                         (mid + hx * 12, cy_d + hy * 12), 3)
        # pulsing scanner eye
        pulse = 3.5 + 1.8 * (0.5 + 0.5 * math.sin(t * 7.0))
        pygame.draw.circle(d, (*_DRONE_EYE, 90), (mid, cy_d), pulse + 4)
        pygame.draw.circle(d, _DRONE_EYE, (mid, cy_d), pulse)

        surface.blit(d, d.get_rect(center=(round(cx), round(cy))))
