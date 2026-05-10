"""
civique/timeline.py
Affichage Rich de la timeline civique.
Drill-down : mode Learning (explication) ou mode Quiz (mini-examen).
"""

import os
import sys
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich import box

from civ.timeline_builder import (
    build_timeline_entries,
    load_timeline,
    load_dataset,
)

# ---------------------------------------------------------------------------
# Constantes UI
# ---------------------------------------------------------------------------

THEME_COLORS = {
    "Principes et valeurs de la République": "blue",
    "Système institutionnel et politique":   "cyan",
    "Droits et devoirs":                     "green",
    "Histoire, géographie et culture":       "yellow",
    "Vivre dans la société française":       "magenta",
}

DEFAULT_COLOR = "white"

TIMELINE_DATASET_PATH = "timeline_dataset.json"
DATASET_DEFAULT_PATH  = "unified_dataset_complete.json"

# ---------------------------------------------------------------------------
# Résolution de la source
# ---------------------------------------------------------------------------

def resolve_source(
    questions: Optional[list[dict]],
    timeline: Optional[list[dict]],
) -> tuple[str, list[dict]]:
    """
    Détermine la source et le mode disponible.

    Retourne (mode_disponible, entries) où mode_disponible est :
        "quiz_or_learn"  — dataset QCM dispo, les deux modes possibles
        "learn_only"     — timeline pré-calculée uniquement
        "none"           — aucune source

    Priorité : timeline_dataset.json (labels curés) > build à la volée.
    """
    if timeline:
        # Labels curés disponibles — source prioritaire
        return "learn_only", timeline

    if questions:
        # Fallback : build à la volée depuis le dataset QCM
        entries = build_timeline_entries(questions, use_haiku=False)
        return "quiz_or_learn", entries

    return "none", []


# ---------------------------------------------------------------------------
# Input clavier bas niveau (comme getch dans ui.py)
# ---------------------------------------------------------------------------

def _getch() -> str:
    """Lit un caractère clavier sans attendre Entrée. Cross-platform."""
    try:
        import tty, termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            # Séquences d'échappement (flèches)
            if ch == "\x1b":
                ch2 = sys.stdin.read(1)
                ch3 = sys.stdin.read(1)
                if ch2 == "[":
                    if ch3 == "A": return "UP"
                    if ch3 == "B": return "DOWN"
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:
        return input()


# ---------------------------------------------------------------------------
# Prompt mode Learning / Quiz
# ---------------------------------------------------------------------------

def prompt_mode(console: Console) -> str:
    """
    Demande à l'utilisateur son mode pour toute la session.
    Retourne "learning" ou "quiz".
    """
    console.print()
    console.print(Panel(
        Text.assemble(
            ("  Choisissez votre mode pour cette session\n\n", "bold white"),
            ("  [L] ", "bold cyan"), ("Mode Learning  ", "white"),
            ("— lire les explications complètes\n", "dim"),
            ("  [Q] ", "bold yellow"), ("Mode Quiz      ", "white"),
            ("— répondre aux questions liées", "dim"),
        ),
        title="[bold]Timeline — Mode de drill-down[/bold]",
        border_style="blue",
        padding=(1, 2),
    ))
    console.print()

    while True:
        key = _getch().lower()
        if key == "l":
            return "learning"
        if key == "q":
            return "quiz"


# ---------------------------------------------------------------------------
# Warning rouge — aucune source
# ---------------------------------------------------------------------------

def render_no_source_warning(console: Console) -> None:
    console.print()
    console.print(Panel(
        Text.assemble(
            ("  ⚠  Aucune source de données disponible\n\n", "bold red"),
            ("  Ni dataset QCM (", "dim"),
            (DATASET_DEFAULT_PATH, "yellow"),
            (")\n", "dim"),
            ("  ni timeline pré-calculée (", "dim"),
            (TIMELINE_DATASET_PATH, "yellow"),
            (") n'ont été trouvés.\n\n", "dim"),
            ("  Appuyez sur ", "dim"),
            ("[↵]", "bold white"),
            (" pour revenir au menu.", "dim"),
        ),
        title="[bold red]Timeline — Erreur[/bold red]",
        border_style="red",
        padding=(1, 2),
    ))
    _getch()


# ---------------------------------------------------------------------------
# Affichage table timeline (windowed)
# ---------------------------------------------------------------------------

WINDOW_SIZE = 12  # nombre de lignes visibles


def render_timeline_table(
    entries: list[dict],
    cursor: int,
    window_start: int,
    console: Console,
) -> None:
    """Affiche la fenêtre courante de la timeline."""
    console.clear()

    # Header
    console.print(Panel(
        Text.assemble(
            ("📅  TIMELINE — HISTOIRE & CIVIQUE DE FRANCE", "bold white"),
        ),
        border_style="blue",
        padding=(0, 2),
    ))

    table = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold dim",
        expand=True,
        padding=(0, 1),
    )
    table.add_column("Année",    style="bold", width=13, no_wrap=True)
    table.add_column("Événement",               ratio=3)
    table.add_column("Thème",    style="dim",   ratio=2)

    window_end = min(window_start + WINDOW_SIZE, len(entries))
    visible = entries[window_start:window_end]

    for i, entry in enumerate(visible):
        abs_i = window_start + i
        is_cursor = abs_i == cursor

        # Année / période
        year_str = str(entry["year"])
        if entry.get("year_end"):
            year_str += f"–{entry['year_end']}"

        # Couleur thème
        color = THEME_COLORS.get(entry["theme"], DEFAULT_COLOR)

        # Label
        label = entry["label"]

        if is_cursor:
            year_cell  = Text(f"▶ {year_str}", style=f"bold {color}")
            label_cell = Text(label, style=f"bold {color}")
            theme_cell = Text(entry["theme"], style=f"{color}")
        else:
            year_cell  = Text(f"  {year_str}", style=color)
            label_cell = Text(label, style="white")
            theme_cell = Text(entry["theme"], style="dim")

        table.add_row(year_cell, label_cell, theme_cell)

    console.print(table)

    # Indicateurs scroll
    scroll_hints = []
    if window_start > 0:
        scroll_hints.append(("  ↑ plus haut", "dim"))
    if window_end < len(entries):
        scroll_hints.append(("  ↓ plus bas", "dim"))

    if scroll_hints:
        t = Text()
        for txt, style in scroll_hints:
            t.append(txt, style=style)
            t.append("   ")
        console.print(t)

    # Légende touches
    console.print()
    console.print(Text.assemble(
        ("  [↑↓] ", "bold cyan"), ("naviguer   ", "dim"),
        ("[↵] ", "bold cyan"), ("drill-down   ", "dim"),
        ("[F] ", "bold cyan"), ("filtrer thème   ", "dim"),
        ("[Q] ", "bold cyan"), ("retour menu", "dim"),
    ))


# ---------------------------------------------------------------------------
# Drill-down — Mode Learning
# ---------------------------------------------------------------------------

def render_drilldown_learning(
    entry: dict,
    questions: Optional[list[dict]],
    console: Console,
) -> None:
    """
    Affiche les explications complètes des questions liées à l'entrée.
    Si questions=None (source pré-calculée), affiche les raw_labels.
    """
    console.clear()

    year_str = str(entry["year"])
    if entry.get("year_end"):
        year_str += f"–{entry['year_end']}"

    color = THEME_COLORS.get(entry["theme"], DEFAULT_COLOR)

    # Titre
    console.print(Panel(
        Text.assemble(
            (f"  📖  {year_str}  —  ", "bold white"),
            (entry["label"], f"bold {color}"),
        ),
        border_style=color,
        padding=(0, 2),
    ))
    console.print()

    # Contenu
    question_ids = entry.get("question_ids", [])

    if questions and question_ids:
        # Source QCM : affiche les explications complètes
        q_map = {q["id"]: q for q in questions}
        found = [q_map[qid] for qid in question_ids if qid in q_map]

        for q in found:
            explication = q.get("explication", "")
            question_text = q.get("question", "")

            console.print(Panel(
                Text.assemble(
                    ("Question  ", "dim"),
                    (q["id"], "bold dim"),
                    ("\n\n", ""),
                    (question_text + "\n\n", "bold white"),
                    (explication, "white"),
                ),
                border_style="dim",
                padding=(1, 2),
            ))
            console.print()

    else:
        # Source timeline_dataset.json : explication > explications[0] > fallback
        explication = (
            entry.get("explication", "").strip()
            or (entry.get("explications") or [""])[0].strip()
            or "Pas d'explication disponible."
        )

        console.print(Panel(
            Text(f"  {explication}", style="white"),
            border_style="dim",
            padding=(1, 2),
        ))
        console.print()

    console.print(Text.assemble(
        ("  [↵] ", "bold cyan"), ("retour timeline", "dim"),
    ))
    _getch()


# ---------------------------------------------------------------------------
# Drill-down — Mode Quiz
# ---------------------------------------------------------------------------

def render_drilldown_quiz(
    entry: dict,
    questions: list[dict],
    console: Console,
) -> None:
    """
    Mini-quiz sur les questions liées à l'entrée.
    Feedback immédiat après chaque réponse.
    """
    import random

    year_str = str(entry["year"])
    if entry.get("year_end"):
        year_str += f"–{entry['year_end']}"

    color = THEME_COLORS.get(entry["theme"], DEFAULT_COLOR)
    question_ids = entry.get("question_ids", [])
    q_map = {q["id"]: q for q in questions}
    quiz_questions = [q_map[qid] for qid in question_ids if qid in q_map]

    if not quiz_questions:
        console.print(Panel(
            Text("  Aucune question trouvée pour cette entrée.", style="yellow"),
            border_style="yellow",
        ))
        _getch()
        return

    score = 0

    for idx, q in enumerate(quiz_questions):
        console.clear()

        console.print(Panel(
            Text.assemble(
                (f"  🎯  Quiz — {year_str}  ", "bold white"),
                (f"Question {idx+1}/{len(quiz_questions)}", "dim"),
            ),
            border_style=color,
            padding=(0, 2),
        ))
        console.print()

        # Shuffle des réponses (correct_index toujours 0 dans le dataset)
        answers = list(q.get("answers", []))
        correct_answer = answers[0] if answers else ""
        random.shuffle(answers)
        correct_display = answers.index(correct_answer)

        # Question
        console.print(Panel(
            q.get("question", ""),
            border_style="dim",
            padding=(1, 2),
        ))
        console.print()

        # Options
        labels = ["A", "B", "C", "D"]
        for i, ans in enumerate(answers):
            console.print(
                Text.assemble(
                    (f"  [{labels[i]}] ", "bold cyan"),
                    (ans, "white"),
                )
            )
        console.print()
        console.print(Text("  Votre réponse : ", style="dim"), end="")

        # Lecture réponse
        chosen = None
        while chosen is None:
            key = _getch().upper()
            if key in labels[:len(answers)]:
                chosen = labels.index(key)

        # Feedback
        console.print()
        if chosen == correct_display:
            score += 1
            console.print(Panel(
                Text.assemble(
                    ("  ✓  Correct !\n\n", "bold green"),
                    (q.get("explication", ""), "white"),
                ),
                border_style="green",
                padding=(1, 2),
            ))
        else:
            correct_label = labels[correct_display]
            console.print(Panel(
                Text.assemble(
                    ("  ✗  Incorrect\n\n", "bold red"),
                    ("  Bonne réponse : ", "dim"),
                    (f"[{correct_label}] {correct_answer}\n\n", "bold yellow"),
                    (q.get("explication", ""), "white"),
                ),
                border_style="red",
                padding=(1, 2),
            ))

        console.print()
        console.print(Text("  [↵] question suivante", style="dim"))
        _getch()

    # Résultat mini-quiz
    console.clear()
    pct = int(score / len(quiz_questions) * 100)
    result_color = "green" if pct >= 80 else "yellow" if pct >= 50 else "red"
    console.print(Panel(
        Text.assemble(
            (f"  Score : {score}/{len(quiz_questions)}  ({pct}%)\n", f"bold {result_color}"),
            (f"  Période : {year_str} — {entry['label']}", "dim"),
        ),
        title="[bold]Résultat mini-quiz[/bold]",
        border_style=result_color,
        padding=(1, 2),
    ))
    console.print()
    console.print(Text("  [↵] retour timeline", style="dim"))
    _getch()


# ---------------------------------------------------------------------------
# Filtre par thème
# ---------------------------------------------------------------------------

def prompt_theme_filter(
    entries: list[dict],
    console: Console,
) -> Optional[str]:
    """
    Affiche les thèmes disponibles, retourne le thème choisi ou None (= tous).
    """
    console.clear()
    themes = sorted({e["theme"] for e in entries})

    console.print(Panel(
        Text("  Filtrer par thème", style="bold white"),
        border_style="blue",
        padding=(0, 2),
    ))
    console.print()

    for i, theme in enumerate(themes):
        color = THEME_COLORS.get(theme, DEFAULT_COLOR)
        console.print(Text.assemble(
            (f"  [{i+1}] ", "bold cyan"),
            (theme, color),
        ))

    console.print()
    console.print(Text.assemble(
        ("  [0] ", "bold cyan"), ("Tous les thèmes", "dim"),
    ))
    console.print()

    while True:
        key = _getch()
        if key == "0":
            return None
        try:
            idx = int(key) - 1
            if 0 <= idx < len(themes):
                return themes[idx]
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# Orchestrateur principal
# ---------------------------------------------------------------------------

def run_timeline(
    dataset_path: Optional[str] = None,
    timeline_path: Optional[str] = None,
    console: Optional[Console] = None,
    force_learn_only: bool = False,
) -> None:
    """
    Point d'entrée principal du module timeline.
    Appelé depuis __main__.py ou directement.

    dataset_path     : chemin vers le dataset QCM (pour build à la volée + quiz)
    timeline_path    : chemin vers timeline_dataset.json (optionnel)
    force_learn_only : si True (ex. --sample), ignore le dataset QCM et n'utilise
                       que timeline_dataset.json en mode Learning
    """
    if console is None:
        console = Console()

    # --- Résolution des sources ---
    questions: Optional[list[dict]] = None
    timeline: Optional[list[dict]] = None

    _dataset_path = dataset_path or DATASET_DEFAULT_PATH
    _timeline_path = timeline_path or TIMELINE_DATASET_PATH

    if not force_learn_only and os.path.exists(_dataset_path):
        try:
            questions = load_dataset(_dataset_path)
        except Exception:
            questions = None

    if os.path.exists(_timeline_path):
        timeline = load_timeline(_timeline_path)

    mode_available, entries = resolve_source(questions, timeline)

    # --- Aucune source ---
    if mode_available == "none":
        render_no_source_warning(console)
        return

    # --- Choix du mode ---
    if force_learn_only or mode_available != "quiz_or_learn":
        drill_mode = "learning"
    else:
        drill_mode = prompt_mode(console)

    # --- Boucle principale timeline ---
    cursor = 0
    window_start = 0
    active_filter: Optional[str] = None
    filtered_entries = entries[:]

    while True:
        render_timeline_table(filtered_entries, cursor, window_start, console)

        key = _getch()

        if key == "UP":
            if cursor > 0:
                cursor -= 1
                if cursor < window_start:
                    window_start = cursor

        elif key == "DOWN":
            if cursor < len(filtered_entries) - 1:
                cursor += 1
                if cursor >= window_start + WINDOW_SIZE:
                    window_start = cursor - WINDOW_SIZE + 1

        elif key in ("\r", "\n"):
            # Drill-down
            if filtered_entries:
                entry = filtered_entries[cursor]
                if drill_mode == "learning":
                    render_drilldown_learning(entry, questions, console)
                else:
                    if questions:
                        render_drilldown_quiz(entry, questions, console)
                    else:
                        # Fallback learning si quiz demandé mais plus de questions
                        render_drilldown_learning(entry, None, console)

        elif key.lower() == "f":
            chosen_theme = prompt_theme_filter(entries, console)
            active_filter = chosen_theme
            if active_filter:
                filtered_entries = [e for e in entries if e["theme"] == active_filter]
            else:
                filtered_entries = entries[:]
            cursor = 0
            window_start = 0

        elif key.lower() == "q":
            break