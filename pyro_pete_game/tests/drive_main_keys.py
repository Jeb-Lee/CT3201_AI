"""Drives the REAL main() with scripted key presses and prints what happened as JSON.

Not a test itself: tests/test_pause.py runs it in a subprocess (main() ends with
pygame.quit(), which would break every other test in the same process).

    python tests/drive_main_keys.py

Sequence (frame numbers): skip the intro, Play vs AI, robot, then
  M -> mute   P -> pause   M -> unmute (while paused)   P -> resume   M -> mute   Esc
"""
import json
import os
import sys
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame

import main as M
import notice
import pause

KEY = lambda k: pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="")
SCRIPT = {
    5: pygame.K_RETURN, 15: pygame.K_RETURN, 30: pygame.K_RETURN, 45: pygame.K_RETURN,
    100: pygame.K_m, 130: pygame.K_p, 150: pygame.K_m, 170: pygame.K_p, 190: pygame.K_m,
    230: pygame.K_ESCAPE,
}
PROBE = (110, 160, 210)                 # frames at which to look at the bottom-right corner

frame = [0]
result = {"pause_frames": [], "notices": [], "corner_lit": {}, "keys": []}
real_get, real_flip = pygame.event.get, pygame.display.flip
real_pause_draw, real_show = pause.PauseScreen.draw, notice.Notices.show


def fake_get(*a, **k):
    frame[0] += 1
    real_get()
    key = SCRIPT.get(frame[0])
    if key is None:
        return []
    result["keys"].append([frame[0], pygame.key.name(key)])
    return [KEY(key)]


def fake_flip():
    real_flip()
    if frame[0] in PROBE:
        surf, chip = pygame.display.get_surface(), notice.chip_rect()
        lit = sum(1 for x in range(chip.left, chip.right, 2) for y in range(chip.top, chip.bottom, 2)
                  if sum(surf.get_at((x, y))[:3]) > 90)
        result["corner_lit"][str(frame[0])] = lit


def draw_spy(self, *a, **k):
    result["pause_frames"].append(frame[0])
    return real_pause_draw(self, *a, **k)


def show_spy(self, text, colour=None):
    result["notices"].append([frame[0], text])
    return real_show(self, text, colour) if colour is not None else real_show(self, text)


pygame.event.get, pygame.display.flip = fake_get, fake_flip
pause.PauseScreen.draw, notice.Notices.show = draw_spy, show_spy
try:
    M.main()
except SystemExit:
    pass
print("RESULT " + json.dumps(result))
