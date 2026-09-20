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
- [x] Optional learned-AI option (opt-in, AI player only): Gymnasium environment, evaluation harness with confidence intervals, `LearnedAgent` -- **no model trained yet**, see "Learned AI (optional)"
- [x] Music for the title, menus, gameplay and both endings -- synthesised at runtime (`audio.py`), no audio assets, mute with `M`
- [x] Per-stage set dressing (`props.py`): each of the ten stages has its own palette and furniture -- canteen tables and chairs, server racks, parked cars, hospital beds, open sky on the roof. Drawn, never collided with, so it changes how a stage looks and not how it plays
- [x] Per-stage music: one gameplay bed parameterised from calm (stage 1) to frantic (stage 10) -- faster tempo, harsher timbre, a drier pulse and a tritone from the midpoint

## Learned AI (optional)

The default AI is the hazard-weighted A* rescuer above, and it stays the
default. There is also an **opt-in learned brain** for the AI player only --
Pete is always keyboard-driven, and nothing here changes how A* plays.

- `pyro_pete_game/ml/` -- the pieces:
  - `observation.py`: what the learned agent sees and the five actions
    (stay / up / down / left / right, one tile per step). It gets **less**
    information than A*, which plans over the whole map and hazard field: only
    explored layout, hazards and occupants within its vision radius, plus the
    exit, head-count and fire countdown that the HUD already shows a human.
  - `env.py`: `EvacuationEnv`, a Gymnasium environment that steps the real
    `GameSession` (same fire, collapses, locked door and stage-end rules).
    Reward comes from the game's own score, with no distance shaping. Passes
    `gymnasium.utils.env_checker.check_env`; `env.action_masks()` is there
    for `sb3_contrib.MaskablePPO`.
  - `policy.py`, `outcome.py`, `evaluation.py`: the policy interface, one
    shared definition of how an AI-only episode ended, and the harness.
- `entities/learned_agent.py` -- `LearnedAgent` shares the A* agent's body
  (health, hazard damage, smoke slowdown, vision, sprites) so both brains face
  identical rules, and replaces only the decision.
- **In the game**, Watch AI Play shows "Choose the AI's Brain" (after the AI skin menu; Play vs AI
  keeps its rival on A\* and has no extra screen) and it lists **A\* planner (the default)**, **Learned v4** and **Learned v5**.
  A model is offered only when its file is in `pyro_pete_game/ml/models/`
  (`ai_v4.zip`, `ai_v5.zip`, and optionally `ai_policy.zip` as "Learned model") and
  stable-baselines3 is importable; the JSON file beside each model records the search
  order it was trained with, so the game configures the AI body to match. With no model
  files the game plays exactly as before, and a model that fails to load falls back to A\*.

**Status: the plumbing is built, tested and has run for real; no model that
plays well exists yet** (see the experiment notes below). Loading a real
stable-baselines3 model through the game's menu has been verified.

Compare agents (works today; needs only `requirements.txt`, not gymnasium or torch):

```bash
python tools/evaluate_agents.py --agents astar,random,stay --stages 1-3 --episodes 20 --workers 4
```

Every agent plays the same stages with the same seeds, and the report gives
Wilson intervals for rates and a paired score comparison. Use plenty of
episodes: an earlier 9-vs-7-deaths difference over 80 runs turned out to be
noise, which is why the intervals are printed. To judge a trained model
fairly, train on stages 1-7 and evaluate on 8-10, which it has never seen.

### Training, and reviewing how it went

```bash
pip install -r requirements.txt -r requirements-ml.txt
python tools/train_agent.py --timesteps 500000 --name first_try
```

Trains MaskablePPO on stages 1-7 and validates on stages 8-10, which it never
trains on. About 550 steps/s with 6 parallel envs on the dev machine (100k
steps in ~3 minutes). Everything is kept in `runs/<name>/` (git-ignored):

| file | what it is |
|---|---|
| `epochs.csv` | **the epoch-vs-accuracy log**: one row per epoch with steps, accuracy over the last 100 training episodes, died / gave-up / timeout rates, game score, reward, policy loss, value loss, entropy, KL, steps/s |
| `evaluations.csv` | at each checkpoint, fixed seeded episodes with the deterministic policy on training stages and held-out stages, with 95% intervals, next to A* on the *same* episodes |
| `epoch_vs_accuracy.png` | chart of the two files above (accuracy, game score, loss/entropy vs epoch) |
| `report.html` | chart + tables + the recordings in one page; auto-refreshes every 30 s while training so it can stay open in a browser |
| `videos/` | screen recordings of the model playing at each checkpoint, and A* once for comparison |
| `checkpoints/`, `best_model.zip`, `final_model.zip` | saved models |
| `final_report.txt` | fresh-seed test at the end: best and final model vs A*, paired |

*Epoch* = one iteration: collect a batch of play with the current policy, then
update the network. *Accuracy* = the share of episodes in which the AI got
every occupant still alive out and survived itself. RL has no fixed dataset, so
there are two accuracies: the noisy rolling **train accuracy** while learning,
and the **validation accuracy** at checkpoints (the honest one, especially on
held-out stages). Choosing the best checkpoint on held-out episodes makes that
number slightly optimistic, which is why the final test uses fresh seeds.

Useful options: `--max-minutes N` (stop gracefully), `--resume MODEL.zip`
(continue; `--run-dir` to keep logging in the same folder), `--install` (copy
the best model to `pyro_pete_game/ml/models/ai_policy.zip` so the game offers
"Learned model" -- only use this on a model that beats or matches A*),
`--record-stages 1,9`, `--eval-every`, `--eval-episodes`, and
`--abandon-penalty` (see below). Ctrl+C saves and still produces the report.

```bash
python tools/record_agent.py --agent model:runs/first_try/best_model.zip --stage 9   # record any agent, any stage
python tools/record_agent.py --agent astar --stage 9 --seed 1000                     # same seed => compare side by side
python tools/plot_training.py runs/first_try                                          # rebuild chart + report
```

Imitation learning (the network is trained to copy A*):

```bash
python tools/train_imitation.py --name imit_b --obs-version 2   # A* demonstrations, cloning, DAgger, final test
```

Logs one row per epoch (loss, action-match accuracy on held-out episodes and on
stages never trained on, and how the network actually plays), writes a chart, and tests
the result against A* on all ten stages. `--obs-version 2` gives the network A*'s own
information (route hints), which is what makes it work; `1` is the local-window ablation.

**What the experiments showed.** Reinforcement learning from scratch has **not** produced
an AI that rescues people: with the plain game-score reward it learned to stand still
(74-91% of episodes, three seeds), and none of the 12 trained models evacuates anyone in
the form the game uses. Imitation learning works far better: trained to copy A* and given
the information A* has, plus a memory of its own path, the best network evacuates **80%** of
300 fresh episodes against A*'s **87%**. It is roughly level with A* on the stages it trained
on (84% vs 87%) and clearly behind on three it never saw (71% vs 87%); with only a local window
it managed 20%. It does **not** match A*. The full
write-up, with the charts, the epoch-vs-accuracy logs, the recordings and the corrections I
had to make to my own claims, is in
[`pyro_pete_game/ml/ML_Findings/`](pyro_pete_game/ml/ML_Findings/README.md). A GPU would not
speed training up (most of the time is the game simulation).

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
Tests (522): `pip install pytest`, then `python -m pytest` from `pyro_pete_game/`
(`tests/test_core.py` also runs standalone with plain `python`).

## Stage identity: set dressing and music

The ten stages are generated from the same maze algorithm, so on their own
they are ten grey corridor grids with different names in the HUD. Two
systems give each one a character of its own.

**Set dressing** (`props.py`). Every stage module declares a `THEME`, which
carries a palette (floor, wall, accent) and a bag of props placed on the
floor:

| Stage | Theme | What's in the room |
|---|---|---|
| 1 Ground Floor | `lobby` | reception desks, benches, planters, noticeboards |
| 2 Staff Canteen | `canteen` | tables, chairs, a serving counter, fridges |
| 3 Records Office | `records` | filing cabinets, shelving, loose paper |
| 4 Server Room | `server` | racks, cable trays, consoles, cooling plant |
| 5 Chemical Store | `chemical` | drums, crates, hazard signs, eyewash |
| 6 Car Park B2 | `carpark` | parked cars, pillars, bay markings, cones |
| 7 Ward Block | `ward` | beds, privacy screens, drip stands, trolleys |
| 8 Turbine Hall | `turbine` | turbines, pipework, valves, a gantry rail |
| 9 Reactor Annex | `reactor` | coolant tanks, shielding, consoles, trefoils |
| 10 Roof Plant | `roof` | open sky, HVAC units, vents, ducts, aerials |

Two rules hold throughout. Props are **drawn, never collided with** --
making a chair solid would change which routes exist, and with them maze
solvability, the A* agent's plan, the difficulty tuning and the
observations the learned agent trains on. `tests/test_campaign.py` pins
this by rebuilding each stage with its theme stripped and asserting an
identical walkability grid. And they are **drawn, not loaded**: pygame
primitives like the rest of the rendering, so ten themed stages cost
nothing in the repository. Placement is seeded off the stage's own `SEED`,
so the furniture is in the same place every run.

**Music** (`audio.py`). The single gameplay track is now
`_build_game(intensity)`, registered once per stage as `game_1` ...
`game_10` and selected by `game_track(session.stage_index)`. Stage 1 is
0.0 and stage 10 is 1.0, and every knob moves one way only, so the ramp
is monotonic by construction rather than by hand-tuning ten tracks:

- **tempo** -- the beat shortens from 0.30s to 0.17s; the strongest cue
- **timbre** -- the arpeggio crosses from a soft triangle to a buzzing square
- **the pulse** -- the eighth-note bass gets louder and drier, like a countdown
- **detune** -- the pad drifts from 8 to 34 cents, from warm to queasy
- **the tritone** -- from the midpoint a dissonant Eb fades in against the A

Tracks stay lazily built, so reaching stage 3 never costs the seven
stages you haven't heard. The tests assert the loop gets strictly shorter
and strictly louder on every one of the ten steps, and measure the
tritone spectrally rather than trusting the builder.

## Project layout

```
pyro_pete_game/
  main.py              # pygame shell: intro -> menus -> playing/watching -> results
  settings.py          # shared constants
  intro.py             # opening cinematic ("First Alarm") -- pygame-native, drawn not loaded
  menu.py              # reusable Play/Watch + skin-select menu, shared muted background
  audio.py             # runtime-synthesised soundtrack; the gameplay bed ramps per stage
  props.py             # per-stage palettes + set dressing (decorative only, never blocks)
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
    learned_agent.py   # same body, decisions from a learned policy (opt-in, AI player only)
  ml/                  # learned-AI option: observation, policy, env (Gymnasium), evaluation,
                       #   expert (A* as a teacher), imitation (cloning + DAgger),
                       #   training (SB3 callbacks), report (epoch-vs-accuracy), recording (video)
  levels/level_01.py   # first map (size + seed)
  assets/pete/         # Pete sprite frames (hand-picked from clips)
  assets/robot/        # walking-robot AI skin (idle + walk, 4 directions)
  assets/victims/<name>/   # GENERATED by tools/build_victim_sprites.py
  assets/opening scene/    # original HTML/canvas prototype intro.py's cinematic was built from
  assets/Claude outputs/   # robot concept sheets from the art-generation pass
  docs/ai_critique.md  # "what AI got wrong" write-up for the report
  tests/test_core.py   # maze / search / hazard-placement checks
  tests/test_campaign.py   # ten stages, stage-end rules, win/lose outcomes, music
  tests/test_ml.py         # observation fairness, learned agent, Gym env, harness statistics
  tests/test_training.py   # run logs, report/chart, recording, a tiny real training run
  tests/test_imitation.py  # A* as teacher, cloning, DAgger data, information parity with A* (no God mode)
  tests/test_search_options.py  # far-side / corner-skip search options, model JSON sidecar, the AI-model menu
tools/
  build_victim_sprites.py  # rebuilds assets/victims/ from the Drive art
  search_comparison.py     # BFS vs Dijkstra vs A* vs Greedy on the maze
  evaluate_agents.py       # compare AI agents on the real game, with confidence intervals
  train_agent.py           # train the learned AI by RL; logs epoch-vs-accuracy, records videos, final test
  train_imitation.py       # train it to copy A* (cloning + DAgger); epoch-vs-accuracy log, final test vs A*
  record_agent.py          # screen-record any agent on any stage (MP4 via ffmpeg, else GIF)
  plot_training.py         # rebuild a run's chart + report.html from its CSVs
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
