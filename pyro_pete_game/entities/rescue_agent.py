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
  * no occupant is left to find (all are out, being escorted, or lost) -> the
    exit (it is told the head-count, like the human player, but not
    where anyone is)
  * otherwise no known victim -> head for the nearest unexplored area
  * if a locked door stands between the agent and its goal and the key
    hasn't been collected, the key becomes the goal first
  * fully explored, nothing left to rescue -> head for the exit

It still doesn't mutate victim state itself -- pickup is the shared,
proximity-based path in main.py's _try_rescue, so whoever reaches a
victim first claims it.
"""

import math
import os

import pygame

from settings import (
    AGENT_SPEED, AGENT_COLOR, AGENT_RADIUS, AGENT_REPLAN_MIN_INTERVAL,
    AGENT_ROUTE_COLOR, AGENT_ROUTE_ALPHA, AGENT_TRAIL_COLOR, AGENT_TRAIL_ALPHA,
    AGENT_VISION_TILES, AGENT_VISUAL, AGENT_SPRITE_HEIGHT, WALK_ANIM_FPS,
    AGENT_EXPLORE_HEALTH_BUDGET,
    HEALTH_MAX, TILE_SIZE,
)
from entities.victim import STATE_IDLE
from collections import deque

from pathfinding import NEIGHBOR_STEPS, astar_path, weighted_distances

OUTLINE_COLOR = (255, 255, 255)
CORE_COLOR = (20, 20, 24)

# Default AI look is a walking robot sprite (assets/robot/, see
# AGENT_VISUAL in settings.py). This is the no-art-required fallback: a
# little search-and-rescue drone drawn from primitives -- a dark body,
# four spinning rotors, and a pulsing scanner eye. Reads instantly as
# "this one is the AI" either way.
_DRONE_BODY = (44, 52, 66)
_DRONE_ARM = (30, 34, 42)
_DRONE_ROTOR = (150, 190, 235)
_DRONE_EYE = (120, 235, 255)
_DRONE_DEAD = (86, 86, 92)

DIRECTIONS = ("down", "up", "left", "right")
ROBOT_ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "robot")


def _direction_from_heading(hx, hy):
    """Same priority Player uses for its own facing: whichever axis is
    moving more decides the sprite direction."""
    if abs(hy) >= abs(hx):
        return "down" if hy >= 0 else "up"
    return "right" if hx > 0 else "left"


def _load_robot_sprite(path, target_height):
    image = pygame.image.load(path).convert_alpha()
    if image.get_height() != target_height:
        scale = target_height / image.get_height()
        new_size = (max(1, round(image.get_width() * scale)), target_height)
        image = pygame.transform.smoothscale(image, new_size)
    return image


def _load_robot_sprites():
    """(idle_frames, walk_frames) dicts keyed by direction, or None if
    assets/robot/ is missing or incomplete -- caller then falls back to
    the drone, same graceful-degradation the victim sprites use. Loaded
    once at import time since, unlike victims, there's only ever one of
    these across the whole run (including restarts)."""
    def load_dir(d):
        idle_path = os.path.join(ROBOT_ASSET_DIR, f"idle_{d}.png")
        walk_paths = [os.path.join(ROBOT_ASSET_DIR, f"walk_{d}_{i}.png") for i in range(1, 5)]
        if not os.path.isfile(idle_path) or not all(os.path.isfile(p) for p in walk_paths):
            return None
        idle = _load_robot_sprite(idle_path, AGENT_SPRITE_HEIGHT)
        walk = [_load_robot_sprite(p, AGENT_SPRITE_HEIGHT) for p in walk_paths]
        return idle, walk

    idle_frames, walk_frames = {}, {}
    for d in DIRECTIONS:
        loaded = load_dir(d)
        if loaded is None:
            return None
        idle_frames[d], walk_frames[d] = loaded
    return idle_frames, walk_frames


_ROBOT_SPRITES_CACHE = "unloaded"  # sentinel distinct from None ("tried, unavailable")


def _get_robot_sprites():
    """Loads (and caches) lazily on first call rather than at import time --
    convert_alpha() needs an active pygame display, which doesn't exist yet
    when this module is first imported (main.py imports RescueAgent before
    calling pygame.init()). First real call happens inside GameSession's
    __init__, safely after display setup. Cached at module level so a
    restart (R) doesn't reload the same 20 files from disk."""
    global _ROBOT_SPRITES_CACHE
    if _ROBOT_SPRITES_CACHE == "unloaded":
        _ROBOT_SPRITES_CACHE = _load_robot_sprites()
    return _ROBOT_SPRITES_CACHE


def _distances_from_exit(tilemap):
    """Walking distance from the exit to every floor cell of the building, over the
    STATIC floor plan (walls only). A locked door or a fallen ceiling does not change
    "which side of the building is far from the exit", and taking them into account would
    leave the whole spawn side (behind the door) with no distance at all. The floor plan
    never changes during a run, so it is computed once per map."""
    cached = getattr(tilemap, "_exit_distance_cache", None)
    if cached is not None:
        return cached
    start = tilemap.exit_cell
    dist = {start: 0}
    queue = deque([start])
    while queue:
        col, row = queue.popleft()
        for dc, dr in NEIGHBOR_STEPS:
            cell = (col + dc, row + dr)
            if cell not in dist and tilemap.tile_at(*cell) != "#":
                dist[cell] = dist[(col, row)] + 1
                queue.append(cell)
    tilemap._exit_distance_cache = dist
    return dist


class RescueAgent:
    # Search-order options. Both are OFF by default, which is the original
    # planner exactly (the benchmark). They exist so an experiment, or a model
    # trained to copy a variant, can ask for a different search without
    # touching how the default agent behaves; see GameSession(agent_options=...).
    #   frontier_lean        > 0 leans the search towards the far side of the map
    #                        (relative to the exit): it picks the frontier that
    #                        minimises  distance_from_agent - lean * distance_to_exit.
    #   frontier_min_reveal  > 0 makes it skip a frontier that would reveal fewer
    #                        than this many unseen floor tiles: no special trip into
    #                        a corner just to finish looking at its last few tiles.
    #   frontier_defer_small True turns the skip into a deferral: a small corner is only
    #                        visited when nothing bigger is left to search (someone is still
    #                        missing, the corner is the only place left), never before.
    frontier_lean = 0.0
    frontier_min_reveal = 0
    frontier_defer_small = False

    def __init__(self, tilemap, start_cell, hazard_field=None, stats=None,
                 visual=None, speed_scale=1.0):
        """speed_scale multiplies AGENT_SPEED for this run -- later
        campaign stages nudge it up so the race stays tight as the
        buildings get bigger (levels.tuning.StageTuning.agent_speed_scale)."""
        self.tilemap = tilemap
        self.hazards = hazard_field
        self.stats = stats
        self.speed_scale = speed_scale
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

        # visual (an explicit param, e.g. from a skin-select menu) picks the
        # look for *this* agent; falls back to the settings.py default when
        # the caller doesn't care. "robot" with a complete assets/robot/
        # set -> walk cycle sprites; otherwise the original hand-drawn
        # drone, no art required. Checked once here rather than every
        # draw() call. Deliberately a constructor param rather than reading
        # settings.AGENT_VISUAL directly, so a menu can set it per-run
        # without fighting Python's "from x import y" import-time binding.
        visual = AGENT_VISUAL if visual is None else visual
        self._sprites = _get_robot_sprites() if visual == "robot" else None

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

    @property
    def completed(self):
        """Finished the stage *successfully* -- out of the building alive.
        Distinct from done(), which is also true when the agent burns to
        death; only this counts as the AI winning the race."""
        return self._finished and not self.is_dead

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
        victim to chase. (With the optional search-order settings above
        it is the best-scoring frontier instead of the nearest.)"""
        if self.frontier_lean or self.frontier_min_reveal:
            return self._preferred_unexplored(dist)
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

    def _preferred_unexplored(self, dist):
        """The frontier chosen when a search-order setting is on. Uses only
        what the default rule uses (the layout, the exit, its own explored
        set): the fog of war is unchanged. A frontier is an unseen floor cell
        next to a seen one."""
        tm = self.tilemap
        d_exit = _distances_from_exit(tm)
        unseen = None
        if self.frontier_min_reveal:
            unseen = {c for c in dist if c not in self.explored}
            radius = int(AGENT_VISION_TILES)
            offsets = [(dc, dr) for dc in range(-radius, radius + 1) for dr in range(-radius, radius + 1)
                       if dc * dc + dr * dr <= AGENT_VISION_TILES * AGENT_VISION_TILES]
        best, best_key = None, (math.inf, (0, 0))
        fallback, fallback_key = None, (math.inf, (0, 0))
        for cell, d in dist.items():
            if cell in self.explored:
                continue
            if not any((cell[0] + dc, cell[1] + dr) in self.explored
                       for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                continue
            key = (d - self.frontier_lean * d_exit.get(cell, 0), cell)
            if key < fallback_key:
                fallback, fallback_key = cell, key
            if unseen is not None:
                reveal = sum(1 for dc, dr in offsets if (cell[0] + dc, cell[1] + dr) in unseen)
                if reveal < self.frontier_min_reveal:
                    continue
            if key < best_key:
                best, best_key = cell, key
        if best is None and self.frontier_defer_small:
            return fallback
        return best

    # ------------------------------------------------------------------ goal
    def _route_damage(self, path):
        """Health the agent would lose walking `path`, judged by the
        hazards as they stand right now.

        Deliberately a snapshot: the fire keeps spreading while it walks,
        so this under-estimates, which is why the caller keeps a reserve
        rather than spending down to zero.
        """
        if self.hazards is None or not path:
            return 0.0
        speed = max(1.0, AGENT_SPEED * self.speed_scale)
        seconds_per_tile = self.tilemap.tile_size / speed
        total = 0.0
        for cell in path:
            x, y = self.tilemap.cell_center(*cell)
            rect = pygame.Rect(0, 0, AGENT_RADIUS * 2, AGENT_RADIUS * 2)
            rect.center = (round(x), round(y))
            dps = self.hazards.damage_per_second(rect)
            if dps:
                total += dps * seconds_per_tile
        return total

    def _worth_exploring(self, target):
        """Can it afford to go and look, and still get back out?

        Only ever consulted when no known occupant is waiting, so a
        cautious answer can never strand someone -- it just means the
        agent stops searching a building it has no evidence still holds
        anyone, which is the difference between finishing a run and
        burning to death two tiles from the door.
        """
        if self.hazards is None:
            return True
        path = astar_path(self.tilemap, self.current_cell, target, self._cost_fn())
        if path is None:
            return False
        # out and back again -- reaching the far side is only half the job
        round_trip = self._route_damage(path) * 2.0
        return round_trip <= self.health * AGENT_EXPLORE_HEALTH_BUDGET

    def _all_occupants_accounted(self, victims):
        """True when nobody is left to find: every occupant is either out
        or already being escorted.

        The agent is told the head-count for the stage -- the same figure
        the HUD shows the human player ("Occupants out 2/6") -- but not
        where anyone is, so this is bookkeeping, not extra eyesight. It is
        what stops it searching a building it has already emptied, which
        used to send it back out looking for people who weren't there
        (and once cost it the run, dying after everyone was already saved).
        """
        if not victims:
            return False   # no head-count to go on; fall back to searching
        # Only an occupant nobody has picked up still needs finding. One
        # who is out, being escorted, or lost with a rescuer that died is
        # already accounted for.
        return not any(v.state == STATE_IDLE for v in victims)

    def _choose_goal_cell(self, victims):
        """Chase the nearest *known* idle victim by weighted distance.
        Everyone accounted for -> the exit. Otherwise explore toward the
        nearest unseen area; nothing left worth exploring -> the exit. A
        locked door on the way makes the key the real next goal."""
        cost_fn = self._cost_fn()
        dist = weighted_distances(self.tilemap, self.current_cell, cost_fn)

        idle = [v.cell for v in self.known_victims
                if v.state == STATE_IDLE and v.cell in dist]
        if idle:
            # Ties on distance are broken by cell, not by whatever order
            # the set of spotted occupants happens to iterate in (that
            # follows memory addresses), so the same situation always
            # gets the same decision -- evaluation runs depend on it.
            target = min(idle, key=lambda c: (dist[c], c))
        elif self._all_occupants_accounted(victims):
            target = self.tilemap.exit_cell
        else:
            unexplored = self._nearest_unexplored(dist)
            if unexplored is not None and not self._worth_exploring(unexplored):
                unexplored = None      # too expensive to go looking; head out
            target = unexplored or self.tilemap.exit_cell

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
            if at_exit and no_known and self._search_over(victims):
                self._finished = True
            return

        self._advance_along_path(dt)

    def _search_over(self, victims):
        """Nothing left to look for: everyone is accounted for, or nothing
        is left to look at, or nothing is left worth the health it would
        cost to go and look. Its own method so an alternative brain
        (entities/learned_agent.py) can define "over" differently."""
        if self._all_occupants_accounted(victims):
            return True
        unexplored = self._nearest_unexplored(
            weighted_distances(self.tilemap, self.current_cell, self._cost_fn())
        )
        return unexplored is None or not self._worth_exploring(unexplored)

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

        speed = AGENT_SPEED * self.speed_scale
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
        if self._sprites is not None:
            self._draw_robot(surface, camera_offset)
            return

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

    def _draw_robot(self, surface, camera_offset):
        """Walking-robot alternative to the drone: same feet-anchored
        convention as Player/Victim (self.x, self.y is the ground point
        the pathfinder/collision use), 4-direction idle/walk sprites, and
        a flat shadow rather than the drone's hover shadow."""
        ox, oy = camera_offset
        cx, cy = round(self.x - ox), round(self.y - oy)
        idle_frames, walk_frames = self._sprites
        direction = _direction_from_heading(*self._heading)
        moving = bool(self._waypoints) and not self.done

        if moving:
            frame = walk_frames[direction][int(self._anim_t * WALK_ANIM_FPS) % 4]
        else:
            frame = idle_frames[direction]

        shadow = pygame.Surface((32, 14), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 70), shadow.get_rect())
        surface.blit(shadow, shadow.get_rect(center=(cx, cy)))

        rect = frame.get_rect(midbottom=(cx, cy))
        if self.is_dead:
            # dim + desaturate a copy rather than mutate the cached frame
            crashed = frame.copy()
            crashed.fill((130, 130, 130, 255), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(crashed, rect)
        else:
            surface.blit(frame, rect)
