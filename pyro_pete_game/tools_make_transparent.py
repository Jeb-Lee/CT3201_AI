"""One-off asset processor: bakes real per-pixel transparency into the
Pete sprites instead of relying on pygame's exact-match colorkey at
runtime.

Why: the AI-generated PNGs aren't truly flat pixel art at the file level
-- they have a thin band of anti-aliased pixels blended between the
character and the flat background color at every silhouette edge. An
exact-match colorkey only removes pixels that are the *exact* background
color, so that blended ring stays opaque and shows up in-game as a grey
halo/"cloud" around the character.

This instead measures each pixel's color distance from the sampled
background color and:
  - pixels close to bg  -> fully transparent
  - pixels far from bg  -> left untouched, fully opaque
  - pixels in between (the AA ring) -> partially transparent AND
    de-blended, i.e. the background tint mixed into that edge pixel is
    mathematically subtracted back out, so it doesn't carry a grey tinge
    at any alpha level

Run once whenever a new/replacement sprite is dropped into assets/pete.
"""

import os
import numpy as np
from PIL import Image

ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets", "pete")

LOW_TOL = 14   # distance below this -> fully transparent
HIGH_TOL = 55  # distance above this -> fully opaque, untouched


def process(path):
    img = Image.open(path).convert("RGBA")
    arr = np.asarray(img).astype(np.float64)  # H, W, 4
    bg = arr[0, 0, :3].copy()

    rgb = arr[..., :3]
    dist = np.sqrt(np.sum((rgb - bg) ** 2, axis=-1))

    alpha_frac = np.clip((dist - LOW_TOL) / (HIGH_TOL - LOW_TOL), 0.0, 1.0)

    # avoid divide-by-zero where alpha_frac is 0 (those pixels are fully
    # transparent anyway so the de-blended color doesn't matter)
    safe_alpha = np.where(alpha_frac > 0.001, alpha_frac, 1.0)[..., None]
    deblended = (rgb - (1 - safe_alpha) * bg) / safe_alpha
    deblended = np.clip(deblended, 0, 255)

    out_rgb = np.where(alpha_frac[..., None] >= 1.0, rgb, deblended)
    out_alpha = np.round(alpha_frac * 255)

    out = np.dstack([out_rgb, out_alpha]).astype(np.uint8)
    Image.fromarray(out, mode="RGBA").save(path)


def main():
    files = [f for f in os.listdir(ASSET_DIR) if f.lower().endswith(".png")]
    for i, f in enumerate(files, 1):
        process(os.path.join(ASSET_DIR, f))
        print(f"[{i}/{len(files)}] {f}")


if __name__ == "__main__":
    main()
