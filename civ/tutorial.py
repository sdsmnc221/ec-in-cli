"""
civique.tutorial — Animated cheat-sheet shown on first launch.
"""

import sys
import time
import select

from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule

from .ui import console, TRICOLOR

# ─── Content ──────────────────────────────────────────────────────────────────

SECTIONS = [
    (
        "① PENDANT L'EXAMEN",
        [
            ("[bold white][A] [B] [C] [D][/]       ", "Répondre à la question affichée"),
            ("[bold white][←] [→][/]               ", "Question précédente / suivante"),
            ("[bold white][↵ Entrée][/]             ", "Sauter à la prochaine non-répondue / marquée"),
            ("[bold white][G][/]                   ", "Aller directement à la question n°__"),
            ("[bold white][M][/]                   ", f"Marquer « pas sûr·e » pour révision  [yellow]?[/]"),
            ("[bold white][Tab][/]                 ", "Répondu mais peu confiant·e          [dim]~[/]"),
            ("[bold white][Q][/]                   ", "Soumettre / Abandonner l'examen"),
        ]
    ),
    (
        "② PANNEAU DE NAVIGATION  (colonne gauche)",
        [
            (f"[bold {TRICOLOR['gold']}]→  12[/]  ", "question en cours"),
            ("[bold white]●  07[/]  ",               "non répondue"),
            (f"[bold {TRICOLOR['green']}]✓  04[/]  ","répondue"),
            ("[bold yellow]?  09[/]  ",              "marquée pour révision"),
            ("[dim]~  11[/]  ",                      "répondue, peu confiante"),
        ]
    ),
    (
        "③ TIMER — CODES COULEUR",
        [
            ("[bold green]⏱ 38:24[/]  ", "vert    →  tranquille"),
            ("[bold yellow]⏱ 09:58[/]  ", "orange  →  accélère"),
            ("[bold red]⏱ 04:59[/]  ",   "rouge   →  urgence"),
            ("[bold red]⏱ 01:59[/]  ",   "rouge vif  →  temps critique, flash"),
        ]
    ),
    (
        "④ FIN D'EXAMEN & RÉSULTATS",
        [
            ("[white]Seuil de réussite[/]    ", "32 / 40  (80%)"),
            ("[white]Sans réponse[/]         ", "comptent comme fausses"),
            ("[white]Après le score[/]       ", "révision interactive des erreurs"),
            ("[white]Historique[/]           ", "10 dernières sessions sauvegardées"),
        ]
    ),
]

TITLE_TEXT = Text(justify="center")
TITLE_TEXT.append("🇫🇷  BIENVENUE — CIVIQUE CLI  🇫🇷\n", style=f"bold {TRICOLOR['blue']}")
TITLE_TEXT.append("Simulateur d'examen de naturalisation française", style="italic white")

# ─── Render ───────────────────────────────────────────────────────────────────

def _render(revealed: list):
    console.clear()
    console.print(Panel(TITLE_TEXT, border_style=TRICOLOR["gold"], padding=(1, 4)))
    console.print()

    for header, rows in revealed:
        console.print(f"  [bold {TRICOLOR['gold']}]{header}[/]")
        console.print(f"  [dim]{'─' * 58}[/]")
        for left, right in rows:
            console.print(f"    {left}  [dim]{right}[/]")
        console.print()

    console.print(f"  [dim]Appuyez sur [white]Entrée[/] pour continuer, ou attendez…[/]")


def _skip_remaining(revealed: list):
    """Add any missing sections at once."""
    for section in SECTIONS:
        if section not in revealed:
            revealed.append(section)


# ─── Public entry ─────────────────────────────────────────────────────────────

def show():
    """
    Display the animated cheat-sheet.
    Sections appear one by one (1.4s apart).
    Press Enter at any point to skip animation and show all at once.
    """
    revealed = []

    for section in SECTIONS:
        revealed.append(section)
        _render(revealed)

        # Wait up to 1.4s, bail early on Enter
        start = time.time()
        skipped = False
        while time.time() - start < 1.4:
            r, _, _ = select.select([sys.stdin], [], [], 0.05)
            if r:
                sys.stdin.readline()
                _skip_remaining(revealed)
                _render(revealed)
                skipped = True
                break
        if skipped:
            break

    console.print()
    console.print(
        f"  [bold white]Prêt·e ?[/]  "
        f"Appuyez sur [bold {TRICOLOR['gold']}]Entrée[/] pour commencer…"
    )
    input()