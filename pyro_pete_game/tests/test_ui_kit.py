"""The shared UI kit (panels, key-cap hints) and the screens built on it.

These check what is on the screen, with the real fonts: hints sit inside their
panel, say the same thing in both modes, and a headline never touches the edge.
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

import hud_icons
import levels
import results
from fonts import ui_font
from settings import SCREEN_WIDTH, SCREEN_HEIGHT, RESULTS_ACCENT_COLOR
from stats import RunStats

pygame.init()
pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

_CHIP, _BODY = ui_font("body", bold=True), ui_font("body")
_FONTS = tuple(ui_font(r) for r in ("title", "heading", "body"))
_ITEMS = [("Enter", "Next stage"), ("R", "Replay"), ("Esc", "Quit")]


def _screen():
    s = pygame.display.get_surface()
    s.fill((0, 0, 0))
    return s


def _stats(label="AI Robot", **kw):
    s = RunStats(label)
    s.victims_saved, s.elapsed, s.distance = kw.get("saved", 3), 43.0, 110 * 64
    s.replans, s.goal_changes, s.finished_reason = 114, 24, kw.get("reason", "exit")
    return s


# --- the kit -------------------------------------------------------------------
def test_hint_row_is_centred_and_as_wide_as_advertised():
    rect = hud_icons.key_hint_row(_screen(), _ITEMS, _CHIP, _BODY, 480, 300)
    assert rect.width == hud_icons.hint_row_width(_ITEMS, _CHIP, _BODY)
    assert rect.centerx == 480


def test_hint_row_is_drawn_exactly_where_it_says_it_is():
    """Measured from the pixels, not from hint_row_width -- a row that under-reports
    its width would be off-centre and could overrun its panel."""
    screen = _screen()
    rect = hud_icons.key_hint_row(screen, _ITEMS, _CHIP, _BODY, 480, 300)
    lit = [x for x in range(200, 760)
           if any(screen.get_at((x, y))[:3] != (0, 0, 0) for y in range(rect.top, rect.bottom))]
    assert 0 <= lit[0] - rect.left <= 2               # ink starts at the row's left edge...
    assert 0 <= rect.right - lit[-1] <= 4             # ...and stops at its right edge
    assert abs((lit[0] + lit[-1]) / 2 - 480) <= 3     # so what you see is centred
    # the labels use the hint colour (brighter than a key cap's fill)
    assert any(tuple(screen.get_at((x, 300))[:3]) == hud_icons.HINT for x in range(rect.left, rect.right))


def test_wider_labels_make_a_wider_row():
    short = hud_icons.hint_row_width([("R", "Go")], _CHIP, _BODY)
    long = hud_icons.hint_row_width([("R", "Go somewhere far away")], _CHIP, _BODY)
    assert long > short


def test_draw_panel_puts_an_accent_edge_and_a_shadow_on_screen():
    screen = _screen()
    screen.fill((120, 120, 120))                # a shadow only shows against something light
    rect = pygame.Rect(200, 200, 300, 120)
    hud_icons.draw_panel(screen, rect, accent=RESULTS_ACCENT_COLOR, alpha=255)
    assert screen.get_at((rect.centerx, rect.top + 1))[:3] != (120, 120, 120)     # the panel
    assert screen.get_at((rect.centerx, rect.bottom + 2))[:3] < (120, 120, 120)   # its shadow, darker
    assert screen.get_at((rect.left - 30, rect.centery))[:3] == (120, 120, 120)   # and no more
    r, g, b = screen.get_at((rect.left + 1, rect.centery))[:3]
    assert r > b                                                                  # gold, not grey


def test_panels_are_built_once_per_size():
    a = hud_icons.cached_panel((120, 80), None, 12, 220)
    assert hud_icons.cached_panel((120, 80), None, 12, 220) is a
    assert hud_icons.cached_panel((121, 80), None, 12, 220) is not a


# --- what the results panels say the keys do -----------------------------------------
def _hint_texts(cleared, has_next):
    msg, items = results._hint_items(cleared, has_next, "FINALE")
    return msg, items


def test_hint_wording_after_a_clear_with_more_stages():
    assert _hint_texts(True, True) == (None, [("Enter", "Next stage"), ("R", "Replay"), ("Esc", "Quit")])


def test_hint_wording_after_the_last_stage():
    msg, items = _hint_texts(True, False)
    assert msg == "FINALE"
    assert items == [("Enter", "Menu"), ("R", "Replay"), ("Esc", "Quit")]


def test_hint_wording_after_a_loss():
    assert _hint_texts(False, False) == (None, [("R", "Try again"), ("Enter", "Menu"), ("Esc", "Quit")])
    assert _hint_texts(False, True) == _hint_texts(False, False)     # a loss never offers "next"


def test_every_key_is_named_the_same_way_in_both_modes():
    """One key used to be described three ways, sentence-style, in different panels."""
    import ast
    tree = ast.parse(open(results.__file__, encoding="utf-8").read())
    strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert not [t for t in strings if "run again" in t or "to replay" in t or "to quit" in t
                or "for menu" in t or "for the next" in t]


def _draw(which, cleared, has_next, monkeypatch):
    seen = {}
    real_row = results.key_hint_row
    monkeypatch.setattr(results, "key_hint_row",
                        lambda *a, **k: seen.setdefault("row", real_row(*a, **k)))
    real_panel = results._draw_panel
    monkeypatch.setattr(results, "_draw_panel",
                        lambda s, px, py, w, h: (seen.setdefault("panel", pygame.Rect(px, py, w, h)),
                                                 real_panel(s, px, py, w, h))[1])
    screen = _screen()
    stage = levels.label(1)
    if which == "watch":
        results.draw_watch_results(screen, *_FONTS, _stats(), 3, stage_label=stage, cleared=cleared,
                                   has_next_stage=has_next, total_font=_CHIP, small_font=ui_font("small"))
    else:
        results.draw_results(screen, *_FONTS, _stats("Pete", saved=0), _stats(), 4,
                             outcome="cleared" if cleared else "died", stage_label=stage,
                             has_next_stage=has_next, total_font=_CHIP, small_font=ui_font("small"))
    return screen, seen["panel"], seen["row"]


@pytest.mark.parametrize("which", ["watch", "race"])
@pytest.mark.parametrize("cleared,has_next", [(True, True), (True, False), (False, True)])
def test_hints_sit_inside_the_panel_and_centred(which, cleared, has_next, monkeypatch):
    _, panel, row = _draw(which, cleared, has_next, monkeypatch)
    assert panel.contains(row)
    assert panel.bottom - row.bottom >= 12                      # breathing room under the keys
    assert abs(row.centerx - panel.centerx) <= 1
    assert panel.left >= 0 and panel.right <= SCREEN_WIDTH
    assert panel.top >= 0 and panel.bottom <= SCREEN_HEIGHT     # the finale line must not push it off


@pytest.mark.parametrize("which", ["watch", "race"])
def test_the_finale_message_is_drawn_in_gold_above_the_keys(which, monkeypatch):
    screen, panel, row = _draw(which, True, False, monkeypatch)
    band = pygame.Rect(panel.left + 20, row.top - 34, panel.width - 40, 30)
    gold = [1 for x in range(band.left, band.right) for y in range(band.top, band.bottom)
            if tuple(screen.get_at((x, y))[:3]) == RESULTS_ACCENT_COLOR[:3]]
    assert len(gold) > 40
    # and not on a panel that has no finale
    screen, panel, row = _draw(which, False, False, monkeypatch)
    band = pygame.Rect(panel.left + 20, row.top - 34, panel.width - 40, 30)
    assert not any(tuple(screen.get_at((x, y))[:3]) == RESULTS_ACCENT_COLOR[:3]
                   for x in range(band.left, band.right) for y in range(band.top, band.bottom))


@pytest.mark.parametrize("cleared", [True, False])
def test_watch_headline_keeps_a_margin_to_the_panel_edge(cleared, monkeypatch):
    _, panel, _ = _draw("watch", cleared, True, monkeypatch)
    headline = "The AI cleared the stage" if cleared else "The AI didn't make it"
    assert _FONTS[0].size(headline)[0] + 2 * results._MARGIN <= panel.width


@pytest.mark.parametrize("which", ["watch", "race"])
def test_results_panels_have_the_gold_edge(which, monkeypatch):
    screen, panel, _ = _draw(which, True, True, monkeypatch)
    r, g, b = screen.get_at((panel.left + 1, panel.centery))[:3]
    assert r - b > 100


# --- the first stage's banner says how to play ---------------------------------------------
import hud
import main as game


def _banner(stage_index, spectate=False):
    s = game.GameSession(levels.get(stage_index), spectate=spectate, agent_visual="robot",
                         stage_index=stage_index)
    s.update(1 / 60, pygame.key.get_pressed())
    banners = [t for t in s.hud.toasts if t.big]
    assert len(banners) == 1
    return s, banners[0]


def test_stage_one_banner_lists_the_keys_and_stays_up_long_enough_to_read():
    _, b = _banner(0)
    assert b.hints == (("WASD", "Move"), ("P", "Pause"), ("M", "Sound"))
    assert b.life == hud.CONTROLS_LIFE and hud.CONTROLS_LIFE > hud.BANNER_LIFE


def test_watching_has_no_move_key():
    _, b = _banner(0, spectate=True)
    assert b.hints == (("P", "Pause"), ("M", "Sound"))


def test_later_stages_do_not_repeat_the_lesson():
    _, b = _banner(1)
    assert b.hints == () and b.life == hud.BANNER_LIFE


def _draw_banner(hints, monkeypatch):
    seen = {}
    real = hud.key_hint_row
    monkeypatch.setattr(hud, "key_hint_row", lambda *a, **k: seen.setdefault("row", real(*a, **k)))
    s, b = _banner(0)
    b.hints = hints
    b.age = 1.0
    surf = _screen()
    s.hud._draw_banner(surf, b)
    lit = [(x, y) for x in range(0, SCREEN_WIDTH, 2) for y in range(0, SCREEN_HEIGHT // 2, 2)
           if surf.get_at((x, y))[:3] != (0, 0, 0)]
    xs, ys = [p[0] for p in lit], [p[1] for p in lit]
    return seen.get("row"), pygame.Rect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def test_a_banner_with_keys_is_taller_and_holds_the_key_row(monkeypatch):
    _, plain = _draw_banner((), monkeypatch)
    row, tall = _draw_banner((("WASD", "Move"), ("P", "Pause"), ("M", "Sound")), monkeypatch)
    assert tall.height >= plain.height + 30
    assert row is not None
    # the row is drawn on the banner's own surface: it fits inside its width and height
    width_needed = hud_icons.hint_row_width((("WASD", "Move"), ("P", "Pause"), ("M", "Sound")),
                                            ui_font("small", bold=True), ui_font("small"))
    assert tall.width >= width_needed + 60
    assert row.width == width_needed
    assert 0 <= row.left and row.right <= tall.width and row.bottom <= tall.height
