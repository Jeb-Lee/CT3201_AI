"""Machine-learning support for the AI rescuer.

Everything here is opt-in and separate from the A* agent in
entities/rescue_agent.py, which stays the default AI:

  observation.py  what a learned agent is allowed to see, as a flat vector
  policy.py       how a trained model is loaded and asked for an action
  outcome.py      one shared definition of how an episode ended
  env.py          a Gymnasium environment, for training (needs gymnasium)
  evaluation.py   the harness that compares agents fairly (see
                  tools/evaluate_agents.py for the command line)

Only the AI player can use a learned policy -- Pete is always human.
"""
