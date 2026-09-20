"""Compare AI agents on the real game, with confidence intervals.

    python tools/evaluate_agents.py --agents astar,random --stages 1-3 --episodes 20

Agents:  astar | random | stay | model | model:PATH | sample:PATH
         (see pyro_pete_game/ml/evaluation.py for what each one is)

Every agent plays the same stages with the same seeds, so each faces the
same occupant layout, and the report includes a paired comparison against
the first agent listed. Use plenty of episodes: 8 per stage is not enough
to tell a real difference from luck (that is why the intervals are shown).

    --stages    1-based, e.g. 1-10 or 1,4,7-9         (default: all ten)
    --episodes  per stage, per agent                   (default: 20)
    --workers   parallel processes                     (default: 1)
    --seed      base seed; change it for a fresh sample (default: 1000)
    --csv PATH  also write every episode to a CSV
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "pyro_pete_game"))


def parse_stages(text, count):
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
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--agents", default="astar,random")
    parser.add_argument("--stages", default=None)
    parser.add_argument("--episodes", type=int, default=20)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--max-seconds", type=float, default=240.0)
    parser.add_argument("--csv", default=None)
    parser.add_argument("--no-per-stage", action="store_true")
    args = parser.parse_args()

    from ml import evaluation
    import levels

    specs = [s.strip() for s in args.agents.split(",") if s.strip()]
    stages = parse_stages(args.stages or f"1-{levels.STAGE_COUNT}", levels.STAGE_COUNT)

    last_quarter = [-1]

    def progress(done, total):
        # live redraw in a terminal; just a few milestone lines when the
        # output is being captured (a redraw there is thousands of lines)
        if sys.stderr.isatty():
            print(f"\r  {done}/{total} episodes", end="", file=sys.stderr, flush=True)
        else:
            quarter = done * 4 // total
            if quarter != last_quarter[0]:
                last_quarter[0] = quarter
                print(f"  {done}/{total} episodes", file=sys.stderr, flush=True)

    print(f"agents={specs}  stages={[s + 1 for s in stages]}  episodes/stage={args.episodes}"
          f"  seed={args.seed}  workers={args.workers}", file=sys.stderr)
    t0 = time.perf_counter()
    results = evaluation.evaluate(specs, stages, args.episodes, base_seed=args.seed,
                                  max_seconds=args.max_seconds, workers=args.workers,
                                  progress=progress)
    print(f"\n  done in {time.perf_counter() - t0:.0f}s" if sys.stderr.isatty()
          else f"  done in {time.perf_counter() - t0:.0f}s", file=sys.stderr)

    print(evaluation.format_report(results, specs, per_stage=not args.no_per_stage))
    if args.csv:
        evaluation.write_csv(results, args.csv)
        print(f"\nwrote {len(results)} episodes to {args.csv}")


if __name__ == "__main__":
    main()
