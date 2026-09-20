"""Copy the curated parts of each training run into ML_Findings/experiments/.

runs/ is git-ignored (it fills up with checkpoints). This keeps what a reader
needs to review or re-plot an experiment -- config, the epoch and evaluation
logs, the chart, the report page, the recordings and the final model -- and
leaves out the per-checkpoint zips. Local absolute paths are scrubbed so the
folder is portable.

    python pyro_pete_game/ml/ML_Findings/scripts/collect_runs.py
"""

import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "pyro_pete_game"))
RUNS = os.path.join(ROOT, "runs")
DEST = os.path.abspath(os.path.join(HERE, "..", "experiments"))

FILES = ["config.json", "epochs.csv", "evaluations.csv", "final_report.txt",
         "final_results.csv", "epoch_vs_accuracy.png", "final_model.zip"]


def main():
    from ml.report import write_report
    names = sorted(n for n in os.listdir(RUNS) if n.startswith("exp")
                   and os.path.isfile(os.path.join(RUNS, n, "final_model.zip")))
    for name in names:
        src, dst = os.path.join(RUNS, name), os.path.join(DEST, name)
        os.makedirs(dst, exist_ok=True)
        for f in FILES:
            if os.path.isfile(os.path.join(src, f)):
                shutil.copy2(os.path.join(src, f), os.path.join(dst, f))
        if os.path.isdir(os.path.join(src, "videos")):
            shutil.copytree(os.path.join(src, "videos"), os.path.join(dst, "videos"),
                            dirs_exist_ok=True)
        cfg_path = os.path.join(dst, "config.json")
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
        cfg["runs_dir"] = "runs"
        cfg["run_dir"] = None
        if cfg.get("resume"):                       # keep the name, drop the local folder
            cfg["resume"] = os.path.basename(cfg["resume"])
        cfg.setdefault("abandon_penalty", 0.0)       # runs made before the flag existed
        cfg.setdefault("give_up_penalty", 0.0)
        cfg.setdefault("timeout_penalty", 0.0)
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
        page = write_report(dst, live=False)
        with open(page, encoding="utf-8") as fh:
            text = fh.read()
        text = text.replace(os.path.abspath(dst), f"ML_Findings/experiments/{name}")
        with open(page, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("collected", name)


if __name__ == "__main__":
    main()
