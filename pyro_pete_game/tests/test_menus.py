"""The choice menus: how they behave, and what they look like on screen."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

import main as game
import menu as menu_mod
from hud_icons import BLUE
from menu import ChoiceMenu
from settings import SCREEN_WIDTH, SCREEN_HEIGHT, RESULTS_ACCENT_COLOR

pygame.init()
pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))


def _key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def _menu(**kw):
    return ChoiceMenu("Title", [("One", 1, "first"), ("Two", 2, "second"), ("Three", 3, None)],
                      subtitle="Pick", **kw)


def _drawn(menu, mouse=None):
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    menu.draw(surf)
    return surf


# --- behaviour (unchanged by the restyle, and worth pinning) ----------------------------
def test_arrows_and_wasd_move_and_wrap():
    m = _menu()
    m.update(0, [_key(pygame.K_DOWN)]); assert m.index == 1
    m.update(0, [_key(pygame.K_s)]); assert m.index == 2
    m.update(0, [_key(pygame.K_DOWN)]); assert m.index == 0
    m.update(0, [_key(pygame.K_UP)]); assert m.index == 2
    m.update(0, [_key(pygame.K_w)]); assert m.index == 1


@pytest.mark.parametrize("k", [pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE])
def test_enter_picks_the_highlighted_option(k):
    m = _menu()
    m.update(0, [_key(pygame.K_DOWN), _key(k)])
    assert m.result == 2


def test_esc_cancels_without_picking():
    m = _menu()
    m.update(0, [_key(pygame.K_ESCAPE)])
    assert m.cancelled and m.result is None


def test_hover_highlights_and_click_picks_the_card_under_the_mouse():
    m = _menu()
    _drawn(m)
    target = m._option_rects[2]
    m.update(0, [pygame.event.Event(pygame.MOUSEMOTION, pos=target.center, rel=(0, 0), buttons=(0, 0, 0))])
    assert m.index == 2 and m.result is None
    m.update(0, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=m._option_rects[1].center, button=1)])
    assert m.result == 2


def test_a_click_beside_the_cards_picks_nothing():
    m = _menu()
    _drawn(m)
    m.update(0, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=1)])
    assert m.result is None


def test_three_part_options_still_work_and_only_four_part_ones_have_icons():
    assert not _menu().has_icons()
    m = ChoiceMenu("T", [("A", "a", "d", "pete"), ("B", "b", None)])
    assert m.has_icons()
    _drawn(m)                                            # the mixed case draws too


# --- the real menus ------------------------------------------------------------------
def test_the_ai_menus_are_blue_and_the_players_is_gold():
    assert game._build_mode_menu(None).accent == RESULTS_ACCENT_COLOR
    assert game._build_skin_menu(None).accent == BLUE
    assert game._build_brain_menu(None).accent == BLUE


def test_mode_and_look_menus_show_who_you_are_choosing():
    mode, skin = game._build_mode_menu(None), game._build_skin_menu(None)
    assert [o[3] for o in mode.options] == ["pete", "robot"]
    assert [o[3] for o in skin.options] == ["robot", "drone"]
    assert not game._build_brain_menu(None).has_icons()


# --- what is on screen -----------------------------------------------------------------
def _edge_colour(surf, rect):
    return tuple(surf.get_at((rect.centerx, rect.top))[:3])


@pytest.mark.parametrize("accent", [RESULTS_ACCENT_COLOR, BLUE])
def test_the_selected_card_is_outlined_in_the_accent_and_the_others_are_not(accent):
    m = _menu(accent=accent)
    surf = _drawn(m)
    sel, other = m._option_rects[0], m._option_rects[1]
    r, g, b = _edge_colour(surf, sel)
    assert (r, g, b) == accent or max(abs(r - accent[0]), abs(g - accent[1]), abs(b - accent[2])) <= 8
    er, eg, eb = _edge_colour(surf, other)
    assert max(abs(er - accent[0]), abs(eg - accent[1]), abs(eb - accent[2])) > 30
    # moving the selection moves the outline
    m.update(0, [_key(pygame.K_DOWN)])
    surf = _drawn(m)
    assert max(abs(c - a) for c, a in zip(_edge_colour(surf, m._option_rects[1]), accent)) <= 8
    assert max(abs(c - a) for c, a in zip(_edge_colour(surf, m._option_rects[0]), accent)) > 30


def test_the_selected_card_is_filled_with_a_tint_of_the_accent():
    gold, blue = _menu(accent=RESULTS_ACCENT_COLOR), _menu(accent=BLUE)
    for m in (gold, blue):
        _drawn(m)
    def fill(m):
        c = m._option_rects[0]
        return _drawn(m).get_at((c.left + 8, c.centery))[:3]
    (gr, _, gb), (br, _, bb) = fill(gold), fill(blue)
    assert gr > gb and bb > br                     # warm fill for gold, cool for blue


def test_cards_and_the_hint_row_sit_inside_the_panel(monkeypatch):
    seen = {}
    real = menu_mod.key_hint_row
    monkeypatch.setattr(menu_mod, "key_hint_row", lambda *a, **k: seen.setdefault("row", real(*a, **k)))
    for build in ("_build_mode_menu", "_build_skin_menu", "_build_brain_menu"):
        seen.clear()
        m = getattr(game, build)(None)
        _drawn(m)
        panel = m.panel_rect(SCREEN_WIDTH)
        assert all(panel.contains(r) for r in m._option_rects)
        assert panel.contains(seen["row"])
        assert seen["row"].top > max(r.bottom for r in m._option_rects)     # keys below the cards
        assert panel.bottom <= SCREEN_HEIGHT and panel.top >= 0


def test_the_key_hints_name_all_three_keys():
    labels = [t for _, t in _menu().hint_items()]
    keys = [k for k, _ in _menu().hint_items()]
    assert labels == ["Choose", "Select", "Quit"] and keys[1:] == ["Enter", "Esc"]


def test_arrow_key_cap_falls_back_to_words_if_the_font_has_no_arrows():
    class NoArrows:
        def metrics(self, text):
            return [None] * len(text)

    class HasArrows:
        def metrics(self, text):
            return [(0, 5, 0, 5, 6)] * len(text)
    assert menu_mod._arrows(NoArrows()) == "Up/Down"
    assert menu_mod._arrows(HasArrows()) == "↑ ↓"


def test_the_selection_chevron_nudges_over_time():
    m = _menu()
    a = _drawn(m)
    m.update(0.3, [])
    b = _drawn(m)
    card = m._option_rects[0]
    zone = pygame.Rect(card.right - 40, card.top + 8, 36, card.height - 16)
    assert pygame.image.tobytes(a.subsurface(zone), "RGB") != pygame.image.tobytes(b.subsurface(zone), "RGB")


def test_a_portrait_is_drawn_in_the_icon_slot():
    """A card is a vertical gradient, so any colour change along a row inside
    the slot is picture, not background."""
    m = ChoiceMenu("T", [("Robot", "r", "d", "robot"), ("Plain", "p", "d", None)])
    surf = _drawn(m)

    def across(card):
        slot = pygame.Rect(card.left + 12, card.centery - menu_mod.ICON // 2, menu_mod.ICON, menu_mod.ICON)
        inner = slot.inflate(-16, -16)
        return {tuple(surf.get_at((x, y))[:3]) for y in range(inner.top, inner.bottom)
                for x in range(inner.left, inner.right)}, {
            tuple(surf.get_at((x, inner.centery))[:3]) for x in range(inner.left, inner.right)}
    _, row_with = across(m._option_rects[0])
    _, row_without = across(m._option_rects[1])
    assert len(row_with) > 3                         # a picture
    assert len(row_without) == 1                     # nothing but the card


# --- many options (the brain menu can list A*, two learned models and an installed one) -------------
def _n_options(n, monkeypatch=None):
    return ChoiceMenu("T", [(f"Option {i}", i, f"description {i}") for i in range(n)], subtitle="Pick")


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_the_panel_stays_on_screen_and_cards_never_touch(n, monkeypatch):
    seen = {}
    real = menu_mod.key_hint_row
    monkeypatch.setattr(menu_mod, "key_hint_row", lambda *a, **k: seen.setdefault("row", real(*a, **k)))
    m = _n_options(n)
    _drawn(m)
    panel = m.panel_rect(SCREEN_WIDTH)
    if n <= 4:                                       # up to four options must fit the screen
        assert panel.bottom <= SCREEN_HEIGHT - menu_mod.PANEL_MARGIN
        assert panel.contains(seen["row"]) and all(panel.contains(r) for r in m._option_rects)
    for a, b in zip(m._option_rects, m._option_rects[1:]):
        assert b.top - a.bottom >= 4                 # a gap between cards, at any count
        assert b.centery - a.centery == m.card_gap()  # and the cards really are laid out at that gap
    assert m._option_rects[-1].bottom + menu_mod.PANEL_FOOT == panel.bottom   # so the panel ends where they do


def test_two_and_three_options_keep_the_designed_spacing():
    for n in (2, 3):
        m = _n_options(n)
        _drawn(m)
        assert m._option_rects[1].centery - m._option_rects[0].centery == menu_mod.CARD_GAP


def test_four_options_close_up_rather_than_run_off_the_screen():
    m = _n_options(4)
    _drawn(m)
    assert m.card_gap() < menu_mod.CARD_GAP
    assert m._option_rects[-1].bottom < SCREEN_HEIGHT - 60      # the hint row still fits below the last card


def test_clicking_the_last_of_four_cards_picks_it():
    m = _n_options(4)
    _drawn(m)
    m.update(0, [pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=m._option_rects[3].center, button=1)])
    assert m.result == 3
