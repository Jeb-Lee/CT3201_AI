"""Turn recordings into things a reader can look at without a video player:
a looping GIF for the featured clips (shows inline on GitHub) and a contact
sheet of stills for every clip.

    python pyro_pete_game/ml/ML_Findings/scripts/make_media.py

Copies each source MP4 into media/<group>/, next to <name>.gif and
<name>_sheet.png. Sources that do not exist yet are skipped, so it can be
re-run as experiments finish.
"""

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(BASE, "..", "..", ".."))
MEDIA = os.path.join(BASE, "media")
EXP = os.path.join(BASE, "experiments")

# (group, name, source mp4, caption)
MANIFEST = [
    ("early_trials", "00_reference_astar_stage1", os.path.join(EXP, "exp01_plain_s0", "videos", "astar_stage01.mp4"),
     "A* on stage 1, for comparison"),
    ("early_trials", "01_untrained_step0", os.path.join(EXP, "exp01_plain_s0", "videos", "step_000000000_stage01.mp4"),
     "Untrained network, before any learning"),
    ("early_trials", "02_step52k", os.path.join(EXP, "exp01_plain_s0", "videos", "step_000052224_stage01.mp4"),
     "After 52,224 steps (epoch 17): mid-way through the collapse"),
    ("early_trials", "03_step101k", os.path.join(EXP, "exp01_plain_s0", "videos", "step_000101376_stage01.mp4"),
     "After 101,376 steps (epoch 33): learned to stand still"),
]
for group in ("baselines", "reward_versions", "imitation"):
    d = os.path.join(MEDIA, group)
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.endswith(".mp4"):
                MANIFEST.append((group, f[:-4], os.path.join(d, f), ""))


# GIFs are only for reading the docs on GitHub, and they are big (1-3 MB each), so
# only the clips the docs feature get one. Every clip keeps its MP4 and contact sheet.
FEATURED_GIFS = {
    "astar_stage05", "random_stage01", "stay_stage01",
    "exp01_plain_s0_step0000000_seed1000_died",
    "exp01_plain_s0_step0101376_seed1001_gave_up",
    "exp07_giveup200_long_s0_step0301056_seed1001_died",
    "exp06_plain_s2_continued_step0402432_seed1001_gave_up",
    # imitation: the clone matching A*, a success on an unseen stage, a failure on an unseen stage,
    # and the local-view network dying on that same unseen stage
    "stage01_seed1000_v2_evacuated", "stage08_seed1000_v2_evacuated",
    "stage07_seed1001_v2_gave_up", "stage09_seed1000_v2_died", "stage08_seed1000_v1_died",
}


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True)
    return float(out.stdout.strip())


def run(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def process(group, name, src):
    out_dir = os.path.join(MEDIA, group)
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, name + ".mp4")
    if os.path.abspath(src) != os.path.abspath(dst):
        shutil.copy2(src, dst)
    dur = duration(dst)
    gif = os.path.join(out_dir, name + ".gif")
    if name in FEATURED_GIFS:
        run("-i", dst, "-t", "24", "-vf",
            "fps=8,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];"
            "[b][p]paletteuse=dither=bayer:bayer_scale=4", "-loop", "0", gif)
    elif os.path.isfile(gif):
        os.remove(gif)
    run("-i", dst, "-vf", f"fps=8/{max(dur, 1):.3f},scale=320:-1,tile=4x2", "-frames:v", "1",
        os.path.join(out_dir, name + "_sheet.png"))
    return dur


if __name__ == "__main__":
    for group, name, src, cap in MANIFEST:
        if not os.path.isfile(src):
            print("skip (missing):", name)
            continue
        print(f"{group}/{name}: {process(group, name, src):.1f}s")
