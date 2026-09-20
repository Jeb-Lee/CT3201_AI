"""Checks for the learned-AI option: observation, agent, environment, harness.

The learned brain is an opt-in alternative to the A* rescuer, so the most
important checks here are (a) the default game is untouched and (b) the
learned agent never sees more than A* does (observation version 1 sees less; see ml/observation.py).

Needs pygame (dummy drivers) and, for the environment tests, gymnasium;
those skip cleanly if it isn't installed. Torch / stable-baselines3 are
never required here -- the SB3 adapter is tested against a stub model.
Run:  python -m pytest   (from pyro_pete_game/)
"""

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

import levels                                            # noqa: E402
from main import GameSession                             # noqa: E402
from entities.learned_agent import (                     # noqa: E402
    LearnedAgent, IDLE_GIVE_UP_SECONDS)
from entities.rescue_agent import RescueAgent            # noqa: E402
from entities.victim import STATE_IDLE                   # noqa: E402
from ml import observation as obs_mod                    # noqa: E402
from ml import policy as policy_mod                      # noqa: E402
from ml import evaluation                                # noqa: E402
from ml.outcome import classify, summarise, OUTCOMES    # noqa: E402
from ml.observation import (                             # noqa: E402
    ACTION_STAY, ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, N_ACTIONS,
    OBS_SIZE, WINDOW, WINDOW_RADIUS, CHANNELS, FEATURES, N_CHANNELS,
    action_mask, build_observation,
)
from ml.policy import RandomPolicy, StayPolicy, SB3Policy   # noqa: E402

DT = 1 / 30
CH = {name: i for i, name in enumerate(CHANNELS)}
FT = {name: i for i, name in enumerate(FEATURES)}


class _NoKeys:
    def __getitem__(self, key):
        return False


def _session(stage=0, brain="learned", policy=None, seed=1):
    random.seed(seed)
    return GameSession(levels.get(stage), spectate=True, agent_visual="drone",
                       stage_index=stage, agent_brain=brain, policy=policy)


def _teleport(agent, tilemap, cell):
    agent.x, agent.y = tilemap.cell_center(*cell)
    agent.current_cell = cell


def _window(obs):
    return obs[:WINDOW * WINDOW * N_CHANNELS].reshape(WINDOW, WINDOW, N_CHANNELS)


def _features(obs):
    return obs[WINDOW * WINDOW * N_CHANNELS:]


def _run(session, seconds):
    keys = _NoKeys()
    for _ in range(int(seconds / DT)):
        if session.state != "playing":
            break
        session.update(DT, keys)


# --------------------------------------------------------- default is intact
def test_default_ai_is_still_astar():
    s = _session(brain="astar")
    assert type(s.agent) is RescueAgent
    assert not isinstance(s.agent, LearnedAgent)


def test_default_brain_argument_is_astar():
    random.seed(1)
    s = GameSession(levels.get(0), spectate=True, agent_visual="drone", stage_index=0)
    assert type(s.agent) is RescueAgent


def test_learned_brain_builds_a_learned_agent_with_its_policy():
    p = StayPolicy()
    s = _session(brain="learned", policy=p)
    assert isinstance(s.agent, LearnedAgent)
    assert s.agent.policy is p
    assert "(learned)" in s.agent_stats.label


def test_reset_keeps_the_brain():
    s = _session(brain="learned", policy=StayPolicy())
    s.reset()
    assert isinstance(s.agent, LearnedAgent)
    a = _session(brain="astar")
    a.reset()
    assert type(a.agent) is RescueAgent


def test_pete_is_never_ml_driven():
    """The learned brain replaces only the AI rescuer; Pete is keyboard-driven."""
    s = GameSession(levels.get(0), spectate=False, agent_visual="drone",
                    stage_index=0, agent_brain="learned", policy=StayPolicy())
    assert type(s.player).__name__ == "Player"
    assert not hasattr(s.player, "policy")


def test_learned_option_hidden_without_a_model(tmp_path):
    assert not policy_mod.model_available(str(tmp_path / "nothing.zip"))


def test_model_needs_the_library_too(tmp_path, monkeypatch):
    f = tmp_path / "m.zip"
    f.write_bytes(b"x")
    monkeypatch.setattr(policy_mod.importlib.util, "find_spec", lambda name: None)
    assert not policy_mod.model_available(str(f))


def test_load_policy_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        policy_mod.load_policy(str(tmp_path / "nothing.zip"))


# ------------------------------------------------------------- observation
def test_observation_shape_dtype_and_range():
    s = _session()
    o = build_observation(s.agent, s.victims)
    assert o.shape == (OBS_SIZE,)
    assert o.dtype == np.float32
    assert np.all(np.isfinite(o))
    assert o.min() >= -1.0 and o.max() <= 2.0


def test_observation_size_matches_layout():
    assert OBS_SIZE == WINDOW * WINDOW * N_CHANNELS + len(FEATURES)
    assert WINDOW == 2 * WINDOW_RADIUS + 1


def test_unexplored_cells_reveal_nothing_but_the_exit():
    """Version 1 hides what it has not explored: an unexplored cell shows no walls, fire or
    occupants (stricter than A*, which plans over the whole map)."""
    s = _session()
    agent = s.agent
    agent.explored = {agent.current_cell}          # forget everything else
    w = _window(build_observation(agent, s.victims))
    for wy in range(WINDOW):
        for wx in range(WINDOW):
            dc, dr = wx - WINDOW_RADIUS, wy - WINDOW_RADIUS
            cell = (agent.current_cell[0] + dc, agent.current_cell[1] + dr)
            inside = 0 <= cell[0] < s.tilemap.cols and 0 <= cell[1] < s.tilemap.rows
            if inside and cell != agent.current_cell:
                assert w[wy, wx, CH["unexplored"]] == 1.0
                for name in ("wall", "blocked", "fire", "smoke", "panel",
                             "occupant", "key"):
                    assert w[wy, wx, CH[name]] == 0.0, (cell, name)


def test_the_agents_own_cell_is_explored():
    s = _session()
    w = _window(build_observation(s.agent, s.victims))
    assert w[WINDOW_RADIUS, WINDOW_RADIUS, CH["unexplored"]] == 0.0


def test_hidden_occupants_are_not_visible():
    """An occupant the agent hasn't spotted must not appear in the window,
    even if the cell happens to be explored."""
    s = _session()
    agent = s.agent
    victim = s.victims[0]
    agent.known_victims.discard(victim)
    agent.explored.add(victim.cell)
    # put the agent's window over the victim
    _teleport(agent, s.tilemap, victim.cell)
    agent.known_victims.clear()
    w = _window(build_observation(agent, s.victims))
    assert w[:, :, CH["occupant"]].sum() == 0.0


def test_spotted_occupants_appear_in_the_window():
    s = _session()
    agent = s.agent
    victim = s.victims[0]
    _teleport(agent, s.tilemap, victim.cell)
    agent.explored.add(victim.cell)
    agent.known_victims.add(victim)
    w = _window(build_observation(agent, s.victims))
    assert w[WINDOW_RADIUS, WINDOW_RADIUS, CH["occupant"]] == 1.0
    f = _features(build_observation(agent, s.victims))
    assert f[FT["spotted"]] > 0.0


def test_fire_outside_vision_is_hidden_and_inside_is_shown():
    s = _session()
    agent = s.agent
    cc, cr = agent.current_cell
    near = far = None
    for dc in range(1, WINDOW_RADIUS + 1):
        for cell in ((cc + dc, cr),):
            agent.explored.add(cell)
            if dc <= 2 and near is None:
                near = cell
            if dc == WINDOW_RADIUS and far is None:
                far = cell
    s.hazards.fire.burning.add(near)
    s.hazards.fire.burning.add(far)
    w = _window(build_observation(agent, s.victims))
    assert w[WINDOW_RADIUS, WINDOW_RADIUS + (near[0] - cc), CH["fire"]] == 1.0
    assert w[WINDOW_RADIUS, WINDOW_RADIUS + (far[0] - cc), CH["fire"]] == 0.0


def test_exit_and_headcount_are_always_known():
    s = _session()
    o = build_observation(s.agent, s.victims)
    f = _features(o)
    assert f[FT["unclaimed"]] == pytest.approx(1.0)      # everyone still inside
    ec, er = s.tilemap.exit_cell
    cc, cr = s.agent.current_cell
    assert f[FT["exit_dx"]] == pytest.approx((ec - cc) / s.tilemap.cols)
    assert f[FT["exit_dy"]] == pytest.approx((er - cr) / s.tilemap.rows)
    assert 0.0 <= f[FT["fire_countdown"]] <= 1.0


def test_health_feature_tracks_damage():
    s = _session()
    full = _features(build_observation(s.agent, s.victims))[FT["health"]]
    assert full == pytest.approx(1.0)
    s.agent.health *= 0.5
    half = _features(build_observation(s.agent, s.victims))[FT["health"]]
    assert half == pytest.approx(0.5)


def test_observation_is_deterministic():
    s = _session()
    a = build_observation(s.agent, s.victims)
    b = build_observation(s.agent, s.victims)
    assert np.array_equal(a, b)


# ------------------------------------------------------------- action mask
def test_stay_is_always_legal_and_walls_are_not():
    s = _session()
    agent = s.agent
    mask = action_mask(agent)
    assert mask.dtype == bool and mask.shape == (N_ACTIONS,)
    assert mask[ACTION_STAY]
    cc, cr = agent.current_cell
    tm = s.tilemap
    assert mask[ACTION_UP] == tm.is_walkable(cc, cr - 1)
    assert mask[ACTION_DOWN] == tm.is_walkable(cc, cr + 1)
    assert mask[ACTION_LEFT] == tm.is_walkable(cc - 1, cr)
    assert mask[ACTION_RIGHT] == tm.is_walkable(cc + 1, cr)
    assert mask.sum() >= 2                # spawn is never a dead end of walls


# ----------------------------------------------------------- learned agent
def _open_action(agent):
    mask = action_mask(agent)
    return next(a for a in (ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT) if mask[a])


def test_command_walks_to_the_neighbouring_tile():
    s = _session()
    agent = s.agent
    start = agent.current_cell
    action = _open_action(agent)
    dc, dr = obs_mod.MOVES[action]
    agent.command(action)
    _run(s, 1.5)
    assert agent.current_cell == (start[0] + dc, start[1] + dr)


def test_a_wall_step_is_a_wasted_decision():
    s = _session()
    agent = s.agent
    mask = action_mask(agent)
    wall_action = next((a for a in range(1, N_ACTIONS) if not mask[a]), None)
    if wall_action is None:
        pytest.skip("spawn has no adjacent wall")
    start = agent.current_cell
    agent.command(wall_action)
    _run(s, 1.0)
    assert agent.current_cell == start


def test_policy_is_asked_for_moves():
    calls = []

    class Recorder:
        def act(self, observation, mask):
            calls.append((observation.shape, mask.copy()))
            return ACTION_STAY

    s = _session(policy=Recorder())
    _run(s, 1.0)
    assert calls, "the policy was never consulted"
    assert calls[0][0] == (OBS_SIZE,)
    assert calls[0][1].dtype == bool


def test_stay_policy_gives_up_after_the_idle_limit():
    s = _session(policy=StayPolicy())
    _run(s, IDLE_GIVE_UP_SECONDS + 3)
    assert s.state != "playing"
    assert summarise(s)["outcome"] == "gave_up"


def test_random_policy_moves_around():
    s = _session(policy=RandomPolicy(3))
    start = s.agent.current_cell
    _run(s, 20)
    assert s.agent_stats.distance > 0
    assert s.agent.current_cell != start or s.agent_stats.distance > 40


def test_learned_agent_shares_the_astar_bodys_rules():
    """Same class hierarchy => same health, smoke slowdown and damage rules."""
    assert issubclass(LearnedAgent, RescueAgent)
    for name in ("_apply_hazards", "update", "draw"):
        if hasattr(RescueAgent, name):
            assert getattr(LearnedAgent, name) is getattr(RescueAgent, name)


def test_astar_is_reproducible_under_a_seed():
    """Guards the (dist, cell) tie-break: A* used to depend on set order."""
    a = evaluation.run_episode("astar", 0, seed=42, max_seconds=60)
    b = evaluation.run_episode("astar", 0, seed=42, max_seconds=60)
    assert a == b


# ----------------------------------------------------------------- outcome
def test_outcomes_are_a_closed_set():
    s = _session(brain="astar")
    assert classify(s) == "timeout"        # still playing at frame zero
    assert classify(s) in OUTCOMES
    s.agent.health = 0          # is_dead follows from health
    s.state = "results"
    assert classify(s) == "died"


# ------------------------------------------------------------------ policies
class _StubModel:
    """Stands in for a stable-baselines3 model (no torch needed)."""

    def __init__(self, action, maskable=False):
        self._action = action
        self.seen_mask = None
        if maskable:
            self.predict = self._predict_masked
        else:
            self.predict = self._predict_plain

    def _predict_plain(self, obs, deterministic=True):
        return np.array([self._action]), None

    def _predict_masked(self, obs, action_masks=None, deterministic=True):
        self.seen_mask = action_masks
        return np.array([self._action]), None


def test_sb3_adapter_returns_a_legal_action():
    mask = np.array([True, True, False, True, True])
    p = SB3Policy(_StubModel(ACTION_UP))
    assert p.act(np.zeros(OBS_SIZE), mask) == ACTION_UP


def test_sb3_adapter_turns_an_illegal_action_into_stay():
    mask = np.array([True, False, True, True, True])
    p = SB3Policy(_StubModel(ACTION_UP))
    assert p.act(np.zeros(OBS_SIZE), mask) == ACTION_STAY


def test_sb3_adapter_ignores_out_of_range_actions():
    p = SB3Policy(_StubModel(99))
    assert p.act(np.zeros(OBS_SIZE), np.ones(N_ACTIONS, dtype=bool)) == ACTION_STAY


def test_sb3_adapter_passes_the_mask_to_maskable_models():
    model = _StubModel(ACTION_RIGHT, maskable=True)
    p = SB3Policy(model)
    mask = np.array([True, False, False, False, True])
    assert p.act(np.zeros(OBS_SIZE), mask) == ACTION_RIGHT
    assert np.array_equal(model.seen_mask, mask)


def test_random_policy_only_picks_legal_actions():
    p = RandomPolicy(0)
    mask = np.array([True, False, True, False, False])
    assert {p.act(None, mask) for _ in range(50)} <= {ACTION_STAY, ACTION_DOWN}


def test_random_policy_is_seeded():
    mask = np.ones(N_ACTIONS, dtype=bool)
    a = [RandomPolicy(5).act(None, mask) for _ in range(1)]
    b = [RandomPolicy(5).act(None, mask) for _ in range(1)]
    assert a == b


# ------------------------------------------------------------------ harness
def test_wilson_interval_behaves_at_the_extremes():
    lo, hi = evaluation.wilson(0, 10)
    assert lo == 0.0 and 0.0 < hi < 0.4
    lo, hi = evaluation.wilson(10, 10)
    assert hi == 1.0 and 0.6 < lo < 1.0
    lo, hi = evaluation.wilson(5, 10)
    assert lo < 0.5 < hi


def test_wilson_narrows_with_more_data():
    w_small = evaluation.wilson(5, 10)
    w_big = evaluation.wilson(500, 1000)
    assert (w_big[1] - w_big[0]) < (w_small[1] - w_small[0])


def test_wilson_with_no_data_is_nan():
    lo, hi = evaluation.wilson(0, 0)
    assert lo != lo and hi != hi


def test_mean_ci():
    mean, half = evaluation.mean_ci([10, 10, 10, 10])
    assert mean == 10 and half == 0
    mean, half = evaluation.mean_ci([0, 10])
    assert mean == 5 and half > 0
    assert evaluation.mean_ci([7])[0] == 7
    assert evaluation.mean_ci([7])[1] != evaluation.mean_ci([7])[1]     # nan


def test_episode_seed_is_shared_across_agents_and_distinct_across_episodes():
    assert evaluation.episode_seed(1000, 2, 3) == evaluation.episode_seed(1000, 2, 3)
    seeds = {evaluation.episode_seed(1000, st, ep) for st in range(10) for ep in range(50)}
    assert len(seeds) == 500


def test_resolve_agent_specs():
    assert evaluation.resolve_agent("astar") == ("astar", None)
    brain, pol = evaluation.resolve_agent("random", 1)
    assert brain == "learned" and isinstance(pol, RandomPolicy)
    brain, pol = evaluation.resolve_agent("stay")
    assert brain == "learned" and isinstance(pol, StayPolicy)
    with pytest.raises(ValueError):
        evaluation.resolve_agent("wizard")


def test_resolve_agent_sample_spec_samples_instead_of_taking_the_argmax(monkeypatch):
    class Fake:
        deterministic = True
    monkeypatch.setattr(evaluation, "load_policy", lambda path: Fake())
    brain, pol = evaluation.resolve_agent("sample:whatever.zip", 3)
    assert brain == "learned" and pol.deterministic is False
    brain, pol = evaluation.resolve_agent("model:whatever.zip", 3)
    assert pol.deterministic is True


def test_run_episode_reports_a_full_record():
    r = evaluation.run_episode("stay", 0, seed=1, max_seconds=30)
    assert r["outcome"] == "gave_up"
    for key in ("agent", "stage", "seed", "victims_out", "victims_total",
                "victims_lost", "score", "damage", "seconds"):
        assert key in r


def test_paired_difference_uses_matching_seeds_only():
    rows = [
        {"agent": "a", "stage": 0, "seed": 1, "score": 100, "outcome": "evacuated"},
        {"agent": "b", "stage": 0, "seed": 1, "score": 40, "outcome": "died"},
        {"agent": "a", "stage": 0, "seed": 2, "score": 100, "outcome": "evacuated"},
        {"agent": "b", "stage": 0, "seed": 3, "score": 0, "outcome": "died"},   # unmatched
    ]
    d = evaluation.paired_score_difference(rows, "a", "b")
    assert d["n"] == 1
    assert d["mean"] == -60
    assert d["only_a_evacuated"] == 1 and d["only_b_evacuated"] == 0


def test_report_and_csv(tmp_path):
    results = evaluation.evaluate(["astar", "stay"], [0], 2, base_seed=7, max_seconds=30)
    assert len(results) == 4
    text = evaluation.format_report(results, ["astar", "stay"])
    assert "astar" in text and "stay" in text and "Paired comparison" in text
    path = tmp_path / "out.csv"
    evaluation.write_csv(results, str(path))
    assert len(path.read_text().strip().splitlines()) == 5


# --------------------------------------------------------------- environment
try:
    import gymnasium                                       # noqa: F401
    from ml.env import EvacuationEnv
    _HAVE_GYM = True
except ImportError:                                        # env tests only
    _HAVE_GYM = False
needs_gym = pytest.mark.skipif(not _HAVE_GYM, reason="gymnasium not installed")


@needs_gym
def test_env_reset_and_step_shapes():
    env = EvacuationEnv(stages=[0])
    obs, info = env.reset(seed=0)
    assert obs.shape == (OBS_SIZE,) and obs.dtype == np.float32
    assert env.observation_space.contains(obs)
    assert info["action_mask"].shape == (N_ACTIONS,)
    obs, reward, terminated, truncated, info = env.step(ACTION_STAY)
    assert env.observation_space.contains(obs)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool) and isinstance(truncated, bool)


@needs_gym
def test_env_passes_the_gymnasium_checker():
    from gymnasium.utils.env_checker import check_env
    check_env(EvacuationEnv(stages=[0]), skip_render_check=True)


@needs_gym
def test_env_is_reproducible_under_a_seed():
    def rollout():
        env = EvacuationEnv(stages=[0, 1, 2])
        obs, info = env.reset(seed=11)
        rng = np.random.default_rng(0)
        trace = [info["stage"]]
        for _ in range(40):
            legal = np.flatnonzero(env.action_masks())
            obs, r, term, trunc, info = env.step(int(rng.choice(legal)))
            trace.append((round(r, 4), float(obs.sum())))
            if term or trunc:
                break
        return trace
    assert rollout() == rollout()


@needs_gym
def test_env_stage_option_and_validation():
    env = EvacuationEnv(stages=[0, 1])
    _, info = env.reset(seed=0, options={"stage": 1})
    assert info["stage"] == 1
    with pytest.raises(ValueError):
        EvacuationEnv(stages=[99])
    with pytest.raises(ValueError):
        env.step(99)


@needs_gym
def test_env_step_before_reset_is_an_error():
    with pytest.raises(RuntimeError):
        EvacuationEnv(stages=[0]).step(ACTION_STAY)


@needs_gym
def test_env_wall_step_costs_a_little():
    env = EvacuationEnv(stages=[0])
    env.reset(seed=0)
    mask = env.action_masks()
    wall = next((a for a in range(1, N_ACTIONS) if not mask[a]), None)
    if wall is None:
        pytest.skip("spawn has no adjacent wall")
    _, r, _, _, info = env.step(wall)
    assert info["invalid"] is True
    assert r < 0


@needs_gym
def test_env_a_stay_only_agent_ends_with_a_loss():
    env = EvacuationEnv(stages=[0])
    env.reset(seed=0)
    total, ended = 0.0, None
    for _ in range(400):
        _, r, term, trunc, info = env.step(ACTION_STAY)
        total += r
        if term or trunc:
            ended = info
            break
    assert ended is not None, "a do-nothing agent should hit the give-up rule"
    assert ended["summary"]["outcome"] == "gave_up"
    assert total < 0


@needs_gym
def test_env_records_an_episode_summary_at_the_end():
    env = EvacuationEnv(stages=[0], max_sim_seconds=3.0)
    env.reset(seed=0)
    info = {}
    for _ in range(400):
        _, _, term, trunc, info = env.step(ACTION_STAY)
        if term or trunc:
            break
    assert info["summary"]["outcome"] in OUTCOMES
