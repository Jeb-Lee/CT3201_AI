"""Imitation learning: teach the network to play the way A* plays.

Behaviour cloning is ordinary supervised learning. The training example is
"what the agent saw" and the answer is "the tile A* stepped to"; the score is
how often the network picks A*'s move (**action-match accuracy**, a real
accuracy in the usual machine-learning sense, logged per epoch). Nothing in the
objective rewards or punishes anything in the game, so unlike the
reinforcement-learning runs there is no cheaper option for the network to
prefer to copying.

The network is the same MaskablePPO policy the RL runs use (same architecture,
same observation, same five actions), so a cloned model can be loaded by the
game, evaluated by the harness, or handed to PPO to fine-tune.

Three things are measured, because action accuracy alone flatters the result:

  action match, seen stages    held-out *episodes* on stages the network trained on
  action match, unseen stages  episodes on stages it never saw (generalisation)
  game outcomes                the network actually plays; how many episodes does
                               it evacuate, next to A* on the same episodes

DAgger (dagger()) repeats: let the current network play, have A* label the
states the *network* reached, add them to the data, train more. Cloning alone
suffers because one small mistake leaves the states the teacher ever visited;
DAgger supplies labels for exactly those states.

Driven by tools/train_imitation.py.
"""

import os
import random
import time

import numpy as np
import torch

from ml import evaluation, expert
from ml.observation import N_ACTIONS, ACTION_STAY
from ml.policy import SB3Policy
from ml.report import CsvLog

EPOCH_FIELDS = ["epoch", "seconds", "lr", "train_loss", "train_acc", "val_seen_loss",
                "val_seen_acc", "val_unseen_acc", "stay_recall_seen",
                "game_seen_evac", "game_seen_occ", "game_unseen_evac", "game_unseen_occ"]
ROUND_FIELDS = ["round", "beta", "new_decisions", "total_decisions", "learner_outcome_died",
                "learner_outcome_gave_up", "learner_outcome_timeout", "learner_outcome_evacuated",
                "val_seen_acc", "val_unseen_acc", "game_seen_evac", "game_seen_occ",
                "game_unseen_evac", "game_unseen_occ", "game_seen_n", "game_unseen_n"]

SEED_TRAIN, SEED_VAL, SEED_UNSEEN, SEED_GAME, SEED_DAGGER = 100_000, 200_000, 300_000, 50_000, 400_000


# --------------------------------------------------------------------- data
def make_tasks(stages, episodes, seed_base):
    return [(st, seed_base + 1000 * st + i) for st in stages for i in range(episodes)]


def build_data(train_stages, heldout_stages, train_episodes, val_episodes, unseen_episodes,
               workers, only_successful=True, max_seconds=90.0, log=print, obs_version=1,
               agent_options=None):
    """Demonstrations from A*: a training set, held-out episodes on the training
    stages, and episodes on stages never trained on."""
    def progress(name):
        return lambda n, total: (log(f"  {name}: {n}/{total} episodes") if n == total else None)

    log(f"collecting demonstrations from A*  ({len(train_stages)} training stages) ...")
    train, tsum = expert.collect(make_tasks(train_stages, train_episodes, SEED_TRAIN),
                                 workers=workers, max_seconds=max_seconds, progress=progress("train"),
                                 obs_version=obs_version, agent_options=agent_options)
    val, vsum = expert.collect(make_tasks(train_stages, val_episodes, SEED_VAL),
                               workers=workers, max_seconds=max_seconds, obs_version=obs_version,
                               agent_options=agent_options)
    unseen, usum = ({}, [])
    if heldout_stages:
        unseen, usum = expert.collect(make_tasks(heldout_stages, unseen_episodes, SEED_UNSEEN),
                                      workers=workers, max_seconds=max_seconds,
                                      obs_version=obs_version, agent_options=agent_options)
    teacher = {"train": _rates(tsum), "val": _rates(vsum), "unseen": _rates(usum)}
    if only_successful:
        keep_eps = {i for i, s in enumerate(tsum) if s["outcome"] == "evacuated"}
        mask = np.isin(train["episode"], list(keep_eps))
        log(f"  keeping the {len(keep_eps)} of {len(tsum)} demonstration episodes in which A* "
            f"evacuated everyone ({int(mask.sum())} of {len(mask)} decisions)")
        train = {k: v[mask] for k, v in train.items()}
    return dict(train=train, val=val, unseen=unseen, teacher=teacher)


def _rates(summaries):
    if not summaries:
        return {}
    n = len(summaries)
    out = {k: sum(s["outcome"] == k for s in summaries) / n
           for k in ("evacuated", "died", "gave_up", "timeout")}
    out["episodes"] = n
    out["occupants_out"] = (sum(s["victims_out"] for s in summaries)
                            / max(1, sum(s["victims_total"] for s in summaries)))
    return out


def merge(a, b):
    """Append dataset b to dataset a (episode ids kept distinct)."""
    if not a:
        return b
    offset = int(a["episode"].max()) + 1
    return {k: np.concatenate([a[k], b[k] + offset if k == "episode" else b[k]]) for k in a}


# -------------------------------------------------------------------- model
def build_model(seed=0, net_arch=(256, 256), algo="maskable", obs_version=1):
    """A fresh policy of the same shape the RL runs use. Returns (model, env);
    the env is only needed to construct it and is safe to close afterwards."""
    from ml import training
    env = training.make_train_env([0], n_envs=1, seed=seed, max_seconds=90.0,
                                  obs_version=obs_version)
    model = training.make_model(algo, env, seed=seed, net_arch=net_arch, n_steps=64,
                                batch_size=64)
    return model, env


def masked_logits(policy, obs, mask):
    features = policy.extract_features(obs)
    if isinstance(features, tuple):
        features = features[0]
    latent = policy.mlp_extractor.forward_actor(features)
    return policy.action_net(latent).masked_fill(~mask, -1e9)


def _batches(n, batch, rng):
    order = rng.permutation(n)
    for i in range(0, n, batch):
        yield order[i:i + batch]


def _to_tensors(data, idx):
    obs = torch.from_numpy(data["obs"][idx].astype(np.float32))
    return obs, torch.from_numpy(data["label"][idx].astype(np.int64)), torch.from_numpy(data["mask"][idx])


@torch.no_grad()
def action_accuracy(policy, data, chunk=8192):
    """(loss, action-match accuracy, recall of the 'stay' action) on a dataset."""
    if not data or len(data["label"]) == 0:
        return float("nan"), float("nan"), float("nan")
    policy.set_training_mode(False)
    n = len(data["label"])
    total_loss, correct = 0.0, 0
    stay_hits = stay_total = 0
    for i in range(0, n, chunk):
        obs, y, m = _to_tensors(data, np.arange(i, min(n, i + chunk)))
        logits = masked_logits(policy, obs, m)
        total_loss += torch.nn.functional.cross_entropy(logits, y, reduction="sum").item()
        pred = logits.argmax(1)
        correct += (pred == y).sum().item()
        is_stay = y == ACTION_STAY
        stay_total += int(is_stay.sum())
        stay_hits += int(((pred == y) & is_stay).sum())
    return total_loss / n, correct / n, (stay_hits / stay_total if stay_total else float("nan"))


# ---------------------------------------------------------- game evaluation
def game_eval(model, seen_stages, unseen_stages, seen_eps=2, unseen_eps=4, max_seconds=90.0,
              deterministic=True, agent_options=None):
    """Let the network play. Returns evacuation rate and occupants-out share on
    training stages ('seen') and on stages it never saw ('unseen')."""
    policy = SB3Policy(model, deterministic=deterministic)
    policy.agent_options = dict(agent_options or {})

    def run(stages, eps):
        rows = [evaluation.run_episode("bc", st, evaluation.episode_seed(SEED_GAME, st, i),
                                       max_seconds=max_seconds, policy=policy)
                for st in stages for i in range(eps)]
        if not rows:
            return float("nan"), float("nan"), 0
        return (sum(r["outcome"] == "evacuated" for r in rows) / len(rows),
                sum(r["victims_out"] for r in rows) / max(1, sum(r["victims_total"] for r in rows)),
                len(rows))

    seen, unseen = run(seen_stages, seen_eps), run(unseen_stages, unseen_eps)
    return dict(game_seen_evac=seen[0], game_seen_occ=seen[1], game_seen_n=seen[2],
                game_unseen_evac=unseen[0], game_unseen_occ=unseen[1], game_unseen_n=unseen[2])


# --------------------------------------------------------------- BC training
def train_bc(model, data, run_dir, epochs=30, batch=512, lr=1e-3, weight_decay=1e-5,
             seen_stages=(), unseen_stages=(), game_every=5, game_seen_eps=2, game_unseen_eps=4,
             seed=0, epoch_offset=0, log=print, log_file="epochs.csv", save_name="bc_model",
             agent_options=None):
    """Supervised training of the policy on A*'s labels. Logs one row per epoch to
    epochs.csv: loss and accuracy on the training data, on held-out episodes of
    the training stages, and on unseen stages, plus (every `game_every` epochs)
    how the network actually plays. Saves the epoch with the best accuracy on
    *seen-stage* held-out episodes (never chosen on the unseen stages, so those
    stay an honest test). Returns the history."""
    policy = model.policy
    params = list(policy.mlp_extractor.policy_net.parameters()) + list(policy.action_net.parameters())
    opt = torch.optim.Adam(params, lr=lr, weight_decay=weight_decay)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, epochs), eta_min=lr * 0.05)
    rng = np.random.default_rng(seed)
    train, val, unseen = data["train"], data["val"], data.get("unseen") or {}
    n = len(train["label"])
    csv_log = CsvLog(os.path.join(run_dir, log_file), EPOCH_FIELDS)
    history, best = [], (-1.0, None)
    t0 = time.time()
    try:
        for epoch in range(1, epochs + 1):
            policy.set_training_mode(True)
            loss_sum, hits = 0.0, 0
            for idx in _batches(n, batch, rng):
                obs, y, m = _to_tensors(train, idx)
                logits = masked_logits(policy, obs, m)
                loss = torch.nn.functional.cross_entropy(logits, y)
                opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(params, 5.0)
                opt.step()
                loss_sum += loss.item() * len(idx)
                hits += (logits.argmax(1) == y).sum().item()
            sched.step()
            vloss, vacc, stay_recall = action_accuracy(policy, val)
            _, uacc, _ = action_accuracy(policy, unseen)
            row = dict(epoch=epoch + epoch_offset, seconds=time.time() - t0,
                       lr=opt.param_groups[0]["lr"], train_loss=loss_sum / n, train_acc=hits / n,
                       val_seen_loss=vloss, val_seen_acc=vacc, val_unseen_acc=uacc,
                       stay_recall_seen=stay_recall)
            if game_every and (epoch % game_every == 0 or epoch == epochs):
                row.update(game_eval(model, seen_stages, unseen_stages, game_seen_eps,
                                     game_unseen_eps, agent_options=agent_options))
            csv_log.write(row)
            history.append(row)
            if vacc > best[0]:
                best = (vacc, epoch + epoch_offset)
                model.save(os.path.join(run_dir, save_name + "_best"))
            game = ""
            if "game_seen_evac" in row:
                game = (f"  | plays: seen {100 * row['game_seen_evac']:.0f}% "
                        f"unseen {100 * row['game_unseen_evac']:.0f}% evacuated")
            log(f"epoch {epoch + epoch_offset:>3}  loss {row['train_loss']:.3f}  "
                f"acc train {100 * row['train_acc']:.1f}%  val {100 * vacc:.1f}%  "
                f"unseen stages {100 * uacc:.1f}%{game}")
    finally:
        csv_log.close()
    model.save(os.path.join(run_dir, save_name))
    return history


# -------------------------------------------------------------------- DAgger
def dagger(model, data, run_dir, rounds=4, episodes_per_stage=25, betas=None, epochs=12,
           train_stages=(), heldout_stages=(), workers=8, batch=512, lr=5e-4, seed=0,
           game_seen_eps=4, game_unseen_eps=6, log=print, max_seconds=90.0, obs_version=1,
           agent_options=None):
    """Let the network play, have A* label where it went, add that to the data,
    train on the union. Round r drives with A* with probability betas[r] (early
    rounds lean on the teacher so episodes stay reasonable); the last rounds are
    the network on its own. Returns the grown dataset."""
    betas = betas if betas is not None else [0.5, 0.3, 0.1] + [0.0] * max(0, rounds - 3)
    rounds_log = CsvLog(os.path.join(run_dir, "rounds.csv"), ROUND_FIELDS)
    epoch_counter = 0
    try:
        for r in range(1, rounds + 1):
            beta = betas[min(r - 1, len(betas) - 1)]
            driver_path = os.path.join(run_dir, f"round{r - 1}_model.zip")
            model.save(driver_path[:-4])
            log(f"\nDAgger round {r}/{rounds}: network drives with probability {1 - beta:.1f}, "
                f"A* labels every state")
            new, summaries = expert.collect(
                make_tasks(train_stages, episodes_per_stage, SEED_DAGGER + 100_000 * r),
                driver_path=driver_path, beta=beta, workers=workers, max_seconds=max_seconds,
                obs_version=obs_version, agent_options=agent_options)
            rates = _rates(summaries)
            data["train"] = merge(data["train"], new)
            log(f"  +{len(new['label'])} labelled states from the network's own play "
                f"(its episodes: {100 * rates['evacuated']:.0f}% evacuated, "
                f"{100 * rates['died']:.0f}% died, {100 * rates['gave_up']:.0f}% gave up); "
                f"training set now {len(data['train']['label'])}")
            train_bc(model, data, run_dir, epochs=epochs, batch=batch, lr=lr, seed=seed + r,
                     seen_stages=train_stages, unseen_stages=heldout_stages, game_every=0,
                     epoch_offset=epoch_counter, log=log, log_file=f"epochs_round{r}.csv",
                     save_name=f"round{r}_model")
            epoch_counter += epochs
            _, vacc, _ = action_accuracy(model.policy, data["val"])
            _, uacc, _ = action_accuracy(model.policy, data.get("unseen") or {})
            game = game_eval(model, train_stages, heldout_stages, game_seen_eps, game_unseen_eps,
                             max_seconds=max_seconds, agent_options=agent_options)
            rounds_log.write(dict(
                round=r, beta=beta, new_decisions=len(new["label"]),
                total_decisions=len(data["train"]["label"]),
                learner_outcome_died=rates["died"], learner_outcome_gave_up=rates["gave_up"],
                learner_outcome_timeout=rates["timeout"],
                learner_outcome_evacuated=rates["evacuated"], val_seen_acc=vacc,
                val_unseen_acc=uacc, **game))
            log(f"  after round {r}: action match {100 * vacc:.1f}% (unseen stages {100 * uacc:.1f}%); "
                f"plays: seen {100 * game['game_seen_evac']:.0f}% unseen "
                f"{100 * game['game_unseen_evac']:.0f}% evacuated")
    finally:
        rounds_log.close()
    return data
