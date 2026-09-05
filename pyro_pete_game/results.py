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


def draw_results(surface, title_font, head_font, body_font,
                 player_stats, agent_stats, total_victims):
    panel_w, panel_h = 660, 470
    px = (SCREEN_WIDTH - panel_w) // 2
    py = (SCREEN_HEIGHT - panel_h) // 2

    shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 160))
    surface.blit(shade, (0, 0))

    panel = pygame.Rect(px, py, panel_w, panel_h)
    pygame.draw.rect(surface, RESULTS_PANEL_COLOR, panel, border_radius=10)
    pygame.draw.rect(surface, RESULTS_ACCENT_COLOR, panel, 2, border_radius=10)

    surface.blit(title_font.render("Run complete", True, RESULTS_TEXT_COLOR),
                 (px + 28, py + 18))
    surface.blit(body_font.render(f"{total_victims} occupants in the building",
                                  True, _DIM), (px + 30, py + 54))

    col_x = [px + 40, px + 360]
    for i, st in enumerate((player_stats, agent_stats)):
        x = col_x[i]
        surface.blit(head_font.render(st.label, True, RESULTS_ACCENT_COLOR), (x, py + 86))
        reason = _REASON_TEXT.get(st.finished_reason, "")
        if reason:
            surface.blit(body_font.render(reason, True, _DIM), (x, py + 112))

        # big score
        surface.blit(title_font.render(str(st.score), True, RESULTS_TEXT_COLOR),
                     (x, py + 132))
        surface.blit(body_font.render("SCORE", True, _DIM), (x + 4, py + 174))

        # breakdown
        y = py + 200
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

    verdict = _verdict(player_stats, agent_stats)
    v = head_font.render(verdict, True, RESULTS_TEXT_COLOR)
    surface.blit(v, (px + (panel_w - v.get_width()) // 2, py + panel_h - 62))
    hint = body_font.render("R to run again     Esc to quit", True, (150, 150, 155))
    surface.blit(hint, (px + (panel_w - hint.get_width()) // 2, py + panel_h - 32))


def _verdict(p, a):
    if p.score > a.score:
        return f"You beat the AI drone  ({p.score} vs {a.score})"
    if a.score > p.score:
        return f"The AI drone beat you  ({a.score} vs {p.score})"
    return f"Dead heat  ({p.score} each)"
