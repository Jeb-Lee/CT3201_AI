"""Markdown -> IEEE 2-column conference .docx for the CT3201 report.

    pip install python-docx
    python tools/md_to_ieee_docx.py

Reads docs/report/REPORT.md and writes docs/report/CT3201_Report_IEEE.docx,
styled after the IEEE A4 two-column conference template
(Downloads/IEEE 2 col conference-template-a4.docx):

  * A4, ~0.62" side margins, two columns with 0.5" gutter
  * Times New Roman 10 pt justified body, 14.4 pt first-line indent
  * 24 pt centred title, 11 pt author block spanning one column
  * 9 pt bold Abstract + 9 pt italic Index Terms
  * roman-numeral small-caps section heads, "A." italic sub-heads
  * tables and the figure placeholder span both columns (1-col sections)

The abstract, index terms and author block are written here (the source
Markdown has none); everything else is transformed from REPORT.md.
"""
import os
import re
from docx import Document
from docx.shared import Pt, RGBColor, Mm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]

AUTHORS = [
    "[TEAM \u2014 full names and matriculation numbers]",
    "CT3201 Artificial Intelligence, School of Computer Science and Engineering",
    "Nanyang Technological University, Singapore",
]

ABSTRACT = (
    "Emergency evacuation of a burning building is a decision problem: a rescuer "
    "with only local visibility must repeatedly choose which trapped occupant to "
    "reach next, and by what route, while fire, smoke and structural collapse "
    "close paths over time. This paper describes Pyro Pete: Emergency Evacuation, "
    "a playable Pygame simulation built for the CT3201 \u201cLearn with AI\u201d "
    "mini project, in which an autonomous rescue agent solves that problem "
    "alongside a human player under identical rules. We formulated the rescuer as "
    "a goal-based agent performing graph search over a grid whose tiles carry "
    "hazard-weighted costs, and used a generative AI assistant (Claude) to "
    "challenge that formulation rather than to design it. AI-prompted critique "
    "moved the design from unweighted breadth-first search with fire treated as a "
    "wall to a hazard-weighted A* agent that plans under partial observability "
    "and re-plans as the environment changes, and surfaced robustness gaps we "
    "then closed. We tested one concrete AI recommendation \u2014 that Greedy "
    "Best-First search would be preferable because it expands fewer nodes \u2014 "
    "with a purpose-built comparison harness, found it inappropriate for a safety "
    "objective, and rejected it with quantitative evidence. We report the "
    "accept / modify / reject decisions, their verification, and a "
    "responsible-AI assessment of deploying such a system."
)

INDEX_TERMS = (
    "heuristic search, A* algorithm, intelligent agents, path planning, "
    "decision-making under uncertainty, human-AI collaboration, responsible AI"
)

ACCENT = RGBColor(0, 0, 0)
GREY = "D9D9D9"


# --------------------------------------------------------------------------- #
#  low-level helpers                                                           #
# --------------------------------------------------------------------------- #
def set_cols(section, num, space_twips=720):
    sectPr = section._sectPr
    cols = sectPr.find(qn("w:cols"))
    if cols is None:
        cols = OxmlElement("w:cols")
        sectPr.append(cols)
    cols.set(qn("w:num"), str(num))
    cols.set(qn("w:space"), str(space_twips))
    cols.set(qn("w:equalWidth"), "1")


def apply_page(section):
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = Pt(36)
    section.bottom_margin = Pt(54)
    section.left_margin = Pt(45)
    section.right_margin = Pt(45)
    section.header_distance = Pt(28)
    section.footer_distance = Pt(28)


def cell_bg(cell, hexc):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hexc)
    tcPr.append(shd)


def fixed_layout(table):
    lay = OxmlElement("w:tblLayout")
    lay.set(qn("w:type"), "fixed")
    table._tbl.tblPr.append(lay)


def runs(paragraph, text, size, bold=False, italic=False, bold_as_italic=False):
    text = text.replace("~~", "").replace("\\*", "\u2217").replace("\\`", "`")
    text = re.sub(r"\\([\[\]()#_.\-])", r"\1", text)
    parts = re.split(r"(\*\*[^*]+\*\*|(?<!\w)\*[^*\n]+\*(?!\w)|`[^`]+`)", text)
    for part in parts:
        if not part:
            continue
        b, i, mono = bold, italic, False
        if part.startswith("**") and part.endswith("**"):
            part = part[2:-2]
            if bold_as_italic:
                i = True
            else:
                b = True
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            part, i = part[1:-1], True
        elif part.startswith("`") and part.endswith("`"):
            part, mono = part[1:-1], True
        r = paragraph.add_run(part)
        r.bold, r.italic = b, i
        r.font.size = Pt(size - 1 if mono else size)
        r.font.name = "Consolas" if mono else "Times New Roman"


# --------------------------------------------------------------------------- #
#  document builder                                                            #
# --------------------------------------------------------------------------- #
class Builder:
    def __init__(self):
        self.doc = Document()
        st = self.doc.styles["Normal"]
        st.font.name = "Times New Roman"
        st.font.size = Pt(10)
        st.paragraph_format.space_after = Pt(0)
        apply_page(self.doc.sections[0])
        self.cur_cols = 1                     # section 0 = title band
        self.sec_cols = {0: 1}

    # -- column-span management -------------------------------------------- #
    def ensure(self, cols):
        if cols == self.cur_cols:
            return
        idx = len(self.doc.sections) - 1
        self.sec_cols[idx] = self.cur_cols
        self.doc.add_section(WD_SECTION.CONTINUOUS)
        apply_page(self.doc.sections[-1])
        self.cur_cols = cols

    def finish(self):
        self.sec_cols[len(self.doc.sections) - 1] = self.cur_cols
        for i, n in self.sec_cols.items():
            set_cols(self.doc.sections[i], n)

    # -- block emitters --------------------------------------------------- #
    def para(self, text, size=10, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
             indent=True, before=0, after=4, bold=False, italic=False,
             keep=False):
        self.ensure(2)
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.alignment = align
        pf.space_before = Pt(before)
        pf.space_after = Pt(after)
        pf.line_spacing = 1.0
        if indent:
            pf.first_line_indent = Pt(14.4)
        if keep:
            pf.keep_with_next = True
        runs(p, text, size, bold=bold, italic=italic, bold_as_italic=True)
        return p

    def bullet(self, text, size=10):
        self.ensure(2)
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf.left_indent = Pt(18)
        pf.first_line_indent = Pt(-9)
        pf.space_after = Pt(2)
        pf.line_spacing = 1.0
        runs(p, "\u2022\u2003" + text, size, bold_as_italic=True)

    def numbered(self, n, text, size=10):
        self.ensure(2)
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf.left_indent = Pt(22)
        pf.first_line_indent = Pt(-22)
        pf.space_after = Pt(3)
        pf.line_spacing = 1.0
        r = p.add_run("%d)\u2003" % n)
        r.bold = True
        r.font.size = Pt(size)
        r.font.name = "Times New Roman"
        runs(p, text, size)

    def h1(self, n, text):
        self.ensure(2)
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf.space_before = Pt(12)
        pf.space_after = Pt(4)
        pf.keep_with_next = True
        label = ("%s.\u2003%s" % (ROMAN[n], text.upper())) if n is not None else text.upper()
        r = p.add_run(label)
        r.font.size = Pt(10)
        r.font.name = "Times New Roman"
        r.font.small_caps = True

    def h2(self, letter, text):
        self.ensure(2)
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_before = Pt(6)
        pf.space_after = Pt(3)
        pf.keep_with_next = True
        r = p.add_run("%s.\u2003" % letter)
        r.italic = True
        r.font.size = Pt(10)
        r.font.name = "Times New Roman"
        runs(p, text, 10, italic=True)

    def table_caption(self, roman, text):
        self.ensure(1)
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf.space_before = Pt(10)
        pf.space_after = Pt(3)
        pf.keep_with_next = True
        r = p.add_run("TABLE %s.\u2003" % roman)
        r.font.size = Pt(8)
        r.font.name = "Times New Roman"
        r2 = p.add_run(text.upper())
        r2.font.size = Pt(8)
        r2.font.name = "Times New Roman"
        r2.font.small_caps = True

    def table(self, rows):
        self.ensure(1)
        rows = [r for r in rows if not all(set(c) <= set("-: ") for c in r)]
        ncol = max(len(r) for r in rows)
        usable = 505  # pt, page width minus margins for a 1-col section
        w = [1.0] * ncol
        if rows[0] and rows[0][0].strip() in ("#", "No", "No.", "Element",
                                              "Dimension", "Section", "Topic",
                                              "strategy"):
            w[0] = 0.5
        w[-1] = 1.7
        if ncol >= 3:
            w[-2] = 1.15
        tot = sum(w)
        widths = [Pt(usable * x / tot) for x in w]

        t = self.doc.add_table(rows=len(rows), cols=ncol)
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        fixed_layout(t)
        for ri, row in enumerate(rows):
            for ci in range(ncol):
                cell = t.cell(ri, ci)
                cell.width = widths[ci]
                cell.text = ""
                p = cell.paragraphs[0]
                p.paragraph_format.space_after = Pt(1)
                p.paragraph_format.line_spacing = 1.0
                p.alignment = (WD_ALIGN_PARAGRAPH.CENTER if ri == 0
                               else WD_ALIGN_PARAGRAPH.LEFT)
                runs(p, row[ci] if ci < len(row) else "", 8,
                     bold=(ri == 0))
                if ri == 0:
                    cell_bg(cell, GREY)
        for ci in range(ncol):
            t.columns[ci].width = widths[ci]
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)

    def figure_placeholder(self, lines):
        self.ensure(1)
        box = self.doc.add_paragraph()
        box.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        box.paragraph_format.left_indent = Pt(18)
        box.paragraph_format.space_after = Pt(2)
        for j, ln in enumerate(lines):
            r = box.add_run(("" if j == 0 else "\n") + ln)
            r.font.name = "Consolas"
            r.font.size = Pt(8)
        cap = self.doc.add_paragraph()
        cap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.space_before = Pt(3)
        cap.paragraph_format.space_after = Pt(8)
        r = cap.add_run("Fig. 1.\u2003The rescue agent's sense\u2013decide\u2013act "
                        "loop. The agent re-runs this cycle roughly four times a "
                        "second and whenever the world changes.")
        r.font.size = Pt(8)
        r.font.name = "Times New Roman"


# --------------------------------------------------------------------------- #
#  markdown -> builder                                                         #
# --------------------------------------------------------------------------- #
def build(md_path, out_path):
    lines = open(md_path, encoding="utf-8").read().splitlines()
    b = Builder()
    doc = b.doc

    # --- title band (section 0, one column) ------------------------------ #
    tp = doc.add_paragraph()
    tp.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tp.paragraph_format.space_after = Pt(6)
    r = tp.add_run("Pyro Pete: Emergency Evacuation \u2014 Designing an "
                   "Evacuation-Routing AI Agent with AI Assistance")
    r.font.size = Pt(20)
    r.font.name = "Times New Roman"

    for i, ln in enumerate(AUTHORS):
        ap = doc.add_paragraph()
        ap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        ap.paragraph_format.space_before = Pt(10 if i == 0 else 0)
        ap.paragraph_format.space_after = Pt(2)
        rr = ap.add_run(ln)
        rr.font.size = Pt(11 if i == 0 else 9)
        rr.font.name = "Times New Roman"
        rr.italic = i > 0

    # --- abstract + index terms (now in 2-col body) -------------------- #
    b.ensure(2)
    ap = doc.add_paragraph()
    ap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    ap.paragraph_format.first_line_indent = Pt(13.6)
    ap.paragraph_format.space_after = Pt(6)
    ap.paragraph_format.line_spacing = 1.0
    r = ap.add_run("Abstract\u2014")
    r.bold = True
    r.italic = True
    r.font.size = Pt(9)
    r.font.name = "Times New Roman"
    r = ap.add_run(ABSTRACT)
    r.bold = True
    r.font.size = Pt(9)
    r.font.name = "Times New Roman"

    kp = doc.add_paragraph()
    kp.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    kp.paragraph_format.first_line_indent = Pt(13.6)
    kp.paragraph_format.space_after = Pt(10)
    kp.paragraph_format.line_spacing = 1.0
    r = kp.add_run("Index Terms\u2014")
    r.bold = True
    r.italic = True
    r.font.size = Pt(9)
    r.font.name = "Times New Roman"
    r = kp.add_run(INDEX_TERMS)
    r.italic = True
    r.font.size = Pt(9)
    r.font.name = "Times New Roman"

    # --- walk the markdown -------------------------------------------- #
    h1_i = -1
    h2_i = 0
    table_i = 0
    last_heading = "results"
    i = 0
    in_fence = False
    fence_lang = ""
    fence_buf = []

    while i < len(lines):
        raw = lines[i]
        s = raw.strip()

        if s.startswith("```"):
            if in_fence:
                if fence_lang == "mermaid":
                    b.figure_placeholder(_mermaid_to_text())
                in_fence = False
                fence_buf = []
            else:
                in_fence = True
                fence_lang = s[3:].strip().lower()
                fence_buf = []
            i += 1
            continue
        if in_fence:
            fence_buf.append(raw)
            i += 1
            continue

        if not s or s == "---":
            i += 1
            continue
        if s.startswith(">"):                       # drop meta blockquotes
            i += 1
            continue
        if s.startswith("# "):                      # doc title already set
            i += 1
            continue
        if re.match(r"^\*\*(Project|Problem area):\*\*", s):   # front-matter
            i += 1
            continue

        if s.startswith("## "):
            txt = s[3:]
            txt = re.sub(r"\s*\*\(.*?\)\*\s*$", "", txt)       # strip phase note
            txt = re.sub(r"^Section\s+\d+\s*[\u2014-]\s*", "", txt)
            if re.match(r"^Appendix", txt):
                txt = "Appendix: " + re.sub(r"^Appendix\s*[\u2014-]\s*", "", txt)
                b.h1(None, txt)
            else:
                h1_i += 1
                b.h1(h1_i, txt)
            h2_i = 0
            last_heading = re.sub(r"^Appendix:\s*", "", txt)
            i += 1
            continue

        if s.startswith("### "):
            txt = s[4:]
            txt = re.sub(r"\s*\*\(.*?\)\*\s*$", "", txt)
            h2_i += 1
            b.h2(chr(ord("A") + h2_i - 1), txt)
            last_heading = txt
            i += 1
            continue

        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells)
                i += 1
            table_i += 1
            b.table_caption(ROMAN[table_i - 1], last_heading)
            b.table(rows)
            continue

        m = re.match(r"^(\d+)\.\s+(.*)", s)
        if m:
            b.numbered(int(m.group(1)), m.group(2))
            i += 1
            continue

        if re.match(r"^[-*]\s+", s):
            b.bullet(re.sub(r"^[-*]\s+", "", s))
            i += 1
            continue

        # plain paragraph: join wrapped lines
        buf = [s]
        i += 1
        while i < len(lines):
            nx = lines[i].strip()
            if (not nx or nx.startswith(("#", "|", ">", "```", "---", "- ", "* "))
                    or re.match(r"^\d+\.\s+", nx)):
                break
            buf.append(nx)
            i += 1
        b.para(" ".join(buf))

    b.finish()
    doc.save(out_path)
    print("wrote", out_path, "-", len(doc.sections), "sections")


def _mermaid_to_text():
    return [
        "sense  : cells + occupants within the vision radius",
        "   |",
        "goal   : nearest KNOWN waiting occupant   (weighted distance)",
        "         else nearest unexplored frontier cell",
        "         else the exit",
        "         (fetch the key first if a locked door blocks the goal)",
        "   |",
        "plan   : hazard-weighted A* route to the goal",
        "   |",
        "act    : step one cell along the route",
        "   |",
        "revise : world changed (fire / collapse / door)?  -> re-plan",
        "         every 0.25 s regardless",
    ]


if __name__ == "__main__":
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "docs", "report")
    build(os.path.join(base, "REPORT.md"),
          os.path.join(base, "CT3201_Report_IEEE.docx"))
