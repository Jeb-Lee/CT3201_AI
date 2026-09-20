"""Pyro Pete: Emergency Evacuation.

You drive Pete (WASD / arrows) through a burning, collapsing maze, picking
up trapped occupants and leading them to the exit. An autonomous AI rescue
agent (entities.rescue_agent.RescueAgent) runs the same maze at the same
time under the same rules -- it has health, takes hazard damage, and plans
with hazard-weighted A* that it re-runs whenever the map changes under it.
Its intended route is drawn on the floor.

You and the agent share one pool of occupants. Reaching the exit banks
whoever you are escorting and nothing more; the stage ends when everyone
left alive has been found and someone gets out (or all are already out),
or when nobody still alive can carry on. A rescuer that dies loses the
occupants it was escorting, and they come off the total. A results panel
compares the two rescuers over the same clock -- victims saved, time,
distance, damage, and (agent only) how many times the shifting hazards
forced it to re-plan. You clear the stage if you are alive at the end
and led at least one occupant out.

Clearing a stage promotes you to the next of the ten in levels/STAGES,
which scale up through bigger floor plans, more occupants and harsher
hazards (levels/tuning.py). Losing one puts you back at the menu.

Hazards (see hazard_field.HazardField): spreading fire + functional smoke
(slows you, closes in your view), stationary sparking panels, ceilings
that collapse into impassable rubble mid-run, and one locked door whose
key is hidden on a side branch.

Controls: WASD / arrows move, P pause, R restart, M mute, Esc quit.
On the results panel, Enter advances to the next stage after a clear, or
returns to the menu otherwise.
"""

import sys
from collections import deque

import pygame

from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS,
    VICTIM_COUNT, VICTIM_RESCUE_RADIUS,
    PLAYER_TRAIL_MAXLEN, AGENT_TRAIL_MAXLEN,
    VICTIM_FOLLOW_LAG_FRAMES, VICTIM_FOLLOW_SPACING_FRAMES,
    PLAYER_TRAIL_COLOR, PLAYER_TRAIL_ALPHA,
)
from entities.player import Player
from entities.victim import (
    place_victims, STATE_IDLE, STATE_FOLLOWING, STATE_SAVED, STATE_DEAD,
)
from entities.rescue_agent import RescueAgent
from entities.learned_agent import LearnedAgent
from camera import Camera
from hazard_field import HazardField
from visibility import VisibilitySystem
from stats import RunStats
from results import draw_results, draw_watch_results
from fonts import ui_font
from hud import Hud
from notice import Notices
from pause import PauseScreen
import levels
from levels.tuning import DEFAULT as DEFAULT_TUNING
from intro import IntroScene
from menu import ChoiceMenu, build_menu_background
from audio import AudioManager
from ml.policy import available_models, load_policy

FONT_COLOR = (230, 230, 230)


# ---------------------------------------------------------------- rescue logic
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


def _lose_escorted(follow_order):
    """A rescuer died: everyone it was still escorting dies with it. They
    come off the stage total rather than staying on it as people nobody
    can reach. Anyone it had already led out stays saved."""
    for victim in follow_order:
        if victim.state == STATE_FOLLOWING:
            victim.state = STATE_DEAD


def _mark_saved(follow_order):
    for victim in follow_order:
        if victim.state == STATE_FOLLOWING:
            victim.state = STATE_SAVED


# ---------------------------------------------------------------- game session
# search-order settings a run may switch on for the AI body (RescueAgent)
AGENT_OPTION_NAMES = ("frontier_lean", "frontier_min_reveal", "frontier_defer_small")


class GameSession:
    """All the per-run state, so restarting is just reset() and main()
    stays a thin pygame shell around update()/draw().

    spectate=True is "Watch AI Play": no Pete at all -- the camera and fog
    of war follow the AI instead, and the run ends (and shows a
    single-column results panel) by the same rules as a race, with the AI
    as the only rescuer.

    agent_visual picks the AI's look ("robot" or "drone") for this run --
    an explicit menu choice rather than always reading settings.AGENT_VISUAL,
    so different runs in the same session can look different."""

    def __init__(self, stage, spectate=False, agent_visual=None, stage_index=0,
                 agent_brain="astar", policy=None, agent_options=None):
        """stage is a module from levels.STAGES -- it carries the map
        (build()), its fixed SEED, and the per-stage difficulty TUNING.
        Taking the module rather than a bare TileMap is what lets one
        GameSession serve all ten stages unchanged.

        agent_brain picks how the AI decides: "astar" (the default -- the
        hazard-weighted route planner) or "learned" (a trained policy,
        see ml/). It only ever affects the AI player; Pete is always
        human. `policy` is the object a learned brain asks for its moves
        (ml.policy); it may be None when something else is stepping the
        agent from outside, as the training environment does."""
        self.stage = stage
        self.agent_brain = agent_brain
        self.policy = policy
        # optional search-order settings for the AI body (see RescueAgent); a
        # policy can carry its own (a model trained to copy a variant needs the
        # same variant in its observation), explicit ones win
        self.agent_options = dict(getattr(policy, "agent_options", None) or {})
        self.agent_options.update(agent_options or {})
        self.stage_index = stage_index
        self.tuning = getattr(stage, "TUNING", DEFAULT_TUNING)
        self.tilemap = stage.build()
        self.spectate = spectate
        self.agent_visual = agent_visual
        self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT,
                             self.tilemap.pixel_width, self.tilemap.pixel_height)
        self.visibility = VisibilitySystem()
        self.hud = Hud()
        # the red "!" over a waiting occupant is a gameplay cue, so it keeps
        # heading size (about the height it had before) rather than shrinking to body
        self.marker_font = ui_font("heading")
        self._trail_surface = None  # reused draw buffer for Pete's trail
        self.reset()

    def reset(self):
        tm = self.tilemap
        tm.clear_dynamic_blocks()
        self.visibility.reset()

        spawn_x, spawn_y = tm.spawn_pos()
        # Player object always exists (RescueAgent's _occupied_cells wants
        # someone to check against) but in spectate mode it's never fed
        # input, updated, or drawn -- see the `if not self.spectate` guards
        # below.
        self.player = Player(spawn_x, spawn_y)
        self.player_stats = RunStats("You (Pete)", kind="you", brain="human")
        label = "AI drone" if self.agent_visual != "robot" else "AI robot"
        if self.agent_brain == "learned":
            label += f" ({getattr(self.policy, 'label', None) or 'learned'})"
        self.agent_stats = RunStats(
            label, kind="robot" if self.agent_visual == "robot" else "drone",
            brain=self.agent_brain)

        self.hazards = HazardField(
            tm, seed=self.stage.SEED,
            protected_cells_fn=self._protected_cells,
            occupied_cells_fn=self._occupied_cells,
            tuning=self.tuning,
        )
        victim_count = self.tuning.victim_count or VICTIM_COUNT
        self.victims = place_victims(
            tm, victim_count, exclude_cells=self.hazards.reserved_cells()
        )
        self.hazards.activate_door()  # after victims, so they spawn on a doorless map

        self.player_trail = deque(maxlen=PLAYER_TRAIL_MAXLEN)
        self.player_follow_order = []
        self.player_done = None  # "exit" | "dead" | None
        self.player_walked = {tm.spawn_cell}  # every cell Pete has stepped on

        agent_args = dict(hazard_field=self.hazards, stats=self.agent_stats,
                          visual=self.agent_visual,
                          speed_scale=self.tuning.agent_speed_scale)
        if self.agent_brain == "learned":
            self.agent = LearnedAgent(tm, tm.spawn_cell, policy=self.policy, **agent_args)
        else:
            self.agent = RescueAgent(tm, tm.spawn_cell, **agent_args)
        for name, value in self.agent_options.items():
            if name not in AGENT_OPTION_NAMES:
                raise ValueError(f"unknown agent option {name!r}")
            setattr(self.agent, name, value)
        self.agent_trail = deque(maxlen=AGENT_TRAIL_MAXLEN)
        self.agent_follow_order = []

        # Race outcome, set by _end_stage: "cleared" (alive, and led at least
        # one occupant out), "outrun" (alive, but the stage ended without
        # him saving anyone), "died" (Pete burned). The
        # campaign in main() reads this to decide whether to advance a
        # stage or re-run the same one.
        self.outcome = None
        # True once the stage ended because everyone left alive was
        # evacuated (as opposed to nobody being able to carry on).
        self.evacuated = False

        self.state = "playing"  # "playing" | "results"
        # Independent of `state`: freezes update() (hazards, both rescuers,
        # timers) without touching run state, so unpausing resumes exactly
        # where it left off. Always cleared on reset so a restart never
        # comes back up paused.
        self.paused = False
        self.hud.reset()

    # -- occupant counters ------------------------------------------------
    @property
    def victims_out(self):
        """Occupants who have actually reached the exit, led there by
        either rescuer. Being picked up isn't enough -- an occupant is only
        "out" once whoever is escorting them gets to the exit, which is
        exactly when their state flips to SAVED."""
        return sum(1 for v in self.victims if v.state == STATE_SAVED)

    @property
    def victims_dead(self):
        """Occupants lost with a rescuer that died while escorting them."""
        return sum(1 for v in self.victims if v.state == STATE_DEAD)

    @property
    def victims_remaining(self):
        """Occupants who can still be saved and aren't out yet: the stage
        total, minus those lost, minus those out."""
        return len(self.victims) - self.victims_dead - self.victims_out

    # -- campaign helpers ------------------------------------------------
    @property
    def stage_label(self):
        return levels.label(self.stage_index)

    @property
    def has_next_stage(self):
        return self.stage_index + 1 < levels.STAGE_COUNT

    @property
    def cleared(self):
        """True when this stage was beaten: Pete got out in a race, or the
        AI got itself out in watch mode."""
        if self.spectate:
            # The AI wins by seeing the evacuation through and surviving
            # it. Giving up early with people still inside is not a win.
            return self.evacuated and not self.agent.is_dead
        return self.outcome == "cleared"

    # -- whichever entity the camera/fog should follow -------------------
    @property
    def _view_anchor(self):
        return self.agent if (self.spectate or self.player.is_dead) else self.player

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
        if self.state != "playing" or self.paused:
            return
        tm = self.tilemap

        if not self.spectate and self.player_done is None:
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
                # Pete is out of it, and so is everyone he was escorting.
                # The stage carries on for the AI (see _resolve_stage).
                self.player_done = "dead"
                _lose_escorted(self.player_follow_order)
            elif tm.is_exit_rect(self.player.get_collision_rect()):
                # Reaching the exit banks whoever he is escorting -- and
                # that is all it does. It no longer ends the stage, so
                # walking out empty-handed can't be a win.
                _mark_saved(self.player_follow_order)

        self.hazards.update(dt)

        if not self.agent.done:
            self.agent_stats.tick(dt)
        self.agent.update(dt, self.victims)
        self.agent_trail.append((self.agent.x, self.agent.y))
        _try_rescue(self.victims, self.agent.get_rect(), self.agent_follow_order)
        _advance_escort(self.agent_follow_order, self.agent_trail)
        self.hazards.doors.try_pickup(self.agent.get_rect())
        if self.agent.is_dead:
            _lose_escorted(self.agent_follow_order)
        elif self.agent.current_cell == tm.exit_cell:
            _mark_saved(self.agent_follow_order)

        self._resolve_stage()

        anchor = self._view_anchor
        self.camera.update(anchor.x, anchor.y)
        self.visibility.update(anchor, self.hazards)

        self.player_stats.set_saved(
            sum(1 for v in self.player_follow_order if v.state == STATE_SAVED))
        self.agent_stats.set_saved(
            sum(1 for v in self.agent_follow_order if v.state == STATE_SAVED))

        self.hud.update(dt, self)

    # -- when does the stage end? -------------------------------------------
    def _resolve_stage(self):
        """One place that decides whether the stage is over.

        Every occupant is in one of four states: waiting to be found,
        being escorted, out, or lost with a rescuer that died. The stage
        ends when either:

          * everyone left alive has been found AND either nobody is still
            being escorted (they are all out), or a rescuer -- Pete or the
            AI -- has reached the exit; or
          * nobody who is still alive can carry on (Pete dead or absent,
            and the AI dead or finished).

        Reaching the exit on its own ends nothing: with occupants still
        waiting to be found it just banks whoever that rescuer was
        escorting. The second condition is the safety net that stops a
        stage hanging forever once the last rescuer has given up or died.
        """
        if self.state != "playing" or not self.victims:
            return
        tm = self.tilemap
        idle = sum(1 for v in self.victims if v.state == STATE_IDLE)
        following = sum(1 for v in self.victims if v.state == STATE_FOLLOWING)

        pete_alive = not self.spectate and not self.player.is_dead
        ai_alive = not self.agent.is_dead
        at_exit = ((pete_alive and tm.is_exit_rect(self.player.get_collision_rect()))
                   or (ai_alive and self.agent.current_cell == tm.exit_cell))

        evacuated = idle == 0 and (following == 0 or at_exit)
        nobody_left = not pete_alive and not (ai_alive and not self.agent.done)
        if evacuated or nobody_left:
            self.evacuated = evacuated
            self._end_stage()

    def _end_stage(self):
        tm = self.tilemap
        if self.agent.is_dead:
            agent_reason = "dead"
        elif self.agent.current_cell == tm.exit_cell:
            agent_reason = "exit"
        else:
            agent_reason = "time"
        self.agent_stats.finish(agent_reason)

        if not self.spectate:
            saved = sum(1 for v in self.player_follow_order if v.state == STATE_SAVED)
            if self.player.is_dead:
                player_reason, self.outcome = "dead", "died"
            elif saved >= 1:
                # He led at least one occupant out and is still alive.
                player_reason = "exit" if tm.is_exit_rect(
                    self.player.get_collision_rect()) else "time"
                self.outcome = "cleared"
            else:
                # Alive, but the stage ended without him saving anyone.
                player_reason, self.outcome = "time", "outrun"
            self.player_done = {"cleared": "exit", "died": "dead"}.get(self.outcome, "outrun")
            self.player_stats.finish(player_reason)
        self.state = "results"

    # -- draw -------------------------------------------------------
    def draw(self, surface):
        cam = self.camera.offset
        self.tilemap.draw(surface, cam)
        self.hazards.draw_ground(surface, cam)
        for victim in self.victims:
            victim.draw(surface, cam, font=self.marker_font)
        if not self.spectate:
            self.player.draw(surface, cam)
        self.visibility.draw(surface, self._view_anchor, cam, self.hazards)

        # Trails + the AI's planned route are drawn ON TOP of the fog on
        # purpose: the point of running an autonomous agent next to the
        # player is being able to compare where each one went, so both
        # paths stay visible even in unlit parts of the maze.
        if not self.spectate:
            self._draw_player_trail(surface, cam)
        self.agent.draw_route(surface, cam)
        self.agent.draw(surface, cam)

        mouse = pygame.mouse.get_pos() if pygame.mouse.get_focused() else None
        self.hud.draw(surface, self, mouse)

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

    # A HUD panel fades to this when the rescuer you are steering is
    # underneath it. Every stage spawns at cell (1, 1) and the camera
    # clamps at the map edge, so the first seconds of every run put you
    # squarely behind the top-left panel -- readable HUD, invisible
    # player. Fading is better than moving the panel: the corner you are
    # in changes, the information does not.
    HUD_ALPHA = 255
    HUD_ALPHA_OCCLUDED = 70

    def _anchor_behind(self, rect):
        anchor = self._view_anchor
        ox, oy = self.camera.offset
        # inflated by roughly a sprite, so it fades just before the
        # overlap rather than at the moment you are already hidden
        return rect.inflate(52, 52).collidepoint(anchor.x - ox, anchor.y - oy)


# ---------------------------------------------------------------- entry point
def _disable_windows_dpi_scaling():
    """Without this, Windows stretches the 960x640 window to fit the
    display's scaling factor and everything looks blurry. No-op elsewhere."""
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    except (ImportError, AttributeError, OSError):
        pass


def _build_mode_menu(background=None):
    return ChoiceMenu(
        "Pyro Pete",
        [
            ("Play vs AI", "play", "Race the AI rescuer yourself"),
            ("Watch AI Play", "watch", "Sit back and watch the AI solve it alone"),
        ],
        subtitle="Choose a mode",
        background=background,
    )


def _build_skin_menu(background=None):
    return ChoiceMenu(
        "Choose the AI's Look",
        [
            ("Robot", "robot", "The walking rescue robot"),
            ("Drone", "drone", "The original quadcopter"),
        ],
        subtitle="How should the AI opponent appear?",
        background=background,
    )


def _build_brain_menu(models=None, background=None):
    """A* first (the default, highlighted when the menu opens), then every
    learned model whose file is present (ml.policy.available_models)."""
    if models is None:
        models = available_models()
    options = [("A* planner", "astar", "The original hazard-aware route planner")]
    options += [(label, "model:" + key, desc) for key, label, desc, _path in models]
    return ChoiceMenu(
        "Choose the AI's Brain",
        options,
        subtitle="How should the AI opponent decide where to go?",
        background=background,
    )


def _brain_choices(mode, models):
    """The models to offer on the brain menu, or [] for no menu. Watch AI Play always
    offers them; Play vs AI (Pete against an A* rival) only when a model was installed
    as ml/models/ai_policy.zip, as before, so an ordinary checkout's Play flow has no
    extra screen."""
    if mode == "watch" or any(key == "installed" for key, *_ in models):
        return list(models)
    return []


def _new_session(stage_index, mode, visual, brain):
    """Build a session for the chosen options. `brain` is "astar" or
    "model:<key>" (ml.policy.available_models). A learned brain needs its
    model loaded; if that fails for any reason the run falls back to the
    A* planner rather than refusing to start."""
    policy = None
    agent_brain = "astar"
    if brain.startswith("model:"):
        key = brain.split(":", 1)[1]
        try:
            path = next(p for k, _label, _desc, p in available_models() if k == key)
            policy = load_policy(path)
            policy.label = next(label for k, label, _d, _p in available_models() if k == key)
            agent_brain = "learned"
        except Exception as exc:
            print(f"Could not load the learned model {key!r} ({exc}); using the A* planner instead.")
            policy = None
    return GameSession(levels.get(stage_index), spectate=(mode == "watch"),
                       agent_visual=visual, stage_index=stage_index,
                       agent_brain=agent_brain, policy=policy)


def main():
    """Thin pygame shell that steps through the run's screens in order:

        intro -> menu_mode -> menu_skin -> [menu_brain] -> playing/watching -> results

    (menu_brain only appears when a trained model exists -- see ml/policy.py)
                    ^________________________________________|
                          (Enter on the results panel)

    Each app_state's update() runs first (handles its own input and may
    advance app_state), then its draw() -- kept as two separate passes so a
    state transition mid-frame never draws half of two different screens.
    """
    _disable_windows_dpi_scaling()
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Pyro Pete - Emergency Evacuation")
    clock = pygame.time.Clock()
    # Falls back to silence on a machine with no audio device -- see audio.py.
    audio = AudioManager()

    title_font = ui_font("title")
    head_font = ui_font("heading")
    body_font = ui_font("body")
    total_font = ui_font("body", bold=True)      # the results' Total row
    small_font = ui_font("small")                # the results' "role \u00b7 outcome" line
    pause_screen = PauseScreen()
    notices = Notices()                          # "Sound off" and the muted chip, on every screen

    # Built once here (not per-call, and not at module import time): it
    # loads sprites via convert_alpha(), which needs the display created
    # above by set_mode() to already exist -- same ordering trap that once
    # bit the robot sprite loader in rescue_agent.py. Same Surface is
    # reused behind every menu screen instead of re-decoding the same PNGs
    # and re-blitting the building crop each time a menu is (re)built.
    menu_background = build_menu_background()

    app_state = "intro"
    intro_scene = IntroScene()
    mode_menu = _build_mode_menu(menu_background)
    skin_menu = None
    brain_menu = None
    chosen_mode = None
    chosen_visual = "robot"
    chosen_brain = "astar"
    session = None
    stage_index = 0  # 0-based position in levels.STAGES for this campaign run

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        events = pygame.event.get()
        notices.update(dt)

        for event in events:
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                audio.toggle_mute()
                notices.sound_changed(audio)
        if not running:
            break

        # ---- update ----
        if app_state == "intro":
            intro_scene.update(dt, events)
            if intro_scene.finished:
                app_state = "menu_mode"
                mode_menu = _build_mode_menu(menu_background)

        elif app_state == "menu_mode":
            mode_menu.update(dt, events)
            if mode_menu.result is not None:
                chosen_mode = mode_menu.result
                skin_menu = _build_skin_menu(menu_background)
                app_state = "menu_skin"

        elif app_state == "menu_skin":
            skin_menu.update(dt, events)
            if skin_menu.result is not None:
                chosen_visual = skin_menu.result
                models = _brain_choices(chosen_mode, available_models())
                if models:
                    # only offered once a trained model exists, so a
                    # checkout without one never sees this screen
                    brain_menu = _build_brain_menu(models, menu_background)
                    app_state = "menu_brain"
                else:
                    chosen_brain = "astar"
                    stage_index = 0  # every campaign starts at stage 1
                    session = _new_session(stage_index, chosen_mode, chosen_visual, chosen_brain)
                    app_state = "playing" if chosen_mode == "play" else "watching"
            elif skin_menu.cancelled:
                app_state = "menu_mode"
                mode_menu = _build_mode_menu(menu_background)

        elif app_state == "menu_brain":
            brain_menu.update(dt, events)
            if brain_menu.result is not None:
                chosen_brain = brain_menu.result
                stage_index = 0
                session = _new_session(stage_index, chosen_mode, chosen_visual, chosen_brain)
                app_state = "playing" if chosen_mode == "play" else "watching"
            elif brain_menu.cancelled:
                skin_menu = _build_skin_menu(menu_background)
                app_state = "menu_skin"

        elif app_state in ("playing", "watching"):
            for event in events:
                if event.type != pygame.KEYDOWN:
                    continue
                if event.key == pygame.K_r:
                    session.reset()
                elif event.key == pygame.K_p and session.state == "playing":
                    session.paused = not session.paused
                elif (session.state == "results"
                      and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER)):
                    # Clearing a stage promotes you to the next one; losing
                    # it (or finishing the campaign) drops back to the menu.
                    if session.cleared and session.has_next_stage:
                        stage_index = session.stage_index + 1
                        # same AI brain (and already-loaded model) for the
                        # whole campaign run
                        session = GameSession(levels.get(stage_index),
                                              spectate=session.spectate,
                                              agent_visual=chosen_visual,
                                              stage_index=stage_index,
                                              agent_brain=session.agent_brain,
                                              policy=session.policy)
                    else:
                        app_state = "menu_mode"
                        mode_menu = _build_mode_menu(menu_background)
            if app_state in ("playing", "watching"):
                session.update(dt, pygame.key.get_pressed())

        # ---- music ----
        # Each screen just names the track it wants; AudioManager.play()
        # no-ops when that track is already running, so this stays a
        # simple per-frame statement instead of transition bookkeeping.
        if app_state == "intro":
            audio.play("title")
        elif app_state in ("menu_mode", "menu_skin", "menu_brain"):
            audio.play("menu")
        elif session is not None and session.state == "results":
            audio.play("win" if session.cleared else "loss")
        else:
            audio.play("game")

        # ---- draw ----
        screen.fill((0, 0, 0))
        if app_state == "intro":
            intro_scene.draw(screen)
        elif app_state == "menu_mode":
            mode_menu.draw(screen)
        elif app_state == "menu_skin":
            skin_menu.draw(screen)
        elif app_state == "menu_brain":
            brain_menu.draw(screen)
        elif app_state in ("playing", "watching"):
            session.draw(screen)
            if session.state == "results":
                if session.spectate:
                    draw_watch_results(screen, title_font, head_font, body_font,
                                       session.agent_stats, len(session.victims),
                                       stage_label=session.stage_label,
                                       cleared=session.cleared,
                                       has_next_stage=session.has_next_stage,
                                       total_font=total_font, small_font=small_font)
                else:
                    draw_results(screen, title_font, head_font, body_font,
                                 session.player_stats, session.agent_stats,
                                 len(session.victims),
                                 outcome=session.outcome,
                                 stage_label=session.stage_label,
                                 has_next_stage=session.has_next_stage,
                                 total_font=total_font, small_font=small_font)
            elif session.paused:
                pause_screen.draw(screen, session, audio)

        notices.draw(screen, audio)                  # over everything, including the pause panel
        pygame.display.flip()

    audio.stop()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
