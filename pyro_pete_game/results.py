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
    "outrun": ("The AI got out first", RESULTS_ACCENT_COLOR),
    "died": ("Pete didn't make it", _NEG),
}


def _draw_column(surface, head_font, body_font, x, top_y, st):
    surface.blit(head_font.render(st.label, True, RESULTS_ACCENT_COLOR), (x, top_y))
    reason = _REASON_TEXT.get(st.finished_reason, "")
    if reason:
        surface.blit(body_font.render(reason, True, _DIM), (x, top_y + 26))

    surface.blit(head_font.render(str(st.score), True, RESULTS_TEXT_COLOR), (x, top_y + 46))
    surface.blit(body_font.render("SCORE", True, _DIM), (x + 4, top_y + 88))

    y = top_y + 114
    for label, pts in st.score_breakdown():
        col = _POS if pts >= 0 else _NEG
        surface.blit(body_font.render(label, True, _DIM), (x, y))
        surface.blit(body_font.render(f"{pts:+d}", True, col), (x + 190, y))
        y += 22

    y += 6
    pygame.draw.line(surface, (60, 62, 70), (x, y), (x + 250, y))
    y += 8
    for label, value in st.summary_rows():
        surface.blit(body_font.render(label, True, _DIM), (x, y))
        surface.blit(body_font.render(value, True, RESULTS_TEXT_COLOR), (x + 150, y))
        y += 22
    return y


def draw_results(surface, title_font, head_font, body_font,
                 player_stats, agent_stats, total_victims,
                 outcome=None, stage_label=None, has_next_stage=False):
    panel_w, panel_h = 660, 470
    px = (SCREEN_WIDTH - panel_w) // 2
    py = (SCREEN_HEIGHT - panel_h) // 2

    shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 160))
    surface.blit(shade, (0, 0))

    panel = pygame.Rect(px, py, panel_w, panel_h)
    pygame.draw.rect(surface, RESULTS_PANEL_COLOR, panel, border_radius=10)
    pygame.draw.rect(surface, RESULTS_ACCENT_COLOR, panel, 2, border_radius=10)

    headline, headline_colour = _OUTCOME_HEADLINE.get(
        outcome, ("Run complete", RESULTS_TEXT_COLOR))
    surface.blit(title_font.render(headline, True, headline_colour),
                 (px + 28, py + 18))
    sub = f"{total_victims} occupants in the building"
    if stage_label:
        sub = f"{stage_label}  --  {sub}"
    surface.blit(body_font.render(sub, True, _DIM), (px + 30, py + 54))

    col_x = [px + 40, px + 360]
    for x, st in zip(col_x, (player_stats, agent_stats)):
        _draw_column(surface, head_font, body_font, x, py + 86, st)

    verdict = _verdict(player_stats, agent_stats)
    v = head_font.render(verdict, True, RESULTS_TEXT_COLOR)
    surface.blit(v, (px + (panel_w - v.get_width()) // 2, py + panel_h - 62))
    if outcome == "cleared" and has_next_stage:
        hint_text = "Enter for the next stage     R to replay     Esc to quit"
    elif outcome == "cleared":
        hint_text = "You finished the last stage!     Enter for menu     Esc to quit"
    else:
        hint_text = "R to try again     Enter for menu     Esc to quit"
    hint = body_font.render(hint_text, True, (150, 150, 155))
    surface.blit(hint, (px + (panel_w - hint.get_width()) // 2, py + panel_h - 32))


def draw_watch_results(surface, title_font, head_font, body_font, agent_stats,
                       total_victims, stage_label=None, cleared=False,
                       has_next_stage=False):
    """Single-column variant for spectate ("Watch AI Play") runs -- same
    panel language as draw_results, just one column since there's no Pete
    to compare against."""
    panel_w, panel_h = 420, 470
    px = (SCREEN_WIDTH - panel_w) // 2
    py = (SCREEN_HEIGHT - panel_h) // 2

    shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 160))
    surface.blit(shade, (0, 0))

    panel = pygame.Rect(px, py, panel_w, panel_h)
    pygame.draw.rect(surface, RESULTS_PANEL_COLOR, panel, border_radius=10)
    pygame.draw.rect(surface, RESULTS_ACCENT_COLOR, panel, 2, border_radius=10)

    headline, headline_colour = (
        ("Stage cleared", _POS) if cleared else ("The AI didn't make it", _NEG))
    surface.blit(title_font.render(headline, True, headline_colour),
                 (px + 28, py + 18))
    sub = f"{total_victims} occupants in the building"
    if stage_label:
        sub = f"{stage_label}  --  {sub}"
    surface.blit(body_font.render(sub, True, _DIM), (px + 30, py + 54))

    _draw_column(surface, head_font, body_font, px + 40, py + 86, agent_stats)

    if cleared and has_next_stage:
        hint_text = "Enter for the next stage     R to replay     Esc to quit"
    elif cleared:
        hint_text = "Campaign complete!     Enter for menu     Esc to quit"
    else:
        hint_text = "R to run again     Enter for menu     Esc to quit"
    hint = body_font.render(hint_text, True, (150, 150, 155))
    surface.blit(hint, (px + (panel_w - hint.get_width()) // 2, py + panel_h - 32))


def _verdict(p, a):
    """Names the opponent from its own stats label, so a run with the
    robot skin doesn't report being beaten by the drone."""
    if p.score > a.score:
        return f"You beat the {a.label}  ({p.score} vs {a.score})"
    if a.score > p.score:
        return f"The {a.label} beat you  ({a.score} vs {p.score})"
    return f"Dead heat  ({p.score} each)"
