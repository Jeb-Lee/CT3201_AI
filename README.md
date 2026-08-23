# Pyro Pete: Emergency Evacuation

A 2D top-down (Zelda-style, "early-days"/chibi art direction) evacuation game
built for the CT3201 AI course. Pyro Pete arrives at a burning building,
navigates a maze-like floor plan, and leads trapped occupants to safety.

The maze/routing setup deliberately mirrors the course's Emergency Evacuation
Routing exercise (floor plan modeled as a graph, exits as goal nodes) so the
same level data can eventually drive both human play and an AI-controlled
pathfinding agent.

## Status

- [x] 4-directional character controller (idle + walk animation, Down/Up/Left/Right)
- [x] Tile-based maze generation (guaranteed-solvable via recursive backtracker) with camera + wall collision
- [ ] Victim NPCs / rescue mechanic
- [ ] Fire & smoke hazards
- [ ] Multiple levels / difficulty progression
- [ ] AI-play mode (pathfinding agent)

## Running it

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
cd pyro_pete_game
..\.venv\Scripts\python main.py
```

Controls: WASD or arrow keys to move, `R` to restart, `Esc` to quit.

## Project layout

```
pyro_pete_game/
  main.py              # game loop / entry point
  settings.py          # shared constants
  mazegen.py           # maze generation (recursive backtracker)
  tilemap.py           # tile grid: collision, rendering, exit detection
  camera.py            # follow-camera with map-bounds clamping
  tools_make_transparent.py  # one-off asset processor (bakes real alpha
                              # into sprites -- see its docstring)
  entities/
    player.py          # Pyro Pete: animation state machine, movement, collision
  levels/
    level_01.py         # first map (size + seed; more levels follow the same shape)
  assets/pete/          # sprite frames (idle + walk, 4 directions)
```

## Asset notes

Character art was AI-generated (Kling) across several batches referencing a
hand-picked style sheet, then post-processed: walk-cycle frames were
extracted from short generated video clips (auto-cropped to the character's
bounding box, aligned to a shared canvas so idle/walk don't jitter), and
`tools_make_transparent.py` bakes real per-pixel alpha into every sprite to
remove anti-aliasing halos that a simple colorkey couldn't catch.
