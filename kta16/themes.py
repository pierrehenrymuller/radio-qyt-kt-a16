"""Colour themes: "atelier" (dark, default) and "papier" (light)."""

from textual.theme import Theme

ATELIER = Theme(
    name="atelier",
    primary="#62adff",
    secondary="#4ec9a0",
    accent="#62adff",
    warning="#e8b866",
    error="#f27d85",
    success="#4ec9a0",
    foreground="#d7dde6",
    background="#14181f",
    surface="#1a2029",
    panel="#223e5c",
    dark=True,
)

PAPIER = Theme(
    name="papier",
    primary="#1d4fd7",
    secondary="#17803f",
    accent="#1d4fd7",
    warning="#a86400",
    error="#c32d17",
    success="#17803f",
    foreground="#1f2328",
    background="#fbfaf7",
    surface="#ffffff",
    panel="#e8eefc",
    dark=False,
)

THEMES = (ATELIER, PAPIER)
