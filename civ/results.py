"""
civique.results — Scoring, session save, and interactive review loop.

Flow:
  score()   → builds ScoredSession from ExamState
  show()    → displays results screen
  review()  → interactive per-question review (incorrect / flagged / all)
"""

import time
from dataclasses import dataclass, field
from datetime import datetime

from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich.text import Text
from rich import box

from .engine import ExamState, AnswerStatus
from .models import Question
from .ui import console, TRICOLOR, THEME_SHORT, getch
from . import stats as stats_module


PASS_THRESHOLD = 32   # out of 40 (80%)
PASS_SCORE_40  = 32


# ─── Scored session ───────────────────────────────────────────────────────────

@dataclass
class QuestionResult:
    question:      Question
    chosen_index:  int | None      # index into shuffled_answers
    correct:       bool
    status:        AnswerStatus
    time_spent_ms: int

    @property
    def chosen_answer(self) -> str:
        if self.chosen_index is None:
            return "— Sans réponse"
        return self.question.shuffled_answers[self.chosen_index]

    @property
    def correct_answer(self) -> str:
        return self.question.correct_answer

    @property
    def chosen_letter(self) -> str:
        if self.chosen_index is None:
            return "—"
        return "ABCD"[self.chosen_index]

    @property
    def correct_letter(self) -> str:
        return self.question.correct_letter


@dataclass
class ScoredSession:
    mode:            str
    total:           int
    elapsed_seconds: int
    duration_seconds: int
    results:         list[QuestionResult] = field(default_factory=list)

    @property
    def correct_count(self) -> int:
        return sum(1 for r in self.results if r.correct)

    @property
    def incorrect(self) -> list[QuestionResult]:
        return [r for r in self.results if not r.correct]

    @property
    def flagged(self) -> list[QuestionResult]:
        return [r for r in self.results if r.status == AnswerStatus.FLAGGED]

    @property
    def low_conf(self) -> list[QuestionResult]:
        return [r for r in self.results if r.status == AnswerStatus.LOW_CONF]

    @property
    def unanswered(self) -> list[QuestionResult]:
        return [r for r in self.results if r.chosen_index is None]

    @property
    def score_40(self) -> int:
        """Normalize score to /40 for non-40-question exams."""
        if self.total == 0:
            return 0
        return round((self.correct_count / self.total) * 40)

    @property
    def passed(self) -> bool:
        return self.score_40 >= PASS_SCORE_40

    @property
    def pct(self) -> int:
        if self.total == 0:
            return 0
        return round((self.correct_count / self.total) * 100)

    def by_theme(self) -> dict[str, dict]:
        """Returns {theme: {correct, total}} for per-theme breakdown."""
        themes: dict[str, dict] = {}
        for r in self.results:
            t = r.question.theme
            if t not in themes:
                themes[t] = {"correct": 0, "total": 0}
            themes[t]["total"] += 1
            if r.correct:
                themes[t]["correct"] += 1
        return themes


# ─── Scoring ──────────────────────────────────────────────────────────────────

def score(state: ExamState) -> ScoredSession:
    """Build a ScoredSession from a finished ExamState."""
    results = []
    for i, (q, slot) in enumerate(zip(state.config.question_pool, state.slots)):
        # KEY: compare against shuffled_correct_index, not source correct_index
        correct = (
            slot.chosen_index is not None
            and slot.chosen_index == q.shuffled_correct_index
        )
        results.append(QuestionResult(
            question=q,
            chosen_index=slot.chosen_index,
            correct=correct,
            status=slot.status,
            time_spent_ms=slot.time_spent_ms,
        ))
    return ScoredSession(
        mode=state.config.mode,
        total=state.config.total_questions,
        elapsed_seconds=state.elapsed_seconds,
        duration_seconds=state.config.duration_seconds,
        results=results,
    )


def persist(session: ScoredSession, stats: dict):
    """Record per-question stats + session summary into stats dict and save."""
    for r in session.results:
        stats_module.record_question(
            stats,
            r.question.id,
            correct=r.correct,
            elapsed_ms=r.time_spent_ms,
        )

    m, s = divmod(session.elapsed_seconds, 60)
    stats_module.record_session(stats, {
        "date":     datetime.now().strftime("%Y-%m-%d %H:%M"),
        "mode":     session.mode,
        "total":    session.total,
        "correct":  session.correct_count,
        "score_40": session.score_40,
        "elapsed":  f"{m:02d}:{s:02d}",
        "passed":   session.passed,
    })
    stats_module.save(stats)


# ─── Results screen ───────────────────────────────────────────────────────────

def _bar(correct: int, total: int, width: int = 20) -> str:
    if total == 0:
        return "[dim]" + "░" * width + "[/]"
    filled = round((correct / total) * width)
    empty  = width - filled
    color  = TRICOLOR["green"] if correct / total >= 0.8 else (
             "yellow" if correct / total >= 0.6 else "red"
    )
    return f"[{color}]{'█' * filled}[/][dim]{'░' * empty}[/]"


def show(session: ScoredSession):
    """Display the full results screen."""
    console.clear()

    # ── Verdict banner ────────────────────────────────────────────────────────
    if session.passed:
        verdict_style = TRICOLOR["green"]
        verdict_icon  = "✅"
        verdict_text  = "REÇU·E"
    else:
        verdict_style = "red"
        verdict_icon  = "❌"
        verdict_text  = "INSUFFISANT"

    m, s = divmod(session.elapsed_seconds, 60)
    dm, ds = divmod(session.duration_seconds, 60)

    banner = Text(justify="center")
    banner.append(f"{verdict_icon}  {verdict_text}\n", style=f"bold {verdict_style}")
    banner.append(
        f"Score : {session.correct_count} / {session.total}  "
        f"({session.pct}%)",
        style="bold white"
    )
    if session.total != 40:
        banner.append(
            f"\n  Équivalent /40 : {session.score_40} / 40  "
            f"(seuil {PASS_SCORE_40}/40)",
            style="dim"
        )
    console.print(Panel(banner, border_style=verdict_style, padding=(1, 4)))
    console.print()

    # ── Summary table ─────────────────────────────────────────────────────────
    summary = Table.grid(padding=(0, 3))
    summary.add_column(style="dim")
    summary.add_column(style="bold white")
    summary.add_column(style="dim")
    summary.add_column(style="bold white")

    summary.add_row(
        "Mode",        session.mode.upper(),
        "Temps",       f"{m:02d}:{s:02d} / {dm:02d}:{ds:02d}",
    )
    summary.add_row(
        "Correctes",   f"[{TRICOLOR['green']}]{session.correct_count}[/]",
        "Incorrectes", f"[red]{len(session.incorrect)}[/]",
    )
    summary.add_row(
        "Marquées ?",  f"[yellow]{len(session.flagged)}[/]",
        "Peu conf. ~", f"[dim]{len(session.low_conf)}[/]",
    )
    summary.add_row(
        "Sans réponse", f"[dim]{len(session.unanswered)}[/]",
        "Seuil requis", f"{PASS_SCORE_40}/40  (80%)",
    )
    console.print(Panel(summary, border_style="dim", padding=(0, 2)))
    console.print()

    # ── Per-theme breakdown ───────────────────────────────────────────────────
    by_theme = session.by_theme()
    if by_theme:
        theme_table = Table(box=box.SIMPLE, show_header=True,
                            header_style=f"bold {TRICOLOR['blue']}")
        theme_table.add_column("Thème", style="white")
        theme_table.add_column("Score", justify="right", style="bold white")
        theme_table.add_column("", no_wrap=True)

        for theme, counts in by_theme.items():
            c, t = counts["correct"], counts["total"]
            short = THEME_SHORT.get(theme, theme)
            theme_table.add_row(short, f"{c}/{t}", _bar(c, t, 16))

        console.print(theme_table)
        console.print()

    # ── Review options ────────────────────────────────────────────────────────
    console.print(Rule(style="dim"))
    options = []
    if session.incorrect:
        options.append(("[I]", f"Réviser les incorrectes ({len(session.incorrect)})"))
    if session.flagged:
        options.append(("[M]", f"Réviser les marquées ({len(session.flagged)})"))
    if session.low_conf:
        options.append(("[Tab]", f"Réviser les peu confiantes ({len(session.low_conf)})"))
    options.append(("[T]", "Réviser toutes les questions"))
    options.append(("[Q]", "Quitter"))

    for key, label in options:
        console.print(f"  [bold white]{key}[/] [dim]{label}[/]")
    console.print()

    # ── Wait for choice ───────────────────────────────────────────────────────
    while True:
        key = getch()
        k = key.lower()
        if k == 'i' and session.incorrect:
            review(session.incorrect, "Incorrectes", session)
            break
        elif k == 'm' and session.flagged:
            review(session.flagged, "Marquées", session)
            break
        elif key == '\t' and session.low_conf:
            review(session.low_conf, "Peu confiantes", session)
            break
        elif k == 't':
            review(session.results, "Toutes", session)
            break
        elif k in ('q', '\x03'):
            break


# ─── Interactive review ───────────────────────────────────────────────────────

def _review_question(r: QuestionResult, idx: int, total: int):
    """Render one question in review mode."""
    console.clear()

    # Header
    status_label = {
        AnswerStatus.ANSWERED:   f"[dim]Répondu[/]",
        AnswerStatus.FLAGGED:    f"[yellow]Marqué ?[/]",
        AnswerStatus.LOW_CONF:   f"[dim]Peu confiant ~[/]",
        AnswerStatus.UNANSWERED: f"[dim]Sans réponse[/]",
    }[r.status]

    verdict = (
        f"[bold {TRICOLOR['green']}]✓ Correct[/]"
        if r.correct else
        f"[bold red]✗ Incorrect[/]"
    )

    secs = r.time_spent_ms // 1000
    ms   = r.time_spent_ms % 1000
    time_str = f"{secs}s {ms//100}ms" if secs < 60 else f"{secs//60}m{secs%60:02d}s"

    header_text = (
        f"[bold {TRICOLOR['blue']}]RÉVISION[/]  [dim]·[/]  "
        f"[white]{idx}/{total}[/]  [dim]·[/]  "
        f"{verdict}  [dim]·[/]  {status_label}  [dim]·[/]  "
        f"[dim]Temps : {time_str}[/]"
    )
    console.print(Panel(header_text, border_style=TRICOLOR["blue"], padding=(0, 1)))
    console.print()

    # Theme + type
    q = r.question
    theme_short = THEME_SHORT.get(q.theme, q.theme)
    type_badge = (
        f"[bold {TRICOLOR['blue']}]CONNAISSANCE[/]"
        if q.type == "connaissance"
        else f"[bold {TRICOLOR['red']}]MISE EN SITUATION[/]"
    )
    console.print(f"  [dim]{theme_short}[/]  {type_badge}")
    console.print()

    # Question
    console.print(f"  [bold white]{q.question}[/]")
    console.print()

    # All answer options with annotations
    for i, answer in enumerate(q.shuffled_answers):
        letter = "ABCD"[i]
        is_correct  = (i == q.shuffled_correct_index)
        is_chosen   = (i == r.chosen_index)

        if is_correct and is_chosen:
            # Correct and chosen
            line = f"  [bold {TRICOLOR['green']}]✓ {letter}[/]  [bold white]{answer}[/]  [dim]← votre réponse ✓[/]"
        elif is_correct:
            # Correct but not chosen
            line = f"  [bold {TRICOLOR['green']}]✓ {letter}[/]  [bold white]{answer}[/]  [dim]← bonne réponse[/]"
        elif is_chosen:
            # Chosen but wrong
            line = f"  [bold red]✗ {letter}[/]  [dim]{answer}[/]  [dim]← votre réponse[/]"
        else:
            line = f"  [dim]  {letter}  {answer}[/]"

        console.print(line)

    console.print()

    # Explication
    if q.explication and q.explication != "Pas d'explication disponible.":
        console.print(Panel(
            f"[dim]Explication :[/]\n[white]{q.explication}[/]",
            border_style="dim", padding=(0, 2)
        ))
    else:
        console.print(f"  [dim]Pas d'explication disponible.[/]")

    console.print()


def review(items: list[QuestionResult], label: str, session: ScoredSession):
    """
    Interactive review loop over a list of QuestionResults.
    [←/→] navigate, [Q] back to results.
    """
    if not items:
        return

    idx = 0

    while True:
        r = items[idx]
        _review_question(r, idx + 1, len(items))

        # Controls
        console.print(Rule(style="dim"))
        nav_parts = []
        if idx > 0:
            nav_parts.append(f"[bold white][←][/][dim] Précédent[/]")
        if idx < len(items) - 1:
            nav_parts.append(f"[bold white][→][/][dim] Suivant[/]")
        nav_parts.append(f"[bold white][Q][/][dim] Retour résultats[/]")
        console.print("  " + "  ".join(nav_parts))
        console.print()

        key = getch()
        k   = key.lower()

        if key in ('RIGHT', 'l') and idx < len(items) - 1:
            idx += 1
        elif key in ('LEFT', 'h') and idx > 0:
            idx -= 1
        elif k in ('q', '\x03'):
            # Return to results screen
            show(session)
            return