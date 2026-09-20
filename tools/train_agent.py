"""Train the learned AI rescuer, and keep a reviewable record of how it went.

    pip install -r requirements.txt -r requirements-ml.txt
    python tools/train_agent.py --timesteps 500000 --name first_try

Everything goes into runs/<name>/ -- open runs/<name>/report.html in a
browser (it refreshes itself while training runs):

    epochs.csv            one row per epoch: steps, accuracy over the last
                          N training episodes, score, reward, loss, entropy
    evaluations.csv       at each checkpoint the model plays fixed seeded
                          episodes on training stages and on HELD-OUT stages
                          (deterministic policy), next to A* on the same ones
    epoch_vs_accuracy.png the chart of those (also inside report.html)
    videos/               screen recordings of the model at each checkpoint
                          (and A* once, for comparison)
    checkpoints/  best_model.zip  final_model.zip  config.json
    final_report.txt      the fresh-seed test at the end: best/final vs A*

"Epoch" here = one iteration: collect a batch of play with the current
policy, then update the network. "Accuracy" = share of episodes where the
AI got everyone still alive out and survived. See ml/report.py.

Train on stages 1-7 and validate on 8-10 (default) so you can tell learning
from memorising the maps. Ctrl+C stops cleanly: the model is saved and the
report and final test are still produced.

    --resume PATH.zip   continue training a saved model (--timesteps is then
                        the *additional* steps); add --run-dir to keep logging
                        into the same folder
    --install           copy the best model to pyro_pete_game/ml/models/ so the
                        game offers "Learned model" on its AI menu
    --max-minutes N     stop after N minutes of wall-clock time
"""

import argparse
import json
import os
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
    ap.add_argument("--timesteps", type=int, default=500_000)
    ap.add_argument("--name", default=None, help="run folder name (default: timestamp)")
    ap.add_argument("--runs-dir", default=os.path.join(ROOT, "runs"))
    ap.add_argument("--run-dir", default=None, help="log into this existing folder")
    ap.add_argument("--resume", default=None, help="model .zip to continue from")
    ap.add_argument("--algo", choices=("maskable", "ppo"), default="maskable")
    ap.add_argument("--train-stages", default="1-7")
    ap.add_argument("--heldout-stages", default="8-10", help="'none' to skip")
    ap.add_argument("--n-envs", type=int, default=4, help="parallel game processes")
    ap.add_argument("--n-steps", type=int, default=512, help="steps per env per epoch")
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--update-epochs", type=int, default=4,
                    help="optimiser passes over each batch (SB3's n_epochs)")
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--gamma", type=float, default=0.995)
    ap.add_argument("--ent-coef", type=float, default=0.01)
    ap.add_argument("--net-arch", default="256,256")
    ap.add_argument("--abandon-penalty", type=float, default=0.0,
                    help="reward penalty per occupant not led out when an episode ends")
    ap.add_argument("--give-up-penalty", type=float, default=0.0,
                    help="extra penalty when the AI stands still until it gives up (experimental)")
    ap.add_argument("--timeout-penalty", type=float, default=0.0,
                    help="extra penalty when the time limit runs out (experimental)")
    ap.add_argument("--obs-version", type=int, choices=(1, 2, 3, 4), default=1,
                    help="observation version (2 = with A*-equivalent route hints, 3 = plus a short memory; "
                         "must match the model)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--max-seconds", type=float, default=180.0,
                    help="game-time cap per episode")
    ap.add_argument("--window", type=int, default=100,
                    help="episodes in the rolling training-accuracy window")
    ap.add_argument("--eval-every", type=int, default=100_000, help="steps between validations")
    ap.add_argument("--eval-episodes", type=int, default=6, help="per stage, per validation")
    ap.add_argument("--record-every", type=int, default=1, help="record every Nth validation (0=never)")
    ap.add_argument("--record-stages", default=None,
                    help="1-based stages to record (default: first training + first held-out)")
    ap.add_argument("--video-speed", type=float, default=2.0)
    ap.add_argument("--print-every", type=int, default=5, help="console line every N epochs")
    ap.add_argument("--max-minutes", type=float, default=None)
    ap.add_argument("--final-episodes", type=int, default=20, help="per stage, final fresh-seed test")
    ap.add_argument("--workers", type=int, default=4, help="processes for the final test")
    ap.add_argument("--install", action="store_true")
    args = ap.parse_args()

    try:
        import stable_baselines3
    except ImportError:
        raise SystemExit("stable-baselines3 is not installed:\n"
                         "  pip install -r requirements.txt -r requirements-ml.txt")
    import levels
    from ml import training
    from ml.policy import MODEL_PATH
    from ml.report import write_report

    train_stages = parse_stages(args.train_stages, levels.STAGE_COUNT)
    heldout_stages = parse_stages(args.heldout_stages, levels.STAGE_COUNT)
    if not train_stages:
        raise SystemExit("need at least one training stage")
    overlap = sorted(set(train_stages) & set(heldout_stages))
    if overlap:
        print(f"warning: stages {[s + 1 for s in overlap]} are in both the training and "
              f"held-out sets, so the held-out number is not independent for them")
    if args.record_stages is None:
        rec = [train_stages[0]] + heldout_stages[:1]
    else:
        rec = parse_stages(args.record_stages, levels.STAGE_COUNT)
    if args.record_every <= 0:
        rec = []
    if args.n_envs * args.n_steps < args.batch_size:
        raise SystemExit("n_envs * n_steps must be at least batch-size")

    run_dir = args.run_dir or os.path.join(
        args.runs_dir, args.name or time.strftime("run_%Y%m%d_%H%M%S"))
    os.makedirs(run_dir, exist_ok=True)
    config = dict(vars(args), train_stages_1based=[s + 1 for s in train_stages],
                  heldout_stages_1based=[s + 1 for s in heldout_stages],
                  stable_baselines3=stable_baselines3.__version__)
    with open(os.path.join(run_dir, "config.json"), "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2)

    print(f"run folder : {run_dir}")
    print(f"review page: {os.path.join(run_dir, 'report.html')}   (open in a browser)")
    print(f"training on stages {[s + 1 for s in train_stages]}, validating on "
          f"{[s + 1 for s in heldout_stages] or 'no held-out stages'}; "
          f"{args.n_envs} envs x {args.n_steps} steps = "
          f"{args.n_envs * args.n_steps} steps per epoch")

    from ml.env import RewardConfig
    env = training.make_train_env(
        train_stages, args.n_envs, args.seed, args.max_seconds, gamma=args.gamma,
        reward=RewardConfig(abandon=args.abandon_penalty, give_up=args.give_up_penalty,
                             timeout=args.timeout_penalty),
        obs_version=args.obs_version)
    net_arch = tuple(int(x) for x in args.net_arch.split(",") if x.strip())
    if args.resume:
        model = training.load_for_training(args.algo, args.resume, env, args.device)
        print(f"resumed from {args.resume} at {model.num_timesteps:,} steps")
    else:
        model = training.make_model(
            args.algo, env, args.seed, device=args.device, n_steps=args.n_steps,
            batch_size=args.batch_size, update_epochs=args.update_epochs,
            learning_rate=args.lr, gamma=args.gamma, ent_coef=args.ent_coef,
            net_arch=net_arch)

    monitor = training.TrainingMonitor(
        run_dir, train_stages, heldout_stages, eval_every=args.eval_every,
        eval_episodes=args.eval_episodes, max_seconds=args.max_seconds,
        record_every=max(1, args.record_every), record_stages=rec, window=args.window,
        print_every=args.print_every, max_minutes=args.max_minutes,
        video_speed=args.video_speed)

    t0 = time.time()
    interrupted = False
    try:
        model.learn(total_timesteps=args.timesteps, callback=monitor,
                    reset_num_timesteps=not args.resume)
    except KeyboardInterrupt:
        interrupted = True
        print("\ninterrupted: saving what we have ...")
        monitor.finish()
    finally:
        env.close()
    final_path = os.path.join(run_dir, "final_model")
    model.save(final_path)
    print(f"\ntrained {model.num_timesteps:,} steps in {(time.time() - t0) / 60:.1f} min"
          f"{' (interrupted)' if interrupted else ''}")

    best_zip = os.path.join(run_dir, "best_model.zip")
    text = training.final_test(
        run_dir, best_zip, final_path + ".zip", train_stages, heldout_stages,
        args.final_episodes, args.max_seconds, args.workers)
    print("\n" + text)
    write_report(run_dir, live=False)

    if args.install:
        src = best_zip if os.path.isfile(best_zip) else final_path + ".zip"
        print(f"\ninstalled {src}\n        -> {training.install_model(src, MODEL_PATH)}")
        print("the game now offers 'Learned model' on the AI menu")
    else:
        print("\nTo let the game use it, re-run with --install, or copy best_model.zip to\n"
              f"  {MODEL_PATH}")
    print(f"\nreview: {os.path.join(run_dir, 'report.html')}")


if __name__ == "__main__":
    main()
