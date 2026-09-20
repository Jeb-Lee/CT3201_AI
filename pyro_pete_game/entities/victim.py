"""Trapped occupants Pete leads to the exit.

A victim sits idle at a fixed maze cell until Pete makes contact, then
switches to "following" and becomes "saved" once it reaches the exit
tile while following. Victims don't do any pathfinding or collision of
their own -- see main.py, which drives a following victim's position by
replaying a delayed slice of Pete's own recent trail. That trail is
guaranteed walkable (it's literally where Pete has already walked), so
victims never need wall-collision logic to trail him safely through the
maze.

Sprite art is optional. If a folder of frames exists under
assets/victims/<sprite_name>/ the victim is drawn as an animated
character (same idle/walk convention as Pete); if not, it falls back to
the original colored-circle marker, so the game still runs with no
victim art present. Any single direction whose files are missing falls
back to the "down" frames, so a partial set still works.

Art note: the generative *video* model could only produce stable
side-view (left/right) clips for these NPCs and never a usable "toward /
away from camera" walk (see docs/ai_critique.md). The 4-direction sets
here were recovered by combining sources: "down" from a front pose,
"up" from the back view on each character sheet, "left" from a side
frame of the LR video clip, and "right" by mirroring "left". The walk
frames are a procedural bob (vertical bounce + slight squash/lean) off
each single pose rather than hand-drawn footwork -- a deliberate
low-effort choice for an NPC that only ever trails the player.
"""

import functools
import os
import random
from collections import deque

import pygame

from settings import (
    VICTIM_COLOR, VICTIM_SAVED_COLOR, VICTIM_RADIUS, VICTIM_MIN_SPAWN_DISTANCE,
    VICTIM_SPRITE_HEIGHT, VICTIM_SPRITE_NAMES, WALK_ANIM_FPS,
)
from pathfinding import bfs_distances

STATE_IDLE = "idle"
STATE_FOLLOWING = "following"
STATE_SAVED = "saved"
# Died with the rescuer who was escorting them. Comes off the stage total
# (see GameSession.victims_remaining) rather than counting as still needing
# rescue, and is drawn as a grey cross instead of a sprite.
STATE_DEAD = "dead"

OUTLINE_COLOR = (20, 20, 24)

ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "victims")
DIRECTIONS = ("down", "up", "left", "right")

# How far (world pixels) a following victim must travel for the 4-frame
# walk cycle to advance one frame. Driving the animation off distance
# moved rather than a timer means it stays in sync with the victim's
# trail-replay motion no matter the frame rate, and it naturally freezes
# when the victim is standing still.
_WALK_FRAME_DISTANCE = 14.0

# Movement below this many pixels in one follow() step counts as "not
# really moving" -- keeps tiny trail jitter from flipping the victim into
# its walk animation while it's essentially parked.
_MOVING_EPSILON = 0.35

# The victim's position each frame is a point on a *delayed replay* of the
# rescuer's trail, so a single frame's delta is small and noisy -- enough
# that picking the facing straight off it makes the sprite flick sideways
# while the victim is really walking down a straight corridor. Instead we
# pick the facing from the summed movement over the last few frames.
_FACING_WINDOW = 8
_FACING_MIN_NET = 0.6  # net px over the window before we'll change facing


def _load_sprite(path, target_height):
    image = pygame.image.load(path).convert_alpha()
    if image.get_height() != target_height:
        scale = target_height / image.get_height()
        new_size = (max(1, round(image.get_width() * scale)), target_height)
        image = pygame.transform.smoothscale(image, new_size)
    return image


@functools.lru_cache(maxsize=None)
def _load_sprite_set(sprite_name):
    """Load {idle,walk} frames for one victim sprite folder.

    Returns (idle_frames, walk_frames) dicts keyed by direction, or None
    if the folder / the mandatory 'down' frames aren't there (caller then
    draws the circle fallback). Any direction whose files are missing
    reuses the 'down' frames, so shipping only a down-facing set is a
    supported, deliberate configuration -- not a broken one.

    Cached per folder: every stage reset places victims again, and reading the
    same PNGs from disk each time was ~40% of a training run's time. The
    frames are only ever blitted (the one tint copies first), so sharing
    them between victims is safe.
    """
    if not sprite_name:
        return None
    folder = os.path.join(ASSET_DIR, sprite_name)
    down_idle = os.path.join(folder, "idle_down.png")
    if not os.path.isfile(down_idle):
        return None

    def load_dir(d):
        idle_path = os.path.join(folder, f"idle_{d}.png")
        walk_paths = [os.path.join(folder, f"walk_{d}_{i}.png") for i in range(1, 5)]
        if not os.path.isfile(idle_path) or not all(os.path.isfile(p) for p in walk_paths):
            return None
        idle = _load_sprite(idle_path, VICTIM_SPRITE_HEIGHT)
        walk = [_load_sprite(p, VICTIM_SPRITE_HEIGHT) for p in walk_paths]
        return idle, walk

    down = load_dir("down")
    if down is None:
        return None

    idle_frames, walk_frames = {}, {}
    for d in DIRECTIONS:
        loaded = load_dir(d) or down
        idle_frames[d], walk_frames[d] = loaded
    return idle_frames, walk_frames


class Victim:
    def __init__(self, cell, tilemap, sprite_name=None):
        self.cell = cell
        self.x, self.y = tilemap.cell_center(*cell)
        self.state = STATE_IDLE

        self.sprite_name = sprite_name
        self._sprites = _load_sprite_set(sprite_name)

        # animation state (only used when _sprites is not None)
        self.direction = "down"
        self._moving = False
        self._walk_distance = 0.0
        self._recent = deque(maxlen=_FACING_WINDOW)  # recent (dx, dy) deltas

    @property
    def has_sprite(self):
        return self._sprites is not None

    def get_rect(self, radius=VICTIM_RADIUS):
        """Square hitbox centered on the victim, sized by `radius` --
        callers use the small VICTIM_RADIUS box for the saved/exit check
        and the larger VICTIM_RESCUE_RADIUS for "is Pete close enough to
        pick this victim up" so a rescue doesn't require pixel-perfect
        overlap with a small idle marker."""
        r = pygame.Rect(0, 0, radius * 2, radius * 2)
        r.center = (round(self.x), round(self.y))
        return r

    def follow(self, x, y):
        """Move to a point on the rescuer's replayed trail. Also derives
        facing + walk-animation state from the delta, so the sprite (when
        present) animates purely as a function of how the victim is being
        dragged along -- no separate update(dt) plumbing needed."""
        dx, dy = x - self.x, y - self.y
        dist = (dx * dx + dy * dy) ** 0.5

        if dist > _MOVING_EPSILON:
            self._moving = True
            self._walk_distance += dist
            self._recent.append((dx, dy))
            net_x = sum(a for a, _ in self._recent)
            net_y = sum(b for _, b in self._recent)
            # only re-face when the smoothed motion is clearly going
            # somewhere; vertical wins ties, matching the player
            if abs(net_x) > _FACING_MIN_NET or abs(net_y) > _FACING_MIN_NET:
                if abs(net_y) >= abs(net_x):
                    self.direction = "down" if net_y > 0 else "up"
                else:
                    self.direction = "right" if net_x > 0 else "left"
        else:
            self._moving = False
            self._walk_distance = 0.0
            self._recent.clear()

        self.x, self.y = x, y

    def _current_frame(self):
        idle_frames, walk_frames = self._sprites
        if self._moving and self.state == STATE_FOLLOWING:
            index = int(self._walk_distance / _WALK_FRAME_DISTANCE) % 4
            return walk_frames[self.direction][index]
        return idle_frames[self.direction]

    def draw(self, surface, camera_offset, font=None):
        """font is optional (only needed to render the idle "!" marker)
        so callers that don't care about that indicator can skip passing
        it. Idle vs. following vs. saved are made visually distinct on
        purpose -- they used to all render as the same plain yellow
        circle, which made it impossible to tell at a glance whether a
        rescue had actually registered."""
        ox, oy = camera_offset
        cx, cy = round(self.x - ox), round(self.y - oy)

        if self.state == STATE_DEAD:
            arm = 9
            for a, b in (((-arm, -arm), (arm, arm)), ((-arm, arm), (arm, -arm))):
                pygame.draw.line(surface, (26, 26, 30), (cx + a[0], cy + a[1]),
                                 (cx + b[0], cy + b[1]), 6)
                pygame.draw.line(surface, (150, 150, 158), (cx + a[0], cy + a[1]),
                                 (cx + b[0], cy + b[1]), 3)
            return

        if self._sprites is not None:
            frame = self._current_frame()
            if self.state == STATE_SAVED:
                frame = frame.copy()
                frame.fill(VICTIM_SAVED_COLOR + (0,), special_flags=pygame.BLEND_RGBA_ADD)
            rect = frame.get_rect()
            rect.midbottom = (cx, cy)
            surface.blit(frame, rect)

            if self.state == STATE_FOLLOWING:
                # small "being escorted" tick above the head, cheap stand-in
                # for the white ring the circle version used
                pygame.draw.circle(surface, (255, 255, 255), (cx, rect.top - 6), 3)
            elif self.state == STATE_IDLE and font is not None:
                marker = font.render("!", True, (255, 80, 80))
                surface.blit(marker, marker.get_rect(center=(cx, rect.top - 10)))
            return

        # --- no sprite art: original colored-circle marker ---
        if self.state == STATE_SAVED:
            color, ring_color, ring_width = VICTIM_SAVED_COLOR, OUTLINE_COLOR, 2
        elif self.state == STATE_FOLLOWING:
            color, ring_color, ring_width = VICTIM_COLOR, (255, 255, 255), 3
        else:
            color, ring_color, ring_width = VICTIM_COLOR, OUTLINE_COLOR, 2

        pygame.draw.circle(surface, color, (cx, cy), VICTIM_RADIUS)
        pygame.draw.circle(surface, ring_color, (cx, cy), VICTIM_RADIUS, ring_width)

        if self.state == STATE_IDLE and font is not None:
            marker = font.render("!", True, (255, 80, 80))
            marker_rect = marker.get_rect(center=(cx, cy - VICTIM_RADIUS - 12))
            surface.blit(marker, marker_rect)


def place_victims(tilemap, count, exclude_cells=()):
    """Pick `count` distinct floor cells for victims: each at least
    VICTIM_MIN_SPAWN_DISTANCE cells from spawn (so none spawn trivially
    next to Pete), and none overlapping spawn/exit or exclude_cells
    (e.g. the fire's ignition cell, so a victim doesn't start on fire).
    Not seeded -- unlike the maze/fire, victim placement is meant to
    vary run to run for replay variety.

    Sprite art is drawn from VICTIM_SPRITE_NAMES, shuffled so a run with
    fewer victims than sprites still shows a random mix (not always the
    first N). Once every sprite has been used it wraps round. A name with
    no matching assets/victims/<name>/ folder falls back to the circle
    marker (see Victim), so the list can safely include art that isn't in.
    """
    dist_from_spawn = bfs_distances(tilemap, tilemap.spawn_cell)
    banned = set(exclude_cells) | {tilemap.spawn_cell, tilemap.exit_cell}

    candidates = [
        cell for cell, dist in dist_from_spawn.items()
        if cell not in banned and dist >= VICTIM_MIN_SPAWN_DISTANCE
    ]
    random.shuffle(candidates)
    chosen = candidates[:count]

    names = list(VICTIM_SPRITE_NAMES) if VICTIM_SPRITE_NAMES else [None]
    random.shuffle(names)
    return [
        Victim(cell, tilemap, sprite_name=names[i % len(names)])
        for i, cell in enumerate(chosen)
    ]
