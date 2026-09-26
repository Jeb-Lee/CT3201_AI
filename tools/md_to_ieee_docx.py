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

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV",
         "XVI", "XVII", "XVIII", "XIX", "XX", "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII", "XXVIII"]

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

ABSTRACT_REV2 = ABSTRACT + (
    " In this revision we also report a second, optional brain for the same agent: a neural network."
    " Reinforcement learning from the game score alone never rescued anyone (0% of episodes fully"
    " evacuated; the network learned to stand still), so we changed the question to imitation of A*"
    " with behaviour cloning and DAgger. Correcting our own information-parity assumption, adding a"
    " memory of the agent's own path and changing the search order it imitates took the network from"
    " 20% (first version) to 84% (final version, on 300 fresh episodes) of stages fully evacuated, against 85% for A* itself: a"
    " difference we cannot tell from noise, although the network still trails A* on stages it never"
    " trained on (73% against 87%)."
)

INDEX_TERMS_REV2 = INDEX_TERMS + ", reinforcement learning, imitation learning, behaviour cloning, DAgger"

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
        r2 = p.add_run(text.replace("\\*", "∗").upper())
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

    def figure(self, path, caption, wide=False):
        """A real picture with its own "Fig. N." caption (numbering continues after the
        hard-coded Fig. 1). Wide figures span both columns."""
        self.fig_no = getattr(self, "fig_no", 1) + 1
        self.ensure(1 if wide else 2)
        p = self.doc.add_paragraph()
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        p.add_run().add_picture(path, width=Pt(500 if wide else 232))
        cap = self.doc.add_paragraph()
        cap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY if not wide else WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.space_after = Pt(8)
        r = cap.add_run("Fig. %d. " % self.fig_no)
        r.font.size = Pt(8)
        r.font.name = "Times New Roman"
        runs(cap, caption, 8)

    def reference(self, text):
        self.ensure(2)
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf.left_indent = Pt(20)
        pf.first_line_indent = Pt(-20)
        pf.space_after = Pt(2)
        pf.line_spacing = 1.0
        runs(p, text, 8)

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
#  revision 3 layout: real heading styles, tables that suit two columns        #
# --------------------------------------------------------------------------- #
COL_W = 234.5       # pt: one column, (505 - 36) / 2
FULL_W = 505        # pt: both columns (page width minus margins)


def _plain_style(style, size, italic=False, small_caps=False):
    """Times New Roman, black, not bold, whatever the template's theme said."""
    f = style.font
    f.name = "Times New Roman"
    f.size = Pt(size)
    f.bold = False
    f.italic = italic
    f.small_caps = small_caps
    f.color.rgb = RGBColor(0, 0, 0)
    rpr = style.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is not None:                      # theme fonts would override the name above
        for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            fonts.attrib.pop(qn(a), None)
    color = rpr.find(qn("w:color"))
    if color is not None:
        for a in ("w:themeColor", "w:themeShade", "w:themeTint"):
            color.attrib.pop(qn(a), None)


def _border(parent, tag, edges, val="single", sz="4"):
    box = parent.find(qn(tag))
    if box is None:
        box = OxmlElement(tag)
        parent.append(box)
    for edge in edges:
        e = OxmlElement("w:" + edge)
        e.set(qn("w:val"), val)
        if val != "nil":
            e.set(qn("w:sz"), sz)
            e.set(qn("w:space"), "0")
            e.set(qn("w:color"), "000000")
        box.append(e)


def _cell_margins(table, left=57, right=57):
    mar = OxmlElement("w:tblCellMar")
    for edge, w in (("left", left), ("right", right), ("top", 0), ("bottom", 0)):
        e = OxmlElement("w:" + edge)
        e.set(qn("w:w"), str(w))
        e.set(qn("w:type"), "dxa")
        mar.append(e)
    table._tbl.tblPr.append(mar)


def _table_width(table, width_pt):
    tblPr = table._tbl.tblPr
    for old in tblPr.findall(qn("w:tblW")):
        tblPr.remove(old)
    w = OxmlElement("w:tblW")
    w.set(qn("w:w"), str(int(width_pt * 20)))
    w.set(qn("w:type"), "dxa")
    tblPr.append(w)


def _float_to_top(table):
    """Take the table out of the text flow and pin it to the top of the page its anchor paragraph is
    on, across both columns; the text of both columns flows underneath (IEEE's table*/figure*)."""
    pp = OxmlElement("w:tblpPr")
    for k, v in dict(leftFromText="0", rightFromText="0", topFromText="0", bottomFromText="200",
                     vertAnchor="margin", horzAnchor="margin", tblpXSpec="center", tblpYSpec="top").items():
        pp.set(qn("w:" + k), v)
    tblPr = table._tbl.tblPr
    tblPr.insert(0, pp) if tblPr.find(qn("w:tblStyle")) is None else tblPr.find(qn("w:tblStyle")).addnext(pp)
    ov = OxmlElement("w:tblOverlap")
    ov.set(qn("w:val"), "never")
    pp.addnext(ov)


def _no_split(row):
    trPr = row._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:cantSplit"))


def _header_row(row):
    row._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))


def _column_widths(rows, total, size):
    """Share `total` pt between columns by how much text each holds, but never narrower than its
    longest word."""
    ncol = max(len(r) for r in rows)
    clean = lambda s: re.sub(r"[*`\\]", "", s)
    weight, least = [], []
    for c in range(ncol):
        cells = [clean(r[c]) if c < len(r) else "" for r in rows]
        weight.append(min(max(len(x) for x in cells), 70) + 4)
        longest = max((len(w) for x in cells for w in x.split()), default=1)
        least.append(min(longest * size * 0.52 + 7, total / ncol * 1.6))
    widths = [total * w / sum(weight) for w in weight]
    for _ in range(4):                       # lift narrow columns to their minimum, take it from the rest
        short = [i for i in range(ncol) if widths[i] < least[i]]
        if not short:
            break
        need = sum(least[i] - widths[i] for i in short)
        rest = [i for i in range(ncol) if i not in short]
        spare = sum(widths[i] for i in rest)
        for i in short:
            widths[i] = least[i]
        for i in rest:
            widths[i] -= need * widths[i] / spare
    return widths


class FloatBuilder(Builder):
    """Revision 3: Word heading styles (so the Navigation pane and a table of contents work), and
    tables and figures that suit two columns: column-width ones stay in the text and never break,
    full-width ones float to the top of a page across both columns. The body never leaves two
    columns, so no text is squeezed into half-height columns around a table."""

    def __init__(self):
        super().__init__()
        self.fig_no = 0                          # figures are all real pictures now
        st = self.doc.styles
        specs = (("Heading 1", 10, False, True, WD_ALIGN_PARAGRAPH.CENTER, 10, 4, 0),
                 ("Heading 2", 10, True, False, WD_ALIGN_PARAGRAPH.LEFT, 7, 3, 0),
                 ("Heading 3", 10, True, False, WD_ALIGN_PARAGRAPH.LEFT, 4, 2, 14.4),
                 ("Caption", 8, False, False, WD_ALIGN_PARAGRAPH.CENTER, 0, 0, 0))
        for name, size, italic, caps, align, before, after, indent in specs:
            style = st[name]
            _plain_style(style, size, italic=italic, small_caps=caps)
            pf = style.paragraph_format
            pf.alignment = align
            pf.space_before, pf.space_after = Pt(before), Pt(after)
            pf.left_indent, pf.first_line_indent = Pt(indent), Pt(0)
            pf.line_spacing = 1.0
            pf.keep_with_next = name != "Caption"
        self._word_2013_mode()

    def _word_2013_mode(self):
        """Without this Word opens the file in Compatibility Mode (the python-docx template is old)."""
        settings = self.doc.settings.element
        compat = settings.find(qn("w:compat"))
        if compat is None:
            compat = OxmlElement("w:compat")
            settings.append(compat)
        for cs in compat.findall(qn("w:compatSetting")):
            if cs.get(qn("w:name")) == "compatibilityMode":
                compat.remove(cs)
        cs = OxmlElement("w:compatSetting")
        for k, v in (("name", "compatibilityMode"), ("uri", "http://schemas.microsoft.com/office/word"), ("val", "15")):
            cs.set(qn("w:" + k), v)
        compat.append(cs)

    # -- headings --------------------------------------------------------- #
    def h1(self, n, text):
        self.ensure(2)
        p = self.doc.add_paragraph(style="Heading 1")
        runs(p, ("%s. %s" % (ROMAN[n], text)) if n is not None else text, 10)
        for r in p.runs:
            r.font.small_caps = True

    def h2(self, letter, text):
        self.ensure(2)
        p = self.doc.add_paragraph(style="Heading 2")
        runs(p, "%s. %s" % (letter, text), 10, italic=True)

    def h3(self, number, text):
        self.ensure(2)
        p = self.doc.add_paragraph(style="Heading 3")
        runs(p, "%d) %s" % (number, text), 10, italic=True)

    # -- captions --------------------------------------------------------- #
    def _table_caption_into(self, p, roman, text):
        p.style = self.doc.styles["Caption"]
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.keep_with_next = True
        r = p.add_run("TABLE %s" % roman)
        r.font.size = Pt(8)
        r.font.name = "Times New Roman"
        r.add_break()
        runs(p, text, 8)
        for r in p.runs[1:]:
            r.font.small_caps = True

    def _figure_caption_into(self, p, text):
        p.style = self.doc.styles["Caption"]
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(8)
        r = p.add_run("Fig. %d. " % self.fig_no)
        r.font.size = Pt(8)
        r.font.name = "Times New Roman"
        runs(p, text, 8)

    def _anchor(self):
        """A 1-pt paragraph after a table: a floating table needs one to hang from, and two tables
        with nothing between them would merge into one."""
        p = self.doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = Pt(1)
        r = p.add_run("")
        r.font.size = Pt(1)
        return p

    # -- tables ----------------------------------------------------------- #
    def ieee_table(self, rows, roman, caption, wide=False):
        self.ensure(2)
        rows = [r for r in rows if not all(set(c) <= set("-: ") for c in r)]
        ncol = max(len(r) for r in rows)
        size = 8 if wide else 7.5
        total = FULL_W if wide else COL_W
        widths = _column_widths(rows, total, size)
        extra = 1 if wide else 0                 # a floating table carries its caption as a first row
        if not wide:
            self._table_caption_into(self.doc.add_paragraph(), roman, caption)
        t = self.doc.add_table(rows=len(rows) + extra, cols=ncol)
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        fixed_layout(t)
        _table_width(t, total)
        _cell_margins(t)
        if wide:
            cap = t.cell(0, 0).merge(t.cell(0, ncol - 1)) if ncol > 1 else t.cell(0, 0)
            cap.text = ""
            self._table_caption_into(cap.paragraphs[0], roman, caption)
            _border(cap._tc.get_or_add_tcPr(), "w:tcBorders", ("top", "left", "right", "bottom"), val="nil")
            _float_to_top(t)
        for ri, row in enumerate(rows):
            tr = t.rows[ri + extra]
            _no_split(tr)
            if ri == 0:
                _header_row(tr)
            for ci in range(ncol):
                cell = t.cell(ri + extra, ci)
                cell.width = Pt(widths[ci])
                cell.text = ""
                p = cell.paragraphs[0]
                p.paragraph_format.space_after = Pt(1)
                p.paragraph_format.line_spacing = 1.0
                # keep a column table in one piece: every row holds on to the next
                p.paragraph_format.keep_with_next = (not wide) and ri < len(rows) - 1
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER if ri == 0 else WD_ALIGN_PARAGRAPH.LEFT
                runs(p, row[ci] if ci < len(row) else "", size, bold=(ri == 0))
                if ri == 0:
                    cell_bg(cell, GREY)
                    if wide:
                        _border(cell._tc.get_or_add_tcPr(), "w:tcBorders", ("top",))
        for ci in range(ncol):
            t.columns[ci].width = Pt(widths[ci])
        if wide:
            self._anchor()
        else:
            gap = self.doc.add_paragraph()
            gap.paragraph_format.space_after = Pt(4)
            gap.paragraph_format.line_spacing = Pt(4)

    # -- figures ---------------------------------------------------------- #
    def figure(self, path, caption, wide=False):
        self.fig_no += 1
        self.ensure(2)
        if not wide:
            p = self.doc.add_paragraph()
            p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.keep_with_next = True
            p.add_run().add_picture(path, width=Pt(COL_W - 2))
            self._figure_caption_into(self.doc.add_paragraph(), caption)
            return
        t = self.doc.add_table(rows=2, cols=1)
        t.autofit = False
        fixed_layout(t)
        _table_width(t, FULL_W)
        _cell_margins(t, 0, 0)
        _border(t._tbl.tblPr, "w:tblBorders", ("top", "left", "bottom", "right", "insideH", "insideV"), val="nil")
        _float_to_top(t)
        pic = t.cell(0, 0).paragraphs[0]
        pic.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pic.add_run().add_picture(path, width=Pt(FULL_W - 6))
        self._figure_caption_into(t.cell(1, 0).paragraphs[0], caption)
        for row in t.rows:
            _no_split(row)
        self._anchor()


# --------------------------------------------------------------------------- #
#  markdown -> builder                                                         #
# --------------------------------------------------------------------------- #
def build(md_path, out_path, abstract=ABSTRACT, index_terms=INDEX_TERMS, layout="sections"):
    """layout "sections" (revisions 1-2): a table switches the page to one column around it.
    layout "float" (revision 3): FloatBuilder, heading styles, tables that suit two columns."""
    lines = open(md_path, encoding="utf-8").read().splitlines()
    md_dir = os.path.dirname(os.path.abspath(md_path))
    modern = layout == "float"
    b = FloatBuilder() if modern else Builder()
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
    r = ap.add_run(abstract)
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
    r = kp.add_run(index_terms)
    r.italic = True
    r.font.size = Pt(9)
    r.font.name = "Times New Roman"

    # --- walk the markdown -------------------------------------------- #
    h1_i = -1
    h2_i = 0
    table_i = 0
    last_heading = "results"
    pending_caption = None
    pending_wide = False
    h3_i = 0
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

        m_img = re.match(r"^!\[(.*)\]\((.+?)\)(\{wide\})?$", s)
        if m_img:                                   # ![caption](path){wide}
            b.figure(os.path.join(md_dir, m_img.group(2)), m_img.group(1), wide=bool(m_img.group(3)))
            i += 1
            continue
        if s.startswith("Table: "):                 # caption for the next table
            pending_caption = s[7:].strip()
            pending_wide = pending_caption.endswith("{wide}")
            pending_caption = pending_caption[:-6].strip() if pending_wide else pending_caption
            i += 1
            continue
        m_ref = re.match(r"^\[(\d+)\]\s+(.*)", s)
        if m_ref:                                   # [n] a reference-list entry
            b.reference("[%s] %s" % (m_ref.group(1), m_ref.group(2)))
            i += 1
            continue

        if s.startswith("## "):
            txt = s[3:]
            txt = re.sub(r"\s*\*\(.*?\)\*\s*$", "", txt)       # strip phase note
            txt = re.sub(r"^Section\s+\d+\s*[\u2014-]\s*", "", txt)
            if re.match(r"^References", txt):
                b.h1(None, "References")
            elif re.match(r"^Appendix", txt):
                txt = "Appendix: " + re.sub(r"^Appendix\s*[\u2014-]\s*", "", txt)
                b.h1(None, txt)
            else:
                h1_i += 1
                b.h1(h1_i, txt)
            h2_i = 0
            h3_i = 0
            last_heading = re.sub(r"^Appendix:\s*", "", txt)
            i += 1
            continue

        if modern and s.startswith("#### "):
            h3_i += 1
            b.h3(h3_i, s[5:].strip())
            i += 1
            continue

        if s.startswith("### "):
            txt = s[4:]
            txt = re.sub(r"\s*\*\(.*?\)\*\s*$", "", txt)
            h2_i += 1
            h3_i = 0
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
            if modern:
                b.ieee_table(rows, ROMAN[table_i - 1], pending_caption or last_heading, wide=pending_wide)
            else:
                b.table_caption(ROMAN[table_i - 1], pending_caption or last_heading)
                b.table(rows)
            pending_caption, pending_wide = None, False
            continue

        m = re.match(r"^(\d+)\.\s+(.*)", s)
        if m or re.match(r"^[-*]\s+", s):
            item = [m.group(2) if m else re.sub(r"^[-*]\s+", "", s)]
            i += 1
            while modern and i < len(lines) and lines[i].startswith(("  ", "\t")) and lines[i].strip():
                item.append(lines[i].strip())
                i += 1
            if m:
                b.numbered(int(m.group(1)), " ".join(item))
            else:
                b.bullet(" ".join(item))
            continue

        # plain paragraph: join wrapped lines
        buf = [s]
        i += 1
        while i < len(lines):
            nx = lines[i].strip()
            if (not nx or nx.startswith(("#", "|", ">", "```", "---", "- ", "* ", "![", "Table: "))
                    or re.match(r"^\d+\.\s+", nx) or re.match(r"^\[\d+\]\s", nx)):
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
    import argparse
    ap = argparse.ArgumentParser(description="REPORT.md -> IEEE two-column .docx")
    ap.add_argument("--rev2", action="store_true",
                    help="revision 2: build REPORT_rev2.md (adds the learned-agent section, figures and "
                         "references) into CT3201_Report_IEEE_rev2.docx, with the extended abstract")
    ap.add_argument("--rev3", action="store_true",
                    help="revision 3: build REPORT_rev3.md into CT3201_Report_IEEE_rev3.docx with the two-column "
                         "layout (heading styles, column-width tables, full-width tables and figures at page tops)")
    args = ap.parse_args()
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "report")
    if args.rev3:
        build(os.path.join(base, "REPORT_rev3.md"), os.path.join(base, "CT3201_Report_IEEE_rev3.docx"),
              abstract=ABSTRACT_REV2, index_terms=INDEX_TERMS_REV2, layout="float")
    elif args.rev2:
        build(os.path.join(base, "REPORT_rev2.md"), os.path.join(base, "CT3201_Report_IEEE_rev2.docx"),
              abstract=ABSTRACT_REV2, index_terms=INDEX_TERMS_REV2)
    else:
        build(os.path.join(base, "REPORT.md"), os.path.join(base, "CT3201_Report_IEEE.docx"))
