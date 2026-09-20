"""What the learned agent sees, and the moves it can make.

INFORMATION PARITY WITH A*  (the rule everything here is built to obey)

The learner and the A* rescuer must play under the same conditions. If the
learner sees LESS than A*, it cannot learn A*'s decisions (the teacher's move is
not a function of what the student sees), and every comparison is unfair to it.
If it sees MORE, it has God mode. What A* actually knows (read from
entities/rescue_agent.py, not assumed):

  * the whole real map: it plans with hazard-weighted A* over every tile
  * the live hazard field EVERYWHERE: fire, smoke, sparking panels, a pending
    collapse (hazards.entry_cost prices them into every route)
  * where the exit is, where the key is, and how many occupants there are
    (the HUD shows a human the exit direction and the head-count)
  * where an occupant is ONLY once one is within AGENT_VISION_TILES (3.5) of it;
    after that it remembers them and reads their live state
  * its "explored" set is used only to choose which unseen area to search next

Observation version 1 gave the learner LESS than that: an 11 x 11 window of tiles
it had walked near, hazards only within vision, no global layout. Version 2 adds
route hints computed from exactly A*'s own inputs (see route_hints), so the
learner has A*'s information and none it lacks. Two things must therefore hold,
and tests/test_imitation.py checks both:

  * NO GOD MODE: nothing A* cannot see may change the observation -- moving an
    occupant the agent has not spotted changes no number in it
  * NOTHING EXTRA: hints read only the map, the hazard field, the spotted
    occupants, the explored set, the exit and the key -- the same inputs as A*

Both agents also share one body (health, damage, smoke slowdown, speed, vision
radius), one game (the same GameSession, stage seeds, occupant placement, time
cap and stage-end rules) and are compared on identical seeded episodes.

Actions are grid steps, not pixel movement: stay, or step to one of the
four neighbouring tiles. A step walks the agent to the next tile centre
using the game's own movement (so smoke slows it exactly as it would the
A* agent), and choosing a wall is simply a wasted step.

The observation is one flat float32 vector so it works with any
standard RL library:

    [ window (WINDOW x WINDOW x N_CHANNELS, row-major, channel last) | features | (v2) route hints ]
"""

import numpy as np

from settings import AGENT_VISION_TILES, HEALTH_MAX
from entities.victim import STATE_IDLE, STATE_FOLLOWING, STATE_SAVED, STATE_DEAD
from pathfinding import bfs_distances, weighted_distances

# ---- actions
ACTION_STAY, ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT = range(5)
N_ACTIONS = 5
MOVES = {
    ACTION_UP: (0, -1),
    ACTION_DOWN: (0, 1),
    ACTION_LEFT: (-1, 0),
    ACTION_RIGHT: (1, 0),
}
ACTION_NAMES = ("stay", "up", "down", "left", "right")

# ---- observation layout
WINDOW_RADIUS = 5
WINDOW = 2 * WINDOW_RADIUS + 1
CHANNELS = ("wall", "blocked", "unexplored", "fire", "smoke",
            "panel", "exit", "occupant", "key")
N_CHANNELS = len(CHANNELS)
FEATURES = (
    "health", "escorting", "out", "unclaimed", "lost", "spotted",
    "exit_dx", "exit_dy", "exit_distance", "fire_countdown",
    "exit_on_fire", "key_needed", "elapsed",
)
N_FEATURES = len(FEATURES)
OBS_SIZE = WINDOW * WINDOW * N_CHANNELS + N_FEATURES        # observation version 1

# ---- observation version 2 = version 1 + route hints
# The A* rescuer plans over the WHOLE real map and the live hazard field, and
# version 1 shows the learner only an 11 x 11 window, so on big mazes the learner
# cannot see where the goals are. Version 2 adds, for each of A*'s three
# candidate goals, what A* itself would compute: the hazard-weighted path cost
# from the agent's position, and how much each of the four moves shortens it.
# (Goal 1: the exit. Goal 2: the nearest spotted, not-yet-rescued occupant.
# Goal 3: the nearest unexplored frontier. Goal 4: the key, while a locked door
# is still in the way -- A* heads for it when the route to its goal is blocked.)
# The network still has to decide WHICH goal to pursue and when; it is told where
# each one is.
HINT_GOALS = ("exit", "occupant", "frontier", "key")
HINT_FIELDS = ("available", "advance_up", "advance_down", "advance_left", "advance_right",
               "distance")
N_HINT = len(HINT_GOALS) * len(HINT_FIELDS)
OBS_SIZE_V2 = OBS_SIZE + N_HINT

# ---- observation version 3 = version 2 + a short memory of the agent's OWN history
# A memoryless network cannot tell that it is pacing between two tiles: at A the picture
# says "go to B", at B "go back to A". Version 3 adds its previous move (one-hot) and the
# last few tiles it stood on, as offsets from where it is now. It is the agent's own past,
# not information about the world, so it gives it nothing A* lacks (A* carries a goal and
# a planned route from one decision to the next).
N_MEMORY_TILES = 4
N_MEMORY = N_ACTIONS + 3 * N_MEMORY_TILES          # previous move + (dx, dy, present) per tile
OBS_SIZE_V3 = OBS_SIZE_V2 + N_MEMORY

# ---- observation version 4 = version 3 + a trail of where it has walked, all episode
# For every tile in the 11 x 11 window: how many times the agent has stood on it this
# episode (capped at TRAIL_CAP, scaled to 0-1). Empty at the start of every episode and
# built only from tiles the agent actually entered. A* records every tile it has walked
# (`trail_cells`) though it only draws them.
TRAIL_CAP = 5
N_TRAIL = WINDOW * WINDOW
OBS_SIZE_V4 = OBS_SIZE_V3 + N_TRAIL
OBS_SIZES = {1: OBS_SIZE, 2: OBS_SIZE_V2, 3: OBS_SIZE_V3, 4: OBS_SIZE_V4}


def obs_version_of(size):
    """Which observation version a vector / network input of this size is."""
    for version, n in OBS_SIZES.items():
        if n == size:
            return version
    raise ValueError(f"no observation version has size {size}")

_FIRE_HORIZON_SECONDS = 300.0


def action_mask(agent):
    """bool[N_ACTIONS]: which actions do something. Staying is always
    allowed; a step is allowed only into a walkable tile."""
    mask = np.zeros(N_ACTIONS, dtype=bool)
    mask[ACTION_STAY] = True
    cc, cr = agent.current_cell
    tm = agent.tilemap
    for action, (dc, dr) in MOVES.items():
        mask[action] = tm.is_walkable(cc + dc, cr + dr)
    return mask


def route_hints(agent, victims):
    """The 24 numbers of observation version 2 (see the constants above).

    For each goal: available (1 if the goal exists and is reachable), then for
    each move up/down/left/right how much closer to the goal that step gets it
    in hazard-weighted cost (+1 is one clean step of progress, negative is
    backwards, -1 also for a wall), then the remaining cost, scaled by the map
    size. Uses the same planner cost as A* (`hazards.entry_cost`) and reads only
    what A* reads."""
    tm = agent.tilemap
    cur = agent.current_cell
    cost_fn = agent._cost_fn()
    from_agent = weighted_distances(tm, cur, cost_fn)
    idle = [v.cell for v in agent.known_victims
            if v.state == STATE_IDLE and v.cell in from_agent]
    doors = agent.hazards.doors if agent.hazards is not None else None
    key_cell = (doors.key_cell if doors is not None and doors.enabled
                and not doors.key_collected else None)
    targets = [
        tm.exit_cell,
        min(idle, key=lambda c: (from_agent[c], c)) if idle else None,
        agent._nearest_unexplored(from_agent),
        key_cell,
    ]
    out = np.zeros(N_HINT, dtype=np.float32)
    scale = float(tm.cols + tm.rows)
    for i, target in enumerate(targets):
        if target is None:
            continue
        to_target = weighted_distances(tm, target, cost_fn)
        d0 = to_target.get(cur)
        if d0 is None:
            continue
        base = i * len(HINT_FIELDS)
        out[base] = 1.0
        for k, action in enumerate((ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT)):
            dc, dr = MOVES[action]
            dn = to_target.get((cur[0] + dc, cur[1] + dr))
            out[base + 1 + k] = -1.0 if dn is None else max(-1.0, min(1.0, (d0 - dn) / 3.0))
        out[base + 5] = min(1.0, d0 / scale)
    return out


def memory_features(agent):
    """The 17 numbers of observation version 3: the last move taken (one-hot over
    stay/up/down/left/right), then for each of the last four tiles it stood on before
    this one (most recent first): dx/5, dy/5 relative to here (clipped) and 1 if that
    slot is filled. Reads only the agent's own history."""
    out = np.zeros(N_MEMORY, dtype=np.float32)
    out[getattr(agent, "last_action", ACTION_STAY)] = 1.0
    history = list(getattr(agent, "cell_history", None) or [])
    if not history or history[-1] != agent.current_cell:
        history.append(agent.current_cell)      # the tile it is on now may not be recorded yet
    cc, cr = agent.current_cell
    for k, cell in enumerate(reversed(history[:-1][-N_MEMORY_TILES:])):
        base = N_ACTIONS + 3 * k
        out[base] = max(-1.0, min(1.0, (cell[0] - cc) / 5.0))
        out[base + 1] = max(-1.0, min(1.0, (cell[1] - cr) / 5.0))
        out[base + 2] = 1.0
    return out


def trail_window(agent):
    """The N_TRAIL numbers of observation version 4: visit counts around the agent."""
    out = np.zeros((WINDOW, WINDOW), dtype=np.float32)
    counts = getattr(agent, "visit_counts", None) or {}
    cc, cr = agent.current_cell
    for (col, row), n in counts.items():
        dc, dr = col - cc, row - cr
        if -WINDOW_RADIUS <= dc <= WINDOW_RADIUS and -WINDOW_RADIUS <= dr <= WINDOW_RADIUS:
            out[dr + WINDOW_RADIUS, dc + WINDOW_RADIUS] = min(n, TRAIL_CAP) / TRAIL_CAP
    return out.reshape(-1)


def build_observation(agent, victims, version=1):
    """Flat float32 vector for the agent's current state (see module doc).
    version 1: the local window and scalars. version 2: plus route hints.
    version 3: plus a short memory of the agent's own history.
    version 4: plus how often it has stood on each nearby tile this episode."""
    tm = agent.tilemap
    haz = agent.hazards
    cc, cr = agent.current_cell
    total = max(1, len(victims))

    window = np.zeros((WINDOW, WINDOW, N_CHANNELS), dtype=np.float32)
    ch = {name: i for i, name in enumerate(CHANNELS)}

    spotted = {v.cell for v in agent.known_victims if v.state == STATE_IDLE}
    door = haz.doors if haz is not None else None
    key_cell = None
    if door is not None and door.enabled and not door.key_collected:
        key_cell = door.key_cell
    debris_pending = haz.debris.pending_cell if haz is not None else None
    vision_sq = AGENT_VISION_TILES * AGENT_VISION_TILES

    for wy in range(WINDOW):
        for wx in range(WINDOW):
            dc, dr = wx - WINDOW_RADIUS, wy - WINDOW_RADIUS
            col, row = cc + dc, cr + dr
            in_map = 0 <= col < tm.cols and 0 <= row < tm.rows
            if not in_map:
                window[wy, wx, ch["wall"]] = 1.0
                continue
            cell = (col, row)
            if cell == tm.exit_cell:
                window[wy, wx, ch["exit"]] = 1.0
            if cell not in agent.explored:
                window[wy, wx, ch["unexplored"]] = 1.0
                continue
            if tm.tile_at(col, row) == "#":
                window[wy, wx, ch["wall"]] = 1.0
            elif cell in tm.dynamic_blocked:
                window[wy, wx, ch["blocked"]] = 1.0
            if cell in spotted:
                window[wy, wx, ch["occupant"]] = 1.0
            if dc * dc + dr * dr <= vision_sq and haz is not None:
                if cell in haz.fire.burning:
                    window[wy, wx, ch["fire"]] = 1.0
                window[wy, wx, ch["smoke"]] = min(1.0, haz.fire.smoke_density(cell))
                if cell in haz.panels.panels:
                    window[wy, wx, ch["panel"]] = 1.0
                if cell == debris_pending:
                    window[wy, wx, ch["blocked"]] = 0.5     # about to drop
                if cell == key_cell:
                    window[wy, wx, ch["key"]] = 1.0

    states = [v.state for v in victims]
    idle = states.count(STATE_IDLE)
    following = states.count(STATE_FOLLOWING)
    saved = states.count(STATE_SAVED)
    dead = states.count(STATE_DEAD)

    exit_col, exit_row = tm.exit_cell
    dist_map = bfs_distances(tm, tm.exit_cell)
    exit_steps = dist_map.get(agent.current_cell)
    exit_distance = 2.0 if exit_steps is None else min(2.0, exit_steps / (tm.cols + tm.rows))

    if haz is not None:
        countdown = min(1.0, haz.fire.seconds_to_exit_fire / _FIRE_HORIZON_SECONDS)
        exit_on_fire = 1.0 if haz.fire.exit_on_fire else 0.0
        elapsed = min(1.0, haz.fire.elapsed / _FIRE_HORIZON_SECONDS)
    else:
        countdown, exit_on_fire, elapsed = 1.0, 0.0, 0.0

    features = np.array([
        max(0.0, agent.health) / HEALTH_MAX,
        following / total,
        saved / total,
        idle / total,
        dead / total,
        len(spotted) / total,
        (exit_col - cc) / tm.cols,
        (exit_row - cr) / tm.rows,
        exit_distance,
        countdown,
        exit_on_fire,
        1.0 if key_cell is not None else 0.0,
        elapsed,
    ], dtype=np.float32)

    parts = [window.reshape(-1), features]
    if version >= 2:
        parts.append(route_hints(agent, victims))
    if version >= 3:
        parts.append(memory_features(agent))
    if version == 4:
        parts.append(trail_window(agent))
    return np.concatenate(parts).astype(np.float32)
