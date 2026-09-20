"""A* as a teacher: label situations with the move A* would make, and collect
demonstrations for imitation learning.

The A* rescuer decides in two pure steps -- pick a goal (nearest known
occupant, else explore, else the exit; the key if a locked door is in the way),
then run hazard-weighted A* to it -- so "what would A* do from here?" can be
asked of *any* agent standing *anywhere*, with no side effects. That is what
makes two things possible:

  behaviour cloning   record A* playing, as (what it saw, the tile it stepped to)
  DAgger              let a *learner* play, and have A* label the states the
                      learner actually wanders into (imitation's known weakness
                      is that a small mistake leaves the states the teacher
                      ever showed; DAgger adds labels for exactly those)

Demonstrations are gathered through the training environment (ml/env.py), so
they use the identical observation, action interface and reward as everything
else: the expert plays the same one-tile-step game the learner does.

    rows, summary = run_episode(env, stage=0, seed=1)                  # A* plays
    rows, summary = run_episode(env, 0, 1, driver=policy, beta=0.5)    # mixed
"""

import os
import random

import numpy as np

from entities.rescue_agent import RescueAgent
from pathfinding import astar_path
from ml.observation import (
    ACTION_STAY, ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, N_ACTIONS,
    action_mask,
)

_STEP_TO_ACTION = {(0, -1): ACTION_UP, (0, 1): ACTION_DOWN,
                   (-1, 0): ACTION_LEFT, (1, 0): ACTION_RIGHT}


def expert_action(agent, victims):
    """The one-tile step A* would take from where `agent` is right now.

    Works on any RescueAgent-derived body (including the learned agent) and
    changes nothing. It reads what A* reads: the whole real map and the live
    hazard field, plus the occupants that agent has spotted (a learner with a
    narrower view is still labelled with the move A* would make, with A*'s view). Stay when A* would have no move: boxed in, or already at
    the exit with nothing left to do."""
    if agent.is_dead or agent._finished:
        return ACTION_STAY
    goal = RescueAgent._choose_goal_cell(agent, victims)
    path = astar_path(agent.tilemap, agent.current_cell, goal, agent._cost_fn())
    if not path or len(path) < 2:
        return ACTION_STAY
    cc, cr = agent.current_cell
    return _STEP_TO_ACTION.get((path[1][0] - cc, path[1][1] - cr), ACTION_STAY)


class Episode:
    """One episode of (observation, expert label, legal-action mask, reward)."""

    def __init__(self, stage, seed):
        self.stage, self.seed = stage, seed
        self.obs, self.label, self.mask, self.reward = [], [], [], []
        self.summary = None

    def add(self, obs, label, mask, reward):
        self.obs.append(np.asarray(obs, dtype=np.float16))
        self.label.append(label)
        self.mask.append(mask)
        self.reward.append(reward)

    def arrays(self):
        n = len(self.label)
        return dict(
            obs=np.stack(self.obs) if n else np.zeros((0, 1), np.float16),
            label=np.asarray(self.label, dtype=np.int8),
            mask=np.stack(self.mask) if n else np.zeros((0, N_ACTIONS), bool),
            reward=np.asarray(self.reward, dtype=np.float32),
            stage=np.full(n, self.stage, dtype=np.int8),
            seed=np.full(n, self.seed, dtype=np.int32),
        )


def run_episode(env, stage, seed, driver=None, beta=1.0, rng=None):
    """Play one episode, labelling every decision with what A* would do.

    Who acts: with probability `beta` the expert's move is executed, otherwise
    the `driver` policy's (if there is no driver, always the expert). The label
    recorded is the expert's move either way.
    beta=1 -> plain demonstrations; beta=0 -> the learner plays, A* only labels
    (the DAgger setting). Returns (Episode, summary dict)."""
    rng = rng or random.Random(seed)
    obs, _ = env.reset(seed=seed, options={"stage": stage})
    ep = Episode(stage, seed)
    while True:
        session = env._session
        label = expert_action(session.agent, session.victims)
        mask = action_mask(session.agent)
        if driver is None or rng.random() < beta:
            action = label
        else:
            action = driver.act(obs, mask)
        nobs, reward, terminated, truncated, info = env.step(action)
        ep.add(obs, label, mask, reward)
        obs = nobs
        if terminated or truncated:
            ep.summary = info["summary"]
            return ep, ep.summary


# ----------------------------------------------------------- parallel collection
_ENV = None
_DRIVER = None


def _init_worker(driver_path, max_seconds, deterministic, obs_version=1, agent_options=None):
    global _ENV, _DRIVER
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    from ml.env import EvacuationEnv
    _ENV = EvacuationEnv(max_sim_seconds=max_seconds, obs_version=obs_version,
                          agent_options=agent_options)
    if driver_path:
        import torch
        torch.set_num_threads(1)
        from ml.policy import load_policy
        _DRIVER = load_policy(driver_path)
        _DRIVER.deterministic = deterministic


def _task(args):
    stage, seed, beta = args
    ep, summary = run_episode(_ENV, stage, seed, driver=_DRIVER, beta=beta)
    return ep.arrays(), dict(summary, stage=stage, seed=seed, decisions=len(ep.label))


def collect(tasks, driver_path=None, beta=1.0, max_seconds=90.0, workers=1, deterministic=True,
            progress=None, obs_version=1, agent_options=None):
    """Run many episodes; tasks = [(stage_index, seed), ...]. Returns
    (dataset dict of concatenated arrays, list of per-episode summaries)."""
    jobs = [(st, sd, beta) for st, sd in tasks]
    parts, summaries = [], []
    if workers <= 1:
        _init_worker(driver_path, max_seconds, deterministic, obs_version, agent_options)
        results = map(_task, jobs)
    else:
        import multiprocessing
        pool = multiprocessing.get_context("spawn").Pool(
            workers, initializer=_init_worker,
            initargs=(driver_path, max_seconds, deterministic, obs_version, agent_options))
        results = pool.imap(_task, jobs, chunksize=2)
    try:
        for n, (arrays, summary) in enumerate(results, 1):
            parts.append(arrays)
            summaries.append(summary)
            if progress:
                progress(n, len(jobs))
    finally:
        if workers > 1:
            pool.close()
            pool.join()
    data = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    # one id per episode, so validation can be split by episode
    data["episode"] = np.concatenate(
        [np.full(len(p["label"]), i, dtype=np.int32) for i, p in enumerate(parts)])
    return data, summaries
