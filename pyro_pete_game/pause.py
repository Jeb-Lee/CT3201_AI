"""The pause screen: a panel that lists the controls and stays off the character.

It used to be the word "PAUSED" and "Press P to resume", drawn at the exact
centre of the screen. The camera also puts the character at the exact centre, so
in normal play the word landed on his belt and legs, and the screen never said
what the other keys did.

Now: a panel in the HUD's style with the controls and the state of the sound. Its
position is chosen so that it does not cover the rescuer you are watching (or the
other one, when there is room): centred if that is clear, otherwise beside or
above/below.
"""

from dataclasses import dataclass

import pygame

from fonts import ui_font
from hud_icons import (
    TEXT, DIM, GREEN, AMBER, gradient_panel, drop_shadow, shadowed_text, pause_icon, key_chip,
)
from settings import SCREEN_WIDTH, SCREEN_HEIGHT, RESULTS_ACCENT_COLOR

# Between the fire clock (bottom edge y=100) and the mission strip (top edge y=586).
REGION = pygame.Rect(10, 110, SCREEN_WIDTH - 20, 466)
PAD = 22
ROW_H = 34
DIM_ALPHA = 140
BOX_MARGIN = 12               # air kept around a character


@dataclass
class Control:
    keys: str                 # what is printed on the key: "P", "Esc", "WASD"
    label: str
    state: tuple = None       # (text, colour) shown at the right, e.g. ("on", GREEN)


def entity_box(session, entity):
    """A rescuer's rectangle on screen: a bit bigger than the sprite, feet at
    (x, y)."""
    ox, oy = session.camera.offset
    return pygame.Rect(round(entity.x - ox) - 36, round(entity.y - oy) - 100, 72, 106)


def characters_on_screen(session):
    """Boxes of the rescuers the panel must not cover, most important first:
    the one the camera follows, then the other (if there is one)."""
    anchor = session._view_anchor
    boxes = [entity_box(session, anchor)]
    if not session.spectate:
        other = session.agent if anchor is session.player else session.player
        if other is session.agent or not session.player.is_dead:
            boxes.append(entity_box(session, other))
    return boxes


def candidate_rects(size):
    """Every spot the panel may take, nearest the middle first."""
    w, h = size
    xs = [(SCREEN_WIDTH - w) // 2, REGION.left + 30, REGION.right - 30 - w]
    ys = [REGION.top + (REGION.h - h) // 2, REGION.top + 8, REGION.bottom - 8 - h]
    cands = [pygame.Rect(x, y, w, h) for y in ys for x in xs]
    cx, cy = REGION.center
    return sorted(cands, key=lambda r: (r.centerx - cx) ** 2 + (r.centery - cy) ** 2)


def choose_rect(size, boxes):
    """The first candidate that clears every box; failing that, the first that
    clears the most important one; failing that, the middle."""
    cands = candidate_rects(size)
    for group in (boxes, boxes[:1]):
        for r in cands:
            if not any(r.colliderect(b.inflate(2 * BOX_MARGIN, 2 * BOX_MARGIN)) for b in group):
                return r
    return cands[0]


class PauseScreen:
    def __init__(self):
        self.f_title = ui_font("title")
        self.f_label = ui_font("body")
        self.f_chip = ui_font("body", bold=True)
        self.f_small = ui_font("small")
        self._panels = {}

    # ---- what it says -------------------------------------------------------
    def controls(self, session, audio):
        if not audio.enabled:
            sound = ("no audio device", DIM)
        elif audio.muted:
            sound = ("off", AMBER)
        else:
            sound = ("on", GREEN)
        rows = []
        if not session.spectate:                       # nothing to steer when watching
            rows.append(Control("WASD", "Move  (or the arrow keys)"))
        rows += [Control("P", "Resume"),
                 Control("R", "Restart the stage"),
                 Control("M", "Sound", sound),
                 Control("Esc", "Quit the game")]
        return rows

    def subtitle(self, session):
        text = session.stage_label.replace(" - ", "  ·  ")
        return text + ("  ·  watching the AI" if session.spectate else "")

    # ---- how big it is ---------------------------------------------------------
    def _chip_w(self, keys):
        return max(28, self.f_chip.size(keys)[0] + 18)

    def size(self, session, audio):
        rows = self.controls(session, audio)
        chip_w = max(self._chip_w(c.keys) for c in rows)
        widest = 0
        for c in rows:
            w = chip_w + 16 + self.f_label.size(c.label)[0]
            if c.state:
                w += 28 + self.f_chip.size(c.state[0])[0]
            widest = max(widest, w)
        title_w = 26 + 12 + self.f_title.size("PAUSED")[0]
        sub_w = self.f_small.size(self.subtitle(session))[0]
        width = max(340, 2 * PAD + max(widest, title_w, sub_w))
        header = self.f_title.get_height() + 4 + self.f_small.get_height() + 14
        height = PAD + header + 1 + 10 + len(rows) * ROW_H + PAD - 6
        return width, height

    def place(self, session, audio):
        """Where the panel goes right now."""
        return choose_rect(self.size(session, audio), characters_on_screen(session))

    # ---- drawing -----------------------------------------------------------------
    def _panel(self, size):
        if size not in self._panels:
            self._panels[size] = gradient_panel(size, RESULTS_ACCENT_COLOR)
        return self._panels[size]

    def draw(self, surface, session, audio):
        """Dim the frozen frame and draw the panel. Returns the panel's rect."""
        dim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 0, DIM_ALPHA))
        surface.blit(dim, (0, 0))

        rows = self.controls(session, audio)
        size = self.size(session, audio)
        rect = self.place(session, audio)
        surface.blit(drop_shadow(size), (rect.x - 6, rect.y - 3))
        panel = pygame.Surface(size, pygame.SRCALPHA)
        panel.blit(self._panel(size), (0, 0))

        y = PAD
        pause_icon(panel, PAD + 13, y + self.f_title.get_height() // 2, 26, RESULTS_ACCENT_COLOR)
        shadowed_text(panel, self.f_title, "PAUSED", TEXT, (PAD + 38, y))
        y += self.f_title.get_height() + 4
        shadowed_text(panel, self.f_small, self.subtitle(session), DIM, (PAD, y))
        y += self.f_small.get_height() + 14
        pygame.draw.line(panel, (255, 255, 255, 46), (PAD, y), (size[0] - PAD, y))
        y += 1 + 10

        chip_w = max(self._chip_w(c.keys) for c in rows)
        for c in rows:
            key_chip(panel, PAD, y + (ROW_H - 28) // 2, c.keys, self.f_chip)
            shadowed_text(panel, self.f_label, c.label, TEXT, (PAD + chip_w + 16, y + ROW_H // 2 - 2),
                          "midleft")
            if c.state:
                text, colour = c.state
                shadowed_text(panel, self.f_chip, text, colour, (size[0] - PAD, y + ROW_H // 2 - 2),
                              "midright")            # bold: it is the one thing here that changes
            y += ROW_H
        surface.blit(panel, rect.topleft)
        return rect
