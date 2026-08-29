# Part 2 — Testing an AI search-strategy recommendation

CT3201 Phase 6 / Stage 7: "Identify at least one important AI-generated
recommendation and test it."

## The recommendation

While discussing the rescue agent's pathfinding, the AI suggested:

> "Use Greedy Best-First Search instead of A\* — it expands fewer nodes,
> so it's faster."

## Why this needed testing rather than accepting

Our routing problem isn't a plain shortest-path search. Fire, smoke and
sparking panels make tiles **expensive but passable**; debris and the
locked door make tiles **impassable**. The agent's objective is the
*least-dangerous* route to a victim / the exit, not the one with the
fewest tiles. "Faster to compute" and "better route" are different axes.

Also: our maze was originally a *perfect* maze (one path between any two
cells), on which BFS, Dijkstra, A\* and Greedy all return the identical
path — the comparison would have been meaningless. We braided the maze
(`level_01.BRAID = 0.18`, `mazegen.generate_maze(..., braid=)`) to add
loops so route choice actually exists.

## The test

`tools/search_comparison.py` runs all four strategies from spawn to exit
over the same hazard-cost function, after letting the fire spread ~40s.
Cost = 1.0 per step + the hazard surcharge of each tile entered
(`HazardField.entry_cost`: fire +8, smoke +2×density, panel +6).

```
spawn (1, 1) -> exit (17, 11), 27 tiles burning

strategy            path cost   steps  hazard tiles
---------------------------------------------------
BFS (unweighted)        101.8      30             9
Dijkstra                 43.8      42             2
A*                       43.8      42             2
Greedy best-first        43.8      42             2
```

Here BFS takes the 30-tile route straight through **9 burning tiles**
(cost 101.8); A\* / Dijkstra spend 12 extra steps to cut that to **2**
(cost 43.8) — less than half. Greedy matched A\* on this fire state
because the safe route also happened to be the roughly-straight one; with
the fire spread differently it diverges (it's heuristic-only). Debris
placement is seeded in the script so the table is reproducible; the exact
numbers shift with how far the fire has spread, but BFS/Greedy staying
cheaper-by-tiles / costlier-by-danger is the consistent finding.

## What the evidence shows

| Claim | Verdict |
|---|---|
| "Greedy expands fewer nodes" | **True** — heuristic-only, no priority queue over cost-so-far. |
| "So it's the better choice for the agent" | **False** — Greedy ignores accumulated cost, so it walks into fire whenever the fire is roughly toward the goal. BFS is worse still: it ignores cost entirely and is ~14% more costly here for the same number of steps. |
| A\* vs Dijkstra | **Identical cost** (A\* = Dijkstra + admissible heuristic). A\* expands fewer nodes getting there, which is the real speed win — without giving up optimality. |

## Decision

| AI suggestion | Decision | Why |
|---|---|---|
| Use Greedy Best-First for the agent | **Rejected** | Not cost-optimal on a hazard-weighted map — routes through fire |
| Use plain BFS | **Rejected** for the agent | Minimises tiles, not danger |
| Use A\* over `HazardField.entry_cost` | **Accepted** | Optimal route (ties Dijkstra) at a fraction of the node expansions |
| Keep BFS for fire-spread ring counting + connectivity checks | **Accepted** | Those are genuinely unweighted — BFS is the right tool there |

Implemented in `entities/rescue_agent.py` (`astar_path`) and
`pathfinding.py` (all four kept, so the comparison stays runnable).

## What would have happened if we'd followed the AI

The agent would have led rescued occupants **through the fire** whenever
the exit was roughly beyond it — taking heavy damage and sometimes dying
mid-escort — while reporting a "shorter" path. The bug would look like
bad game balance, not a wrong algorithm choice.
