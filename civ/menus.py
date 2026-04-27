"""
civique.menus — Interactive pre-exam menus:
  - theme_menu()  : toggle which themes are included
  - mode_menu()   : choose super-hard or marathon (+ marathon size)
"""

import sys
from dataclasses import dataclass

from rich.panel import Panel
from rich.rule import Rule

from .loader import DataLoader
from .models import Question
from .ui import console, TRICOLOR, THEMES, THEME_SHORT, getch


# ─── Session config (output of menus) ────────────────────────────────────────

@dataclass
class SessionConfig:
    mode: str               # "super-hard" | "marathon"
    selected_themes: list[str]
    question_pool: list[Question]
    total_questions: int    # 40 for super-hard, N×40 for marathon
    duration_seconds: int   # 45min per 40 questions


# ─── Theme menu ───────────────────────────────────────────────────────────────

def theme_menu(loader: DataLoader) -> list[str]:
    """
    Arrow keys ↑↓ to navigate, Space to toggle, Enter to confirm.
    Returns list of selected theme names.
    """
    by_theme = loader.by_theme()
    available = [t for t in THEMES if by_theme.get(t)]
    selected = {t: True for t in available}
    cursor = 0

    def render():
        console.clear()
        console.print(Panel(
            f"[bold {TRICOLOR['blue']}]THÈMES INCLUS[/]  [dim]—  "
            f"↑↓ naviguer   Espace toggle   Entrée confirmer[/]",
            border_style=TRICOLOR["blue"], padding=(0, 2)
        ))
        console.print()

        for i, theme in enumerate(available):
            count = len(by_theme[theme])
            is_on = selected[theme]
            is_cursor = (i == cursor)

            arrow = f"[bold {TRICOLOR['gold']}]▶[/]" if is_cursor else " "
            check = f"[bold {TRICOLOR['green']}]✓[/]" if is_on else "[dim]○[/]"
            label_style = "bold white" if is_cursor else ("white" if is_on else "dim")
            count_style = TRICOLOR["gold"] if is_on else "dim"

            console.print(
                f"  {arrow} {check}  [{label_style}]{THEME_SHORT.get(theme, theme)}[/]"
                f"  [{count_style}]({count} questions)[/]"
            )

        total_sel = sum(len(by_theme[t]) for t in available if selected[t])
        console.print()
        console.print(Rule(style="dim"))
        console.print(
            f"  Sélectionnées : [bold {TRICOLOR['gold']}]{total_sel}[/] / {len(loader.questions)}"
        )
        if total_sel < 40:
            console.print(
                f"  [bold yellow]⚠ Moins de 40 questions — examen complet impossible.[/]"
            )

    while True:
        render()
        key = getch()
        if key in ('UP', 'k') and cursor > 0:
            cursor -= 1
        elif key in ('DOWN', 'j') and cursor < len(available) - 1:
            cursor += 1
        elif key == ' ':
            t = available[cursor]
            if selected[t] and sum(selected.values()) == 1:
                pass  # block deselecting last theme
            else:
                selected[t] = not selected[t]
        elif key in ('\r', '\n', ''):
            break
        elif key in ('q', 'Q', '\x03'):
            console.print("\n[dim]Annulé.[/]\n")
            sys.exit(0)

    return [t for t in available if selected[t]]


# ─── Mode menu ────────────────────────────────────────────────────────────────

def mode_menu(preselected: str | None = None) -> tuple[str, int]:
    """
    Choose between super-hard (40q / 45min) and marathon (N×40q).
    Returns (mode_name, total_questions).
    """
    if preselected == "super-hard":
        return ("super-hard", 40)
    if preselected == "marathon":
        return _marathon_size_menu()

    options = ["super-hard", "marathon"]
    cursor = 0

    descriptions = {
        "super-hard": (
            "40 questions  ·  45 minutes",
            "Ratio officiel : 28 connaissances + 12 mises en situation.\n"
            "  Tirage pondéré par vos erreurs passées (si historique existant)."
        ),
        "marathon": (
            "N × 40 questions  ·  N × 45 minutes",
            "Choisissez un multiple de 40 (80, 120…).\n"
            "  Idéal pour une session d'entraînement intensive."
        ),
    }

    def render():
        console.clear()
        console.print(Panel(
            f"[bold {TRICOLOR['blue']}]MODE D'EXAMEN[/]  [dim]—  ↑↓ naviguer   Entrée confirmer[/]",
            border_style=TRICOLOR["blue"], padding=(0, 2)
        ))
        console.print()

        for i, mode in enumerate(options):
            is_cursor = (i == cursor)
            arrow = f"[bold {TRICOLOR['gold']}]▶[/]" if is_cursor else " "
            name_style = f"bold {TRICOLOR['gold']}" if is_cursor else "white"
            subtitle, detail = descriptions[mode]

            console.print(f"  {arrow} [{name_style}]{mode.upper()}[/]  [dim]{subtitle}[/]")
            if is_cursor:
                for line in detail.split('\n'):
                    console.print(f"       [dim]{line}[/]")
            console.print()

    while True:
        render()
        key = getch()
        if key in ('UP', 'k') and cursor > 0:
            cursor -= 1
        elif key in ('DOWN', 'j') and cursor < len(options) - 1:
            cursor += 1
        elif key in ('\r', '\n', ''):
            mode = options[cursor]
            if mode == "marathon":
                return _marathon_size_menu()
            return (mode, 40)
        elif key in ('\x03',):
            sys.exit(0)


def _marathon_size_menu() -> tuple[str, int]:
    """Choose marathon size: multiples of 40 from 80 to 200+."""
    sizes = [80, 120, 160, 200]
    cursor = 0

    def render():
        console.clear()
        console.print(Panel(
            f"[bold {TRICOLOR['blue']}]MARATHON — NOMBRE DE QUESTIONS[/]  "
            f"[dim]—  ↑↓ naviguer   Entrée confirmer[/]",
            border_style=TRICOLOR["blue"], padding=(0, 2)
        ))
        console.print()
        for i, n in enumerate(sizes):
            is_cursor = (i == cursor)
            arrow = f"[bold {TRICOLOR['gold']}]▶[/]" if is_cursor else " "
            style = f"bold {TRICOLOR['gold']}" if is_cursor else "white"
            mins = (n // 40) * 45
            console.print(
                f"  {arrow} [{style}]{n} questions[/]  [dim]({mins} minutes)[/]"
            )
        console.print()
        console.print(f"  [dim]Chaque bloc de 40 questions = 45 minutes.[/]")

    while True:
        render()
        key = getch()
        if key in ('UP', 'k') and cursor > 0:
            cursor -= 1
        elif key in ('DOWN', 'j') and cursor < len(sizes) - 1:
            cursor += 1
        elif key in ('\r', '\n', ''):
            return ("marathon", sizes[cursor])
        elif key in ('\x03',):
            sys.exit(0)


# ─── Build session config ─────────────────────────────────────────────────────

def build_config(
    loader: DataLoader,
    selected_themes: list[str],
    mode: str,
    total_questions: int,
    stats: dict,
) -> SessionConfig:
    """
    Draw the question pool from selected themes.
    super-hard: maintains 28 conn + 12 mise-sit ratio per 40-block.
    marathon:   same ratio, repeated across blocks.
    Applies difficulty weighting if stats history exists.
    """
    from . import stats as stats_module

    by_theme = loader.by_theme()

    # Pool filtered to selected themes
    pool_conn = [
        q for t in selected_themes
        for q in by_theme.get(t, [])
        if q.type == "connaissance"
    ]
    pool_mise = [
        q for t in selected_themes
        for q in by_theme.get(t, [])
        if q.type == "mise-situation"
    ]

    blocks = total_questions // 40
    n_conn = 28 * blocks
    n_mise = 12 * blocks

    # Clamp to available
    n_conn = min(n_conn, len(pool_conn))
    n_mise = min(n_mise, len(pool_mise))

    def weighted_sample(pool: list[Question], n: int) -> list[Question]:
        if not stats["questions"] or len(pool) <= n:
            import random
            return random.sample(pool, min(n, len(pool)))
        # Weight by difficulty score — harder questions drawn more often
        weights = [
            0.1 + stats_module.difficulty_score(stats, q.id)
            for q in pool
        ]
        import random
        total_w = sum(weights)
        probs = [w / total_w for w in weights]
        chosen = set()
        result = []
        while len(result) < n and len(chosen) < len(pool):
            idx = random.choices(range(len(pool)), weights=probs, k=1)[0]
            if idx not in chosen:
                chosen.add(idx)
                result.append(pool[idx])
        return result

    drawn_conn = weighted_sample(pool_conn, n_conn)
    drawn_mise = weighted_sample(pool_mise, n_mise)

    import random
    question_pool = drawn_conn + drawn_mise
    random.shuffle(question_pool)

    duration = blocks * 45 * 60  # seconds

    return SessionConfig(
        mode=mode,
        selected_themes=selected_themes,
        question_pool=question_pool,
        total_questions=len(question_pool),
        duration_seconds=duration,
    )
