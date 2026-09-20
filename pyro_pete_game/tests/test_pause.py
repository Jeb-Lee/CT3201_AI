"""The pause screen, the mute notice, and the real game handling P and M.

Layout is checked with the real fonts and real sessions; the last test drives the
actual main() with key presses in a subprocess.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

import hud_icons
import levels
import main as game
import notice
import pause
from audio import AudioManager
from pause import PauseScreen, candidate_rects, characters_on_screen, choose_rect, entity_box
from settings import SCREEN_HEIGHT, SCREEN_WIDTH

pygame.init()
SCREEN = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
_GAME_DIR = Path(__file__).resolve().parent.parent


class FakeAudio:
    """The three states a machine can be in."""
    def __init__(self, enabled=True, muted=False):
        self.enabled, self.muted = enabled, muted


def session(spectate=False, stage=0, at=None):
    s = game.GameSession(levels.get(stage), spectate=spectate, agent_visual="robot", stage_index=stage)
    if at is not None:
        s.player.x, s.player.y = at
        s.camera.update(*at)
    return s


def blank():
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    surf.fill((0, 0, 0))
    return surf


# ============================================================ where the panel goes
def _map_positions(s, n=5):
    """A grid of world positions covering the whole map, corners included."""
    tm = s.tilemap
    return [(round(tm.pixel_width * (0.06 + 0.88 * i / (n - 1))),
             round(tm.pixel_height * (0.08 + 0.84 * j / (n - 1)))) for i in range(n) for j in range(n)]


@pytest.mark.parametrize("stage", [0, 4, 9])
def test_the_panel_never_covers_the_character_wherever_he_stands(stage):
    """The bug this replaces: "PAUSED" at the screen centre, with the camera
    putting the character at the screen centre."""
    ps = PauseScreen()
    s = session(stage=stage)
    for at in _map_positions(s):
        s.player.x, s.player.y = at
        s.camera.update(*at)
        rect = ps.place(s, FakeAudio())
        assert not rect.colliderect(entity_box(s, s.player)), (at, rect, entity_box(s, s.player))


def test_the_panel_stays_between_the_fire_clock_and_the_mission_strip():
    ps = PauseScreen()
    for stage in range(levels.STAGE_COUNT):
        for spectate in (False, True):
            s = session(spectate, stage)
            rect = ps.place(s, FakeAudio())
            assert SCREEN.get_rect().contains(rect) and pause.REGION.contains(rect)
            for name, hud_rect in s.hud.layout(s).items():
                assert not rect.colliderect(hud_rect), (stage, spectate, name)


def test_no_spot_the_panel_can_take_touches_the_hud():
    """Every spot, not just the one chosen today -- and measured against the HUD's
    own layout rather than pause's REGION, which would agree with itself."""
    ps = PauseScreen()
    for stage in range(levels.STAGE_COUNT):
        for spectate in (False, True):
            s = session(spectate, stage)
            hud_rects = list(s.hud.layout(s).values())
            top_of_free = max(r.bottom for k, r in s.hud.layout(s).items() if k != "strip")
            bottom_of_free = s.hud.layout(s)["strip"].top
            assert pause.REGION.top >= top_of_free and pause.REGION.bottom <= bottom_of_free
            for r in candidate_rects(ps.size(s, FakeAudio(enabled=False))):
                assert not any(r.colliderect(h) for h in hud_rects), (stage, spectate, r)


def test_it_is_centred_when_nothing_is_in_the_way():
    s = session(at=(96.0, 96.0))                         # spawn corner: the camera cannot centre him
    rect = PauseScreen().place(s, FakeAudio())
    assert abs(rect.centerx - SCREEN_WIDTH // 2) <= 1


def test_mid_map_it_moves_to_the_side_instead_of_covering_him():
    s = session(at=(672.0, 416.0))                       # the camera centres him here
    box = entity_box(s, s.player)
    assert box.collidepoint(SCREEN_WIDTH // 2, box.centery)          # he really is in the middle
    rect = PauseScreen().place(s, FakeAudio())
    assert abs(rect.centerx - SCREEN_WIDTH // 2) > 100 or abs(rect.centery - box.centery) > 100
    assert not rect.colliderect(box)


def _character_at(point):
    """A character-sized box (72x106, as entity_box makes) centred on `point`."""
    r = pygame.Rect(0, 0, 72, 106)
    r.center = point
    return r


def test_it_avoids_the_other_rescuer_too_when_there_is_room():
    size = (340, 260)
    cands = candidate_rects(size)
    a, b = _character_at(cands[0].center), _character_at(cands[1].center)   # two characters, in the best spots
    chosen = choose_rect(size, [a, b])
    assert not chosen.colliderect(a) and not chosen.colliderect(b)
    assert chosen != cands[0] and chosen != cands[1]


def test_when_it_cannot_avoid_both_it_still_avoids_the_one_being_watched():
    size = (340, 260)
    cands = candidate_rects(size)
    important = _character_at(cands[0].center)
    others = [_character_at(c.center) for c in cands[1:]]                   # a character at every other spot
    chosen = choose_rect(size, [important] + others)
    assert not chosen.colliderect(important)
    assert any(chosen.colliderect(o) for o in others)                       # it could not dodge them all


def test_every_candidate_spot_fits_the_region():
    for size in ((340, 260), (400, 300)):
        for r in candidate_rects(size):
            assert pause.REGION.contains(r)


def test_boxes_follow_the_camera_and_the_rescuer_being_watched():
    s = session(spectate=True)
    boxes = characters_on_screen(s)
    assert len(boxes) == 1 and boxes[0] == entity_box(s, s.agent)      # watching: only the AI
    r = session()
    assert len(characters_on_screen(r)) == 2                           # racing: both
    r.player.health = 0.0
    assert r.player.is_dead
    assert characters_on_screen(r) == [entity_box(r, r.agent)]         # Pete is down: the camera follows the AI


# =============================================================== what it says
def test_the_controls_listed_match_the_mode():
    ps = PauseScreen()
    race = [c.keys for c in ps.controls(session(), FakeAudio())]
    watch = [c.keys for c in ps.controls(session(spectate=True), FakeAudio())]
    assert race == ["WASD", "P", "R", "M", "Esc"]
    assert watch == ["P", "R", "M", "Esc"]                             # nothing to steer when watching


def test_every_key_it_lists_is_one_the_game_really_handles():
    src = (_GAME_DIR / "main.py").read_text(encoding="utf-8")
    for token in ("pygame.K_p", "pygame.K_r", "pygame.K_m", "pygame.K_ESCAPE"):
        assert token in src, token
    player_src = (_GAME_DIR / "entities" / "player.py").read_text(encoding="utf-8")
    for token in ("K_w", "K_a", "K_s", "K_d", "K_UP", "K_DOWN", "K_LEFT", "K_RIGHT"):
        assert token in player_src, token                              # "WASD (or the arrow keys)"


@pytest.mark.parametrize("audio,text", [(FakeAudio(), "on"), (FakeAudio(muted=True), "off"),
                                        (FakeAudio(enabled=False), "no audio device")])
def test_the_sound_row_tells_the_truth_about_the_sound(audio, text):
    rows = PauseScreen().controls(session(), audio)
    sound = next(c for c in rows if c.keys == "M")
    assert sound.state[0] == text


def test_the_subtitle_names_the_stage_and_says_when_watching():
    ps = PauseScreen()
    assert ps.subtitle(session()) == "Stage 1/10  ·  Ground Floor"
    assert ps.subtitle(session(spectate=True)).endswith("watching the AI")


def test_the_panel_fits_for_every_stage_name_in_both_modes():
    ps = PauseScreen()
    for stage in range(levels.STAGE_COUNT):
        for spectate in (False, True):
            w, h = ps.size(session(spectate, stage), FakeAudio(enabled=False))    # the widest state text
            assert w <= pause.REGION.w and h <= pause.REGION.h


# ================================================================== drawing
def test_drawing_dims_the_frame_and_returns_the_panel():
    s = session()
    ps = PauseScreen()
    for audio in (FakeAudio(), FakeAudio(muted=True), FakeAudio(enabled=False)):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surf.fill((200, 200, 200))
        rect = ps.draw(surf, s, audio)
        assert rect == ps.place(s, audio)
        corner = surf.get_at((3, SCREEN_HEIGHT // 2))[:3]
        assert 60 < max(corner) < 130                                      # dimmed a lot (200 -> ~90), not blacked out
        assert surf.get_at((rect.centerx, rect.top + 40))[:3] != corner    # and a panel is on top of it


def test_the_panel_has_a_gold_edge_like_the_results_panel():
    from settings import RESULTS_ACCENT_COLOR
    surf = blank()
    rect = PauseScreen().draw(surf, session(), FakeAudio())
    edge_px = surf.get_at((rect.centerx, rect.top))[:3]
    assert max(abs(a - b) for a, b in zip(edge_px, RESULTS_ACCENT_COLOR)) < 40


# ============================================================ mute notice
def test_notices_appear_fade_and_expire():
    n = notice.Notices()
    n.show("Sound off")
    assert n.items[0].alpha == 0.0                                     # about to fade in
    n.update(0.5)
    assert n.items[0].alpha == 1.0
    n.update(notice.LIFE - 0.5 - 0.1)
    assert 0 < n.items[0].alpha < 1.0                                  # fading out
    n.update(1.0)
    assert n.items == []


def test_showing_the_same_message_again_replaces_it_instead_of_stacking():
    n = notice.Notices()
    n.show("Sound off")
    n.update(1.0)
    n.show("Sound off")
    assert len(n.items) == 1 and n.items[0].age == 0.0


@pytest.mark.parametrize("audio,text", [(FakeAudio(muted=True), "Sound off"), (FakeAudio(), "Sound on"),
                                        (FakeAudio(enabled=False), "No audio device")])
def test_the_message_says_what_m_did(audio, text):
    n = notice.Notices()
    n.sound_changed(audio)
    assert [i.text for i in n.items] == [text]


def test_the_muted_chip_shows_only_while_muted():
    n = notice.Notices()
    chip = notice.chip_rect()

    def lit(audio):
        surf = blank()
        n.draw(surf, audio)
        return sum(1 for x in range(chip.left, chip.right) for y in range(chip.top, chip.bottom)
                   if surf.get_at((x, y))[:3] != (0, 0, 0))
    assert lit(FakeAudio(muted=True)) > 200
    assert lit(FakeAudio()) == 0
    assert lit(FakeAudio(enabled=False)) == 0                          # nothing to report without a device


def test_the_notice_and_the_chip_never_touch_the_mission_strip_or_the_hud():
    widest_text = max(notice.Notices().font.size(t)[0] + 44 for t in ("Sound off", "Sound on", "No audio device"))
    zone = [notice.chip_rect(), notice.pill_rect(widest_text)]
    for stage in range(levels.STAGE_COUNT):
        for spectate in (False, True):
            s = session(spectate, stage)
            for name, rect in s.hud.layout(s).items():
                for z in zone:
                    assert not rect.colliderect(z), (stage, spectate, name, rect, z)
    for z in zone:
        assert SCREEN.get_rect().contains(z)


def test_a_message_is_drawn_where_pill_rect_says():
    n = notice.Notices()
    n.show("Sound on")
    n.update(0.5)
    surf = blank()
    n.draw(surf, FakeAudio())
    width = n.font.size("Sound on")[0] + 44
    r = notice.pill_rect(width)
    assert any(surf.get_at((x, r.centery))[:3] != (0, 0, 0) for x in range(r.left, r.right))
    outside = pygame.Rect(0, 0, SCREEN_WIDTH, r.top - 4)
    assert all(surf.get_at((x, y))[:3] == (0, 0, 0) for x in range(0, SCREEN_WIDTH, 40) for y in range(0, outside.h, 40))


def test_the_real_audio_manager_reports_muted_honestly():
    audio = AudioManager()
    if audio.enabled:
        assert not audio.muted
        assert audio.toggle_mute() is True and audio.muted
        assert audio.toggle_mute() is False and not audio.muted
    else:
        # no device: there is no switch, so it must not claim to be muted
        assert not audio.muted


def test_muted_is_false_without_an_audio_device_whatever_the_volume_says():
    """Built by hand so it does not depend on this machine having sound: with no
    device there is no switch, and "muted" would be a claim about nothing."""
    a = AudioManager.__new__(AudioManager)
    a.enabled, a.volume = False, 0.0
    assert a.muted is False
    a.enabled, a.volume = True, 0.0
    assert a.muted is True
    a.volume = 0.55
    assert a.muted is False


# ================================================================== icons
def test_the_speaker_shows_a_slash_only_when_muted():
    def colours(muted):
        surf = pygame.Surface((60, 60))
        surf.fill((0, 0, 0))
        hud_icons.speaker_icon(surf, 30, 30, 40, (200, 200, 200), muted=muted)
        return {surf.get_at((x, y))[:3] for x in range(60) for y in range(60)}
    assert (230, 80, 70) in colours(True)
    assert (230, 80, 70) not in colours(False)
    assert len(colours(False)) > 1


def test_key_chips_grow_with_their_label_and_have_a_minimum():
    font = pygame.font.SysFont(None, 20)
    surf = pygame.Surface((200, 60))
    widths = [hud_icons.key_chip(surf, 4, 4, k, font).width for k in ("P", "Esc", "WASD")]
    assert widths == sorted(widths) and widths[0] >= 28 and widths[2] > widths[0]


def test_the_pause_icon_is_two_bars():
    surf = pygame.Surface((40, 40))
    surf.fill((0, 0, 0))
    hud_icons.pause_icon(surf, 20, 20, 30, (255, 255, 255))
    row = [surf.get_at((x, 20))[:3] != (0, 0, 0) for x in range(40)]
    edges = sum(1 for a, b in zip(row, row[1:]) if a != b)
    assert edges == 4                                                  # dark|bar|dark|bar|dark


# ============================================================ wiring + end to end
def test_main_wires_the_pause_panel_and_the_notices():
    src = (_GAME_DIR / "main.py").read_text(encoding="utf-8")
    assert "_draw_pause_overlay" not in src
    assert "pause_screen.draw(screen, session, audio)" in src
    m = src.index("audio.toggle_mute()")
    assert "notices.sound_changed(audio)" in src[m:m + 120]            # M says what it did
    assert src.index("notices.draw(screen, audio)") < src.index("pygame.display.flip()")
    assert "notices.update(dt)" in src


def test_the_real_game_pauses_on_p_and_answers_m_on_every_screen():
    """Drives the actual main(): skip the intro, Play vs AI, robot, then
    M (mute), P (pause), M (unmute, while paused), P (resume), M (mute)."""
    run = subprocess.run([sys.executable, str(Path(__file__).with_name("drive_main_keys.py"))],
                         capture_output=True, text=True, timeout=180, cwd=str(_GAME_DIR))
    line = next((l for l in run.stdout.splitlines() if l.startswith("RESULT ")), None)
    assert line, run.stdout[-500:] + run.stderr[-500:]
    r = json.loads(line[len("RESULT "):])

    # paused from the first P (frame 130) to just before the second (170) -- and nowhere else
    assert r["pause_frames"] == list(range(130, 170))

    audio_on = [t for _, t in r["notices"]] == ["Sound off", "Sound on", "Sound off"]
    no_device = [t for _, t in r["notices"]] == ["No audio device"] * 3
    assert audio_on or no_device, r["notices"]                          # one answer per M, in order
    assert [f for f, _ in r["notices"]] == [100, 150, 190]              # including the M pressed while paused

    lit = r["corner_lit"]
    if audio_on:                                                        # the chip follows the state
        assert lit["110"] > 50 and lit["160"] == 0 and lit["210"] > 50
