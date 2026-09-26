"""Training support: build the model, watch it learn, keep the records.

Needs stable-baselines3 (pip install -r requirements-ml.txt); nothing else
in the game imports this module. Driven by tools/train_agent.py.

TrainingMonitor is the part that answers "is it learning, and how well?":

  every epoch      -> a row in epochs.csv (accuracy over the last N training
                      episodes, game score, reward, optimiser loss/entropy)
  every checkpoint -> the model plays fixed, seeded episodes with the
                      deterministic policy on training stages and on stages
                      it has never trained on; the A* AI plays the very same
                      episodes once at the start as the yardstick
                   -> a checkpoint file, best_model.zip if it is the best so
                      far, and screen recordings of it playing
                   -> the chart and report.html are rebuilt

Held-out stages are the honest number: a policy can score well on maps it
has trained on simply by memorising them. The best model is picked on the
held-out validation episodes, which makes that number slightly optimistic,
so the script finishes with a fresh-seed test (see final_test).
"""

import os
import shutil
import time
from collections import deque

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

import levels
from ml import evaluation
from ml.policy import SB3Policy
from ml.recording import record_episode
from ml.report import (CsvLog, EPOCH_FIELDS, EVAL_FIELDS, read_csv, last_epoch,
                       write_report)

TRAIN_SEED_BASE = 0            # only used to name things; training seeds come from the env
EVAL_SEED_BASE = 50_000        # validation episodes during training
FINAL_SEED_BASE = 90_000       # the fresh-seed test at the end
RECORD_SEED = 7


# ------------------------------------------------------------------ building
def make_train_env(stages, n_envs, seed, max_seconds, gamma=0.995, reward=None, obs_version=1):
    """Parallel game processes. Rewards are scaled for the optimiser (an
    episode is worth hundreds of points, which makes the value network's
    targets huge); observations are already ~unit range and are left alone,
    so a saved model needs no normaliser to be used in the game. The logged
    accuracy / score / reward are the raw game numbers (Monitor sits below)."""
    from stable_baselines3.common.env_util import make_vec_env
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecNormalize
    from ml.env import EvacuationEnv
    env = make_vec_env(EvacuationEnv, n_envs=n_envs, seed=seed,
                       vec_env_cls=SubprocVecEnv if n_envs > 1 else DummyVecEnv,
                       env_kwargs=dict(stages=list(stages), max_sim_seconds=max_seconds,
                                       reward=reward, obs_version=obs_version))
    return VecNormalize(env, norm_obs=False, norm_reward=True, gamma=gamma)


def make_model(algo, env, seed, device="cpu", n_steps=512, batch_size=256,
               update_epochs=4, learning_rate=3e-4, gamma=0.995, ent_coef=0.01,
               net_arch=(256, 256)):
    """PPO with an MLP. `algo` is 'maskable' (sb3-contrib MaskablePPO, never
    wastes a step on a wall) or 'ppo' (plain; walls are a small penalty)."""
    kwargs = dict(n_steps=n_steps, batch_size=batch_size, n_epochs=update_epochs,
                  learning_rate=learning_rate, gamma=gamma, gae_lambda=0.95,
                  ent_coef=ent_coef, seed=seed, device=device, verbose=0,
                  policy_kwargs=dict(net_arch=list(net_arch)))
    if algo == "maskable":
        from sb3_contrib import MaskablePPO
        return MaskablePPO("MlpPolicy", env, **kwargs)
    if algo == "ppo":
        from stable_baselines3 import PPO
        return PPO("MlpPolicy", env, **kwargs)
    raise ValueError(f"algo must be 'maskable' or 'ppo', got {algo!r}")


def load_for_training(algo, path, env, device="cpu"):
    if algo == "maskable":
        from sb3_contrib import MaskablePPO
        return MaskablePPO.load(path, env=env, device=device)
    from stable_baselines3 import PPO
    return PPO.load(path, env=env, device=device)


# ---------------------------------------------------------------- evaluation
def evaluate_split(label, policy, stages, episodes, base_seed, max_seconds):
    """Play `episodes` fixed-seed episodes on each stage. policy=None with
    label 'astar' plays the A* AI. Same seeds => same layouts for everyone."""
    out = []
    for st in stages:
        for i in range(episodes):
            out.append(evaluation.run_episode(
                label, st, evaluation.episode_seed(base_seed, st, i),
                max_seconds=max_seconds, policy=policy))
    return out


def eval_row(agent, split, stages, results, epoch, timesteps):
    s = evaluation.summarise_group(results)
    lo, hi = s["evacuated_ci"]
    return {"epoch": epoch, "timesteps": timesteps, "agent": agent, "split": split,
            "stages": " ".join(str(st + 1) for st in stages), "episodes": s["n"],
            "accuracy": s["evacuated"], "accuracy_lo": lo, "accuracy_hi": hi,
            "died": s["died"], "gave_up": s["gave_up"], "timeout": s["timeout"],
            "occupants_out": s["occupants_out"], "score": s["score"],
            "score_ci": s["score_ci"], "seconds": s["seconds"]}


def _fmt_steps(n):
    return f"{n:,}"


# ------------------------------------------------------------------- monitor
class TrainingMonitor(BaseCallback):
    def __init__(self, run_dir, train_stages, heldout_stages, eval_every=100_000,
                 eval_episodes=6, max_seconds=180.0, record_every=1,
                 record_stages=(), window=100, print_every=5, max_minutes=None,
                 video_speed=2.0):
        super().__init__(verbose=0)
        self.run_dir = run_dir
        self.train_stages = list(train_stages)
        self.heldout_stages = list(heldout_stages)
        self.eval_every = int(eval_every)
        self.eval_episodes = int(eval_episodes)
        self.max_seconds = float(max_seconds)
        self.record_every = int(record_every)
        self.record_stages = list(record_stages)
        self.window = int(window)
        self.print_every = max(1, int(print_every))
        self.max_minutes = max_minutes
        self.video_speed = video_speed

        os.makedirs(os.path.join(run_dir, "checkpoints"), exist_ok=True)
        self.epochs_log = CsvLog(os.path.join(run_dir, "epochs.csv"), EPOCH_FIELDS)
        self.evals_log = CsvLog(os.path.join(run_dir, "evaluations.csv"), EVAL_FIELDS)

        self._recent = deque(maxlen=self.window)     # (outcome, occ_frac, score, reward, length)
        self._epoch_results = []
        self._episodes_total = 0
        self._epoch = last_epoch(run_dir)
        self._pending = None
        self._t0 = time.time()
        self._last_flush = (time.time(), 0)
        self._next_eval = 0
        self._evals_done = 0
        self._best = None                            # (score, epoch)
        self._finished = False
        self._stop = False

    # ---------------------------------------------------------- callback API
    def _on_training_start(self):
        self._t0 = time.time()
        self._last_flush = (time.time(), self.num_timesteps)
        self._next_eval = self.num_timesteps + self.eval_every
        old = read_csv(os.path.join(self.run_dir, "evaluations.csv"))
        model_rows = [r for r in old if r["agent"] == "model"]
        sel = "heldout" if self.heldout_stages else "train"
        scored = [r for r in model_rows if r["split"] == sel and r["score"] is not None]
        if scored:
            top = max(scored, key=lambda r: r["score"])
            self._best = (top["score"], top["epoch"])
        self._evals_done = len({r["timesteps"] for r in model_rows})
        if not any(r["agent"] == "astar" for r in old):
            self._baseline()
        if not model_rows:
            self._evaluate(self._epoch, self.num_timesteps)      # the untrained starting point

    def _on_rollout_start(self):
        self._flush()

    def _on_step(self):
        infos, dones = self.locals["infos"], self.locals["dones"]
        for info, done in zip(infos, dones):
            summ = info.get("summary")
            if not done or summ is None:
                continue
            mon = info.get("episode") or {}
            total = max(1, summ["victims_total"])
            item = (summ["outcome"], summ["victims_out"] / total, summ["score"],
                    mon.get("r"), mon.get("l"))
            self._recent.append(item)
            self._epoch_results.append(item)
            self._episodes_total += 1
        if self.max_minutes and (time.time() - self._t0) / 60 >= self.max_minutes:
            print(f"\nreached --max-minutes {self.max_minutes}: stopping", flush=True)
            self._stop = True
            return False
        return True

    def _on_rollout_end(self):
        self._epoch += 1
        recent = list(self._recent)

        def rate(items, outcome):
            return (sum(1 for x in items if x[0] == outcome) / len(items)) if items else None

        def mean(items, idx):
            vals = [x[idx] for x in items if x[idx] is not None]
            return float(np.mean(vals)) if vals else None

        this = self._epoch_results
        self._pending = {
            "epoch": self._epoch, "timesteps": self.num_timesteps,
            "episodes_total": self._episodes_total, "window_episodes": len(recent),
            "train_accuracy": rate(recent, "evacuated"), "died": rate(recent, "died"),
            "gave_up": rate(recent, "gave_up"), "timeout": rate(recent, "timeout"),
            "occupants_out": mean(recent, 1), "score": mean(recent, 2),
            "reward": mean(recent, 3), "episode_len": mean(recent, 4),
            "epoch_episodes": len(this), "epoch_accuracy": rate(this, "evacuated"),
        }
        self._epoch_results = []

    def _on_training_end(self):
        self.finish()

    # ------------------------------------------------------------- internals
    def finish(self):
        """Write the last epoch, a final checkpoint evaluation, the report.
        Safe to call twice (Ctrl+C calls it from the script)."""
        if self._finished:
            return
        self._finished = True
        self._flush(force_eval=True)
        self.evals_log.close()
        self.epochs_log.close()
        write_report(self.run_dir, live=False)

    def _flush(self, force_eval=False):
        row = self._pending
        if row is not None:
            self._pending = None
            vals = self.model.logger.name_to_value      # the update that followed this batch
            ent = vals.get("train/entropy_loss")
            row.update(
                policy_loss=vals.get("train/policy_gradient_loss"),
                value_loss=vals.get("train/value_loss"),
                entropy=None if ent is None else -ent,
                approx_kl=vals.get("train/approx_kl"),
                clip_fraction=vals.get("train/clip_fraction"),
                explained_variance=vals.get("train/explained_variance"),
                learning_rate=vals.get("train/learning_rate"))
            now = time.time()
            prev_t, prev_steps = self._last_flush
            row["wall_seconds"] = now - self._t0
            row["steps_per_second"] = (row["timesteps"] - prev_steps) / max(1e-6, now - prev_t)
            self._last_flush = (now, row["timesteps"])
            self.epochs_log.write(row)
            if row["epoch"] % self.print_every == 0 or row["epoch"] == 1:
                self._print_epoch(row)
        if row is not None and (force_eval or self.num_timesteps >= self._next_eval):
            while self._next_eval <= self.num_timesteps:
                self._next_eval += self.eval_every
            self._evaluate(row["epoch"], row["timesteps"])
            self._last_flush = (time.time(), row["timesteps"])   # keep steps/s about training

    def _print_epoch(self, r):
        def p(x):
            return "  n/a" if x is None else f"{100 * x:4.0f}%"
        score = "  n/a" if r.get("score") is None else f"{r['score']:6.0f}"
        ent = "n/a" if r.get("entropy") is None else f"{r['entropy']:.2f}"
        print(f"epoch {r['epoch']:>4}  steps {_fmt_steps(r['timesteps']):>10}  "
              f"train acc {p(r['train_accuracy'])} (last {r['window_episodes']:>3} eps)  "
              f"died {p(r['died'])}  score {score}  entropy {ent}  "
              f"{r['steps_per_second']:.0f} steps/s", flush=True)

    def _baseline(self):
        """A* on the validation episodes -- the yardstick, played once."""
        print("baseline: playing the A* AI on the validation episodes ...", flush=True)
        for split, stages in self._splits():
            res = evaluate_split("astar", None, stages, self.eval_episodes,
                                 EVAL_SEED_BASE, self.max_seconds)
            row = eval_row("astar", split, stages, res, self._epoch, self.num_timesteps)
            self.evals_log.write(row)
            print(f"  A* on {split:<7} stages {row['stages']:<8} accuracy "
                  f"{100 * row['accuracy']:.0f}%  score {row['score']:.0f}", flush=True)
        for st in self.record_stages:
            path = os.path.join(self.run_dir, "videos", f"astar_stage{st + 1:02d}.mp4")
            if not os.path.isfile(path):
                self._record("astar", None, st, path, "A* baseline")

    def _splits(self):
        out = []
        if self.train_stages:
            out.append(("train", self.train_stages))
        if self.heldout_stages:
            out.append(("heldout", self.heldout_stages))
        return out

    def _evaluate(self, epoch, timesteps):
        t0 = time.time()
        policy = SB3Policy(self.model, deterministic=True)
        scores = {}
        for split, stages in self._splits():
            res = evaluate_split("model", policy, stages, self.eval_episodes,
                                 EVAL_SEED_BASE, self.max_seconds)
            row = eval_row("model", split, stages, res, epoch, timesteps)
            self.evals_log.write(row)
            scores[split] = row
        sel = "heldout" if "heldout" in scores else "train"

        self.model.save(os.path.join(self.run_dir, "checkpoints", f"step_{timesteps:09d}"))
        new_best = self._best is None or scores[sel]["score"] > self._best[0]
        if new_best:
            self._best = (scores[sel]["score"], epoch)
            self.model.save(os.path.join(self.run_dir, "best_model"))

        if self._evals_done % self.record_every == 0:
            for st in self.record_stages:
                path = os.path.join(self.run_dir, "videos",
                                    f"step_{timesteps:09d}_stage{st + 1:02d}.mp4")
                self._record("model", policy, st, path, f"epoch {epoch}  step {timesteps:,}")
        self._evals_done += 1

        write_report(self.run_dir, live=True)
        bits = "  ".join(
            f"{split} {100 * r['accuracy']:.0f}% ({100 * r['accuracy_lo']:.0f}-"
            f"{100 * r['accuracy_hi']:.0f}) score {r['score']:.0f}"
            for split, r in scores.items())
        print(f"  >> validation @ epoch {epoch}: {bits}"
              f"{'   * new best' if new_best else ''}   ({time.time() - t0:.0f}s)", flush=True)

    def _record(self, label, policy, stage, path, caption):
        try:
            record_episode(label, stage, RECORD_SEED, path, policy=policy, caption=caption,
                           max_seconds=self.max_seconds, speed=self.video_speed)
        except Exception as exc:          # a recording must never kill a training run
            print(f"  (recording {os.path.basename(path)} failed: {exc})", flush=True)


# ---------------------------------------------------------------- final test
def final_test(run_dir, best_path, final_path, train_stages, heldout_stages,
               episodes, max_seconds, workers, log=print):
    """Fresh seeds the model has never been selected on: best and final model
    vs A*, on held-out and on training stages. Writes final_report.txt and
    final_results.csv, and returns the report text."""
    specs = ["astar"]
    labels = {"astar": "astar"}
    if best_path and os.path.isfile(best_path):
        specs.append(f"model:{best_path}")
        labels[specs[-1]] = "best"
    if final_path and os.path.isfile(final_path):
        specs.append(f"model:{final_path}")
        labels[specs[-1]] = "final"
    parts, all_rows = [], []
    for split, stages in (("HELD-OUT stages (never trained on)", heldout_stages),
                          ("TRAINING stages", train_stages)):
        if not stages:
            continue
        log(f"final test on {split.lower()}: {episodes} episodes/stage x {len(specs)} agents ...")
        results = evaluation.evaluate(specs, stages, episodes, base_seed=FINAL_SEED_BASE,
                                      max_seconds=max_seconds, workers=workers)
        for r in results:
            r["agent"] = labels[r["agent"]]
        short = [labels[s] for s in specs]
        parts.append(f"{split}: stages {[s + 1 for s in stages]}, {episodes} episodes each, "
                     f"fresh seeds\n" + evaluation.format_report(results, short, per_stage=False))
        all_rows.extend(dict(r, split=split) for r in results)
    text = "\n\n".join(parts)
    with open(os.path.join(run_dir, "final_report.txt"), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    if all_rows:
        evaluation.write_csv(all_rows, os.path.join(run_dir, "final_results.csv"))
    return text


def install_model(src, dest):
    """Copy a trained model to where the game looks for it. The game's
    'Learned model' menu entry appears once this file exists.

    The model's JSON file (its search-order settings, see ml.policy) goes with
    it; a model without one gets none, so an earlier install's settings are
    never applied to a different model."""
    from ml.policy import options_path
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(src, dest)
    if os.path.isfile(options_path(src)):
        shutil.copyfile(options_path(src), options_path(dest))
    elif os.path.isfile(options_path(dest)):
        os.remove(options_path(dest))
    return dest
