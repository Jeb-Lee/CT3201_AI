"""Per-rescuer run metrics, so the end screen can show a real
human-vs-AI comparison instead of just a saved count.

One RunStats per rescuer (Pete, the agent). main.py feeds it events; the
results screen reads it back. Deliberately plain -- this is the raw
material for the project's "human vs AI" reflection, so it tracks the
things that make that comparison meaningful: how long, how far, how much
damage taken, and (agent only) how much re-planning the changing map
forced.
"""

class RunStats:
    def __init__(self, label):
        self.label = label
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
    def summary_rows(self):
        """(label, value-string) pairs for the results panel."""
        rows = [
            ("Victims saved", str(self.victims_saved)),
            ("Time", f"{self.elapsed:5.1f}s"),
            ("Distance", f"{self.distance / 64:5.1f} tiles"),
            ("Damage taken", f"{self.damage_taken:5.0f}"),
        ]
        if self.replans or self.goal_changes:
            rows.append(("Route updates", str(self.replans)))
            rows.append(("Goal switches", str(self.goal_changes)))
        if self.deaths:
            rows.append(("Died", "yes"))
        return rows
