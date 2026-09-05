"""Pyro Pete: Emergency Evacuation.

You drive Pete (WASD / arrows) through a burning, collapsing maze, picking
up trapped occupants and leading them to the exit. An autonomous AI rescue
agent (entities.rescue_agent.RescueAgent) runs the same maze at the same
time under the same rules -- it has health, takes hazard damage, and plans
with hazard-weighted A* that it re-runs whenever the map changes under it.
Its intended route is drawn on the floor.

The run is a race against that agent: it ends when Pete reaches the exit
or dies, and a results panel compares the two rescuers over the same
clock -- victims saved, time, distance, damage, and (agent only) how many
times the shifting hazards forced it to re-plan.

Hazards (see hazard_field.HazardField): spreading fire + functional smoke
(slows you, closes in your view), stationary sparking panels, ceilings
that collapse into impassable rubble mid-run, and one locked door whose
key is hidden on a side branch.

Controls: WASD / arrows move, R restart, Esc quit.
"""

import sys
from collections import deque

import pygame

from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS,
    HEALTH_MAX,
    HEALTH_BAR_WIDTH, HEALTH_BAR_HEIGHT, HEALTH_BAR_MARGIN,
    HEALTH_BAR_BG_COLOR, HEALTH_BAR_FILL_COLOR, HEALTH_BAR_BORDER_COLOR,
    HEALTH_BAR_COLOR_FULL, HEALTH_BAR_COLOR_MID,
    VICTIM_COUNT, VICTIM_RESCUE_RADIUS,
    PLAYER_TRAIL_MAXLEN, AGENT_TRAIL_MAXLEN,
    VICTIM_FOLLOW_LAG_FRAMES, VICTIM_FOLLOW_SPACING_FRAMES,
    KEY_COLOR, PLAYER_TRAIL_COLOR, PLAYER_TRAIL_ALPHA,
)
from entities.player import Player
from entities.victim import place_victims, STATE_IDLE, STATE_FOLLOWING, STATE_SAVED
from entities.rescue_agent import RescueAgent
from camera import Camera
from hazard_field import HazardField
from visibility import VisibilitySystem
from stats import RunStats
from results import draw_results
from levels import level_01

FONT_COLOR = (230, 230, 230)


# ---------------------------------------------------------------- rescue logic
def _health_bar_color(frac):
    """Green at full health, through yellow/orange, to red as it drops --
    added after playtesting feedback that a static red bar gave no sense
    of urgency (see playtesting/Playtest_Feedback_and_Run_Notes.md)."""
    frac = max(0.0, min(1.0, frac))
    if frac >= 0.5:
        t = (1.0 - frac) / 0.5
        start, end = HEALTH_BAR_COLOR_FULL, HEALTH_BAR_COLOR_MID
    else:
        t = (0.5 - frac) / 0.5
        start, end = HEALTH_BAR_COLOR_MID, HEALTH_BAR_FILL_COLOR
    return tuple(round(a + (b - a) * t) for a, b in zip(start, end))


def _try_rescue(victims, rescuer_rect, follow_order):
    """Any idle victim touched by rescuer_rect starts following. Shared by
    Pete and the AI agent -- whichever's rect gets here first claims the
    victim, so this is what makes rescues a fair race. Mutates follow_order."""
    for victim in victims:
        if victim.state == STATE_IDLE and rescuer_rect.colliderect(
            victim.get_rect(radius=VICTIM_RESCUE_RADIUS)
        ):
            victim.state = STATE_FOLLOWING
            follow_order.append(victim)


def _advance_escort(follow_order, rescuer_trail):
    """Move each following victim to a delayed slice of its rescuer's
    trail -- guaranteed walkable since it's where the rescuer already
    walked. Index in follow_order adds lag so they queue single-file."""
    for index, victim in enumerate(follow_order):
        if victim.state != STATE_FOLLOWING:
            continue
        lag = VICTIM_FOLLOW_LAG_FRAMES + index * VICTIM_FOLLOW_SPACING_FRAMES
        if len(rescuer_trail) > lag:
            target = rescuer_trail[-1 - lag]
        elif rescuer_trail:
            target = rescuer_trail[0]
        else:
            target = (victim.x, victim.y)
        victim.follow(*target)


def _mark_saved(follow_order):
    for victim in follow_order:
        if victim.state == STATE_FOLLOWING:
            victim.state = STATE_SAVED


# ---------------------------------------------------------------- game session
class GameSession:
    """All the per-run state, so restarting is just reset() and main()
    stays a thin pygame shell around update()/draw()."""

    def __init__(self, tilemap):
        self.tilemap = tilemap
        self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT,
                             tilemap.pixel_width, tilemap.pixel_height)
        self.visibility = VisibilitySystem()
        self.hud_font = pygame.font.SysFont(None, 28)
        self._trail_surface = None  # reused draw buffer for Pete's trail
        self.reset()

    def reset(self):
        tm = self.tilemap
        tm.clear_dynamic_blocks()
        self.visibility.reset()

        spawn_x, spawn_y = tm.spawn_pos()
        self.player = Player(spawn_x, spawn_y)
        self.player_stats = RunStats("You (Pete)")
        self.agent_stats = RunStats("AI agent")

        self.hazards = HazardField(
            tm, seed=level_01.SEED,
            protected_cells_fn=self._protected_cells,
            occupied_cells_fn=self._occupied_cells,
        )
        self.victims = place_victims(
            tm, VICTIM_COUNT, exclude_cells=self.hazards.reserved_cells()
        )
        self.hazards.activate_door()  # after victims, so they spawn on a doorless map

        self.player_trail = deque(maxlen=PLAYER_TRAIL_MAXLEN)
        self.player_follow_order = []
        self.player_done = None  # "exit" | "dead" | None
        self.player_walked = {tm.spawn_cell}  # every cell Pete has stepped on

        self.agent = RescueAgent(tm, tm.spawn_cell,
                                 hazard_field=self.hazards, stats=self.agent_stats)
        self.agent_trail = deque(maxlen=AGENT_TRAIL_MAXLEN)
        self.agent_follow_order = []

        self.state = "playing"  # "playing" | "results"

    # -- debris callbacks ------------------------------------------------
    def _protected_cells(self):
        cells = [self.tilemap.spawn_cell, self.tilemap.exit_cell]
        cells += [v.cell for v in getattr(self, "victims", [])]
        haz = getattr(self, "hazards", None)
        if haz and haz.doors.key_cell and not haz.doors.key_collected:
            cells.append(haz.doors.key_cell)
        return cells

    def _occupied_cells(self):
        ts = self.tilemap.tile_size
        out = [self.agent.current_cell] if hasattr(self, "agent") else []
        if hasattr(self, "player"):
            out.append((int(self.player.x // ts), int(self.player.y // ts)))
        return out

    # -- update -------------------------------------------------------
    def update(self, dt, keys):
        if self.state != "playing":
            return
        tm = self.tilemap

        if self.player_done is None:
            self.player_stats.tick(dt)
            self.player.update(dt, keys, tilemap=tm,
                               hazards=self.hazards, stats=self.player_stats)
            self.player_trail.append((self.player.x, self.player.y))
            self.player_walked.add((int(self.player.x // tm.tile_size),
                                    int(self.player.y // tm.tile_size)))

            dps = self.hazards.damage_per_second(self.player.get_collision_rect())
            if dps:
                self.player.take_damage(dps * dt)
                self.player_stats.add_damage(dps * dt)

            _try_rescue(self.victims, self.player.get_collision_rect(),
                        self.player_follow_order)
            _advance_escort(self.player_follow_order, self.player_trail)
            self.hazards.doors.try_pickup(self.player.get_collision_rect())

            if self.player.is_dead:
                self._end_run("dead")
            elif tm.is_exit_rect(self.player.get_collision_rect()):
                _mark_saved(self.player_follow_order)
                self._end_run("exit")

        self.hazards.update(dt)

        if not self.agent.done:
            self.agent_stats.tick(dt)
        self.agent.update(dt, self.victims)
        self.agent_trail.append((self.agent.x, self.agent.y))
        _try_rescue(self.victims, self.agent.get_rect(), self.agent_follow_order)
        _advance_escort(self.agent_follow_order, self.agent_trail)
        self.hazards.doors.try_pickup(self.agent.get_rect())
        if self.agent.current_cell == tm.exit_cell:
            _mark_saved(self.agent_follow_order)

        self.camera.update(self.player.x, self.player.y)
        self.visibility.update(self.player, self.hazards)

        self.player_stats.set_saved(
            sum(1 for v in self.player_follow_order if v.state == STATE_SAVED))
        self.agent_stats.set_saved(
            sum(1 for v in self.agent_follow_order if v.state == STATE_SAVED))

    def _end_run(self, player_reason):
        self.player_done = player_reason
        self.player_stats.finish(player_reason)
        if self.agent.is_dead:
            agent_reason = "dead"
        elif self.agent.current_cell == self.tilemap.exit_cell:
            agent_reason = "exit"
        else:
            agent_reason = "time"
        self.agent_stats.finish(agent_reason)
        self.state = "results"

    # -- draw -------------------------------------------------------
    def draw(self, surface):
        cam = self.camera.offset
        self.tilemap.draw(surface, cam)
        self.hazards.draw_ground(surface, cam)
        for victim in self.victims:
            victim.draw(surface, cam, font=self.hud_font)
        self.player.draw(surface, cam)
        self.visibility.draw(surface, self.player, cam, self.hazards)

        # Trails + the AI's planned route are drawn ON TOP of the fog on
        # purpose: the point of running an autonomous agent next to the
        # player is being able to compare where each one went, so both
        # paths stay visible even in unlit parts of the maze.
        self._draw_player_trail(surface, cam)
        self.agent.draw_route(surface, cam)
        self.agent.draw(surface, cam)

        self._draw_hud(surface)

    def _draw_player_trail(self, surface, camera_offset):
        ox, oy = camera_offset
        ts = self.tilemap.tile_size
        sw, sh = surface.get_size()
        if self._trail_surface is None or self._trail_surface.get_size() != (sw, sh):
            self._trail_surface = pygame.Surface((sw, sh), pygame.SRCALPHA)
        layer = self._trail_surface
        layer.fill((0, 0, 0, 0))
        pad = 8
        for c, r in self.player_walked:
            x, y = c * ts - ox, r * ts - oy
            if -ts < x < sw and -ts < y < sh:
                pygame.draw.rect(layer, (*PLAYER_TRAIL_COLOR, PLAYER_TRAIL_ALPHA),
                                 (x + pad, y + pad, ts - 2 * pad, ts - 2 * pad))
        surface.blit(layer, (0, 0))

    def _panel(self, surface, rect):
        """Translucent backing so HUD text stays readable over sprites /
        fire when the camera is pinned in a corner."""
        p = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        p.fill((12, 14, 20, 165))
        surface.blit(p, rect.topleft)

    def _draw_hud(self, surface):
        f = self.hud_font

        # ---- left panel: rescue count / AI health / key ----
        self._panel(surface, pygame.Rect(8, 8, 340, 78))
        total = len(self.victims)
        total_saved = sum(1 for v in self.victims if v.state == STATE_SAVED)
        surface.blit(f.render(
            f"Rescued {total_saved}/{total}   You {self.player_stats.victims_saved}"
            f"   AI {self.agent_stats.victims_saved}", True, FONT_COLOR), (16, 14))

        ah = max(0.0, min(1.0, self.agent.health / HEALTH_MAX))
        pygame.draw.rect(surface, HEALTH_BAR_BG_COLOR, pygame.Rect(16, 40, 120, 10))
        pygame.draw.rect(surface, (120, 150, 210), pygame.Rect(16, 40, round(120 * ah), 10))
        surface.blit(f.render("AI drone", True, (150, 170, 210)), (144, 36))

        if self.hazards.doors.enabled and not self.hazards.doors.key_collected:
            surface.blit(f.render("Door locked - find the key", True, KEY_COLOR), (16, 60))
        elif self.hazards.doors.enabled:
            surface.blit(f.render("Key collected", True, (140, 200, 140)), (16, 60))

        # ---- right panel: health / run time / fire countdown ----
        x = SCREEN_WIDTH - HEALTH_BAR_WIDTH - HEALTH_BAR_MARGIN
        self._panel(surface, pygame.Rect(x - 10, 8, HEALTH_BAR_WIDTH + 20, 92))
        y = HEALTH_BAR_MARGIN
        bg = pygame.Rect(x, y, HEALTH_BAR_WIDTH, HEALTH_BAR_HEIGHT)
        pygame.draw.rect(surface, HEALTH_BAR_BG_COLOR, bg)
        frac = max(0.0, min(1.0, self.player.health / HEALTH_MAX))
        pygame.draw.rect(surface, _health_bar_color(frac),
                         pygame.Rect(x, y, round(HEALTH_BAR_WIDTH * frac), HEALTH_BAR_HEIGHT))
        pygame.draw.rect(surface, HEALTH_BAR_BORDER_COLOR, bg, 2)
        surface.blit(f.render("HEALTH", True, FONT_COLOR), (x, y + HEALTH_BAR_HEIGHT + 3))

        elapsed = self.player_stats.elapsed
        surface.blit(f.render(f"Time  {int(elapsed // 60)}:{int(elapsed % 60):02d}",
                              True, FONT_COLOR), (x + 96, y + HEALTH_BAR_HEIGHT + 3))
        if self.hazards.fire.exit_on_fire:
            label, colour = "EXIT ON FIRE", (240, 90, 60)
        else:
            left = self.hazards.fire.seconds_to_exit_fire
            colour = (240, 90, 60) if left < 15 else (
                (235, 175, 70) if left < 35 else (205, 205, 210))
            label = f"Fire -> exit  {int(left // 60)}:{int(left % 60):02d}"
        surface.blit(f.render(label, True, colour), (x, y + HEALTH_BAR_HEIGHT + 24))


# ---------------------------------------------------------------- entry point
def _disable_windows_dpi_scaling():
    """Without this, Windows stretches the 960x640 window to fit the
    display's scaling factor and everything looks blurry. No-op elsewhere."""
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    except (ImportError, AttributeError, OSError):
        pass


def main():
    _disable_windows_dpi_scaling()
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Pyro Pete - Emergency Evacuation")
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont(None, 44)
    head_font = pygame.font.SysFont(None, 30)
    body_font = pygame.font.SysFont(None, 24)

    session = GameSession(level_01.build())

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    session.reset()

        session.update(dt, pygame.key.get_pressed())

        screen.fill((0, 0, 0))
        session.draw(screen)
        if session.state == "results":
            draw_results(screen, title_font, head_font, body_font,
                         session.player_stats, session.agent_stats,
                         len(session.victims))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
