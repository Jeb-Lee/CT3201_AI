"""Screen-record an AI playing one stage, for review or comparison.

    python tools/record_agent.py --agent astar --stage 3 --out runs/astar_s3.mp4
    python tools/record_agent.py --agent model:runs/x/best_model.zip --stage 9

Agents: astar | random | stay | model | model:PATH  (as in evaluate_agents.py)
Record the same stage and seed for two agents to compare them side by side.
Needs ffmpeg on PATH for MP4; otherwise a (half-size) GIF is written.

    --speed   game-seconds per video-second (default 2)
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "pyro_pete_game"))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--agent", default="astar")
    parser.add_argument("--stage", type=int, default=1, help="1-based")
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--out", default=None)
    parser.add_argument("--speed", type=float, default=2.0)
    parser.add_argument("--max-seconds", type=float, default=240.0)
    parser.add_argument("--skin", choices=("robot", "drone"), default="robot")
    args = parser.parse_args()

    from ml.recording import record_episode
    import levels
    if not 1 <= args.stage <= levels.STAGE_COUNT:
        raise SystemExit(f"--stage must be 1..{levels.STAGE_COUNT}")
    name = args.agent.replace(":", "_").replace("\\", "_").replace("/", "_")
    out = args.out or f"{name}_stage{args.stage}_seed{args.seed}.mp4"
    result = record_episode(args.agent, args.stage - 1, args.seed, out,
                            max_seconds=args.max_seconds, speed=args.speed,
                            agent_visual=args.skin)
    print(f"{result['outcome']}: {result['victims_out']}/{result['victims_total']} out, "
          f"score {result['score']}, {result['seconds']}s game time -> {result['video']}")


if __name__ == "__main__":
    main()
