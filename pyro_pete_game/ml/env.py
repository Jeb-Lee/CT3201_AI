"""A Gymnasium environment for training the AI rescuer.

The learner *is* the AI player: an episode is one stage played by the AI
alone (no Pete), driven by exactly the same GameSession, hazards, fire,
collapses, locked door and stage-end rules as the real game. Nothing about
the game is re-implemented here -- the environment only steps it.

    from ml.env import EvacuationEnv
    env = EvacuationEnv(stages=range(7))          # train on stages 1-7
    obs, info = env.reset(seed=0)
    obs, reward, terminated, truncated, info = env.step(action)

Actions and observations are defined in ml/observation.py (a flat float32
vector; five discrete actions: stay / up / down / left / right, each a
one-tile step). `env.action_masks()` returns the legal-action mask for
sb3-contrib's MaskablePPO.

Reward is built from the game's own scoring, so what the agent learns to
maximise is what the results screen scores:

    + per occupant led out          (settings.SCORE_PER_SURVIVOR)
    + reaching the exit at the end  (settings.SCORE_REACH_EXIT + speed bonus)
    - health lost                   (settings.SCORE_DAMAGE_PENALTY per point)
    - a flat penalty for dying
    - a small cost per second, and for stepping into a wall
    - optionally, a penalty per occupant still inside when the episode ends
      (RewardConfig.abandon): in the game, giving up means they are lost, and
      without it a policy that simply stands still beats one that explores

There is deliberately no distance-to-goal shaping: paying for "getting
closer" invites an agent that hovers near the exit or a victim without
ever finishing, and this game's dynamics (a spreading fire clock) already
supply time pressure.

`info["summary"]` (outcome, occupants out, score, ...) is added when an episode
ends -- not "episode", which stable-baselines3's Monitor wrapper writes.

Episodes end (terminated) when the game says the stage is over, and are
cut off (truncated) after max_sim_seconds of game time.
"""

import os
import random
from dataclasses import dataclass

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError as exc:                    # pragma: no cover
    raise ImportError(
        "ml.env needs gymnasium:  pip install -r requirements-ml.txt") from exc

import numpy as np

# Headless by default: training must not open a window or need a sound
# device. setdefault so a caller that has already set up pygame wins.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame                                  # noqa: E402

import levels                                  # noqa: E402
from main import GameSession                   # noqa: E402
from settings import (                         # noqa: E402
    SCREEN_WIDTH, SCREEN_HEIGHT,
    SCORE_PER_SURVIVOR, SCORE_REACH_EXIT, SCORE_DAMAGE_PENALTY,
)
from ml.observation import (                   # noqa: E402
    OBS_SIZES, N_ACTIONS, ACTION_STAY, action_mask, build_observation,
)
from ml.outcome import summarise, classify      # noqa: E402

DT = 1 / 30                # game seconds per simulation frame
STAY_FRAMES = 8            # a "stay" lasts about a quarter of a second
MAX_MOVE_FRAMES = 60       # a one-tile step takes ~12 frames; smoke slows it


@dataclass
class RewardConfig:
    occupant: float = float(SCORE_PER_SURVIVOR)
    exit_bonus: float = float(SCORE_REACH_EXIT)
    damage: float = float(SCORE_DAMAGE_PENALTY)     # per point of health lost
    death: float = 100.0
    time_per_second: float = 0.05
    invalid_move: float = 0.2
    # Per occupant not led out when the episode ends. Without it standing
    # still is the best policy (giving up costs ~nothing, exploring risks
    # the death penalty) -- see the docstring above.
    abandon: float = 0.0
    # Extra penalty for each way of failing *without dying*. Experiments in
    # ml/ML_Findings: with none of these, the cheapest failure (giving up,
    # then pacing until the clock runs out) beats trying, so that is what
    # is learned; they exist to test that explanation, not as a fix.
    give_up: float = 0.0      # the AI stood still until it gave up
    timeout: float = 0.0      # the time limit ran out


class _NoKeys:
    """Stands in for pygame's key state. The AI is never keyboard-driven,
    but GameSession.update takes the state for Pete's sake."""

    def __getitem__(self, key):
        return False


_KEYS = _NoKeys()


def _ensure_pygame():
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))


class EvacuationEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, stages=None, max_sim_seconds=240.0, reward=None, obs_version=1, agent_options=None):
        """stages: 0-based stage indices to sample from each episode
        (default: all ten). Train on some and evaluate on others -- a
        policy that has only ever seen the training maps can memorise them."""
        super().__init__()
        _ensure_pygame()
        self.stages = tuple(range(levels.STAGE_COUNT) if stages is None else stages)
        if not self.stages or any(not 0 <= i < levels.STAGE_COUNT for i in self.stages):
            raise ValueError(f"stages must be indices 0..{levels.STAGE_COUNT - 1}")
        self.max_sim_seconds = float(max_sim_seconds)
        self.reward_config = reward or RewardConfig()

        self.action_space = spaces.Discrete(N_ACTIONS)
        self.observation_space = spaces.Box(
            low=-1.0, high=2.0, shape=(OBS_SIZES[obs_version],), dtype=np.float32)
        self.obs_version = obs_version
        self.agent_options = dict(agent_options or {})   # search-order settings, see RescueAgent

        self._sessions = {}
        self._session = None
        self._stage_index = None
        self._prev_saved = 0
        self._prev_damage = 0.0
        self._death_charged = False

    # ------------------------------------------------------------------ API
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        options = options or {}
        if "stage" in options:
            idx = int(options["stage"])
        else:
            idx = int(self.np_random.choice(self.stages))
        # Occupant placement and debris use Python's global RNG, so seed it
        # from the environment's own generator: same gym seed, same episode.
        random.seed(int(self.np_random.integers(0, 2 ** 31 - 1)))

        session = self._sessions.get(idx)
        if session is None:
            session = GameSession(levels.get(idx), spectate=True, agent_visual="drone",
                                  stage_index=idx, agent_brain="learned", policy=None,
                                  agent_options=self.agent_options)
            self._sessions[idx] = session
        else:
            session.reset()
        self._session, self._stage_index = session, idx
        self._prev_saved = 0
        self._prev_damage = 0.0
        self._death_charged = False
        return self._observe(), self._info()

    def step(self, action):
        if self._session is None:
            raise RuntimeError("call reset() before step()")
        action = int(action)
        if not 0 <= action < N_ACTIONS:
            raise ValueError(f"action must be in 0..{N_ACTIONS - 1}, got {action}")

        s = self._session
        agent = s.agent
        cfg = self.reward_config
        stats = s.agent_stats

        invalid = action != ACTION_STAY and not action_mask(agent)[action]
        t0 = stats.elapsed
        agent.command(action)

        s.update(DT, _KEYS)
        frames = 1
        if s.state == "playing":
            if agent._waypoints:                       # started walking a tile
                while s.state == "playing" and agent._waypoints and frames < MAX_MOVE_FRAMES:
                    s.update(DT, _KEYS)
                    frames += 1
            else:                                       # stayed put
                while s.state == "playing" and frames < STAY_FRAMES:
                    s.update(DT, _KEYS)
                    frames += 1

        reward = cfg.occupant * (stats.victims_saved - self._prev_saved)
        reward -= cfg.damage * (stats.damage_taken - self._prev_damage)
        reward -= cfg.time_per_second * max(0.0, stats.elapsed - t0)
        if invalid:
            reward -= cfg.invalid_move
        self._prev_saved = stats.victims_saved
        self._prev_damage = stats.damage_taken

        terminated = s.state != "playing"
        if agent.is_dead and not self._death_charged:
            reward -= cfg.death
            self._death_charged = True
        if terminated and s.evacuated and not agent.is_dead:
            reward += cfg.exit_bonus + stats.time_bonus
        truncated = (not terminated) and stats.elapsed >= self.max_sim_seconds
        if terminated or truncated:
            reward -= cfg.abandon * (len(s.victims) - s.victims_out)
        if terminated and cfg.give_up and classify(s) == "gave_up":
            reward -= cfg.give_up
        if truncated:
            reward -= cfg.timeout

        info = self._info()
        info["invalid"] = bool(invalid)
        if terminated or truncated:
            info["summary"] = summarise(s)
        return self._observe(), float(reward), terminated, truncated, info

    def action_masks(self):
        """bool[N_ACTIONS] of legal actions -- for sb3-contrib MaskablePPO."""
        return action_mask(self._session.agent)

    # ------------------------------------------------------------ internals
    def _observe(self):
        return build_observation(self._session.agent, self._session.victims, self.obs_version)

    def _info(self):
        return {"stage": self._stage_index,
                "action_mask": action_mask(self._session.agent)}
