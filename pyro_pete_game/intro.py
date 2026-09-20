"""Opening cinematic: "First Alarm".

Native-Pygame version of the "First Alarm" title sequence (originally
prototyped as an HTML/canvas artifact -- see assets/"opening scene").
Same beats: camera starts low, pointed up at a tall building with smoke
rolling off the roof; it settles at street level; Pete and the AI walk in
from either side, meet in the middle, turn, and walk into the building,
shrinking a little to read as moving away from camera; the screen ends on
a slow-blinking "PRESS ENTER TO START".

Runs as its own self-contained scene object: main.py just calls
update(dt, events) then draw(surface) every frame and checks .finished.

Deliberately drawn, not loaded from art -- same low-primitive-count,
prerender-once-and-blit approach as the HTML prototype, so it costs
nothing to keep in the game rather than shipping a video file.
"""

import math
import os
import random

import pygame

from fonts import ui_font
from settings import SCREEN_WIDTH, SCREEN_HEIGHT

# ---------------------------------------------------------------- timeline
# Seconds. Mirrors the HTML prototype's T1..T6 beats.
T1 = 2.2   # rooftop hold, smoke building
T2 = 7.0   # camera descent to street level ends
T3 = 7.4   # characters start walking in from the sides
T4 = 9.6   # they've met in the middle, start turning to face the building
T5 = 10.6  # they've reached the doorway (shrunk, facing away)
T6 = 11.2  # prompt fully faded in; held here until Enter

PETE_ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "pete")
ROBOT_ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "robot")
SPRITE_HEIGHT = 110

# --- palette (daytime) ---
SKY_TOP = (120, 172, 214)
SKY_BOTTOM = (198, 213, 210)
HAZE_COLOR = (255, 150, 90)
BRICK = (122, 67, 53)
BRICK_DARK = (98, 52, 41)
MORTAR = (168, 128, 108)
WINDOW_DARK = (46, 40, 46)
WINDOW_FIRE = (255, 140, 55)
WINDOW_GLOWING = (224, 78, 40)     # lit red/orange but no flames through it yet
FLAME_OUTER = (255, 140, 40)
FLAME_INNER = (255, 224, 110)
CORNICE = (168, 132, 104)
ROOF = (70, 58, 54)
SIDEWALK = (161, 154, 141)
SIDEWALK_LINE = (120, 108, 90)
STEPS = (143, 124, 104)
ENTRANCE = (56, 40, 34)
LAMP_POST = (40, 34, 30)
LAMP_GLASS = (201, 195, 184)
EMBER = (255, 106, 44)
EMBER_HOT = (255, 184, 77)
SMOKE_COLOR = (155, 149, 143)
INK = (21, 15, 12)
ROAD_COLOR = (58, 58, 62)
ROAD_LINE = (222, 200, 90)
CROWD_SKIN = (196, 156, 122)
CROWD_CLOTHES = ((90, 96, 120), (140, 78, 70), (86, 110, 92), (150, 130, 70), (100, 90, 110))
CAR_COLORS = ((150, 60, 56), (60, 84, 130), (150, 148, 140))

# --- the sun: drawn separately from the sky gradient, always fixed in
# screen space (never moves with the camera), on the left, and styled like
# a child's crayon drawing -- a bold circle with straight rays that pulse
# in and out. ---
SUN_FILL = (255, 210, 60)
SUN_OUTLINE = (219, 146, 24)
SUN_RAY_COLOR = (255, 176, 46)


def _load_sprite(path, target_height):
    image = pygame.image.load(path).convert_alpha()
    if image.get_height() != target_height:
        scale = target_height / image.get_height()
        new_size = (max(1, round(image.get_width() * scale)), target_height)
        image = pygame.transform.smoothscale(image, new_size)
    return image


def _load_walker(asset_dir):
    """{'idle': {dir: surf}, 'walk': {dir: [surf x4]}} -- graceful None if
    the asset folder isn't there (so a checkout missing art doesn't crash,
    it just skips the intro's characters)."""
    try:
        idle = {}
        walk = {}
        for d in ("up", "down", "left", "right"):
            idle[d] = _load_sprite(os.path.join(asset_dir, f"idle_{d}.png"), SPRITE_HEIGHT)
            walk[d] = [_load_sprite(os.path.join(asset_dir, f"walk_{d}_{i}.png"), SPRITE_HEIGHT)
                       for i in range(1, 5)]
        return {"idle": idle, "walk": walk}
    except (pygame.error, FileNotFoundError):
        return None


def ease_in_out_cubic(t):
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 4 * t * t * t
    f = -2 * t + 2
    return 1 - (f * f * f) / 2


def lerp(a, b, t):
    return a + (b - a) * t


def clamp01(t):
    return max(0.0, min(1.0, t))


def _draw_person(surf, x, ground_y, clothes, rng):
    """One tiny onlooker: circle head + a simple trapezoid body, facing the
    building. Cheap enough to draw a whole crowd of them."""
    h = rng.uniform(34, 46)
    head_r = h * 0.22
    body_top = ground_y - h
    body_w = h * 0.42
    pygame.draw.ellipse(surf, (0, 0, 0, 60), (x - body_w / 2, ground_y - 4, body_w, 8))
    pygame.draw.polygon(surf, clothes, [
        (x - body_w / 2, ground_y), (x + body_w / 2, ground_y),
        (x + body_w / 3, body_top + head_r * 1.6), (x - body_w / 3, body_top + head_r * 1.6),
    ])
    pygame.draw.circle(surf, CROWD_SKIN, (round(x), round(body_top + head_r)), round(head_r))


def _draw_car(surf, x, ground_y, color):
    """A boxy little parked car, side-on -- simple body block, cabin bump,
    two wheels, one window line. Reads fine at the size the intro shows it."""
    body_w, body_h = 92, 30
    bx = x - body_w / 2
    by = ground_y - body_h
    pygame.draw.rect(surf, (0, 0, 0, 70), (bx + 4, ground_y - 6, body_w - 8, 8), border_radius=4)
    pygame.draw.rect(surf, color, (bx, by, body_w, body_h), border_radius=8)
    pygame.draw.rect(surf, color, (bx + body_w * 0.22, by - 16, body_w * 0.56, 20),
                      border_radius=6)
    pygame.draw.rect(surf, (200, 220, 230), (bx + body_w * 0.28, by - 12, body_w * 0.44, 12),
                      border_radius=3)
    for wx in (bx + body_w * 0.22, bx + body_w * 0.78):
        pygame.draw.circle(surf, (24, 22, 22), (round(wx), round(ground_y)), 10)
        pygame.draw.circle(surf, (90, 88, 88), (round(wx), round(ground_y)), 4)


def _draw_flame(surf, cx, base_y, win_w, win_h, rng):
    """Baked-in (static) flame so an on-fire window reads as fire even
    before intro.py's per-frame flicker overlay ever runs -- also what the
    menu background's building crop shows, since that's a one-time bake
    with no per-frame animation of its own."""
    for dx, scale in ((-win_w * 0.17, 0.75), (0, 1.0), (win_w * 0.17, 0.75)):
        fx = cx + dx
        fh = win_h * (0.5 + 0.12 * rng.random()) * scale
        fw = win_w * 0.22 * scale
        pygame.draw.polygon(surf, FLAME_OUTER, [
            (fx, base_y), (fx - fw, base_y - fh * 0.5), (fx, base_y - fh), (fx + fw, base_y - fh * 0.5)])
    pygame.draw.polygon(surf, FLAME_INNER, [
        (cx, base_y), (cx - win_w * 0.09, base_y - win_h * 0.34),
        (cx, base_y - win_h * 0.56), (cx + win_w * 0.09, base_y - win_h * 0.34)])


def build_building_layer(width=900, ground=1120, center_x=450, seed=1337,
                          flame_chance=0.80, glowing_chance=0.15):
    """Prerenders the whole street-facing scene onto one tall Surface: the
    burning building (brick coursing, most windows either alight with
    flames or glowing red/orange, roof details, entrance), then a
    sidewalk with lamp posts and a small crowd of onlookers, then a road
    with a couple of parked cars. Drawn once and blitted every frame
    through the camera transform, same as the rest of the intro.

    Each window independently rolls one of three states: flame_chance
    (default 80%) it's fully alight -- a flame shape drawn right on the
    glass, no soft halo behind it; glowing_chance (default 15%) it's lit
    red/orange but no flame has broken through yet; the remaining share
    is a plain, unlit window. Applies across the whole facade, not just
    the top floors, so "the building is on fire" reads from every angle.

    Returns (surface, fire_rects) -- fire_rects is the list of *flaming*
    window rects (in this surface's own coordinates, glowing-only windows
    excluded) so the caller can lay an animated flicker on top each frame
    without having to redraw (or even re-scan) the static art.
    """
    w, h = width, ground + 420
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = center_x
    rng = random.Random(seed)

    bw = 360
    bx0, bx1 = cx - bw // 2, cx + bw // 2
    by0, by1 = 40, ground

    # brick coursing
    pygame.draw.rect(surf, BRICK, (bx0, by0, bw, by1 - by0))
    course_h = 14
    y = by0
    row = 0
    while y < by1:
        shade = BRICK_DARK if row % 2 == 0 else BRICK
        pygame.draw.rect(surf, shade, (bx0, y, bw, course_h - 2))
        row += 1
        y += course_h
    for gx in range(bx0, bx1, 3):
        if rng.random() < 0.5:
            pygame.draw.line(surf, MORTAR, (gx, by0), (gx, by1), 1)

    # windows -- 5 columns x N rows, spanning the whole facade. Each one
    # independently rolls flaming / glowing / plain (see docstring).
    cols = 5
    rows = max(3, (by1 - by0 - 60) // 90)
    win_w, win_h = 34, 50
    margin_x = (bw - cols * (win_w + 24) + 24) / 2
    fire_rects = []
    for r in range(rows):
        wy = by0 + 40 + r * 90
        for c in range(cols):
            wx = bx0 + margin_x + c * (win_w + 24)
            roll = rng.random()
            flaming = roll < flame_chance
            glowing = (not flaming) and roll < flame_chance + glowing_chance
            col = WINDOW_FIRE if flaming else (WINDOW_GLOWING if glowing else WINDOW_DARK)
            pygame.draw.rect(surf, (60, 44, 40), (wx - 3, wy - 3, win_w + 6, win_h + 6),
                              border_radius=2)
            pygame.draw.rect(surf, col, (wx, wy, win_w, win_h))
            if flaming:
                _draw_flame(surf, wx + win_w / 2, wy + win_h, win_w, win_h, rng)
                fire_rects.append(pygame.Rect(wx, wy, win_w, win_h))
            pygame.draw.line(surf, (30, 24, 24), (wx + win_w / 2, wy), (wx + win_w / 2, wy + win_h))

    # cornice ledges every ~3 rows
    for r in range(0, rows, 3):
        wy = by0 + 30 + r * 90
        pygame.draw.rect(surf, CORNICE, (bx0 - 8, wy, bw + 16, 8))

    # roof
    pygame.draw.rect(surf, ROOF, (bx0 - 14, by0 - 26, bw + 28, 30))
    pygame.draw.rect(surf, ROOF, (cx - 70, by0 - 70, 40, 46))   # water tower legs block
    pygame.draw.ellipse(surf, (86, 72, 66), (cx - 78, by0 - 96, 56, 30))  # tank
    pygame.draw.rect(surf, ROOF, (cx + 40, by0 - 60, 14, 36))  # chimney

    # entrance + steps
    ent_w = 70
    pygame.draw.rect(surf, ENTRANCE, (cx - ent_w / 2, by1 - 90, ent_w, 90), border_radius=6)
    pygame.draw.rect(surf, (30, 22, 20), (cx - ent_w / 2 + 6, by1 - 82, ent_w - 12, 60),
                      border_radius=4)
    for i, sw in enumerate((ent_w + 40, ent_w + 24, ent_w + 8)):
        pygame.draw.rect(surf, STEPS, (cx - sw / 2, by1 - 4 + i * 7, sw, 7))

    # sidewalk band + lamp posts
    sidewalk_top, sidewalk_bot = by1 + 18, by1 + 78
    pygame.draw.rect(surf, SIDEWALK, (0, sidewalk_top, w, sidewalk_bot - sidewalk_top))
    for lx in range(20, w - 20, 90):
        pygame.draw.line(surf, SIDEWALK_LINE, (lx, sidewalk_top), (lx, sidewalk_bot), 1)
    lamp_xs = (cx - 220, cx + 220, cx - w * 0.32, cx + w * 0.32)
    for lx in lamp_xs:
        pygame.draw.rect(surf, LAMP_POST, (lx - 3, by1 - 70, 6, 88))
        pygame.draw.circle(surf, LAMP_GLASS, (lx, by1 - 78), 8)

    # a crowd of onlookers gathered on the sidewalk either side of the
    # building -- clear of the entrance and the strip Pete/the AI walk
    # down the middle of.
    crowd_y = sidewalk_bot - 6
    for side in (-1, 1):
        for _ in range(14):
            spread = rng.uniform(0, w * 0.30 - 40)
            px = cx + side * (bw / 2 + 60 + spread)
            if 0 < px < w:
                _draw_person(surf, px, crowd_y, rng.choice(CROWD_CLOTHES), rng)

    # the street: a road band beyond the sidewalk with a couple of parked
    # cars, so "ground level" reads as a real city block and not just a
    # strip of pavement. Runs all the way down to the bottom of the canvas
    # (not just a thin strip) so that once the camera settles at street
    # level there is real road/pavement in view all the way to the bottom
    # of the game screen, instead of empty sky showing through underneath.
    road_top, road_bot = sidewalk_bot, h - 2
    pygame.draw.rect(surf, ROAD_COLOR, (0, road_top, w, road_bot - road_top))
    dash_y = road_top + 40
    for dx in range(10, w, 46):
        pygame.draw.rect(surf, ROAD_LINE, (dx, dash_y - 2, 26, 4))
    car_y = road_top + 30
    for i, side in enumerate((-1, 1)):
        car_x = cx + side * (bw / 2 + 120)
        _draw_car(surf, car_x, car_y, CAR_COLORS[i % len(CAR_COLORS)])

    return surf, fire_rects


class _Particles:
    """Simple embers/smoke -- spawn/step/draw, world-space positions."""

    def __init__(self, color, spawn_rate, max_particles, vy_range, vx_range,
                 radius_range, life_range, gravity=0.0):
        self.color = color
        self.spawn_rate = spawn_rate
        self.max_particles = max_particles
        self.vy_range = vy_range
        self.vx_range = vx_range
        self.radius_range = radius_range
        self.life_range = life_range
        self.gravity = gravity
        self.items = []  # each: [x, y, vx, vy, r, life, maxlife]

    def spawn_from(self, x, y, spread, dt, rate_mult=1.0):
        expected = self.spawn_rate * rate_mult * dt
        if len(self.items) >= self.max_particles:
            return
        if random.random() < expected:
            vx = random.uniform(*self.vx_range)
            vy = random.uniform(*self.vy_range)
            r = random.uniform(*self.radius_range)
            life = random.uniform(*self.life_range)
            px = x + random.uniform(-spread, spread)
            self.items.append([px, y, vx, vy, r, life, life])

    def step(self, dt):
        alive = []
        for p in self.items:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += self.gravity * dt
            p[5] -= dt
            if p[5] > 0:
                alive.append(p)
        self.items = alive

    def draw(self, surface, cam_x, cam_y, zoom):
        for x, y, vx, vy, r, life, maxlife in self.items:
            alpha = clamp01(life / maxlife)
            sx = (x - cam_x) * zoom + surface.get_width() / 2
            sy = (y - cam_y) * zoom + surface.get_height() / 2
            rad = max(1, int(r * zoom))
            s = pygame.Surface((rad * 2 + 2, rad * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, int(255 * alpha)), (rad + 1, rad + 1), rad)
            surface.blit(s, (sx - rad - 1, sy - rad - 1))


class IntroScene:
    """Self-contained title-sequence scene.

    update(dt, events) each frame; check .finished / .skip_requested; then
    draw(surface). Enter (or a click) during the animation jumps straight
    to the held final frame; Enter again from there sets .finished."""

    # World layout, in the building-layer's own coordinate space (a tall,
    # wide strip -- wide enough that the street scene either side of the
    # building is still there once the camera settles at street level).
    # y grows downward; BLD_GROUND is the sidewalk line.
    BLD_TOP = 0
    BLD_GROUND = 1120
    BLD_WIDTH = 900
    BLD_CENTER_X = 450
    GROUND_Y = 1185          # characters' feet baseline (inside the sidewalk)
    GROUND_VIEW_Y = 1069     # camera focus once settled -- keeps the
                              # building's base low in frame
    ENTER_Y = BLD_GROUND - 12

    def __init__(self):
        self.t = 0.0
        self.finished = False
        self.blink_t = 0.0
        self._phase = "playing"  # "playing" -> "held"
        self.pete_sprites = _load_walker(PETE_ASSET_DIR)
        self.robot_sprites = _load_walker(ROBOT_ASSET_DIR)
        self.building_layer, self.fire_rects = build_building_layer(
            width=self.BLD_WIDTH, ground=self.BLD_GROUND, center_x=self.BLD_CENTER_X)
        self.embers = _Particles(
            EMBER, spawn_rate=10, max_particles=140,
            vy_range=(-70, -25), vx_range=(-12, 12),
            radius_range=(1.4, 3.2), life_range=(0.9, 1.8), gravity=-20)
        self.smoke = _Particles(
            SMOKE_COLOR, spawn_rate=3.0, max_particles=60,
            vy_range=(-38, -18), vx_range=(-8, 8),
            radius_range=(10, 26), life_range=(2.2, 3.6),
            gravity=0.0)

    # ------------------------------------------------------------- camera
    def _camera_at(self, t):
        if t < T1:
            p = clamp01(t / T1)
            focus_y = lerp(self.BLD_TOP + 40, self.BLD_TOP + 90, p)
            zoom = lerp(1.9, 1.6, p)
        elif t < T2:
            p = ease_in_out_cubic(clamp01((t - T1) / (T2 - T1)))
            focus_y = lerp(self.BLD_TOP + 90, self.GROUND_VIEW_Y, p)
            zoom = lerp(1.6, 1.05, p)
        else:
            focus_y = self.GROUND_VIEW_Y
            zoom = 1.05
        return focus_y, zoom

    # --------------------------------------------------------- characters
    def _frame_index(self, t, fps=6):
        return int(t * fps) % 4

    def _characters_at(self, t):
        """Returns (pete_x, pete_y, pete_scale, pete_frame_key,
                     bot_x, bot_y, bot_scale, bot_frame_key)."""
        cx = self.BLD_CENTER_X
        if t < T3:
            pete = (cx - 200, self.GROUND_Y, 1.0, ("idle", "right"))
            bot = (cx + 200, self.GROUND_Y, 1.0, ("idle", "left"))
        elif t < T4:
            p = ease_in_out_cubic(clamp01((t - T3) / (T4 - T3)))
            pete_x = lerp(cx - 200, cx - 44, p)
            bot_x = lerp(cx + 200, cx + 44, p)
            fi = self._frame_index(t) + 1
            pete = (pete_x, self.GROUND_Y, 1.0, ("walk", "right", fi))
            bot = (bot_x, self.GROUND_Y, 1.0, ("walk", "left", fi))
        elif t < T5:
            p = ease_in_out_cubic(clamp01((t - T4) / (T5 - T4)))
            pete_x = lerp(cx - 44, cx - 32, p)
            bot_x = lerp(cx + 44, cx + 56, p)
            y = lerp(self.GROUND_Y, self.ENTER_Y, p)
            scale = lerp(1.0, 0.55, p)
            fi = self._frame_index(t) + 1
            pete = (pete_x, y, scale, ("walk", "up", fi))
            bot = (bot_x, y, scale, ("walk", "up", fi))
        else:
            pete = (cx - 32, self.ENTER_Y, 0.55, ("idle", "up"))
            bot = (cx + 56, self.ENTER_Y, 0.55, ("idle", "up"))
        return pete, bot

    def _sprite_for(self, sprites, key):
        if sprites is None:
            return None
        if key[0] == "idle":
            return sprites["idle"][key[1]]
        return sprites["walk"][key[1]][(key[2] - 1) % 4]

    # ------------------------------------------------------------- update
    def update(self, dt, events):
        for event in events:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._advance()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._advance()

        if self._phase == "playing":
            self.t += dt
            if self.t >= T6:
                self.t = T6
                self._phase = "held"
        self.blink_t += dt

        cam_y, zoom = self._camera_at(self.t)
        cam_x = self.BLD_CENTER_X
        progress = clamp01((cam_y - 100) / (self.GROUND_VIEW_Y - 100))
        # sky-lit windows glow a bit more as we approach street level
        spawn_x, spawn_y = self.BLD_CENTER_X, self.BLD_TOP + 46
        self.embers.spawn_from(spawn_x, spawn_y, 90, dt, rate_mult=1.0)
        self.smoke.spawn_from(spawn_x, spawn_y - 10, 60, dt, rate_mult=1.0)
        self.embers.step(dt)
        self.smoke.step(dt)
        self._cam_y, self._zoom, self._ground_progress = cam_y, zoom, progress

    def _advance(self):
        if self._phase == "playing":
            self.t = T6
            self._phase = "held"
        else:
            self.finished = True

    # --------------------------------------------------------------- draw
    def _draw_sky(self, surface, progress):
        w, h = surface.get_size()
        for y in range(0, h, 4):
            t = y / h
            col = tuple(round(lerp(a, b, t)) for a, b in zip(SKY_TOP, SKY_BOTTOM))
            pygame.draw.rect(surface, col, (0, y, w, 4))

    def _draw_sun(self, surface, t, progress):
        """Fixed to the top-left of the screen -- deliberately NOT tied to
        the camera's pan, so it never drifts down with the building.
        Instead it fades out over the camera's descent and is gone well
        before the shot settles at street level: once the camera angle has
        leveled out to look straight down the street, the sun (up near
        the rooftop) would be out of frame. Styled like a child's drawing:
        a bold circle with rays that breathe in and out."""
        alpha = clamp01(1.0 - progress / 0.6)
        if alpha <= 0.01:
            return
        w, h = surface.get_size()
        pad = 120
        tmp = pygame.Surface((pad * 2, pad * 2), pygame.SRCALPHA)
        cx, cy = pad, pad
        base_r = 46
        n_rays = 12
        ray_len = 30 + 10 * math.sin(t * 1.6)
        for i in range(n_rays):
            ang = (2 * math.pi / n_rays) * i
            inner = base_r + 8
            outer = inner + ray_len
            x0, y0 = cx + math.cos(ang) * inner, cy + math.sin(ang) * inner
            x1, y1 = cx + math.cos(ang) * outer, cy + math.sin(ang) * outer
            pygame.draw.line(tmp, SUN_RAY_COLOR, (x0, y0), (x1, y1), 6)
            pygame.draw.circle(tmp, SUN_RAY_COLOR, (round(x1), round(y1)), 3)
        pygame.draw.circle(tmp, SUN_FILL, (round(cx), round(cy)), base_r)
        pygame.draw.circle(tmp, SUN_OUTLINE, (round(cx), round(cy)), base_r, 5)
        tmp.set_alpha(int(255 * alpha))
        surface.blit(tmp, (w * 0.20 - pad, h * 0.20 - pad))

    def _draw_fire_glow(self, surface, cam_x, cam_y, zoom):
        """Animated flicker on top of the prerendered flame windows -- just
        the flame shapes re-drawn slightly taller/shorter each frame, no
        halo behind them -- so the fire reads as alive rather than static,
        without the soft "egg" glow shape the static art doesn't have
        either."""
        t = self.blink_t
        for i, rect in enumerate(self.fire_rects):
            wx = rect.centerx - cam_x
            wy = rect.centery - cam_y
            sx = wx * zoom + surface.get_width() / 2
            sy = wy * zoom + surface.get_height() / 2
            if not (-60 < sx < surface.get_width() + 60 and -60 < sy < surface.get_height() + 60):
                continue
            phase = i * 1.7

            fw, fh = rect.width * zoom, rect.height * zoom
            base_y = sy + fh * 0.42
            flick2 = 0.5 + 0.5 * abs(math.sin(t * 6.0 + phase * 1.3))
            flame_h = fh * (0.32 + 0.14 * flick2)
            for dx, scale, col in ((-fw * 0.16, 0.8, FLAME_OUTER), (0, 1.0, FLAME_OUTER),
                                   (fw * 0.16, 0.8, FLAME_OUTER)):
                fx = sx + dx
                pts = [(fx, base_y), (fx - fw * 0.09 * scale, base_y - flame_h * 0.55 * scale),
                       (fx, base_y - flame_h * scale), (fx + fw * 0.09 * scale, base_y - flame_h * 0.55 * scale)]
                pygame.draw.polygon(surface, col, pts)
            pygame.draw.polygon(surface, FLAME_INNER, [
                (sx, base_y), (sx - fw * 0.05, base_y - flame_h * 0.4),
                (sx, base_y - flame_h * 0.7), (sx + fw * 0.05, base_y - flame_h * 0.4)])

    def draw(self, surface):
        w, h = surface.get_size()
        self._draw_sky(surface, self._ground_progress)
        self._draw_sun(surface, self.blink_t, self._ground_progress)

        cam_x, cam_y, zoom = self.BLD_CENTER_X, self._cam_y, self._zoom
        layer = self.building_layer
        lw, lh = layer.get_size()
        scaled = pygame.transform.smoothscale(layer, (max(1, int(lw * zoom)), max(1, int(lh * zoom))))
        blit_x = w / 2 - cam_x * zoom
        blit_y = h / 2 - cam_y * zoom
        surface.blit(scaled, (blit_x, blit_y))

        self._draw_fire_glow(surface, cam_x, cam_y, zoom)
        self.smoke.draw(surface, cam_x, cam_y, zoom)
        self.embers.draw(surface, cam_x, cam_y, zoom)

        if self.t >= T3 - 0.05:
            pete, bot = self._characters_at(self.t)
            self._draw_character(surface, self.pete_sprites, pete, cam_x, cam_y, zoom)
            self._draw_character(surface, self.robot_sprites, bot, cam_x, cam_y, zoom)

        if self._phase == "held":
            self._draw_prompt(surface)

    def _draw_character(self, surface, sprites, state, cam_x, cam_y, zoom):
        frame = self._sprite_for(sprites, state[3])
        x, y, scale = state[0], state[1], state[2]
        sx = (x - cam_x) * zoom + surface.get_width() / 2
        sy = (y - cam_y) * zoom + surface.get_height() / 2
        if frame is None:
            # graceful fallback if art is missing: a simple colored marker
            r = int(18 * zoom * scale)
            pygame.draw.circle(surface, (200, 60, 60), (sx, sy - r), r)
            return
        fh = frame.get_height()
        target_h = fh * zoom * scale
        target_w = frame.get_width() * (target_h / fh)
        scaled = pygame.transform.smoothscale(frame, (max(1, int(target_w)), max(1, int(target_h))))
        rect = scaled.get_rect(midbottom=(sx, sy))
        surface.blit(scaled, rect)

    def _draw_prompt(self, surface):
        w, h = surface.get_size()
        visible = (self.blink_t % 1.2) < 0.8
        if not visible:
            return
        # created once, not every blink frame
        font = getattr(self, "_prompt_font", None)
        if font is None:
            font = self._prompt_font = ui_font("title")
        text = font.render("PRESS ENTER TO START", True, (245, 238, 224))
        shadow = font.render("PRESS ENTER TO START", True, (0, 0, 0))
        rect = text.get_rect(center=(w // 2, h // 2))
        surface.blit(shadow, rect.move(2, 2))
        surface.blit(text, rect)
