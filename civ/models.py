"""
civique.models — Data models.
"""

import random
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Question:
    id: str
    source: str
    theme: str
    type: str               # connaissance | mise-situation
    difficulte: str         # standard | hard | piege
    question: str
    answers: list[str]      # answers[correct_index] is the correct one (always index 0 in source)
    correct_index: int
    explication: str
    needs_manual_review: bool = False
    qa_flag_type: Optional[str] = None

    # Runtime — populated by shuffle()
    shuffled_answers: list[str] = field(default_factory=list)
    shuffled_correct_index: int = 0

    def shuffle(self):
        """Randomize answer order, tracking the new position of the correct answer."""
        indices = list(range(len(self.answers)))
        random.shuffle(indices)
        self.shuffled_answers = [self.answers[i] for i in indices]
        self.shuffled_correct_index = indices.index(self.correct_index)

    @property
    def correct_answer(self) -> str:
        return self.shuffled_answers[self.shuffled_correct_index]

    @property
    def correct_letter(self) -> str:
        return "ABCD"[self.shuffled_correct_index]
