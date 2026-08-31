---
title: Pyro Pete — Playtest Feedback & Run-by-Run Notes
---

# Feedback for the team

Three findings from playtesting, each checked against the actual code (`pyro_pete_game/`) so they're backed by evidence, not just impressions.

## 1. Health bar should change color as health drops

**What I noticed:** The health bar stays the same solid red the entire time, from full health down to near-death — there's no visual escalation of urgency.

**Why it's worth fixing:** Checked `settings.py` — `HEALTH_BAR_FILL_COLOR = (196, 64, 56)` is a single hardcoded color, drawn the same way regardless of the health fraction (`main.py`, health bar draw call). A green → yellow/orange → red gradient as health drops is a standard, low-cost UX pattern that gives the player an at-a-glance danger cue without reading the numbers.

**Suggested fix:** Interpolate the fill color based on `health / HEALTH_MAX` instead of using a fixed color — e.g. green above ~60%, yellow/orange 30–60%, red below 30%.

## 2. Victim rescue is "first to touch it" — no take-over from the AI

**What I asked:** Can the player take over a victim the AI is already escorting, so we don't lose runs where the AI finds a victim but never makes it to the exit?

**What the code actually does:** Traced it through `main.py` and `entities/victim.py`. Both the player and the AI call the same shared function, `_try_rescue()`. It only lets a victim be claimed while its state is `IDLE`; the moment either rescuer touches an idle victim, it flips to `FOLLOWING` that specific rescuer and is skipped by everyone else after that. So no — there's currently no way to take over a victim from the AI once it's claimed one. This is confirmed design, not a bug.

**Discussion point for the team:** Worth deciding deliberately whether a take-over mechanic should be added. It would reduce "wasted" rescues (see Run 8 below, where the AI saved all 3 victims but hadn't reached the exit when I did, so those rescues didn't fully register), but it also changes what the game is testing — it stops being a clean "who's better at finding and routing to victims" comparison and starts being "can the human clean up after the AI." Recommend deciding this based on what you want Section 5/6 of the report to demonstrate.

## 3. Electrical panel's routing cost may be underweighted relative to its real danger

**What I noticed:** The AI walks through sparking panels quickly and without hesitation, while it visibly slows down and gets "caught" in fire/smoke.

**Why that's not a bug — it's the speed penalty:** Checked `hazard_field.py` — fire/smoke applies a real movement slowdown (`SMOKE_SLOW_AT_FULL = 0.45`, i.e. 45% speed in full smoke), while the panel applies **zero** speed penalty. So fire costs more (partly) because you're stuck in it longer, not just because of raw damage/sec.

**But the numbers say the panel is still underpriced.** Working through it:

- A burning tile's *real* A* cost is `FIRE_TILE_COST (8.0) + SMOKE_TILE_COST (2.0)` = **10.0** (burning tiles sit at full smoke density) vs. the panel's **6.0** → the game currently treats fire as **1.67x** costlier than a panel.
- Expected damage per crossing, factoring in the speed penalty (`DPS ÷ speed multiplier`): fire = `20 ÷ 0.45 ≈ 44.4`, panel = `34 ÷ 1.0 = 34` → fire is only about **1.31x** as dangerous to actually cross as a panel.

Since the game prices fire as 1.67x costlier but it's really only ~1.31x more dangerous, the panel is priced lower than its proportional share. Scaling the panel's cost off fire's real cost (10.0) proportionally gives `34 × (10.0 / 44.4) ≈ 7.7`.

**Suggested fix:** Raise `SPARK_PANEL_TILE_COST` from 6.0 to roughly **7.5–8.0** in `settings.py`, so the AI treats panels with routing caution closer to what their actual lethality (34 dmg/sec, ~3 seconds to kill) warrants.

## No bugs found

Deliberately tried to get cornered by spreading fire, tested the key/door mechanic, and died once mid-run (Run 6 below) — nothing crashed, froze, or behaved inconsistently. Restart (`R`) worked cleanly every time. Worth reporting as "tested, no defects found" rather than treating the absence of bugs as incomplete testing.

---

# Playtest log — what each row shows

10 runs logged in `Pyro_Pete_Playtest_Log.xlsx` (`playtesting/` folder). Here's what happened in each, in plain terms — useful for explaining the data in the report or slides.

**Run 1 — You won (1 saved vs 0).** Explored and rescued 1 victim before exiting in 17.9s. The AI was still mid-search (0 saved, 8 damage taken) when I exited, so its run got cut short before it could finish.

**Run 2 — AI won (2 saved vs 0).** I beelined straight for the exit without looking for anyone (31.7s, 0 saved). The AI, still searching when I exited, had already rescued 2. This is the clearest case of "human strategy matters more than reflexes" — rushing cost me the comparison entirely.

**Run 3 — AI won (3 saved vs 0), and the AI actually finished.** Unlike most other runs, the AI reached the exit itself this time (30.9s) with all 3 victims saved, before I even got out (36.4s). I took heavy fire damage (45) along the way, which likely slowed me down enough for the AI to fully complete its run for once.

**Run 4 — You won (1 saved vs 0).** Similar pattern to Run 1 — I found 1 victim before exiting (26.0s); AI still searching at that point.

**Run 5 — You won (2 saved vs 0), fastest run so far (16.2s).** Found 2 victims quickly with zero damage taken. AI still mid-search.

**Run 6 — You won on rescues, but this is the "danger" run.** I took 50 damage and the AI actually died (100 damage, hazard fatality) before finishing — the AI's run ended in death rather than "still searching." This is good evidence that the hazards are genuinely lethal to the AI too, not just decorative, and worth using as a demonstration clip.

**Run 7 — AI won (2 saved vs 0).** Same rush-to-exit pattern as Run 2 — I exited at 17.3s having saved nobody; AI had already saved 2.

**Run 8 — AI won (3 saved vs 0), and this is the key evidence for Feedback #2 above.** The AI had already rescued all 3 victims but had not yet reached the exit (still "searching" — really returning) when I exited at 25.4s. This is the clearest example of the "run ends the moment either side reaches the exit" quirk: the AI's full rescue effort doesn't fully register in the final stats because it never got the chance to finish its own exit run.

**Run 9 — Tie.** Neither of us saved anyone (0 victims total logged for either side), but I got out (26.2s) while the AI was still searching. The verdict line correctly reflects a tie-on-rescues with a "you got out" tiebreaker.

**Run 10 — Tie, same shape as Run 9.** 0 saved each, I exited at 28.2s, AI still searching. Two ties back-to-back suggests these particular maze layouts may have placed victims somewhere neither of us reached efficiently — could be worth a note in the report about maze-seed variance affecting outcomes.

**Overall pattern across all 10 runs:** You won 4, AI won 4, tied 2 (see Summary tab). The clearest driver of outcome isn't reflexes or speed — it's whether the human prioritizes searching for victims (Runs 1, 4, 5, 6) versus rushing the exit (Runs 2, 7, and partially 9/10). Every AI "win" happened when I rushed. That's a genuinely strong, simple finding for the reflection section: a systematic searcher (the AI) reliably beats an unguided rusher (a human optimizing for exit time alone), but a human who deliberately searches performs comparably or better.
