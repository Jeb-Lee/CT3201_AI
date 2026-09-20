"""One definition of how an AI-only episode ended, shared by the training
environment and the evaluation harness so they can never disagree.

    evacuated   the AI survived and everyone still alive got out
    died        the AI burned
    gave_up     the stage ended with the AI alive but people still inside
                (it stopped, or stood still too long)
    timeout     the time cap hit while the stage was still running
"""

OUTCOMES = ("evacuated", "died", "gave_up", "timeout")


def classify(session):
    if session.state == "playing":
        return "timeout"
    if session.agent.is_dead:
        return "died"
    if session.evacuated:
        return "evacuated"
    return "gave_up"


def summarise(session):
    """A flat dict of everything worth recording about a finished (or
    capped) AI-only episode."""
    stats = session.agent_stats
    return {
        "outcome": classify(session),
        "victims_out": session.victims_out,
        "victims_total": len(session.victims),
        "victims_lost": session.victims_dead,
        "score": stats.score,
        "damage": round(stats.damage_taken, 1),
        "seconds": round(stats.elapsed, 1),
    }
