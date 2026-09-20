"""End-of-run results panel: the human-vs-AI comparison.

Drawn over the frozen game when a run ends (Pete reached the exit, or
died). Two columns -- You vs the AI drone -- over the same wall-clock,
because "how far did the optimal agent get while I was doing that" is the
comparison the project's reflection turns on. The headline number is the
score (see stats.RunStats.score); the breakdown and raw stats below show
where it came from.
"""

import pygame

from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    RESULTS_PANEL_COLOR, RESULTS_TEXT_COLOR, RESULTS_ACCENT_COLOR,
)

_REASON_TEXT = {
    "exit": "reached the exit",
    "dead": "did not make it",
    "time": "still searching",
}
_DIM = (172, 172, 178)
_POS = (150, 210, 150)
_NEG = (222, 130, 110)

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


def _head_block(head_font, body_font):
    """(reason_y, score_y, height) of a column's name / reason / big-score
    block, relative to the column's top."""
    reason_y = head_font.get_height() + 6
    score_y = reason_y + body_font.get_height() + 4
    return reason_y, score_y, score_y + head_font.get_height() + 12


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


def _column_height(head_font, body_font, st):
    """Height _draw_column will use, so a panel can be sized to its content
    instead of a fixed 470px with a dead strip at the bottom."""
    section = body_font.get_height() + 2 + 8
    row = _row_h(body_font)
    return (_head_block(head_font, body_font)[2]
            + section + len(st.score_breakdown()) * row
            + _TOTAL_PAD + row
            + _SECTION_GAP
            + section + len(st.summary_rows()) * row)


def _draw_column(surface, head_font, body_font, x, top_y, width, st, total_font=None):
    right = x + width
    reason_y, score_y, head_h = _head_block(head_font, body_font)
    surface.blit(head_font.render(st.label, True, RESULTS_ACCENT_COLOR), (x, top_y))
    reason = _REASON_TEXT.get(st.finished_reason, "")
    if reason:
        surface.blit(body_font.render(reason, True, _DIM), (x, top_y + reason_y))
    surface.blit(head_font.render(str(st.score), True, RESULTS_TEXT_COLOR),
                 (x, top_y + score_y))

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
    panel = pygame.Rect(px, py, panel_w, panel_h)
    pygame.draw.rect(surface, RESULTS_PANEL_COLOR, panel, border_radius=10)
    pygame.draw.rect(surface, RESULTS_ACCENT_COLOR, panel, 2, border_radius=10)


def draw_results(surface, title_font, head_font, body_font,
                 player_stats, agent_stats, total_victims,
                 outcome=None, stage_label=None, has_next_stage=False,
                 total_font=None):
    sub = f"{total_victims} occupants in the building"
    if stage_label:
        sub = f"{stage_label}  --  {sub}"
    sub_surf = body_font.render(sub, True, _DIM)

    verdict = _verdict(player_stats, agent_stats)
    v = head_font.render(verdict, True, RESULTS_TEXT_COLOR)
    if outcome == "cleared" and has_next_stage:
        hint_text = "Enter for the next stage     R to replay     Esc to quit"
    elif outcome == "cleared":
        hint_text = "You finished the last stage!     Enter for menu     Esc to quit"
    else:
        hint_text = "R to try again     Enter for menu     Esc to quit"
    hint = body_font.render(hint_text, True, (150, 150, 155))

    panel_w = _fit_panel_width(sub_surf.get_width() + 2 * _MARGIN,
                               v.get_width() + 2 * _MARGIN,
                               hint.get_width() + 40, minimum=660)
    col_w = (panel_w - 2 * _MARGIN - _GAP) // 2
    top = _top(title_font, body_font)
    col_h = max(_column_height(head_font, body_font, player_stats),
                _column_height(head_font, body_font, agent_stats))
    # columns, then the verdict, then the hint -- panel is as tall as that
    panel_h = top + col_h + 16 + v.get_height() + 14 + hint.get_height() + 18
    px = (SCREEN_WIDTH - panel_w) // 2
    py = (SCREEN_HEIGHT - panel_h) // 2
    _draw_panel(surface, px, py, panel_w, panel_h)

    headline, headline_colour = _OUTCOME_HEADLINE.get(
        outcome, ("Run complete", RESULTS_TEXT_COLOR))
    _draw_heading(surface, title_font, headline, headline_colour, sub_surf,
                  px, py, panel_w)

    for i, st in enumerate((player_stats, agent_stats)):
        x = px + _MARGIN + i * (col_w + _GAP)
        _draw_column(surface, head_font, body_font, x, py + top, col_w, st, total_font)
    # a thin rule down the gutter so the two columns read as two blocks
    mid = px + _MARGIN + col_w + _GAP // 2
    pygame.draw.line(surface, (60, 62, 70), (mid, py + top + 4),
                     (mid, py + top + col_h - 4))

    vy = py + top + col_h + 16
    surface.blit(v, (px + (panel_w - v.get_width()) // 2, vy))
    surface.blit(hint, (px + (panel_w - hint.get_width()) // 2,
                        vy + v.get_height() + 14))


def draw_watch_results(surface, title_font, head_font, body_font, agent_stats,
                       total_victims, stage_label=None, cleared=False,
                       has_next_stage=False, total_font=None):
    """Single-column variant for spectate ("Watch AI Play") runs -- same
    panel language as draw_results, just one column since there's no Pete
    to compare against."""
    sub = f"{total_victims} occupants in the building"
    if stage_label:
        sub = f"{stage_label}  --  {sub}"
    sub_surf = body_font.render(sub, True, _DIM)

    if cleared and has_next_stage:
        hint_text = "Enter for the next stage     R to replay     Esc to quit"
    elif cleared:
        hint_text = "Campaign complete!     Enter for menu     Esc to quit"
    else:
        hint_text = "R to run again     Enter for menu     Esc to quit"
    hint = body_font.render(hint_text, True, (150, 150, 155))

    # The subtitle carries the stage name, so its length varies per stage
    # ("Turbine Hall" vs "Staff Canteen"). A fixed panel let it spill out the
    # right-hand side; size the panel to the widest line instead, never
    # narrower than the original design and never wider than the screen.
    panel_w = _fit_panel_width(sub_surf.get_width() + 2 * _MARGIN,
                               hint.get_width() + 40)
    top = _top(title_font, body_font)
    col_h = _column_height(head_font, body_font, agent_stats)
    panel_h = top + col_h + 16 + hint.get_height() + 18
    px = (SCREEN_WIDTH - panel_w) // 2
    py = (SCREEN_HEIGHT - panel_h) // 2
    _draw_panel(surface, px, py, panel_w, panel_h)

    headline, headline_colour = (
        ("Stage cleared", _POS) if cleared else ("The AI didn't make it", _NEG))
    _draw_heading(surface, title_font, headline, headline_colour, sub_surf,
                  px, py, panel_w)

    _draw_column(surface, head_font, body_font, px + _MARGIN, py + top,
                 panel_w - 2 * _MARGIN, agent_stats, total_font)

    surface.blit(hint, (px + (panel_w - hint.get_width()) // 2,
                        py + top + col_h + 16))


def _verdict(p, a):
    """Names the opponent from its own stats label, so a run with the
    robot skin doesn't report being beaten by the drone."""
    if p.score > a.score:
        return f"You beat the {a.label}  ({p.score} vs {a.score})"
    if a.score > p.score:
        return f"The {a.label} beat you  ({a.score} vs {p.score})"
    if p.score == 0:
        # Both on nothing is a tie only arithmetically. Calling it a dead
        # heat reads as a photo finish, and sits directly under a
        # headline that has just said Pete didn't make it.
        return "Nobody got out"
    return f"Dead heat  ({p.score} each)"
