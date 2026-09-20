"""The AI rescuer driven by a learned policy instead of A*.

An opt-in alternative to entities/rescue_agent.RescueAgent, chosen per run
(GameSession(agent_brain="learned")). It shares that class's *body* --
health, hazard damage, smoke slowdown, vision, walking between tiles,
drawing -- so the two brains face identical rules and look identical, and
overrides only the *decision*: instead of choosing a goal and running A*,
it asks a policy which way to step.

Each decision is one grid step (see ml/observation.py): stay, or walk to
the adjacent tile. It never calls the pathfinder to plan, so the only
route-finding it has is whatever the policy has learned.

Two ways to supply decisions:
  * a `policy` object with .act(observation, action_mask) -> int, asked
    whenever the agent is idle (this is what the game uses); or
  * command(action), for a training environment that is stepping it from
    outside (ml/env.py).

Giving up: a policy that just stands still would leave a stage running
forever, so an agent that has not moved for IDLE_GIVE_UP_SECONDS declares
itself finished, exactly as the A* agent does when it judges the search
not worth the risk. The stage then ends as a loss for it.
"""

from entities.rescue_agent import RescueAgent
from ml.observation import (
    MOVES, ACTION_STAY, N_ACTIONS, action_mask, build_observation,
)

# How long a "stay" decision lasts before the policy is asked again.
STAY_SECONDS = 0.25
# Standing still for this long without a single successful step = gave up.
IDLE_GIVE_UP_SECONDS = 12.0


class LearnedAgent(RescueAgent):
    def __init__(self, tilemap, start_cell, hazard_field=None, stats=None,
                 visual=None, speed_scale=1.0, policy=None):
        super().__init__(tilemap, start_cell, hazard_field=hazard_field,
                         stats=stats, visual=visual, speed_scale=speed_scale)
        self.policy = policy
        self.last_action = ACTION_STAY
        self._pending_action = None
        self._next_decision_at = 0.0
        self._last_move_at = 0.0
        # the tiles it has stood on, in order (memory for observation version 3);
        # the agent's own past, which A* also carries in its goal and planned route
        self.cell_history = [start_cell]
        self.visit_counts = {start_cell: 1}     # times it has entered each tile (observation version 4)

    def _remember_cell(self):
        """Note the tile it is standing on (at each decision, every tile it enters is one)."""
        if self.current_cell != self.cell_history[-1]:
            self.visit_counts[self.current_cell] = self.visit_counts.get(self.current_cell, 0) + 1
            self.cell_history.append(self.current_cell)
            if len(self.cell_history) > 64:
                del self.cell_history[:-64]

    # ------------------------------------------------------------ control
    def command(self, action):
        """Queue an action from outside (a training environment). It is
        taken the next time the agent is idle, ahead of any policy."""
        self._pending_action = int(action)

    # ----------------------------------------------- overridden decisions
    def _replan(self, victims):
        """The A* agent plans a route here. This asks for one step."""
        self._remember_cell()
        if self._waypoints:
            return   # mid-step: finish walking to the next tile first

        if self._anim_t - self._last_move_at >= IDLE_GIVE_UP_SECONDS:
            self._finished = True
            return

        action = self._next_action(victims)
        if action is None:
            return
        self._apply(action)

    def _search_over(self, victims):
        """A learned agent has no notion of an exhausted search -- it is
        finished at the exit once nobody is left to find, and otherwise it
        keeps going until it gives up or dies."""
        return self._all_occupants_accounted(victims)

    # ----------------------------------------------------------- internals
    def _next_action(self, victims):
        if self._pending_action is not None:
            action, self._pending_action = self._pending_action, None
            return action
        if self.policy is None or self._anim_t < self._next_decision_at:
            return None
        version = getattr(self.policy, "obs_version", 1)
        return self.policy.act(build_observation(self, victims, version), action_mask(self))

    def _apply(self, action):
        self.last_action = action
        cc, cr = self.current_cell
        if action in MOVES and 0 <= action < N_ACTIONS:
            dc, dr = MOVES[action]
            target = (cc + dc, cr + dr)
            if self.tilemap.is_walkable(*target):
                self._waypoints = [self.tilemap.cell_center(*target)]
                self.planned_route = [self.current_cell, target]
                self._last_move_at = self._anim_t
                return
        # stay, or a step into a wall: a wasted decision
        self._waypoints = []
        self.planned_route = [self.current_cell]
        self._next_decision_at = self._anim_t + STAY_SECONDS
