"""Policies: things that turn an observation into an action.

The interface is deliberately tiny -- `act(observation, action_mask) -> int`
-- so the game, the training environment and the evaluation harness all
drive a learned agent the same way, and so this module has no hard
dependency on any RL library. Torch / stable-baselines3 are imported only
when a trained model is actually loaded.

  RandomPolicy   uniform over the legal actions (a sanity baseline)
  StayPolicy     never moves (the floor: it can only ever lose)
  SB3Policy      wraps a model trained with stable-baselines3

A trained model lives at MODEL_PATH. The game only offers the "Learned
model" AI option when model_available() is true, so a checkout with no
trained model plays exactly as before.
"""

import importlib.util
import inspect
import os
import random

import numpy as np

from ml.observation import ACTION_STAY, N_ACTIONS

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "ai_policy.zip")


class RandomPolicy:
    def __init__(self, seed=None):
        self._rng = random.Random(seed)

    def act(self, observation, action_mask):
        legal = [a for a in range(N_ACTIONS) if action_mask[a]]
        return self._rng.choice(legal) if legal else ACTION_STAY


class StayPolicy:
    def act(self, observation, action_mask):
        return ACTION_STAY


class SB3Policy:
    """Adapter around a stable-baselines3 model. If the model supports
    action masking (sb3-contrib's MaskablePPO) the mask is passed to it;
    otherwise an illegal choice is turned into a stay, which is what the
    agent does with a step into a wall anyway."""

    def __init__(self, model, deterministic=True):
        self.model = model
        self.deterministic = deterministic
        try:
            self._maskable = "action_masks" in inspect.signature(model.predict).parameters
        except (TypeError, ValueError):
            self._maskable = False

    def act(self, observation, action_mask):
        obs = np.asarray(observation, dtype=np.float32)
        if self._maskable:
            action, _ = self.model.predict(obs, action_masks=np.asarray(action_mask),
                                           deterministic=self.deterministic)
        else:
            action, _ = self.model.predict(obs, deterministic=self.deterministic)
        action = int(np.asarray(action).reshape(-1)[0])
        if not (0 <= action < N_ACTIONS) or not action_mask[action]:
            return ACTION_STAY
        return action


def model_available(path=MODEL_PATH):
    """True when there is a trained model *and* the library to run it."""
    return (os.path.isfile(path)
            and importlib.util.find_spec("stable_baselines3") is not None)


def load_policy(path=MODEL_PATH):
    """Load a trained model as a Policy. Raises if it can't -- callers
    (the menu, the harness) decide what to do about that."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"no trained model at {path}")
    errors = []
    loaders = []
    if importlib.util.find_spec("sb3_contrib") is not None:
        from sb3_contrib import MaskablePPO
        loaders.append(MaskablePPO)
    from stable_baselines3 import PPO
    loaders.append(PPO)
    for cls in loaders:
        try:
            return SB3Policy(cls.load(path, device="cpu"))
        except Exception as exc:          # wrong algorithm for this file: try the next
            errors.append(f"{cls.__name__}: {exc}")
    raise RuntimeError("could not load " + path + " -- " + "; ".join(errors))
