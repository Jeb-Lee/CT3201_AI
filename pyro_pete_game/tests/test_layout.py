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


# --- results panel alignment -------------------------------------------------
import results
from stats import RunStats

_FONTS = tuple(pygame.font.SysFont(None, s) for s in (44, 30, 24))


def _stats(label="AI robot", **kw):
    s = RunStats(label)
    s.victims_saved = kw.get("saved", 3)
    s.elapsed = kw.get("secs", 43.0)
    s.distance = kw.get("tiles", 110.4) * 64
    s.damage_taken = kw.get("dmg", 33)
    s.replans, s.goal_changes = kw.get("replans", 114), kw.get("goals", 24)
    s.finished_reason = kw.get("reason", "exit")
    if kw.get("died"):
        s.deaths = 1
    return s


def test_summary_values_are_not_space_padded():
    """Space-padding never lined up in a proportional font, and it left
    "0" sitting further right than "58". Alignment is the renderer's job."""
    for label, value in _stats(dmg=0).summary_rows():
        assert value == value.strip(), (label, value)


def test_summary_health_lost_is_not_confused_with_the_damage_penalty():
    labels = [l for l, _ in _stats().summary_rows()]
    assert "Health lost" in labels and "Damage taken" not in labels
    assert "Damage taken" in [l for l, _ in _stats().score_breakdown()]


@pytest.mark.parametrize("kw", [dict(), dict(dmg=0), dict(died=True, reason="dead")])
def test_draw_column_uses_exactly_the_height_it_reports(kw):
    """The panel is sized from _column_height, so it must match what
    _draw_column really uses or rows overrun the panel again."""
    st = _stats(**kw)
    surf = pygame.Surface((600, 700), pygame.SRCALPHA)
    end = results._draw_column(surf, _FONTS[1], _FONTS[2], 0, 10, 300, st)
    assert end - 10 == results._column_height(_FONTS[2], st)


def test_values_end_on_the_shared_right_edge():
    """A number is right-aligned to the column edge: it touches it and never
    pokes past it. (Left-aligned values left the right edges ragged.)"""
    st = _stats()
    surf = pygame.Surface((400, 500))
    surf.fill((0, 0, 0))
    right = 380
    results._draw_column(surf, _FONTS[1], _FONTS[2], 20, 0, right - 20, st)
    # first score row: y = section heading + rule, then one row of text
    row_top = results._HEAD_H + _FONTS[2].get_height() + 2 + 8
    band = range(row_top, row_top + _FONTS[2].get_height())
    lit = [x for x in range(399, 20, -1)
           if any(surf.get_at((x, yy))[:3] != (0, 0, 0) for yy in band)]
    assert lit, "no text drawn on the first score row"
    assert right - 3 <= lit[0] <= right       # value ends on the edge, not past it


@pytest.mark.parametrize("draw", ["watch", "race"])
def test_results_panel_fits_on_screen_even_with_every_row(draw, monkeypatch):
    seen = []
    real = results._draw_panel
    monkeypatch.setattr(results, "_draw_panel",
                        lambda s, px, py, w, h: (seen.append((px, py, w, h)),
                                                 real(s, px, py, w, h))[1])
    screen = pygame.display.get_surface()
    worst = _stats(dmg=200, died=True, reason="dead")
    label = levels.label(levels.STAGE_COUNT - 1)
    if draw == "watch":
        results.draw_watch_results(screen, *_FONTS, worst, 12, stage_label=label,
                                   cleared=False, has_next_stage=True)
    else:
        results.draw_results(screen, *_FONTS, _stats("You (Pete)", dmg=200,
                             died=True, reason="dead"), worst, 12,
                             outcome="died", stage_label=label, has_next_stage=True)
    px, py, w, h = seen[0]
    assert px >= 0 and py >= 0
    assert px + w <= SCREEN_WIDTH and py + h <= results.SCREEN_HEIGHT
