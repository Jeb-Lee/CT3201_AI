"""Assemble REPORT_rev3.md (the source of report revision 3).

Revision 3 is revision 2 laid out for a two-column page. The words are unchanged except where the
layout forced it; what changes is structure:

  * every table gets a real caption, and a width: column-width (the default) or `{wide}`, which the
    generator floats to the top of a page across both columns (the IEEE convention);
  * the Responsible-AI "dimension / assessment" table, whose cells are paragraphs, becomes paragraphs
    with run-in headings: prose does not read well in a table cell at any width;
  * Section 5's text sketch of the decision loop becomes a drawn flowchart (figures/fig_decision_loop.png),
    and the draft note about slide screenshots is removed;
  * subsection titles are in title case, and the learned-agent section has a three-level hierarchy
    (rev3_section_learning.md).

Then build the Word file:  python tools/md_to_ieee_docx.py --rev3

    python docs/report/build_rev3.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_rev2 import assemble, replace_once          # noqa: E402

MERMAID = re.compile(r"```mermaid\n.*?```\n", re.S)


def rev3_edits(text):
    # Section 2: the formulation table (column width)
    text = replace_once(text, "\n| Element | Our project |",
                        "\nTable: The rescuer formulated as a search problem\n\n| Element | Our project |")
    # Section 3 and 4: wide, three columns of sentences -> full width at the top of a page
    text = replace_once(text, "\n| We asked AI to… |",
                        "\nTable: What we asked AI, what it surfaced and what we took from it {wide}\n\n| We asked AI to… |")
    text = replace_once(text, "\n| AI suggestion / critique |",
                        "\nTable: AI suggestions and critiques, our decision and how we verified it {wide}\n\n"
                        "| AI suggestion / critique |")

    # Section 5: title-case subheadings, the drawn flowchart, no draft note about slides
    text = replace_once(text, "### The agent's decision loop", "### The Agent's Decision Loop")
    text = replace_once(text, "### Techniques used (from the brief's list)", "### Techniques Used (from the Brief's List)")
    text = replace_once(text, "### Other systems", "### Other Systems")
    if not MERMAID.search(text):
        raise SystemExit("Section 5's mermaid block not found (has REPORT.md changed?)")
    text = MERMAID.sub("Fig. 1 shows the loop the agent runs.\n\n"
                       "![The rescue agent's sense–decide–act loop. It re-plans whenever the world "
                       "changes, and at least every 0.25 s.](figures/fig_decision_loop.png)\n", text, count=1)
    text = replace_once(text, "\n*Screenshots + a short clip go on this slide — see `docs/report/VIDEO_OUTLINE.md`.*\n", "\n")

    # Section 6: the search-strategy table (column width)
    text = replace_once(text, "\n| strategy | path cost |",
                        "\nTable: Search strategies from spawn to exit after about 40 s of fire (seeded)\n\n"
                        "| strategy | path cost |")

    # Responsible AI: the dimension table becomes run-in paragraphs
    start = text.index("| Dimension | Assessment |")
    end = text.index("\n\n", start)
    rows = [r for r in text[start:end].split("\n")[2:] if r.strip()]
    paras = []
    for row in rows:
        name, body = [c.strip() for c in row.strip().strip("|").split("|", 1)]
        name = name.strip("*").strip()
        paras.append("**%s.** %s" % (name, body.strip().rstrip("|").strip()))
    text = text[:start] + "\n\n".join(paras) + text[end:]
    text = replace_once(text, "\n| AI‑suggested risk | Relevant to our system? |",
                        "\nTable: Further risks suggested by AI, and our verdict\n\n"
                        "| AI‑suggested risk | Relevant to our system? |")

    # Appendix
    text = replace_once(text, "\n| Topic | File |",
                        "\nTable: Where each part of the project lives in the repository\n\n| Topic | File |")
    return text


def main():
    assemble("rev3_section_learning.md", "REPORT_rev3.md", extra_edits=rev3_edits)


if __name__ == "__main__":
    main()
