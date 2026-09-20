"""Reusable keyboard+mouse choice menu, used for both the mode-select
screen (Play vs AI / Watch AI Play) and the skin-select screen
(Robot / Drone). One small generic class rather than two bespoke ones,
since they're the same interaction shape with different labels.
"""

import math
import os
import traceback

import pygame

from fonts import ui_font
from hud_icons import DIM, EDGE, PANEL_BOT, draw_panel, key_hint_row, lerp_colour
from portraits import draw_portrait
from settings import SCREEN_WIDTH, SCREEN_HEIGHT, RESULTS_ACCENT_COLOR
from intro import build_building_layer, _load_sprite, PETE_ASSET_DIR, ROBOT_ASSET_DIR

BG_COLOR = (16, 17, 21)
TITLE_COLOR = (232, 232, 232)
SUBTITLE_COLOR = (150, 150, 158)
OPTION_COLOR = (190, 190, 196)
OPTION_DESC_COLOR = (128, 128, 136)
HIGHLIGHT_BG = (40, 42, 50)


def build_menu_background(width=SCREEN_WIDTH, height=SCREEN_HEIGHT):
    """Pete on the left facing right, the AI robot on the right facing
    left, a closer shot of the burning building between them -- then the
    whole thing dimmed down so it reads as scenery, not competing with the
    title/options drawn on top of it. Built once and cached by whoever
    calls it (main.py), since it's the same picture behind both menu
    screens.

    Falls back to the flat BG_COLOR if the character art isn't there --
    same graceful-degradation the rest of the game uses for missing art.
    Any piece that fails to load/draw is skipped rather than crashing the
    menu, but the failure is printed (not swallowed silently) so a real
    problem shows up in the console instead of just "no background".
    """
    surf = pygame.Surface((width, height))
    surf.fill((28, 24, 22))
    problems = []  # (label, exception) pairs -- rendered onto the surface
                    # itself at the end, not just printed, so a failure is
                    # visible right in the game window even if nobody is
                    # watching a console.

    # closer shot of the building: a narrower layer than the intro's
    # establishing shot, cropped to a few floors of windows and scaled up
    # to fill the middle of the screen.
    try:
        layer, _ = build_building_layer(width=500, ground=1120, center_x=250)
        crop_rect = pygame.Rect(50, 40, 400, 420).clip(layer.get_rect())
        crop = layer.subsurface(crop_rect).copy()
        crop_w, crop_h = 420, int(height * 0.86)
        crop = pygame.transform.smoothscale(crop, (crop_w, crop_h))
        surf.blit(crop, (width // 2 - crop_w // 2, height - crop_h - 10))
    except Exception as exc:
        print("menu background: building crop failed, skipping it:")
        traceback.print_exc()
        problems.append(("building", exc))

    # Pete (left, facing right) and the robot (right, facing left)
    char_h = int(height * 0.66)
    try:
        pete = _load_sprite(os.path.join(PETE_ASSET_DIR, "idle_right.png"), char_h)
        rect = pete.get_rect(midbottom=(int(width * 0.14), height - 6))
        surf.blit(pete, rect)
    except Exception as exc:
        print("menu background: Pete sprite failed to load, skipping it:")
        traceback.print_exc()
        problems.append(("Pete sprite", exc))
    try:
        robot = _load_sprite(os.path.join(ROBOT_ASSET_DIR, "idle_left.png"), char_h)
        rect = robot.get_rect(midbottom=(int(width * 0.86), height - 6))
        surf.blit(robot, rect)
    except Exception as exc:
        print("menu background: robot sprite failed to load, skipping it:")
        traceback.print_exc()
        problems.append(("robot sprite", exc))

    # Mute the whole scene so it reads as backdrop, not foreground. Uses a
    # plain multiply rather than an alpha-blended overlay -- multiply just
    # scales the colors already on `surf` down by a fixed factor, so there
    # is no separate alpha-compositing step that could (on some pygame/SDL
    # builds) end up treating the overlay as fully opaque and blacking
    # everything out.
    mult = pygame.Surface((width, height))
    mult.fill((58, 52, 54))
    surf.blit(mult, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    # If anything above failed, say so right on the surface -- bright text,
    # drawn *after* the dimming step so it isn't muted away with the rest of
    # the scene. This is a temporary diagnostic: the background has failed
    # silently on at least one real machine, and printed tracebacks aren't
    # visible to someone just running the packaged game, so surface the
    # actual exception text directly in the window instead.
    if problems:
        diag_font = ui_font("small")
        y = 8
        surf.blit(diag_font.render(
            "menu background error(s) -- see below:", True, (255, 80, 80)), (8, y))
        y += 22
        for label, exc in problems:
            line = f"[{label}] {type(exc).__name__}: {exc}"
            surf.blit(diag_font.render(line, True, (255, 210, 90)), (8, y))
            y += 20

    return surf


PANEL_W = 560       # the panel behind the title and options
CARD_W = 480        # one option's card
CARD_H = 64
CARD_GAP = 84       # centre to centre
FIRST_CARD_CY = 280
PANEL_TOP = 55
ICON = 44           # the portrait on an option that has one
_CARDS = {}


def _card(size, accent, selected):
    """An option's card, built once: the selected one glows in the accent
    colour, the others are a faint outline."""
    key = (size, accent, selected)
    if key not in _CARDS:
        w, h = size
        card = pygame.Surface(size, pygame.SRCALPHA)
        if selected:
            top, bot = lerp_colour(PANEL_BOT, accent, 0.30), lerp_colour(PANEL_BOT, accent, 0.10)
            for y in range(h):
                card.fill((*lerp_colour(top, bot, y / max(1, h - 1)), 255), (0, y, w, 1))
        else:
            card.fill((255, 255, 255, 10))
        mask = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=10)
        card.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        pygame.draw.rect(card, accent if selected else EDGE, card.get_rect(),
                         2 if selected else 1, border_radius=10)
        _CARDS[key] = card
    return _CARDS[key]


def _arrows(font):
    """The up/down arrows for a key cap if the font has those glyphs, else words."""
    if all(m is not None for m in font.metrics("↑↓")):
        return "↑ ↓"
    return "Up/Down"


class ChoiceMenu:
    """options: list of (label, value, description_or_None[, icon]), where icon
    is "pete", "robot" or "drone" -- a portrait drawn beside the label.

    Navigate with Up/Down (wraps) or mouse hover; confirm with
    Enter/Space or a click. .result holds the chosen value once picked,
    else None. Esc leaves .cancelled True (the game itself quits on Esc).
    `accent` is the colour of the selection: gold for the player's own
    choices, blue (the AI's colour) for choices about the AI."""

    def __init__(self, title, options, subtitle=None, background=None, accent=RESULTS_ACCENT_COLOR):
        self.title = title
        self.subtitle = subtitle
        self.options = options
        self.background = background  # pre-rendered pygame.Surface, or None for flat BG_COLOR
        self.accent = accent
        self.index = 0
        self.t = 0.0
        self.result = None
        self.cancelled = False
        self._option_rects = []

        self._title_font = ui_font("title")
        self._subtitle_font = ui_font("body")
        self._option_font = ui_font("heading")
        self._desc_font = ui_font("small")
        self._hint_font = ui_font("small")
        self._chip_font = ui_font("small", bold=True)

    def hint_items(self):
        return [(_arrows(self._chip_font), "Choose"), ("Enter", "Select"), ("Esc", "Quit")]

    def has_icons(self):
        return any(len(o) > 3 and o[3] for o in self.options)

    def update(self, dt, events):
        self.t += dt
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    self.index = (self.index + 1) % len(self.options)
                elif event.key in (pygame.K_UP, pygame.K_w):
                    self.index = (self.index - 1) % len(self.options)
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    self.result = self.options[self.index][1]
                elif event.key == pygame.K_ESCAPE:
                    self.cancelled = True
            elif event.type == pygame.MOUSEMOTION:
                for i, rect in enumerate(self._option_rects):
                    if rect.collidepoint(event.pos):
                        self.index = i
                        break
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, rect in enumerate(self._option_rects):
                    if rect.collidepoint(event.pos):
                        self.index = i
                        self.result = self.options[i][1]
                        break

    def panel_rect(self, width=SCREEN_WIDTH):
        """The panel behind everything: from the title down past the hint row."""
        last_bottom = FIRST_CARD_CY + (len(self.options) - 1) * CARD_GAP + CARD_H // 2
        rect = pygame.Rect(0, PANEL_TOP, min(PANEL_W, width - 40), last_bottom + 92 - PANEL_TOP)
        rect.centerx = width // 2
        return rect

    def draw(self, surface):
        if self.background is not None:
            surface.blit(self.background, (0, 0))
        else:
            surface.fill(BG_COLOR)
        w = surface.get_width()

        panel = self.panel_rect(w)
        draw_panel(surface, panel, accent=self.accent, radius=16, alpha=205)

        title_surf = self._title_font.render(self.title, True, TITLE_COLOR)
        title_rect = title_surf.get_rect(center=(w // 2, 150))
        surface.blit(title_surf, title_rect)

        bottom = title_rect.bottom
        if self.subtitle:
            sub_surf = self._subtitle_font.render(self.subtitle, True, SUBTITLE_COLOR)
            sub_rect = sub_surf.get_rect(center=(w // 2, title_rect.bottom + 26))
            surface.blit(sub_surf, sub_rect)
            bottom = sub_rect.bottom
        pygame.draw.rect(surface, self.accent,                       # a short accent rule
                         pygame.Rect(w // 2 - 24, bottom + 12, 48, 3), border_radius=2)

        self._option_rects = []
        icons = self.has_icons()
        for i, option in enumerate(self.options):
            label, value, desc = option[:3]
            icon = option[3] if len(option) > 3 else None
            rect = pygame.Rect(0, 0, CARD_W, CARD_H)
            rect.center = (w // 2, FIRST_CARD_CY + i * CARD_GAP)
            self._option_rects.append(rect)

            selected = (i == self.index)
            surface.blit(_card(rect.size, self.accent, selected), rect.topleft)

            label_surf = self._option_font.render(label, True, self.accent if selected else OPTION_COLOR)
            desc_surf = (self._desc_font.render(desc, True, DIM if selected else OPTION_DESC_COLOR)
                         if desc else None)
            dy = 10 if desc else 0
            if icons:
                box = pygame.Rect(0, 0, ICON, ICON)
                box.midleft = (rect.left + 12, rect.centery)
                if icon:
                    draw_portrait(surface, box, icon, self.accent if selected else EDGE)
                x = box.right + 14
                surface.blit(label_surf, label_surf.get_rect(midleft=(x, rect.centery - dy)))
                if desc_surf:
                    surface.blit(desc_surf, desc_surf.get_rect(midleft=(x, rect.centery + 16)))
            else:
                surface.blit(label_surf, label_surf.get_rect(center=(rect.centerx, rect.centery - dy)))
                if desc_surf:
                    surface.blit(desc_surf, desc_surf.get_rect(center=(rect.centerx, rect.centery + 16)))
            if selected:                                             # a chevron that nudges
                nx = rect.right - 22 + round(2 * math.sin(self.t * 5))
                pygame.draw.polygon(surface, self.accent, [(nx - 5, rect.centery - 8),
                                                           (nx + 3, rect.centery), (nx - 5, rect.centery + 8)])

        key_hint_row(surface, self.hint_items(), self._chip_font, self._hint_font,
                     w // 2, panel.bottom - 34)
