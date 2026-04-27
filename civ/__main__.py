"""
civique.__main__ — Entry point. Run with: python -m civique
"""

import sys
from pathlib import Path

from .cli import parse_args, SAMPLE_DATASET
from .loader import DataLoader
from .ui import console, TRICOLOR, header_panel
from . import stats as stats_module
from . import tutorial
from .menus import theme_menu, mode_menu, build_config
from .engine import run as run_exam
from .results import score, persist, show as show_results


def show_startup(loader: DataLoader, dataset_path: str):
    console.clear()
    console.print(header_panel("CIVIQUE CLI", "Simulateur d'examen de naturalisation"))
    console.print()
    console.print(f"  [dim]Dataset :[/] [white]{dataset_path}[/]")
    if loader.skipped:
        console.print(
            f"  [yellow]⚠ {loader.skipped} question(s) ignorée(s) "
            f"(distracteurs incomplets)[/]"
        )
    for err in loader.errors[:5]:
        console.print(f"    [dim red]· {err}[/]")
    console.print()
    console.print(loader.stats_table())

    # Show difficulty distribution + last sessions if history exists
    stats_peek = stats_module.load()
    sessions   = stats_peek.get("sessions", [])
    dist       = stats_module.difficulty_distribution(stats_peek)
    total_seen = dist["standard"] + dist["hard"] + dist["piege"]

    if total_seen > 0:
        console.print(f"\n  [dim]Difficulté dynamique ({total_seen} questions vues) :[/]")
        console.print(
            f"    [{TRICOLOR['green']}]●[/] [dim]standard[/] [white]{dist['standard']}[/]  "
            f"[yellow]●[/] [dim]hard[/] [white]{dist['hard']}[/]  "
            f"[red]●[/] [dim]piège[/] [white]{dist['piege']}[/]"
        )

    if sessions:
        console.print(f"\n  [dim]Dernières sessions :[/]")
        for s in reversed(sessions[-3:]):
            icon = "✅" if s.get("passed") else "❌"
            console.print(
                f"    [dim]{s['date']}[/]  {icon}  "
                f"[white]{s['correct']}/{s['total']}[/]  "
                f"[dim]{s['mode']}  {s['elapsed']}[/]"
            )

    console.print(f"\n  [dim]Appuyez sur [bold white]Entrée[/] pour continuer…[/]\n")
    input()


def main():
    args = parse_args()
    stats = stats_module.load()

    # Resolve dataset path
    if args.sample:
        dataset_path = SAMPLE_DATASET
        console.print(
            f"\n[bold yellow]⚠ Mode démo — vous utilisez un dataset d'exemple ({SAMPLE_DATASET}).[/]\n"
            f"  [dim]Les scores et statistiques ne reflètent pas l'examen réel.[/]\n"
        )
    else:
        dataset_path = args.dataset
        if not Path(dataset_path).exists():
            console.print(
                f"\n[bold red]✗ Dataset introuvable :[/] [white]{dataset_path}[/]\n"
                f"  [dim]Utilisez [bold white]--sample[/] pour lancer la démo, "
                f"ou compilez un dataset au même format que [bold white]{SAMPLE_DATASET}[/].[/]\n"
            )
            sys.exit(1)

    # Load dataset
    console.print(f"\n[dim]Chargement de [white]{dataset_path}[/]…[/]")
    loader = DataLoader(dataset_path)
    if not loader.load():
        sys.exit(1)

    # Startup
    show_startup(loader, dataset_path)

    # Tutorial
    if stats_module.is_first_launch(stats) or args.tutorial:
        tutorial.show()
        stats_module.mark_launched(stats)
        stats_module.save(stats)

    # Theme → mode → config
    selected_themes = theme_menu(loader)
    mode, total_questions = mode_menu(preselected=args.mode)
    config = build_config(loader, selected_themes, mode, total_questions, stats)

    # Confirm start
    console.clear()
    console.print(header_panel("CIVIQUE CLI", "Prêt à démarrer"))
    console.print()
    console.print(f"  Mode       : [bold {TRICOLOR['gold']}]{config.mode.upper()}[/]")
    console.print(f"  Questions  : [bold white]{config.total_questions}[/]")
    mins = config.duration_seconds // 60
    console.print(f"  Durée      : [bold white]{mins} minutes[/]")
    console.print(f"  Thèmes     : [dim]{', '.join(config.selected_themes)}[/]")
    console.print()
    console.print(f"  [dim]Appuyez sur [bold white]Entrée[/] pour démarrer le chronomètre…[/]")
    input()

    # Run exam
    state = run_exam(config, stats)

    # Score + persist
    session = score(state)
    persist(session, stats)

    # Show results + review
    show_results(session)


if __name__ == "__main__":
    main()