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

# Sprites come from several different AI-generation batches at wildly
# different native resolutions (300-600px tall). Scale everyone down to
# a consistent in-game height so Pete reads sensibly against a 64px tile.
PLAYER_SPRITE_HEIGHT = 96
