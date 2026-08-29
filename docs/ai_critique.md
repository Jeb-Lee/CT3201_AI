# Critical evaluation — what AI got wrong, and testing an AI suggestion

CT3201 Mini Project. Two worked examples for the mandatory
"Critical Evaluation" section:

1. **Asset generation** — the `identified -> verified -> corrected` story
   (below).
2. **Search-strategy recommendation** — testing an AI suggestion against
   evidence (`docs/search_comparison.md`, summarised at the end here).

---

## Part 1 — AI-assisted asset generation

## Context

*Pyro Pete: Emergency Evacuation* needs top-down character sprites for the
player and for the trapped-occupant ("victim") NPCs. The team has no
pixel artist, so character art was produced with generative AI against a
hand-picked style reference, then post-processed into game frames
(auto-crop to the character, align to a shared canvas, bake per-pixel
alpha — see `pyro_pete_game/tools_make_transparent.py`).

## What AI actually did well

- Generated a consistent chibi/"early-days" art direction across multiple
  characters from one reference sheet.
- Produced clean, stable **side-view (left/right) walk clips** that the
  frame-extraction pipeline could turn into usable sprites.
- Produced usable **static** front and back poses on character sheets.

## The AI suggestion we tested

> Use a generative **video** model to produce the NPC walk animations,
> then extract frames — the same pipeline already used for Pete.

We asked it to generate directional walk cycles for three occupant NPCs
(office worker, office lady, cleaner).

## What AI produced (the failure)

| Expected for a top-down game | What the model returned |
|---|---|
| Walk cycles for **4 facings**: down / up / left / right | **Left/right only.** No "toward camera" or "away from camera" walk was ever produced across multiple attempts |
| **Stable** character size + proportions every frame | Head size, body height and even facing **drifted** frame to frame |
| Transparent / flat background | Flat grey background with an anti-aliased halo and a baked ground shadow |
| A clean, loopable stride | Mixed intent — some clips had the character standing, pointing, or looking tired instead of walking (`Failed_generation.mp4` is one such reject) |

Source clips: Google Drive `NPCs/` — `*LR.mp4` (LR = the only axis it could do),
`D_pixel_art_character_walk_cy.mp4`, `Failed_generation.mp4`.

## How we verified it was wrong

Checked the output against the concrete requirements of our own engine
(`entities/player.py`): the renderer needs, per character, an
`idle_<dir>` frame and four `walk_<dir>_<n>` frames for
`dir in {down, up, left, right}`, all the same pixel height, anchored at
the feet so idle<->walk doesn't jitter. The generated clips satisfied
**one** of the four directions and failed the stability requirement. This
isn't a taste judgement — the missing frames are a hard functional gap:
walk a character "up" in-engine with no up frames and it either freezes
or moon-walks sideways.

## Our decision

| AI suggestion | Decision | Why |
|---|---|---|
| Generate NPC animation as **video**, extract frames | **Rejected as the sole method** | Only yields the left/right axis; proportions unstable |
| Keep re-prompting the video model for up/down | **Rejected** | Repeated attempts never produced a usable toward/away walk; not worth the time budget |
| **Recover the missing directions from other assets we already had** | **Accepted (modified approach)** | The video wasn't the only source — see below |
| Hand-drawn walk footwork | **Rejected** (no artist) → replaced with a **procedural bob** (vertical bounce + slight squash/lean) off each pose | Cheap, deterministic, fine for an NPC that only ever trails the player |

### The correction: combine sources instead of forcing one

The video model failing at up/down didn't actually block us, because the
video was never the only reference. Each victim's 4-direction set was
assembled from what we already had:

| Direction | Source |
|---|---|
| **down** (front) | Standalone front pose / character-sheet front figure |
| **up** (back) | The **back view** already drawn on each character sheet |
| **left** (side) | One clean side frame pulled from the LR video clip |
| **right** (side) | Horizontal mirror of **left** |

So the human contribution was recognising that the AI's failure was
*narrow* (one model, one axis) and routing around it with assets from a
different generation, plus a mirror trick — not accepting a hole in the
animation set and not throwing the whole AI pipeline out.

Implemented in `entities/victim.py`: the loader still falls back to the
`down` frames for any missing direction, and the whole sprite system
falls back to the original coloured-circle marker if no art is present —
so the pipeline degrades gracefully at every level instead of breaking
the build.

## What this shows about using AI responsibly

- AI **accelerated** concept art and the side-view case, but could not
  deliver a **complete, production-ready** asset set.
- The gap was only obvious because we checked the output against a
  concrete spec we wrote ourselves. Taking the clips at face value
  ("looks like a walk") would have surfaced the problem only at
  integration time.
- Human judgement decided the *scope reduction* (victims don't need 4
  directions) and the *fallback strategy*. The model offered neither.

## If we had blindly followed the AI

Taking "the video model can't do up/down" at face value, we would have
either shipped victim NPCs that only ever face the screen (wrong facing
almost constantly, since they trail the player through a maze in every
direction) or scrapped the AI-art pipeline entirely. Neither was
necessary — the fix was to notice the failure was specific to one model
and one axis, and pull the missing views from the character sheets and a
single mirrored video frame instead.

---

## Part 2 — Testing an AI search-strategy recommendation

Full write-up + reproducible evidence: **`docs/search_comparison.md`**
(run `python tools/search_comparison.py`).

In short: the AI recommended Greedy Best-First Search for the rescue
agent's pathfinding ("fewer node expansions"). We tested BFS / Dijkstra /
A* / Greedy on our own hazard-weighted maze and found Greedy and BFS take
routes ~14% more costly (straight through fire) because they minimise
*tiles*, not *danger*. **Accepted** A* (ties Dijkstra for optimality,
keeps most of the speed); **rejected** Greedy and BFS for the agent;
**kept** BFS only for the genuinely-unweighted jobs (fire-spread ring
counting, connectivity checks). Implemented in `pathfinding.py` /
`entities/rescue_agent.py`.
