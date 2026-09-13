"""Reusable keyboard+mouse choice menu, used for both the mode-select
screen (Play vs AI / Watch AI Play) and the skin-select screen
(Robot / Drone). One small generic class rather than two bespoke ones,
since they're the same interaction shape with different labels.
"""

import os
import traceback

import pygame

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
        diag_font = pygame.font.SysFont(None, 20)
        y = 8
        surf.blit(diag_font.render(
            "menu background error(s) -- see below:", True, (255, 80, 80)), (8, y))
        y += 22
        for label, exc in problems:
            line = f"[{label}] {type(exc).__name__}: {exc}"
            surf.blit(diag_font.render(line, True, (255, 210, 90)), (8, y))
            y += 20

    return surf


class ChoiceMenu:
    """options: list of (label, value, description_or_None).

    Navigate with Up/Down (wraps) or mouse hover; confirm with
    Enter/Space or a click. .result holds the chosen value once picked,
    else None. Esc leaves .cancelled True so main.py can back out a
    screen instead of quitting outright, when that's wired up."""

    def __init__(self, title, options, subtitle=None, background=None):
        self.title = title
        self.subtitle = subtitle
        self.options = options
        self.background = background  # pre-rendered pygame.Surface, or None for flat BG_COLOR
        self.index = 0
        self.result = None
        self.cancelled = False
        self._option_rects = []

        self._title_font = pygame.font.SysFont(None, 54)
        self._subtitle_font = pygame.font.SysFont(None, 24)
        self._option_font = pygame.font.SysFont(None, 36)
        self._desc_font = pygame.font.SysFont(None, 22)
        self._hint_font = pygame.font.SysFont(None, 22)

    def update(self, dt, events):
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

    def draw(self, surface):
        if self.background is not None:
            surface.blit(self.background, (0, 0))
        else:
            surface.fill(BG_COLOR)
        w = surface.get_width()

        # a soft dark panel behind the title/options column -- belt and
        # braces alongside the background's own dimming, so light parts of
        # the scenery (a flame, a lit window) never fight with the text.
        panel = pygame.Surface((min(560, w - 40), 430), pygame.SRCALPHA)
        pygame.draw.rect(panel, (8, 8, 10, 130), panel.get_rect(), border_radius=16)
        surface.blit(panel, panel.get_rect(center=(w // 2, 270)))

        title_surf = self._title_font.render(self.title, True, TITLE_COLOR)
        title_rect = title_surf.get_rect(center=(w // 2, 150))
        surface.blit(title_surf, title_rect)

        if self.subtitle:
            sub_surf = self._subtitle_font.render(self.subtitle, True, SUBTITLE_COLOR)
            surface.blit(sub_surf, sub_surf.get_rect(center=(w // 2, title_rect.bottom + 26)))

        self._option_rects = []
        top = 280
        gap = 84
        opt_w = 420
        for i, (label, value, desc) in enumerate(self.options):
            cy = top + i * gap
            rect = pygame.Rect(0, 0, opt_w, 60)
            rect.center = (w // 2, cy)
            self._option_rects.append(rect)

            selected = (i == self.index)
            if selected:
                pygame.draw.rect(surface, HIGHLIGHT_BG, rect, border_radius=8)
                pygame.draw.rect(surface, RESULTS_ACCENT_COLOR, rect, 2, border_radius=8)

            label_color = RESULTS_ACCENT_COLOR if selected else OPTION_COLOR
            label_surf = self._option_font.render(label, True, label_color)
            label_rect = label_surf.get_rect(center=(rect.centerx, rect.centery - (10 if desc else 0)))
            surface.blit(label_surf, label_rect)

            if desc:
                desc_surf = self._desc_font.render(desc, True, OPTION_DESC_COLOR)
                surface.blit(desc_surf, desc_surf.get_rect(center=(rect.centerx, rect.centery + 16)))

        hint = self._hint_font.render(
            "Arrow keys or mouse to choose, Enter to select", True, SUBTITLE_COLOR)
        surface.blit(hint, hint.get_rect(center=(w // 2, surface.get_height() - 40)))
