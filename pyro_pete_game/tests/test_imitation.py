"""Checks for imitation learning: A* as a teacher, demonstrations, cloning, DAgger data.

Needs stable-baselines3 + gymnasium (skips cleanly without them). Run:
    python -m pytest     (from pyro_pete_game/)
"""

import importlib.util
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

HAVE = (importlib.util.find_spec("stable_baselines3") is not None
        and importlib.util.find_spec("gymnasium") is not None)
pytestmark = pytest.mark.skipif(not HAVE, reason="stable-baselines3 / gymnasium not installed")

if HAVE:
    import torch
    from ml import expert, imitation
    from ml.env import EvacuationEnv
    from ml.observation import (OBS_SIZE, N_ACTIONS, ACTION_STAY, action_mask, build_observation)
    from ml.policy import load_policy


@pytest.fixture(scope="module")
def env():
    return EvacuationEnv(max_sim_seconds=60.0)


# ------------------------------------------------------------------ the teacher
def test_expert_action_is_legal_and_changes_nothing(env):
    env.reset(seed=3, options={"stage": 0})
    s = env._session
    before = (s.agent.current_cell, list(s.agent._waypoints), s.agent._goal_cell,
              set(s.agent.explored), s.agent.health)
    a1 = expert.expert_action(s.agent, s.victims)
    a2 = expert.expert_action(s.agent, s.victims)
    after = (s.agent.current_cell, list(s.agent._waypoints), s.agent._goal_cell,
             set(s.agent.explored), s.agent.health)
    assert a1 == a2 and before == after
    assert action_mask(s.agent)[a1]


def test_expert_stays_when_it_has_nothing_to_do(env):
    env.reset(seed=3, options={"stage": 0})
    agent = env._session.agent
    agent._finished = True
    assert expert.expert_action(agent, env._session.victims) == ACTION_STAY


def test_expert_plays_a_stage_and_every_label_is_legal(env):
    ep, summary = expert.run_episode(env, 0, 11)
    a = ep.arrays()
    n = len(a["label"])
    assert n > 10
    assert a["obs"].shape == (n, OBS_SIZE) and a["obs"].dtype == np.float16
    assert a["mask"].shape == (n, N_ACTIONS)
    assert a["mask"][np.arange(n), a["label"]].all()          # never an illegal move
    assert summary["outcome"] == "evacuated"                   # stage 1 is A*'s easy one
    assert (a["stage"] == 0).all() and (a["seed"] == 11).all()


def test_expert_runs_are_reproducible(env):
    a = expert.run_episode(env, 1, 5)[0].arrays()
    b = expert.run_episode(env, 1, 5)[0].arrays()
    assert np.array_equal(a["label"], b["label"])
    assert np.array_equal(a["obs"], b["obs"])


def test_the_teacher_rarely_stands_still(env):
    """The whole point: unlike the RL runs, the data does not reward standing still."""
    labels = np.concatenate([expert.run_episode(env, st, 20 + st)[0].arrays()["label"]
                             for st in (0, 2, 4)])
    assert (labels == ACTION_STAY).mean() < 0.1


def test_learner_drives_when_beta_is_zero_but_expert_still_labels(env):
    class AlwaysStay:
        def act(self, obs, mask):
            return ACTION_STAY
    ep, summary = expert.run_episode(env, 0, 7, driver=AlwaysStay(), beta=0.0)
    labels = np.asarray(ep.label)
    assert (labels != ACTION_STAY).mean() > 0.5               # A* wanted to move...
    assert summary["outcome"] in ("gave_up", "died", "timeout")  # ...but the learner never did
    assert summary["victims_out"] == 0


def test_collect_returns_arrays_and_summaries():
    data, summaries = expert.collect([(0, 1), (0, 2), (1, 3)], workers=1, max_seconds=60.0)
    assert len(summaries) == 3
    n = len(data["label"])
    assert data["obs"].shape[0] == n == len(data["episode"]) == len(data["stage"])
    assert sorted(set(data["episode"].tolist())) == [0, 1, 2]
    assert set(data["stage"].tolist()) == {0, 1}


def test_merge_keeps_episode_ids_distinct():
    a, _ = expert.collect([(0, 1)], workers=1, max_seconds=60.0)
    b, _ = expert.collect([(0, 2)], workers=1, max_seconds=60.0)
    m = imitation.merge(a, b)
    assert len(m["label"]) == len(a["label"]) + len(b["label"])
    assert len(set(m["episode"].tolist())) == 2
    assert imitation.merge({}, b) is b


# --------------------------------------------------------------------- learning
@pytest.fixture(scope="module")
def tiny():
    data, _ = expert.collect([(0, 1), (0, 2), (1, 3), (2, 4)], workers=1, max_seconds=60.0)
    return data


def test_masked_logits_never_pick_an_illegal_action(tiny):
    model, e = imitation.build_model(seed=0, net_arch=(32,))
    try:
        idx = np.arange(min(200, len(tiny["label"])))
        obs, _, mask = imitation._to_tensors(tiny, idx)
        pred = imitation.masked_logits(model.policy, obs, mask).argmax(1).numpy()
        assert mask.numpy()[np.arange(len(idx)), pred].all()
    finally:
        e.close()


def test_cloning_learns_the_teachers_moves(tiny, tmp_path):
    """On a tiny dataset the network should be able to fit A*'s moves -- accuracy
    rises well above where it starts."""
    model, e = imitation.build_model(seed=0, net_arch=(128,))
    try:
        data = dict(train=tiny, val=tiny, unseen={})
        _, before, _ = imitation.action_accuracy(model.policy, tiny)
        hist = imitation.train_bc(model, data, str(tmp_path), epochs=40, batch=128, lr=2e-3,
                                  game_every=0, log=lambda *a: None)
        assert hist[-1]["train_acc"] > 0.9
        assert hist[-1]["val_seen_acc"] > before + 0.3
        assert hist[-1]["train_loss"] < hist[0]["train_loss"]
        # the log has one row per epoch with the accuracy columns
        rows = open(tmp_path / "epochs.csv").read().strip().splitlines()
        assert rows[0].startswith("epoch,") and len(rows) == 41
        # a cloned model loads through the game's own loader and answers with a legal move
        policy = load_policy(str(tmp_path / "bc_model.zip"))
        env = EvacuationEnv(max_sim_seconds=30.0)
        obs, info = env.reset(seed=9, options={"stage": 0})
        assert info["action_mask"][policy.act(obs, info["action_mask"])]
    finally:
        e.close()


def test_action_accuracy_on_nothing_is_nan():
    model, e = imitation.build_model(seed=0, net_arch=(16,))
    try:
        loss, acc, stay = imitation.action_accuracy(model.policy, {})
        assert loss != loss and acc != acc
    finally:
        e.close()


def test_best_epoch_is_chosen_on_seen_stages_not_unseen(tiny, tmp_path):
    """Model selection must not peek at the unseen stages, or they stop being a test."""
    import inspect
    src = inspect.getsource(imitation.train_bc)
    assert "vacc > best[0]" in src and "uacc > best" not in src


def test_cloned_model_can_be_rolled_out_as_a_dagger_driver(tiny, tmp_path):
    model, e = imitation.build_model(seed=0, net_arch=(64,))
    try:
        imitation.train_bc(model, dict(train=tiny, val=tiny, unseen={}), str(tmp_path), epochs=5,
                           batch=128, game_every=0, log=lambda *a: None)
        path = str(tmp_path / "bc_model.zip")
        data, summaries = expert.collect([(0, 31), (0, 32)], driver_path=path, beta=0.0,
                                         workers=1, max_seconds=30.0)
        assert len(summaries) == 2 and len(data["label"]) > 0
        assert data["mask"][np.arange(len(data["label"])), data["label"]].all()
    finally:
        e.close()


def test_imitation_chart_draws_from_the_logs(tmp_path):
    pytest.importorskip("matplotlib")
    from ml.imitation_report import plot_imitation
    from ml.report import CsvLog
    log = CsvLog(str(tmp_path / "epochs.csv"), imitation.EPOCH_FIELDS)
    for e in range(1, 6):
        log.write(dict(epoch=e, train_loss=1.0 / e, train_acc=0.5 + e / 20, val_seen_acc=0.5 + e / 22,
                       val_unseen_acc=0.45 + e / 25, game_seen_evac=(e / 10 if e % 5 == 0 else None),
                       game_unseen_evac=(e / 12 if e % 5 == 0 else None)))
    log.close()
    (tmp_path / "baseline.json").write_text('{"seen_evac": 0.9, "unseen_evac": 0.8}')
    path = plot_imitation(str(tmp_path))
    assert path and os.path.getsize(path) > 5000


# ------------------------------------------------- observation version 2 (route hints)
def _v2_env():
    return EvacuationEnv(max_sim_seconds=60.0, obs_version=2)


def _open_door(session):
    """Put the game where every stage soon is: the key collected, the door open (the
    same two things doors.try_pickup does). Every stage starts with the spawn sealed
    behind a locked door, so 'the exit is reachable' needs this."""
    doors = session.hazards.doors
    doors.key_collected = True
    for d in doors.doors:
        session.tilemap.unblock_cell(d)


def _open_game(stage=3, seed=4, version=2):
    e = EvacuationEnv(max_sim_seconds=60.0, obs_version=version)
    e.reset(seed=seed, options={"stage": stage})
    _open_door(e._session)
    return e, e._session, e._session.agent


def test_version_2_extends_version_1_and_leaves_it_untouched():
    from ml.observation import OBS_SIZE_V2, N_HINT, obs_version_of
    assert OBS_SIZE_V2 == OBS_SIZE + N_HINT and N_HINT == 24
    assert obs_version_of(OBS_SIZE) == 1 and obs_version_of(OBS_SIZE_V2) == 2
    with pytest.raises(ValueError):
        obs_version_of(123)
    e = _v2_env()
    obs2, _ = e.reset(seed=4, options={"stage": 0})
    a = e._session.agent
    obs1 = build_observation(a, e._session.victims, 1)
    assert obs2.shape == (OBS_SIZE_V2,) and obs2.dtype == np.float32
    assert np.array_equal(obs2[:OBS_SIZE], obs1)


def test_every_stage_starts_behind_a_locked_door_so_the_key_is_the_first_goal():
    """The fact that made the key hint necessary: at spawn the exit is unreachable on
    all ten stages, and A* itself heads for the key."""
    from ml.observation import route_hints, HINT_FIELDS
    n = len(HINT_FIELDS)
    e = _v2_env()
    for stage in range(10):
        e.reset(seed=4, options={"stage": stage})
        a = e._session.agent
        hints = route_hints(a, e._session.victims)
        assert hints[0] == 0.0, f"stage {stage + 1}: exit unexpectedly reachable at spawn"
        assert hints[3 * n] == 1.0, f"stage {stage + 1}: no key hint"


def test_the_exit_hint_points_the_way_a_star_would_step():
    from ml.observation import route_hints, HINT_FIELDS, MOVES
    from pathfinding import astar_path
    e, s, a = _open_game()
    hints = route_hints(a, s.victims)
    exit_block = hints[:len(HINT_FIELDS)]
    assert exit_block[0] == 1.0
    path = astar_path(a.tilemap, a.current_cell, a.tilemap.exit_cell, a._cost_fn())
    step = (path[1][0] - a.current_cell[0], path[1][1] - a.current_cell[1])
    advance = exit_block[1:5]                                       # up, down, left, right
    best = [i for i, act in enumerate((1, 2, 3, 4)) if MOVES[act] == step][0]
    assert advance[best] == advance.max() and advance[best] > 0


def test_occupant_and_frontier_hints_only_exist_when_there_is_something_to_go_to():
    from ml.observation import route_hints, HINT_FIELDS
    from pathfinding import weighted_distances
    e, s, a = _open_game()
    n = len(HINT_FIELDS)
    a.known_victims.clear()
    none = route_hints(a, s.victims)
    assert none[n] == 0.0 and not none[n + 1:2 * n].any()            # no spotted occupant
    reach = weighted_distances(a.tilemap, a.current_cell, a._cost_fn())
    v = next(v for v in s.victims if v.cell in reach)
    a.known_victims.add(v)
    some = route_hints(a, s.victims)
    assert some[n] == 1.0 and some[n + 5] > 0                        # spotted: it is hinted at
    assert some[2 * n] == 1.0                                       # unexplored ground remains


def test_a_walled_direction_is_marked_as_the_worst_move():
    from ml.observation import route_hints, HINT_FIELDS, HINT_GOALS
    e, s, a = _open_game()
    hints = route_hints(a, s.victims)
    mask = action_mask(a)
    n = len(HINT_FIELDS)
    checked = 0
    for g in range(len(HINT_GOALS)):
        if hints[g * n] == 1.0:
            for k, act in enumerate((1, 2, 3, 4)):
                if not mask[act]:
                    assert hints[g * n + 1 + k] == -1.0
                    checked += 1
    assert checked > 0


def test_a_version_2_policy_is_given_a_version_2_observation():
    """The game asks the policy which observation it wants, so a v2 model just works."""
    from ml.observation import OBS_SIZE_V2
    seen = []

    class Recorder:
        obs_version = 2

        def act(self, observation, mask):
            seen.append(observation.shape[0])
            return ACTION_STAY

    from main import GameSession
    import levels
    random.seed(1)
    s = GameSession(levels.get(0), spectate=True, agent_visual="drone", stage_index=0,
                    agent_brain="learned", policy=Recorder())

    class K:
        def __getitem__(self, k):
            return False
    for _ in range(60):
        s.update(1 / 30, K())
    assert seen and set(seen) == {OBS_SIZE_V2}


def test_sb3_policy_reads_the_observation_version_from_the_networks_input_size():
    from ml.policy import SB3Policy
    for version, size in ((1, OBS_SIZE), (2, OBS_SIZE + 24), (3, OBS_SIZE + 24 + 17),
                          (4, OBS_SIZE + 24 + 17 + 121)):
        class Space:
            shape = (size,)

        class FakeModel:
            observation_space = Space()

            def predict(self, obs, deterministic=True):
                return np.array([0]), None
        assert SB3Policy(FakeModel()).obs_version == version


# ------------------------------------------------ information parity with A* (no God mode)
def _far_floor_cell(agent, exclude):
    from settings import AGENT_VISION_TILES
    tm = agent.tilemap
    cc, cr = agent.current_cell
    for col in range(tm.cols - 1, 0, -1):
        for row in range(tm.rows - 1, 0, -1):
            if (tm.is_walkable(col, row) and (col, row) != exclude
                    and (col - cc) ** 2 + (row - cr) ** 2 > (AGENT_VISION_TILES + 4) ** 2):
                return (col, row)
    raise AssertionError("no far floor cell")


@pytest.mark.parametrize("version", [1, 2, 3, 4])
def test_moving_an_occupant_the_agent_has_not_spotted_changes_nothing_it_sees(version):
    """No God mode: A* cannot see an unspotted occupant, so neither the learner's
    observation nor A*'s own decision may depend on where one is."""
    from settings import AGENT_VISION_TILES
    e, s, a = _open_game(version=version)
    tm = a.tilemap
    v = s.victims[0]
    cc, cr = a.current_cell
    assert (v.cell[0] - cc) ** 2 + (v.cell[1] - cr) ** 2 > AGENT_VISION_TILES ** 2
    a.known_victims.discard(v)
    before_obs = build_observation(a, s.victims, version)
    before_label = expert.expert_action(a, s.victims)
    new_cell = _far_floor_cell(a, v.cell)
    v.cell = new_cell
    v.x, v.y = tm.cell_center(*new_cell)
    assert v not in a.known_victims
    assert np.array_equal(before_obs, build_observation(a, s.victims, version))
    assert before_label == expert.expert_action(a, s.victims)


def test_spotting_an_occupant_does_change_what_the_learner_sees():
    """...and the other direction: once an occupant IS spotted the observation must
    reflect it (otherwise the learner would have less than A*)."""
    from ml.observation import route_hints, HINT_FIELDS
    from pathfinding import weighted_distances
    e, s, a = _open_game()
    a.known_victims.clear()
    n = len(HINT_FIELDS)
    reach = weighted_distances(a.tilemap, a.current_cell, a._cost_fn())
    v = next(v for v in s.victims if v.cell in reach)
    hidden = route_hints(a, s.victims)
    a.known_victims.add(v)
    seen = route_hints(a, s.victims)
    assert hidden[n] == 0.0 and seen[n] == 1.0


def test_the_hints_read_only_agent_knowledge_not_the_list_of_all_occupants():
    """route_hints takes the victim list for the interface's sake; it must not use it
    (unspotted occupants are hidden from A*, so from the hints)."""
    from ml.observation import route_hints
    e, s, a = _open_game()
    assert np.array_equal(route_hints(a, s.victims), route_hints(a, []))


def test_the_learner_and_a_star_share_one_body_and_one_game():
    """Same stage, same seed: the same map, occupants, hazards, speed and health;
    only the decision-maker differs."""
    from main import GameSession
    from ml.policy import StayPolicy
    import levels
    for stage in (0, 4, 8):
        sessions = []
        for brain, policy in (("astar", None), ("learned", StayPolicy())):
            random.seed(17)
            sessions.append(GameSession(levels.get(stage), spectate=True, agent_visual="drone",
                                        stage_index=stage, agent_brain=brain, policy=policy))
        A, L = sessions
        assert A.tilemap.exit_cell == L.tilemap.exit_cell
        assert A.tilemap.spawn_cell == L.tilemap.spawn_cell
        assert [v.cell for v in A.victims] == [v.cell for v in L.victims]
        assert A.hazards.doors.key_cell == L.hazards.doors.key_cell
        assert A.hazards.fire.burning == L.hazards.fire.burning
        assert A.agent.speed_scale == L.agent.speed_scale
        assert A.agent.health == L.agent.health
        assert A.agent.current_cell == L.agent.current_cell
        from entities.rescue_agent import RescueAgent
        assert isinstance(A.agent, RescueAgent) and isinstance(L.agent, RescueAgent)   # one body


# ------------------------------------------------- observation versions 3 and 4 (memory)
def _memory_game(version, stage=3, seed=4):
    e = EvacuationEnv(max_sim_seconds=60.0, obs_version=version)
    e.reset(seed=seed, options={"stage": stage})
    _open_door(e._session)
    return e, e._session, e._session.agent


def _walk(e, n):
    """Take n legal, non-stay moves; returns the actions."""
    done = []
    for _ in range(n):
        mask = e.action_masks()
        act = next(a for a in (4, 2, 3, 1) if mask[a])
        e.step(act)
        done.append(act)
    return done


def test_versions_3_and_4_extend_version_2():
    from ml.observation import OBS_SIZE_V3, OBS_SIZE_V4, N_MEMORY, N_TRAIL, OBS_SIZE_V2
    assert OBS_SIZE_V3 == OBS_SIZE_V2 + N_MEMORY == OBS_SIZE + 24 + 17
    assert OBS_SIZE_V4 == OBS_SIZE_V3 + N_TRAIL == OBS_SIZE_V3 + 121
    for version in (3, 4):
        e = EvacuationEnv(max_sim_seconds=60.0, obs_version=version)
        obs, _ = e.reset(seed=4, options={"stage": 3})
        s = e._session
        assert obs.shape == (OBS_SIZES_[version],)
        assert np.array_equal(obs[:OBS_SIZE_V2], build_observation(s.agent, s.victims, 2))


OBS_SIZES_ = {}
if HAVE:
    from ml.observation import OBS_SIZES as OBS_SIZES_


def test_memory_starts_empty_every_episode():
    """The rule the project owner asked for: it starts with nothing, on every episode."""
    from ml.observation import memory_features, trail_window, N_ACTIONS
    e, s, a = _memory_game(4)
    _walk(e, 5)
    assert len(a.cell_history) > 1
    e.reset(seed=4, options={"stage": 3})                      # a new episode, same stage
    a = e._session.agent
    assert a.cell_history == [a.current_cell] and a.visit_counts == {a.current_cell: 1}
    mem = memory_features(a)
    assert mem[0] == 1.0 and mem[1:].sum() == 0.0              # 'last move: stay' and nothing else
    trail = trail_window(a)
    assert np.count_nonzero(trail) == 1                        # only the tile it stands on


def test_memory_records_the_previous_move_and_the_tiles_it_came_from():
    from ml.observation import memory_features, N_ACTIONS, MOVES
    e, s, a = _memory_game(3)
    acts = _walk(e, 3)
    mem = memory_features(a)
    assert mem[acts[-1]] == 1.0 and mem[:N_ACTIONS].sum() == 1.0            # last move, one-hot
    prev = a.cell_history[-2] if a.cell_history[-1] == a.current_cell else a.cell_history[-1]
    dc, dr = MOVES[acts[-1]]
    assert (prev[0] - a.current_cell[0], prev[1] - a.current_cell[1]) == (-dc, -dr)   # it came from behind
    assert mem[N_ACTIONS] == pytest.approx(-dc / 5.0) and mem[N_ACTIONS + 1] == pytest.approx(-dr / 5.0)
    assert mem[N_ACTIONS + 2] == 1.0                                        # slot filled


def test_the_trail_counts_visits_and_only_visits():
    """Going A -> B -> A must count A twice; a tile it never entered must read zero."""
    from ml.observation import trail_window, WINDOW, WINDOW_RADIUS, TRAIL_CAP, MOVES
    e, s, a = _memory_game(4)
    start = a.current_cell
    mask = e.action_masks()
    out = next(x for x in (4, 2, 3, 1) if mask[x])
    back = {1: 2, 2: 1, 3: 4, 4: 3}[out]
    e.step(out)
    e.step(back)
    assert a.current_cell == start and a.visit_counts[start] == 2
    trail = trail_window(a).reshape(WINDOW, WINDOW)
    assert trail[WINDOW_RADIUS, WINDOW_RADIUS] == pytest.approx(2 / TRAIL_CAP)
    walked = set(a.visit_counts)
    for wy in range(WINDOW):
        for wx in range(WINDOW):
            cell = (start[0] + wx - WINDOW_RADIUS, start[1] + wy - WINDOW_RADIUS)
            if cell not in walked:
                assert trail[wy, wx] == 0.0


def test_memory_only_ever_holds_tiles_the_agent_actually_stood_on():
    e, s, a = _memory_game(4)
    _walk(e, 8)
    assert set(a.cell_history) <= a.trail_cells                    # A*'s own record of walked tiles
    assert set(a.visit_counts) == set(a.cell_history)
    assert all(n >= 1 for n in a.visit_counts.values())


def test_the_learned_agent_still_shares_astars_update_and_hazard_rules():
    from entities.learned_agent import LearnedAgent
    from entities.rescue_agent import RescueAgent
    for name in ("update", "_apply_hazards", "draw"):
        if hasattr(RescueAgent, name):
            assert getattr(LearnedAgent, name) is getattr(RescueAgent, name)
