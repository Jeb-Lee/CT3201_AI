"""Drawing primitives for the HUD: panels, text, icons.

Pure functions that draw onto a surface they are handed -- no game state, no
animation state. hud.py decides what to draw and when; this file is how.
"""

import math

import pygame

# --- palette ---------------------------------------------------------------
TEXT = (236, 236, 240)
DIM = (150, 152, 162)
BLUE = (120, 150, 210)          # the AI (gold is "you": settings.RESULTS_ACCENT_COLOR)
GREEN = (130, 210, 140)         # good news: unlocked, sound on, reached the exit
AMBER = (240, 178, 64)          # a warning: sound off, fire spreading
PANEL_TOP, PANEL_BOT = (36, 39, 49), (15, 17, 23)
EDGE = (74, 78, 92)


def lerp_colour(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def ease_out(t):
    """Fast start, gentle stop -- for things sliding into place."""
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


# --- text / panels -----------------------------------------------------------
def shadowed_text(surface, font, text, colour, pos, anchor="topleft", alpha=255):
    """Text with a 1px dark drop so it stays readable over any map tile.
    Returns the rect it was drawn at."""
    img = font.render(text, True, colour)
    drop = font.render(text, True, (0, 0, 0))
    if alpha < 255:
        img.set_alpha(alpha)
        drop.set_alpha(alpha)
    rect = img.get_rect(**{anchor: pos})
    surface.blit(drop, rect.move(1, 1))
    surface.blit(img, rect)
    return rect


def gradient_panel(size, accent=None, radius=12, alpha=220):
    """A rounded vertical-gradient panel with a hairline edge and a top sheen,
    plus an optional accent border."""
    w, h = size
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        panel.fill((*lerp_colour(PANEL_TOP, PANEL_BOT, y / max(1, h - 1)), alpha), (0, y, w, 1))
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
    panel.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    pygame.draw.line(panel, (255, 255, 255, 34), (radius, 1), (w - radius, 1))
    pygame.draw.rect(panel, (*EDGE, 255), panel.get_rect(), 1, border_radius=radius)
    if accent:
        pygame.draw.rect(panel, (*accent, 235), panel.get_rect(), 2, border_radius=radius)
    return panel


def drop_shadow(size, radius=12):
    """A soft shadow for a panel of `size`: a few stacked translucent rounds,
    on a surface 12px wider and 14px taller (blit it at (x-6, y-3))."""
    w, h = size
    shadow = pygame.Surface((w + 12, h + 14), pygame.SRCALPHA)
    for i, a in enumerate((26, 18, 10)):
        r = pygame.Rect(6, 3, w, h).inflate(i * 3, i * 3).move(0, 3 + i)
        pygame.draw.rect(shadow, (0, 0, 0, a), r, border_radius=radius + i)
    return shadow


# --- icons ------------------------------------------------------------------
def flame(surface, cx, base_y, size, t,
          colours=((255, 120, 30), (255, 190, 60), (255, 236, 150))):
    """A three-layer flame; each layer flickers on its own phase (t = seconds)."""
    for i, colour in enumerate(colours):
        k = 1.0 - i * 0.30
        wob = math.sin(t * (7.0 + i * 2.3) + i) * size * 0.06
        h = size * k * (1.0 + 0.06 * math.sin(t * 9.0 + i * 1.7))
        w = size * 0.62 * k
        pts = [(cx - w / 2, base_y), (cx - w * 0.50, base_y - h * 0.38),
               (cx - w * 0.12 + wob, base_y - h * 0.68), (cx + wob * 1.6, base_y - h),
               (cx + w * 0.16 + wob, base_y - h * 0.62), (cx + w * 0.52, base_y - h * 0.36),
               (cx + w / 2, base_y)]
        pygame.draw.polygon(surface, colour, pts)
        pygame.draw.circle(surface, colour, (round(cx), round(base_y - w * 0.28)), round(w / 2))


def person(surface, cx, cy, s, colour, outline=None):
    """A person pip: round head over a rounded body, `s` px tall-ish."""
    head = max(1, round(s * 0.23))
    pygame.draw.circle(surface, colour, (cx, cy - round(s * 0.24)), head)
    body = pygame.Rect(0, 0, round(s * 0.58), round(s * 0.46))
    body.midtop = (cx, cy - round(s * 0.24) + head)
    pygame.draw.rect(surface, colour, body, border_radius=round(s * 0.2))
    if outline:
        pygame.draw.circle(surface, outline, (cx, cy - round(s * 0.24)), head, 1)
        pygame.draw.rect(surface, outline, body, 1, border_radius=round(s * 0.2))


def cross(surface, cx, cy, half, colour, width=2):
    pygame.draw.line(surface, colour, (cx - half, cy - half), (cx + half, cy + half), width)
    pygame.draw.line(surface, colour, (cx + half, cy - half), (cx - half, cy + half), width)


def key_icon(surface, cx, cy, s, colour):
    r = round(s * 0.24)
    pygame.draw.circle(surface, colour, (cx - round(s * 0.24), cy), r, 3)
    pygame.draw.line(surface, colour, (cx - round(s * 0.24) + r, cy),
                     (cx + round(s * 0.34), cy), 3)
    for dx in (0.16, 0.34):
        pygame.draw.line(surface, colour, (cx + round(s * dx), cy),
                         (cx + round(s * dx), cy + round(s * 0.2)), 3)


def padlock(surface, cx, cy, s, colour):
    body = pygame.Rect(0, 0, round(s * 0.56), round(s * 0.4))
    body.center = (cx, cy + round(s * 0.12))
    pygame.draw.rect(surface, colour, body, border_radius=3)
    pygame.draw.arc(surface, colour, pygame.Rect(body.x + 3, body.y - round(s * 0.34),
                                                 body.w - 6, round(s * 0.6)), 0, math.pi, 3)


def clock_icon(surface, cx, cy, s, colour):
    pygame.draw.circle(surface, colour, (cx, cy), round(s * 0.42), 2)
    pygame.draw.line(surface, colour, (cx, cy), (cx, cy - round(s * 0.26)), 2)
    pygame.draw.line(surface, colour, (cx, cy), (cx + round(s * 0.2), cy), 2)


def tick(surface, cx, cy, half, colour, width=3):
    pygame.draw.lines(surface, colour, False,
                      [(cx - half, cy), (cx - half // 3, cy + half * 2 // 3), (cx + half, cy - half // 2)],
                      width)


def drone_icon(surface, rect, colour=(150, 190, 235)):
    """The drone skin has no sprite sheet, so its portrait is drawn."""
    c = rect.center
    r = rect.w // 2 - 6
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        p = (c[0] + dx * r, c[1] + dy * r)
        pygame.draw.line(surface, (60, 68, 84), c, p, 3)
        pygame.draw.circle(surface, colour, p, 5, 2)
    pygame.draw.circle(surface, (44, 52, 66), c, r // 2 + 2)
    pygame.draw.circle(surface, (120, 235, 255), c, 4)


def speaker_icon(surface, cx, cy, size, colour, muted=False):
    """A loudspeaker: box and cone, with sound waves, or with a red slash when muted."""
    s = size
    pygame.draw.rect(surface, colour, pygame.Rect(round(cx - 0.42 * s), round(cy - 0.18 * s),
                                                  round(0.22 * s), round(0.36 * s)))
    pygame.draw.polygon(surface, colour, [(cx - 0.22 * s, cy - 0.18 * s), (cx + 0.06 * s, cy - 0.42 * s),
                                          (cx + 0.06 * s, cy + 0.42 * s), (cx - 0.22 * s, cy + 0.18 * s)])
    if muted:
        pygame.draw.line(surface, (230, 80, 70), (cx - 0.44 * s, cy + 0.44 * s),
                         (cx + 0.44 * s, cy - 0.44 * s), max(2, round(s * 0.1)))
    else:
        for r in (0.24, 0.42):
            box = pygame.Rect(0, 0, round(2 * r * s), round(2 * r * s))
            box.center = (round(cx + 0.06 * s), round(cy))
            pygame.draw.arc(surface, colour, box, -0.85, 0.85, max(2, round(s * 0.07)))


def pause_icon(surface, cx, cy, size, colour):
    """Two bars: the universal "paused"."""
    w, h = max(3, round(size * 0.24)), round(size * 0.78)
    for dx in (-0.22, 0.22):
        bar = pygame.Rect(0, 0, w, h)
        bar.center = (round(cx + dx * size), round(cy))
        pygame.draw.rect(surface, colour, bar, border_radius=2)


def key_chip(surface, x, y, label, font, colour=TEXT, height=28):
    """A keyboard key: a small rounded cap with a darker lower edge. `label`
    is the key ("P", "Esc", "WASD"); (x, y) is its top-left. Returns its rect."""
    text = font.render(label, True, colour)
    rect = pygame.Rect(x, y, max(height, text.get_width() + 18), height)
    pygame.draw.rect(surface, (18, 19, 25), rect.move(0, 2), border_radius=6)        # the key's depth
    pygame.draw.rect(surface, (44, 47, 58), rect, border_radius=6)
    pygame.draw.rect(surface, (104, 108, 124), rect, 1, border_radius=6)
    surface.blit(text, text.get_rect(center=rect.center))
    return rect
