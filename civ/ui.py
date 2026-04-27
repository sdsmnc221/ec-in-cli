"""
civique.ui — Shared Rich helpers, color constants, keyboard input.
"""

import sys
import tty
import termios

from rich.console import Console
from rich.text import Text
from rich.panel import Panel

# ─── Console (singleton) ──────────────────────────────────────────────────────

console = Console()

# ─── Color palette ────────────────────────────────────────────────────────────

TRICOLOR = {
    "blue":  "#0055A4",
    "white": "#FFFFFF",
    "red":   "#EF4135",
    "gold":  "#F5C842",
    "green": "#2ECC71",
    "dim":   "#6B7A99",
    "dark":  "#0A1628",
}

# ─── Theme constants ───────────────────────────────────────────────────────────

THEMES = [
    "Principes et valeurs de la République",
    "Système institutionnel et politique",
    "Droits et devoirs",
    "Histoire, géographie et culture",
    "Vivre dans la société française",
]

THEME_REMAP = {
    "Symboles de la République": "Principes et valeurs de la République",
}

THEME_SHORT = {
    "Principes et valeurs de la République": "Principes & valeurs",
    "Système institutionnel et politique":   "Institutions",
    "Droits et devoirs":                     "Droits & devoirs",
    "Histoire, géographie et culture":       "Histoire & culture",
    "Vivre dans la société française":       "Société française",
}

# ─── Keyboard ─────────────────────────────────────────────────────────────────

def getch() -> str:
    """Read a single keypress without waiting for Enter."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            ch2 = sys.stdin.read(1)
            ch3 = sys.stdin.read(1)
            if ch2 == '[':
                if ch3 == 'A': return 'UP'
                if ch3 == 'B': return 'DOWN'
                if ch3 == 'C': return 'RIGHT'
                if ch3 == 'D': return 'LEFT'
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

# ─── Reusable UI helpers ──────────────────────────────────────────────────────

def header_panel(text: str, subtitle: str = "") -> Panel:
    """Standard branded header panel."""
    t = Text()
    t.append("🇫🇷  ", style="bold")
    t.append(text, style=f"bold {TRICOLOR['blue']}")
    if subtitle:
        t.append("  —  ", style="dim")
        t.append(subtitle, style="italic white")
    return Panel(t, border_style=TRICOLOR["blue"], padding=(0, 2))


def confirm_exit() -> bool:
    """Ask user to confirm before quitting. Returns True if confirmed."""
    console.print(f"\n  [bold yellow]Abandonner l'examen ?[/]  [dim][O]ui / [N]on[/]  ", end="")
    key = getch()
    return key.lower() in ('o', 'y')
