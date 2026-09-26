"""End-of-run results panel: the human-vs-AI comparison.

Drawn over the frozen game when a run ends (Pete reached the exit, or
died). Two columns -- You vs the AI drone -- over the same wall-clock,
because "how far did the optimal agent get while I was doing that" is the
comparison the project's reflection turns on. The headline number is the
score (see stats.RunStats.score); the breakdown and raw stats below show
where it came from.
"""

import pygame

from hud_icons import BLUE, draw_panel, hint_row_width, key_hint_row
from portraits import draw_portrait
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    RESULTS_TEXT_COLOR, RESULTS_ACCENT_COLOR,
)

_DIM = (172, 172, 178)
_POS = (150, 210, 150)
_NEG = (222, 130, 110)
_AMBER = (240, 178, 64)

# How a rescuer's run ended, in words and in the colour that says whether that
# was good: green got out, red died, amber gave up with people still inside.
_STATUS = {
    "exit": ("reached the exit", _POS),
    "dead": ("did not make it", _NEG),
    "time": ("still searching", _AMBER),
}

# Headline for the race outcome (GameSession.outcome). Falls back to the
# old neutral "Run complete" when no outcome was recorded, so spectate
# runs and any future caller that doesn't track one still render.
_OUTCOME_HEADLINE = {
    "cleared": ("Stage cleared", _POS),
    # alive at the end, but the stage finished without Pete leading anyone out
    "outrun": ("You didn't save anyone", RESULTS_ACCENT_COLOR),
    "died": ("Pete didn't make it", _NEG),
}


# --- layout -----------------------------------------------------------
# One left margin and one right edge for everything in a column, so labels
# line up on the left and every number lines up on the right. (Previously the
# title, subtitle and column each started at a different x, the points and
# stats numbers sat at different distances, and the values were left-aligned
# so their right edges were ragged.)
_MARGIN = 32          # panel edge -> content, both sides
_ROW = 22             # minimum height of one label/value row
_GAP = 40             # between the two columns of the race panel
_SECTION_GAP = 10     # blank space between the score and stats sections
_TOTAL_PAD = 10       # rule + gap above the Total row (rule is 4px in, row 6px below)
_PORTRAIT = 50        # the rescuer's framed face, top-left of its column
_PORTRAIT_GAP = 10    # portrait -> name
_COMPACT_BELOW = 340  # columns narrower than this (the race panel's) get the compact header
_SEP = "  \u00b7  "        # between the subtitle's parts
_INFO_SEP = " \u00b7 "       # tighter, on the header's info line: room is short in a race column


# Vertical spacing comes from the fonts' own heights, not fixed pixel offsets.
# The offsets were tuned for pygame's default font (16px lines) and left a
# taller face (Arial, ~23px lines) cramped: rows touching, the subtitle
# touching the headline. With the default font these work out to exactly the
# old numbers (row 22, first column 86px down, name/reason/score at 0/26/46,
# 78px before the first section), so the fallback layout is unchanged.
def _row_h(body_font):
    return max(_ROW, body_font.get_linesize() + 1)


def _sub_y(title_font):
    """Subtitle's top, relative to the panel: below the headline."""
    return 18 + title_font.get_height() + 6


def _top(title_font, body_font):
    """Panel top -> first column: below the headline and the subtitle."""
    return _sub_y(title_font) + body_font.get_height() + 16


def _head_block(head_font, info_font):
    """(name_y, info_y, height) of a column's header -- portrait, name, and the
    "how it decided / how it ended" line -- relative to the column's top."""
    name_y = 2
    info_y = name_y + head_font.get_height() + 3
    return name_y, info_y, max(_PORTRAIT, info_y + info_font.get_height()) + 16


def _section(surface, body_font, x, right, y, title):
    """A dim heading with a full-width rule under it. Returns the next y."""
    surface.blit(body_font.render(title, True, _DIM), (x, y))
    rule_y = y + body_font.get_height() + 2
    pygame.draw.line(surface, (60, 62, 70), (x, rule_y), (right, rule_y))
    return rule_y + 8


def _row(surface, body_font, x, right, y, label, value, value_colour,
         label_colour=_DIM, font=None):
    """Label at the left edge, value right-aligned to the shared right edge.
    `font` draws the text in something other than body_font (the bold Total);
    the row's height still comes from body_font so the layout is unchanged."""
    f = font or body_font
    surface.blit(f.render(label, True, label_colour), (x, y))
    v = f.render(value, True, value_colour)
    surface.blit(v, (right - v.get_width(), y))
    return y + _row_h(body_font)


def _column_height(head_font, body_font, st, small_font=None):
    """Height _draw_column will use, so a panel can be sized to its content
    instead of a fixed 470px with a dead strip at the bottom."""
    section = body_font.get_height() + 2 + 8
    row = _row_h(body_font)
    return (_head_block(head_font, small_font or body_font)[2]
            + section + len(st.score_breakdown()) * row
            + _TOTAL_PAD + row
            + _SECTION_GAP
            + section + len(st.summary_rows()) * row)


def _info_parts(font, role, status, colour, avail):
    """The header's second line as (text, colour) pieces: "role \u00b7 status"
    with the status coloured. When that is wider than `avail` the role is the
    part that gives way -- how it ended matters more than how it decided."""
    if status and font.size(role + _INFO_SEP + status)[0] <= avail:
        return [(role, _DIM), (_INFO_SEP, _DIM), (status, colour)]
    if status:
        return [(status, colour)]
    return [(role, _DIM)]


def _draw_header(surface, x, top_y, width, st, head_font, small_font, title_font):
    """Portrait, name, "role \u00b7 outcome", and the score.

    Colour says who it is, the same as in the HUD: gold for Pete, blue for the
    AI. A wide column (Watch AI Play) puts a big score with a POINTS caption on
    the right; a narrow one (the race panel's two columns) shares the name's
    line with a smaller score, so nothing collides."""
    right = x + width
    you = st.kind == "you"
    accent = RESULTS_ACCENT_COLOR if you else BLUE
    draw_portrait(surface, pygame.Rect(x, top_y, _PORTRAIT, _PORTRAIT),
                  "pete" if you else st.kind, accent)
    nx = x + _PORTRAIT + _PORTRAIT_GAP
    name_y, info_y, _ = _head_block(head_font, small_font)
    surface.blit(head_font.render(st.display_name, True, accent), (nx, top_y + name_y))

    score = str(st.score)
    if width >= _COMPACT_BELOW:
        num = (title_font or head_font).render(score, True, RESULTS_TEXT_COLOR)
        cap = small_font.render("POINTS", True, _DIM)
        surface.blit(num, (right - num.get_width(), top_y - 2))
        surface.blit(cap, (right - cap.get_width(), top_y - 2 + num.get_height() - 2))
        reserved = max(num.get_width(), cap.get_width()) + 12      # the info line stops short of it
    else:
        num = head_font.render(score, True, RESULTS_TEXT_COLOR)
        surface.blit(num, (right - num.get_width(), top_y + name_y))
        reserved = 0                                                # it sits below the score
    status, colour = _STATUS.get(st.finished_reason, ("", _DIM))
    px = nx
    for text, c in _info_parts(small_font, st.role, status, colour, right - nx - reserved):
        img = small_font.render(text, True, c)
        surface.blit(img, (px, top_y + info_y))
        px += img.get_width()


def _draw_column(surface, head_font, body_font, x, top_y, width, st, total_font=None,
                 title_font=None, small_font=None):
    right = x + width
    small = small_font or body_font
    _draw_header(surface, x, top_y, width, st, head_font, small, title_font)
    head_h = _head_block(head_font, small)[2]

    y = _section(surface, body_font, x, right, top_y + head_h, "SCORE")
    for label, pts in st.score_breakdown():
        # green is for points actually earned and red for penalties; a zero
        # row ("Occupants led out x0  +0") is neither
        colour = _POS if pts > 0 else _NEG if pts < 0 else _DIM
        y = _row(surface, body_font, x, right, y, label, f"{pts:+d}", colour)

    # The rows above are what the total is made of. Rule + Total makes the sum
    # visible; when damage drove it below zero the score is held at 0, so the
    # label says so rather than leaving rows that add to -40 above a "0".
    # It is the one row set in bold (label and value, full white): it is the
    # number everything above adds up to, and at regular weight it read as just
    # another row that the eye had to hunt for.
    pygame.draw.line(surface, (60, 62, 70), (x, y + 4), (right, y + 4))
    y = _row(surface, body_font, x, right, y + _TOTAL_PAD,
             "Total (min 0)" if st.score_floored else "Total",
             str(st.score), RESULTS_TEXT_COLOR,
             label_colour=RESULTS_TEXT_COLOR, font=total_font)

    y += _SECTION_GAP
    y = _section(surface, body_font, x, right, y, "RUN STATS")
    for label, value in st.summary_rows():
        y = _row(surface, body_font, x, right, y, label, value, RESULTS_TEXT_COLOR)
    return y


def _subtitle(stage_label, total):
    """"Stage 1/10 \u00b7 Ground Floor \u00b7 3 occupants" -- dots, as in the HUD,
    rather than hyphens; "1 occupant", not "1 occupants"."""
    people = f"{total} occupant" + ("" if total == 1 else "s")
    parts = ([stage_label.replace(" - ", _SEP)] if stage_label else []) + [people]
    return _SEP.join(parts)


def _fit_panel_width(*needed, minimum=420):
    """Width for a panel whose widest content line needs `needed` pixels:
    never narrower than `minimum`, never wider than the screen."""
    return min(max(minimum, *needed), SCREEN_WIDTH - 20)


def _draw_heading(surface, title_font, headline, colour, sub_surf, px, py, panel_w):
    """Headline and subtitle, centred on the panel like the verdict and hint
    at the bottom -- they used to be left-aligned, so the panel mixed the two."""
    h = title_font.render(headline, True, colour)
    surface.blit(h, (px + (panel_w - h.get_width()) // 2, py + 18))
    surface.blit(sub_surf, (px + (panel_w - sub_surf.get_width()) // 2,
                            py + _sub_y(title_font)))


def _draw_panel(surface, px, py, panel_w, panel_h):
    shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 160))
    surface.blit(shade, (0, 0))
    draw_panel(surface, pygame.Rect(px, py, panel_w, panel_h), accent=RESULTS_ACCENT_COLOR,
               radius=12, alpha=240)


def _hint_items(cleared, has_next, finale):
    """What the foot of a results panel says the keys do: (message, [(key, label)]).

    One name per key in both modes (one key used to be described three different
    ways, sentence-style). After a clear R replays the stage; after a loss it
    tries again; on the last stage a message (`finale`) says so and Enter goes
    to the menu."""
    if cleared and has_next:
        return None, [("Enter", "Next stage"), ("R", "Replay"), ("Esc", "Quit")]
    if cleared:
        return finale, [("Enter", "Menu"), ("R", "Replay"), ("Esc", "Quit")]
    return None, [("R", "Try again"), ("Enter", "Menu"), ("Esc", "Quit")]


def _hint_block(cleared, has_next, finale, body_font, chip_font):
    """(items, message surface or None, width, height) of the hint area."""
    message, items = _hint_items(cleared, has_next, finale)
    msg = body_font.render(message, True, RESULTS_ACCENT_COLOR) if message else None
    width = max(hint_row_width(items, chip_font, body_font), msg.get_width() if msg else 0)
    height = 30 + (msg.get_height() + 6 if msg else 0)
    return items, msg, width, height


def _draw_hints(surface, block, body_font, chip_font, cx, y):
    """Draw a hint block whose top is `y`, centred on `cx`."""
    items, msg, _, _ = block
    if msg:
        surface.blit(msg, msg.get_rect(midtop=(cx, y)))
        y += msg.get_height() + 6
    key_hint_row(surface, items, chip_font, body_font, cx, y + 15)


def draw_results(surface, title_font, head_font, body_font,
                 player_stats, agent_stats, total_victims,
                 outcome=None, stage_label=None, has_next_stage=False,
                 total_font=None, small_font=None):
    sub_surf = body_font.render(_subtitle(stage_label, total_victims), True, _DIM)

    verdict = _verdict(player_stats, agent_stats)
    v = head_font.render(verdict, True, RESULTS_TEXT_COLOR)
    chip_font = total_font or body_font
    hints = _hint_block(outcome == "cleared", has_next_stage, "You finished the last stage!",
                        body_font, chip_font)

    panel_w = _fit_panel_width(sub_surf.get_width() + 2 * _MARGIN,
                               v.get_width() + 2 * _MARGIN,
                               hints[2] + 40, minimum=660)
    col_w = (panel_w - 2 * _MARGIN - _GAP) // 2
    top = _top(title_font, body_font)
    col_h = max(_column_height(head_font, body_font, player_stats, small_font),
                _column_height(head_font, body_font, agent_stats, small_font))
    # columns, then the verdict, then the hint -- panel is as tall as that
    panel_h = top + col_h + 16 + v.get_height() + 14 + hints[3] + 18
    px = (SCREEN_WIDTH - panel_w) // 2
    py = (SCREEN_HEIGHT - panel_h) // 2
    _draw_panel(surface, px, py, panel_w, panel_h)

    headline, headline_colour = _OUTCOME_HEADLINE.get(
        outcome, ("Run complete", RESULTS_TEXT_COLOR))
    _draw_heading(surface, title_font, headline, headline_colour, sub_surf,
                  px, py, panel_w)

    for i, st in enumerate((player_stats, agent_stats)):
        x = px + _MARGIN + i * (col_w + _GAP)
        _draw_column(surface, head_font, body_font, x, py + top, col_w, st, total_font,
                     title_font, small_font)
    # a thin rule down the gutter so the two columns read as two blocks
    mid = px + _MARGIN + col_w + _GAP // 2
    pygame.draw.line(surface, (60, 62, 70), (mid, py + top + 4),
                     (mid, py + top + col_h - 4))

    vy = py + top + col_h + 16
    surface.blit(v, (px + (panel_w - v.get_width()) // 2, vy))
    _draw_hints(surface, hints, body_font, chip_font, px + panel_w // 2,
                vy + v.get_height() + 14)


def draw_watch_results(surface, title_font, head_font, body_font, agent_stats,
                       total_victims, stage_label=None, cleared=False,
                       has_next_stage=False, total_font=None, small_font=None):
    """Single-column variant for spectate ("Watch AI Play") runs -- same
    panel language as draw_results, just one column since there's no Pete
    to compare against."""
    sub_surf = body_font.render(_subtitle(stage_label, total_victims), True, _DIM)

    chip_font = total_font or body_font
    hints = _hint_block(cleared, has_next_stage, "Campaign complete!", body_font, chip_font)

    # The subtitle carries the stage name, so its length varies per stage
    # ("Turbine Hall" vs "Staff Canteen"). A fixed panel let it spill out the
    # right-hand side; size the panel to the widest line instead, never
    # narrower than the original design and never wider than the screen.
    headline, headline_colour = (
        ("The AI cleared the stage", _POS) if cleared else ("The AI didn't make it", _NEG))
    headline_w = title_font.size(headline)[0]
    panel_w = _fit_panel_width(sub_surf.get_width() + 2 * _MARGIN, hints[2] + 40,
                               headline_w + 2 * _MARGIN)
    top = _top(title_font, body_font)
    col_h = _column_height(head_font, body_font, agent_stats, small_font)
    panel_h = top + col_h + 16 + hints[3] + 18
    px = (SCREEN_WIDTH - panel_w) // 2
    py = (SCREEN_HEIGHT - panel_h) // 2
    _draw_panel(surface, px, py, panel_w, panel_h)

    _draw_heading(surface, title_font, headline, headline_colour, sub_surf,
                  px, py, panel_w)

    _draw_column(surface, head_font, body_font, px + _MARGIN, py + top,
                 panel_w - 2 * _MARGIN, agent_stats, total_font, title_font, small_font)

    _draw_hints(surface, hints, body_font, chip_font, px + panel_w // 2, py + top + col_h + 16)


def _verdict(p, a):
    """Names the opponent the way its heading does ("AI Robot", "AI Drone"),
    so a run with the robot skin doesn't report being beaten by the drone and
    the panel never spells the same rescuer two ways."""
    if p.score > a.score:
        return f"You beat {a.display_name}  ({p.score} vs {a.score})"
    if a.score > p.score:
        return f"{a.display_name} beat you  ({a.score} vs {p.score})"
    if p.score == 0:
        # Both on nothing is a tie only arithmetically. Calling it a dead
        # heat reads as a photo finish, and sits directly under a
        # headline that has just said Pete didn't make it.
        return "Nobody got out"
    return f"Dead heat  ({p.score} each)"
