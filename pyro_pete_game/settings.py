"""Shared constants for the Pyro Pete evacuation game."""

SCREEN_WIDTH = 960
SCREEN_HEIGHT = 640
FPS = 60

# Background color behind the sprites (used as colorkey so the flat grey
# generation background becomes transparent). Sampled from the corner pixel
# of each sprite at load time instead, but kept here as a documented default.
DEFAULT_BG_COLORKEY_TOLERANCE = 20

PLAYER_SPEED = 180  # pixels per second
WALK_ANIM_FPS = 8   # how fast the 4 walk frames cycle while moving

FLOOR_COLOR = (46, 50, 58)
GRID_COLOR = (58, 63, 73)
TILE_SIZE = 64

# Tilemap placeholder colors (no tile art yet -- flat rects for now)
WALL_COLOR = (76, 58, 46)
EXIT_COLOR = (72, 140, 90)
GRID_LINE_COLOR = (58, 63, 73)
DEBRIS_COLOR = (92, 84, 72)       # fallen rubble -- impassable
LOCKED_DOOR_COLOR = (104, 72, 40)   # locked door -- impassable until key
LOCKED_DOOR_PANEL_COLOR = (140, 100, 56)
KEY_COLOR = (240, 210, 70)

# Sprites come from several different AI-generation batches at wildly
# different native resolutions (300-600px tall). Scale everyone down to
# a consistent in-game height so Pete reads sensibly against a 64px tile.
PLAYER_SPRITE_HEIGHT = 96

# --- Fire hazard ---
# The maze is a perfect maze (mazegen.py), so there is exactly one path
# between the ignition point and the exit. FireSystem uses that to pick
# a spread rate so fire reaches the exit roughly this many seconds after
# ignition, regardless of maze size.
FIRE_TARGET_SECONDS_TO_EXIT = 80
FIRE_COLOR = (214, 92, 40)
FIRE_ALPHA = 90   # scorch tint under the flames
FIRE_SCORCH_COLOR = (34, 22, 18)
FIRE_FLAME_COLORS = ((248, 170, 58), (232, 104, 34), (188, 46, 26))

# Smoke particles drifting up from burning tiles -- decorative layer.
SMOKE_COLOR = (110, 112, 118)
SMOKE_SPAWN_RATE = 0.9        # expected particles per burning tile per second
SMOKE_MAX_PARTICLES = 220     # hard cap so a big fire can't tank the frame rate
SMOKE_MIN_LIFETIME = 0.9
SMOKE_MAX_LIFETIME = 1.8
SMOKE_RISE_SPEED = 34         # pixels/sec upward drift
SMOKE_DRIFT_SPEED = 10        # pixels/sec horizontal sway
SMOKE_MIN_RADIUS = 4
SMOKE_MAX_RADIUS = 11
SMOKE_MAX_ALPHA = 120

# Functional smoke field: burning tiles are thick smoke (density 1.0),
# tiles one ring out are thinner (SMOKE_SPREAD_FALLOFF). Standing in smoke
# slows you and shrinks your view, and it's a mild routing cost the AI
# prefers to avoid but will cut through when it's faster.
SMOKE_SPREAD_FALLOFF = 0.45
SMOKE_SLOW_AT_FULL = 0.45          # move speed multiplier in density-1.0 smoke
SMOKE_VISION_AT_FULL = 0.50        # vision-radius multiplier in density-1.0 smoke
SMOKE_TILE_COST = 2.0             # extra A* cost to enter a full-smoke tile
SMOKE_HAZE_COLOR = (86, 88, 96)
SMOKE_HAZE_MAX_ALPHA = 150

# --- Sparking electrical panels ---
# Stationary hazard placed at generation: fixed tiles that deal fast
# damage (a shorted-out panel arcing across the corridor). They don't
# spread. Passable in a pinch but the AI routes around them.
SPARK_PANEL_COUNT = 3
SPARK_PANEL_MIN_SPAWN_DISTANCE = 3   # cells from spawn
SPARK_PANEL_DAMAGE_PER_SECOND = 34
SPARK_PANEL_TILE_COST = 7.5  # was 6.0 -- raised after playtesting: panels do more
                              # dmg/sec (34) than fire (20) and the AI wasn't
                              # weighting that danger heavily enough (see
                              # playtesting/Playtest_Feedback_and_Run_Notes.md)
SPARK_PANEL_BOX_COLOR = (58, 54, 40)      # the dead panel housing
SPARK_PANEL_COLOR = (250, 226, 120)       # arc glow
SPARK_PANEL_CORE_COLOR = (150, 200, 255)  # arc bolt

# --- Collapsing debris ---
# The ceiling gives way over the course of a run: every
# DEBRIS_COLLAPSE_INTERVAL seconds a random floor tile becomes permanently
# impassable rubble. A collapse is skipped if it would cut spawn, exit or
# any victim off from the rest of the map, so a run is never made
# unwinnable -- but it does force everyone (the AI especially) to re-plan.
DEBRIS_COLLAPSE_INTERVAL = 9.0
DEBRIS_MAX_TILES = 10
DEBRIS_MIN_SPAWN_DISTANCE = 2
DEBRIS_WARN_SECONDS = 1.4          # dust/cracks shown on a tile before it drops
DEBRIS_WARN_COLOR = (150, 140, 120)
DEBRIS_PENDING_COST = 25.0         # A* surcharge for a tile that's about to collapse

# --- Locked door + key ---
# One door sits on the spawn->exit corridor; a key is hidden on a side
# branch reachable without crossing the door. Walking over the key picks
# it up (for whoever touches it -- Pete or the AI), which unlocks every
# door. Adds a sub-goal to the routing problem.
LOCKED_DOOR_ENABLED = True
KEY_PICKUP_RADIUS = 22

# --- Player health ---
# Hazards don't kill on contact -- they drain health over time, so a quick
# dash through is survivable but lingering isn't. Shared by Pete and the
# AI agent (entities/rescue_agent.py) so the human-vs-AI race is fair.
HEALTH_MAX = 100
HEALTH_DRAIN_PER_SECOND = 20  # 5s of continuously standing in fire = dead

# Extra A* cost for the AI to enter a burning tile. High enough that it
# detours around fire whenever a detour exists, low enough that it will
# still dash through one tile of fire rather than walk 20 tiles around.
FIRE_TILE_COST = 8.0

# Health bar HUD
HEALTH_BAR_WIDTH = 200
HEALTH_BAR_HEIGHT = 18
HEALTH_BAR_MARGIN = 16
HEALTH_BAR_BG_COLOR = (40, 40, 44)
HEALTH_BAR_FILL_COLOR = (196, 64, 56)     # low-health red (gradient endpoint)
HEALTH_BAR_COLOR_FULL = (86, 184, 108)    # full-health green (gradient endpoint)
HEALTH_BAR_COLOR_MID = (232, 181, 65)     # mid-health yellow/orange (gradient midpoint)
HEALTH_BAR_BORDER_COLOR = (230, 230, 230)

# --- Visibility (fog of war) ---
# Only tiles within this radius of Pete are fully lit. Tiles he's seen
# before but can't see right now stay faintly visible (FOG_EXPLORED_ALPHA)
# -- "you remember roughly where you've been" -- while never-seen tiles
# are pitch black. Smoke shrinks the live radius (hazards.vision_multiplier).
VISIBILITY_RADIUS_TILES = 2.5
VISIBILITY_SOFT_EDGE_TILES = 1.0  # gradient width so the edge isn't a hard circle
FOG_COLOR = (0, 0, 0)
FOG_EXPLORED_ALPHA = 150          # 0 = explored looks fully lit, 255 = as black as unseen

# --- Victims ---
# Trapped occupants Pete leads to the exit. Drawn as an animated sprite
# when art exists under assets/victims/<name>/, otherwise a colored
# circle placeholder (see entities/victim.py).
VICTIM_COUNT = 3  # one of each sprite in VICTIM_SPRITE_NAMES, shuffled per run
VICTIM_MIN_SPAWN_DISTANCE = 4  # cells from spawn, same idea as fire's runway rule
VICTIM_RADIUS = 12
VICTIM_COLOR = (235, 196, 60)
VICTIM_SAVED_COLOR = (110, 200, 120)
VICTIM_RESCUE_RADIUS = TILE_SIZE * 0.9  # how close Pete must get to trigger a rescue

# Slightly shorter than Pete (PLAYER_SPRITE_HEIGHT) so occupants don't
# visually upstage the character the player controls.
VICTIM_SPRITE_HEIGHT = 88
# Asset folders under assets/victims/ to assign to victims, round-robin.
# A name with no matching folder falls back to the circle marker, so it's
# safe to list victims whose art isn't done yet. Each folder has a full
# 4-direction set assembled from mixed sources -- see entities/victim.py's
# art note and docs/ai_critique.md.
VICTIM_SPRITE_NAMES = ("cleaner", "office_lady", "salaryman")

# Escort behavior: a rescued victim doesn't pathfind or collide on its
# own -- it just replays a delayed slice of its rescuer's own trail (Pete
# or the AI agent, see main.py), which is guaranteed walkable since it's
# literally where the rescuer already walked. Lag is in frames at FPS;
# each subsequently-rescued victim in the same escort gets extra spacing
# so they queue up single-file rather than overlapping.
PLAYER_TRAIL_MAXLEN = 600
VICTIM_FOLLOW_LAG_FRAMES = 40
VICTIM_FOLLOW_SPACING_FRAMES = 40

# --- AI rescue agent ---
# Autonomous NPC that runs alongside Pete, using hazard-weighted A*
# (pathfinding.astar_path) to find and escort victims on its own. It has
# health and takes hazard damage exactly like Pete, re-plans its route
# whenever the map changes under it (fire spread, a collapse, a door
# unlocking), and will detour to fetch the key if a locked door blocks
# its goal. See entities/rescue_agent.py.
AGENT_SPEED = 165  # pixels/sec -- tune relative to PLAYER_SPEED to race Pete
AGENT_COLOR = (90, 160, 230)
AGENT_RADIUS = 8              # small dot -- the drawn route is the real "tell"

# Visual style for the AI: "robot" draws the walking sprite in
# assets/robot/ (4-direction idle + walk, matching Pete/victim
# conventions); "drone" draws the original hand-drawn quadcopter, no art
# needed. Automatically falls back to "drone" if assets/robot/ is missing
# or incomplete, so an art-less checkout still runs.
AGENT_VISUAL = "robot"
AGENT_SPRITE_HEIGHT = 88  # matches VICTIM_SPRITE_HEIGHT -- doesn't upstage Pete
AGENT_TRAIL_MAXLEN = PLAYER_TRAIL_MAXLEN
AGENT_ROUTE_COLOR = (120, 190, 255)   # the AI's *planned* route
AGENT_ROUTE_ALPHA = 130
AGENT_TRAIL_COLOR = (150, 150, 158)    # cells the AI has *actually* walked (grey)
AGENT_TRAIL_ALPHA = 70
PLAYER_TRAIL_COLOR = (210, 175, 120)   # cells Pete has walked (warm) -- so a
PLAYER_TRAIL_ALPHA = 60                # side-by-side "who went where" is readable
AGENT_REPLAN_MIN_INTERVAL = 0.25   # seconds -- don't re-run A* more often than this
# The agent doesn't get a map of where the victims are -- it only "knows"
# a victim once it's come within this many tiles of one, same as the
# player learning the building by walking it. Until then it heads for the
# nearest unexplored area. Makes the race fair and means the AI plans
# under uncertainty (and sometimes commits to a wrong direction, then
# re-plans when it finds out) rather than beelining omnisciently.
AGENT_VISION_TILES = 3.5

# --- Run stats / score / results ---
# Both rescuers are instrumented (see stats.py) so the end screen can show
# a real human-vs-AI comparison, which is the point of running an
# autonomous agent next to the player.
#
# Scoring: leading occupants out is the objective, so that's the bulk of
# the score; getting yourself out is a smaller bonus; a speed bonus and a
# damage penalty separate a fast/reckless run from a slow/careful one
# (which is exactly the human-vs-AI trade-off worth showing).
SCORE_PER_SURVIVOR = 100      # each occupant led to the exit
SCORE_REACH_EXIT = 50        # you (or the drone) got out too
SCORE_TIME_BONUS_PAR = 90.0  # beat this many seconds for a speed bonus
SCORE_TIME_BONUS_MAX = 60    # points for an instant finish, scaling to 0 at PAR
SCORE_DAMAGE_PENALTY = 0.4   # points lost per point of health burned off

RESULTS_PANEL_COLOR = (24, 26, 32)
RESULTS_TEXT_COLOR = (232, 232, 232)
RESULTS_ACCENT_COLOR = (235, 196, 60)
