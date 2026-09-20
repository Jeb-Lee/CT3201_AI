"""One name per rescuer, on every screen.

A rescuer used to be spelled three ways: "AI Robot" in the results heading,
"AI robot" in the verdict line and the toasts, and "AI ROBOT (LEARNED)" on the
HUD card. RunStats.display_name / .role are now the only thing shown; the running
label ("AI robot (learned)") is internal. These tests record every string the HUD
and both results panels draw and check the old wording is gone, and that no code
reaches for the label again.
"""
import os
import re
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

import levels
import main as game
import results
from entities.victim import STATE_DEAD
from fonts import ui_font
from settings import SCREEN_HEIGHT, SCREEN_WIDTH
from stats import RunStats

pygame.init()
SCREEN = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
_GAME_DIR = Path(__file__).resolve().parent.parent

# what must never be drawn: the old lowercase label, and "(learned)" on a name
_OLD = ("AI robot", "AI drone", "(learned)", "(LEARNED)", "LEARNED)")


class Rec:
    """A font that records every string rendered with it (and otherwise is the font)."""
    def __init__(self, font, sink):
        self._f, self._sink = font, sink

    def render(self, text, *a, **k):
        self._sink.append(text)
        return self._f.render(text, *a, **k)

    def __getattr__(self, name):
        return getattr(self._f, name)


def _stats(label, saved=0, reason="exit", **kw):
    st = RunStats(label, **kw)
    st.set_saved(saved)
    st.finish(reason)
    return st


def _session(visual="robot", learned=False):
    s = game.GameSession(levels.get(0), spectate=False, agent_visual=visual)
    if learned:                                     # the stats a learned run would have
        s.agent_stats = RunStats(f"AI {visual} (learned)", kind=visual, brain="learned")
    return s


def _record_hud(s):
    said = []
    for f in ("f_title", "f_head", "f_body", "f_small"):
        setattr(s.hud, f, Rec(getattr(s.hud, f), said))
    return said


# ------------------------------------------------------------------ the verdict
@pytest.mark.parametrize("label,name", [("AI robot", "AI Robot"), ("AI drone", "AI Drone"),
                                        ("AI robot (learned)", "AI Robot"),
                                        ("AI drone (learned)", "AI Drone")])
def test_the_verdict_names_the_opponent_like_its_heading(label, name):
    pete_out, pete_none = _stats("You (Pete)", 3), _stats("You (Pete)", 0, "dead")
    ai_out, ai_none = _stats(label, 3), _stats(label, 0, "dead")
    assert results._verdict(pete_none, ai_out) == f"{name} beat you  ({ai_out.score} vs 0)"
    assert results._verdict(pete_out, ai_none) == f"You beat {name}  ({pete_out.score} vs 0)"
    for text in (results._verdict(pete_none, ai_out), results._verdict(pete_out, ai_none)):
        assert not any(old in text for old in _OLD)


# ------------------------------------------------------------------ the HUD
def test_toasts_use_the_name_even_for_a_learned_model():
    s = _session(learned=True)
    h = s.hud
    h.update(0.0, s)
    h.toasts.clear()
    s.agent_stats.victims_saved = 1
    s.agent.health = 0.0
    assert s.agent.is_dead
    h.update(0.016, s)
    texts = [t.text for t in h.toasts if not t.big]
    assert any(t.endswith("AI Robot led an occupant out") for t in texts)
    assert "AI Robot is down" in texts
    assert not any(old in t for t in texts for old in _OLD)


@pytest.mark.parametrize("visual,expected", [("robot", "AI  ·  ROBOT"), ("drone", "AI  ·  DRONE")])
def test_the_ai_card_shows_the_name_without_learned(visual, expected):
    s = _session(visual, learned=True)
    said = _record_hud(s)
    s.hud.t = 5.0
    s.hud.update(0.0, s)
    s.hud.draw(SCREEN, s)
    assert expected in said and "YOU  ·  PETE" in said
    assert not any(old in t for t in said for old in _OLD)


def test_the_tooltip_titles_the_rescuer_and_says_who_is_driving():
    s = _session(learned=True)
    ai = s.hud.tooltip_rows("ai", s)
    assert ai[0].text == "AI ROBOT" and ai[0].head
    assert {r.text: r.value for r in ai}["Controlled by"] == "Learned model"
    you = s.hud.tooltip_rows("you", s)
    assert you[0].text == "PETE" and {r.text: r.value for r in you}["Controlled by"] == "Human player"
    assert {r.text: r.value for r in _session().hud.tooltip_rows("ai", _session())}["Controlled by"] == "A* planner"


# ------------------------------------------- everything drawn, in one sweep
@pytest.mark.parametrize("visual", ["robot", "drone"])
def test_no_screen_draws_the_old_label_anywhere(visual):
    """Every string the HUD (with toasts and every tooltip) and both results
    panels draw, for a learned model -- the case that used to leak "(learned)"."""
    s = _session(visual, learned=True)
    said = _record_hud(s)
    h = s.hud
    h.t = 5.0
    h.update(0.0, s)
    s.agent_stats.victims_saved = 1                     # toasts
    s.agent.health = 0.0
    s.victims[0].state = STATE_DEAD
    h.update(0.016, s)
    h.draw(SCREEN, s)
    for rect, kind in list(h.hot):                       # every tooltip
        h.draw(SCREEN, s, mouse=rect.center)

    fonts = [Rec(ui_font(r), said) for r in ("title", "heading", "body")]
    small, bold = Rec(ui_font("small"), said), Rec(ui_font("body", bold=True), said)
    pete = _stats("You (Pete)", 1, "exit")
    ai = _stats(f"AI {visual} (learned)", 2, "exit")
    for outcome in ("cleared", "outrun", "died"):
        results.draw_results(SCREEN, *fonts, pete, ai, 3, outcome=outcome,
                             stage_label="Stage 1/10 - Ground Floor", has_next_stage=True,
                             total_font=bold, small_font=small)
    for cleared in (True, False):
        results.draw_watch_results(SCREEN, *fonts, ai, 3, stage_label="Stage 1/10 - Ground Floor",
                                   cleared=cleared, has_next_stage=True, total_font=bold,
                                   small_font=small)
    assert len(said) > 40                                # it really recorded a lot
    assert not [t for t in said if any(old in t for old in _OLD)]


def test_no_code_in_the_hud_or_results_shows_the_running_label():
    """`stats.label` is internal now. Reaching for it again is how the old
    spellings would creep back."""
    offenders = []
    for name in ("hud.py", "results.py"):
        for n, line in enumerate((_GAME_DIR / name).read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if re.search(r"\b\w+\.label\b(?!\()", code):
                offenders.append(f"{name}:{n}: {line.strip()}")
    assert not offenders, "show display_name / role instead of .label:\n" + "\n".join(offenders)
