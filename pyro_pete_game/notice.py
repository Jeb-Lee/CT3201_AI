"""Feedback for global keys, drawn over every screen.

M (mute) is handled at the top of the game loop, so it works on the intro, the
menus, in play and in the pause screen -- and used to give no sign it had done
anything. Two things now answer it:

  * a small pill, "Sound off" / "Sound on", that fades after a moment
  * a speaker chip in the bottom-right corner that stays for as long as the
    sound is muted, so the state is visible without pressing anything

The corner is free on every screen: the widest mission strip (stage 9) ends at
x=811, and the chip starts at x=916. On a machine with no audio device there is
no switch to report, so the honest message is "No audio device".

Notices are timed by real time, not game time, so they keep working while the
game is paused.
"""

from dataclasses import dataclass

import pygame

from fonts import ui_font
from hud_icons import (
    DIM, TEXT, GREEN, AMBER, gradient_panel, drop_shadow, speaker_icon, shadowed_text,
)
from settings import SCREEN_WIDTH, SCREEN_HEIGHT

MARGIN = 10
CHIP = 34                   # the persistent speaker chip
LIFE = 1.8                  # seconds a message stays
PILL_H = 32
GAP = 16                    # chip top -> pill bottom


@dataclass
class _Notice:
    text: str
    colour: tuple
    age: float = 0.0

    @property
    def alpha(self):
        """In over 0.15s, out over the last 0.45s."""
        return max(0.0, min(1.0, self.age / 0.15, (LIFE - self.age) / 0.45))


def chip_rect():
    """The persistent speaker chip, bottom-right."""
    return pygame.Rect(SCREEN_WIDTH - MARGIN - CHIP, SCREEN_HEIGHT - MARGIN - CHIP, CHIP, CHIP)


def pill_rect(width):
    """Where a message of `width` sits: right-aligned, just above the chip."""
    return pygame.Rect(SCREEN_WIDTH - MARGIN - width, chip_rect().top - GAP - PILL_H, width, PILL_H)


class Notices:
    def __init__(self):
        self.font = ui_font("body", bold=True)
        self.items = []
        self._chip = None
        self._pill = {}

    def show(self, text, colour=TEXT):
        self.items = [n for n in self.items if n.text != text]      # a repeat replaces, not stacks
        self.items.append(_Notice(text, colour))

    def sound_changed(self, audio):
        """Say what pressing M just did."""
        if not audio.enabled:
            self.show("No audio device", DIM)
        elif audio.muted:
            self.show("Sound off", AMBER)
        else:
            self.show("Sound on", GREEN)

    def update(self, dt):
        for n in self.items:
            n.age += dt
        self.items = [n for n in self.items if n.age < LIFE]

    # ---- drawing ---------------------------------------------------------
    def _chip_surface(self):
        if self._chip is None:
            chip = pygame.Surface((CHIP, CHIP), pygame.SRCALPHA)
            chip.blit(gradient_panel((CHIP, CHIP), radius=9), (0, 0))
            speaker_icon(chip, CHIP // 2, CHIP // 2, 22, DIM, muted=True)
            self._chip = chip
        return self._chip

    def _pill_surface(self, text, colour, width):
        key = (text, colour)
        if key not in self._pill:
            pill = pygame.Surface((width, PILL_H), pygame.SRCALPHA)
            pill.blit(gradient_panel((width, PILL_H), radius=12), (0, 0))
            pygame.draw.rect(pill, (*colour, 255), pygame.Rect(0, 0, 6, PILL_H),
                             border_top_left_radius=12, border_bottom_left_radius=12)
            shadowed_text(pill, self.font, text, TEXT, (22, PILL_H // 2), "midleft")
            self._pill[key] = pill
        return self._pill[key]

    def draw(self, surface, audio):
        rect = chip_rect()
        if audio.muted:                                  # stays while muted
            surface.blit(drop_shadow(rect.size, radius=9), (rect.x - 6, rect.y - 3))
            surface.blit(self._chip_surface(), rect.topleft)
        for n in self.items:
            width = self.font.size(n.text)[0] + 44
            pill = self._pill_surface(n.text, n.colour, width)
            pill.set_alpha(round(255 * n.alpha))
            surface.blit(pill, pill_rect(width).topleft)
