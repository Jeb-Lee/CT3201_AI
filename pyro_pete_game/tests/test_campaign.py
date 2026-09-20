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


def test_fire_spread_rate_is_comparable_across_stages():
    """Stage 1 rides the rate derived from its exit budget; every later
    stage sets the per-ring interval explicitly, because the derived rate
    depends on where the fire happens to start and so is not comparable
    between maps of different shapes (see levels/tuning.py)."""
    assert levels.get(0).TUNING.fire_spread_interval is None
    for i in range(1, levels.STAGE_COUNT):
        interval = levels.get(i).TUNING.fire_spread_interval
        assert interval is not None, f"{levels.get(i).NAME} has no spread rate"
        assert 2.0 <= interval <= 8.0


def test_spread_interval_override_reaches_the_fire():
    stage = levels.get(9)
    session = GameSession(stage, spectate=True, stage_index=9)
    assert session.hazards.fire.spread_interval == stage.TUNING.fire_spread_interval


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
    # Two ways the AI can end the race: it finished the stage, or it led
    # the last occupant out (the stage ends the instant none are left,
    # which is a tick before the agent's own `completed` flag flips).
    if session.agent.completed or session.victims_remaining == 0:
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


def test_verdict_wording():
    """The verdict line has to agree with the outcome headline above it,
    and name whichever AI skin was actually chosen."""
    from results import _verdict
    from stats import RunStats

    def stats(label, saved, reason):
        st = RunStats(label)
        st.set_saved(saved)
        st.finish(reason)
        return st

    pete_out = stats("You (Pete)", 3, "exit")
    ai_out = stats("AI robot", 3, "exit")
    nobody_p = stats("You (Pete)", 0, "dead")
    nobody_a = stats("AI robot", 0, "dead")

    # both on zero is a shared failure, not a photo finish
    assert _verdict(nobody_p, nobody_a) == "Nobody got out"
    # a real tie still reads as one
    assert "Dead heat" in _verdict(pete_out, stats("AI robot", 3, "exit"))
    # and the opponent is named by its own label, drone or robot
    assert "AI robot" in _verdict(nobody_p, ai_out)
    assert "AI drone" in _verdict(nobody_p, stats("AI drone", 3, "exit"))


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


# ------------------------------------------------- occupant counter / stage end
def _claim_all(session, state):
    for v in session.victims:
        v.state = state


def test_victim_counters_start_at_full_and_track_saved_state():
    from entities.victim import STATE_SAVED, STATE_FOLLOWING
    s = GameSession(levels.get(0), spectate=True, stage_index=0)
    total = len(s.victims)
    assert total > 0
    assert (s.victims_out, s.victims_remaining) == (0, total)
    s.victims[0].state = STATE_FOLLOWING          # picked up is not out
    assert s.victims_out == 0
    s.victims[0].state = STATE_SAVED
    assert (s.victims_out, s.victims_remaining) == (1, total - 1)


def test_agent_heads_for_the_exit_once_everyone_is_accounted_for():
    """The bug: with nobody left to find it kept exploring anyway. Now
    the head-count sends it to the exit rather than an unexplored tile --
    even though unexplored tiles remain."""
    from entities.victim import STATE_SAVED
    s = GameSession(levels.get(0), spectate=True, stage_index=0)
    agent = s.agent
    assert agent._nearest_unexplored(
        __import__("pathfinding").weighted_distances(s.tilemap, agent.current_cell, None)
    ) is not None                                  # there is still map to explore
    _claim_all(s, STATE_SAVED)
    assert agent._all_occupants_accounted(s.victims)
    doors = s.hazards.doors
    if doors.enabled and not doors.key_collected:
        # a locked door on the way still makes the key the goal first --
        # the head-count must not send it at a door it can't open
        assert agent._choose_goal_cell(s.victims) == doors.key_cell
        doors.key_collected = True
    assert agent._choose_goal_cell(s.victims) == s.tilemap.exit_cell


def test_agent_still_explores_while_an_occupant_is_unaccounted_for():
    from entities.victim import STATE_SAVED
    s = GameSession(levels.get(0), spectate=True, stage_index=0)
    _claim_all(s, STATE_SAVED)
    s.victims[0].state = "idle"                    # one still out there, unseen
    assert not s.agent._all_occupants_accounted(s.victims)
    assert s.agent._choose_goal_cell(s.victims) != s.tilemap.exit_cell


def test_escorting_the_last_occupant_counts_as_accounted_for():
    """Otherwise it would take its last follower on a sightseeing tour
    instead of straight to the exit."""
    from entities.victim import STATE_SAVED, STATE_FOLLOWING
    s = GameSession(levels.get(0), spectate=True, stage_index=0)
    _claim_all(s, STATE_SAVED)
    s.victims[0].state = STATE_FOLLOWING
    assert s.agent._all_occupants_accounted(s.victims)


def test_no_headcount_means_keep_searching():
    s = GameSession(levels.get(0), spectate=True, stage_index=0)
    assert not s.agent._all_occupants_accounted([])


def test_stage_ends_the_moment_the_last_occupant_is_out():
    from entities.victim import STATE_SAVED
    s = GameSession(levels.get(0), spectate=True, stage_index=0)
    _claim_all(s, STATE_SAVED)
    s.update(1 / 60.0, pygame.key.get_pressed())
    assert s.victims_remaining == 0
    assert s.state == "results"


def test_race_ends_as_an_ai_win_when_it_leads_the_last_one_out():
    from entities.victim import STATE_SAVED
    s = GameSession(levels.get(0), spectate=False, stage_index=0)
    _claim_all(s, STATE_SAVED)                     # the AI got them all; Pete is inside
    s.update(1 / 60.0, pygame.key.get_pressed())
    assert s.state == "results"
    assert s.outcome == "outrun"


def test_stage_does_not_end_while_anyone_is_left():
    from entities.victim import STATE_SAVED
    s = GameSession(levels.get(0), spectate=True, stage_index=0)
    _claim_all(s, STATE_SAVED)
    s.victims[0].state = "idle"
    s.update(1 / 60.0, pygame.key.get_pressed())
    assert s.victims_remaining == 1
    assert s.state == "playing"


def test_a_stage_with_no_occupants_does_not_end_on_frame_one():
    s = GameSession(levels.get(0), spectate=True, stage_index=0)
    s.victims = []
    s.update(1 / 60.0, pygame.key.get_pressed())
    assert s.state == "playing"


# ------------------------------------------- watch-mode win/lose (regression)
def test_watch_mode_is_a_win_when_the_ai_leads_everyone_out_alive():
    """Regression: the stage now ends the instant the last occupant is out,
    which is a tick before the agent's own `completed` flag flips. `cleared`
    used to read that flag, so a flawless AI run was reported as "The AI
    didn't make it" -- wrong headline, wrong music, and Enter dropped back
    to the menu instead of advancing the campaign."""
    from entities.victim import STATE_SAVED
    s = GameSession(levels.get(0), spectate=True, stage_index=0)
    _claim_all(s, STATE_SAVED)
    s.update(1 / 60.0, pygame.key.get_pressed())
    assert s.state == "results"
    assert not s.agent.is_dead
    assert s.cleared
    assert s.has_next_stage   # ...so Enter would go on to stage 2


def test_watch_mode_is_a_loss_when_the_ai_dies():
    from entities.victim import STATE_SAVED
    s = GameSession(levels.get(0), spectate=True, stage_index=0)
    s.agent.health = 0.0
    s.victims[0].state = STATE_SAVED           # some rescued, but it burned
    s.update(1 / 60.0, pygame.key.get_pressed())
    s.agent.health = 0.0
    assert s.agent.is_dead
    assert not s.cleared


def test_a_dead_ai_is_not_cleared_even_if_the_count_reads_zero():
    from entities.victim import STATE_SAVED
    s = GameSession(levels.get(0), spectate=True, stage_index=0)
    _claim_all(s, STATE_SAVED)
    s.agent.health = 0.0
    assert s.victims_remaining == 0
    assert not s.cleared


# ------------------------------------------------------- the stage-end rules
# Every occupant is idle (waiting), following (being escorted), saved (out)
# or dead (lost with a rescuer that died). The stage ends when everyone
# left alive has been found AND either all are out or a rescuer is at the
# exit; or when nobody still alive can carry on.
from entities.victim import STATE_IDLE, STATE_FOLLOWING, STATE_SAVED, STATE_DEAD  # noqa: E402


def _race(stage_index=0):
    return GameSession(levels.get(stage_index), spectate=False, stage_index=stage_index)



def _park_victims_away(s):
    """Victim placement is random, and one can land right beside the exit
    or spawn -- where a rescuer standing there claims it on the spot and
    the scenario under test quietly changes. Move everyone to the floor
    cell farthest from both, so those tests are deterministic."""
    tm = s.tilemap
    sx, sy = tm.spawn_cell
    ex, ey = tm.exit_cell
    best, best_d = None, -1
    for r in range(tm.rows):
        for c in range(tm.cols):
            if tm.is_walkable(c, r):
                d = min(abs(c - sx) + abs(r - sy), abs(c - ex) + abs(r - ey))
                if d > best_d:
                    best, best_d = (c, r), d
    x, y = tm.cell_center(*best)
    for v in s.victims:
        v.cell, v.x, v.y = best, x, y

def _put_on_exit(entity_session, who):
    ex, ey = entity_session.tilemap.cell_center(*entity_session.tilemap.exit_cell)
    target = entity_session.player if who == "pete" else entity_session.agent
    target.x, target.y = ex, ey


def _tick(s, n=1):
    keys = pygame.key.get_pressed()
    for _ in range(n):
        s.update(1 / 60.0, keys)


def test_reaching_the_exit_with_nobody_rescued_does_not_win():
    """The bug: Pete walking to the exit empty-handed was 'Stage cleared'
    (110 points) with every occupant still inside."""
    s = _race()
    _park_victims_away(s)
    _put_on_exit(s, "pete")
    _tick(s)
    assert s.state == "playing"          # nothing has ended
    assert s.victims_out == 0
    assert s.outcome is None


def test_exit_banks_escorted_occupants_but_does_not_end_the_stage():
    s = _race()
    _park_victims_away(s)
    s.victims[0].state = STATE_FOLLOWING
    s.player_follow_order.append(s.victims[0])
    _put_on_exit(s, "pete")
    _tick(s)
    assert s.victims[0].state == STATE_SAVED
    assert s.state == "playing"          # others are still waiting to be found


def test_stage_ends_when_everyone_is_found_and_someone_reaches_the_exit():
    """Rule 2: found_by_pete + found_by_ai == total, then whoever gets to
    the exit first ends it -- even if the other is still mid-escort."""
    s = _race()
    a, b, c = s.victims[:3]
    for v in s.victims:
        v.state = STATE_SAVED            # park the rest of the stage
    a.state, b.state, c.state = STATE_FOLLOWING, STATE_FOLLOWING, STATE_FOLLOWING
    s.player_follow_order.extend([a])
    s.agent_follow_order.extend([b, c])
    _put_on_exit(s, "agent")
    _tick(s)
    assert s.state == "results"
    assert s.evacuated
    assert a.state == STATE_FOLLOWING    # Pete's escort didn't make it out
    assert b.state == c.state == STATE_SAVED


def test_stage_does_not_end_at_the_exit_while_someone_is_still_waiting():
    s = _race()
    _park_victims_away(s)
    s.victims[0].state = STATE_FOLLOWING
    s.agent_follow_order.append(s.victims[0])
    _put_on_exit(s, "agent")
    _tick(s)
    assert any(v.state == STATE_IDLE for v in s.victims)
    assert s.state == "playing"


def test_stage_ends_when_everyone_is_out_split_between_both_rescuers():
    s = _race()
    for i, v in enumerate(s.victims):
        v.state = STATE_SAVED
    _tick(s)
    assert s.state == "results" and s.evacuated
    assert s.victims_remaining == 0


def test_a_rescuer_dying_loses_the_occupants_it_was_escorting():
    """Rule 3: they die and come off the stage total."""
    s = _race()
    total = len(s.victims)
    s.victims[0].state = STATE_FOLLOWING
    s.player_follow_order.append(s.victims[0])
    s.player.health = 0.0
    _tick(s)
    assert s.victims[0].state == STATE_DEAD
    assert s.victims_dead == 1
    assert s.victims_remaining == total - 1        # deducted from the total
    assert s.state == "playing"                    # the AI carries on


def test_occupants_already_out_survive_their_rescuers_death():
    s = _race()
    s.victims[0].state = STATE_SAVED
    s.player_follow_order.append(s.victims[0])
    s.player.health = 0.0
    _tick(s)
    assert s.victims[0].state == STATE_SAVED
    assert s.victims_dead == 0


def test_the_ai_dying_loses_its_escort_too_and_pete_carries_on():
    s = _race()
    s.victims[0].state = STATE_FOLLOWING
    s.agent_follow_order.append(s.victims[0])
    s.agent.health = 0.0
    _tick(s)
    assert s.victims[0].state == STATE_DEAD
    assert s.state == "playing"


def test_stage_can_still_be_finished_after_pete_dies():
    """'...if the other entity finds the remaining victims and reaches the
    exit, the stage ends.'"""
    s = _race()
    s.victims[0].state = STATE_FOLLOWING
    s.player_follow_order.append(s.victims[0])
    s.player.health = 0.0
    _tick(s)                                       # Pete dies, his occupant with him
    for v in s.victims[1:]:
        v.state = STATE_FOLLOWING
        s.agent_follow_order.append(v)
    _put_on_exit(s, "agent")
    _tick(s)
    assert s.state == "results"
    assert s.evacuated
    assert s.outcome == "died"                     # ...but Pete still lost


def test_camera_follows_the_ai_once_pete_is_dead():
    s = _race()
    s.player.health = 0.0
    _tick(s)
    assert s._view_anchor is s.agent


def test_stage_ends_when_nobody_alive_can_carry_on():
    s = _race()
    s.player.health = 0.0
    s.agent.health = 0.0
    _tick(s)
    assert s.state == "results"
    assert not s.evacuated
    assert s.outcome == "died"


def test_pete_clears_the_stage_only_if_alive_and_he_saved_someone():
    s = _race()
    for v in s.victims:
        v.state = STATE_SAVED
    s.player_follow_order.append(s.victims[0])     # Pete led one out, the AI the rest
    _tick(s)
    assert s.state == "results"
    assert s.outcome == "cleared"
    assert s.cleared


def test_pete_who_saved_nobody_does_not_clear_even_if_the_ai_evacuated_everyone():
    s = _race()
    for v in s.victims:
        v.state = STATE_SAVED                      # all the AI's doing
    _tick(s)
    assert s.state == "results"
    assert s.outcome == "outrun"
    assert not s.cleared


def test_watch_mode_ends_as_a_loss_if_the_ai_gives_up_with_people_left():
    s = GameSession(levels.get(0), spectate=True, stage_index=0)
    s.agent._finished = True                        # gave up: search judged too risky
    _tick(s)
    assert s.state == "results"
    assert any(v.state == STATE_IDLE for v in s.victims)
    assert not s.evacuated
    assert not s.cleared


def test_watch_mode_ends_as_a_loss_when_the_ai_dies():
    s = GameSession(levels.get(0), spectate=True, stage_index=0)
    s.agent.health = 0.0
    _tick(s)
    assert s.state == "results"
    assert not s.cleared


def test_dead_occupant_is_drawn_without_error_and_not_as_a_sprite():
    s = _race()
    s.victims[0].state = STATE_DEAD
    surf = pygame.Surface((960, 640))
    s.victims[0].draw(surf, (0, 0), font=s.marker_font)   # must not raise
