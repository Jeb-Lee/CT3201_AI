"""Per-rescuer run metrics, so the end screen can show a real
human-vs-AI comparison instead of just a saved count.

One RunStats per rescuer (Pete, the agent). main.py feeds it events; the
results screen reads it back. Deliberately plain -- this is the raw
material for the project's "human vs AI" reflection, so it tracks the
things that make that comparison meaningful: how long, how far, how much
damage taken, and (agent only) how much re-planning the changing map
forced.
"""

from settings import (
    SCORE_PER_SURVIVOR, SCORE_REACH_EXIT, SCORE_TIME_BONUS_PAR,
    SCORE_TIME_BONUS_MAX, SCORE_DAMAGE_PENALTY,
)


_KINDS = {"you": "Pete", "robot": "AI Robot", "drone": "AI Drone"}     # kind -> name shown
_ROLES = {"human": "Human player", "astar": "A* planner", "learned": "Learned model"}


def _kind_from_label(label):
    l = label.lower()
    return "you" if l.startswith("you") else "drone" if "drone" in l else "robot"


class RunStats:
    def __init__(self, label, kind=None, brain=None):
        """`label` is the running text ("You (Pete)", "AI robot (learned)").
        `kind` ("you", "robot" or "drone") and `brain` ("human", "astar" or
        "learned") say who this is; when omitted they are read off the label,
        so older callers keep working."""
        self.label = label
        self.kind = kind or _kind_from_label(label)
        self.brain = brain or ("human" if self.kind == "you"
                               else "learned" if "(learned)" in label else "astar")
        if self.kind not in _KINDS or self.brain not in _ROLES:
            raise ValueError(f"unknown rescuer kind/brain: {self.kind!r}/{self.brain!r}")
        self.elapsed = 0.0           # seconds of *game* time (accumulated dt)
        self._running = True

        self.victims_saved = 0
        self.distance = 0.0          # world pixels travelled
        self.damage_taken = 0.0      # cumulative health lost
        self.deaths = 0

        # agent-only; stays 0 for the human
        self.replans = 0
        self.goal_changes = 0

        self.finished_reason = None  # "exit" | "dead" | None (still going)

    @property
    def display_name(self):
        """The name for a heading: "Pete", "AI Robot" or "AI Drone"."""
        return _KINDS[self.kind]

    @property
    def role(self):
        """How it decides: "Human player", "A* planner" or "Learned model"."""
        return _ROLES[self.brain]

    # -- events ---------------------------------------------------------
    def tick(self, dt):
        if self._running:
            self.elapsed += dt

    def add_distance(self, d):
        self.distance += d

    def add_damage(self, amount):
        self.damage_taken += amount

    def mark_death(self):
        self.deaths += 1
        self.finish("dead")

    def mark_replan(self):
        self.replans += 1

    def mark_goal_change(self):
        self.goal_changes += 1

    def set_saved(self, n):
        self.victims_saved = n

    def finish(self, reason):
        if self._running:
            self._running = False
            self.finished_reason = reason

    # -- readback -----------------------------------------------------
    @property
    def time_bonus(self):
        if self.finished_reason != "exit" or self.elapsed >= SCORE_TIME_BONUS_PAR:
            return 0
        return round(SCORE_TIME_BONUS_MAX * (1 - self.elapsed / SCORE_TIME_BONUS_PAR))

    @property
    def _raw_score(self):
        s = self.victims_saved * SCORE_PER_SURVIVOR
        if self.finished_reason == "exit":
            s += SCORE_REACH_EXIT + self.time_bonus
        s -= round(self.damage_taken * SCORE_DAMAGE_PENALTY)
        return s

    @property
    def score(self):
        """Occupants led out are the objective (bulk of the score); getting
        yourself out is a bonus; speed adds, damage subtracts. Never < 0."""
        return max(0, self._raw_score)

    @property
    def score_floored(self):
        """True when damage pushed the score below zero and it was held at 0,
        i.e. the breakdown rows sum to less than the total shown."""
        return self._raw_score < 0

    def score_breakdown(self):
        """(label, points) rows explaining the score on the results panel."""
        rows = [(f"Occupants led out  x{self.victims_saved}",
                 self.victims_saved * SCORE_PER_SURVIVOR)]
        if self.finished_reason == "exit":
            rows.append(("Reached the exit", SCORE_REACH_EXIT))
            if self.time_bonus:
                rows.append(("Speed bonus", self.time_bonus))
        dmg = round(self.damage_taken * SCORE_DAMAGE_PENALTY)
        if dmg:
            rows.append(("Damage taken", -dmg))
        return rows

    def summary_rows(self):
        """(label, value-string) pairs for the results panel."""
        # No space-padding to line the numbers up: the game font is
        # proportional, so padding never aligned. results.py right-aligns
        # the values instead. "Health lost" (raw health) is named apart from
        # the "Damage taken" points penalty in score_breakdown.
        rows = [
            ("Time", f"{self.elapsed:.1f}s"),
            ("Distance", f"{self.distance / 64:.1f} tiles"),
            ("Health lost", f"{self.damage_taken:.0f}"),
        ]
        if self.replans or self.goal_changes:
            rows.append(("Route updates", str(self.replans)))
            rows.append(("Goal switches", str(self.goal_changes)))
        # Pete's death arrives via finish("dead") without touching `deaths`
        # (only RescueAgent calls mark_death), so keying on the counter alone
        # gave the AI a "Died" row and left Pete's column without one.
        if self.deaths or self.finished_reason == "dead":
            rows.append(("Died", "yes"))
        return rows
