"""
civique.engine — Exam loop, live timer, question display, navigation, flagging.

Layout (two-column):
┌─────────────────────────────────────────────────────────────┐
│  CIVIQUE CLI   Question 12/40   [super-hard]   ⏱ 38:24     │
├──────────────┬──────────────────────────────────────────────┤
│ Nav panel    │  Question body + answer options              │
│ (left col)   │                                              │
├──────────────┴──────────────────────────────────────────────┤
│  Controls bar                                               │
└─────────────────────────────────────────────────────────────┘
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule

from .models import Question
from .menus import SessionConfig
from .ui import console, TRICOLOR, THEME_SHORT, getch


# ─── Answer state per question ────────────────────────────────────────────────

class AnswerStatus(Enum):
    UNANSWERED  = "unanswered"
    ANSWERED    = "answered"
    FLAGGED     = "flagged"     # [M] not sure, keep for review
    LOW_CONF    = "low_conf"    # [Tab] answered but not confident


@dataclass
class AnswerSlot:
    status: AnswerStatus = AnswerStatus.UNANSWERED
    chosen_index: Optional[int] = None   # 0-3 index into shuffled_answers
    time_spent_ms: int = 0
    _started_at: Optional[float] = field(default=None, repr=False)

    def start_timer(self):
        self._started_at = time.time()

    def pause_timer(self):
        if self._started_at is not None:
            self.time_spent_ms += int((time.time() - self._started_at) * 1000)
            self._started_at = None

    @property
    def is_answered(self) -> bool:
        return self.chosen_index is not None

    @property
    def chosen_letter(self) -> Optional[str]:
        if self.chosen_index is None:
            return None
        return "ABCD"[self.chosen_index]


# ─── Exam state ───────────────────────────────────────────────────────────────

@dataclass
class ExamState:
    config: SessionConfig
    slots: list = field(default_factory=list)
    current_idx: int = 0
    started_at: float = field(default_factory=time.time)
    finished: bool = False

    def __post_init__(self):
        self.slots = [AnswerSlot() for _ in self.config.question_pool]
        self.slots[0].start_timer()

    @property
    def current_question(self) -> Question:
        return self.config.question_pool[self.current_idx]

    @property
    def current_slot(self) -> AnswerSlot:
        return self.slots[self.current_idx]

    @property
    def elapsed_seconds(self) -> int:
        return int(time.time() - self.started_at)

    @property
    def remaining_seconds(self) -> int:
        return max(0, self.config.duration_seconds - self.elapsed_seconds)

    @property
    def unanswered_indices(self) -> list:
        return [i for i, s in enumerate(self.slots) if s.chosen_index is None]

    @property
    def answered_count(self) -> int:
        return sum(1 for s in self.slots if s.chosen_index is not None)

    def navigate_to(self, idx: int):
        self.slots[self.current_idx].pause_timer()
        self.current_idx = max(0, min(idx, len(self.slots) - 1))
        self.slots[self.current_idx].start_timer()

    def answer(self, letter: str):
        idx = "ABCD".index(letter.upper())
        slot = self.current_slot
        slot.chosen_index = idx
        if slot.status == AnswerStatus.UNANSWERED:
            slot.status = AnswerStatus.ANSWERED

    def toggle_flag(self):
        slot = self.current_slot
        if slot.status == AnswerStatus.FLAGGED:
            slot.status = AnswerStatus.ANSWERED if slot.is_answered else AnswerStatus.UNANSWERED
        else:
            slot.status = AnswerStatus.FLAGGED

    def toggle_low_conf(self):
        slot = self.current_slot
        if slot.status == AnswerStatus.LOW_CONF:
            slot.status = AnswerStatus.ANSWERED if slot.is_answered else AnswerStatus.UNANSWERED
        else:
            slot.status = AnswerStatus.LOW_CONF


# ─── Timer formatting ─────────────────────────────────────────────────────────

def _timer_style(seconds: int) -> str:
    if seconds <= 300:
        return "bold red"
    elif seconds <= 600:
        return "bold yellow"
    return "bold green"


def _timer_str(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"


# ─── Nav panel ────────────────────────────────────────────────────────────────

# Legend: separator + 5 symbol rows + trailing blank = 7 lines
_NAV_LEGEND_LINES = 7
# "Nav" header + blank = 2 lines
_NAV_HEADER_LINES = 2
_NAV_RESERVED = _NAV_HEADER_LINES + _NAV_LEGEND_LINES


def _nav_window_size() -> int:
    """
    How many question slots fit in the nav column given current terminal height.
    Accounts for: header panel (3) + body borders (2) + controls (2) + nav overhead.
    Minimum 5 slots always shown.
    """
    import shutil
    _, rows = shutil.get_terminal_size(fallback=(80, 24))
    available = rows - 3 - 2 - 2 - _NAV_RESERVED
    return max(5, available)


def _nav_symbol(slot: AnswerSlot, is_current: bool) -> str:
    if is_current:
        return f"[bold {TRICOLOR['gold']}]→[/]"
    if slot.status == AnswerStatus.FLAGGED:
        return "[bold yellow]?[/]"
    if slot.status == AnswerStatus.LOW_CONF:
        return "[dim]~[/]"
    if slot.is_answered:
        return f"[bold {TRICOLOR['green']}]✓[/]"
    return "[white]●[/]"


def _render_nav(state: ExamState) -> str:
    total = len(state.slots)
    cur   = state.current_idx
    win   = min(_nav_window_size(), total)

    # Center window on current, clamp to bounds
    half  = win // 2
    start = max(0, min(cur - half, total - win))
    end   = start + win  # exclusive

    lines = ["[dim]Nav[/]", ""]

    # ↑ more indicator
    if start > 0:
        lines.append(f" [dim]↑ {start} plus[/]")
    else:
        lines.append("")

    # Visible slots
    for i in range(start, end):
        sym = _nav_symbol(state.slots[i], i == cur)
        num = f"[dim]{i+1:02d}[/]"
        lines.append(f" {sym} {num}")

    # ↓ more indicator
    remaining = total - end
    if remaining > 0:
        lines.append(f" [dim]↓ {remaining} plus[/]")
    else:
        lines.append("")

    # Legend
    lines += [
        "",
        "[dim]──────[/]",
        f" [bold {TRICOLOR['gold']}]→[/] [dim]actuel[/]",
        f" [bold {TRICOLOR['green']}]✓[/] [dim]répondu[/]",
        " [bold yellow]?[/] [dim]marqué[/]",
        " [dim]~  peu conf.[/]",
        " [white]●[/] [dim]vide[/]",
    ]
    return "\n".join(lines)


# ─── Question panel ───────────────────────────────────────────────────────────

def _render_question(state: ExamState) -> str:
    q   = state.current_question
    slot = state.current_slot
    lines = []

    # Theme + type
    theme_short = THEME_SHORT.get(q.theme, q.theme)
    type_badge = (
        f"[bold {TRICOLOR['blue']}]CONNAISSANCE[/]"
        if q.type == "connaissance"
        else f"[bold {TRICOLOR['red']}]MISE EN SITUATION[/]"
    )
    lines += [f"[dim]{theme_short}[/]  {type_badge}", ""]

    # Question text
    lines += [f"[bold white]{q.question}[/]", ""]

    # Answer options
    for i, answer in enumerate(q.shuffled_answers):
        letter = "ABCD"[i]
        chosen = slot.chosen_index == i
        if chosen:
            lines.append(
                f"  [bold {TRICOLOR['gold']}]▶ {letter}[/]  [bold white]{answer}[/]"
            )
        else:
            lines.append(f"  [dim]  {letter}[/]  [white]{answer}[/]")

    lines.append("")

    # Status line
    if slot.chosen_index is not None:
        lbl = slot.chosen_letter
        status_str = {
            AnswerStatus.ANSWERED:  f"[{TRICOLOR['gold']}]· Réponse : {lbl}[/]",
            AnswerStatus.FLAGGED:   f"[yellow]? Réponse : {lbl}  — marqué pour révision[/]",
            AnswerStatus.LOW_CONF:  f"[dim]~ Réponse : {lbl}  — peu confiant·e[/]",
            AnswerStatus.UNANSWERED:"",
        }[slot.status]
    else:
        status_str = {
            AnswerStatus.FLAGGED:    "[yellow]? Marqué pour révision (sans réponse)[/]",
            AnswerStatus.UNANSWERED: "[dim]— Non répondu[/]",
            AnswerStatus.LOW_CONF:   "[dim]~ Peu confiant·e — Non répondu[/]",
            AnswerStatus.ANSWERED:   "",
        }[slot.status]

    lines.append(status_str)
    return "\n".join(lines)


# ─── Full screen draw ─────────────────────────────────────────────────────────

def _draw(state: ExamState, review_mode: bool = False):
    console.clear()

    # Header
    n       = state.current_idx + 1
    total   = state.config.total_questions
    mode    = state.config.mode.upper()
    rem     = state.remaining_seconds
    t_str   = _timer_str(rem)
    t_style = _timer_style(rem)

    # Blink effect in last 2 min
    if rem <= 120 and int(time.time()) % 2 == 0:
        timer_display = f"[{t_style} blink]⏱ {t_str}[/]"
    else:
        timer_display = f"[{t_style}]⏱ {t_str}[/]"

    header_text = (
        f"[bold {TRICOLOR['blue']}]CIVIQUE CLI[/]  [dim]·[/]  "
        f"Question [bold white]{n}/{total}[/]  [dim]·[/]  "
        f"[{TRICOLOR['gold']}]{mode}[/]  [dim]·[/]  "
        f"{timer_display}  [dim]·[/]  "
        f"[dim]{state.answered_count}/{total} répondues[/]"
    )
    console.print(Panel(header_text, border_style=TRICOLOR["blue"], padding=(0, 1)))

    # Body: two-column grid (nav left, question right)
    nav_lines = _render_nav(state).split("\n")
    q_lines   = _render_question(state).split("\n")
    max_rows  = max(len(nav_lines), len(q_lines))
    nav_lines += [""] * (max_rows - len(nav_lines))
    q_lines   += [""] * (max_rows - len(q_lines))

    body = Table.grid(padding=(0, 2))
    body.add_column(width=14)
    body.add_column()
    for nl, ql in zip(nav_lines, q_lines):
        body.add_row(nl, ql)

    console.print(Panel(body, border_style="dim", padding=(0, 1)))

    # Controls
    console.print(Rule(style="dim"))
    if review_mode:
        controls = (
            f"  [bold white][A-D][/][dim]Modifier réponse[/]  "
            f"[bold white][←→][/][dim]Question précédente/suivante[/]  "
            f"[bold white][M][/][dim]Marquer ?[/]  "
            f"[bold white][Tab][/][dim]Peu confiant ~[/]  "
            f"[bold white][↵/Q][/][dim]Retour au résumé[/]"
        )
    else:
        controls = (
            f"  [bold white][A-D][/][dim]Répondre[/]  "
            f"[bold white][←→][/][dim]Naviguer[/]  "
            f"[bold white][↵][/][dim]Suivant non-répondu[/]  "
            f"[bold white][G][/][dim]Aller à Qn[/]  "
            f"[bold white][M][/][dim]Marquer ?[/]  "
            f"[bold white][Tab][/][dim]Peu confiant ~[/]  "
            f"[bold white][?][/][dim]Aide[/]  "
            f"[bold white][Q][/][dim]Soumettre/Quitter[/]"
        )
    console.print(controls)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _submission_guard(state: ExamState) -> bool:
    """Warn about unanswered questions. Returns True = submit, False = go back."""
    unanswered = state.unanswered_indices
    if not unanswered:
        return True

    console.clear()
    nums = ", ".join(str(i + 1) for i in unanswered[:20])
    if len(unanswered) > 20:
        nums += f" … (+{len(unanswered) - 20})"

    console.print(Panel(
        f"[bold yellow]⚠  {len(unanswered)} question(s) sans réponse : {nums}[/]\n\n"
        f"[dim]Ces questions compteront comme fausses.[/]",
        border_style="yellow", padding=(1, 2)
    ))
    console.print()
    console.print(f"  [bold white][R][/] [dim]Revenir (premier sans réponse)[/]")
    console.print(f"  [bold white][S][/] [dim]Soumettre quand même[/]")
    console.print()

    while True:
        key = getch()
        if key.lower() == 'r':
            state.navigate_to(unanswered[0])
            return False
        elif key.lower() == 's':
            return True
        elif key == '\x03':
            sys.exit(0)


def _goto_prompt(state: ExamState):
    """Prompt to jump to a specific question number."""
    total = state.config.total_questions
    console.print(
        f"\n  [bold white]Aller à la question (1–{total}) :[/] ", end=""
    )
    try:
        raw = input().strip()
        n = int(raw)
        if 1 <= n <= total:
            state.navigate_to(n - 1)
        else:
            console.print(f"  [red]Numéro invalide (1–{total}).[/]")
            time.sleep(0.8)
    except (ValueError, EOFError):
        pass



# ─── Pre-submit review sub-loop ───────────────────────────────────────────────

def _review_loop(state: ExamState, indices: list[int]):
    """
    Constrained navigation over flagged/low-conf questions before submitting.
    A/B/C/D updates the answer in place — no auto-advance, no submit trigger.
    ←/→ moves only within the review subset.
    Enter or Q returns to the pre-submit screen.
    """
    pos = 0
    state.navigate_to(indices[pos])

    while True:
        _draw(state, review_mode=True)
        key = getch()

        if key.upper() in ('A', 'B', 'C', 'D'):
            letter_idx = "ABCD".index(key.upper())
            if letter_idx < len(state.current_question.shuffled_answers):
                state.current_slot.chosen_index = letter_idx

        elif key in ('RIGHT', 'l') and pos < len(indices) - 1:
            pos += 1
            state.navigate_to(indices[pos])

        elif key in ('LEFT', 'h') and pos > 0:
            pos -= 1
            state.navigate_to(indices[pos])

        elif key.lower() == 'm':
            state.toggle_flag()

        elif key == '\t':
            state.toggle_low_conf()

        elif key in ('\r', '\n') or key.lower() == 'q':
            break

        elif key == '\x03':
            sys.exit(0)


# ─── Pre-submit review screen ─────────────────────────────────────────────────

def _presubmit_screen(state: ExamState) -> bool:
    """
    Shown automatically when all questions are answered.
    Summarises flagged / low-conf counts, offers to review or submit.
    Returns True = submit, False = go back to exam.
    """
    total = len(state.slots)

    while True:
        # Recompute each iteration so changes made in review are reflected
        flagged  = [i for i, s in enumerate(state.slots) if s.status == AnswerStatus.FLAGGED]
        low_conf = [i for i, s in enumerate(state.slots) if s.status == AnswerStatus.LOW_CONF]

        console.clear()

        # Header
        console.print(Panel(
            f"[bold {TRICOLOR['gold']}]EXAMEN TERMINÉ — SOUMETTRE ?[/]",
            border_style=TRICOLOR["gold"], padding=(0, 2)
        ))
        console.print()

        # Completion status
        console.print(
            f"  [{TRICOLOR['green']}]✓[/]  [bold white]{total} / {total}[/]"
            f"  [dim]questions répondues[/]"
        )
        console.print()

        # Flagged / low-conf summary
        if flagged:
            nums = ", ".join(str(i + 1) for i in flagged[:10])
            if len(flagged) > 10: nums += "…"
            console.print(
                f"  [bold yellow]?[/]  [bold white]{len(flagged)}[/]"
                f"  [dim]marquée(s) pour révision : Q{nums}[/]"
            )
        if low_conf:
            nums = ", ".join(str(i + 1) for i in low_conf[:10])
            if len(low_conf) > 10: nums += "…"
            console.print(
                f"  [dim]~[/]  [bold white]{len(low_conf)}[/]"
                f"  [dim]peu confiante(s) : Q{nums}[/]"
            )

        if not flagged and not low_conf:
            console.print(f"  [dim]Aucune question marquée ou peu confiante.[/]")

        console.print()
        console.print(Rule(style="dim"))
        console.print()

        # Options — only show review if there's something to review
        if flagged or low_conf:
            console.print(
                f"  [bold white][R][/]  "
                f"[dim]Revoir les marquées / peu confiantes avant de soumettre[/]"
            )
        console.print(f"  [bold white][↵][/]  [dim]Soumettre maintenant[/]")
        console.print(f"  [bold white][←][/]  [dim]Retourner à l'examen[/]")
        console.print()

        key = getch()
        k   = key.lower()

        if key in ('\r', '\n'):
            return True   # submit

        elif k == 'r' and (flagged or low_conf):
            review_indices = sorted(set(flagged + low_conf))
            _review_loop(state, review_indices)
            # Loop continues: counts recomputed at top of next iteration

        elif key in ('LEFT', 'h', '\x1b'):
            return False  # back to exam

        elif key == '\x03':
            import sys
            sys.exit(0)


# ─── Public entry ─────────────────────────────────────────────────────────────

def run(config: SessionConfig, stats: dict) -> ExamState:
    """Run the exam loop. Returns final ExamState for scoring."""
    state = ExamState(config=config)

    while not state.finished:

        # Time up
        if state.remaining_seconds <= 0:
            console.clear()
            console.print(Panel(
                "[bold red]⏱ Temps écoulé !  L'examen est terminé automatiquement.[/]",
                border_style="red", padding=(1, 2)
            ))
            time.sleep(2)
            break

        _draw(state)
        key = getch()

        # Answer A/B/C/D
        if key.upper() in ('A', 'B', 'C', 'D'):
            n_opts = len(state.current_question.shuffled_answers)
            if "ABCD".index(key.upper()) < n_opts:
                state.answer(key.upper())
                is_last = state.current_idx == len(state.slots) - 1
                all_answered = state.answered_count == len(state.slots)

                if all_answered:
                    # All done — trigger pre-submit screen
                    if _presubmit_screen(state):
                        state.finished = True
                elif (not is_last
                        and state.current_slot.status == AnswerStatus.ANSWERED):
                    # Auto-advance on plain answers (not flagged/low-conf)
                    state.navigate_to(state.current_idx + 1)

        # Navigate
        elif key in ('LEFT', 'h') and state.current_idx > 0:
            state.navigate_to(state.current_idx - 1)
        elif key in ('RIGHT', 'l') and state.current_idx < len(state.slots) - 1:
            state.navigate_to(state.current_idx + 1)

        # Go-to
        elif key.lower() == 'g':
            _draw(state)
            _goto_prompt(state)

        # Flag / low-conf
        elif key.lower() == 'm':
            state.toggle_flag()
        elif key == '\t':
            state.toggle_low_conf()

        # Enter: advance to next unanswered/flagged, or pre-submit if all done
        elif key in ('\r', '\n'):
            if state.answered_count == len(state.slots):
                if _presubmit_screen(state):
                    state.finished = True
            else:
                # Find next question needing attention (unanswered or flagged)
                total = len(state.slots)
                cur   = state.current_idx
                candidates = list(range(cur + 1, total)) + list(range(0, cur))
                next_idx = None
                for i in candidates:
                    s = state.slots[i]
                    if s.chosen_index is None or s.status == AnswerStatus.FLAGGED:
                        next_idx = i
                        break
                if next_idx is not None:
                    state.navigate_to(next_idx)

        # Quit / submit
        elif key.lower() == 'q':
            if state.answered_count == len(state.slots):
                if _presubmit_screen(state):
                    state.finished = True
            else:
                _draw(state)
                if _submission_guard(state):
                    state.finished = True

        # In-exam help
        elif key == '?':
            from . import tutorial
            tutorial.show()

        # Ctrl+C
        elif key == '\x03':
            sys.exit(0)

    state.slots[state.current_idx].pause_timer()
    state.finished = True
    return state