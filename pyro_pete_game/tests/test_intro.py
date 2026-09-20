"""The title screen: the lockup fades in over the top, the prompt sits at the foot
(clear of Pete and the robot at the door), and Enter still moves things along."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

import intro
from settings import SCREEN_WIDTH, SCREEN_HEIGHT, RESULTS_ACCENT_COLOR

pygame.init()
pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
GOLD = RESULTS_ACCENT_COLOR[:3]
ENTER = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)


@pytest.fixture(scope="module")
def scene():
    return intro.IntroScene()


def _held(scene, held_t=5.0, blink_t=0.0):
    scene._phase, scene.t = "held", intro.T6
    scene.update(0, [])
    scene.held_t, scene.blink_t = held_t, blink_t
    return scene


def _frame(scene, **hide):
    """The scene as drawn, optionally with pieces switched off."""
    saved = {}
    for name in hide:
        saved[name] = getattr(scene, name)
        setattr(scene, name, lambda surface: None)
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    try:
        scene.draw(surf)
    finally:
        for name, fn in saved.items():
            setattr(scene, name, fn)
    return surf


def _region(surf, rect):
    return pygame.image.tobytes(surf.subsurface(rect), "RGB")


def _gold_columns(surf, rect):
    return [x for x in range(rect.left, rect.right)
            if any(tuple(surf.get_at((x, y))[:3]) == GOLD for y in range(rect.top, rect.bottom))]


TOP = pygame.Rect(0, 0, SCREEN_WIDTH, 120)
BOTTOM = pygame.Rect(0, SCREEN_HEIGHT - 110, SCREEN_WIDTH, 110)
DOOR = pygame.Rect(380, 280, 200, 110)          # where Pete and the robot stand


# --- the flow is unchanged --------------------------------------------------------------
def test_enter_skips_to_the_held_frame_then_finishes():
    s = intro.IntroScene()
    assert not s.finished and s._phase == "playing"
    s.update(0.1, [ENTER])
    assert s._phase == "held" and not s.finished
    s.update(0.1, [ENTER])
    assert s.finished


def test_the_held_clock_only_runs_on_the_held_frame():
    s = intro.IntroScene()
    s.update(1.0, [])
    assert s.held_t == 0.0
    s.update(0.0, [ENTER])
    s.update(0.5, [])
    s.update(0.5, [])
    assert s.held_t == pytest.approx(1.0)


# --- the title lockup ---------------------------------------------------------------------
def test_the_title_fades_in_from_nothing(scene):
    _held(scene, held_t=0.0)
    with_lockup, without = _frame(scene), _frame(scene, _draw_lockup=1)
    assert _region(with_lockup, TOP) == _region(without, TOP)            # nothing yet
    _held(scene, held_t=intro.LOCKUP_FADE * 0.3)
    partial = _frame(scene)
    assert _region(partial, TOP) != _region(without, TOP)
    _held(scene, held_t=intro.LOCKUP_FADE)
    full = _frame(scene)
    assert len(_gold_columns(full, TOP)) > 100                              # the gold title
    assert len(_gold_columns(partial, TOP)) < len(_gold_columns(full, TOP))


def test_the_title_is_centred_and_fully_on_screen(scene):
    _held(scene)
    cols = _gold_columns(_frame(scene), pygame.Rect(0, 0, SCREEN_WIDTH, 100))
    assert abs((cols[0] + cols[-1]) / 2 - SCREEN_WIDTH / 2) <= 4
    assert cols[0] > 20 and cols[-1] < SCREEN_WIDTH - 20


def test_the_title_reads_against_a_dark_band(scene):
    """Gold on the daytime sky or brick would wash out: the band behind it is dark."""
    _held(scene)
    f = _frame(scene)
    for x in (10, 100, 860, 950):
        assert sum(f.get_at((x, 40))[:3]) < 150


def test_the_tagline_is_letter_spaced():
    font = intro.ui_font("body", bold=True)
    plain = font.size("ABC")[0]
    spaced = intro.IntroScene._spaced(font, "ABC", (255, 255, 255), 5).get_width()
    assert spaced >= plain + 10 - 3           # two gaps of 5 (kerning aside)


def test_the_tagline_is_drawn_tracked_out_on_screen(scene):
    _held(scene)
    f = _frame(scene)
    light = (232, 226, 214)
    xs = [x for x in range(SCREEN_WIDTH)
          if any(max(abs(a - b) for a, b in zip(f.get_at((x, y))[:3], light)) < 12 for y in range(105, 140))]
    plain = intro.ui_font("body", bold=True).size(intro.TAGLINE)[0]
    gaps = (len(intro.TAGLINE) - 1) * 5
    assert xs[-1] - xs[0] >= plain + gaps * 0.8


# --- the prompt ------------------------------------------------------------------------------
def test_the_prompt_is_at_the_foot_and_never_over_the_characters(scene):
    _held(scene)
    with_prompt, without = _frame(scene), _frame(scene, _draw_prompt=1)
    assert _region(with_prompt, DOOR) == _region(without, DOOR)          # Pete and the robot are clear
    assert _region(with_prompt, BOTTOM) != _region(without, BOTTOM)      # and it is at the bottom
    centre = pygame.Rect(0, 150, SCREEN_WIDTH, SCREEN_HEIGHT - 150 - 110)
    assert _region(with_prompt, centre) == _region(without, centre)      # nowhere else at all


def test_the_prompt_is_centred(scene):
    _held(scene)
    a, b = _frame(scene), _frame(scene, _draw_prompt=1)
    xs = [x for x in range(SCREEN_WIDTH)
          if any(a.get_at((x, y)) != b.get_at((x, y)) for y in range(SCREEN_HEIGHT - 90, SCREEN_HEIGHT - 20))]
    assert abs((xs[0] + xs[-1]) / 2 - SCREEN_WIDTH / 2) <= 6


def test_the_prompt_waits_a_moment_then_stays_up_without_blinking(scene):
    _held(scene, held_t=intro.PROMPT_DELAY * 0.5)
    early = _frame(scene)
    assert _region(early, BOTTOM) == _region(_frame(scene, _draw_prompt=1), BOTTOM)
    for phase in (0.0, 0.5, 0.9, 1.1, 1.19):          # the old prompt was off a third of the time
        _held(scene, held_t=5.0, blink_t=phase)
        assert _region(_frame(scene), BOTTOM) != _region(_frame(scene, _draw_prompt=1), BOTTOM), phase


def test_the_pill_edge_pulses(scene):
    _held(scene, blink_t=0.0)
    a = _frame(scene)
    _held(scene, blink_t=0.5)
    b = _frame(scene)
    assert _region(a, BOTTOM) != _region(b, BOTTOM)


def test_fonts_used_by_the_title_screen_come_from_the_shared_scale(scene):
    _held(scene)
    _frame(scene)
    f = scene._fonts()
    assert f["display"].get_height() == intro.ui_font("display").get_height()
    assert f["label"].get_height() == intro.ui_font("body").get_height()


# --- the skip hint ------------------------------------------------------------------------------
def test_a_skip_hint_appears_while_the_animation_plays_and_not_at_first_or_once_held(scene):
    corner = pygame.Rect(SCREEN_WIDTH - 200, SCREEN_HEIGHT - 70, 200, 70)
    scene._phase = "playing"
    scene.t = 3.0
    scene.update(0, [])
    scene.t = 0.2
    assert _region(_frame(scene), corner) == _region(_frame(scene, _draw_skip_hint=1), corner)   # too early
    scene.t = 3.0
    scene.update(0, [])
    scene.t = 3.0
    assert _region(_frame(scene), corner) != _region(_frame(scene, _draw_skip_hint=1), corner)
    _held(scene)
    assert _region(_frame(scene), corner) == _region(_frame(scene, _draw_skip_hint=1), corner)   # held: pill instead
