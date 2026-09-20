"""Teach the learned AI to play like A* (imitation learning), with an epoch-vs-accuracy log.

    python tools/train_imitation.py --name imit1

What it does, in order (all output in runs/<name>/):

  1. Collect demonstrations: A* plays training stages through the network's own
     one-tile-step interface; every decision is recorded as (what it saw, the
     move A* made). Also collects held-out episodes on the training stages and
     episodes on stages the network never sees.
  2. Behaviour cloning: supervised training of the same MaskablePPO policy the
     RL runs use. epochs.csv gets one row per epoch: loss and action-match
     accuracy on the training data, on held-out episodes, and on unseen stages,
     plus how the network actually plays in the game every few epochs.
  3. DAgger (--dagger-rounds): the network plays, A* labels the states it
     reaches, those are added to the data, training continues. rounds.csv.
  4. A final test of the result in the game, next to A*, on all ten stages
     (deterministic policy, which is what the game uses, and sampled).

Outputs: imitation_epoch_vs_accuracy.png, epochs*.csv, rounds.csv, baseline.json,
final_report.txt, and the models (bc_model.zip, roundN_model.zip, final_model.zip).
Any of them loads in the game via ml/policy.py or in the harness as model:PATH.

    --train-stages / --heldout-stages   1-based, default 1-7 / 8-10
    --dagger-rounds 0                   cloning only
"""

import argparse
import json
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pyro_pete_game"))


def parse_stages(text, count):
    if text.strip().lower() in ("", "none"):
        return []
    out = []
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.extend(range(int(lo), int(hi) + 1))
        elif part:
            out.append(int(part))
    bad = [n for n in out if not 1 <= n <= count]
    if bad:
        raise SystemExit(f"stages must be between 1 and {count}, got {bad}")
    return [n - 1 for n in dict.fromkeys(out)]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default=None)
    ap.add_argument("--runs-dir", default=os.path.join(ROOT, "runs"))
    ap.add_argument("--train-stages", default="1-7")
    ap.add_argument("--heldout-stages", default="8-10")
    ap.add_argument("--train-episodes", type=int, default=120, help="A* demonstrations per training stage")
    ap.add_argument("--val-episodes", type=int, default=20)
    ap.add_argument("--unseen-episodes", type=int, default=30)
    ap.add_argument("--all-demos", action="store_true",
                    help="also imitate the demonstrations in which A* failed (default: successes only)")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch-size", type=int, default=512)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--net-arch", default="256,256")
    ap.add_argument("--obs-version", type=int, choices=(1, 2, 3, 4), default=2,
                    help="1: local window only (LESS than A* sees). 2: adds route hints from A*'s own "
                         "inputs, so learner and A* have the same information (default). "
                         "3: version 2 plus a short memory of the agent's own last move and tiles. "
                         "4: version 3 plus how often it has stood on each nearby tile this episode")
    ap.add_argument("--frontier-lean", type=float, default=0.0,
                    help="teacher search order: lean towards the far side of the map (0 = A*'s own nearest-frontier rule; 0.5 = 'far side')")
    ap.add_argument("--frontier-min-reveal", type=int, default=0,
                    help="teacher skips a frontier that would reveal fewer than this many unseen floor tiles (no trips into a corner's last few tiles)")
    ap.add_argument("--game-every", type=int, default=5, help="play the game every N epochs")
    ap.add_argument("--dagger-rounds", type=int, default=4)
    ap.add_argument("--dagger-episodes", type=int, default=25, help="per training stage, per round")
    ap.add_argument("--dagger-epochs", type=int, default=12)
    ap.add_argument("--final-episodes", type=int, default=10, help="per stage, final test")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-seconds", type=float, default=90.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--install", action="store_true", help="copy the final model to ml/models/ai_policy.zip")
    args = ap.parse_args()

    import numpy as np
    import torch
    import levels
    from ml import evaluation, imitation, training
    from ml.imitation_report import plot_imitation
    from ml.policy import MODEL_PATH, write_agent_options

    torch.manual_seed(args.seed)
    train_stages = parse_stages(args.train_stages, levels.STAGE_COUNT)
    agent_options = {}
    if args.frontier_lean:
        agent_options["frontier_lean"] = args.frontier_lean
    if args.frontier_min_reveal:
        agent_options["frontier_min_reveal"] = args.frontier_min_reveal
    heldout = parse_stages(args.heldout_stages, levels.STAGE_COUNT)
    run_dir = os.path.join(args.runs_dir, args.name or time.strftime("imit_%Y%m%d_%H%M%S"))
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "config.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(vars(args), train_stages_1based=[s + 1 for s in train_stages],
                       heldout_stages_1based=[s + 1 for s in heldout]), fh, indent=2)
    print(f"run folder: {run_dir}")
    t0 = time.time()

    data = imitation.build_data(train_stages, heldout, args.train_episodes, args.val_episodes,
                                args.unseen_episodes, args.workers,
                                only_successful=not args.all_demos, max_seconds=args.max_seconds,
                                obs_version=args.obs_version, agent_options=agent_options)
    n = len(data["train"]["label"])
    lab = np.bincount(data["train"]["label"], minlength=5) / n
    print(f"{n} training decisions, {len(data['val']['label'])} validation, "
          f"{len(data['unseen'].get('label', []))} on unseen stages; "
          f"labels stay/up/down/left/right = {np.round(lab, 3).tolist()}")
    t = data["teacher"]
    print(f"A* through this interface evacuates {100 * t['train']['evacuated']:.0f}% of "
          f"training-stage and {100 * t['unseen'].get('evacuated', float('nan')):.0f}% of "
          f"unseen-stage demonstration episodes")

    # A* on the very episodes the network will be tested on during training (chart reference lines)
    def a_star(stages, eps):
        rows = [evaluation.run_episode("astar", st, evaluation.episode_seed(imitation.SEED_GAME, st, i),
                                       max_seconds=args.max_seconds)
                for st in stages for i in range(eps)]
        return sum(r["outcome"] == "evacuated" for r in rows) / max(1, len(rows)) if rows else float("nan")
    baseline = {"seen_evac": a_star(train_stages, 2), "unseen_evac": a_star(heldout, 4),
                "teacher": t}
    with open(os.path.join(run_dir, "baseline.json"), "w", encoding="utf-8") as fh:
        json.dump(baseline, fh, indent=2)

    net_arch = tuple(int(x) for x in args.net_arch.split(","))
    model, env = imitation.build_model(seed=args.seed, net_arch=net_arch,
                                       obs_version=args.obs_version)
    print(f"\nbehaviour cloning: {args.epochs} epochs")
    imitation.train_bc(model, data, run_dir, epochs=args.epochs, batch=args.batch_size, lr=args.lr,
                       seen_stages=train_stages, unseen_stages=heldout, game_every=args.game_every,
                       seed=args.seed, agent_options=agent_options)
    plot_imitation(run_dir)

    if args.dagger_rounds:
        imitation.dagger(model, data, run_dir, rounds=args.dagger_rounds,
                         episodes_per_stage=args.dagger_episodes, epochs=args.dagger_epochs,
                         train_stages=train_stages, heldout_stages=heldout, workers=args.workers,
                         seed=args.seed, max_seconds=args.max_seconds,
                         obs_version=args.obs_version, agent_options=agent_options)
    env.close()
    plot_imitation(run_dir)

    final_path = os.path.join(run_dir, "final_model")
    model.save(final_path)
    write_agent_options(final_path + ".zip", agent_options, obs_version=args.obs_version)
    print(f"\nfinal test on all ten stages, {args.final_episodes} fresh episodes each ...")
    specs = ["astar", f"model:{final_path}.zip", f"sample:{final_path}.zip"]
    stages = list(range(levels.STAGE_COUNT))
    results = evaluation.evaluate(specs, stages, args.final_episodes, base_seed=90_000,
                                  max_seconds=args.max_seconds, workers=args.workers)
    label = {specs[0]: "astar", specs[1]: "cloned (deterministic)", specs[2]: "cloned (sampled)"}
    for r in results:
        r["agent"] = label[r["agent"]]
    names = [label[s] for s in specs]
    parts = []
    for title, sel in (("TRAINED stages " + str([s + 1 for s in train_stages]), train_stages),
                       ("UNSEEN stages " + str([s + 1 for s in heldout]), heldout)):
        if sel:
            sub = [r for r in results if r["stage"] in sel]
            parts.append(title + "\n" + evaluation.format_report(sub, names, per_stage=False))
    parts.append("ALL ten stages\n" + evaluation.format_report(results, names, per_stage=True))
    text = "\n\n".join(parts)
    with open(os.path.join(run_dir, "final_report.txt"), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    evaluation.write_csv(results, os.path.join(run_dir, "final_results.csv"))
    print("\n" + text)
    if args.install:
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        shutil.copyfile(final_path + ".zip", MODEL_PATH)
        print(f"\ninstalled -> {MODEL_PATH}")
    print(f"\ndone in {(time.time() - t0) / 60:.1f} min; chart: "
          f"{os.path.join(run_dir, 'imitation_epoch_vs_accuracy.png')}")


if __name__ == "__main__":
    main()
