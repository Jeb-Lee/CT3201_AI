"""The HUD: layout, animation logic, event toasts, damage flash, fade, tooltips.

The HUD only reads the session and draws, so these tests build real sessions,
poke the state they need (health, occupants, fire) and check what the HUD does
with it. Layout is measured with the real fonts.
"""
import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

import hud as hud_mod
import levels
import main as game
from entities.victim import STATE_DEAD, STATE_FOLLOWING, STATE_IDLE, STATE_SAVED
from hud import Hud, Toast, fire_zone, health_colour
from settings import HEALTH_MAX, SCORE_PER_SURVIVOR, SCREEN_HEIGHT, SCREEN_WIDTH

pygame.init()
SCREEN = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))


def session(spectate=False, stage=0):
    return game.GameSession(levels.get(stage), spectate=spectate,
                            agent_visual="robot", stage_index=stage)


def settled(s, seconds=1.0):
    """The HUD after its slide-in has finished and the banner has faded."""
    s.hud.t = 0.0
    s.hud.update(0.0, s)
    s.hud.toasts.clear()
    s.hud.t = seconds
    return s.hud


# ------------------------------------------------------------------ layout
@pytest.mark.parametrize("spectate", [False, True], ids=["race", "watch"])
@pytest.mark.parametrize("stage", range(levels.STAGE_COUNT))
def test_panels_stay_on_screen_and_never_overlap(stage, spectate):
    s = session(spectate, stage)
    rects = s.hud.layout(s)
    screen = pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
    for name, r in rects.items():
        assert screen.contains(r), (name, r)
    names = list(rects)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert not rects[a].colliderect(rects[b]), (a, b, rects[a], rects[b])


def test_race_has_two_cards_and_watch_has_one():
    assert set(session(False).hud.layout(session(False))) >= {"you", "ai", "fire", "strip"}
    w = session(True)
    assert "you" not in w.hud.layout(w) and "ai" in w.hud.layout(w)


def test_the_two_cards_mirror_each_other():
    s = session(False)
    r = s.hud.layout(s)
    assert r["you"].left == SCREEN_WIDTH - r["ai"].right
    assert r["fire"].centerx == SCREEN_WIDTH // 2 == r["strip"].centerx


def test_every_stage_draws_without_error_in_both_modes():
    for stage in range(levels.STAGE_COUNT):
        for spectate in (False, True):
            s = session(spectate, stage)
            s.hud.update(0.016, s)
            s.hud.draw(SCREEN, s)


# --------------------------------------------------------------- pure helpers
def test_health_colour_runs_green_to_red():
    assert health_colour(1.0) == hud_mod.HEALTH_BAR_COLOR_FULL
    assert health_colour(0.5) == hud_mod.HEALTH_BAR_COLOR_MID
    assert health_colour(0.0) == hud_mod.HEALTH_BAR_FILL_COLOR
    assert health_colour(5.0) == health_colour(1.0) and health_colour(-1) == health_colour(0)


class _Fire:
    def __init__(self, left, on_fire=False):
        self.seconds_to_exit_fire, self.exit_on_fire = left, on_fire


@pytest.mark.parametrize("left,on_fire,zone", [(90, False, 0), (35.0, False, 0), (34.9, False, 1),
                                                (15.0, False, 1), (14.9, False, 2), (0, False, 2),
                                                (0, True, 3)])
def test_fire_zone_thresholds(left, on_fire, zone):
    assert fire_zone(_Fire(left, on_fire)) == zone


# ---------------------------------------------------- health ghost + hit flash
def test_damage_leaves_a_ghost_that_holds_then_drains():
    h = Hud()
    h._track("you", 100.0, 0, 0.016)
    h._track("you", 60.0, 0, 0.016)
    r = h._r["you"]
    assert r["hit"] > 0 and r["ghost"] == 100.0           # the pale segment starts at what you had
    h._track("you", 60.0, 0, hud_mod.GHOST_HOLD / 2)
    assert h._r["you"]["ghost"] == 100.0                  # still holding
    for _ in range(200):
        h._track("you", 60.0, 0, 0.016)
    assert h._r["you"]["ghost"] == 60.0 and h._r["you"]["hit"] == 0.0   # drained to the real value


def test_healing_does_not_leave_a_ghost():
    h = Hud()
    h._track("you", 50.0, 0, 0.016)
    h._track("you", 80.0, 0, 0.016)
    assert h._r["you"]["ghost"] == 80.0 and h._r["you"]["hit"] == 0


# --------------------------------------------------------------- score pop
def test_a_rescue_pops_the_score_and_floats_a_plus():
    h = Hud()
    h._track("you", 100, 0, 0.016)
    h._track("you", 100, SCORE_PER_SURVIVOR, 0.016)
    assert h._r["you"]["pop"] > 0
    assert [(w, t) for w, t, _ in h.floats] == [("you", f"+{SCORE_PER_SURVIVOR}")]


def test_damage_shaving_the_score_does_not_pop_or_float():
    """Damage lowers the score a point at a time and would spam "-1"s."""
    h = Hud()
    h._track("you", 100, 200, 0.016)
    for score in (199, 198, 197):
        h._track("you", 100, score, 0.016)
    assert h._r["you"]["pop"] == 0 and h.floats == []


def test_floats_expire():
    h = Hud()
    h.floats.append(["you", "+100", 0.0])
    s = session()
    for _ in range(80):
        h.update(0.016, s)
    assert h.floats == []


# ---------------------------------------------------------- damage vignette
def test_vignette_flashes_on_a_hit_then_fades():
    s = session()
    h = s.hud
    h.update(0.016, s)
    assert h.vignette_strength(s) == 0.0
    s.player.health = 70.0
    h.update(0.016, s)
    assert 0.5 < h.vignette_strength(s) <= 0.7
    for _ in range(60):
        h.update(0.016, s)
    assert h.vignette_strength(s) == 0.0


def test_vignette_pulses_while_nearly_dead_and_stops_when_down():
    s = session()
    h = s.hud
    s.player.health = 15.0
    h.update(0.016, s)
    seen = set()
    for _ in range(90):
        h.t += 0.05
        seen.add(round(h.vignette_strength(s), 2))
    assert min(seen) >= 0.25 and max(seen) > min(seen)        # never off, and it breathes
    s.player.health = 0.0
    assert h.vignette_strength(s) == 0.0                      # dead: nothing more to warn about


def test_no_vignette_when_watching_the_ai():
    s = session(True)
    s.agent.health = 10.0
    s.hud.update(0.016, s)
    # Even with a hit flash and near-death health recorded for "you" -- which a
    # watch run never tracks -- nothing is drawn: there is no Pete to warn.
    s.hud._r["you"].update(h=10.0, ghost=10.0, hit=hud_mod.HIT)
    assert s.hud.vignette_strength(s) == 0.0


# ------------------------------------------------------------------- toasts
def test_the_first_frame_shows_a_stage_banner():
    s = session()
    s.hud.update(0.016, s)
    banners = [t for t in s.hud.toasts if t.big]
    assert len(banners) == 1
    assert "GROUND FLOOR" in banners[0].text and "racing you" in banners[0].sub
    w = session(True)
    w.hud.update(0.016, w)
    assert "Watching" in w.hud.toasts[0].sub


def _texts(h):
    return [t.text for t in h.toasts if not t.big]


def test_rescue_key_loss_and_death_each_make_a_toast():
    s = session()
    h = settled(s)
    h.update(0.0, s)                                          # take the baseline snapshot
    s.player_stats.victims_saved = 1
    s.agent_stats.victims_saved = 2
    s.hazards.doors.key_collected = True
    s.victims[0].state = STATE_DEAD
    s.player.health = 0.0
    h.update(0.016, s)
    texts = _texts(h)
    assert any(f"+{SCORE_PER_SURVIVOR}" in t and "Pete" in t for t in texts)
    assert any(f"+{2 * SCORE_PER_SURVIVOR}" in t and "2 occupants" in t for t in texts)
    assert any("Key collected" in t for t in texts)
    assert any("Occupant lost" in t for t in texts)
    assert any("Pete is down" in t for t in texts)


def test_fire_warnings_come_once_each_and_only_getting_worse():
    s = session()
    h = settled(s)
    h.update(0.0, s)
    fire = s.hazards.fire
    total = fire.seconds_to_exit_total
    got = []
    for left in (total, 30.0, 30.0, 10.0, 10.0):              # calm -> warn -> (repeat) -> hot -> (repeat)
        fire.elapsed = total - left
        h.update(0.016, s)
        got.append(len(_texts(h)))
    assert got == [0, 1, 1, 2, 2]
    fire.elapsed = total - 30                                 # danger -> warning again: the estimate
    h.update(0.016, s)                                        # improved, so it must not re-alert
    assert len(_texts(h)) == 2
    fire.burning.add(s.tilemap.exit_cell)
    h.update(0.016, s)
    assert len(_texts(h)) == 2                                # the clock plate is the banner: no third toast
    assert fire_zone(fire) == 3
    fire.elapsed = total - 50                                 # ...nor should it after the fire clears
    fire.burning.discard(s.tilemap.exit_cell)
    n = len(_texts(h))
    h.update(0.016, s)
    assert len(_texts(h)) == n


def test_toasts_fade_in_and_out_then_expire():
    t = Toast("x", (1, 2, 3))
    assert t.alpha == 0.0
    t.age = 1.0
    assert t.alpha == 1.0
    t.age = t.life - 0.1
    assert 0 < t.alpha < 1
    s = session()
    s.hud.update(0.016, s)
    for _ in range(300):
        s.hud.update(0.016, s)
    assert s.hud.toasts == []


def test_only_the_newest_three_pills_are_drawn():
    s = session()
    h = settled(s)
    for i in range(6):
        h._toast(f"message {i}", (255, 255, 255))
    h.draw(SCREEN, s)                                          # must not raise
    assert len([t for t in h.toasts if not t.big]) == 6        # kept, just not all shown
    pills = [t for t in h.toasts if not t.big][-hud_mod.MAX_TOASTS:]
    assert [t.text for t in pills] == ["message 3", "message 4", "message 5"]


# ------------------------------------------------------- slide-in and fade
def test_panels_slide_in_from_off_screen_at_stage_start():
    s = session()
    h = s.hud
    h.t = 0.0
    h.draw(SCREEN, s)
    assert all(r.bottom <= 0 for r, k in h.hot if k in ("you", "ai", "fire"))
    assert next(r for r, k in h.hot if k == "occupants").top >= SCREEN_HEIGHT - 60 + 1
    h.t = 5.0
    h.draw(SCREEN, s)
    assert next(r for r, k in h.hot if k == "you").top == hud_mod.MARGIN


def test_a_panel_fades_when_the_rescuer_is_behind_it():
    s = session()
    h = settled(s)

    def brightness(behind):
        s._anchor_behind = lambda rect: behind
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surf.fill((0, 0, 0))
        h.draw(surf, s)
        r = h.layout(s)["you"]
        return sum(sum(surf.get_at((x, y))[:3]) for x in range(r.x, r.right, 3)
                   for y in range(r.y, r.bottom, 3))

    assert brightness(True) < 0.5 * brightness(False)


# ---------------------------------------------------------------- portraits
def test_dead_and_finished_portraits_draw():
    s = session()
    h = settled(s)
    s.player.health = 0.0
    s.agent_stats.finish("exit")
    h.draw(SCREEN, s)                                          # veil + cross, and the exit tick


def test_the_drone_skin_gets_a_drawn_portrait_not_a_missing_sprite():
    s = game.GameSession(levels.get(0), spectate=False, agent_visual="drone")
    h = settled(s)
    h.draw(SCREEN, s)                                          # the drawn portrait must not raise
    from portraits import portrait_image
    assert portrait_image("drone", 56) is None                 # no sprite art: it is drawn instead


# ----------------------------------------------------------------- tooltips
def test_every_panel_is_hoverable_and_hover_names_it():
    s = session()
    h = settled(s)
    h.draw(SCREEN, s)
    kinds = {k for _, k in h.hot}
    assert {"you", "ai", "fire", "occupants"} <= kinds
    for rect, kind in h.hot:
        assert h.hovered(rect.center) == kind
    assert h.hovered(None) is None and h.hovered((SCREEN_WIDTH // 2, 300)) is None


def test_the_key_is_only_hoverable_when_the_stage_has_a_door():
    s = session()
    s.hazards.doors.enabled = False
    h = settled(s)
    h.draw(SCREEN, s)
    assert "key" not in {k for _, k in h.hot}


def test_score_tooltip_reproduces_the_results_breakdown():
    s = session()
    s.player_stats.victims_saved = 2
    s.player_stats.damage_taken = 30
    s.player_stats.finish("exit")
    rows = s.hud.tooltip_rows("you", s)
    body = {r.text: r.value for r in rows}
    for label, pts in s.player_stats.score_breakdown():
        assert body[label] == f"{pts:+d}"
    assert rows[-1].text.startswith("Total") and rows[-1].value == str(s.player_stats.score)


def test_the_occupant_legend_covers_all_four_states():
    rows = session().hud.tooltip_rows("occupants", session())
    text = " ".join(r.text for r in rows)
    for word in ("Out", "Escorted", "Waiting", "Lost"):
        assert word in text
    assert sum(1 for r in rows if r.marker) == 4


@pytest.mark.parametrize("kind", ["you", "ai", "fire", "occupants", "key"])
def test_tooltips_have_content_and_stay_on_screen(kind):
    s = session()
    h = settled(s)
    assert h.tooltip_rows(kind, s)
    h.draw(SCREEN, s)
    for corner in ((0, 0), (SCREEN_WIDTH - 1, 0), (0, SCREEN_HEIGHT - 1),
                   (SCREEN_WIDTH - 1, SCREEN_HEIGHT - 1)):
        h.hot = [(pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT), kind)]
        tip = h._draw_hover(SCREEN, s, corner)
        assert SCREEN.get_rect().contains(tip), (kind, corner, tip)   # clamped inside the window


def test_the_exit_on_fire_tooltip_replaces_the_estimate():
    s = session()
    s.hazards.fire.burning.add(s.tilemap.exit_cell)
    rows = s.hud.tooltip_rows("fire", s)
    assert rows[0].text == "EXIT ON FIRE"


# ------------------------------------------------------- state, restart, cost
def test_reset_clears_all_animation_state_and_replays_the_intro():
    s = session()
    h = s.hud
    h.update(0.016, s)
    h._toast("x", (1, 1, 1))
    h.floats.append(["you", "+100", 0.0])
    h._r["you"]["hit"] = 1.0
    s.reset()
    assert h.toasts == [] and h.floats == [] and h.t == 0.0 and h._r["you"]["h"] is None
    h.update(0.016, s)
    assert any(t.big for t in h.toasts)                        # the banner again


def test_the_hud_never_changes_the_game():
    """update()/draw() only read the session."""
    s = session()
    before = (s.player.health, s.agent.health, s.player_stats.score, s.agent_stats.score,
              [v.state for v in s.victims], s.hazards.fire.elapsed, len(s.hazards.fire.burning))
    for _ in range(30):
        s.hud.update(0.016, s)
        s.hud.draw(SCREEN, s, mouse=(300, 40))
    after = (s.player.health, s.agent.health, s.player_stats.score, s.agent_stats.score,
             [v.state for v in s.victims], s.hazards.fire.elapsed, len(s.hazards.fire.burning))
    assert before == after


def test_a_real_run_with_the_hud_drawing_every_frame():
    s = session(True)
    keys = pygame.key.get_pressed()
    for i in range(60 * 12):
        s.update(1 / 60, keys)
        if i % 6 == 0:
            s.draw(SCREEN)
    assert s.hud.t > 0


def test_hud_drawing_is_cheap():
    """Measured ~1ms a frame; a 60fps frame is 16.7ms. Generous so it isn't flaky."""
    s = session()
    h = settled(s)
    h.draw(SCREEN, s)
    t0 = time.perf_counter()
    for _ in range(100):
        h.update(1 / 60, s)
        h.draw(SCREEN, s)
    assert (time.perf_counter() - t0) / 100 < 0.010


def test_a_bottom_edge_tooltip_opens_above_so_it_does_not_cover_what_it_describes():
    s = session()
    h = settled(s)
    h.draw(SCREEN, s)
    strip_part = next(r for r, k in h.hot if k == "occupants")
    tip = h._draw_hover(SCREEN, s, strip_part.center)
    assert tip.bottom <= strip_part.top                         # entirely above the strip
    card = next(r for r, k in h.hot if k == "you")
    tip = h._draw_hover(SCREEN, s, card.center)
    assert tip.top >= card.bottom                               # top-edge elements: below the element,
                                                                # so a card's score is not hidden by its tooltip
