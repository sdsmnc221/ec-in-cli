#!/usr/bin/env python3
"""
civique-cli.py — Simulateur d'examen de naturalisation française
Step 2 : Tutorial (animated cheat-sheet) + Theme toggle menu
"""

import argparse
import json
import sys
import random
import time
import tty
import termios
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich import box

# ─── Constants ────────────────────────────────────────────────────────────────

DEFAULT_DATASET = "unified_dataset_complete.json"
STATS_FILE = Path.home() / ".civique_stats.json"

THEMES = [
    "Principes et valeurs de la République",
    "Système institutionnel et politique",
    "Droits et devoirs",
    "Histoire, géographie et culture",
    "Vivre dans la société française",
]

# Remap stray themes to official ones
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

TRICOLOR = {
    "blue":  "#0055A4",
    "white": "#FFFFFF",
    "red":   "#EF4135",
    "gold":  "#F5C842",
    "dim":   "#6B7A99",
    "dark":  "#0A1628",
    "green": "#2ECC71",
}

console = Console()


# ─── Keyboard helper ──────────────────────────────────────────────────────────

def getch() -> str:
    """Read a single keypress without waiting for Enter."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        # Handle escape sequences (arrow keys)
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


# ─── Data model ───────────────────────────────────────────────────────────────

@dataclass
class Question:
    id: str
    source: str
    theme: str
    type: str               # connaissance | mise-situation
    difficulte: str         # standard | hard | piege
    question: str
    answers: list[str]      # answers[0] is always correct in source
    correct_index: int      # always 0 in source; shuffled on load
    explication: str
    needs_manual_review: bool = False
    qa_flag_type: Optional[str] = None

    # Runtime (set after shuffle)
    shuffled_answers: list[str] = field(default_factory=list)
    shuffled_correct_index: int = 0

    def shuffle(self):
        """Shuffle answer options, track new correct index."""
        indices = list(range(len(self.answers)))
        random.shuffle(indices)
        self.shuffled_answers = [self.answers[i] for i in indices]
        self.shuffled_correct_index = indices.index(self.correct_index)

    @property
    def correct_answer(self) -> str:
        return self.shuffled_answers[self.shuffled_correct_index]


# ─── DataLoader ───────────────────────────────────────────────────────────────

class DataLoader:
    def __init__(self, path: str):
        self.path = Path(path)
        self.questions: list[Question] = []
        self.skipped: int = 0
        self.errors: list[str] = []

    def load(self) -> bool:
        if not self.path.exists():
            console.print(f"\n[bold red]✗ Fichier introuvable :[/] {self.path}")
            console.print(f"  [dim]Vérifiez le chemin ou utilisez --dataset pour spécifier un fichier.[/]\n")
            return False

        try:
            with open(self.path, encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as e:
            console.print(f"\n[bold red]✗ JSON invalide :[/] {e}\n")
            return False

        if not isinstance(raw, list):
            console.print("\n[bold red]✗ Format inattendu :[/] le fichier doit contenir une liste JSON.\n")
            return False

        for item in raw:
            q = self._parse(item)
            if q:
                q.shuffle()
                self.questions.append(q)
            else:
                self.skipped += 1

        return len(self.questions) > 0

    def _parse(self, item: dict) -> Optional[Question]:
        required = ["id", "question", "answers", "correct_index"]
        for f in required:
            if f not in item:
                self.errors.append(f"Champ manquant '{f}' dans {item.get('id', '?')}")
                return None

        if len(item["answers"]) < 4:
            return None  # incomplete distractors — skip silently

        # Remap stray themes
        theme = item.get("theme", "")
        theme = THEME_REMAP.get(theme, theme)

        explication = (item.get("explication") or "").strip()
        if not explication:
            explication = "Pas d'explication disponible."

        return Question(
            id=item.get("id", "?"),
            source=item.get("source", ""),
            theme=theme,
            type=item.get("type", "connaissance"),
            difficulte=item.get("difficulte", "standard"),
            question=item.get("question", ""),
            answers=item["answers"],
            correct_index=item["correct_index"],
            explication=explication,
            needs_manual_review=item.get("needs_manual_review", False),
            qa_flag_type=item.get("qa_flag_type"),
        )

    def by_theme(self) -> dict[str, list[Question]]:
        result = {t: [] for t in THEMES}
        for q in self.questions:
            if q.theme in result:
                result[q.theme].append(q)
            # unknown themes already remapped; silently drop anything remaining
        return result

    def stats_table(self) -> Table:
        by_theme = self.by_theme()
        table = Table(box=box.SIMPLE, show_header=True, header_style=f"bold {TRICOLOR['blue']}")
        table.add_column("Thème", style="white")
        table.add_column("Questions", justify="right", style=f"bold {TRICOLOR['gold']}")
        table.add_column("Conn.", justify="right", style="dim")
        table.add_column("Mise-sit.", justify="right", style="dim")

        total = 0
        for theme, qs in by_theme.items():
            if not qs:
                continue
            conn = sum(1 for q in qs if q.type == "connaissance")
            mise = sum(1 for q in qs if q.type == "mise-situation")
            table.add_row(THEME_SHORT.get(theme, theme), str(len(qs)), str(conn), str(mise))
            total += len(qs)

        table.add_section()
        table.add_row("[bold]TOTAL[/]", f"[bold {TRICOLOR['gold']}]{total}[/]", "", "")
        return table


# ─── Stats / persistence ──────────────────────────────────────────────────────

def load_stats() -> dict:
    if STATS_FILE.exists():
        try:
            with open(STATS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"first_launch": True, "questions": {}, "sessions": []}


def save_stats(stats: dict):
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        console.print(f"[dim yellow]⚠ Impossible de sauvegarder les stats : {e}[/]")


# ─── Startup screen ───────────────────────────────────────────────────────────

def show_startup(loader: DataLoader, dataset_path: str):
    console.clear()

    title = Text()
    title.append("🇫🇷  ", style="bold")
    title.append("CIVIQUE CLI", style=f"bold {TRICOLOR['blue']}")
    title.append("  —  ", style="dim")
    title.append("Simulateur d'examen de naturalisation", style="italic white")

    console.print(Panel(title, border_style=TRICOLOR["blue"], padding=(0, 2)))
    console.print()
    console.print(f"  [dim]Dataset :[/] [white]{dataset_path}[/]")

    if loader.skipped:
        console.print(f"  [yellow]⚠ {loader.skipped} question(s) ignorée(s) (distracteurs incomplets)[/]")
    if loader.errors:
        for e in loader.errors[:5]:
            console.print(f"    [dim red]· {e}[/]")

    console.print()
    console.print(loader.stats_table())
    console.print(f"\n  [dim]Appuyez sur [bold white]Entrée[/] pour continuer…[/]\n")
    input()


# ─── Tutorial ─────────────────────────────────────────────────────────────────

TUTORIAL_SECTIONS = [
    (
        "① PENDANT L'EXAMEN",
        [
            ("  [bold white][A] [B] [C] [D][/]", "Répondre à la question affichée"),
            ("  [bold white][←] [→][/]            ", "Question précédente / suivante"),
            ("  [bold white][G][/]                  ", "Aller directement à la question n°__"),
            ("  [bold white][M][/]                  ", "Marquer « pas sûr·e » pour révision  [yellow]?[/]"),
            ("  [bold white][C][/]                  ", "Répondu mais peu confiant·e          [dim]~[/]"),
            ("  [bold white][Q][/]                  ", "Abandonner l'examen (confirmation)"),
        ]
    ),
    (
        "② PANNEAU DE NAVIGATION  (colonne gauche)",
        [
            ("  [bold white]→  12[/]", "question en cours"),
            ("  [bold white]●  07[/]", "non répondue"),
            ("  [bold green]✓  04[/]", "répondue"),
            ("  [bold yellow]?  09[/]", "marquée pour révision"),
            ("  [dim]~  11[/]",        "répondue, peu confiante"),
        ]
    ),
    (
        "③ TIMER — CODES COULEUR",
        [
            ("  [bold green]⏱ 38:24[/]", "→  vert    : tranquille"),
            ("  [bold yellow]⏱ 09:58[/]", "→  orange  : accélère"),
            ("  [bold red]⏱ 04:59[/]", "→  rouge   : urgence"),
            ("  [bold red blink]⏱ 01:59[/]", "→  flash   : temps critique"),
        ]
    ),
    (
        "④ FIN D'EXAMEN & RÉSULTATS",
        [
            ("  Seuil de réussite", ": 32 / 40  (80%)"),
            ("  Questions sans réponse", ": comptent comme fausses"),
            ("  Après le score", ": révision interactive des erreurs"),
            ("  Historique", ": 10 dernières sessions sauvegardées"),
        ]
    ),
]


def show_tutorial(force: bool = False):
    """Animated cheat-sheet tutorial. Shown on first launch or with --tutorial."""
    console.clear()

    # Title panel
    title = Text(justify="center")
    title.append("🇫🇷  BIENVENUE — CIVIQUE CLI  🇫🇷\n", style=f"bold {TRICOLOR['blue']}")
    title.append("Simulateur d'examen de naturalisation française", style="italic white")
    console.print(Panel(title, border_style=TRICOLOR["gold"], padding=(1, 4)))
    console.print()

    revealed = []

    def render_all():
        console.clear()
        console.print(Panel(title, border_style=TRICOLOR["gold"], padding=(1, 4)))
        console.print()
        for header, rows in revealed:
            console.print(f"  [bold {TRICOLOR['gold']}]{header}[/]")
            console.print(f"  [dim]{'─' * 60}[/]")
            for left, right in rows:
                console.print(f"    {left}  [dim]{right}[/]")
            console.print()
        console.print(f"  [dim]Appuyez sur [white]Entrée[/] pour continuer, ou attendez…[/]")

    # Reveal each section with a pause, allow Enter to skip animation
    import select

    for section in TUTORIAL_SECTIONS:
        revealed.append(section)
        render_all()

        # Wait up to 1.4s but bail early on Enter
        start = time.time()
        while time.time() - start < 1.4:
            r, _, _ = select.select([sys.stdin], [], [], 0.05)
            if r:
                sys.stdin.readline()  # consume the Enter
                # Skip remaining animation — show all sections at once
                for remaining in TUTORIAL_SECTIONS:
                    if remaining not in revealed:
                        revealed.append(remaining)
                render_all()
                console.print()
                console.print(f"  [dim]Appuyez sur [white]Entrée[/] pour commencer…[/]")
                input()
                return

    # All sections shown — wait for final Enter
    console.print()
    console.print(f"  [bold white]Prêt·e ?[/]  Appuyez sur [bold {TRICOLOR['gold']}]Entrée[/] pour commencer…")
    input()


# ─── Theme toggle menu ────────────────────────────────────────────────────────

def theme_menu(loader: DataLoader) -> list[str]:
    """
    Interactive checklist to toggle which themes are included.
    Arrow keys to move, Space to toggle, Enter to confirm.
    Returns list of selected theme names.
    """
    by_theme = loader.by_theme()
    available = [t for t in THEMES if by_theme.get(t)]
    selected = {t: True for t in available}
    cursor = 0

    def render():
        console.clear()
        console.print(Panel(
            f"[bold {TRICOLOR['blue']}]THÈMES INCLUS[/]  —  "
            f"[dim]↑↓ naviguer   Espace toggle   Entrée confirmer[/]",
            border_style=TRICOLOR["blue"],
            padding=(0, 2)
        ))
        console.print()

        total_selected = sum(len(by_theme[t]) for t in available if selected[t])

        for i, theme in enumerate(available):
            count = len(by_theme[theme])
            is_on = selected[theme]
            is_cursor = (i == cursor)

            # Cursor arrow
            arrow = f"[bold {TRICOLOR['gold']}]▶[/]" if is_cursor else " "

            # Checkbox
            check = f"[bold {TRICOLOR['green']}]✓[/]" if is_on else f"[dim]○[/]"

            # Theme label
            label_style = "bold white" if is_cursor else ("white" if is_on else "dim")
            label = f"[{label_style}]{THEME_SHORT.get(theme, theme)}[/]"

            # Count
            count_style = TRICOLOR['gold'] if is_on else "dim"
            count_str = f"[{count_style}]({count} questions)[/]"

            console.print(f"  {arrow} {check}  {label}  {count_str}")

        console.print()
        console.print(Rule(style="dim"))
        console.print(
            f"  Questions sélectionnées : "
            f"[bold {TRICOLOR['gold']}]{total_selected}[/] / {len(loader.questions)}"
        )

        # Warning if too few for an exam
        if total_selected < 40:
            console.print(
                f"  [bold yellow]⚠ Moins de 40 questions — "
                f"impossible de générer un examen complet.[/]"
            )

    while True:
        render()
        key = getch()

        if key in ('UP', 'k') and cursor > 0:
            cursor -= 1
        elif key in ('DOWN', 'j') and cursor < len(available) - 1:
            cursor += 1
        elif key == ' ':
            theme = available[cursor]
            # Prevent deselecting all
            if selected[theme] and sum(selected.values()) == 1:
                pass  # silently block
            else:
                selected[theme] = not selected[theme]
        elif key in ('\r', '\n', ''):
            break
        elif key in ('q', 'Q', '\x03'):  # Ctrl+C or q
            console.print("\n[dim]Annulé.[/]\n")
            sys.exit(0)

    return [t for t in available if selected[t]]


# ─── CLI entry ────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Simulateur CLI d'examen de naturalisation française",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python civique-cli.py
  python civique-cli.py --dataset mon_dataset.json
  python civique-cli.py --mode marathon
  python civique-cli.py --tutorial
        """
    )
    parser.add_argument(
        "--dataset", "-d",
        default=DEFAULT_DATASET,
        help=f"Chemin vers le fichier JSON (défaut : {DEFAULT_DATASET})"
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["super-hard", "marathon"],
        default=None,
        help="Mode de simulation (défaut : sélection interactive)"
    )
    parser.add_argument(
        "--tutorial",
        action="store_true",
        help="Afficher le tutoriel même si déjà vu"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Load stats
    stats = load_stats()

    # Load dataset
    loader = DataLoader(args.dataset)
    console.print(f"\n[dim]Chargement de [white]{args.dataset}[/]…[/]")
    if not loader.load():
        sys.exit(1)

    # Startup screen
    show_startup(loader, args.dataset)

    # Tutorial — first launch or --tutorial flag
    if stats.get("first_launch", True) or args.tutorial:
        show_tutorial(force=args.tutorial)
        stats["first_launch"] = False
        save_stats(stats)

    # Theme selection menu
    selected_themes = theme_menu(loader)

    # Summary before exam (placeholder for Step 3)
    console.clear()
    console.print(f"\n  [bold {TRICOLOR['gold']}]Thèmes sélectionnés :[/]")
    for t in selected_themes:
        console.print(f"    [dim]·[/] {THEME_SHORT.get(t, t)}")

    console.print(f"\n  [dim]Step 2 OK — Tutorial + Theme menu fonctionnels.[/]")
    console.print(f"  [dim]Prochain step : sélection du mode (super-hard / marathon).[/]\n")


if __name__ == "__main__":
    main()