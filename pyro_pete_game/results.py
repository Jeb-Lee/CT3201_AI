"""End-of-run results panel: the human-vs-AI comparison.

Drawn over the frozen game when a run ends (Pete reached the exit, or
died). Two columns -- You vs the AI agent -- over the same wall-clock,
because "how far did the optimal agent get while I was doing that" is the
comparison the project's reflection turns on.
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


def draw_results(surface, title_font, head_font, body_font,
                 player_stats, agent_stats, total_victims):
    panel_w, panel_h = 620, 400
    px = (SCREEN_WIDTH - panel_w) // 2
    py = (SCREEN_HEIGHT - panel_h) // 2

    shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 150))
    surface.blit(shade, (0, 0))

    panel = pygame.Rect(px, py, panel_w, panel_h)
    pygame.draw.rect(surface, RESULTS_PANEL_COLOR, panel, border_radius=10)
    pygame.draw.rect(surface, RESULTS_ACCENT_COLOR, panel, 2, border_radius=10)

    title = title_font.render("Run complete", True, RESULTS_TEXT_COLOR)
    surface.blit(title, (px + 28, py + 20))
    sub = body_font.render(
        f"{total_victims} occupants in the building", True, (170, 170, 175)
    )
    surface.blit(sub, (px + 30, py + 56))

    col_x = [px + 40, px + 340]
    for i, st in enumerate((player_stats, agent_stats)):
        x = col_x[i]
        head = head_font.render(st.label, True, RESULTS_ACCENT_COLOR)
        surface.blit(head, (x, py + 92))
        reason = _REASON_TEXT.get(st.finished_reason, "")
        if reason:
            r = body_font.render(reason, True, (170, 170, 175))
            surface.blit(r, (x, py + 118))

        y = py + 150
        for label, value in st.summary_rows():
            surface.blit(body_font.render(label, True, (185, 185, 190)), (x, y))
            surface.blit(body_font.render(value, True, RESULTS_TEXT_COLOR), (x + 150, y))
            y += 26

    # verdict line
    verdict = _verdict(player_stats, agent_stats)
    v = head_font.render(verdict, True, RESULTS_TEXT_COLOR)
    surface.blit(v, (px + (panel_w - v.get_width()) // 2, py + panel_h - 66))

    hint = body_font.render("R to run again    Esc to quit", True, (150, 150, 155))
    surface.blit(hint, (px + (panel_w - hint.get_width()) // 2, py + panel_h - 34))


def _verdict(p, a):
    if p.victims_saved > a.victims_saved:
        return "You rescued more than the AI."
    if a.victims_saved > p.victims_saved:
        return "The AI rescued more than you."
    if p.finished_reason == "exit" and a.finished_reason != "exit":
        return "Tie on rescues - but you got out and the AI didn't."
    return "You and the AI tied."
