"""
civique.__main__ — Entry point. Run with: python -m civique
"""

import sys
from pathlib import Path

from .cli import parse_args, SAMPLE_DATASET
from .loader import DataLoader
from .ui import console, TRICOLOR, header_panel, getch
from . import stats as stats_module
from . import tutorial
from .menus import theme_menu, mode_menu, build_config
from .engine import run as run_exam
from .results import score, persist, show as show_results
from . import sync as sync_module
from .outside import sync_pull_only


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
    dataset_ids = {q.id for q in loader.questions}
    dist        = stats_module.difficulty_distribution(stats_peek, question_ids=dataset_ids)
    total_seen  = dist["standard"] + dist["hard"] + dist["piege"]

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

    # Sync status line
    console.print()
    console.print(sync_module.status_line(stats_peek))
    console.print()
    console.print(f"  [dim]Appuyez sur [bold white]Entrée[/] pour continuer, ou [bold white][S][/] pour gérer le sync…[/]\n")

    while True:
        key = getch()
        if key.lower() == 's':
            changed = sync_module.toggle_screen(stats_peek)
            if changed:
                stats_module.save(stats_peek)
                # Pull on sync enable
                if sync_module.is_enabled(stats_peek):
                    sync_pull_only(sync_module.get_key(stats_peek), stats_peek)
                    stats_module.save(stats_peek)
            # Redraw startup screen
            show_startup(loader, dataset_path)
            return
        elif key in ('\r', '\n', ''):
            break


def main():
    args = parse_args()
    stats = stats_module.load()

    # Resolve dataset path
    if args.sample:
        dataset_path = SAMPLE_DATASET
        console.print(
            f"\n[bold yellow]⚠ Vous utilisez le dataset d'exemple ({SAMPLE_DATASET}) — 40 questions QA-ées, tirage réel simulé.[/]\n"
            f"  [dim]Pour accéder au dataset complet (~586 questions), fournissez un fichier via --dataset.[/]\n"
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

    # Tutorial (first launch only, outside the session loop)
    if stats_module.is_first_launch(stats) or args.tutorial:
        show_startup(loader, dataset_path)
        tutorial.show()
        stats_module.mark_launched(stats)
        stats_module.save(stats)

    # ── Session loop ──────────────────────────────────────────────────────────
    while True:
        stats = stats_module.load()

        # Home screen
        show_startup(loader, dataset_path)

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

        # Results — True loops back to home, False exits
        if not show_results(session):
            break


if __name__ == "__main__":
    main()