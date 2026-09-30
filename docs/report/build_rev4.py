"""Assemble REPORT_rev4.md (the source of report revision 4).

Revision 4 is revision 3 with the team's own details filled in, from an interview with the team
(29 Sep 2026):

  * the [TEAM] markers: the user, the "think first" note, the first plan before AI, and the
    deployment position; the placeholder row in the Section 4 table is removed;
  * fire is described as the team intended it from the start, a hazard that drains health.
    "Fire treated as a wall" described only the first prototype, and the AI's contribution was
    weighted search, not the fire mechanic (the abstract is changed the same way, in the generator);
  * Section 6 cites the 150-situation Greedy test (tools/greedy_vs_astar_scan.py).

The author block (team name, names, matric numbers) is in tools/md_to_ieee_docx.py (AUTHORS_REV4).
The reflection answers in Section 9 are NOT rewritten here: the brief requires them in the team's
own words.

Then build the Word file:  python tools/md_to_ieee_docx.py --rev4

    python docs/report/build_rev4.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_rev2 import assemble, replace_once          # noqa: E402
from build_rev3 import rev3_edits                     # noqa: E402

H = "‑"            # REPORT.md uses non-breaking hyphens


def replace_paragraph(text, starts_with, new):
    """Replace the whole paragraph that begins with `starts_with` (up to the next blank line)."""
    i = text.index(starts_with)
    j = text.index("\n\n", i)
    return text[:i] + new + text[j:]


USER = ("**User.** We first defined the users as building occupants, and secondarily safety officers "
        "or an automated guidance system. To make the problem visual we reframed it as a rescuer who "
        "searches for occupants and leads them out: a simulation in which students and players can "
        "watch, and race, an AI that makes these decisions.")

THINK_FIRST = ("**\"Think first\" note.** Over two days we pooled candidate problems in a shared "
               "spreadsheet, each written in the brief's Stage 1 format (problem, user, environment, "
               "desired outcome, main decision). Ideas came from daily life and some entries' wording "
               "from Gemini and Claude. The choice was ours: we voted for Emergency Evacuation "
               "Routing, the course's own exercise, because it let us show the search algorithms "
               "from class working visually, as a game, inspired by videos of AI learning to play "
               "Mario and Pokémon.")

FIRST_PLAN = ("**Initial plan (pre" + H + "AI).** The rescuer searches the building; occupants who "
              "come within two squares see him and follow. Breadth" + H + "first search finds the way. "
              "Fire was always meant to be a hazard that drains health rather than a wall, so pushing "
              "through it is a gamble between speed and survival, especially on later stages.")

DEPLOY = ("**Should it be deployed?** As a real rescue system, no: it was never meant to replace people, "
          "and the concerns above (triage bias, trust in the hazard sensors, accountability) would all "
          "need answering first. As what it is, an interactive showcase that makes the search "
          "algorithms we learnt in class visible, yes: anyone who plays can see that the rescuer "
          "racing them runs on A\\*, and read the lecture notes to learn more. There is little risk "
          "here: no real building and no personal data.")

GREEDY_EVIDENCE = ("The cost table above, and the same comparison repeated across every stage, three "
                   "debris layouts and five fire" + H + "spread times (150 situations, "
                   "`tools/greedy_vs_astar_scan.py`): Greedy's route cost more than A\\*'s in **98**, "
                   "tied in 52, and was never cheaper. On stage 2 after 20 s of fire, A\\* reaches the "
                   "exit through no hazard tiles (cost 32) while Greedy crosses 16 (cost 195). Plus:")


def rev4_edits(text):
    text = rev3_edits(text)
    # the drafting note at the top ("[TEAM] marks a spot where you must...") is done with
    text = replace_paragraph(text, "> **How to use this file.**", "")
    text = replace_paragraph(text, "**User.** `[TEAM", USER)
    text = replace_paragraph(text, "**\"Think first\" note.** `[TEAM]`", THINK_FIRST)
    text = replace_paragraph(text, "**Initial plan (pre" + H + "AI).** `[TEAM: confirm]`", FIRST_PLAN)
    text = replace_paragraph(text, "**Should it be deployed?** `[TEAM", DEPLOY)
    # Section 3 table: the plan AI challenged was BFS itself
    text = replace_once(text, "| challenge our BFS" + H + "with" + H + "fire" + H + "as" + H + "a" + H + "wall plan |",
                        "| challenge our BFS plan |")
    # Section 4 table: drop the placeholder row
    i = text.index("| `[TEAM]` add any other decisions")
    j = text.index("\n", i)
    text = text[:i].rstrip("\n") + text[j:]
    # Section 6: the 150-situation evidence
    text = replace_once(text, "The cost table above (and\nre" + H + "running the harness after more fire spread, "
                        "where Greedy separates from\nA\\*), plus:", GREEDY_EVIDENCE)
    # Reflection: describe what AI actually changed (routing), not the fire mechanic
    text = replace_once(text, "redirected us from \"BFS with fire as a wall\" to weighted search.",
                        "redirected us from plain BFS to weighted search.")
    text = replace_once(text, "Weighted costs instead of\n   walls;", "Weighted hazard costs in the\n   search;")
    text = replace_once(text, "Fire: instant" + H + "kill wall → time" + H + "based health drain\n   and a routing cost.",
                        "Routing: fire, smoke and panels became costs in the search, so the\n   agent weighs a dash "
                        "through danger against a longer safe route.")
    if "[TEAM" in text:
        raise SystemExit("a [TEAM] marker is left: " + text[text.index("[TEAM") - 60:text.index("[TEAM") + 60])
    return text


def main():
    assemble("rev3_section_learning.md", "REPORT_rev4.md", extra_edits=rev4_edits)


if __name__ == "__main__":
    main()
