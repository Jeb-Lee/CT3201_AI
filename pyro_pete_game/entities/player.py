"""Pyro Pete: 4-directional player character with idle/walk animation."""

import os
import pygame

from settings import PLAYER_SPEED, WALK_ANIM_FPS, PLAYER_SPRITE_HEIGHT, HEALTH_MAX

ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "pete")

DIRECTIONS = ("down", "up", "left", "right")

# The player's collision box is deliberately much smaller than the sprite
# and anchored at the feet -- using the full sprite (which includes the
# helmet towering above his head) as the hitbox would make him "bump" into
# walls well before he visually looks like he's touching them.
COLLISION_WIDTH = 28
COLLISION_HEIGHT = 20


def _load_sprite(path, target_height=None):
    """Load a sprite (real per-pixel alpha baked in by
    tools_make_transparent.py -- see that file for why colorkey alone
    wasn't enough) and scale it to a consistent in-game height, since
    sprites arrive at wildly different native resolutions depending on
    which generation batch made them."""
    image = pygame.image.load(path).convert_alpha()
    if target_height is not None and image.get_height() != target_height:
        scale = target_height / image.get_height()
        new_size = (max(1, round(image.get_width() * scale)), target_height)
        image = pygame.transform.smoothscale(image, new_size)
    return image


class Player:
    """(x, y) is the character's feet-center anchor point in world space,
    not a bounding-box corner. Idle and walk frames come from different
    generation batches and are not all the same canvas size, so anchoring
    by a corner would make the sprite visibly shift/jitter every time the
    animation switches between idle and walking. Anchoring by feet-center
    keeps that point stable no matter which frame is currently showing.
    """

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.direction = "down"
        self.moving = False
        self.anim_timer = 0.0
        self.anim_index = 0

        # Drains while standing in fire (see hazards.FireSystem); a quick
        # dash through a burning tile is survivable, lingering isn't.
        self.health = HEALTH_MAX

        self.idle_frames = {}
        self.walk_frames = {}
        for d in DIRECTIONS:
            self.idle_frames[d] = _load_sprite(
                os.path.join(ASSET_DIR, f"idle_{d}.png"), PLAYER_SPRITE_HEIGHT
            )
            self.walk_frames[d] = [
                _load_sprite(os.path.join(ASSET_DIR, f"walk_{d}_{i}.png"), PLAYER_SPRITE_HEIGHT)
                for i in range(1, 5)
            ]

    def handle_input(self, keys):
        dx = dy = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx += 1
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            dy -= 1
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy += 1

        self.moving = dx != 0 or dy != 0

        # Facing direction: prioritize the most recently pressed axis by
        # just picking vertical over horizontal when both are held, which
        # reads fine for 4-directional top-down movement.
        if dy < 0:
            self.direction = "up"
        elif dy > 0:
            self.direction = "down"
        elif dx < 0:
            self.direction = "left"
        elif dx > 0:
            self.direction = "right"

        if dx and dy:
            # normalize diagonal movement so it isn't faster than cardinal
            dx *= 0.7071
            dy *= 0.7071

        return dx, dy

    def take_damage(self, amount):
        self.health = max(0.0, self.health - amount)

    @property
    def is_dead(self):
        return self.health <= 0

    def get_collision_rect(self, x=None, y=None):
        """Small hitbox anchored at the feet point, independent of
        whichever sprite frame happens to be showing."""
        x = self.x if x is None else x
        y = self.y if y is None else y
        rect = pygame.Rect(0, 0, COLLISION_WIDTH, COLLISION_HEIGHT)
        rect.midbottom = (round(x), round(y))
        return rect

    def update(self, dt, keys, tilemap=None, hazards=None, stats=None):
        dx, dy = self.handle_input(keys)

        # smoke drags on you the same way it costs the AI (hazards.entry_cost)
        speed = PLAYER_SPEED
        if hazards is not None:
            speed *= hazards.move_multiplier(self.x, self.y)
        move_x = dx * speed * dt
        move_y = dy * speed * dt

        start_x, start_y = self.x, self.y
        if tilemap is None:
            self.x += move_x
            self.y += move_y
        else:
            # resolve each axis separately so bumping into a wall on one
            # axis doesn't also cancel out legal movement on the other
            # (lets the player slide along a wall instead of sticking)
            new_x = self.x + move_x
            if tilemap.rect_walkable(self.get_collision_rect(x=new_x)):
                self.x = new_x

            new_y = self.y + move_y
            if tilemap.rect_walkable(self.get_collision_rect(y=new_y)):
                self.y = new_y

        if stats is not None:
            stats.add_distance(((self.x - start_x) ** 2 + (self.y - start_y) ** 2) ** 0.5)

        if self.moving:
            self.anim_timer += dt
            frame_duration = 1.0 / WALK_ANIM_FPS
            if self.anim_timer >= frame_duration:
                self.anim_timer -= frame_duration
                self.anim_index = (self.anim_index + 1) % 4
        else:
            self.anim_timer = 0.0
            self.anim_index = 0

    def get_size(self):
        return self.idle_frames[self.direction].get_size()

    def current_frame(self):
        if self.moving:
            return self.walk_frames[self.direction][self.anim_index]
        return self.idle_frames[self.direction]

    def draw(self, surface, camera_offset=(0, 0)):
        ox, oy = camera_offset
        frame = self.current_frame()
        rect = frame.get_rect()
        rect.midbottom = (round(self.x - ox), round(self.y - oy))
        surface.blit(frame, rect)
