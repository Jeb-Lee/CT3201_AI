"""Fonts for the results panels and the pause overlay.

pygame's built-in default font, at the small sizes those panels use, snaps
every glyph to whole pixels and spaces them unevenly -- "exit" reads as
"ex it", "Distance" as "Dista nce". A real TrueType face doesn't do that,
so this looks for Arial on the machine and uses the default font only when
it can't find one.

The file is located by path rather than asked for by name: on Windows,
pygame.font.SysFont("arial") resolves to ARIALN.TTF (Arial *Narrow*) and
"segoeui" to the Light weight, because of how pygame maps family names.
"""

import os

import pygame

# Tried in order; the first one that exists wins.
_ARIAL_PATHS = (
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arial.ttf"),
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)

# role -> (size in the TrueType face, size in pygame's default font)
# The two sizes differ because the faces differ in size; Arial at these sizes is
# about as wide as the default font at its size (174px vs 173px for the longest
# score label), and small enough that the tallest results panel fits the screen.
_SIZES = {
    "title": (36, 44),
    "head": (24, 30),
    "body": (18, 24),
}


def _find_face():
    for path in _ARIAL_PATHS:
        if os.path.exists(path):
            return path
    return None


def ui_font(role):
    """Font for "title", "head" or "body" text."""
    face_size, default_size = _SIZES[role]
    path = _find_face()
    if path is not None:
        try:
            return pygame.font.Font(path, face_size)
        except (OSError, pygame.error):
            pass                      # cannot open the file: fall through to the default
    return pygame.font.SysFont(None, default_size)
