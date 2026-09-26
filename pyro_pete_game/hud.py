"""The in-game HUD: a versus layout that reacts to what happens.

    top-left    YOU card    portrait, health bar, score              (gold)
    top-right   AI card     portrait, health bar, score              (blue)
    top-centre  fire clock  countdown to the exit, urgency states
    bottom      mission     stage, one icon per occupant, key, run time
    on demand   toasts, floating "+100"s, a damage vignette, hover tooltips

It is a view of a GameSession plus some purely cosmetic animation state
(ghost health, hit flashes, score pops, toasts). Nothing here changes the game:
update() only reads the session, draw() only draws.

Fonts come from fonts.ui_font, so the HUD shares the game's one typeface and
size scale.
"""

import math
from dataclasses import dataclass

import pygame

from entities.victim import STATE_IDLE, STATE_FOLLOWING
from fonts import ui_font
from hud_icons import (
    TEXT, DIM, EDGE, BLUE, GREEN, lerp_colour, ease_out, shadowed_text, gradient_panel, drop_shadow,
    flame, person, cross, key_icon, padlock, clock_icon, tick, drone_icon, hint_row_width, key_hint_row,
)
from portraits import portrait_image
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, HEALTH_MAX, SCORE_PER_SURVIVOR,
    HEALTH_BAR_COLOR_FULL, HEALTH_BAR_COLOR_MID, HEALTH_BAR_FILL_COLOR,
    RESULTS_ACCENT_COLOR,
)

# --- palette ---------------------------------------------------------------
GOLD = RESULTS_ACCENT_COLOR                 # Pete / "you" (the same gold as the menus)
POS, NEG = (150, 210, 150), (222, 130, 110)
FIRE_CALM, FIRE_WARN, FIRE_HOT = (222, 224, 230), (240, 178, 64), (240, 84, 58)

# --- geometry ----------------------------------------------------------------
MARGIN = 10
CARD_W, CARD_H = 268, 84
CLOCK_W, CLOCK_H = 214, 90
STRIP_H = 44

# --- timing (seconds) ------------------------------------------------------------
INTRO = 0.55                # panels slide in when a stage starts
POP = 0.5                   # score / occupant-pip pop
HIT = 0.35                  # portrait + screen flash after damage
GHOST_HOLD = 0.45           # the pale "you just lost this" bar segment waits...
GHOST_DRAIN = 70.0          # ...then drains at this many health points a second
TOAST_LIFE = 2.6
BANNER_LIFE = 3.2
CONTROLS_LIFE = 5.5         # the first stage's banner stays up long enough to read the keys
FLOAT_LIFE = 0.9
MAX_TOASTS = 3
FIRE_WARN_SECONDS, FIRE_HOT_SECONDS = 35, 15


def health_colour(frac):
    """Green at full health, through amber, to red -- the bar's colour ramp."""
    frac = max(0.0, min(1.0, frac))
    if frac >= 0.5:
        t, a, b = (1.0 - frac) / 0.5, HEALTH_BAR_COLOR_FULL, HEALTH_BAR_COLOR_MID
    else:
        t, a, b = (0.5 - frac) / 0.5, HEALTH_BAR_COLOR_MID, HEALTH_BAR_FILL_COLOR
    return lerp_colour(a, b, t)


def fire_zone(fire):
    """0 calm, 1 warning, 2 danger, 3 the exit is on fire."""
    if fire.exit_on_fire:
        return 3
    left = fire.seconds_to_exit_fire
    return 2 if left < FIRE_HOT_SECONDS else 1 if left < FIRE_WARN_SECONDS else 0


@dataclass
class Toast:
    text: str
    colour: tuple
    life: float = TOAST_LIFE
    age: float = 0.0
    sub: str = ""               # a banner's second line
    big: bool = False           # a banner rather than a pill
    hints: tuple = ()           # key caps under a banner: ((key, what it does), ...)

    @property
    def alpha(self):
        """Fades in over 0.2s and out over the last 0.45s."""
        return max(0.0, min(1.0, self.age / 0.2, (self.life - self.age) / 0.45))


@dataclass
class Row:
    """One line of a tooltip."""
    text: str
    colour: tuple = DIM
    value: str = ""
    vcolour: tuple = TEXT
    head: bool = False          # a heading: bold, larger
    rule: bool = False          # a thin line above this row
    marker: tuple = None        # ("person", fill, outline) drawn before the text


def _new_rescuer():
    return {"h": None, "ghost": None, "hold": 0.0, "hit": 0.0, "score": 0, "pop": 0.0}


class Hud:
    def __init__(self):
        self.f_title = ui_font("title")
        self.f_head = ui_font("heading")
        self.f_body = ui_font("body", bold=True)
        self.f_small = ui_font("small")
        self.f_chip = ui_font("small", bold=True)
        self._panels, self._shadows = {}, {}
        self._vignette = None
        self.reset()

    def reset(self):
        """Fresh animation state -- a new stage or a restart."""
        self.t = 0.0
        self._r = {"you": _new_rescuer(), "ai": _new_rescuer()}
        self._snap = None
        self._out_pop = 0.0
        self.toasts = []
        self.floats = []            # [who, text, age]
        self.hot = []               # (rect, kind): hover regions from the last draw

    # =====================================================================
    #  animation state + events
    # =====================================================================
    def update(self, dt, s):
        self.t += dt
        snap = self._snapshot(s)
        if self._snap is None:
            self._stage_banner(s)
        else:
            self._events(self._snap, snap, s)
            if snap["out"] > self._snap["out"]:
                self._out_pop = POP
        self._snap = snap

        if not s.spectate:
            self._track("you", s.player.health, s.player_stats.score, dt)
        self._track("ai", s.agent.health, s.agent_stats.score, dt)
        self._out_pop = max(0.0, self._out_pop - dt)

        for t in self.toasts:
            t.age += dt
        self.toasts = [t for t in self.toasts if t.age < t.life]
        for f in self.floats:
            f[2] += dt
        self.floats = [f for f in self.floats if f[2] < FLOAT_LIFE]

    def _snapshot(self, s):
        return {
            "saved_you": 0 if s.spectate else s.player_stats.victims_saved,
            "saved_ai": s.agent_stats.victims_saved,
            "out": s.victims_out,
            "lost": s.victims_dead,
            "key": s.hazards.doors.key_collected,
            "you_dead": (not s.spectate) and s.player.is_dead,
            "ai_dead": s.agent.is_dead,
            "zone": fire_zone(s.hazards.fire),
        }

    def _toast(self, text, colour, **kw):
        self.toasts.append(Toast(text, colour, **kw))

    def _stage_banner(self, s):
        goal = ("Watching the AI rescuer work" if s.spectate
                else "Lead every occupant out  ·  the AI is racing you")
        hints = ()
        if s.stage_index == 0:              # a new player's first look at the keys
            hints = ((("P", "Pause"), ("M", "Sound")) if s.spectate
                     else (("WASD", "Move"), ("P", "Pause"), ("M", "Sound")))
        self._toast(s.stage_label.replace(" - ", "  ·  ").upper(), GOLD,
                    life=CONTROLS_LIFE if hints else BANNER_LIFE, sub=goal, big=True, hints=hints)

    def _events(self, prev, now, s):
        """Turn changes in the game into toasts."""
        for who, name, colour in (("you", s.player_stats.display_name, GOLD),
                                  ("ai", s.agent_stats.display_name, BLUE)):
            gained = now[f"saved_{who}"] - prev[f"saved_{who}"]
            if gained > 0:
                what = "an occupant" if gained == 1 else f"{gained} occupants"
                self._toast(f"+{gained * SCORE_PER_SURVIVOR}   {name} led {what} out", colour)
        if now["key"] and not prev["key"]:
            self._toast("Key collected — the door is unlocked", GREEN)
        if now["lost"] > prev["lost"]:
            n = now["lost"] - prev["lost"]
            self._toast("Occupant lost" if n == 1 else f"{n} occupants lost", FIRE_HOT)
        if now["you_dead"] and not prev["you_dead"]:
            self._toast("Pete is down!", FIRE_HOT)
        if now["ai_dead"] and not prev["ai_dead"]:
            self._toast(f"{s.agent_stats.display_name} is down", FIRE_HOT)
        # zone 3 (exit on fire) has no toast: the clock plate itself becomes an
        # "EXIT ON FIRE" banner, and saying it twice a few pixels apart is noise
        if now["zone"] > prev["zone"] and now["zone"] in (1, 2):
            text, colour = {1: ("Fire is spreading toward the exit", FIRE_WARN),
                            2: ("The fire is almost at the exit!", FIRE_HOT)}[now["zone"]]
            self._toast(text, colour)

    def _track(self, who, health, score, dt):
        r = self._r[who]
        if r["h"] is None:
            r["h"] = r["ghost"] = health
            r["score"] = score
        if health < r["h"] - 0.01:                      # took damage
            r["hit"] = HIT
            r["ghost"] = max(r["ghost"], r["h"])
            r["hold"] = GHOST_HOLD
        elif health > r["h"] + 0.01:                    # healed: nothing to ghost
            r["ghost"] = health
        r["h"] = health
        if r["hold"] > 0:
            r["hold"] -= dt
        else:
            r["ghost"] = max(health, r["ghost"] - GHOST_DRAIN * dt)
        # damage also lowers the score a point at a time; only real gains
        # (a rescue, the exit bonus) deserve a "+N" and a pop
        if score - r["score"] >= 10:
            r["pop"] = POP
            self.floats.append([who, f"+{score - r['score']}", 0.0])
        r["score"] = score
        r["hit"] = max(0.0, r["hit"] - dt)
        r["pop"] = max(0.0, r["pop"] - dt)

    # =====================================================================
    #  layout
    # =====================================================================
    def _strip_metrics(self, s):
        n = len(s.victims)
        pip = 24 if n <= 8 else 20 if n <= 12 else 16
        label = s.stage_label.replace("Stage ", "STAGE ").replace(" - ", "  ·  ").upper()
        total = n - s.victims_dead
        count = f"{s.victims_out}/{total}"
        elapsed = (s.agent_stats if s.spectate else s.player_stats).elapsed
        clock = f"{int(elapsed // 60)}:{int(elapsed % 60):02d}"
        w_label = self.f_body.size(label)[0]
        w_pips = max(1, n) * pip
        w_count = self.f_head.size(count)[0]
        w_key = 62 if s.hazards.doors.enabled else 0
        w_clock = 26 + self.f_body.size("00:00")[0]
        width = 14 + w_label + 18 + w_pips + 8 + w_count + 15 + w_key + w_clock + 14
        return dict(pip=pip, label=label, count=count, clock=clock, w_label=w_label,
                    w_pips=w_pips, w_count=w_count, w_key=w_key, width=width)

    def layout(self, s):
        """Every panel's resting rectangle, by name."""
        rects = {}
        if s.spectate:
            rects["ai"] = pygame.Rect(MARGIN, MARGIN, CARD_W, CARD_H)
        else:
            rects["you"] = pygame.Rect(MARGIN, MARGIN, CARD_W, CARD_H)
            rects["ai"] = pygame.Rect(SCREEN_WIDTH - MARGIN - CARD_W, MARGIN, CARD_W, CARD_H)
        rects["fire"] = pygame.Rect((SCREEN_WIDTH - CLOCK_W) // 2, MARGIN, CLOCK_W, CLOCK_H)
        strip = pygame.Rect(0, 0, self._strip_metrics(s)["width"], STRIP_H)
        strip.midbottom = (SCREEN_WIDTH // 2, SCREEN_HEIGHT - MARGIN)
        rects["strip"] = strip
        return rects

    # =====================================================================
    #  drawing
    # =====================================================================
    def draw(self, surface, s, mouse=None):
        self.hot = []
        rects = self.layout(s)
        intro = ease_out(self.t / INTRO)
        self._draw_vignette(surface, s)
        for who in ("you", "ai"):
            if who in rects:
                self._card(surface, rects[who], who, s, intro)
        self._fire_clock(surface, rects["fire"], s, ease_out((self.t - 0.12) / INTRO))
        self._mission_strip(surface, rects["strip"], s, intro)
        self._draw_toasts(surface)
        self._draw_hover(surface, s, mouse)

    # ---- shared helpers ------------------------------------------------
    def _panel(self, size, accent=None):
        key = (size, accent)
        if key not in self._panels:
            self._panels[key] = gradient_panel(size, accent)
        return self._panels[key]

    def _shadow(self, size):
        if size not in self._shadows:
            self._shadows[size] = drop_shadow(size)
        return self._shadows[size]

    def _put(self, surface, img, rest, dy, s, kind=None):
        """Blit a panel at its resting spot (+dy while sliding in). It fades when
        the rescuer you are steering is underneath it: every stage spawns at
        cell (1, 1) and the camera clamps at the map edge, so the first seconds
        put you squarely behind the top-left corner."""
        alpha = s.HUD_ALPHA_OCCLUDED if s._anchor_behind(rest) else s.HUD_ALPHA
        if alpha >= 200:
            surface.blit(self._shadow(rest.size), (rest.x - 6, rest.y + dy - 3))
        img.set_alpha(alpha)
        surface.blit(img, (rest.x, rest.y + dy))
        if kind:
            self.hot.append((rest.move(0, dy), kind))

    # ---- rescuer cards -------------------------------------------------
    def _card(self, surface, rest, who, s, intro):
        r = self._r[who]
        you = who == "you"
        stats = s.player_stats if you else s.agent_stats
        health = s.player.health if you else s.agent.health
        accent = GOLD if you else BLUE
        card = pygame.Surface(rest.size, pygame.SRCALPHA)
        card.blit(self._panel(rest.size, accent), (0, 0))

        # portrait: framed, flashes red when hurt, greys out when down, a tick at the exit
        pr = pygame.Rect(9, 10, 64, 64)
        pygame.draw.rect(card, (8, 9, 13, 255), pr, border_radius=9)
        kind = "pete" if you else ("robot" if s.agent_visual == "robot" else "drone")
        img = portrait_image(kind, 56)               # None for the drone: it is drawn
        if img is not None:
            card.blit(img, img.get_rect(center=pr.center))
        else:
            drone_icon(card, pr)
        if health <= 0:
            veil = pygame.Surface(pr.size, pygame.SRCALPHA)
            veil.fill((40, 40, 46, 190))
            card.blit(veil, pr)
            cross(card, pr.centerx, pr.centery, 22, (220, 70, 60), 4)
        if r["hit"] > 0:
            veil = pygame.Surface(pr.size, pygame.SRCALPHA)
            veil.fill((255, 60, 40, round(150 * r["hit"] / HIT)))
            card.blit(veil, pr)
        pygame.draw.rect(card, (*accent, 255), pr, 2, border_radius=9)
        if stats.finished_reason == "exit":
            pygame.draw.circle(card, (30, 110, 60, 255), (pr.right - 6, pr.bottom - 6), 10)
            tick(card, pr.right - 6, pr.bottom - 6, 5, (235, 250, 235), 2)

        # name, health bar and number
        x0 = pr.right + 12
        name = ("YOU  ·  PETE" if you
                else stats.display_name.upper().replace("AI ", "AI  ·  ", 1))
        shadowed_text(card, self.f_small, name, accent, (x0, 9))
        bar = pygame.Rect(x0, 30, rest.w - x0 - 52, 14)
        self._health_bar(card, bar, health / HEALTH_MAX,
                         None if r["ghost"] is None else r["ghost"] / HEALTH_MAX)
        shadowed_text(card, self.f_body, str(max(0, round(health))), TEXT, (bar.right + 8, 27))

        # score, popping (and showing a "+N") when it rises
        label = shadowed_text(card, self.f_small, "SCORE", DIM, (x0, 63), "midleft")
        pop = r["pop"] / POP
        num = self.f_head.render(str(stats.score), True, lerp_colour(accent, (255, 255, 255), 0.7 * pop))
        if pop > 0:
            k = 1.0 + 0.35 * math.sin(math.pi * (1 - pop))
            num = pygame.transform.smoothscale(
                num, (round(num.get_width() * k), round(num.get_height() * k)))
        num_rect = num.get_rect(midleft=(label.right + 8, 63))
        card.blit(num, num_rect)
        for f_who, text, age in self.floats:
            if f_who == who:
                a = 1.0 - age / FLOAT_LIFE
                shadowed_text(card, self.f_body, text, lerp_colour(accent, (255, 255, 255), 0.5),
                              (num_rect.right + 10, 63 - round(22 * age / FLOAT_LIFE)),
                              "midleft", round(255 * a))
        self._put(surface, card, rest, -round((1 - intro) * (rest.h + 20)), s, kind=who)

    def _health_bar(self, surface, rect, frac, ghost):
        frac = max(0.0, min(1.0, frac))
        pygame.draw.rect(surface, (24, 26, 32, 255), rect, border_radius=6)
        if ghost is not None and ghost > frac:              # what you just lost, fading out
            g = pygame.Rect(rect.x, rect.y, round(rect.w * min(1.0, ghost)), rect.h)
            pygame.draw.rect(surface, (250, 226, 190, 255), g, border_radius=6)
        if frac > 0:
            fill = pygame.Rect(rect.x, rect.y, max(rect.h, round(rect.w * frac)), rect.h)
            pygame.draw.rect(surface, health_colour(frac), fill, border_radius=6)
            gloss = pygame.Surface((fill.w, fill.h // 2), pygame.SRCALPHA)
            pygame.draw.rect(gloss, (255, 255, 255, 62), gloss.get_rect(), border_radius=6)
            surface.blit(gloss, (fill.x, fill.y + 1))
        for i in (1, 2, 3, 4):                              # 20% ticks over the fill
            x = rect.x + round(rect.w * i / 5)
            pygame.draw.line(surface, (0, 0, 0, 90), (x, rect.y + 2), (x, rect.bottom - 3))
        low = 0.5 + 0.5 * math.sin(self.t * 9.0) if 0 < frac < 0.25 else 0.0
        pygame.draw.rect(surface, lerp_colour((96, 100, 114), (240, 70, 58), low), rect, 2,
                         border_radius=6)

    # ---- fire clock ----------------------------------------------------
    def _fire_clock(self, surface, rest, s, intro):
        fire = s.hazards.fire
        zone = fire_zone(fire)
        left = fire.seconds_to_exit_fire
        total = max(1.0, fire.seconds_to_exit_total)
        colour = FIRE_HOT if zone >= 2 else FIRE_WARN if zone == 1 else FIRE_CALM
        pulse = 0.5 + 0.5 * math.sin(self.t * (10.0 if zone >= 2 else 4.0))

        panel = pygame.Surface(rest.size, pygame.SRCALPHA)
        accent = lerp_colour(EDGE, FIRE_HOT, pulse) if zone >= 2 else FIRE_WARN if zone == 1 else None
        panel.blit(self._panel(rest.size, accent), (0, 0))
        if zone >= 2:                                        # a warm glow that breathes
            glow = pygame.Surface(rest.size, pygame.SRCALPHA)
            pygame.draw.rect(glow, (240, 70, 40, round(70 * pulse)), glow.get_rect(), border_radius=12)
            panel.blit(glow, (0, 0))

        cx = rest.w // 2
        if zone == 3:
            flame(panel, 20, 60, 30, self.t)
            flame(panel, rest.w - 20, 60, 30, self.t + 1.3)
            shadowed_text(panel, self.f_head, "EXIT ON FIRE",
                          FIRE_HOT if pulse > 0.4 else (255, 200, 180), (cx, 38), "center")
            shadowed_text(panel, self.f_small, "GET OUT NOW", DIM, (cx, 64), "center")
        else:
            shadowed_text(panel, self.f_small, "FIRE REACHES EXIT IN", DIM, (cx, 17), "center")
            flame(panel, 42, 64, 36, self.t)
            shadowed_text(panel, self.f_title, f"{int(left // 60)}:{int(left % 60):02d}", colour,
                          (cx + 18, 45), "center")
            bar = pygame.Rect(16, 73, rest.w - 32, 7)         # drains as the fire closes in
            pygame.draw.rect(panel, (24, 26, 32, 255), bar, border_radius=4)
            fill = pygame.Rect(bar.x, bar.y, max(bar.h, round(bar.w * max(0.0, min(1.0, left / total)))),
                               bar.h)
            pygame.draw.rect(panel, colour, fill, border_radius=4)
        self._put(surface, panel, rest, -round((1 - intro) * (rest.h + 20)), s, kind="fire")

    # ---- mission strip -------------------------------------------------
    def _mission_strip(self, surface, rest, s, intro):
        m = self._strip_metrics(s)
        doors = s.hazards.doors
        n_out, n_lost = s.victims_out, s.victims_dead
        n_esc = sum(1 for v in s.victims if v.state == STATE_FOLLOWING)
        n_wait = sum(1 for v in s.victims if v.state == STATE_IDLE)
        pip = m["pip"]

        strip = pygame.Surface(rest.size, pygame.SRCALPHA)
        strip.blit(self._panel(rest.size), (0, 0))
        cy = rest.h // 2
        hot = []                                              # (local rect, kind)

        def divider(x):
            pygame.draw.line(strip, (255, 255, 255, 40), (x, 9), (x, rest.h - 10))

        x = 14
        shadowed_text(strip, self.f_body, m["label"], GOLD, (x, cy), "midleft")
        x += m["w_label"] + 9
        divider(x)
        x += 9

        occ_x = x
        i = 0
        for kind, count in (("out", n_out), ("esc", n_esc), ("wait", n_wait), ("lost", n_lost)):
            for _ in range(count):
                px = x + i * pip + pip // 2
                size = round(pip * 0.9)
                if kind == "out":
                    bump = (1.0 + 0.25 * math.sin(math.pi * (1 - self._out_pop / POP))
                            if self._out_pop > 0 and i == n_out - 1 else 1.0)
                    person(strip, px, cy + 4, round(size * bump), GOLD)
                elif kind == "esc":
                    person(strip, px, cy + 4, size, (110, 170, 240))
                elif kind == "wait":
                    person(strip, px, cy + 4, size, (58, 62, 74), (120, 124, 138))
                else:
                    person(strip, px, cy + 4, size, (70, 40, 40), (200, 70, 60))
                    cross(strip, px, cy + 1, 6, (230, 80, 70))
                i += 1
        x += m["w_pips"] + 8
        count = self.f_head.render(m["count"], True, TEXT)
        strip.blit(count, count.get_rect(midleft=(x, cy)))
        x += count.get_width() + 6
        hot.append((pygame.Rect(occ_x, 0, x - occ_x, rest.h), "occupants"))
        divider(x)
        x += 9

        if doors.enabled:
            key_x = x
            if doors.key_collected:                            # unlocked: a green key
                key_icon(strip, x + 26, cy, 30, GREEN)
            else:                                              # locked: padlock, key still to find
                padlock(strip, x + 12, cy, 30, (240, 96, 70))
                key_icon(strip, x + 46, cy, 24, DIM)
            x += 62
            hot.append((pygame.Rect(key_x, 0, 62, rest.h), "key"))
            divider(x - 4)
            x += 5
        clock_icon(strip, x + 9, cy, 22, DIM)
        shadowed_text(strip, self.f_body, m["clock"], TEXT, (x + 24, cy), "midleft")

        dy = round((1 - intro) * (rest.h + 20))
        self._put(surface, strip, rest, dy, s)
        for r, kind in hot:
            self.hot.append((r.move(rest.x, rest.y + dy), kind))

    # ---- damage vignette -------------------------------------------------
    def _get_vignette(self):
        if self._vignette is None:
            # built small and scaled up, which gives a smooth falloff for free
            w, h = SCREEN_WIDTH // 8, SCREEN_HEIGHT // 8
            small = pygame.Surface((w, h), pygame.SRCALPHA)
            for i in range(0, 18):
                a = round(200 * (1 - i / 18) ** 2)
                pygame.draw.rect(small, (210, 20, 10, a), small.get_rect().inflate(-2 * i, -2 * i), 2)
            self._vignette = pygame.transform.smoothscale(small, (SCREEN_WIDTH, SCREEN_HEIGHT))
        return self._vignette

    def vignette_strength(self, s):
        """0..1: a red edge flash right after Pete is hurt, and a heartbeat
        pulse while he is nearly dead. Only for a human run."""
        r = self._r["you"]
        if s.spectate or r["h"] is None or s.player.is_dead:
            return 0.0
        strength = 0.70 * r["hit"] / HIT
        if r["h"] / HEALTH_MAX < 0.25:
            strength = max(strength, 0.25 + 0.30 * max(0.0, math.sin(self.t * 8.0)) ** 2)
        return min(1.0, strength)

    def _draw_vignette(self, surface, s):
        strength = self.vignette_strength(s)
        if strength > 0.02:
            img = self._get_vignette()
            img.set_alpha(min(255, round(255 * strength)))
            surface.blit(img, (0, 0))

    # ---- toasts ----------------------------------------------------------------
    def _draw_toasts(self, surface):
        y = MARGIN + CLOCK_H + 10
        pills = [t for t in self.toasts if not t.big][-MAX_TOASTS:]
        for t in reversed(pills):                             # newest nearest the clock
            a = t.alpha
            img = self.f_body.render(t.text, True, TEXT)
            w, h = img.get_width() + 44, 32
            pill = pygame.Surface((w, h), pygame.SRCALPHA)
            pill.blit(self._panel((w, h), None), (0, 0))
            pygame.draw.rect(pill, (*t.colour, 255), pygame.Rect(0, 0, 6, h), border_top_left_radius=12,
                             border_bottom_left_radius=12)
            pill.blit(img, img.get_rect(midleft=(20, h // 2)))
            pill.set_alpha(round(255 * a))
            surface.blit(pill, ((SCREEN_WIDTH - w) // 2, y - round(10 * (1 - min(1.0, t.age / 0.2)))))
            y += h + 6
        for t in self.toasts:
            if t.big:
                self._draw_banner(surface, t)

    def _draw_banner(self, surface, t):
        title = self.f_title.render(t.text, True, t.colour)
        sub = self.f_body.render(t.sub, True, TEXT) if t.sub else None
        keys_w = hint_row_width(t.hints, self.f_chip, self.f_small) if t.hints else 0
        w = max(title.get_width(), sub.get_width() if sub else 0, keys_w) + 64
        h = title.get_height() + (sub.get_height() + 6 if sub else 0) + 28 + (38 if t.hints else 0)
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.blit(self._panel((w, h), t.colour), (0, 0))
        panel.blit(title, title.get_rect(midtop=(w // 2, 12)))
        if sub:
            panel.blit(sub, sub.get_rect(midtop=(w // 2, 12 + title.get_height() + 6)))
        if t.hints:
            key_hint_row(panel, t.hints, self.f_chip, self.f_small, w // 2, h - 12 - 15)
        panel.set_alpha(round(255 * t.alpha))
        surface.blit(panel, ((SCREEN_WIDTH - w) // 2, SCREEN_HEIGHT // 3 - h // 2))

    # ---- hover tooltips ----------------------------------------------------------
    def hovered(self, mouse):
        """The kind of HUD element under the mouse, or None."""
        if mouse is None:
            return None
        for rect, kind in self.hot:
            if rect.collidepoint(mouse):
                return kind
        return None

    def tooltip_rows(self, kind, s):
        if kind in ("you", "ai"):
            you = kind == "you"
            stats = s.player_stats if you else s.agent_stats
            health = s.player.health if you else s.agent.health
            rows = [Row(stats.display_name.upper(), GOLD if you else BLUE, head=True),
                    Row("Controlled by", DIM, stats.role),
                    Row("Health", DIM, f"{max(0, round(health))} / {HEALTH_MAX}",
                        health_colour(health / HEALTH_MAX))]
            for label, pts in stats.score_breakdown():
                rows.append(Row(label, DIM, f"{pts:+d}", POS if pts > 0 else NEG if pts < 0 else DIM))
            rows.append(Row("Total (min 0)" if stats.score_floored else "Total", TEXT,
                            str(stats.score), TEXT, rule=True))
            return rows
        if kind == "fire":
            if s.hazards.fire.exit_on_fire:
                return [Row("EXIT ON FIRE", FIRE_HOT, head=True),
                        Row("The exit tile is burning — crossing it costs health."),
                        Row("Get out before the rest of the floor goes.")]
            return [Row("FIRE", FIRE_WARN, head=True),
                    Row("Estimated time until the flames reach the exit."),
                    Row("It is only an estimate: the fire keeps spreading."),
                    Row("Standing in fire drains health fast.")]
        if kind == "occupants":
            legend = (("Out", "led to the exit", GOLD, None),
                      ("Escorted", "following a rescuer", (110, 170, 240), None),
                      ("Waiting", "not found yet", (58, 62, 74), (120, 124, 138)),
                      ("Lost", "died with their rescuer", (70, 40, 40), (200, 70, 60)))
            rows = [Row("OCCUPANTS", GOLD, head=True)]
            rows += [Row(f"{name}  —  {what}", DIM, marker=("person", fill, edge))
                     for name, what, fill, edge in legend]
            return rows
        if kind == "key":
            if s.hazards.doors.key_collected:
                return [Row("KEY", GREEN, head=True), Row("Collected — the locked door is open.")]
            return [Row("LOCKED DOOR", (240, 96, 70), head=True),
                    Row("A door blocks the way. Find the key to open it,"),
                    Row("for both rescuers.")]
        return []

    def _draw_hover(self, surface, s, mouse):
        """Highlight the hovered panel and draw its tooltip beside the mouse.
        Returns the tooltip's rect, or None if nothing is hovered."""
        kind = self.hovered(mouse)
        if kind is None:
            return None
        rect = next(r for r, k in self.hot if k == kind and r.collidepoint(mouse))
        hl = pygame.Surface(rect.size, pygame.SRCALPHA)       # a soft highlight: "this is live"
        pygame.draw.rect(hl, (255, 255, 255, 70), hl.get_rect(), 2, border_radius=12)
        surface.blit(hl, rect.topleft)

        rows = self.tooltip_rows(kind, s)
        if not rows:
            return None
        widths = []
        for r in rows:
            f = self.f_body if r.head else self.f_small
            widths.append(f.size(r.text)[0] + (22 if r.marker else 0)
                          + (24 + self.f_small.size(r.value)[0] if r.value else 0))
        w = max(widths) + 28
        line = 22
        h = 16 + sum(line + (8 if r.head else 0) + (6 if r.rule else 0) for r in rows)
        tip = pygame.Surface((w, h), pygame.SRCALPHA)
        tip.blit(self._panel((w, h), None), (0, 0))
        y = 10
        for r in rows:
            if r.rule:
                pygame.draw.line(tip, (255, 255, 255, 50), (12, y + 2), (w - 12, y + 2))
                y += 6
            x = 14
            if r.marker:
                person(tip, x + 7, y + line // 2 + 4, 16, r.marker[1], r.marker[2])
                x += 22
            f = self.f_body if r.head else self.f_small
            tip.blit(f.render(r.text, True, r.colour), (x, y + (0 if r.head else 2)))
            if r.value:
                v = self.f_small.render(r.value, True, r.vcolour)
                tip.blit(v, (w - 14 - v.get_width(), y + 2))
            y += line + (8 if r.head else 0)
        # Beside the element, never over it: a bottom-edge element (the mission
        # strip) gets its tooltip above; a top-edge one (a card, the clock)
        # gets it below, so the card's own score is not hidden by its tooltip.
        top = rect.top - h - 8 if mouse[1] > SCREEN_HEIGHT // 2 else rect.bottom + 8
        pos = pygame.Rect(mouse[0] + 16, top, w, h).clamp(surface.get_rect().inflate(-8, -8))
        surface.blit(tip, pos.topleft)
        return pos                                            # where it went (tests check it is on screen)
