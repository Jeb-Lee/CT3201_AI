# Short Video Presentation — outline (7–10 min)

Target ~9 min. One speaker per section is fine. Record gameplay clips
ahead of time so you're not fighting the game live.

| # | Section | Time | Show on screen | Say (key points) |
|---|---|---|---|---|
| 1 | **Problem** | 0:45 | a still of the burning maze | Evacuation routing: find occupants who don't know the layout, lead them out before fire / smoke / collapse cut the route. The main decision: push deeper for another person, or bank the ones you have. |
| 2 | **Human‑first formulation** | 1:00 | the formulation table (Section 2) | State / actions / goal / **cost** (hazards as weighted costs, not walls) / constraints / **partial** information. Our first plan was plain BFS with fire as a wall. |
| 3 | **AI‑assisted exploration** | 1:15 | 2–3 prompt/response cards | We used AI to *challenge*, not to design. It redirected us from BFS to weighted search, listed A\* / Dijkstra / Greedy, and caught two bad assumptions (full occupant map; single‑path maze). |
| 4 | **AI critique & our decisions** | 1:15 | the Accept/Modify/Reject table (Section 4) | Walk 3 rows: rejected Greedy, accepted A\*, kept BFS only for unweighted jobs. Emphasise we verified each, not just trusted it. |
| 5 | **Final solution — demo** | 1:45 | **live‑ish gameplay clip**: drone planning a route, re‑planning around a collapse, fetching the key, the score on the results screen | The decision loop (sense → choose goal → A\* plan → move → re‑plan). Human and AI drone race the same map; results screen scores both. |
| 6 | **Evaluation** | 1:15 | the search comparison cost table | AI said "use Greedy, fewer expansions." We tested all four. BFS routes through 9 fire tiles (cost 102) vs A\* through 2 (cost 44); Greedy is unreliable — matches A\* only when the straight line is safe. *Fewer expansions ≠ safer route.* Verdict: rejected for routing. |
| 7 | **COMPULSORY — What AI got wrong** *(critical evaluation)* | 1:30 | side‑by‑side: the failed AI video clip vs the final 4‑direction sprite | **What worked:** side‑view walk clips, concept art, the whole implementation. **What didn't:** the video model never produced a walk‑toward/away‑camera cycle; proportions drifted. **What AI got wrong:** it treated "looks like a walk" as done. **How verified:** checked against the engine's needs — 4 directions, fixed size, feet anchor — it met one. **Corrected:** assembled the sprites from mixed sources + procedural animation. This is our *identified → verified → corrected* example. |
| 8 | **Responsible AI** | 0:45 | the 7‑dimension table | Fairness (agent takes damage too), **bias** (greedy nearest‑first has no triage), **transparency** (it draws its route), oversight (decision‑support, not autonomous). Should it deploy? Not as an autonomous router — yes as a transparent aid a trained rescuer can override. |
| 9 | **Reflection & conclusion** | 0:45 | one line per takeaway | AI is fast at breadth; you must supply the objective and verify against it. A technically‑true suggestion can still be wrong for your problem. Every final decision was ours. |

## Clips to record beforehand

1. Drone planning a route (blue line), then a ceiling collapse forcing it
   to re‑plan a different way — ~8 s.
2. Drone reaching a locked door, detouring to the key, door opening — ~8 s.
3. A full short run to the results screen showing the score breakdown — ~10 s.
4. The failed AI walk video (`NPCs/.../*_LR.mp4` and `Failed_generation.mp4`)
   next to the final in‑game 4‑direction sprite — ~6 s.
5. `python tools/search_comparison.py` output scrolling — ~5 s.

## The one required demonstration

The brief requires showing **one example where you identified → verified →
corrected/rejected** an AI suggestion. Use **Section 7** (the NPC animation).
Backup if a marker disputes it's "corrected": also mention the Greedy →
A\* rejection in Section 6, which is *identified → verified → rejected*.
