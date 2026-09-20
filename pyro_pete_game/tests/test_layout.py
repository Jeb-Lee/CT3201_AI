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
    sub = results._subtitle(levels.label(index), 12)
    body, chips = ui_font("body"), ui_font("body", bold=True)
    hint_w = results._hint_block(True, True, "", body, chips)[2]
    w = _fit_panel_width(_BODY.size(sub)[0] + 60, hint_w + 40)
    assert w >= _BODY.size(sub)[0] + 60           # text plus its margins
    assert w >= hint_w + 40
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
    # The panel is a vertical gradient, so "background" is the colour at the
    # panel's left inner edge on the same row; anything else is headline text.
    band = range(py + 18, py + 18 + _FONTS[0].get_height() - 8)   # headline text
    bg = {y: screen.get_at((px + 14, y))[:3] for y in band}
    lit = [x for x in range(px + 14, px + w - 14)
           if any(screen.get_at((x, y))[:3] != bg[y] for y in band)]
    assert lit, "no headline text found"
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
    # the header changed (portrait + name + info line), so this is its new baseline
    assert results._head_block(h, b) == (2, 25, 66)


@pytest.mark.parametrize("fonts_", [_FONTS, _DEFAULT_FONTS, _TALL_FONTS],
                         ids=["arial", "default", "tall"])
def test_spacing_scales_with_the_font_so_nothing_overlaps(fonts_):
    """The reason for deriving spacing from font heights: a taller face used
    to leave rows touching and the subtitle touching the headline."""
    t, h, b = fonts_
    assert results._row_h(b) >= b.get_linesize()            # rows don't collide
    assert results._sub_y(t) >= 18 + t.get_height()         # subtitle below headline
    assert results._top(t, b) >= results._sub_y(t) + b.get_height()
    name_y, info_y, head_h = results._head_block(h, b)
    assert info_y >= name_y + h.get_height()                # the info line is below the name
    assert head_h >= info_y + b.get_height()                # the SCORE section is below the info line
    assert head_h >= results._PORTRAIT                      # ...and below the portrait


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
    heights = [ui_font(r).get_height() for r in ("display", "title", "heading", "body", "small")]
    assert heights == sorted(heights, reverse=True) and len(set(heights)) == 5
    # the scale's weights: display, titles and headings bold, reading text regular
    assert fonts._SCALE["display"][2] and fonts._SCALE["title"][2] and fonts._SCALE["heading"][2]
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


# --- the name block: who it is, how it decided, how it ended --------------------
import fonts
from hud_icons import BLUE
from portraits import draw_portrait, portrait_image
from settings import RESULTS_ACCENT_COLOR

_SMALL = ui_font("small")
_TITLE = _FONTS[0]


class _Rec:
    """A font that records what it was asked to render (and otherwise is the font)."""
    def __init__(self, font):
        self._f, self.said = font, []

    def render(self, text, *a, **k):
        self.said.append(text)
        return self._f.render(text, *a, **k)

    def __getattr__(self, name):
        return getattr(self._f, name)


def _col(st, width, head=None, small=None, title=None):
    """A column drawn at (20, 10); returns (surface, x, top_y)."""
    surf = pygame.Surface((max(400, width + 40), 520))
    surf.fill((0, 0, 0))
    results._draw_column(surf, head or _FONTS[1], _FONTS[2], 20, 10, width, st, _BOLD,
                         title or _TITLE, small or _SMALL)
    return surf, 20, 10


def _has(surf, colour, box):
    x0, y0, x1, y1 = box
    return any(surf.get_at((x, y))[:3] == colour
               for x in range(x0, x1) for y in range(y0, y1))


# ---- who a rescuer is (stats.py) ------------------------------------------------
def test_a_rescuer_knows_its_name_and_how_it_decides():
    pete, robot = RunStats("You (Pete)"), RunStats("AI robot")
    drone, learned = RunStats("AI drone"), RunStats("AI robot (learned)")
    assert (pete.kind, pete.brain, pete.display_name, pete.role) == ("you", "human", "Pete", "Human player")
    assert (robot.kind, robot.brain, robot.display_name, robot.role) == ("robot", "astar", "AI Robot", "A* planner")
    assert (drone.display_name, drone.role) == ("AI Drone", "A* planner")
    assert (learned.display_name, learned.role) == ("AI Robot", "Learned model")   # "(learned)" leaves the name
    assert RunStats("anything", kind="drone", brain="learned").display_name == "AI Drone"   # explicit wins
    with pytest.raises(ValueError):
        RunStats("x", kind="cat")
    with pytest.raises(ValueError):
        RunStats("x", kind="robot", brain="magic")


@pytest.mark.parametrize("visual,kind", [("robot", "robot"), ("drone", "drone")])
def test_the_game_says_who_each_rescuer_is_instead_of_leaving_it_to_the_label(visual, kind):
    s = game.GameSession(levels.get(0), spectate=False, agent_visual=visual)
    assert (s.player_stats.kind, s.player_stats.brain) == ("you", "human")
    assert (s.agent_stats.kind, s.agent_stats.brain) == (kind, "astar")


# ---- portraits ---------------------------------------------------------------------
def test_pete_and_the_robot_have_portraits_and_the_drone_is_drawn():
    for kind in ("pete", "robot"):
        img = portrait_image(kind, 42)
        assert img is not None and max(img.get_size()) <= 42
        assert portrait_image(kind, 42) is img                    # cached
    assert portrait_image("drone", 42) is None
    for kind, accent in (("pete", RESULTS_ACCENT_COLOR), ("robot", BLUE), ("drone", BLUE)):
        surf = pygame.Surface((80, 80))
        surf.fill((0, 0, 0))
        rect = pygame.Rect(10, 10, 50, 50)
        draw_portrait(surf, rect, kind, accent)
        assert surf.get_at((rect.centerx, rect.y))[:3] == accent  # framed in the rescuer's colour


# ---- colour: gold is you, blue is the AI (as in the HUD) ------------------------------
@pytest.mark.parametrize("width", [278, 356], ids=["race column", "watch column"])
def test_pete_is_gold_and_the_ai_is_blue(width):
    nx = 20 + results._PORTRAIT + results._PORTRAIT_GAP
    name = (nx, 10, nx + 110, 10 + 30)
    pete, _, _ = _col(_stats("You (Pete)"), width)
    ai, _, _ = _col(_stats("AI robot"), width)
    assert _has(pete, RESULTS_ACCENT_COLOR, name) and not _has(pete, BLUE, name)
    assert _has(ai, BLUE, name) and not _has(ai, RESULTS_ACCENT_COLOR, name)


@pytest.mark.parametrize("reason,colour", [("exit", results._POS), ("dead", results._NEG),
                                           ("time", results._AMBER)])
def test_the_outcome_is_coloured_by_whether_it_was_good(reason, colour):
    nx = 20 + results._PORTRAIT + results._PORTRAIT_GAP
    info_y = results._head_block(_FONTS[1], _SMALL)[1]
    surf, _, _ = _col(_stats(reason=reason), 356)
    assert _has(surf, colour, (nx, 10 + info_y, 20 + 356, 10 + info_y + _SMALL.get_height()))


# ---- wording -----------------------------------------------------------------------------
def test_the_name_block_uses_the_names_and_says_how_it_decided_and_ended():
    head, small = _Rec(_FONTS[1]), _Rec(_SMALL)
    _col(_stats("AI robot (learned)", reason="time"), 356, head=head, small=small)
    assert "AI Robot" in head.said and not any("learned" in t for t in head.said)
    assert "Learned model" in small.said and "still searching" in small.said
    head, small = _Rec(_FONTS[1]), _Rec(_SMALL)
    _col(_stats("You (Pete)", reason="dead"), 278, head=head, small=small)
    assert "Pete" in head.said and "You (Pete)" not in head.said
    assert "Human player" in small.said and "did not make it" in small.said


def test_the_role_gives_way_before_the_outcome():
    parts = results._info_parts
    full = parts(_SMALL, "A* planner", "reached the exit", results._POS, 10_000)
    assert [t for t, _ in full] == ["A* planner", results._INFO_SEP, "reached the exit"]
    assert parts(_SMALL, "A* planner", "reached the exit", results._POS, 30) == [
        ("reached the exit", results._POS)]                         # no room: keep the outcome
    assert parts(_SMALL, "A* planner", "", results._DIM, 10_000) == [("A* planner", results._DIM)]


@pytest.mark.skipif(not fonts._first_existing(fonts._REGULAR_PATHS),
                    reason="widths differ on the fallback font; the role dropping is its design")
def test_every_role_and_outcome_fits_a_race_column_with_arial():
    """If any pair overflowed, that rescuer's role would vanish and its column
    would disagree with its neighbour's."""
    col_w = (660 - 2 * results._MARGIN - results._GAP) // 2
    avail = col_w - results._PORTRAIT - results._PORTRAIT_GAP
    for role in ("Human player", "A* planner", "Learned model"):
        for status, _ in results._STATUS.values():
            assert _SMALL.size(role + results._INFO_SEP + status)[0] <= avail, (role, status)


def test_in_a_race_column_the_name_and_score_share_a_line_without_touching():
    col_w = (660 - 2 * results._MARGIN - results._GAP) // 2
    room = col_w - results._PORTRAIT - results._PORTRAIT_GAP
    widest_name = max(_FONTS[1].size(n)[0] for n in ("Pete", "AI Robot", "AI Drone"))
    score = _FONTS[1].size("9999")[0]
    assert widest_name + score + 12 <= room


def test_a_wide_column_has_a_points_caption_and_a_narrow_one_does_not():
    wide, narrow = _Rec(_SMALL), _Rec(_SMALL)
    _col(_stats(), 356, small=wide)
    _col(_stats(), 278, small=narrow)
    assert "POINTS" in wide.said and "POINTS" not in narrow.said


def test_the_info_line_leaves_room_for_the_big_score(monkeypatch):
    seen = []
    real = results._info_parts
    monkeypatch.setattr(results, "_info_parts",
                        lambda font, role, status, colour, avail: (seen.append(avail),
                                                                   real(font, role, status, colour, avail))[1])
    nx = results._PORTRAIT + results._PORTRAIT_GAP
    _col(_stats(saved=12, dmg=0), 356)                            # wide: 4-digit score, big
    big = _TITLE.size(str(_stats(saved=12, dmg=0).score))[0]
    cap = _SMALL.size("POINTS")[0]
    assert seen[-1] == 356 - nx - (max(big, cap) + 12)
    _col(_stats(), 278)                                           # narrow: the score is on the name's line
    assert seen[-1] == 278 - nx


# ---- the subtitle and the headline --------------------------------------------------------------
def test_the_subtitle_uses_dots_and_gets_singular_and_plural_right():
    assert results._subtitle("Stage 1/10 - Ground Floor", 3) == "Stage 1/10  ·  Ground Floor  ·  3 occupants"
    assert results._subtitle("Stage 1/10 - Ground Floor", 1).endswith("1 occupant")
    assert results._subtitle(None, 3) == "3 occupants"
    for text in (results._subtitle(levels.label(i), n) for i in range(levels.STAGE_COUNT) for n in (1, 5)):
        assert "--" not in text and " - " not in text


@pytest.mark.parametrize("cleared,headline", [(True, "The AI cleared the stage"),
                                              (False, "The AI didn't make it")])
def test_the_watch_headline_says_who_did_it(cleared, headline):
    title = _Rec(_FONTS[0])
    results.draw_watch_results(pygame.display.get_surface(), title, _FONTS[1], _FONTS[2], _stats(),
                               3, stage_label="Stage 1/10 - Ground Floor", cleared=cleared,
                               has_next_stage=True, total_font=_BOLD, small_font=_SMALL)
    assert headline in title.said


# ---- the panels still fit, and main wires the new font ------------------------------------------
@pytest.mark.parametrize("draw", ["watch", "race"])
@pytest.mark.parametrize("kind", ["robot", "drone"])
def test_the_new_header_keeps_every_panel_on_screen(draw, kind, monkeypatch):
    seen = []
    real = results._draw_panel
    monkeypatch.setattr(results, "_draw_panel",
                        lambda s, px, py, w, h: (seen.append((px, py, w, h)), real(s, px, py, w, h))[1])
    screen = pygame.display.get_surface()
    ai = _stats(f"AI {kind} (learned)", saved=12, dmg=200, died=True, reason="dead")
    label = levels.label(levels.STAGE_COUNT - 1)
    if draw == "watch":
        results.draw_watch_results(screen, *_FONTS, ai, 12, stage_label=label, cleared=False,
                                   has_next_stage=True, total_font=_BOLD, small_font=_SMALL)
    else:
        results.draw_results(screen, *_FONTS, _stats("You (Pete)", saved=12, dmg=200, died=True,
                             reason="dead"), ai, 12, outcome="died", stage_label=label,
                             has_next_stage=True, total_font=_BOLD, small_font=_SMALL)
    px, py, w, h = seen[0]
    assert py >= 10 and py + h <= results.SCREEN_HEIGHT - 10 and px >= 0 and px + w <= SCREEN_WIDTH


@pytest.mark.parametrize("width", [278, 356], ids=["race column", "watch column"])
def test_the_column_reports_its_height_with_the_new_header(width):
    for kw in (dict(), dict(dmg=200, reason="dead", died=True), dict(reason="time")):
        st = _stats(**kw)
        surf = pygame.Surface((500, 600))
        end = results._draw_column(surf, _FONTS[1], _FONTS[2], 20, 10, width, st, _BOLD, _TITLE, _SMALL)
        assert end - 10 == results._column_height(_FONTS[1], _FONTS[2], st, _SMALL)


def test_the_game_hands_the_small_font_to_both_results_panels():
    src = (_GAME_DIR / "main.py").read_text(encoding="utf-8")
    assert 'small_font = ui_font("small")' in src
    assert src.count("small_font=small_font") == 2
