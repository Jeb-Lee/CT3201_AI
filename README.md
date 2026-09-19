# Pyro Pete: Emergency Evacuation

A 2D top-down (Zelda-style, "early-days"/chibi art direction) evacuation game
built for the CT3201 AI course. You drive Pyro Pete through a burning,
collapsing maze, pick up trapped occupants and lead them to the exit -- while
an autonomous **AI rescue agent** runs the same maze at the same time, under
the same rules. The two of you share one pool of occupants, and a results
panel compares the two rescuers when the stage ends (see *How a stage ends*).

Clearing a stage promotes you to the next of **ten**, which scale up through
bigger floor plans, more occupants and harsher hazards.

Launching the game opens a short animated title sequence ("First Alarm"),
then a menu to choose **Play vs AI** or **Watch AI Play** (spectate only,
no Pete), then a skin menu to pick how the AI opponent looks -- a walking
**robot** or the original **drone** -- before dropping into a run.

The floor-plan-as-graph setup mirrors the course's Emergency Evacuation
Routing exercise, and the hazards deliberately make routing non-trivial so
BFS is no longer automatically optimal -- see `docs/ai_critique.md` for the
BFS / Dijkstra / A* / Greedy comparison this enables.

## How a stage ends

Every occupant is in one of four states: **waiting** to be found, **being
escorted** by a rescuer, **out**, or **lost**. An occupant counts as *out* only
once whoever is escorting them reaches the exit. The HUD shows this as
`Occupants out 2/5   Left 3`, plus `Lost 1` when someone has died.

The stage ends when either:

1. everyone still alive has been **found** and either they are all out, or
   Pete or the AI reaches the exit (first one there ends it -- an escort still
   on its way doesn't count as out); or
2. nobody still alive can carry on (Pete dead or absent, and the AI dead or
   finished).

Reaching the exit on its own does not end anything -- it only banks whoever
you are escorting, so walking out empty-handed is not a win. If a rescuer dies,
the occupants it was escorting die with it and come off the total; the other
rescuer carries on with whoever is left.

**Pete clears the stage** if he is alive at the end and led at least one
occupant out; otherwise the panel reads "You didn't save anyone" or "Pete
didn't make it". In Watch AI Play the AI clears it if it survives an
evacuation of everyone left; giving up with people still inside is not a clear.

The AI is told the stage's head-count (the same figure the HUD shows you) but
not where anyone is, so it stops searching once nobody is left to find rather
than wandering an emptied building.

## Status

- [x] 4-directional character controller (idle + walk, Down/Up/Left/Right)
- [x] Tile-based maze generation (guaranteed-solvable recursive backtracker) + camera + collision
- [x] Victim NPCs / rescue + escort mechanic (animated sprites, circle fallback)
- [x] Hazards: spreading fire, functional smoke (slow + vision), sparking panels, collapsing debris, locked door + key
- [x] Hazard-weighted A* AI agent: partial observability (no victim map), takes damage, re-plans as the map changes, fetches the key, draws its route
- [x] Fog of war with memory (seen tiles stay dim)
- [x] Human-vs-AI results screen + per-rescuer stats
- [x] Search-strategy comparison harness (`tools/search_comparison.py`) + unit tests (`tests/test_core.py`)
- [x] Animated title sequence ("First Alarm") + Play/Watch and AI-skin-select menus
- [x] Robot sprite option for the AI, alongside the original drone (picked at the skin menu)
- [x] "Watch AI Play" spectate mode -- no Pete, camera/fog follow the AI, single-column results
- [x] Pause (`P`)
- [x] Ten-stage campaign with a scaling difficulty curve (`levels/`, tuned via `levels/tuning.py`)
- [x] Shared occupant pool: `out / left / lost` counter, stage ends when everyone left alive is out (or found and someone reaches the exit); a dead rescuer loses its escort
- [x] Outcome-aware results panel -- Enter advances a stage after a clear
- [x] The AI knows the stage head-count, so it stops searching once nobody is left to find
- [x] Music for the title, menus, gameplay and both endings -- synthesised at runtime (`audio.py`), no audio assets, mute with `M`

## Running it

Your system Python already has the deps (`pygame`, `numpy`, `pillow`):

```bash
cd pyro_pete_game
python main.py
```

or in a venv: `python -m venv .venv && .venv\Scripts\pip install -r requirements.txt`.

Controls: WASD / arrows move, `P` pause, `R` restart, `M` mute, `Esc` quit.
On the results panel, Enter goes to the next stage after a clear, or back to
the menu otherwise.
Menus: arrow keys or mouse to choose, Enter/click to confirm, `Esc` to back out a screen.
Tests: `pip install pytest`, then `python -m pytest` from `pyro_pete_game/`
(`tests/test_core.py` also runs standalone with plain `python`).

## Project layout

```
pyro_pete_game/
  main.py              # pygame shell: intro -> menus -> playing/watching -> results
  settings.py          # shared constants
  intro.py             # opening cinematic ("First Alarm") -- pygame-native, drawn not loaded
  menu.py              # reusable Play/Watch + skin-select menu, shared muted background
  audio.py             # runtime-synthesised soundtrack (title/menu/game/win/loss), silent without a device
  levels/              # the ten campaign stages + tuning.py (per-stage difficulty knobs)
  mazegen.py           # perfect-maze generation (recursive backtracker)
  tilemap.py           # tile grid: collision, dynamic blocks (debris/doors), rendering
  pathfinding.py       # BFS, Dijkstra, A*, Greedy -- all take a per-tile cost_fn
  camera.py            # follow-camera with map-bounds clamping
  visibility.py        # fog of war with explored-tile memory
  stats.py             # per-rescuer run metrics
  results.py           # end-of-run You-vs-AI panel, plus a spectate-only variant
  hazard_field.py      # aggregates every hazard; answers damage / cost / slow / vision
  hazards.py           #   spreading fire + functional smoke field
  panels.py            #   stationary sparking electrical panels
  debris.py            #   timed ceiling collapse (connectivity-checked)
  doors.py             #   one locked door + its key
  tools_make_transparent.py  # one-off sprite alpha baker (see its docstring)
  entities/
    player.py          # Pyro Pete: animation, movement, smoke slowdown
    victim.py          # trapped occupants: 4-dir sprites + circle fallback, escort;
                       #   states idle / following / saved / dead
    rescue_agent.py    # autonomous hazard-weighted A* agent (robot or drone skin)
  levels/level_01.py   # first map (size + seed)
  assets/pete/         # Pete sprite frames (hand-picked from clips)
  assets/robot/        # walking-robot AI skin (idle + walk, 4 directions)
  assets/victims/<name>/   # GENERATED by tools/build_victim_sprites.py
  assets/opening scene/    # original HTML/canvas prototype intro.py's cinematic was built from
  assets/Claude outputs/   # robot concept sheets from the art-generation pass
  docs/ai_critique.md  # "what AI got wrong" write-up for the report
  tests/test_core.py   # maze / search / hazard-placement checks
  tests/test_campaign.py   # ten stages, stage-end rules, win/lose outcomes, music
tools/
  build_victim_sprites.py  # rebuilds assets/victims/ from the Drive art
  search_comparison.py     # BFS vs Dijkstra vs A* vs Greedy on the maze
```

## Asset notes

Character art was AI-generated (Kling) across several batches referencing a
hand-picked style sheet, then post-processed: walk-cycle frames were
extracted from short generated video clips (auto-cropped to the character's
bounding box, aligned to a shared canvas so idle/walk don't jitter), and
`tools_make_transparent.py` bakes real per-pixel alpha into every sprite to
remove anti-aliasing halos that a simple colorkey couldn't catch.

Victim NPCs are the exception: the video model would only produce stable
**side-view** clips and never a usable "toward / away from camera" walk.
So `assets/victims/<name>/` is **generated** by
`tools/build_victim_sprites.py`, which combines:

- **left / right** — a real 4-frame walk cycle pulled from the side-view
  (`*LR*`) clip (moving legs, like Pete), raw + mirrored
- **down / up** — a straight front pose + the back-view figure from the
  character sheet, animated with a procedural leg-step (no walk-to-camera
  footage exists)

The raw art (character sheets + clips, ~35 MB, mostly video) is **not in
git** — it lives in the shared Drive folder `CT 3201 AI / NPCs`. To
rebuild the sprites: download that folder, `pip install av scipy`, then
`VICTIM_SRC=<path> python tools/build_victim_sprites.py`.

Working around the video-model limitation is the project's "what AI got
wrong" example — see `docs/ai_critique.md`.

The robot AI skin (`assets/robot/`) came from a different, simpler pipeline
than Pete/the victims: clean pre-made sprites with real transparency already
baked in, no video-frame extraction or `tools_make_transparent.py` pass
needed. `assets/Claude outputs/` keeps the concept sheets from that
generation pass for reference. `assets/opening scene/` is the original
HTML/canvas prototype of the title cinematic (`first_alarm.html`) that
`intro.py`'s native-pygame version was built to match — kept for reference,
not loaded by the game at runtime.
