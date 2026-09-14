"""Checks for the ten-stage campaign, the AI-win ending, and the music.

These need pygame (the game session builds sprites and fonts), so unlike
test_core.py they open a dummy video/audio driver rather than staying
pure-Python. Run:  python -m pytest   (from pyro_pete_game/)
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
import pytest

from pathfinding import bfs_path

pygame.init()
pygame.display.set_mode((960, 640))

import levels                        # noqa: E402  (needs pygame up first)
from levels.tuning import StageTuning  # noqa: E402
from main import GameSession          # noqa: E402
from audio import AudioManager, note_hz, _TRACKS  # noqa: E402


# ------------------------------------------------------------------ stages
def test_campaign_has_ten_stages():
    assert levels.STAGE_COUNT == 10
    assert len(set(id(s) for s in levels.STAGES)) == 10


@pytest.mark.parametrize("index", range(10))
def test_stage_module_shape(index):
    """Every stage exposes the same four names, so main.py can load any of
    them without special-casing."""
    stage = levels.get(index)
    assert isinstance(stage.NAME, str) and stage.NAME
    assert stage.DIFFICULTY == index + 1
    assert isinstance(stage.TUNING, StageTuning)
    assert callable(stage.build)


@pytest.mark.parametrize("index", range(10))
def test_stage_is_completable(index):
    """The exit must be reachable from spawn on a freshly built map --
    a stage nobody can finish is the one bug a difficulty curve can
    introduce that playtesting might not catch until late."""
    tm = levels.get(index).build()
    assert bfs_path(tm, tm.spawn_cell, tm.exit_cell) is not None


@pytest.mark.parametrize("index", range(10))
def test_stage_has_room_for_its_hazards(index):
    """Victims, spark panels and the collapse budget all consume floor
    tiles; a later stage asking for more than the map holds would fail at
    runtime rather than here."""
    stage = levels.get(index)
    tm = stage.build()
    t = stage.TUNING
    floor_cells = sum(
        1 for r in range(tm.rows) for c in range(tm.cols) if tm.is_walkable(c, r)
    )
    wanted = (t.victim_count or 3) + (t.panel_count or 3) + (t.debris_max_tiles or 10)
    assert wanted < floor_cells * 0.6, (
        f"{stage.NAME}: wants {wanted} special tiles out of {floor_cells} floor")


def test_difficulty_never_goes_backwards():
    """The campaign is meant to ramp; a stage easier than the one before
    it means the tuning table was edited wrongly.

    The ramp is carried by occupants, spark panels and the collapse rate.
    The fire timer is deliberately NOT part of it: it is a playability
    budget that has to keep up with the size of the building. Measured
    headless, shrinking it on the bigger maps did not make them harder,
    it made them unfinishable -- the AI reached the last occupants and
    then burned on the way out, on every single run. So what is asserted
    here is that the budget never shrinks as the floor plan grows.
    """
    prev_fire, prev_panels, prev_victims, prev_area = 0, 0, 0, 0
    for i in range(levels.STAGE_COUNT):
        stage = levels.get(i)
        t = stage.TUNING
        fire = t.fire_seconds_to_exit or 80
        area = stage.COLS * stage.ROWS
        panels = t.panel_count or 3
        victims = t.victim_count or 3
        if area > prev_area:
            assert fire >= prev_fire, (
                f"{stage.NAME} is a bigger map on a shorter fire timer")
        assert panels >= prev_panels
        assert victims >= prev_victims
        prev_fire, prev_panels, prev_victims, prev_area = fire, panels, victims, area


def test_stage_label_is_one_based():
    assert levels.label(0).startswith("Stage 1/10")
    assert levels.label(9).startswith("Stage 10/10")


def test_get_clamps_out_of_range():
    assert levels.get(-5) is levels.STAGES[0]
    assert levels.get(99) is levels.STAGES[-1]


# ------------------------------------------------- the AI-win stage ending
def _run(session, max_seconds=240):
    keys = pygame.key.get_pressed()
    frames = 0
    while session.state == "playing" and frames < 60 * max_seconds:
        session.update(1 / 60.0, keys)
        frames += 1
    return frames / 60.0


def test_race_ends_when_the_ai_gets_out():
    """The bug this fixes: with no player input Pete stands still, so
    before the fix the run only ended when he eventually burned to death,
    long after the AI had finished. Now the AI finishing ends it."""
    session = GameSession(levels.get(0), spectate=False, agent_visual="robot")
    _run(session)
    assert session.state == "results"
    if session.agent.completed:
        assert session.player_done == "outrun"
        assert session.outcome == "outrun"
        assert not session.cleared
    else:
        # The AI died on the way; Pete's own death still ends the run.
        assert session.player_done in ("dead", "exit")


def test_outrun_is_not_scored_as_an_exit():
    """Being beaten must not bank Pete the reach-the-exit bonus."""
    session = GameSession(levels.get(0), spectate=False, agent_visual="robot")
    _run(session)
    if session.outcome == "outrun":
        assert session.player_stats.finished_reason == "time"
        assert session.player_stats.time_bonus == 0


def test_spectate_run_terminates():
    session = GameSession(levels.get(0), spectate=True, agent_visual="robot")
    _run(session)
    assert session.state == "results"


def test_has_next_stage_is_false_on_the_last_one():
    first = GameSession(levels.get(0), spectate=True, stage_index=0)
    last = GameSession(levels.get(9), spectate=True, stage_index=9)
    assert first.has_next_stage
    assert not last.has_next_stage


def test_tuning_reaches_the_hazards():
    """A stage's TUNING must actually change the world, not just sit in
    the module -- this is the wiring that makes the campaign scale."""
    stage = levels.get(9)
    session = GameSession(stage, spectate=True, stage_index=9)
    assert len(session.hazards.panels.panels) == stage.TUNING.panel_count
    assert session.hazards.fire.seconds_to_exit == stage.TUNING.fire_seconds_to_exit
    assert session.hazards.debris.interval == stage.TUNING.debris_interval
    assert len(session.victims) == stage.TUNING.victim_count
    assert session.agent.speed_scale == stage.TUNING.agent_speed_scale


def test_stage_one_still_uses_the_defaults():
    """Stage 1 is the level the game shipped with; the campaign must not
    have silently changed how it plays."""
    import settings
    session = GameSession(levels.get(0), spectate=True, stage_index=0)
    assert session.hazards.fire.seconds_to_exit == settings.FIRE_TARGET_SECONDS_TO_EXIT
    assert len(session.hazards.panels.panels) == settings.SPARK_PANEL_COUNT
    assert session.hazards.debris.interval == settings.DEBRIS_COLLAPSE_INTERVAL
    assert len(session.victims) == settings.VICTIM_COUNT
    assert session.agent.speed_scale == 1.0


# ------------------------------------------------------------------- music
def test_note_names_resolve_to_the_right_pitches():
    assert note_hz("A4") == pytest.approx(440.0)
    assert note_hz("A5") == pytest.approx(880.0)
    assert note_hz("A3") == pytest.approx(220.0)
    assert note_hz("C5") == pytest.approx(523.25, abs=0.1)
    assert note_hz("-") == 0.0


@pytest.mark.parametrize("name", sorted(_TRACKS))
def test_track_synthesises_to_audible_non_clipping_audio(name):
    samples = _TRACKS[name]()
    assert len(samples) > 8000            # at least a fraction of a second
    peak = float(abs(samples).max())
    assert 0.05 < peak <= 1.0             # audible, and not clipped flat


def test_audio_manager_never_raises_without_a_device():
    """Under the dummy audio driver the mixer may or may not open; either
    way none of these calls may raise, because main.py calls them every
    frame with no guard."""
    am = AudioManager()
    for name in _TRACKS:
        am.play(name)
    am.set_volume(0.3)
    am.toggle_mute()
    am.stop()


def test_playing_the_same_track_twice_does_not_restart_it():
    am = AudioManager()
    if not am.enabled:
        pytest.skip("no audio device in this environment")
    am.play("game")
    assert am.current == "game"
    am.play("game")
    assert am.current == "game"
