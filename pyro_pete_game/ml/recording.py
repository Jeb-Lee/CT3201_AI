"""Screen-record an AI playing a stage, for review.

Renders the real game -- the same frames a player would see, in spectate
mode -- to an MP4 (via ffmpeg) or, if ffmpeg isn't installed, a GIF. A
caption bar is added along the bottom with whatever you tell it (training
step, agent, stage) plus the live health / occupants-out figures and, when
the episode ends, the outcome.

    from ml.recording import record_episode
    record_episode("astar", stage_index=0, seed=1, path="a_star.mp4")
    record_episode("learned", 8, 1, "step_200k.mp4", policy=my_policy,
                   caption="step 200,000")

Command line: tools/record_agent.py
"""

import os
import random
import shutil
import subprocess

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame                                   # noqa: E402

import levels                                   # noqa: E402
from main import GameSession                    # noqa: E402
from settings import SCREEN_WIDTH, SCREEN_HEIGHT  # noqa: E402
from ml.evaluation import resolve_agent, _ensure_pygame, _NoKeys, DT  # noqa: E402
from ml.outcome import summarise                # noqa: E402

BAR_HEIGHT = 34
END_HOLD_SECONDS = 2.0
_OUTCOME_TEXT = {
    "evacuated": ("EVACUATED", (120, 230, 130)),
    "died": ("THE AI DIED", (240, 100, 90)),
    "gave_up": ("GAVE UP", (240, 190, 80)),
    "timeout": ("TIME LIMIT", (240, 190, 80)),
}


def find_ffmpeg():
    return shutil.which("ffmpeg")


class _Writer:
    """Frames in, file out. ffmpeg when available, otherwise a GIF."""

    def __init__(self, path, size, fps):
        self.size, self.fps = size, fps
        self.frames = None
        self.proc = None
        ffmpeg = find_ffmpeg()
        base, ext = os.path.splitext(path)
        if ffmpeg and ext.lower() in (".mp4", ".mkv", ".webm", ""):
            self.path = path if ext else base + ".mp4"
            self.proc = subprocess.Popen(
                [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo",
                 "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}", "-r", str(fps),
                 "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast",
                 "-crf", "23", "-pix_fmt", "yuv420p", self.path],
                stdin=subprocess.PIPE)
        else:
            self.path = base + ".gif"
            self.frames = []

    def add(self, surface):
        raw = pygame.image.tostring(surface, "RGB")
        if self.proc is not None:
            self.proc.stdin.write(raw)
        else:
            from PIL import Image
            self.frames.append(Image.frombytes("RGB", self.size, raw)
                               .resize((self.size[0] // 2, self.size[1] // 2)))

    def close(self):
        if self.proc is not None:
            self.proc.stdin.close()
            self.proc.wait()
        elif self.frames:
            self.frames[0].save(self.path, save_all=True, append_images=self.frames[1:],
                                duration=int(1000 / self.fps), loop=0)
        return self.path


def _caption(screen, font, session, caption, agent_label, ended):
    w, h = screen.get_size()
    bar = pygame.Surface((w, BAR_HEIGHT), pygame.SRCALPHA)
    bar.fill((10, 12, 18, 215))
    screen.blit(bar, (0, h - BAR_HEIGHT))
    left = "   |   ".join(part for part in (caption, agent_label) if part)
    screen.blit(font.render(left, True, (235, 235, 240)), (10, h - BAR_HEIGHT + 8))
    stats = (f"health {max(0, int(session.agent.health))}   "
             f"out {session.victims_out}/{len(session.victims)}   "
             f"score {session.agent_stats.score}")
    text = font.render(stats, True, (255, 214, 90))
    screen.blit(text, (w - text.get_width() - 10, h - BAR_HEIGHT + 8))
    if ended:
        label, colour = _OUTCOME_TEXT[ended]
        banner = pygame.font.Font(None, 64).render(label, True, colour)
        shade = pygame.Surface((banner.get_width() + 40, banner.get_height() + 20),
                               pygame.SRCALPHA)
        shade.fill((0, 0, 0, 170))
        cx, cy = w // 2, h // 2
        screen.blit(shade, (cx - shade.get_width() // 2, cy - shade.get_height() // 2))
        screen.blit(banner, (cx - banner.get_width() // 2, cy - banner.get_height() // 2))


def record_episode(spec, stage_index, seed, path, policy=None, caption="",
                   max_seconds=240.0, speed=2.0, fps=30, agent_visual="robot"):
    """Play one AI-only episode and save it as a video.

    speed   game-seconds per video-second (2 = twice real time). Long,
            wandering episodes stay watchable.
    Returns the summary dict (as ml.outcome.summarise) plus 'video'."""
    _ensure_pygame()
    if policy is not None:
        brain = "learned"
    else:
        brain, policy = resolve_agent(spec, seed)
    random.seed(seed)
    session = GameSession(levels.get(stage_index), spectate=True,
                          agent_visual=agent_visual, stage_index=stage_index,
                          agent_brain=brain, policy=policy)
    screen = pygame.display.get_surface() or pygame.display.set_mode(
        (SCREEN_WIDTH, SCREEN_HEIGHT))
    font = pygame.font.Font(None, 26)
    label = f"stage {stage_index + 1}: {getattr(levels.get(stage_index), 'NAME', '')}"
    agent_label = f"{spec}  seed {seed}  |  {label}"

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    writer = _Writer(path, screen.get_size(), fps)
    keys = _NoKeys()
    every = max(1, round(speed * fps * DT))     # simulation frames per video frame
    frame, max_frames = 0, int(max_seconds / DT) * 2
    try:
        while (session.state == "playing" and session.agent_stats.elapsed < max_seconds
               and frame < max_frames):
            session.update(DT, keys)
            frame += 1
            if frame % every == 0:
                session.draw(screen)
                _caption(screen, font, session, caption, agent_label, None)
                writer.add(screen)
        result = summarise(session)
        for _ in range(int(END_HOLD_SECONDS * fps)):       # hold on the ending
            session.draw(screen)
            _caption(screen, font, session, caption, agent_label, result["outcome"])
            writer.add(screen)
    finally:
        video = writer.close()
    result.update(agent=spec, stage=stage_index, seed=seed, video=video)
    return result
