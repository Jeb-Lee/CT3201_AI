# Report drafts — CT3201 Mini Project

First drafts of the written deliverables, built from the game as it stands
and the AI‑assisted work in `docs/ai_critique.md` and
`docs/search_comparison.md`.

| File | Covers | Deliverable |
|---|---|---|
| `CT3201_Slides_rev02.pptx` | **slides, revision 02 (latest)**: the 11-slide deck for the presentation | **deliverable 1** |
| `CT3201_Report_IEEE_rev6.docx` | **revision 6 (latest, final)**: revision 5 with the final edits made by hand in Word: the full course and college names, "the drone" changed to "the AI" throughout, consistent capitalisation in the tables, and live cross-references between sections | edited by hand in Word from revision 5; the last Markdown source is `REPORT_rev4.md` |
| Earlier Word files (`CT3201_Slides.pptx`, `CT3201_Report.docx`, `CT3201_Report_IEEE.docx` and revisions 2 to 5) | removed from the working tree once revisions 6 and 02 superseded them | still in the Git history; the Markdown sources and `build_rev*.py` scripts that produced revisions 2 to 4 remain here |
| `CT3201_AI_Interaction_Log.docx` | the interaction log as a Word table | **deliverable 2** |
| `../../tools/greedy_vs_astar_scan.py` | the 150-situation test behind "Greedy took a costlier route in 98 of 150" (10 stages × 3 layouts × 5 fire times); run it to reproduce | evidence for Sections VI and VII |
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

## Revision 2 (learned-agent section)

`REPORT.md` and `CT3201_Report_IEEE.docx` (revision 1) are untouched. Revision 2 is assembled, not hand-edited:

| File | Role |
|---|---|
| `rev2_section_learning.md` | the new Section 7 (edit this to change the section) |
| `rev2_references.md` | reference entries by key; cited in the text as `[@key]`, numbered by first appearance |
| `build_rev2.py` | inserts the section into `REPORT.md`, renumbers later sections, fixes the "no neural network" statement in Responsible AI, adds conclusion / appendix lines and the reference list; writes `REPORT_rev2.md` |
| `make_figures.py` | draws the section's figures at report size into `figures/` from `pyro_pete_game/ml/ML_Findings/` data |

```
python docs/report/make_figures.py
python docs/report/build_rev2.py
python tools/md_to_ieee_docx.py --rev2      # writes CT3201_Report_IEEE_rev2.docx
```

References were checked against publisher / arXiv records for the less well known ones (masking, Neural A\*,
Stable-Baselines3, the imitation-learning survey, DAgger, DQfD); please still verify every entry before submission.

## Revision 3 (two-column layout)

Same words as revision 2; the layout changes. How tables and two columns work together in it:

- **Narrow tables stay in the column.** Up to about five short columns fit 3.3 in at 7.5 pt; they carry a
  `TABLE N` caption above, repeat their header row and never break across a page or column.
- **Wide tables and figures float to the top of a page across both columns** (the IEEE convention).
  Mark them `{wide}` at the end of the `Table:` caption line or the `![...](...)` line. The body never leaves
  two columns, so no text is squeezed into half-height columns around a table any more.
- **Prose does not go in tables.** A table whose cells are paragraphs becomes run-in paragraphs
  (the Responsible-AI dimensions).
- **Headings are Word styles**: Heading 1 (I., II.), Heading 2 (A., B.), Heading 3 (1), 2)) — `##`, `###`, `####`.

| File | Role |
|---|---|
| `rev3_section_learning.md` | Section 7 with the three-level heading structure and width markers |
| `build_rev3.py` | revision 2's assembly plus captions, widths, the Section 5 flowchart and the Responsible-AI paragraphs; writes `REPORT_rev3.md` |

```
python docs/report/make_figures.py
python docs/report/build_rev3.py
python tools/md_to_ieee_docx.py --rev3      # writes CT3201_Report_IEEE_rev3.docx
```

Revisions 1 and 2 still build with the same text as their committed .docx files with `python tools/md_to_ieee_docx.py` and `--rev2`.
