"""Assemble REPORT_rev2.md (the source of report revision 2) from REPORT.md plus the learned-agent section.

  REPORT.md                       untouched first-draft source (revision 1)
  rev2_section_learning.md        the new Section 7 (v0-v5, architecture, alternatives, results)
  rev2_references.md              reference entries by key; cited in the text as [@key] or [@a,@b]

What this does, in order:
  1. Renumbers the sections after the insertion point (Responsible AI 7 -> 8, Reflection 8 -> 9,
     Conclusion 9 -> 10) and fixes the one in-text cross-reference to Responsible AI.
  2. Inserts the new section before Responsible AI.
  3. Makes the small edits the new section forces elsewhere: a bullet under "Techniques used", the
     "no neural network in the agent" row of the Responsible-AI table (no longer true), two sentences
     in the Conclusion, and rows in the Appendix.
  4. Numbers citations in order of first appearance and appends the reference list.
  5. Numbers tables in order and resolves {tab:key} labels to "Table N".

Then build the Word file:  python tools/md_to_ieee_docx.py --rev2

    python docs/report/build_rev2.py
"""

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII",
         "XVIII", "XIX", "XX", "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII", "XXVIII"]


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


def replace_once(text, old, new):
    if old not in text:
        raise SystemExit("pattern not found in REPORT.md (has it changed?): " + old[:70])
    return text.replace(old, new, 1)


def assemble(section_name="rev2_section_learning.md", out_name="REPORT_rev2.md", extra_edits=None):
    """REPORT.md + a learned-agent section -> out_name. `extra_edits(text) -> text`, if given, runs
    after the section is inserted and before tables and citations are numbered (revision 3 uses it)."""
    report = read("REPORT.md")
    section = read(section_name).strip() + "\n\n---\n\n"
    refs = {}
    for line in read("rev2_references.md").splitlines():
        if line.strip():
            key, text = line.split(":", 1)
            refs[key.strip()] = text.strip()

    # 1. renumber the sections that follow the insertion point
    def bump(m):
        n = int(m.group(1))
        return "## Section %d — " % (n + 1 if n >= 7 else n)
    report = re.sub(r"^## Section (\d+) — ", bump, report, flags=re.M)
    report = replace_once(report, "| identify ethical risks | see Section 7 |", "| identify ethical risks | see Section 8 |")

    # 3. edits forced by the new section
    report = replace_once(
        report, "### Other systems",
        "- **Machine learning (optional second brain)** — a neural network trained by reinforcement learning and\n"
        "  by imitation of A\\* (Section 7). It never replaces the A\\* agent, which stays the default and the benchmark.\n\n"
        "### Other systems")
    report = replace_once(
        report,
        "| Adversarial inputs to a neural component | **Not applicable** — no neural network in the agent. |",
        "| Adversarial inputs to a neural component | **Applies only to the optional learned brain (Section 7), not to the A\\* agent.** "
        "A network can misjudge inputs A\\* handles routinely (it trails A\\* on stages it has never seen: 73% against 87%), "
        "so it is never the default and A\\* stays the benchmark. |")
    report = replace_once(
        report, "final decision were ours.\n",
        "final decision were ours.\n\n"
        "We then asked whether a neural network could learn the same job. Reinforcement learning from the game score "
        "alone could not (0% of episodes evacuated; the network learned to stand still), so we switched to imitating A\\* "
        "and recorded every assumption that turned out to be wrong: the information the learner was given, the test time "
        "cap, the size of the memory gain, and a flaw in our own search-order rule. The final model (v5) evacuates 84% of "
        "300 fresh episodes against A\\*'s 85%, a difference we cannot distinguish from noise, but it remains behind A\\* on "
        "stages it has never seen (73% against 87%). A\\* stays the default and the benchmark.\n")
    report = replace_once(
        report, "| Playtest feedback | `playtesting/` |",
        "| Playtest feedback | `playtesting/` |\n"
        "| Learned agent: environment, network, cloning, DAgger | `pyro_pete_game/ml/`, `tools/train_imitation.py` |\n"
        "| Trained models v4 and v5 (offered in Watch AI Play) | `pyro_pete_game/ml/models/` |\n"
        "| Findings: logs, predictions, data, figures, recordings | `pyro_pete_game/ml/ML_Findings/` |")

    # 2. insert the section before Responsible AI
    marker = "## Section 8 — Responsible AI"
    report = replace_once(report, marker, section + marker)
    if extra_edits is not None:
        report = extra_edits(report)

    # 5. table labels -> numbers (count table blocks in document order, outside code fences and quotes)
    lines, in_fence, n_tables, prev_table, labels, pending = report.split("\n"), False, 0, False, {}, None
    for ln in lines:
        s = ln.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or s.startswith(">"):
            continue
        m = re.match(r"^Table: \{tab:(\w+)\}", s)
        if m:
            pending = m.group(1)
        is_table = s.startswith("|")
        if is_table and not prev_table:
            n_tables += 1
            if pending:
                labels[pending] = ROMAN[n_tables - 1]
                pending = None
        prev_table = is_table
    report = re.sub(r"^(Table: )\{tab:\w+\} ", r"\1", report, flags=re.M)
    report = re.sub(r"\{tab:(\w+)\}", lambda m: "Table " + labels[m.group(1)], report)

    # 4. citations by first appearance
    order = []

    def cite(m):
        keys = [k.strip().lstrip("@") for k in m.group(1).split(",")]
        for k in keys:
            if k not in refs:
                raise SystemExit("unknown reference key: " + k)
            if k not in order:
                order.append(k)
        return ", ".join("[%d]" % (order.index(k) + 1) for k in keys)
    report = re.sub(r"\[(@[\w]+(?:\s*,\s*@[\w]+)*)\]", cite, report)
    unused = sorted(set(refs) - set(order))
    if unused:
        raise SystemExit("references defined but never cited: " + ", ".join(unused))
    report = report.rstrip("\n") + "\n\n---\n\n## References\n\n" + "\n\n".join(
        "[%d] %s" % (i + 1, refs[k]) for i, k in enumerate(order)) + "\n"

    out = os.path.join(HERE, out_name)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(report)
    print("wrote", out, "-", len(order), "references,", n_tables, "tables; labels:", labels)


def main():
    assemble()


if __name__ == "__main__":
    main()
