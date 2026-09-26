"""Search-order options (far-side lean, corner skip), the model sidecar file, and the game's
AI-model menu.

The default agent is the benchmark and must not change; the options are opt-in. Run:
    python -m pytest     (from pyro_pete_game/)
"""

import importlib.util
import json
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pygame
import pytest

pygame.init()
pygame.display.set_mode((960, 640))

import levels                                                      # noqa: E402
from entities.rescue_agent import RescueAgent                     # noqa: E402
from main import GameSession, _build_brain_menu, _new_session     # noqa: E402
from entities.rescue_agent import _distances_from_exit           # noqa: E402
from pathfinding import weighted_distances                        # noqa: E402

HAVE_SB3 = importlib.util.find_spec("stable_baselines3") is not None


class _NoKeys:
    def __getitem__(self, key):
        return False


def _explored_session(stage, options=None, frames=240, seed=4):
    """A session where the agent has walked a little, so it has real frontiers."""
    random.seed(seed)
    s = GameSession(levels.get(stage), spectate=True, agent_visual="drone", stage_index=stage,
                    agent_brain="astar", policy=None, agent_options=options)
    keys = _NoKeys()
    for _ in range(frames):
        s.update(1 / 30, keys)
    return s


def test_the_default_agent_has_every_search_option_off():
    """The benchmark: A* with nothing switched on."""
    assert RescueAgent.frontier_lean == 0.0
    assert RescueAgent.frontier_min_reveal == 0
    assert RescueAgent.frontier_defer_small is False
    s = _explored_session(0)
    assert s.agent_options == {}
    assert s.agent.frontier_lean == 0.0 and s.agent.frontier_min_reveal == 0


def test_options_reach_the_agent_and_unknown_ones_are_refused():
    s = _explored_session(0, {"frontier_lean": 0.5, "frontier_min_reveal": 4}, frames=1)
    assert s.agent.frontier_lean == 0.5 and s.agent.frontier_min_reveal == 4
    with pytest.raises(ValueError):
        GameSession(levels.get(0), spectate=True, stage_index=0, agent_options={"health": 999})


@pytest.mark.parametrize("stage", [0, 3, 6])
def test_leaning_towards_the_far_side_never_picks_a_frontier_nearer_the_exit(stage):
    """By construction: minimising d_agent - lean * d_exit can only move the choice to a frontier
    at least as far from the exit as the nearest-frontier choice."""
    s = _explored_session(stage)
    a = s.agent
    d_exit = _distances_from_exit(a.tilemap)
    dist = weighted_distances(a.tilemap, a.current_cell, a._cost_fn())
    nearest = a._nearest_unexplored(dist)
    a.frontier_lean = 0.5
    leaned = a._nearest_unexplored(dist)
    assert nearest is not None and leaned is not None
    assert d_exit[leaned] >= d_exit[nearest]


def test_a_corner_too_small_to_be_worth_a_trip_is_skipped_or_deferred():
    s = _explored_session(3)
    a = s.agent
    dist = weighted_distances(a.tilemap, a.current_cell, a._cost_fn())
    plain = a._nearest_unexplored(dist)
    assert plain is not None
    a.frontier_min_reveal = 10_000          # nothing can reveal that many tiles
    assert a._nearest_unexplored(dist) is None, "strict: no trip is worth it"
    a.frontier_defer_small = True
    assert a._nearest_unexplored(dist) == plain, "deferred: still visited when nothing else is left"


@pytest.mark.skipif(not HAVE_SB3, reason="stable-baselines3 not installed")
@pytest.mark.parametrize("options", [{}, {"frontier_lean": 0.5, "frontier_min_reveal": 4}])
def test_the_options_do_not_open_the_fog_of_war(options):
    """No God mode with the options on: moving an occupant the agent has not spotted changes no
    number in its observation and not the teacher's decision."""
    from ml import expert
    from ml.env import EvacuationEnv
    from ml.observation import build_observation
    from settings import AGENT_VISION_TILES
    e = EvacuationEnv(max_sim_seconds=60.0, obs_version=4, agent_options=options)
    e.reset(seed=4, options={"stage": 3})
    s, a = e._session, e._session.agent
    assert a.frontier_lean == options.get("frontier_lean", 0.0)
    v = s.victims[0]
    cc, cr = a.current_cell
    assert (v.cell[0] - cc) ** 2 + (v.cell[1] - cr) ** 2 > AGENT_VISION_TILES ** 2
    a.known_victims.discard(v)
    before_obs = build_observation(a, s.victims, 4)
    before_label = expert.expert_action(a, s.victims)
    tm = a.tilemap
    far = next((c, r) for r in range(tm.rows) for c in range(tm.cols)
               if tm.tile_at(c, r) != "#" and (c, r) not in (tm.spawn_cell, tm.exit_cell)
               and (c - cc) ** 2 + (r - cr) ** 2 > (AGENT_VISION_TILES + 4) ** 2 and (c, r) != v.cell)
    v.cell = far
    v.x, v.y = tm.cell_center(*far)
    assert v not in a.known_victims
    assert np.array_equal(before_obs, build_observation(a, s.victims, 4))
    assert before_label == expert.expert_action(a, s.victims)


# ---------------------------------------------------------- the model's JSON sidecar
def test_a_model_records_the_search_order_it_was_trained_with(tmp_path):
    from ml.policy import options_path, read_agent_options, write_agent_options
    model = str(tmp_path / "m.zip")
    assert options_path(model).endswith("m.json")
    assert read_agent_options(model) == {}, "no file: trained against the default agent"
    write_agent_options(model, {"frontier_lean": 0.5, "frontier_min_reveal": 4}, obs_version=4)
    assert read_agent_options(model) == {"frontier_lean": 0.5, "frontier_min_reveal": 4}
    with open(options_path(model), encoding="utf-8") as fh:
        assert json.load(fh)["obs_version"] == 4


def test_a_policy_carrying_options_configures_the_game_agent():
    from ml.policy import StayPolicy
    p = StayPolicy()
    p.agent_options = {"frontier_lean": 0.5}
    s = GameSession(levels.get(0), spectate=True, stage_index=0, agent_brain="learned", policy=p)
    assert s.agent.frontier_lean == 0.5
    # an explicit option beats the policy's
    s2 = GameSession(levels.get(0), spectate=True, stage_index=0, agent_brain="learned", policy=p,
                     agent_options={"frontier_lean": 0.2})
    assert s2.agent.frontier_lean == 0.2


# ------------------------------------------------------------------- the game menu
def test_the_brain_menu_lists_astar_first_then_the_available_models():
    models = [("v4", "Learned v4", "d4", "p4"), ("v5", "Learned v5", "d5", "p5")]
    menu = _build_brain_menu(models)
    assert [o[1] for o in menu.options] == ["astar", "model:v4", "model:v5"]
    assert menu.index == 0, "A* is the default selection"


@pytest.mark.skipif(not HAVE_SB3, reason="stable-baselines3 not installed")
def test_the_shipped_models_are_offered_and_start_a_session():
    from ml.policy import MODEL_CHOICES, available_models
    have = {k for k, *_ in available_models()}
    assert have <= {k for k, *_ in MODEL_CHOICES} | {"installed"}
    assert "v4" in have, "ml/models/ai_v4.zip ships with the game"
    s = _new_session(0, "watch", "drone", "model:v4")
    assert s.agent_brain == "learned" and s.spectate
    assert "Learned v4" in s.agent_stats.label
    if "v5" in have:
        s5 = _new_session(0, "watch", "drone", "model:v5")
        assert s5.agent_brain == "learned"
        assert s5.agent.frontier_lean == s5.policy.agent_options.get("frontier_lean", 0.0)


def test_astar_and_an_unknown_model_both_give_the_astar_planner():
    assert _new_session(0, "watch", "drone", "astar").agent_brain == "astar"
    assert _new_session(0, "watch", "drone", "model:nope").agent_brain == "astar"


def test_distance_from_the_exit_covers_the_whole_building_even_behind_the_locked_door():
    """The flaw this guards against: measuring it with the door closed left the spawn side out
    (no distance at all), so the far-side lean silently did nothing there."""
    for stage in range(10):
        s = _explored_session(stage, frames=1)
        tm = s.tilemap
        d = _distances_from_exit(tm)
        floor = [(c, r) for r in range(tm.rows) for c in range(tm.cols) if tm.tile_at(c, r) != "#"]
        assert all(cell in d for cell in floor), f"stage {stage + 1}: cells with no exit distance"
        assert d[tm.exit_cell] == 0
        assert tm.dynamic_blocked, "the door is closed at the start, which is the case that used to break it"


def test_the_brain_menu_is_a_watch_mode_screen():
    """Watch AI Play always offers the models; Play vs AI keeps its old flow (no extra screen)
    unless a model was installed as ml/models/ai_policy.zip."""
    from main import _brain_choices
    models = [("v4", "Learned v4", "d", "p"), ("v5", "Learned v5", "d", "p")]
    assert _brain_choices("watch", models) == models
    assert _brain_choices("play", models) == []
    assert _brain_choices("watch", []) == []
    installed = models + [("installed", "Learned model", "d", "p")]
    assert _brain_choices("play", installed) == installed


# ------------------------------------------------ installing a model (review findings)
@pytest.mark.skipif(not HAVE_SB3, reason="stable-baselines3 not installed")
def test_installing_a_model_carries_its_search_settings_and_drops_stale_ones(tmp_path):
    """--install used to copy only the .zip, so a model trained against a far-side teacher
    ran against the default search (or an earlier install's settings)."""
    from ml.policy import options_path, read_agent_options, write_agent_options
    from ml.training import install_model
    src = tmp_path / "run" / "final_model.zip"
    src.parent.mkdir()
    src.write_bytes(b"model")
    write_agent_options(str(src), {"frontier_lean": 0.5, "frontier_min_reveal": 4}, obs_version=4)
    dest = str(tmp_path / "models" / "ai_policy.zip")
    install_model(str(src), dest)
    assert read_agent_options(dest) == {"frontier_lean": 0.5, "frontier_min_reveal": 4}
    # a later model trained against the default agent must not inherit those settings
    plain = tmp_path / "run" / "plain.zip"
    plain.write_bytes(b"model")
    install_model(str(plain), dest)
    assert not os.path.isfile(options_path(dest))
    assert read_agent_options(dest) == {}


def test_no_learned_model_is_offered_without_sb3_contrib(monkeypatch):
    """Every shipped model is a MaskablePPO policy from sb3-contrib; offering one that cannot
    load would silently hand the player A* instead of the model they picked."""
    import importlib.util
    from ml import policy
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec",
                        lambda name, *a, **k: None if name == "sb3_contrib" else real(name, *a, **k))
    assert policy.available_models() == []
