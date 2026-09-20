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
# Each draw function fills one tile rect (64px). Three rules keep them
# readable at that size and under the fog:
#
# 1. A contact shadow under everything that stands up, so props sit on
#    the floor instead of floating on it.
# 2. Distinct silhouettes. Six props that are all "a rectangle with a
#    line through it" are six props the player cannot tell apart, which
#    was the first version's real failing.
# 3. Detail that identifies rather than decorates -- a chair needs a
#    back, a plant needs foliage wider than its pot, paper needs to look
#    like sheets rather than scattered dots.

def _inset(rect, fx, fy=None):
    """A rect inset to a fraction of the tile, centred."""
    fy = fx if fy is None else fy
    w, h = int(rect.width * fx), int(rect.height * fy)
    return pygame.Rect(rect.centerx - w // 2, rect.centery - h // 2, w, h)


def _shadow(s, rect, pal, dx=2, dy=3, radius=3):
    """Contact shadow: the floor colour darkened, offset down-right.

    Cheaper than an alpha surface (no per-frame allocation) and reads the
    same at this size, because it is always drawn straight onto floor.
    """
    pygame.draw.rect(s, _shade(pal.floor, 0.68), rect.move(dx, dy),
                     border_radius=radius)


def _body(s, rect, color, radius=2, lit=True):
    """A solid object: fill, a lit top edge for volume, a darker outline."""
    pygame.draw.rect(s, color, rect, border_radius=radius)
    if lit and rect.height > 4:
        pygame.draw.line(s, _shade(color, 1.3), (rect.left + 2, rect.top + 1),
                         (rect.right - 3, rect.top + 1))
    pygame.draw.rect(s, _shade(color, 0.5), rect, 1, border_radius=radius)


def _legs(s, rect, color, size=3):
    """Four feet peeking out from under a top -- reads as furniture."""
    for cx, cy in ((rect.left, rect.top), (rect.right - size, rect.top),
                   (rect.left, rect.bottom - size),
                   (rect.right - size, rect.bottom - size)):
        pygame.draw.rect(s, color, (cx, cy, size, size))


# -- stage 1: lobby ---------------------------------------------------
def _draw_desk(s, r, pal, v):
    """Office desk from above: worktop, a monitor at the back, papers."""
    top = _inset(r, 0.80, 0.50)
    _shadow(s, top, pal)
    _body(s, top, pal.accent, radius=2)
    # drawer unit down one end
    end = pygame.Rect(top.left + 2, top.top + 2, 12, top.height - 4)
    pygame.draw.rect(s, _shade(pal.accent, 0.72), end, border_radius=1)
    for i in range(2):
        y = end.top + 3 + i * (end.height // 2)
        pygame.draw.line(s, _shade(pal.accent, 0.45), (end.left + 2, y),
                         (end.right - 2, y))
    # monitor
    mon = pygame.Rect(top.right - 18, top.top + 3, 14, 10)
    pygame.draw.rect(s, (44, 48, 54), mon, border_radius=1)
    pygame.draw.rect(s, (96, 140, 170), mon.inflate(-4, -4))
    # papers
    pygame.draw.rect(s, (226, 222, 210), (top.centerx - 3, top.bottom - 9, 9, 6))


def _draw_bench(s, r, pal, v):
    """Slatted bench -- the gaps between planks are what stop this
    reading as yet another plain rectangle."""
    horiz = v < 0.5
    body = _inset(r, 0.82, 0.34) if horiz else _inset(r, 0.34, 0.82)
    _shadow(s, body, pal)
    wood = _shade(pal.accent, 0.88)
    pygame.draw.rect(s, _shade(wood, 0.6), body, border_radius=2)
    if horiz:
        for i in range(3):
            slat = pygame.Rect(body.left + 1, body.top + 1 + i * (body.height // 3),
                               body.width - 2, max(2, body.height // 3 - 2))
            pygame.draw.rect(s, wood, slat, border_radius=1)
        _legs(s, body, _shade(wood, 0.45))
    else:
        for i in range(3):
            slat = pygame.Rect(body.left + 1 + i * (body.width // 3), body.top + 1,
                               max(2, body.width // 3 - 2), body.height - 2)
            pygame.draw.rect(s, wood, slat, border_radius=1)
        _legs(s, body, _shade(wood, 0.45))


def _draw_planter(s, r, pal, v):
    """A pot with a plant in it, seen from above.

    The foliage has to be *wider than the pot* and clearly leafy, or it
    reads as a lump of soil -- which is exactly what the first version
    looked like.
    """
    cx, cy = r.centerx, r.centery + 2
    pot_r = max(9, int(r.width * 0.26))
    pygame.draw.circle(s, _shade(pal.floor, 0.68), (cx + 2, cy + 3), pot_r)
    pygame.draw.circle(s, (146, 94, 62), (cx, cy), pot_r)          # terracotta
    pygame.draw.circle(s, (176, 118, 80), (cx, cy), pot_r, 2)      # rim
    pygame.draw.circle(s, (72, 52, 38), (cx, cy), pot_r - 3)       # soil
    # foliage: overlapping leaves spilling over the rim
    leaves = ((0, -7, 7, (96, 156, 86)), (-8, -2, 6, (74, 132, 72)),
              (8, -2, 6, (74, 132, 72)), (-4, 5, 5, (110, 172, 96)),
              (5, 5, 5, (88, 148, 80)), (0, -1, 6, (120, 182, 104)))
    for dx, dy, rad, col in leaves:
        pygame.draw.circle(s, col, (cx + dx, cy + dy), rad)
    pygame.draw.circle(s, (56, 100, 58), (cx, cy - 1), 3)          # crown


def _draw_noticeboard(s, r, pal, v):
    """Cork board with pinned notices."""
    board = _inset(r, 0.70, 0.46)
    _shadow(s, board, pal, dy=2)
    pygame.draw.rect(s, (156, 118, 74), board, border_radius=1)     # cork
    pygame.draw.rect(s, _shade(pal.accent, 0.55), board, 2, border_radius=1)
    notes = ((226, 222, 208), (232, 214, 140), (206, 220, 232))
    for i in range(3):
        x = board.left + 4 + i * ((board.width - 6) // 3)
        n = pygame.Rect(x, board.top + 4, 8, 9)
        pygame.draw.rect(s, notes[i], n)
        pygame.draw.rect(s, (180, 60, 50), (n.centerx - 1, n.top - 1, 2, 2))
    pygame.draw.rect(s, (226, 222, 208), (board.left + 6, board.bottom - 10, 10, 7))


# -- stage 2: canteen -------------------------------------------------
def _draw_table(s, r, pal, v):
    """Round canteen table: a circular top with legs under it."""
    cx, cy = r.centerx, r.centery
    rad = max(11, int(r.width * 0.30))
    pygame.draw.circle(s, _shade(pal.floor, 0.68), (cx + 2, cy + 3), rad)
    for dx, dy in ((-rad + 4, rad - 3), (rad - 5, rad - 3)):
        pygame.draw.rect(s, _shade(pal.accent, 0.4), (cx + dx, cy + dy - 2, 3, 5))
    pygame.draw.circle(s, pal.accent, (cx, cy), rad)
    pygame.draw.circle(s, _shade(pal.accent, 0.55), (cx, cy), rad, 2)
    pygame.draw.circle(s, _shade(pal.accent, 1.12), (cx, cy), rad - 4, 1)


def _draw_chair(s, r, pal, v):
    """Seat plus a clearly separate backrest -- without the back it is
    just a small square, which is what it used to be."""
    face = int(v * 4) % 4                      # which way the back faces
    seat = _inset(r, 0.36)
    seat.move_ip(int((v - 0.5) * r.width * 0.22),
                 int((v * 7 % 1 - 0.5) * r.height * 0.22))
    _shadow(s, seat, pal, dy=2)
    wood = _shade(pal.accent, 0.82)
    _legs(s, seat.inflate(4, 4), _shade(wood, 0.45), size=2)
    pygame.draw.rect(s, wood, seat, border_radius=2)
    pygame.draw.rect(s, _shade(wood, 0.5), seat, 1, border_radius=2)
    back = {0: pygame.Rect(seat.left - 1, seat.top - 7, seat.width + 2, 6),
            1: pygame.Rect(seat.left - 1, seat.bottom + 1, seat.width + 2, 6),
            2: pygame.Rect(seat.left - 7, seat.top - 1, 6, seat.height + 2),
            3: pygame.Rect(seat.right + 1, seat.top - 1, 6, seat.height + 2)}[face]
    pygame.draw.rect(s, _shade(pal.floor, 0.68), back.move(2, 2), border_radius=2)
    pygame.draw.rect(s, _shade(wood, 0.7), back, border_radius=2)
    pygame.draw.rect(s, _shade(wood, 0.42), back, 1, border_radius=2)


def _draw_counter(s, r, pal, v):
    """Serving counter: worktop, a front panel below it, a till."""
    body = _inset(r, 0.88, 0.42)
    _shadow(s, body, pal)
    front = pygame.Rect(body.left, body.centery, body.width, body.height // 2)
    pygame.draw.rect(s, _shade(pal.accent, 0.6), front)
    top = pygame.Rect(body.left, body.top, body.width, body.height // 2 + 2)
    pygame.draw.rect(s, (198, 198, 192), top)                       # steel top
    pygame.draw.line(s, (232, 232, 228), (top.left + 1, top.top + 1),
                     (top.right - 2, top.top + 1))
    pygame.draw.rect(s, _shade(pal.accent, 0.4), body, 1)
    till = pygame.Rect(body.right - 14, body.top - 5, 11, 8)
    pygame.draw.rect(s, (70, 74, 80), till, border_radius=1)
    pygame.draw.rect(s, (150, 200, 170), till.inflate(-4, -4))


def _draw_fridge(s, r, pal, v):
    """Upright fridge: door seam, handles, a freezer compartment."""
    body = _inset(r, 0.48, 0.74)
    _shadow(s, body, pal)
    _body(s, body, (206, 210, 214), radius=2)
    split = body.top + body.height // 3
    pygame.draw.line(s, (130, 136, 142), (body.left + 1, split),
                     (body.right - 2, split), 2)
    for y in (split - 8, split + 6):
        pygame.draw.rect(s, (96, 102, 110), (body.right - 6, y, 3, 7),
                         border_radius=1)
    pygame.draw.rect(s, (176, 182, 188), (body.left + 3, body.top + 3,
                                          body.width - 6, 4))


# -- stage 3: records -------------------------------------------------
def _draw_cabinet(s, r, pal, v):
    """Filing cabinet: three drawer fronts, each with a handle."""
    body = _inset(r, 0.52, 0.76)
    _shadow(s, body, pal)
    _body(s, body, _shade(pal.accent, 0.78), radius=1)
    for i in range(3):
        d = pygame.Rect(body.left + 2, body.top + 2 + i * ((body.height - 4) // 3),
                        body.width - 4, (body.height - 6) // 3)
        pygame.draw.rect(s, _shade(pal.accent, 0.92), d)
        pygame.draw.rect(s, _shade(pal.accent, 0.45), d, 1)
        pygame.draw.rect(s, (60, 56, 48), (d.centerx - 4, d.centery - 1, 8, 2))


def _draw_shelf(s, r, pal, v):
    """Shelving with books on it -- the coloured spines are the tell."""
    horiz = v < 0.5
    body = _inset(r, 0.84, 0.46) if horiz else _inset(r, 0.46, 0.84)
    _shadow(s, body, pal)
    pygame.draw.rect(s, _shade(pal.accent, 0.55), body, border_radius=1)
    pygame.draw.rect(s, _shade(pal.accent, 0.35), body, 1, border_radius=1)
    spines = ((172, 92, 70), (196, 172, 96), (108, 136, 160), (150, 156, 120),
              (180, 130, 80), (120, 150, 128))
    if horiz:
        for row in range(2):
            y = body.top + 2 + row * (body.height // 2)
            for i in range(6):
                x = body.left + 3 + i * ((body.width - 6) // 6)
                pygame.draw.rect(s, spines[(i + row + int(v * 6)) % 6],
                                 (x, y, max(2, (body.width - 8) // 6), body.height // 2 - 3))
    else:
        for col in range(2):
            x = body.left + 2 + col * (body.width // 2)
            for i in range(6):
                y = body.top + 3 + i * ((body.height - 6) // 6)
                pygame.draw.rect(s, spines[(i + col + int(v * 6)) % 6],
                                 (x, y, body.width // 2 - 3, max(2, (body.height - 8) // 6)))


def _draw_paper(s, r, pal, v):
    """Dropped paperwork: overlapping sheets with ruled lines, not specks.

    Also the visual excuse for how fast this stage burns.
    """
    rng = random.Random(int(v * 10_000))
    for i in range(3):
        x = r.left + 8 + rng.randint(0, max(1, r.width - 30))
        y = r.top + 8 + rng.randint(0, max(1, r.height - 26))
        sheet = pygame.Rect(x, y, 15, 13)
        pygame.draw.rect(s, _shade(pal.floor, 0.72), sheet.move(1, 2))
        pygame.draw.rect(s, (228, 224, 212), sheet)
        pygame.draw.rect(s, (176, 170, 156), sheet, 1)
        for ln in range(3):
            pygame.draw.line(s, (168, 162, 148), (sheet.left + 2, sheet.top + 3 + ln * 3),
                             (sheet.right - 3, sheet.top + 3 + ln * 3))


# -- stage 4: server --------------------------------------------------
def _draw_rack(s, r, pal, v):
    """Server rack: stacked 1U slots and a column of status LEDs."""
    body = _inset(r, 0.48, 0.84)
    _shadow(s, body, pal)
    _body(s, body, (40, 44, 54), radius=1)
    for i in range(6):
        y = body.top + 3 + i * ((body.height - 6) // 6)
        unit = pygame.Rect(body.left + 3, y, body.width - 6, max(2, (body.height - 10) // 6))
        pygame.draw.rect(s, (26, 30, 38), unit)
        pygame.draw.rect(s, (58, 64, 76), unit, 1)
        if (i + int(v * 6)) % 2 == 0:
            pygame.draw.rect(s, pal.accent, (unit.right - 4, unit.top + 1, 2, 2))
        else:
            pygame.draw.rect(s, (110, 200, 130), (unit.right - 4, unit.top + 1, 2, 2))


def _draw_cabletray(s, r, pal, v):
    """Cable tray: side rails with bundled cables running through."""
    horiz = v < 0.5
    if horiz:
        tray = pygame.Rect(r.left, r.centery - 8, r.width, 16)
        pygame.draw.rect(s, _shade(pal.floor, 0.72), tray.move(0, 3))
        pygame.draw.rect(s, (74, 80, 92), tray)
        pygame.draw.rect(s, (48, 54, 64), tray, 1)
        for i, col in enumerate(((86, 140, 190), (196, 170, 90), (170, 96, 86))):
            pygame.draw.line(s, col, (tray.left, tray.top + 4 + i * 4),
                             (tray.right, tray.top + 4 + i * 4), 2)
    else:
        tray = pygame.Rect(r.centerx - 8, r.top, 16, r.height)
        pygame.draw.rect(s, _shade(pal.floor, 0.72), tray.move(3, 0))
        pygame.draw.rect(s, (74, 80, 92), tray)
        pygame.draw.rect(s, (48, 54, 64), tray, 1)
        for i, col in enumerate(((86, 140, 190), (196, 170, 90), (170, 96, 86))):
            pygame.draw.line(s, col, (tray.left + 4 + i * 4, tray.top),
                             (tray.left + 4 + i * 4, tray.bottom), 2)


def _draw_console(s, r, pal, v):
    """Operator console: angled screen, keyboard, indicator lights."""
    base = _inset(r, 0.68, 0.48)
    _shadow(s, base, pal)
    _body(s, base, (58, 64, 74), radius=2)
    screen = pygame.Rect(base.left + 3, base.top + 2, base.width - 6, base.height // 2)
    pygame.draw.rect(s, (24, 30, 38), screen)
    pygame.draw.rect(s, _shade(pal.accent, 0.85), screen.inflate(-4, -4))
    for ln in range(2):
        pygame.draw.line(s, _shade(pal.accent, 1.3),
                         (screen.left + 4, screen.top + 4 + ln * 3),
                         (screen.right - 6, screen.top + 4 + ln * 3))
    kb = pygame.Rect(base.left + 4, base.bottom - 8, base.width - 8, 5)
    pygame.draw.rect(s, (86, 92, 102), kb)
    for i in range(4):
        col = (230, 120, 80) if (i + int(v * 4)) % 2 else (120, 210, 140)
        pygame.draw.rect(s, col, (kb.left + 1 + i * 5, kb.top + 1, 3, 3))


def _draw_cooler(s, r, pal, v):
    """Cooling unit: a finned cylinder, so it cannot be confused with the
    boxy roof HVAC unit."""
    cx, cy = r.centerx, r.centery
    rad = max(10, int(r.width * 0.27))
    pygame.draw.circle(s, _shade(pal.floor, 0.68), (cx + 2, cy + 3), rad)
    pygame.draw.circle(s, (78, 92, 104), (cx, cy), rad)
    pygame.draw.circle(s, (52, 62, 72), (cx, cy), rad, 2)
    for ang in range(0, 360, 30):                       # cooling fins
        a = math.radians(ang)
        pygame.draw.line(s, (52, 62, 72),
                         (cx + (rad - 5) * math.cos(a), cy + (rad - 5) * math.sin(a)),
                         (cx + rad * math.cos(a), cy + rad * math.sin(a)), 2)
    pygame.draw.circle(s, _shade(pal.accent, 1.05), (cx, cy), max(3, rad // 3))
    pygame.draw.circle(s, (30, 38, 46), (cx, cy), 2)


# -- stage 5: chemical ------------------------------------------------
def _draw_drum(s, r, pal, v):
    """Chemical drum from above: lid rings and two bung caps."""
    cx = r.centerx + int((v - 0.5) * r.width * 0.26)
    cy = r.centery + int((v * 5 % 1 - 0.5) * r.height * 0.26)
    rad = max(10, int(r.width * 0.22))
    pygame.draw.circle(s, _shade(pal.floor, 0.68), (cx + 2, cy + 3), rad)
    pygame.draw.circle(s, _shade(pal.accent, 0.9), (cx, cy), rad)
    pygame.draw.circle(s, _shade(pal.accent, 0.45), (cx, cy), rad, 2)
    pygame.draw.circle(s, _shade(pal.accent, 1.15), (cx, cy), rad - 3, 1)
    pygame.draw.circle(s, _shade(pal.accent, 0.6), (cx - rad // 2, cy), 3)
    pygame.draw.circle(s, _shade(pal.accent, 0.6), (cx + rad // 2, cy), 2)


def _draw_crate(s, r, pal, v):
    """Wooden crate: plank lines, corner brackets, a stencil mark."""
    body = _inset(r, 0.56)
    _shadow(s, body, pal)
    wood = _shade(pal.accent, 0.66)
    pygame.draw.rect(s, wood, body)
    for i in range(3):
        y = body.top + 3 + i * (body.height // 3)
        pygame.draw.line(s, _shade(wood, 0.72), (body.left + 1, y), (body.right - 2, y))
    for cx, cy in ((body.left, body.top), (body.right - 5, body.top),
                   (body.left, body.bottom - 5), (body.right - 5, body.bottom - 5)):
        pygame.draw.rect(s, _shade(wood, 0.5), (cx, cy, 5, 5))
    pygame.draw.rect(s, _shade(wood, 0.4), body, 1)
    pygame.draw.line(s, (40, 36, 28), (body.centerx - 3, body.centery),
                     (body.centerx + 3, body.centery), 2)


def _draw_hazardsign(s, r, pal, v):
    """Warning triangle on a small stand."""
    size = max(11, int(r.width * 0.34))
    cx, cy = r.centerx, r.centery - 1
    pts = [(cx, cy - size // 2 - 2), (cx + size // 2 + 1, cy + size // 2),
           (cx - size // 2 - 1, cy + size // 2)]
    pygame.draw.polygon(s, _shade(pal.floor, 0.68),
                        [(x + 2, y + 3) for x, y in pts])
    pygame.draw.polygon(s, (236, 200, 60), pts)
    pygame.draw.polygon(s, (36, 32, 22), pts, 2)
    pygame.draw.line(s, (36, 32, 22), (cx, cy - 3), (cx, cy + 2), 3)
    pygame.draw.rect(s, (36, 32, 22), (cx - 1, cy + 4, 2, 2))
    pygame.draw.rect(s, (90, 86, 72), (cx - size // 2, cy + size // 2, size, 2))


def _draw_eyewash(s, r, pal, v):
    """Eyewash station: basin, two spray heads, a green back plate."""
    body = _inset(r, 0.42, 0.52)
    _shadow(s, body, pal, dy=2)
    pygame.draw.rect(s, (60, 140, 90), body, border_radius=2)       # green plate
    pygame.draw.rect(s, (36, 96, 62), body, 1, border_radius=2)
    basin = pygame.Rect(body.left + 1, body.centery, body.width - 2, body.height // 2 - 1)
    pygame.draw.rect(s, (188, 208, 214), basin, border_radius=2)
    for dx in (-4, 4):
        pygame.draw.rect(s, (150, 168, 178), (body.centerx + dx - 1, body.centery - 5, 2, 5))
        pygame.draw.circle(s, (210, 232, 240), (body.centerx + dx, body.centery - 6), 2)
    pygame.draw.rect(s, (236, 236, 230), (body.centerx - 4, body.top + 2, 8, 3))


# -- stage 6: carpark -------------------------------------------------
def _draw_car(s, r, pal, v):
    """Car from above: windscreen, rear window, roof, mirrors."""
    horiz = v < 0.5
    body = _inset(r, 0.88, 0.48) if horiz else _inset(r, 0.48, 0.88)
    hue = [(150, 66, 62), (58, 88, 136), (92, 100, 110), (158, 148, 102),
           (176, 176, 180)][int(v * 5) % 5]
    _shadow(s, body, pal, radius=6)
    pygame.draw.rect(s, hue, body, border_radius=7)
    pygame.draw.rect(s, _shade(hue, 0.55), body, 1, border_radius=7)
    glass = _shade(hue, 1.7)
    if horiz:
        pygame.draw.rect(s, glass, (body.left + 5, body.top + 3, 8, body.height - 6),
                         border_radius=2)
        pygame.draw.rect(s, glass, (body.right - 12, body.top + 3, 7, body.height - 6),
                         border_radius=2)
        pygame.draw.rect(s, _shade(hue, 1.15),
                         (body.left + 15, body.top + 2, body.width - 28, body.height - 4),
                         border_radius=2)
        for dy in (0, body.height - 3):
            pygame.draw.rect(s, _shade(hue, 0.5), (body.left + 12, body.top + dy, 4, 3))
    else:
        pygame.draw.rect(s, glass, (body.left + 3, body.top + 5, body.width - 6, 8),
                         border_radius=2)
        pygame.draw.rect(s, glass, (body.left + 3, body.bottom - 12, body.width - 6, 7),
                         border_radius=2)
        pygame.draw.rect(s, _shade(hue, 1.15),
                         (body.left + 2, body.top + 15, body.width - 4, body.height - 28),
                         border_radius=2)
        for dx in (0, body.width - 3):
            pygame.draw.rect(s, _shade(hue, 0.5), (body.left + dx, body.top + 12, 3, 4))


def _draw_pillar(s, r, pal, v):
    """Concrete pillar with a hazard-striped kick band."""
    body = _inset(r, 0.5)
    pygame.draw.rect(s, _shade(pal.floor, 0.6), body.move(3, 4))
    pygame.draw.rect(s, _shade(pal.wall, 1.15), body)
    pygame.draw.rect(s, _shade(pal.wall, 0.65), body, 2)
    band = pygame.Rect(body.left, body.bottom - 7, body.width, 6)
    pygame.draw.rect(s, (222, 190, 60), band)
    for i in range(-1, band.width // 5 + 1):        # diagonal hazard stripes
        x = band.left + i * 5
        pygame.draw.polygon(s, (40, 38, 30), [
            (x, band.bottom), (x + 3, band.bottom), (x + 6, band.top), (x + 3, band.top)])
    pygame.draw.rect(s, _shade(pal.wall, 0.65), band, 1)


def _draw_baymark(s, r, pal, v):
    """Painted bay markings -- floor paint, nothing standing, so no shadow."""
    col = (206, 198, 158)
    if v < 0.5:
        pygame.draw.line(s, col, (r.left + 7, r.top + 4), (r.left + 7, r.bottom - 4), 3)
        pygame.draw.line(s, col, (r.right - 7, r.top + 4), (r.right - 7, r.bottom - 4), 3)
        pygame.draw.line(s, col, (r.left + 7, r.bottom - 5), (r.right - 7, r.bottom - 5), 3)
    else:
        pygame.draw.line(s, col, (r.left + 4, r.top + 7), (r.right - 4, r.top + 7), 3)
        pygame.draw.line(s, col, (r.left + 4, r.bottom - 7), (r.right - 4, r.bottom - 7), 3)
        pygame.draw.line(s, col, (r.right - 5, r.top + 7), (r.right - 5, r.bottom - 7), 3)


def _draw_cone(s, r, pal, v):
    """Traffic cone: square base, tapered body, reflective band."""
    cx = r.centerx + int((v - 0.5) * r.width * 0.26)
    cy = r.centery + 4
    size = max(9, int(r.width * 0.26))
    base = pygame.Rect(cx - size, cy + size // 2 - 2, size * 2, 5)
    pygame.draw.ellipse(s, _shade(pal.floor, 0.68), base.move(2, 3))
    pygame.draw.polygon(s, (224, 112, 44),
                        [(cx, cy - size - 2), (cx + size - 2, cy + size // 2),
                         (cx - size + 2, cy + size // 2)])
    pygame.draw.rect(s, (242, 240, 236), (cx - size // 2 - 1, cy - 3, size + 2, 4))
    pygame.draw.polygon(s, (176, 80, 30),
                        [(cx, cy - size - 2), (cx + size - 2, cy + size // 2),
                         (cx - size + 2, cy + size // 2)], 1)
    pygame.draw.rect(s, (200, 96, 36), base, border_radius=2)


# -- stage 7: ward ----------------------------------------------------
def _draw_bed(s, r, pal, v):
    """Hospital bed: headboard bars, pillow, blanket, foot rail."""
    horiz = v < 0.5
    body = _inset(r, 0.84, 0.48) if horiz else _inset(r, 0.48, 0.84)
    _shadow(s, body, pal)
    pygame.draw.rect(s, (228, 230, 228), body, border_radius=2)     # mattress
    pygame.draw.rect(s, (150, 156, 158), body, 1, border_radius=2)
    if horiz:
        head = pygame.Rect(body.left - 3, body.top - 1, 4, body.height + 2)
        pygame.draw.rect(s, (168, 176, 180), head, border_radius=1)
        pygame.draw.rect(s, (244, 246, 246), (body.left + 2, body.top + 2, 10, body.height - 4),
                         border_radius=2)                            # pillow
        pygame.draw.rect(s, (126, 166, 192), (body.left + 14, body.top + 2,
                                              body.width - 18, body.height - 4))
        pygame.draw.line(s, (96, 136, 164), (body.left + 20, body.top + 2),
                         (body.left + 20, body.bottom - 3))
        pygame.draw.rect(s, (168, 176, 180), (body.right - 2, body.top, 3, body.height))
    else:
        head = pygame.Rect(body.left - 1, body.top - 3, body.width + 2, 4)
        pygame.draw.rect(s, (168, 176, 180), head, border_radius=1)
        pygame.draw.rect(s, (244, 246, 246), (body.left + 2, body.top + 2, body.width - 4, 10),
                         border_radius=2)
        pygame.draw.rect(s, (126, 166, 192), (body.left + 2, body.top + 14,
                                              body.width - 4, body.height - 18))
        pygame.draw.line(s, (96, 136, 164), (body.left + 2, body.top + 20),
                         (body.right - 3, body.top + 20))
        pygame.draw.rect(s, (168, 176, 180), (body.left, body.bottom - 2, body.width, 3))


def _draw_screen(s, r, pal, v):
    """Folding privacy screen -- the concertina zigzag is the giveaway."""
    horiz = v < 0.5
    if horiz:
        y = r.centery
        pts = [(r.left + 6, y - 5), (r.left + 18, y + 4), (r.centerx + 2, y - 5),
               (r.right - 12, y + 4), (r.right - 6, y - 3)]
        pygame.draw.lines(s, _shade(pal.floor, 0.68),
                          False, [(x + 1, yy + 3) for x, yy in pts], 6)
        pygame.draw.lines(s, (196, 214, 208), False, pts, 6)
        pygame.draw.lines(s, (118, 146, 142), False, pts, 1)
        for x, yy in pts[::2]:
            pygame.draw.circle(s, (120, 128, 130), (x, yy + 6), 2)
    else:
        x = r.centerx
        pts = [(x - 5, r.top + 6), (x + 4, r.top + 18), (x - 5, r.centery + 2),
               (x + 4, r.bottom - 12), (x - 3, r.bottom - 6)]
        pygame.draw.lines(s, _shade(pal.floor, 0.68),
                          False, [(xx + 3, yy + 1) for xx, yy in pts], 6)
        pygame.draw.lines(s, (196, 214, 208), False, pts, 6)
        pygame.draw.lines(s, (118, 146, 142), False, pts, 1)
        for xx, yy in pts[::2]:
            pygame.draw.circle(s, (120, 128, 130), (xx + 6, yy), 2)


def _draw_dripstand(s, r, pal, v):
    """IV stand: wheeled base, pole, fluid bag with a drip line."""
    cx = r.centerx + int((v - 0.5) * r.width * 0.28)
    top, bot = r.top + 8, r.bottom - 10
    pygame.draw.ellipse(s, _shade(pal.floor, 0.68), (cx - 8, bot - 2, 18, 8))
    for ang in (0, 120, 240):                       # castor legs
        a = math.radians(ang)
        pygame.draw.line(s, (150, 156, 162), (cx, bot),
                         (cx + 8 * math.cos(a), bot + 4 * math.sin(a)), 2)
    pygame.draw.line(s, (186, 192, 198), (cx, top), (cx, bot), 3)
    pygame.draw.line(s, (150, 156, 162), (cx - 5, top + 1), (cx + 5, top + 1), 2)
    bag = pygame.Rect(cx + 2, top + 2, 8, 12)
    pygame.draw.rect(s, (206, 228, 238), bag, border_radius=3)
    pygame.draw.rect(s, (140, 172, 186), bag, 1, border_radius=3)
    pygame.draw.line(s, (170, 196, 208), (bag.centerx, bag.bottom),
                     (bag.centerx - 2, bag.bottom + 8))


def _draw_trolley(s, r, pal, v):
    """Equipment trolley: tray with a raised rim, lower shelf, castors."""
    body = _inset(r, 0.56, 0.42)
    _shadow(s, body, pal)
    pygame.draw.rect(s, (196, 202, 206), body, border_radius=2)
    pygame.draw.rect(s, (128, 134, 140), body, 2, border_radius=2)
    pygame.draw.line(s, (150, 156, 162), (body.left + 2, body.centery + 2),
                     (body.right - 3, body.centery + 2))
    for dx in (3, body.width - 6):                  # castors
        pygame.draw.circle(s, (86, 92, 98), (body.left + dx, body.bottom + 2), 2)
    pygame.draw.rect(s, (150, 190, 180), (body.left + 3, body.top + 2, 7, 5))
    pygame.draw.rect(s, (226, 226, 220), (body.right - 11, body.top + 2, 8, 4))


# -- stage 8: turbine -------------------------------------------------
def _draw_turbine(s, r, pal, v):
    """Turbine set: casing, bolted flanges, a bladed rotor."""
    horiz = v < 0.5
    body = _inset(r, 0.82, 0.52) if horiz else _inset(r, 0.52, 0.82)
    _shadow(s, body, pal, radius=8)
    pygame.draw.rect(s, _shade(pal.accent, 0.62), body, border_radius=9)
    pygame.draw.rect(s, _shade(pal.accent, 0.38), body, 2, border_radius=9)
    if horiz:
        for x in (body.left + 7, body.right - 8):
            pygame.draw.line(s, _shade(pal.accent, 0.42), (x, body.top + 1),
                             (x, body.bottom - 2), 2)
    else:
        for y in (body.top + 7, body.bottom - 8):
            pygame.draw.line(s, _shade(pal.accent, 0.42), (body.left + 1, y),
                             (body.right - 2, y), 2)
    cx, cy = body.center
    rad = max(6, min(body.width, body.height) // 3)
    pygame.draw.circle(s, _shade(pal.accent, 0.45), (cx, cy), rad)
    for ang in range(0, 360, 45):                   # rotor blades
        a = math.radians(ang + v * 40)
        pygame.draw.line(s, _shade(pal.accent, 1.2), (cx, cy),
                         (cx + rad * math.cos(a), cy + rad * math.sin(a)), 2)
    pygame.draw.circle(s, _shade(pal.accent, 1.35), (cx, cy), 3)


def _draw_pipe(s, r, pal, v):
    """Pipe run with flanged joints and a specular highlight."""
    col = _shade(pal.accent, 0.72)
    if v < 0.5:
        body = pygame.Rect(r.left, r.centery - 7, r.width, 14)
        pygame.draw.rect(s, _shade(pal.floor, 0.68), body.move(0, 3))
        pygame.draw.rect(s, col, body)
        pygame.draw.line(s, _shade(col, 1.45), (body.left, body.top + 3),
                         (body.right, body.top + 3), 2)
        pygame.draw.line(s, _shade(col, 0.6), (body.left, body.bottom - 2),
                         (body.right, body.bottom - 2), 2)
        for x in (r.left + 6, r.right - 9):         # flanges
            pygame.draw.rect(s, _shade(col, 0.55), (x, body.top - 2, 3, body.height + 4))
    else:
        body = pygame.Rect(r.centerx - 7, r.top, 14, r.height)
        pygame.draw.rect(s, _shade(pal.floor, 0.68), body.move(3, 0))
        pygame.draw.rect(s, col, body)
        pygame.draw.line(s, _shade(col, 1.45), (body.left + 3, body.top),
                         (body.left + 3, body.bottom), 2)
        pygame.draw.line(s, _shade(col, 0.6), (body.right - 2, body.top),
                         (body.right - 2, body.bottom), 2)
        for y in (r.top + 6, r.bottom - 9):
            pygame.draw.rect(s, _shade(col, 0.55), (body.left - 2, y, body.width + 4, 3))


def _draw_valve(s, r, pal, v):
    """Valve: a pipe stub with a spoked red handwheel on top."""
    cx, cy = r.centerx, r.centery
    rad = max(8, int(r.width * 0.21))
    pygame.draw.rect(s, _shade(pal.floor, 0.68), (cx - 5, cy - 2, 10, rad + 6))
    pygame.draw.rect(s, _shade(pal.accent, 0.6), (cx - 5, cy, 10, rad + 4))
    pygame.draw.rect(s, _shade(pal.accent, 0.4), (cx - 7, cy + rad, 14, 4))
    pygame.draw.circle(s, (188, 74, 58), (cx, cy), rad, 4)
    for ang in range(0, 360, 60):
        a = math.radians(ang)
        pygame.draw.line(s, (188, 74, 58), (cx, cy),
                         (cx + rad * math.cos(a), cy + rad * math.sin(a)), 2)
    pygame.draw.circle(s, (232, 224, 214), (cx, cy), 3)


def _draw_gantry(s, r, pal, v):
    """Overhead gantry: a beam on posts, with cross-bracing."""
    col = _shade(pal.accent, 0.5)
    if v < 0.5:
        y = r.top + 12
        pygame.draw.line(s, _shade(pal.floor, 0.7), (r.left, y + 4), (r.right, y + 4), 4)
        pygame.draw.rect(s, col, (r.left, y - 3, r.width, 6))
        pygame.draw.line(s, _shade(col, 1.35), (r.left, y - 2), (r.right, y - 2))
        for x in range(r.left + 5, r.right, 16):
            pygame.draw.rect(s, _shade(col, 0.8), (x, y + 3, 4, 12))
            pygame.draw.line(s, _shade(col, 0.65), (x, y + 14), (x + 12, y + 3))
    else:
        x = r.left + 12
        pygame.draw.line(s, _shade(pal.floor, 0.7), (x + 4, r.top), (x + 4, r.bottom), 4)
        pygame.draw.rect(s, col, (x - 3, r.top, 6, r.height))
        pygame.draw.line(s, _shade(col, 1.35), (x - 2, r.top), (x - 2, r.bottom))
        for y in range(r.top + 5, r.bottom, 16):
            pygame.draw.rect(s, _shade(col, 0.8), (x + 3, y, 12, 4))
            pygame.draw.line(s, _shade(col, 0.65), (x + 14, y), (x + 3, y + 12))


# -- stage 9: reactor -------------------------------------------------
def _draw_tank(s, r, pal, v):
    """Coolant tank: banded cylinder with a level gauge and a valve."""
    body = _inset(r, 0.54, 0.78)
    _shadow(s, body, pal, radius=10)
    pygame.draw.rect(s, (120, 132, 140), body, border_radius=11)
    pygame.draw.rect(s, (66, 76, 84), body, 2, border_radius=11)
    pygame.draw.line(s, (168, 180, 188), (body.left + 4, body.top + 5),
                     (body.left + 4, body.bottom - 5), 2)          # highlight
    for i in range(2):
        y = body.top + 9 + i * (body.height // 2 - 2)
        pygame.draw.rect(s, (86, 96, 104), (body.left + 1, y, body.width - 2, 3))
    gauge = pygame.Rect(body.centerx - 2, body.top + 6, 4, body.height - 14)
    pygame.draw.rect(s, (30, 38, 40), gauge)
    pygame.draw.rect(s, _shade(pal.accent, 1.0),
                     (gauge.left, gauge.centery, gauge.width, gauge.height // 2))
    pygame.draw.circle(s, (176, 96, 72), (body.centerx, body.top + 2), 3)


def _draw_shielding(s, r, pal, v):
    """Shielding blocks: bevelled slabs with a hazard stripe."""
    horiz = v < 0.5
    body = _inset(r, 0.86, 0.46) if horiz else _inset(r, 0.46, 0.86)
    _shadow(s, body, pal, radius=1)
    pygame.draw.rect(s, (104, 112, 106), body)
    pygame.draw.rect(s, (142, 150, 142), body, 1)
    pygame.draw.rect(s, (62, 70, 66), body, 1)
    n = 3
    if horiz:
        for i in range(1, n):
            x = body.left + i * body.width // n
            pygame.draw.line(s, (62, 70, 66), (x, body.top), (x, body.bottom), 2)
        pygame.draw.rect(s, (206, 186, 72), (body.left, body.top + 1, body.width, 2))
    else:
        for i in range(1, n):
            y = body.top + i * body.height // n
            pygame.draw.line(s, (62, 70, 66), (body.left, y), (body.right, y), 2)
        pygame.draw.rect(s, (206, 186, 72), (body.left + 1, body.top, 2, body.height))


def _draw_radsign(s, r, pal, v):
    """Radiation trefoil on a yellow plate."""
    cx, cy = r.centerx, r.centery
    rad = max(9, int(r.width * 0.24))
    pygame.draw.circle(s, _shade(pal.floor, 0.68), (cx + 2, cy + 3), rad)
    pygame.draw.circle(s, (232, 206, 66), (cx, cy), rad)
    pygame.draw.circle(s, (40, 38, 28), (cx, cy), rad, 2)
    for ang in (270, 30, 150):                      # three blades, 120 apart
        pts = [(cx, cy)]
        for step in range(-28, 29, 7):
            a = math.radians(ang + step)
            pts.append((cx + (rad - 2) * math.cos(a), cy + (rad - 2) * math.sin(a)))
        pygame.draw.polygon(s, (40, 38, 28), pts)
    pygame.draw.circle(s, (232, 206, 66), (cx, cy), max(3, rad // 4))
    pygame.draw.circle(s, (40, 38, 28), (cx, cy), max(3, rad // 4), 1)


# -- stage 10: roof ---------------------------------------------------
def _draw_sky(s, r, pal, v):
    """Open air: a gap in the roof deck, parapet on two sides, stars."""
    gap = _inset(r, 0.86)
    pygame.draw.rect(s, (22, 27, 42), gap)
    pygame.draw.rect(s, (16, 20, 32), gap.inflate(-8, -8))          # depth
    rng = random.Random(int(v * 10_000))
    for _ in range(5):
        x = gap.left + rng.randint(3, max(4, gap.width - 4))
        y = gap.top + rng.randint(3, max(4, gap.height - 4))
        b = rng.choice((1, 1, 2))
        pygame.draw.rect(s, (196, 208, 232), (x, y, b, b))
    pygame.draw.rect(s, _shade(pal.accent, 0.62), gap, 2)           # parapet
    pygame.draw.line(s, _shade(pal.accent, 0.95), (gap.left, gap.top),
                     (gap.right - 1, gap.top), 2)
    pygame.draw.line(s, _shade(pal.accent, 0.95), (gap.left, gap.top),
                     (gap.left, gap.bottom - 1), 2)


def _draw_hvac(s, r, pal, v):
    """Air-handling unit: boxy housing, a big fan, a louvred side."""
    body = _inset(r, 0.74, 0.62)
    _shadow(s, body, pal)
    _body(s, body, (112, 120, 134), radius=2)
    fan = (body.centerx + 4, body.centery)
    rad = max(7, body.height // 3)
    pygame.draw.circle(s, (66, 74, 88), fan, rad)
    for ang in range(0, 360, 60):                   # fan blades
        a = math.radians(ang + v * 50)
        pygame.draw.line(s, (156, 166, 182), fan,
                         (fan[0] + rad * math.cos(a), fan[1] + rad * math.sin(a)), 2)
    pygame.draw.circle(s, (200, 208, 220), fan, 2)
    louvre = pygame.Rect(body.left + 2, body.top + 3, 9, body.height - 6)
    pygame.draw.rect(s, (86, 94, 108), louvre)
    for i in range(4):
        y = louvre.top + 2 + i * (louvre.height // 4)
        pygame.draw.line(s, (54, 60, 72), (louvre.left + 1, y), (louvre.right - 1, y))


def _draw_vent(s, r, pal, v):
    """Floor vent: framed grille with angled slats."""
    body = _inset(r, 0.56, 0.56)
    _shadow(s, body, pal, dy=2, radius=1)
    pygame.draw.rect(s, (104, 112, 126), body)
    pygame.draw.rect(s, (62, 68, 80), body, 2)
    inner = body.inflate(-6, -6)
    pygame.draw.rect(s, (46, 52, 62), inner)
    for i in range(4):
        y = inner.top + 1 + i * (inner.height // 4)
        pygame.draw.rect(s, (130, 138, 150), (inner.left, y, inner.width, 2))


def _draw_aerial(s, r, pal, v):
    """Mast with crossbars, guy wires and a small dish."""
    cx = r.centerx + int((v - 0.5) * r.width * 0.22)
    base, top = r.bottom - 9, r.top + 5
    pygame.draw.ellipse(s, _shade(pal.floor, 0.68), (cx - 7, base - 2, 16, 7))
    pygame.draw.rect(s, (96, 104, 116), (cx - 6, base - 2, 12, 4), border_radius=1)
    for dx in (-9, 9):                              # guy wires
        pygame.draw.line(s, (120, 128, 140), (cx, top + 6), (cx + dx, base - 1))
    pygame.draw.line(s, (190, 198, 210), (cx, top), (cx, base), 3)
    for i, w in enumerate((11, 8, 5)):
        y = top + 4 + i * 6
        pygame.draw.line(s, (170, 178, 192), (cx - w // 2, y), (cx + w // 2, y), 2)
    pygame.draw.circle(s, (206, 212, 222), (cx + 6, top + 9), 4)    # dish
    pygame.draw.circle(s, (140, 148, 160), (cx + 6, top + 9), 4, 1)


def _draw_duct(s, r, pal, v):
    """Ribbed ducting: one continuous run, not a row of blocks."""
    col = (124, 132, 146)
    horiz = v < 0.5
    body = (pygame.Rect(r.left, r.centery - 9, r.width, 18) if horiz
            else pygame.Rect(r.centerx - 9, r.top, 18, r.height))
    pygame.draw.rect(s, _shade(pal.floor, 0.68), body.move(0, 3) if horiz else body.move(3, 0))
    pygame.draw.rect(s, col, body)
    if horiz:
        pygame.draw.line(s, _shade(col, 1.35), (body.left, body.top + 4),
                         (body.right, body.top + 4), 2)
        for x in range(body.left + 4, body.right, 9):
            pygame.draw.line(s, _shade(col, 0.68), (x, body.top), (x, body.bottom), 2)
        pygame.draw.rect(s, _shade(col, 0.55), body, 1)
    else:
        pygame.draw.line(s, _shade(col, 1.35), (body.left + 4, body.top),
                         (body.left + 4, body.bottom), 2)
        for y in range(body.top + 4, body.bottom, 9):
            pygame.draw.line(s, _shade(col, 0.68), (body.left, y), (body.right, y), 2)
        pygame.draw.rect(s, _shade(col, 0.55), body, 1)


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
