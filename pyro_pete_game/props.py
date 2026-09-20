"""Per-stage set dressing: the furniture that tells you what room you're in.

Every stage is generated from the same recursive-backtracker maze, so
without this they are ten identical grey corridor grids with different
names in the HUD. A stage's THEME gives it a palette (floor, wall and an
accent) and a bag of props -- tables and chairs in the canteen, racks in
the server room, parked cars in the car park, open sky on the roof.

Two rules shape everything here:

1. **Props never block anything.** They are drawn, not collided with.
   Making a chair solid would change which routes exist, which changes
   maze solvability, the A* agent's plan, the difficulty tuning and the
   observations the learned agent trains on -- a very large blast radius
   for set dressing. So `is_walkable()` never consults this module, and a
   stage plays exactly as it did before it was decorated.

2. **Drawn, not loaded.** Like intro.py and tilemap.py, the props are
   pygame primitives rather than sprite files, so ten themed stages cost
   nothing in the repository and look the same on every machine.

Placement is seeded off the stage's own SEED, so a stage's furniture is
in the same place every run -- the same reproducibility the maze itself
has, and it means a screenshot of stage 4 is always the same stage 4.
"""

import math
import random

import pygame

from settings import FLOOR_COLOR, WALL_COLOR, GRID_LINE_COLOR


# --------------------------------------------------------------- palettes
class Palette:
    """The three colours a theme repaints the tile grid with.

    `floor` and `wall` replace the settings.py defaults for this stage;
    `accent` is the prop colour the theme leans on, so the furniture
    reads as belonging to the room rather than sitting on top of it.
    """

    __slots__ = ("floor", "wall", "accent")

    def __init__(self, floor, wall, accent):
        self.floor = floor
        self.wall = wall
        self.accent = accent


DEFAULT_PALETTE = Palette(FLOOR_COLOR, WALL_COLOR, GRID_LINE_COLOR)


class Theme:
    """A stage's look: what the tiles are painted and what stands on them.

    `props` is a list of (kind, weight) -- the weight is relative, so
    ("chair", 3) against ("fridge", 1) puts roughly three times as many
    chairs down as fridges. `density` is the fraction of eligible floor
    tiles that get something on them; too high and the corridors read as
    cluttered rather than furnished, so these stay between 0.10 and 0.22.
    """

    __slots__ = ("name", "palette", "props", "density")

    def __init__(self, name, palette, props, density=0.16):
        self.name = name
        self.palette = palette
        self.props = props
        self.density = density


THEMES = {
    # 1 -- Ground Floor: an office lobby. Warm, tidy, nothing threatening
    # yet; this is the stage that has to look safe so the later ones read
    # as a step down into something worse.
    "lobby": Theme(
        "lobby",
        Palette((52, 56, 64), (84, 66, 52), (128, 104, 74)),
        [("desk", 2), ("bench", 3), ("planter", 3), ("noticeboard", 2)],
        density=0.13,
    ),
    # 2 -- Staff Canteen: tables and chairs, a serving counter, fridges.
    "canteen": Theme(
        "canteen",
        Palette((58, 58, 62), (92, 74, 56), (176, 150, 104)),
        [("table", 3), ("chair", 5), ("counter", 2), ("fridge", 1)],
        density=0.20,
    ),
    # 3 -- Records Office: filing cabinets and paper. Paper is also the
    # visual excuse for how fast this stage burns.
    "records": Theme(
        "records",
        Palette((54, 52, 50), (88, 70, 50), (150, 134, 96)),
        [("cabinet", 4), ("shelf", 3), ("desk", 2), ("paper", 3)],
        density=0.19,
    ),
    # 4 -- Server Room: racks and cable trays, cold blue light.
    "server": Theme(
        "server",
        Palette((40, 46, 56), (58, 64, 78), (86, 140, 190)),
        [("rack", 5), ("cabletray", 3), ("console", 2), ("cooler", 2)],
        density=0.18,
    ),
    # 5 -- Chemical Store: drums and crates, hazard yellow.
    "chemical": Theme(
        "chemical",
        Palette((50, 50, 44), (86, 76, 44), (196, 168, 60)),
        [("drum", 4), ("crate", 3), ("hazardsign", 2), ("eyewash", 1)],
        density=0.19,
    ),
    # 6 -- Car Park B2: concrete, pillars, parked cars, bay markings.
    "carpark": Theme(
        "carpark",
        Palette((62, 64, 68), (74, 76, 80), (150, 154, 160)),
        [("car", 3), ("pillar", 3), ("baymark", 4), ("cone", 2)],
        density=0.17,
    ),
    # 7 -- Ward Block: beds, screens, drip stands. Clinical pale green.
    "ward": Theme(
        "ward",
        Palette((56, 64, 62), (96, 104, 98), (176, 196, 186)),
        [("bed", 4), ("screen", 3), ("dripstand", 3), ("trolley", 2)],
        density=0.18,
    ),
    # 8 -- Turbine Hall: heavy plant. Big machines, pipework, gantry rail.
    "turbine": Theme(
        "turbine",
        Palette((48, 48, 52), (80, 72, 62), (168, 128, 66)),
        [("turbine", 3), ("pipe", 4), ("valve", 3), ("gantry", 2)],
        density=0.18,
    ),
    # 9 -- Reactor Annex: shielding, coolant tanks, radiation trefoils.
    "reactor": Theme(
        "reactor",
        Palette((44, 52, 48), (66, 78, 70), (140, 200, 120)),
        [("tank", 3), ("shielding", 3), ("console", 3), ("radsign", 2)],
        density=0.18,
    ),
    # 10 -- Roof Plant: outdoors at last. The palette goes cold and pale
    # (night sky, not interior), and `sky` props are the open-air gaps
    # beyond the parapet -- the only theme where the "prop" is an absence
    # of building.
    "roof": Theme(
        "roof",
        Palette((66, 72, 84), (58, 62, 76), (150, 168, 196)),
        [("sky", 4), ("hvac", 3), ("vent", 3), ("aerial", 2), ("duct", 2)],
        density=0.20,
    ),
}


def palette_for(theme_name):
    """The palette a TileMap should paint itself with. Unknown or missing
    theme -> the settings.py defaults, so an undecorated map is unchanged."""
    theme = THEMES.get(theme_name)
    return theme.palette if theme else DEFAULT_PALETTE


# -------------------------------------------------------------- placement
def _shade(color, factor):
    """Lighten (factor > 1) or darken (factor < 1) a colour, clamped."""
    return tuple(max(0, min(255, int(c * factor))) for c in color)


def _weighted_kinds(spec, rng, count):
    kinds = [k for k, _ in spec]
    weights = [w for _, w in spec]
    return rng.choices(kinds, weights=weights, k=count)


def place(tilemap, theme_name, seed=0):
    """Choose what stands where. Returns {(col, row): (kind, variant)}.

    Eligible tiles are plain floor only: never a wall, never the exit,
    and never within one tile of the spawn or the exit, so the two places
    the player needs to read at a glance stay clear of furniture.

    `variant` is a per-prop number the draw functions use for small
    rotations and offsets, so a room full of chairs doesn't look stamped.
    """
    theme = THEMES.get(theme_name)
    if theme is None:
        return {}

    from tilemap import WALL, EXIT   # local: tilemap imports this module

    keep_clear = set()
    for cell in (tilemap.spawn_cell, tilemap.exit_cell):
        c, r = cell
        for dc in (-1, 0, 1):
            for dr in (-1, 0, 1):
                keep_clear.add((c + dc, r + dr))

    eligible = [
        (c, r)
        for r in range(tilemap.rows)
        for c in range(tilemap.cols)
        if tilemap.grid[r][c] not in (WALL, EXIT) and (c, r) not in keep_clear
    ]

    rng = random.Random(seed ^ 0x9E3779B9)
    rng.shuffle(eligible)
    count = int(len(eligible) * theme.density)
    chosen = eligible[:count]
    kinds = _weighted_kinds(theme.props, rng, len(chosen))
    return {cell: (kind, rng.random())
            for cell, kind in zip(chosen, kinds)}


# ---------------------------------------------------------------- drawing
# Each draw function fills one tile rect. They deliberately stay simple
# shapes: at 64px a tile, detail beyond a few rects and circles is lost,
# and the fog of war dims most of them most of the time anyway.

def _inset(rect, fx, fy=None):
    """A rect inset to a fraction of the tile, centred."""
    fy = fx if fy is None else fy
    w, h = int(rect.width * fx), int(rect.height * fy)
    return pygame.Rect(rect.centerx - w // 2, rect.centery - h // 2, w, h)


def _box(surface, rect, color, border=None):
    pygame.draw.rect(surface, color, rect, border_radius=2)
    pygame.draw.rect(surface, border or _shade(color, 0.65), rect, 1,
                     border_radius=2)


def _draw_desk(s, r, pal, v):
    body = _inset(r, 0.72, 0.46)
    body.centery = r.centery + int((v - 0.5) * r.height * 0.18)
    _box(s, body, pal.accent)
    pygame.draw.line(s, _shade(pal.accent, 0.6),
                     (body.left + 3, body.centery), (body.right - 3, body.centery))


def _draw_bench(s, r, pal, v):
    body = _inset(r, 0.78, 0.3) if v < 0.5 else _inset(r, 0.3, 0.78)
    _box(s, body, _shade(pal.accent, 0.85))


def _draw_planter(s, r, pal, v):
    pot = _inset(r, 0.42)
    pygame.draw.rect(s, _shade(pal.accent, 0.7), pot, border_radius=3)
    leaf = (74, 132, 82)
    pygame.draw.circle(s, leaf, (pot.centerx, pot.top + 2),
                       max(4, int(r.width * 0.16)))


def _draw_noticeboard(s, r, pal, v):
    board = _inset(r, 0.62, 0.38)
    _box(s, board, _shade(pal.accent, 0.75))
    for i in range(3):
        x = board.left + 4 + i * max(4, board.width // 4)
        pygame.draw.rect(s, (216, 212, 200), (x, board.top + 4, 5, 6))


def _draw_table(s, r, pal, v):
    top = _inset(r, 0.62)
    pygame.draw.rect(s, pal.accent, top, border_radius=4)
    pygame.draw.rect(s, _shade(pal.accent, 0.6), top, 1, border_radius=4)
    for cx, cy in ((top.left + 3, top.top + 3), (top.right - 4, top.top + 3),
                   (top.left + 3, top.bottom - 4), (top.right - 4, top.bottom - 4)):
        pygame.draw.rect(s, _shade(pal.accent, 0.5), (cx, cy, 2, 2))


def _draw_chair(s, r, pal, v):
    seat = _inset(r, 0.3)
    off = int((v - 0.5) * r.width * 0.3)
    seat.move_ip(off, int((v - 0.5) * r.height * 0.3))
    _box(s, seat, _shade(pal.accent, 0.78))
    back = pygame.Rect(seat.left, seat.top - 3, seat.width, 3)
    pygame.draw.rect(s, _shade(pal.accent, 0.55), back)


def _draw_counter(s, r, pal, v):
    body = _inset(r, 0.86, 0.34)
    _box(s, body, _shade(pal.accent, 0.9))
    pygame.draw.line(s, (206, 200, 186), (body.left + 2, body.top + 2),
                     (body.right - 2, body.top + 2), 2)


def _draw_fridge(s, r, pal, v):
    body = _inset(r, 0.46, 0.7)
    _box(s, body, (188, 192, 198))
    pygame.draw.line(s, (120, 124, 130), (body.left + 2, body.centery),
                     (body.right - 2, body.centery))
    pygame.draw.rect(s, (110, 114, 120), (body.right - 5, body.centery - 6, 2, 5))


def _draw_cabinet(s, r, pal, v):
    body = _inset(r, 0.5, 0.72)
    _box(s, body, _shade(pal.accent, 0.8))
    for i in range(3):
        y = body.top + 4 + i * max(4, body.height // 3)
        pygame.draw.rect(s, _shade(pal.accent, 0.55), (body.left + 3, y, body.width - 6, 2))


def _draw_shelf(s, r, pal, v):
    body = _inset(r, 0.8, 0.44) if v < 0.5 else _inset(r, 0.44, 0.8)
    _box(s, body, _shade(pal.accent, 0.7))
    if body.width > body.height:
        pygame.draw.line(s, _shade(pal.accent, 0.45),
                         (body.left + 2, body.centery), (body.right - 2, body.centery))
    else:
        pygame.draw.line(s, _shade(pal.accent, 0.45),
                         (body.centerx, body.top + 2), (body.centerx, body.bottom - 2))


def _draw_paper(s, r, pal, v):
    """Scattered paper -- also why this stage burns the way it does."""
    rng = random.Random(int(v * 10_000))
    for _ in range(4):
        x = r.left + rng.randint(4, max(5, r.width - 10))
        y = r.top + rng.randint(4, max(5, r.height - 8))
        pygame.draw.rect(s, (214, 210, 196), (x, y, 6, 4))


def _draw_rack(s, r, pal, v):
    body = _inset(r, 0.44, 0.8)
    _box(s, body, (44, 48, 58))
    for i in range(5):
        y = body.top + 3 + i * max(3, (body.height - 6) // 5)
        pygame.draw.rect(s, (30, 34, 42), (body.left + 3, y, body.width - 6, 2))
        if (i + int(v * 5)) % 2 == 0:
            pygame.draw.rect(s, pal.accent, (body.right - 6, y, 2, 2))


def _draw_cabletray(s, r, pal, v):
    y = r.centery + int((v - 0.5) * r.height * 0.4)
    pygame.draw.rect(s, _shade(pal.accent, 0.5), (r.left, y - 3, r.width, 6))
    for i in range(3):
        pygame.draw.line(s, _shade(pal.accent, 0.9),
                         (r.left, y - 2 + i * 2), (r.right, y - 2 + i * 2))


def _draw_console(s, r, pal, v):
    body = _inset(r, 0.62, 0.42)
    _box(s, body, (52, 58, 66))
    screen = _inset(body, 0.8, 0.55)
    pygame.draw.rect(s, _shade(pal.accent, 0.8), screen)
    for i in range(3):
        if (i + int(v * 3)) % 2:
            pygame.draw.rect(s, (230, 120, 80),
                             (body.left + 3 + i * 5, body.bottom - 5, 3, 3))


def _draw_cooler(s, r, pal, v):
    body = _inset(r, 0.56, 0.56)
    _box(s, body, (70, 84, 96))
    pygame.draw.circle(s, _shade(pal.accent, 1.1), body.center,
                       max(4, int(body.width * 0.3)), 2)


def _draw_drum(s, r, pal, v):
    rad = max(6, int(r.width * 0.2))
    cx = r.centerx + int((v - 0.5) * r.width * 0.3)
    cy = r.centery + int((v - 0.5) * r.height * 0.3)
    pygame.draw.circle(s, _shade(pal.accent, 0.85), (cx, cy), rad)
    pygame.draw.circle(s, _shade(pal.accent, 0.5), (cx, cy), rad, 2)
    pygame.draw.circle(s, _shade(pal.accent, 1.15), (cx, cy), max(2, rad // 2), 1)


def _draw_crate(s, r, pal, v):
    body = _inset(r, 0.5)
    _box(s, body, _shade(pal.accent, 0.7))
    pygame.draw.line(s, _shade(pal.accent, 0.45), body.topleft, body.bottomright)
    pygame.draw.line(s, _shade(pal.accent, 0.45), body.topright, body.bottomleft)


def _draw_hazardsign(s, r, pal, v):
    size = max(8, int(r.width * 0.3))
    cx, cy = r.centerx, r.centery
    pts = [(cx, cy - size // 2), (cx + size // 2, cy + size // 2),
           (cx - size // 2, cy + size // 2)]
    pygame.draw.polygon(s, (226, 192, 60), pts)
    pygame.draw.polygon(s, (40, 36, 24), pts, 2)
    pygame.draw.line(s, (40, 36, 24), (cx, cy - 2), (cx, cy + 3), 2)


def _draw_eyewash(s, r, pal, v):
    body = _inset(r, 0.3, 0.5)
    _box(s, body, (80, 150, 170))
    pygame.draw.rect(s, (200, 230, 240), (body.centerx - 2, body.top - 3, 4, 3))


def _draw_car(s, r, pal, v):
    horiz = v < 0.5
    body = _inset(r, 0.86, 0.5) if horiz else _inset(r, 0.5, 0.86)
    hue = [(132, 64, 60), (60, 84, 128), (86, 96, 104), (140, 132, 92)][int(v * 4) % 4]
    pygame.draw.rect(s, hue, body, border_radius=5)
    pygame.draw.rect(s, _shade(hue, 0.6), body, 1, border_radius=5)
    glass = _inset(body, 0.5, 0.62) if horiz else _inset(body, 0.62, 0.5)
    pygame.draw.rect(s, _shade(hue, 1.5), glass, border_radius=2)


def _draw_pillar(s, r, pal, v):
    body = _inset(r, 0.46)
    pygame.draw.rect(s, _shade(pal.wall, 1.1), body)
    pygame.draw.rect(s, _shade(pal.wall, 0.7), body, 2)
    pygame.draw.rect(s, (216, 180, 60), (body.left, body.bottom - 4, body.width, 3))


def _draw_baymark(s, r, pal, v):
    """Painted parking bay lines -- floor markings, nothing standing."""
    col = (198, 190, 150)
    if v < 0.5:
        pygame.draw.line(s, col, (r.left + 6, r.top + 5), (r.left + 6, r.bottom - 5), 2)
        pygame.draw.line(s, col, (r.right - 6, r.top + 5), (r.right - 6, r.bottom - 5), 2)
    else:
        pygame.draw.line(s, col, (r.left + 5, r.top + 6), (r.right - 5, r.top + 6), 2)


def _draw_cone(s, r, pal, v):
    cx = r.centerx + int((v - 0.5) * r.width * 0.3)
    cy = r.centery
    size = max(7, int(r.width * 0.22))
    pygame.draw.polygon(s, (222, 118, 48),
                        [(cx, cy - size), (cx + size // 2, cy + size // 2),
                         (cx - size // 2, cy + size // 2)])
    pygame.draw.rect(s, (238, 238, 236), (cx - size // 2, cy + size // 2 - 1, size, 2))


def _draw_bed(s, r, pal, v):
    horiz = v < 0.5
    body = _inset(r, 0.78, 0.44) if horiz else _inset(r, 0.44, 0.78)
    _box(s, body, (222, 226, 224))
    if horiz:
        pygame.draw.rect(s, _shade(pal.accent, 0.8), (body.left + 2, body.top + 2, 8, body.height - 4))
        pygame.draw.rect(s, (150, 178, 196), (body.left + 12, body.top + 2, body.width - 14, body.height - 4))
    else:
        pygame.draw.rect(s, _shade(pal.accent, 0.8), (body.left + 2, body.top + 2, body.width - 4, 8))
        pygame.draw.rect(s, (150, 178, 196), (body.left + 2, body.top + 12, body.width - 4, body.height - 14))


def _draw_screen(s, r, pal, v):
    """A privacy curtain on wheels."""
    body = _inset(r, 0.7, 0.2) if v < 0.5 else _inset(r, 0.2, 0.7)
    pygame.draw.rect(s, (168, 196, 190), body)
    pygame.draw.rect(s, (96, 124, 120), body, 1)


def _draw_dripstand(s, r, pal, v):
    cx = r.centerx + int((v - 0.5) * r.width * 0.3)
    top = r.top + 6
    pygame.draw.line(s, (176, 182, 186), (cx, top), (cx, r.bottom - 8), 2)
    pygame.draw.circle(s, (176, 182, 186), (cx, r.bottom - 8), 3, 1)
    pygame.draw.rect(s, (208, 228, 236), (cx + 1, top, 6, 9), border_radius=2)


def _draw_trolley(s, r, pal, v):
    body = _inset(r, 0.5, 0.36)
    _box(s, body, (188, 194, 198))
    pygame.draw.line(s, (120, 128, 132), (body.left + 2, body.centery),
                     (body.right - 2, body.centery))


def _draw_turbine(s, r, pal, v):
    body = _inset(r, 0.76, 0.5)
    pygame.draw.rect(s, _shade(pal.accent, 0.62), body, border_radius=8)
    pygame.draw.rect(s, _shade(pal.accent, 0.4), body, 2, border_radius=8)
    pygame.draw.circle(s, _shade(pal.accent, 1.1), body.center, max(4, body.height // 3), 2)


def _draw_pipe(s, r, pal, v):
    col = _shade(pal.accent, 0.7)
    if v < 0.5:
        pygame.draw.rect(s, col, (r.left, r.centery - 5, r.width, 10))
        pygame.draw.line(s, _shade(col, 1.3), (r.left, r.centery - 3), (r.right, r.centery - 3), 2)
    else:
        pygame.draw.rect(s, col, (r.centerx - 5, r.top, 10, r.height))
        pygame.draw.line(s, _shade(col, 1.3), (r.centerx - 3, r.top), (r.centerx - 3, r.bottom), 2)


def _draw_valve(s, r, pal, v):
    cx, cy = r.centerx, r.centery
    rad = max(6, int(r.width * 0.18))
    pygame.draw.circle(s, _shade(pal.accent, 0.8), (cx, cy), rad, 3)
    pygame.draw.line(s, (196, 80, 60), (cx - rad, cy), (cx + rad, cy), 2)
    pygame.draw.line(s, (196, 80, 60), (cx, cy - rad), (cx, cy + rad), 2)


def _draw_gantry(s, r, pal, v):
    col = _shade(pal.accent, 0.55)
    y = r.top + 8 if v < 0.5 else r.bottom - 10
    pygame.draw.line(s, col, (r.left, y), (r.right, y), 3)
    for x in range(r.left + 6, r.right, 14):
        pygame.draw.line(s, col, (x, y), (x, y + 6), 2)


def _draw_tank(s, r, pal, v):
    body = _inset(r, 0.5, 0.72)
    pygame.draw.rect(s, (110, 122, 130), body, border_radius=10)
    pygame.draw.rect(s, (66, 76, 84), body, 2, border_radius=10)
    pygame.draw.rect(s, _shade(pal.accent, 0.9), (body.left + 3, body.centery - 2, body.width - 6, 4))


def _draw_shielding(s, r, pal, v):
    body = _inset(r, 0.8, 0.42) if v < 0.5 else _inset(r, 0.42, 0.8)
    pygame.draw.rect(s, (92, 100, 94), body)
    pygame.draw.rect(s, (56, 64, 60), body, 2)
    for i in range(2):
        pygame.draw.line(s, (56, 64, 60),
                         (body.left + (i + 1) * body.width // 3, body.top),
                         (body.left + (i + 1) * body.width // 3, body.bottom))


def _draw_radsign(s, r, pal, v):
    cx, cy = r.centerx, r.centery
    rad = max(7, int(r.width * 0.2))
    pygame.draw.circle(s, (226, 200, 60), (cx, cy), rad)
    pygame.draw.circle(s, (40, 40, 30), (cx, cy), rad, 1)
    for ang in (0, 120, 240):
        a = math.radians(ang - 30)
        b = math.radians(ang + 30)
        pygame.draw.polygon(s, (40, 40, 30), [
            (cx, cy),
            (cx + rad * 0.95 * math.cos(a), cy + rad * 0.95 * math.sin(a)),
            (cx + rad * 0.95 * math.cos(b), cy + rad * 0.95 * math.sin(b)),
        ])
    pygame.draw.circle(s, (226, 200, 60), (cx, cy), max(2, rad // 4))


def _draw_sky(s, r, pal, v):
    """Open air: a gap in the roof deck with a low parapet on one side.

    The only "prop" that is a hole rather than an object -- it is what
    makes the last stage read as being outdoors on top of the building
    rather than in one more grey room.
    """
    gap = _inset(r, 0.82)
    night = (26, 32, 48)
    pygame.draw.rect(s, night, gap)
    pygame.draw.rect(s, _shade(pal.accent, 0.5), gap, 2)
    rng = random.Random(int(v * 10_000))
    for _ in range(3):
        x = gap.left + rng.randint(2, max(3, gap.width - 3))
        y = gap.top + rng.randint(2, max(3, gap.height - 3))
        pygame.draw.rect(s, (188, 200, 224), (x, y, 2, 2))


def _draw_hvac(s, r, pal, v):
    body = _inset(r, 0.68, 0.58)
    _box(s, body, (108, 116, 130))
    pygame.draw.circle(s, (72, 80, 94), body.center, max(5, body.height // 3))
    pygame.draw.circle(s, _shade(pal.accent, 1.1), body.center, max(5, body.height // 3), 2)


def _draw_vent(s, r, pal, v):
    body = _inset(r, 0.5, 0.5)
    pygame.draw.rect(s, (96, 104, 118), body)
    pygame.draw.rect(s, (60, 66, 78), body, 1)
    for i in range(3):
        y = body.top + 3 + i * max(3, body.height // 3)
        pygame.draw.line(s, (60, 66, 78), (body.left + 2, y), (body.right - 2, y))


def _draw_aerial(s, r, pal, v):
    cx = r.centerx + int((v - 0.5) * r.width * 0.25)
    base = r.bottom - 8
    pygame.draw.line(s, (176, 186, 200), (cx, base), (cx, r.top + 6), 2)
    for i, w in enumerate((10, 7, 4)):
        y = r.top + 10 + i * 6
        pygame.draw.line(s, (176, 186, 200), (cx - w // 2, y), (cx + w // 2, y))
    pygame.draw.circle(s, (120, 130, 144), (cx, base), 3)


def _draw_duct(s, r, pal, v):
    col = (118, 126, 138)
    if v < 0.5:
        body = pygame.Rect(r.left, r.centery - 7, r.width, 14)
    else:
        body = pygame.Rect(r.centerx - 7, r.top, 14, r.height)
    pygame.draw.rect(s, col, body)
    pygame.draw.rect(s, _shade(col, 0.7), body, 1)
    if body.width > body.height:
        for x in range(body.left + 5, body.right, 10):
            pygame.draw.line(s, _shade(col, 0.7), (x, body.top), (x, body.bottom))
    else:
        for y in range(body.top + 5, body.bottom, 10):
            pygame.draw.line(s, _shade(col, 0.7), (body.left, y), (body.right, y))


DRAWERS = {
    "desk": _draw_desk, "bench": _draw_bench, "planter": _draw_planter,
    "noticeboard": _draw_noticeboard,
    "table": _draw_table, "chair": _draw_chair, "counter": _draw_counter,
    "fridge": _draw_fridge,
    "cabinet": _draw_cabinet, "shelf": _draw_shelf, "paper": _draw_paper,
    "rack": _draw_rack, "cabletray": _draw_cabletray, "console": _draw_console,
    "cooler": _draw_cooler,
    "drum": _draw_drum, "crate": _draw_crate, "hazardsign": _draw_hazardsign,
    "eyewash": _draw_eyewash,
    "car": _draw_car, "pillar": _draw_pillar, "baymark": _draw_baymark,
    "cone": _draw_cone,
    "bed": _draw_bed, "screen": _draw_screen, "dripstand": _draw_dripstand,
    "trolley": _draw_trolley,
    "turbine": _draw_turbine, "pipe": _draw_pipe, "valve": _draw_valve,
    "gantry": _draw_gantry,
    "tank": _draw_tank, "shielding": _draw_shielding, "radsign": _draw_radsign,
    "sky": _draw_sky, "hvac": _draw_hvac, "vent": _draw_vent,
    "aerial": _draw_aerial, "duct": _draw_duct,
}


def draw(surface, placements, palette, camera_offset, tile_size,
         cols, rows, skip_cells=()):
    """Draw every prop the camera can see.

    Culls to the visible tile range the same way TileMap.draw does --
    stage 10 is 31x21 tiles and only a fraction is on screen at a time,
    so drawing all of them every frame would be wasted work.

    `skip_cells` is whatever now covers the floor there (fallen debris, a
    locked door); a chair drawn on top of rubble reads as a bug.
    """
    if not placements:
        return
    ox, oy = camera_offset
    screen_w, screen_h = surface.get_size()
    first_col = max(0, int(ox // tile_size))
    first_row = max(0, int(oy // tile_size))
    last_col = min(cols, int((ox + screen_w) // tile_size) + 1)
    last_row = min(rows, int((oy + screen_h) // tile_size) + 1)

    for row in range(first_row, last_row):
        for col in range(first_col, last_col):
            found = placements.get((col, row))
            if not found or (col, row) in skip_cells:
                continue
            kind, variant = found
            drawer = DRAWERS.get(kind)
            if drawer is None:
                continue
            rect = pygame.Rect(col * tile_size - ox, row * tile_size - oy,
                               tile_size, tile_size)
            drawer(surface, rect, palette, variant)
