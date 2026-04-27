"""
civique.loader — JSON dataset loading and validation.
"""

import json
from pathlib import Path
from typing import Optional

from rich.table import Table
from rich import box

from .models import Question
from .ui import console, TRICOLOR, THEMES, THEME_REMAP, THEME_SHORT


class DataLoader:
    def __init__(self, path: str):
        self.path = Path(path)
        self.questions: list[Question] = []
        self.skipped: int = 0
        self.errors: list[str] = []

    # ── Public ────────────────────────────────────────────────────────────────

    def load(self) -> bool:
        if not self.path.exists():
            console.print(f"\n[bold red]✗ Fichier introuvable :[/] {self.path}")
            console.print("  [dim]Vérifiez le chemin ou utilisez --dataset.[/]\n")
            return False

        try:
            with open(self.path, encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as e:
            console.print(f"\n[bold red]✗ JSON invalide :[/] {e}\n")
            return False

        if not isinstance(raw, list):
            console.print("\n[bold red]✗ Format inattendu :[/] liste JSON attendue.\n")
            return False

        for item in raw:
            q = self._parse(item)
            if q:
                q.shuffle()
                self.questions.append(q)
            else:
                self.skipped += 1

        return len(self.questions) > 0

    def by_theme(self) -> dict[str, list[Question]]:
        result = {t: [] for t in THEMES}
        for q in self.questions:
            if q.theme in result:
                result[q.theme].append(q)
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

    # ── Private ───────────────────────────────────────────────────────────────

    def _parse(self, item: dict) -> Optional[Question]:
        for field in ["id", "question", "answers", "correct_index"]:
            if field not in item:
                self.errors.append(f"Champ manquant '{field}' dans {item.get('id', '?')}")
                return None

        if len(item["answers"]) < 4:
            return None  # incomplete distractors — skip silently

        theme = THEME_REMAP.get(item.get("theme", ""), item.get("theme", ""))
        explication = (item.get("explication") or "").strip() or "Pas d'explication disponible."

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
