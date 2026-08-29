"""Regenerate pyro_pete_game/assets/victims/<name>/ from the raw AI art.

The victim sprites in the repo are GENERATED, not hand-drawn. This script
is the record of how -- run it to rebuild them or to tweak a pose / frame
pick.

Sources (NOT in git -- ~35 MB, mostly video):
    the shared Drive folder  "CT 3201 AI / NPCs"
Download that folder locally and point SRC_DIR at it (or set the
env var VICTIM_SRC), then:  python tools/build_victim_sprites.py

Needs two packages beyond requirements.txt:
    pip install av scipy

--------------------------------------------------------------------------
How each of the 4 directions is built (per character):

  down  <- a straight-to-camera front pose cropped from the character
           sheet.  walk = procedural: contact / pass / contact(other leg)
           / pass, with an actual stepping leg (see _step_feet).
  up    <- the back-view figure on the character sheet. Same procedural walk.
  left  } one of these is a REAL 4-frame walk cycle pulled from the
  right } side-view (*LR*) video clip -- actual moving legs, like Pete --
        for whichever way the clip faces; the other is that mirrored.

down/up have no real walk footage because the video model only ever
produced side-view ("LR") walk clips for these NPCs, never a
walk-toward/away-from-camera one. That gap is the project's worked
"what AI got wrong" example (docs/ai_critique.md); the procedural
bob+step is the fallback.

Every direction for one character is composited onto ONE shared canvas
size so the sprite never jumps when the character turns. Alpha is keyed
from the flat background and de-haloed the same way tools_make_transparent
does for Pete.
"""

import os

import av
import numpy as np
from PIL import Image
from scipy import ndimage

# Point this at your local copy of the Drive "NPCs" folder.
SRC_DIR = os.environ.get(
    "VICTIM_SRC",
    os.path.expanduser(r"~\Downloads\NPCs"),
)
OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "pyro_pete_game", "assets", "victims",
)
TH = 460  # normalize every source to this height before compositing


# --------------------------------------------------------------- keying
def key_out(img, white_bg, low, high, shadow=True, trim_bottom=0.0):
    """Cut the character out of its flat background. `low`/`high` are the
    colour-distance band for the anti-aliased edge; `shadow` also removes
    a flat grey drop-shadow; `trim_bottom` lops off a bottom sliver (video
    frames fuse an elliptical ground shadow to the feet)."""
    arr = np.asarray(img.convert("RGBA")).astype(np.float64)
    if white_bg:
        bg = np.array([255.0, 255.0, 255.0])
    else:
        corners = np.concatenate([arr[:24, :24, :3].reshape(-1, 3),
                                  arr[:24, -24:, :3].reshape(-1, 3)])
        bg = np.median(corners, 0)
    rgb = arr[..., :3]
    dist = np.sqrt(((rgb - bg) ** 2).sum(-1))
    af = np.clip((dist - low) / (high - low), 0, 1)
    safe = np.where(af > 0.001, af, 1.0)[..., None]
    deblended = np.clip((rgb - (1 - safe) * bg) / safe, 0, 255)
    out_rgb = np.where(af[..., None] >= 1.0, rgb, deblended)
    a = np.round(af * 255).astype(int)
    r, g, b = [out_rgb[..., i].astype(int) for i in range(3)]
    if shadow:
        mx = np.maximum(np.maximum(r, g), b)
        mn = np.minimum(np.minimum(r, g), b)
        grey = (a > 0) & ((mx - mn) < 24) & (mx > 90) & (mx < 236)
        a[grey] = 0
    im = Image.fromarray(np.dstack([r, g, b, a]).astype(np.uint8), "RGBA")

    # keep only the largest opaque blob (drops keying speckles)
    m = ndimage.binary_opening(np.asarray(im)[..., 3] > 8, iterations=2)
    lbl, n = ndimage.label(m)
    if n:
        sizes = ndimage.sum(m, lbl, range(1, n + 1))
        keep = lbl == (int(np.argmax(sizes)) + 1)
        na = np.asarray(im)[..., 3].copy()
        na[~keep] = 0
        im = Image.fromarray(np.dstack([np.asarray(im)[..., :3], na]).astype(np.uint8), "RGBA")

    im = im.crop(im.getbbox())
    if trim_bottom > 0:
        w, h = im.size
        im = im.crop((0, 0, w, int(h * (1 - trim_bottom)))).crop(im.getbbox())
    return im


def _src(*parts):
    return os.path.join(SRC_DIR, *parts)


def video_frame(rel, idx):
    container = av.open(_src(rel))
    frames = [f.to_image() for f in container.decode(video=0)]
    container.close()
    return frames[idx]


def side_cycle(rel, ids):
    container = av.open(_src(rel))
    frames = [f.to_image() for f in container.decode(video=0)]
    container.close()
    return [key_out(frames[i], False, 30, 82, trim_bottom=0.05) for i in ids]


def norm(im):
    s = TH / im.height
    return im.resize((max(1, round(im.width * s)), TH), Image.LANCZOS)


# --------------------------------------------------------------- walk fx
def _step_feet(img, which):
    """Lift + swing one leg so a static front/back pose reads as walking.
    which: 0 = planted, -1 = left leg strides, +1 = right leg strides.
    Authored at ~460px tall and shrinks ~5x in game, so the offsets are
    deliberately large -- a 6px shift would vanish."""
    if which == 0:
        return img
    w, h = img.size
    knee = int(h * 0.74)
    lift, swing = int(h * 0.055), int(h * 0.05)
    out = img.copy()
    if which < 0:
        leg = img.crop((0, knee, w // 2 + 3, h))
        out.paste((0, 0, 0, 0), (0, knee, w // 2 + 3, h))
        out.alpha_composite(leg, (swing, knee - lift))
    else:
        leg = img.crop((w // 2 - 3, knee, w, h))
        out.paste((0, 0, 0, 0), (w // 2 - 3, knee, w, h))
        out.alpha_composite(leg, (-swing, knee - lift))
    return out


# --------------------------------------------------------------- build
def build(name, down_up, side, side_faces):
    """down_up: {"down": img, "up": img} keyed static poses.
    side: [f1,f2,f3,f4] real keyed walk frames from the LR clip.
    side_faces: "left" or "right" -- the way `side` faces."""
    du = {d: norm(im) for d, im in down_up.items()}
    sc = [norm(f) for f in side]
    maxw = max([i.width for i in du.values()] + [i.width for i in sc])
    canvas = (maxw + 32, TH + 30)
    out = os.path.join(OUT_DIR, name)
    os.makedirs(out, exist_ok=True)

    def place(im, dy=0, squash=0.0, dx=0, rot=0.0, step=0):
        layer = _step_feet(im, step)
        if rot:
            layer = layer.rotate(rot, resample=Image.BICUBIC, expand=True)
        sw, sh = layer.size
        if squash:
            layer = layer.resize((int(sw * (1 + squash * 0.5)), int(sh * (1 - squash))),
                                 Image.LANCZOS)
            sw, sh = layer.size
        cv = Image.new("RGBA", canvas, (0, 0, 0, 0))
        cv.paste(layer, ((canvas[0] - sw) // 2 + dx, (canvas[1] - 13) - sh + dy), layer)
        return cv

    # down / up -- procedural (no real footage)
    poses = [
        dict(dy=0,   squash=0.00, rot=-2.0, step=-1),
        dict(dy=-26, squash=0.05, dx=4,  rot=3.0,  step=0),
        dict(dy=0,   squash=0.00, rot=2.0,  step=1),
        dict(dy=-26, squash=0.05, dx=-4, rot=-3.0, step=0),
    ]
    for d, im in du.items():
        place(im).save(os.path.join(out, f"idle_{d}.png"))
        for i, p in enumerate(poses, 1):
            place(im, **p).save(os.path.join(out, f"walk_{d}_{i}.png"))

    # left / right -- the real cycle, raw + mirrored
    other = "left" if side_faces == "right" else "right"
    bob = [0, -2, 0, -2]
    for k, fr in enumerate(sc, 1):
        place(fr, dy=bob[k - 1]).save(os.path.join(out, f"walk_{side_faces}_{k}.png"))
        place(fr.transpose(Image.FLIP_LEFT_RIGHT), dy=bob[k - 1]).save(
            os.path.join(out, f"walk_{other}_{k}.png"))
    place(sc[0]).save(os.path.join(out, f"idle_{side_faces}.png"))
    place(sc[0].transpose(Image.FLIP_LEFT_RIGHT)).save(os.path.join(out, f"idle_{other}.png"))

    for f in os.listdir(out):  # re-save with PNG optimisation
        Image.open(os.path.join(out, f)).save(os.path.join(out, f), optimize=True)
    print(f"  {name:12s} canvas {canvas[0]}x{canvas[1]}, side cycle faces {side_faces}")


def main():
    if not os.path.isdir(SRC_DIR):
        raise SystemExit(
            f"source art not found: {SRC_DIR}\n"
            "Download the Drive 'NPCs' folder and set VICTIM_SRC to its path."
        )
    print(f"source: {SRC_DIR}\noutput: {OUT_DIR}\n")

    # ---- CLEANER ----  clip walks LEFT (mop trailing right)
    cs = Image.open(_src("Cleaner", "Cleaner Character sheet.jpg"))
    build(
        "cleaner",
        {"down": key_out(cs.crop((120, 1700, 395, 2250)), True, 22, 78),   # straight front pose
         "up":   key_out(cs.crop((1035, 95, 1462, 640)), True, 22, 78)},   # back view
        side_cycle(r"Cleaner\D_pixel_art_character_walk_cy.mp4", [14, 22, 30, 38]),
        "left",
    )

    # ---- OFFICE LADY ----  clip walks RIGHT
    opera = Image.open(_src("Office lady 1", "Opera still.jpg"))
    build(
        "office_lady",
        {"down": key_out(opera.crop((95, 0, 800, 1536)), True, 18, 70),     # front figure
         "up":   key_out(opera.crop((2000, 0, 2770, 1536)), True, 18, 70)}, # 3rd figure = back
        side_cycle(r"Office lady 1\Office lady 1 LR.mp4", [146, 150, 154, 158]),
        "right",
    )

    # ---- SALARYMAN ----  clip walks RIGHT
    ms = Image.open(_src("Office man 1", "Office Man Character Sheet.png"))
    build(
        "salaryman",
        {"down": key_out(Image.open(_src("Office man 1", "Office Man 1.jpg")), True, 18, 70),
         "up":   key_out(ms.crop((2450, 300, 3250, 1310)), True, 22, 78)},  # top-row back view
        side_cycle(r"Office man 1\Office man 2 LR.mp4", [46, 52, 58, 64]),
        "right",
    )
    print("\ndone.")


if __name__ == "__main__":
    main()
