"""HUD / results text must stay inside the panel it is drawn on.

Both bugs these cover were only visible on screen: the spectate results
subtitle ("Stage 2/10 - Staff Canteen -- 3 occupants in the building") ran out
of a fixed 420px panel, and the top-right status panel let "AI HEALTH  Time
0:43" run past its right edge. Layout is measured with the real fonts.
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

import levels
import main as game
from results import _fit_panel_width
from settings import SCREEN_WIDTH

pygame.init()
pygame.display.set_mode((SCREEN_WIDTH, 640))
_BODY = pygame.font.SysFont(None, 24)


@pytest.mark.parametrize("index", range(levels.STAGE_COUNT))
def test_watch_results_panel_fits_every_stage_subtitle(index):
    sub = f"{levels.label(index)}  --  12 occupants in the building"
    hint = "Enter for the next stage     R to replay     Esc to quit"
    w = _fit_panel_width(_BODY.size(sub)[0] + 60, _BODY.size(hint)[0] + 40)
    assert w >= _BODY.size(sub)[0] + 60           # text plus its margins
    assert w >= _BODY.size(hint)[0] + 40
    assert w <= SCREEN_WIDTH - 20                 # and still on screen


def test_panel_width_never_drops_below_the_original_design():
    assert _fit_panel_width(10, 10) == 420


@pytest.mark.parametrize("spectate,expected_label", [(False, "HEALTH"),
                                                     (True, "AI HEALTH")])
def test_status_panel_contains_its_widest_row(spectate, expected_label):
    session = game.GameSession(levels.get(0), spectate=spectate,
                               agent_visual="robot")
    rects = []
    real = session._blit_panel
    session._blit_panel = lambda s, layer, r: (rects.append(r.copy()),
                                               real(s, layer, r))[1]
    screen = pygame.display.get_surface()
    session.draw(screen)

    status = rects[-1]                            # drawn last, top-right
    assert status.right <= SCREEN_WIDTH
    f = session.hud_font
    row = f.size(expected_label)[0] + 14 + f.size("Time  99:59")[0]
    assert status.width - 20 >= row               # 10px padding each side


def test_status_panel_width_does_not_twitch_as_the_clock_changes():
    """Proportional font: "1:11" is narrower than "0:00". The panel must be
    sized from the widest possible clock, not the current one."""
    session = game.GameSession(levels.get(0), spectate=True, agent_visual="robot")
    real = session._blit_panel
    widths = set()
    session._blit_panel = lambda s, layer, r: (widths.add(r.width) if r.x > 400
                                               else None, real(s, layer, r))[1]
    screen = pygame.display.get_surface()
    for elapsed in (0.0, 11.0, 71.0, 111.0, 600.0):
        session.agent_stats.elapsed = elapsed
        session.draw(screen)
    assert len(widths) == 1
