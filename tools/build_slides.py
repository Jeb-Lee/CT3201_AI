"""CT3201 starter slide deck (9 sections) from the report draft.
python-pptx. Layout is plain on purpose -- the team adds visuals/screenshots.
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

_OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "docs", "report", "CT3201_Slides.pptx")

ACCENT = RGBColor(0x1F, 0x4E, 0x79)
DARK = RGBColor(0x22, 0x22, 0x22)
GREY = RGBColor(0x66, 0x66, 0x66)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def slide(title, subtitle=None):
    s = prs.slides.add_slide(BLANK)
    tb = s.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12.1), Inches(0.9))
    p = tb.text_frame.paragraphs[0]
    r = p.add_run(); r.text = title
    r.font.size = Pt(30); r.font.bold = True; r.font.color.rgb = ACCENT
    if subtitle:
        p2 = tb.text_frame.add_paragraph()
        r2 = p2.add_run(); r2.text = subtitle
        r2.font.size = Pt(13); r2.font.color.rgb = GREY
    return s


def bullets(s, items, top=1.5, size=16, left=0.7, width=12.0):
    box = s.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(5.5))
    tf = box.text_frame; tf.word_wrap = True
    for i, it in enumerate(items):
        lvl = 0
        while it.startswith("  "):
            it = it[2:]; lvl += 1
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.level = lvl
        r = p.add_run(); r.text = ("• " if lvl == 0 else "– ") + it
        r.font.size = Pt(size - lvl * 2); r.font.color.rgb = DARK
        p.space_after = Pt(6)


def table(s, rows, top=1.5, left=0.6, width=12.1, size=11):
    nr, nc = len(rows), max(len(r) for r in rows)
    gt = s.shapes.add_table(nr, nc, Inches(left), Inches(top),
                            Inches(width), Inches(0.4 * nr)).table
    for ci in range(nc):
        gt.columns[ci].width = Inches(width / nc)
    for ri, row in enumerate(rows):
        for ci in range(nc):
            cell = gt.cell(ri, ci)
            cell.text = row[ci] if ci < len(row) else ""
            for pr in cell.text_frame.paragraphs:
                for rn in pr.runs:
                    rn.font.size = Pt(size)
                    if ri == 0:
                        rn.font.bold = True; rn.font.color.rgb = RGBColor(255, 255, 255)
            if ri == 0:
                cell.fill.solid(); cell.fill.fore_color.rgb = ACCENT
    return gt


# ---- Title ----
s = slide("Pyro Pete: Emergency Evacuation",
          "CT3201 Mini Project  ·  an evacuation-routing AI agent  ·  Learn with AI")
bullets(s, ["Team: [names]",
            "Problem area: search / intelligent agent / decision-making under uncertainty",
            "Can AI help us design AI - and can we recognise when AI is wrong?"], top=3.2, size=18)

# ---- 1 Problem Definition ----
s = slide("1 - Problem Definition", "Phase 1, Stage 1 - defined human-first, before using AI")
bullets(s, [
    "Problem: occupants who don't know a burning building's layout must be found and led to an exit before fire, smoke and collapse cut the route off",
    "User: [fire-service route planners / a rescuer-training simulator / a decision-support tool for a rescuer in the field]",
    "Environment: multi-room floor plan as a grid graph; hazards evolve over time; only a small radius is visible",
    "Desired outcome: all reachable occupants out, then the rescuer out - fast, with minimal hazard exposure",
    "Main decision: push deeper for another occupant, or take the ones I have and get out now?",
    "[TEAM] confirm this matches your Stage-1 notes made before any AI use",
])

# ---- 2 Initial Human Solution ----
s = slide("2 - Initial Human Solution", "Phase 1, Stage 2 - the AI formulation")
table(s, [
    ["Element", "Our project"],
    ["Agent", "one autonomous rescue unit (drone in-game; human plays the same role)"],
    ["State", "current cell · occupant statuses · map seen so far · health"],
    ["Actions", "move to one of the 4 adjacent floor cells"],
    ["Goal", "lead every reachable occupant to the exit, then exit"],
    ["Cost", "1 / step + hazard surcharge (fire +8, smoke +2xdensity, panel +7.5, pending collapse +25)"],
    ["Constraints", "walls & debris impassable; door impassable until key; health drains in hazards, 0 = run over"],
    ["Information", "PARTIAL - only cells/occupants within a vision radius; re-plan when reality differs"],
], size=11)
bullets(s, ["Initial plan (pre-AI): BFS to the nearest occupant, escort out, repeat; treat fire as a wall"],
        top=5.7, size=13)

# ---- 3 AI-Assisted Exploration ----
s = slide("3 - AI-Assisted Exploration", "Phase 2, Stage 3 - used AI to challenge, not to design")
table(s, [
    ["We asked AI to...", "What it surfaced", "What we took from it"],
    ["challenge BFS-with-fire-as-a-wall", "BFS minimises tiles, not danger - it walks through fire to save a step", "treat hazards as weighted costs; use cost-aware search"],
    ["suggest alternative search strategies", "Dijkstra / A* / Greedy and their trade-offs", "implement all four to compare on our own map"],
    ["point out assumptions", "we assumed a full map of occupant locations", "add partial observability + frontier exploration"],
    ["what could make it fail?", "locked door on the only corridor; a collapse could trap someone", "key sub-goal; connectivity-checked collapse"],
], size=11)

# ---- 4 AI Critique & Decisions ----
s = slide("4 - AI Critique and Student Decisions", "Phase 3 & 4 - Accept / Modify / Reject, each verified")
table(s, [
    ["AI suggestion", "Decision", "Why / how verified"],
    ["Use Greedy Best-First (fewer expansions)", "Reject", "not cost-optimal on a weighted map; comparison harness shows BFS routes through 9 fire tiles"],
    ["Use A* over the hazard cost", "Accept", "ties Dijkstra for optimality, far fewer expansions; search theory + harness"],
    ["Keep BFS for unweighted jobs", "Accept", "fire-ring counting & connectivity have no weights; unit tests"],
    ["Generate NPC walk as AI video", "Reject", "video model only did side-view, unstable; checked vs engine needs (see ai_critique.md)"],
    ["Perfect (single-path) maze", "Modify", "every search returns the same route -> braided the maze so routing has choices"],
    ["Give the agent a full occupant map", "Reject", "contradicts 'you don't know the building'; unbalances the human-vs-AI race"],
], size=10)

# ---- 5 Final AI Solution ----
s = slide("5 - Final AI Solution", "playable game + autonomous rescue drone")
bullets(s, [
    "Decision loop:  sense (vision radius)  ->  choose goal  ->  hazard-weighted A* plan  ->  step  ->  re-plan every 0.25 s",
    "Goal selection: nearest KNOWN occupant by weighted distance; else nearest unexplored area; else the exit; key first if a door blocks the goal",
    "Techniques (from the brief's list): Search (BFS/Dijkstra/A*/Greedy) · Intelligent agent · Decision-making under uncertainty",
    "Systems: spreading fire + functional smoke · sparking panels · timed ceiling collapse · locked door + key · fog of war with memory",
    "Score: +100 per occupant led out · +50 for exiting · speed bonus · damage penalty",
    "[SLIDE: paste the decision-loop flowchart + 2-3 gameplay screenshots here]",
])

# ---- 6 Evaluation ----
s = slide("6 - Evaluation and Testing", "Phase 6, Stage 7 - testing an AI recommendation with evidence")
bullets(s, ["AI recommendation tested: \"Use Greedy Best-First - fewer node expansions, so it's faster.\""], top=1.4, size=15)
table(s, [
    ["strategy", "path cost", "steps", "hazard tiles crossed"],
    ["BFS (unweighted)", "101.8", "30", "9"],
    ["Dijkstra", "43.8", "42", "2"],
    ["A*", "43.8", "42", "2"],
    ["Greedy best-first", "43.8", "42", "2  (only when the straight line is safe)"],
], top=2.3, size=12)
bullets(s, [
    "Appropriate? NO - 'fewer expansions' optimises the wrong thing. BFS/Greedy minimise tiles, not danger.",
    "Evidence: BFS route = 2.3x the cost through 9 burning tiles. A* = Dijkstra cost, fewer expansions -> optimal AND fast.",
    "Decision: A* for routing; Greedy & BFS rejected; BFS kept only for unweighted jobs.  Plus 12 unit tests.",
], top=4.5, size=13)

# ---- 7 Responsible AI ----
s = slide("7 - Responsible AI", "Phase 7, Stage 8 - should this system be deployed?")
table(s, [
    ["Dimension", "Assessment"],
    ["Fairness", "in-game the drone takes hazard damage & has the same vision as the human - fair by construction"],
    ["Bias", "goal selection is greedy nearest-first: no triage, no notion of who is most at risk"],
    ["Transparency", "the agent DRAWS its planned route + walked trail - you can see what it decided and why it changed"],
    ["Privacy", "a real occupant-locator needs live location data on people - sensitive, must be minimised"],
    ["Security", "the agent trusts its hazard map; a spoofed feed could steer it (and followers) into a hazard"],
    ["Accountability", "if it leads someone into a collapse - operator? developer? sensor vendor? needs an audit log"],
    ["Human oversight", "it's decision-support, not an autonomous replacement for firefighters - the right posture"],
], size=10)
bullets(s, ["Should it deploy? [TEAM] - defensible: not as an autonomous router; yes as a transparent aid a trained rescuer can override, if the sensor feed's integrity is assured and triage replaces greedy nearest-first"],
        top=6.4, size=11)

# ---- 8 Human-AI Reflection ----
s = slide("8 - Human-AI Reflection", "Phase 8, Stage 9 - MANDATORY - rewrite in your own words")
bullets(s, [
    "AI helped: explained tiles-vs-cost, listed search options, caught bad assumptions, sped up implementation",
    "AI got wrong: video model couldn't do walk-to-camera NPC animation; recommended Greedy without weighting 'safe' vs 'fast'",
    "Accepted: weighted costs, A*, partial observability, key sub-goal, connectivity-checked collapse, braided maze",
    "Rejected: Greedy & BFS for routing, full occupant map, AI-video for toward/away directions",
    "Verified via: search theory, a purpose-built comparison harness, 12 unit tests, checking assets vs engine requirements",
    "Human judgement was necessary for: scope decisions, tuning, recognising the AI failure was narrow, the Responsible-AI position",
    "If we'd blindly followed AI: the agent would lead people through the fire and we'd have debugged 'bad game balance' instead of a wrong algorithm",
    "[TEAM] full 11-question answers in the report - REWRITE these in your own words",
], size=13)

# ---- 9 Conclusion ----
s = slide("9 - Conclusion")
bullets(s, [
    "Designed the agent human-first, then used AI to challenge and broaden it",
    "AI moved us from unweighted BFS to a hazard-weighted A* agent that plans under partial information and re-plans as the building changes",
    "Tested an AI recommendation (Greedy) against a purpose-built comparison - found it inappropriate, rejected it with evidence",
    "The AI's clearest failure (directional NPC animation) was identified, verified against requirements, and routed around",
    "AI widened the option space and sped the work; the objective, the verification and every final decision were ours",
], top=1.8, size=17)

prs.save(_OUT)
print("wrote", _OUT, "-", len(prs.slides._sldIdLst), "slides")
