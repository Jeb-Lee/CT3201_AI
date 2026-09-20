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


# --- results panel alignment -------------------------------------------------
import results
from fonts import ui_font
from stats import RunStats

_FONTS = tuple(ui_font(r) for r in ("title", "heading", "body"))       # what the game uses
_DEFAULT_FONTS = tuple(pygame.font.SysFont(None, s) for s in (44, 30, 24))  # the fallback
_TALL_FONTS = tuple(pygame.font.SysFont(None, s) for s in (72, 54, 44))      # stress: much taller lines


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
    assert end - 10 == results._column_height(_FONTS[1], _FONTS[2], st)


def test_values_end_on_the_shared_right_edge():
    """A number is right-aligned to the column edge: it touches it and never
    pokes past it. (Left-aligned values left the right edges ragged.)"""
    st = _stats()
    surf = pygame.Surface((400, 500))
    surf.fill((0, 0, 0))
    right = 380
    results._draw_column(surf, _FONTS[1], _FONTS[2], 20, 0, right - 20, st)
    # first score row: y = section heading + rule, then one row of text
    row_top = results._head_block(_FONTS[1], _FONTS[2])[2] + _FONTS[2].get_height() + 2 + 8
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


# --- second tidy-up: died row, Total row, divider, zero rows, centring --------
def test_pete_gets_a_died_row_like_the_agent_does():
    """Pete's death is recorded with finish("dead") and never touches
    `deaths`; only RescueAgent.mark_death() does. Both must show "Died"."""
    pete, agent = RunStats("You (Pete)"), RunStats("AI robot")
    pete.finish("dead")
    agent.mark_death()
    assert ("Died", "yes") in pete.summary_rows()
    assert ("Died", "yes") in agent.summary_rows()
    assert ("Died", "yes") not in _stats().summary_rows()      # survivors: none


def test_total_matches_the_rows_unless_the_score_was_floored():
    ok = _stats(saved=3, dmg=33)
    assert not ok.score_floored
    assert sum(p for _, p in ok.score_breakdown()) == ok.score

    floored = _stats(saved=0, dmg=100, reason="dead")      # +0 and -40
    assert floored.score_floored
    assert sum(p for _, p in floored.score_breakdown()) == -40
    assert floored.score == 0                                # held at zero


def _row_pixels(st, colour):
    """Does any pixel of `colour` appear on the first score row?"""
    surf = pygame.Surface((400, 500))
    surf.fill((0, 0, 0))
    results._draw_column(surf, _FONTS[1], _FONTS[2], 20, 0, 360, st)
    top = results._head_block(_FONTS[1], _FONTS[2])[2] + _FONTS[2].get_height() + 2 + 8
    return any(surf.get_at((x, y))[:3] == colour
               for x in range(20, 380) for y in range(top, top + _FONTS[2].get_height()))


def test_a_zero_points_row_is_not_green_but_real_points_are():
    assert _row_pixels(_stats(saved=3), results._POS)          # +300: green
    assert not _row_pixels(_stats(saved=0, dmg=0, reason="dead"), results._POS)


def test_race_panel_has_a_divider_between_the_columns(monkeypatch):
    seen = []
    real = results._draw_panel
    monkeypatch.setattr(results, "_draw_panel",
                        lambda s, px, py, w, h: (seen.append((px, py, w, h)),
                                                 real(s, px, py, w, h))[1])
    screen = pygame.display.get_surface()
    results.draw_results(screen, *_FONTS, _stats("You (Pete)"), _stats(), 4,
                         outcome="cleared", stage_label="Stage 2/10 - Staff Canteen",
                         has_next_stage=True)
    px, py, w, h = seen[0]
    col_w = (w - 2 * results._MARGIN - results._GAP) // 2
    mid = px + results._MARGIN + col_w + results._GAP // 2
    assert screen.get_at((mid, py + results._top(_FONTS[0], _FONTS[2]) + 20))[:3] == (60, 62, 70)


@pytest.mark.parametrize("which", ["watch", "race"])
def test_headline_is_centred_on_the_panel(which, monkeypatch):
    seen = []
    real = results._draw_panel
    monkeypatch.setattr(results, "_draw_panel",
                        lambda s, px, py, w, h: (seen.append((px, py, w, h)),
                                                 real(s, px, py, w, h))[1])
    screen = pygame.display.get_surface()
    stage = levels.label(1)
    if which == "watch":
        results.draw_watch_results(screen, *_FONTS, _stats(), 3, stage_label=stage,
                                   cleared=True, has_next_stage=True)
    else:
        results.draw_results(screen, *_FONTS, _stats("You (Pete)"), _stats(), 4,
                             outcome="cleared", stage_label=stage, has_next_stage=True)
    px, py, w, h = seen[0]
    bg = tuple(results.RESULTS_PANEL_COLOR[:3])
    band = range(py + 18, py + 18 + _FONTS[0].get_height() - 8)   # headline text
    lit = [x for x in range(px + 4, px + w - 4)
           if any(screen.get_at((x, y))[:3] != bg for y in band)]
    assert abs((lit[0] + lit[-1]) / 2 - (px + w / 2)) <= 3


# --- fonts -------------------------------------------------------------------
import fonts


def test_ui_font_falls_back_to_the_default_font_when_no_face_exists(monkeypatch):
    """Teammates on other machines may have no Arial at all. The game must
    still start, with the default font."""
    monkeypatch.setattr(fonts, "_REGULAR_PATHS", ("/no/such/font.ttf",))
    monkeypatch.setattr(fonts, "_BOLD_PATHS", ("/no/such/font-bold.ttf",))
    for role, (_, default_size, _) in fonts._SCALE.items():
        f = fonts.ui_font(role)
        assert f.get_height() == pygame.font.SysFont(None, default_size).get_height()


def test_ui_font_falls_back_when_the_font_file_cannot_be_opened(monkeypatch):
    """A file that exists but can't be opened (permissions, locked) raises
    OSError; the game should fall back rather than fail to start. (A
    *corrupt* file is not testable: pygame 2.6 crashes the whole process on
    one instead of raising.)"""
    def cannot_open(*a, **k):
        raise OSError("cannot open")
    monkeypatch.setattr(fonts.pygame.font, "Font", cannot_open)
    monkeypatch.setattr(fonts, "_first_existing", lambda paths: "C:/Windows/Fonts/arial.ttf")
    f = fonts.ui_font("body")
    assert f.get_height() == pygame.font.SysFont(None, fonts._SCALE["body"][1]).get_height()


def test_default_font_layout_is_unchanged_by_the_font_metrics_refactor():
    """Spacing now derives from font heights. With pygame's default font it
    must come out to the numbers that were hard-coded before, so the fallback
    looks exactly as it did."""
    t, h, b = _DEFAULT_FONTS
    assert results._row_h(b) == 22
    assert results._sub_y(t) == 54
    assert results._top(t, b) == 86
    assert results._head_block(h, b) == (26, 46, 78)


@pytest.mark.parametrize("fonts_", [_FONTS, _DEFAULT_FONTS, _TALL_FONTS],
                         ids=["arial", "default", "tall"])
def test_spacing_scales_with_the_font_so_nothing_overlaps(fonts_):
    """The reason for deriving spacing from font heights: a taller face used
    to leave rows touching and the subtitle touching the headline."""
    t, h, b = fonts_
    assert results._row_h(b) >= b.get_linesize()            # rows don't collide
    assert results._sub_y(t) >= 18 + t.get_height()         # subtitle below headline
    assert results._top(t, b) >= results._sub_y(t) + b.get_height()
    reason_y, score_y, head_h = results._head_block(h, b)
    assert reason_y >= h.get_height()                       # reason below the name
    assert score_y >= reason_y + b.get_height()             # score below the reason
    assert head_h >= score_y + h.get_height()               # section below the score


@pytest.mark.parametrize("fonts_", [_FONTS, _DEFAULT_FONTS], ids=["arial", "default"])
@pytest.mark.parametrize("draw", ["watch", "race"])
def test_results_panel_fits_the_screen_with_either_font(fonts_, draw, monkeypatch):
    """Arial's lines are taller than the default font's, so the tallest panel
    (4 score rows + 5 stats rows + Total + verdict) must still fit on screen."""
    seen = []
    real = results._draw_panel
    monkeypatch.setattr(results, "_draw_panel",
                        lambda s, px, py, w, h: (seen.append((px, py, w, h)),
                                                 real(s, px, py, w, h))[1])
    screen = pygame.display.get_surface()
    st = _stats(saved=3, dmg=200, reason="exit", died=True)
    label = levels.label(levels.STAGE_COUNT - 1)
    if draw == "watch":
        results.draw_watch_results(screen, *fonts_, st, 12, stage_label=label,
                                   cleared=True, has_next_stage=True)
    else:
        results.draw_results(screen, *fonts_, st, st, 12, outcome="cleared",
                             stage_label=label, has_next_stage=True)
    px, py, w, h = seen[0]
    assert py >= 10 and py + h <= results.SCREEN_HEIGHT - 10   # a margin each side
    assert px >= 0 and px + w <= SCREEN_WIDTH


# --- one typeface, one scale, across every screen ------------------------------
import re
from pathlib import Path

_GAME_DIR = Path(__file__).resolve().parent.parent


def test_no_module_creates_its_own_font():
    """The point of fonts.ui_font: one typeface and one size scale. A stray
    pygame.font.SysFont / Font call anywhere else is how the intro ended up in
    Courier New, the menus in six default-font sizes and the results in Arial."""
    offenders = []
    for path in _GAME_DIR.rglob("*.py"):
        rel = path.relative_to(_GAME_DIR).as_posix()
        if rel.startswith(("tests/", "ml/")) or rel == "fonts.py":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if re.search(r"font\.(SysFont|Font)\(|freetype", code):
                offenders.append(f"{rel}:{n}: {line.strip()}")
    assert not offenders, "create fonts through fonts.ui_font instead:\n" + "\n".join(offenders)


def test_the_scale_is_strictly_ordered_and_bold_differs_from_regular():
    heights = [ui_font(r).get_height() for r in ("title", "heading", "body", "small")]
    assert heights == sorted(heights, reverse=True) and len(set(heights)) == 4
    # the scale's weights: titles and headings bold, reading text regular
    assert fonts._SCALE["title"][2] and fonts._SCALE["heading"][2]
    assert not fonts._SCALE["body"][2] and not fonts._SCALE["small"][2]
    # asking for bold body text really gives a different (wider) face
    if fonts._first_existing(fonts._BOLD_PATHS):
        assert ui_font("body", bold=True).size("Occupants out")[0] > \
            ui_font("body", bold=False).size("Occupants out")[0]


@pytest.mark.parametrize("build", ["_build_mode_menu", "_build_skin_menu", "_build_brain_menu"])
def test_every_menu_line_fits_its_panel(build):
    """The menu panel is min(560, width-40) wide and each option box 420: the
    subtitle, every label and description and the hint must fit inside."""
    menu = getattr(game, build)(None)
    panel_w = min(560, SCREEN_WIDTH - 40)
    lines = [(menu._title_font, menu.title, panel_w - 40),
             (menu._subtitle_font, menu.subtitle or "", panel_w - 40),
             (menu._hint_font, "Arrow keys or mouse to choose, Enter to select", panel_w - 40)]
    for label, _, desc in menu.options:
        lines.append((menu._option_font, label, 420 - 20))
        if desc:
            lines.append((menu._desc_font, desc, 420 - 20))
    for font, text, room in lines:
        assert font.size(text)[0] <= room, (text, font.size(text)[0], room)
    # and the whole thing draws
    menu.draw(pygame.Surface((SCREEN_WIDTH, 640)))


def test_waiting_occupant_marker_stays_at_least_as_tall_as_it_was():
    """The red "!" is a gameplay cue: it must not shrink now that the HUD font
    is smaller. (It measured 14px in the old default font at size 28.)"""
    s = game.GameSession(levels.get(0), spectate=False, agent_visual="robot")
    glyph = s.marker_font.render("!", True, (255, 80, 80)).get_bounding_rect()
    assert glyph.height >= 14


def test_intro_prompt_font_is_created_once_not_every_frame():
    import intro

    class Scene:
        blink_t = 0.0
    surf = pygame.Surface((SCREEN_WIDTH, 640))
    intro.IntroScene._draw_prompt(Scene, surf)
    first = Scene._prompt_font
    intro.IntroScene._draw_prompt(Scene, surf)
    assert Scene._prompt_font is first


# --- the Total row is the one bold row ----------------------------------------
_BOLD = ui_font("body", bold=True)


def _draw_col(st, total_font):
    surf = pygame.Surface((400, 500))
    surf.fill((0, 0, 0))
    end = results._draw_column(surf, _FONTS[1], _FONTS[2], 20, 0, 360, st, total_font)
    return surf, end


def _total_band(st):
    """The y range of the Total row in a column drawn at top 0."""
    body = _FONTS[2]
    y = (results._head_block(_FONTS[1], body)[2] + body.get_height() + 2 + 8
         + len(st.score_breakdown()) * results._row_h(body) + results._TOTAL_PAD)
    return y, y + body.get_height()


def _ink(surf, box):
    """How many non-black pixels are inside box (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    return sum(1 for x in range(x0, x1) for y in range(y0, y1) if surf.get_at((x, y))[:3] != (0, 0, 0))


def test_only_the_total_row_changes_when_it_goes_bold():
    st = _stats()
    regular, _ = _draw_col(st, None)
    bold, _ = _draw_col(st, _BOLD)
    top, bottom = _total_band(st)
    diff = [y for y in range(500) if any(regular.get_at((x, y)) != bold.get_at((x, y))
                                         for x in range(400))]
    assert diff and top - 2 <= min(diff) and max(diff) <= bottom + 2      # nothing outside the Total row
    assert _ink(bold, (20, top, 380, bottom)) > _ink(regular, (20, top, 380, bottom))


def test_the_total_label_is_full_white_where_the_other_labels_are_dim():
    st = _stats()
    surf, _ = _draw_col(st, _BOLD)
    body = _FONTS[2]

    def brightest(top):
        return max(max(surf.get_at((x, y))[:3]) for x in range(20, 100)
                   for y in range(top, top + body.get_height()))
    total_top, _ = _total_band(st)
    first_row = results._head_block(_FONTS[1], body)[2] + body.get_height() + 2 + 8
    assert brightest(total_top) >= 225            # RESULTS_TEXT_COLOR
    assert brightest(first_row) <= 180            # "Occupants led out": dim grey


def test_a_bold_total_does_not_change_the_columns_height():
    """The panel is sized from _column_height; the Total row's height comes
    from the body font, not the bold one."""
    for kw in (dict(), dict(dmg=200, reason="dead", died=True)):
        st = _stats(**kw)
        _, end_regular = _draw_col(st, None)
        _, end_bold = _draw_col(st, _BOLD)
        assert end_regular == end_bold == results._column_height(_FONTS[1], _FONTS[2], st)


def test_the_widest_bold_total_still_fits_a_race_column():
    col_w = (660 - 2 * results._MARGIN - results._GAP) // 2
    assert _BOLD.size("Total (min 0)")[0] + 24 + _BOLD.size("99999")[0] <= col_w


@pytest.mark.parametrize("draw", ["watch", "race"])
def test_both_results_panels_accept_the_bold_total_and_still_fit(draw, monkeypatch):
    seen = []
    real = results._draw_panel
    monkeypatch.setattr(results, "_draw_panel",
                        lambda s, px, py, w, h: (seen.append((px, py, w, h)), real(s, px, py, w, h))[1])
    screen = pygame.display.get_surface()
    st = _stats(saved=3, dmg=200, reason="exit", died=True)
    label = levels.label(levels.STAGE_COUNT - 1)
    if draw == "watch":
        results.draw_watch_results(screen, *_FONTS, st, 12, stage_label=label, cleared=True,
                                   has_next_stage=True, total_font=_BOLD)
    else:
        results.draw_results(screen, *_FONTS, st, st, 12, outcome="cleared", stage_label=label,
                             has_next_stage=True, total_font=_BOLD)
    px, py, w, h = seen[0]
    assert py >= 10 and py + h <= results.SCREEN_HEIGHT - 10 and px >= 0 and px + w <= SCREEN_WIDTH


def test_the_game_hands_the_bold_font_to_both_results_panels():
    """main() is a loop that can't be driven from a test, so check the wiring
    at the source: a font built once, and passed at both call sites."""
    src = (_GAME_DIR / "main.py").read_text(encoding="utf-8")
    assert 'total_font = ui_font("body", bold=True)' in src
    assert src.count("total_font=total_font") == 2      # draw_results and draw_watch_results
