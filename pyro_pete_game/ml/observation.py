"""What the learned agent sees, and the moves it can make.

Fair-information rules. The A* agent is told the stage head-count and
finds occupants and layout by walking near them, and the learned agent is
held to exactly that -- nothing it couldn't legitimately know:

  * layout: walls/blocked tiles are shown only for cells it has explored;
    unexplored cells are flagged as such and show nothing else
  * hazards, occupants and the key: only within its live vision radius
    (settings.AGENT_VISION_TILES), the same radius the A* agent uses
  * occupants it has already spotted stay visible while unclaimed
  * the exit location, the stage head-count and the fire countdown: always
    known -- the exit is drawn on the HUD's compass for the human, and the
    other two are on the HUD

Actions are grid steps, not pixel movement: stay, or step to one of the
four neighbouring tiles. A step walks the agent to the next tile centre
using the game's own movement (so smoke slows it exactly as it would the
A* agent), and choosing a wall is simply a wasted step.

The observation is one flat float32 vector so it works with any
standard RL library:

    [ window (WINDOW x WINDOW x N_CHANNELS, row-major, channel last) | features ]
"""

import numpy as np

from settings import AGENT_VISION_TILES, HEALTH_MAX
from entities.victim import STATE_IDLE, STATE_FOLLOWING, STATE_SAVED, STATE_DEAD
from pathfinding import bfs_distances

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
OBS_SIZE = WINDOW * WINDOW * N_CHANNELS + N_FEATURES

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


def build_observation(agent, victims):
    """Flat float32 vector for the agent's current state (see module doc)."""
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

    return np.concatenate([window.reshape(-1), features]).astype(np.float32)
