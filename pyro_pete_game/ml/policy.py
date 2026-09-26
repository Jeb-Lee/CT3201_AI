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
import json
import os
import random

import numpy as np

from ml.observation import ACTION_STAY, N_ACTIONS, obs_version_of

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "ai_policy.zip")


class RandomPolicy:
    obs_version = 1

    def __init__(self, seed=None):
        self._rng = random.Random(seed)

    def act(self, observation, action_mask):
        legal = [a for a in range(N_ACTIONS) if action_mask[a]]
        return self._rng.choice(legal) if legal else ACTION_STAY


class StayPolicy:
    obs_version = 1

    def act(self, observation, action_mask):
        return ACTION_STAY


class SB3Policy:
    """Adapter around a stable-baselines3 model. If the model supports
    action masking (sb3-contrib's MaskablePPO) the mask is passed to it;
    otherwise an illegal choice is turned into a stay, which is what the
    agent does with a step into a wall anyway."""

    def __init__(self, model, deterministic=True, agent_options=None):
        self.model = model
        self.deterministic = deterministic
        # search-order settings the model was trained with (see RescueAgent); the game
        # applies them to the agent body so its observation matches the training one
        self.agent_options = dict(agent_options or {})
        # which observation the network was trained on, read from its input size,
        # so the game builds the right one without being told
        space = getattr(model, "observation_space", None)
        self.obs_version = obs_version_of(space.shape[0]) if space is not None else 1
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


# Models the game menu can offer, in the order shown. A model is offered only when its
# file exists (and stable-baselines3 is installed), so a checkout without a file simply
# has a shorter menu. The key is what the menu passes back; the JSON file next to each
# model (see read_agent_options) tells the game which search-order settings it was trained with.
MODEL_CHOICES = (
    ("v4", "Learned v4", "Cloned from A*, with memory of its path", "ai_v4.zip"),
    ("v5", "Learned v5", "Cloned from a far-side-first searcher", "ai_v5.zip"),
)


def available_models():
    """[(key, label, description, path)] for every menu model whose file is present.
    Needs sb3-contrib as well as stable-baselines3: every model here is a
    MaskablePPO policy, and offering one that cannot load would silently give
    the player A* instead of what they picked."""
    if (importlib.util.find_spec("stable_baselines3") is None
            or importlib.util.find_spec("sb3_contrib") is None):
        return []
    found = [(key, label, desc, os.path.join(MODEL_DIR, name))
             for key, label, desc, name in MODEL_CHOICES
             if os.path.isfile(os.path.join(MODEL_DIR, name))]
    if os.path.isfile(MODEL_PATH):      # a model installed with tools/train_*.py --install
        found.append(("installed", "Learned model", "The model installed as ml/models/ai_policy.zip", MODEL_PATH))
    return found


def model_available(path=MODEL_PATH):
    """True when there is a trained model *and* the library to run it."""
    return (os.path.isfile(path)
            and importlib.util.find_spec("stable_baselines3") is not None)


def options_path(model_path):
    """The small JSON file that sits next to a model (model.zip -> model.json)."""
    return os.path.splitext(model_path)[0] + ".json"


def read_agent_options(model_path):
    """Search-order settings recorded with a model, or {} (a model without a
    JSON file was trained against the default agent)."""
    path = options_path(model_path)
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return dict(json.load(fh).get("agent_options", {}))


def write_agent_options(model_path, agent_options, **notes):
    with open(options_path(model_path), "w", encoding="utf-8") as fh:
        json.dump(dict(agent_options=dict(agent_options), **notes), fh, indent=2)


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
    options = read_agent_options(path)
    for cls in loaders:
        try:
            return SB3Policy(cls.load(path, device="cpu"), agent_options=options)
        except Exception as exc:          # wrong algorithm for this file: try the next
            errors.append(f"{cls.__name__}: {exc}")
    raise RuntimeError("could not load " + path + " -- " + "; ".join(errors))
