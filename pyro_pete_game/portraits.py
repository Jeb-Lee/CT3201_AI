"""Rescuer portraits, shared by the HUD cards and the results panels.

Pete and the robot have sprite sheets, so their portrait is the head and
shoulders of the idle-down frame. The drone has no sprite art (it is drawn in
code), so its portrait is drawn too. Using one source means a rescuer looks the
same on the results screen as it did in the HUD.
"""

import os

import pygame

from hud_icons import drone_icon

_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_SHEETS = {"pete": "pete", "robot": "robot"}          # kind -> folder under assets/
_cache = {}


def portrait_image(kind, size):
    """The head-and-shoulders crop of `kind`'s idle sprite, scaled to fit a
    `size` x `size` box -- or None when there is no sprite art (the drone, or a
    missing asset), in which case the caller draws a stand-in."""
    key = (kind, size)
    if key not in _cache:
        img = None
        folder = _SHEETS.get(kind)
        path = os.path.join(_ASSETS, folder, "idle_down.png") if folder else None
        if path and os.path.exists(path):
            src = pygame.image.load(path).convert_alpha()
            crop = src.get_bounding_rect()
            crop.h = int(crop.h * 0.58)                   # head and shoulders only
            src = src.subsurface(crop)
            k = size / max(src.get_width(), src.get_height())
            img = pygame.transform.smoothscale(
                src, (max(1, round(src.get_width() * k)), max(1, round(src.get_height() * k))))
        _cache[key] = img
    return _cache[key]


def draw_portrait(surface, rect, kind, accent, radius=9):
    """A framed portrait: dark well, the sprite (or the drawn drone), and a border
    in the rescuer's colour."""
    pygame.draw.rect(surface, (8, 9, 13), rect, border_radius=radius)
    img = portrait_image(kind, rect.w - 8)
    if img is not None:
        surface.blit(img, img.get_rect(center=rect.center))
    else:
        drone_icon(surface, rect)
    pygame.draw.rect(surface, accent, rect, 2, border_radius=radius)
