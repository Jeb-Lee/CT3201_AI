"""The game's one typeface and one size scale.

Every piece of text -- intro, menus, HUD, results, pause -- gets its font from
ui_font(role) so the whole game reads as one thing. Nothing else should call
pygame.font.SysFont / pygame.font.Font (tests/test_layout.py checks that).

Typeface: Arial, found on the machine by file path, with the pygame default
font used only when no Arial-like file exists. pygame's default font, at the
sizes a UI uses, snaps glyphs to whole pixels and spaces them unevenly
("exit" reads as "ex it"); a real TrueType face doesn't.

The file is located by path rather than asked for by name: on Windows,
pygame.font.SysFont("arial") resolves to ARIALN.TTF (Arial *Narrow*) and
"segoeui" to the Light weight, because of how pygame maps family names.

Scale (role -> where it is used):
    title    36  menu titles, results headline, pause, intro prompt   bold
    heading  24  menu options, rescuer names, scores, verdict         bold
    body     18  HUD, subtitles, score/stat rows                      regular
    small    15  menu descriptions and hints                          regular
The HUD asks for body in bold: it sits over a busy map, where regular
weight gets lost.
"""

import os

import pygame

_WIN_FONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")

# Tried in order; the first one that exists wins.
_REGULAR_PATHS = (
    os.path.join(_WIN_FONTS, "arial.ttf"),
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
_BOLD_PATHS = (
    os.path.join(_WIN_FONTS, "arialbd.ttf"),
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)

# role -> (size in the TrueType face, size in pygame's default font, bold)
# The default-font sizes are for the fallback only. Arial at these sizes is
# about as wide as the old default font was at its size, and small enough that
# the tallest results panel fits the screen (larger sizes made it 643px tall
# against a 640px window).
_SCALE = {
    "title": (36, 44, True),
    "heading": (24, 30, True),
    "body": (18, 24, False),
    "small": (15, 22, False),
}


def _first_existing(paths):
    for path in paths:
        if os.path.exists(path):
            return path
    return None


def ui_font(role, bold=None):
    """The font for a role: "title", "heading", "body" or "small".

    `bold` overrides the role's usual weight (the HUD passes bold=True for
    body text)."""
    face_size, default_size, role_bold = _SCALE[role]
    want_bold = role_bold if bold is None else bold
    path = _first_existing(_BOLD_PATHS if want_bold else _REGULAR_PATHS)
    if path is not None:
        try:
            return pygame.font.Font(path, face_size)
        except (OSError, pygame.error):
            pass                      # cannot open the file: fall through to the default
    # The default font is already heavy, so there is no bold to ask for.
    return pygame.font.SysFont(None, default_size)
