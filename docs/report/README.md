# Report drafts — CT3201 Mini Project

First drafts of the written deliverables, built from the game as it stands
and the AI‑assisted work in `docs/ai_critique.md` and
`docs/search_comparison.md`.

| File | Covers | Deliverable |
|---|---|---|
| `CT3201_Slides.pptx` | 10‑slide starter deck (title + 9 sections) | **deliverable 1** — add names, screenshots, the flowchart image, refine |
| `CT3201_Report_IEEE.docx` | the report in **IEEE A4 two‑column conference format** (matches `~/Downloads/IEEE 2 col conference-template-a4.docx`) | **report deliverable** — submit this one; add authors, fill `[TEAM]` markers, replace the Fig. 1 ASCII sketch with the real flowchart |
| `CT3201_Report.docx` | same content, plain single‑column Word doc | working draft only |
| `CT3201_AI_Interaction_Log.docx` | the interaction log as a Word table | **deliverable 2** |
| `VIDEO_OUTLINE.md` | 7–10 min video script + clips to record | **deliverable 3** (script) |
| `REPORT.md` / `AI_INTERACTION_LOG.md` | the Markdown source the .docx/.pptx were built from | edit these + regenerate, or edit the Office files directly |

Regenerate the Office files after editing the Markdown:
`pip install python-docx python-pptx` then run the scripts in
`../../tools/` — `md_to_ieee_docx.py` (IEEE report), `md_to_docx.py`
(plain report + interaction log), `build_slides.py` (deck).

## Before you submit

- **Rewrite Section 8 (reflection) in your own words** — the brief grades
  your judgement, not a draft.
- Fill every **`[TEAM]`** marker.
- Add rows to `AI_INTERACTION_LOG.md` for any AI other than Claude Code.
- Confirm Section 1's problem/user framing matches your actual Stage‑1
  notes (done *before* using AI).
- The mermaid flowchart in `REPORT.md` Section 5 renders on GitHub; export
  it (or redraw it) for the slide.
