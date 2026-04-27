"""
civique.stats — Persistent per-question stats and session history.
Stored in ~/.civique_stats.json
"""

import json
from pathlib import Path

from .ui import console

STATS_FILE = Path.home() / ".civique_stats.json"
MAX_SESSIONS = 10

# Difficulty thresholds (matches spec)
THRESHOLD_STANDARD = 0.3   # score < 0.3  → standard (maîtrisé)
THRESHOLD_HARD     = 0.6   # score 0.3–0.6 → hard    (fragile)
                            # score > 0.6  → piege   (zone rouge)

SPEED_MAX_MS   = 60_000    # 60s = max normalization for response time
VIEWS_MAX      = 20        # 20 views = max normalization for exposure count


def load() -> dict:
    if STATS_FILE.exists():
        try:
            with open(STATS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "first_launch": True,
        "questions": {},   # question_id → { vues, erreurs, temps_moyen_ms }
        "sessions": [],    # list of session summaries (max 10)
    }


def save(stats: dict):
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        console.print(f"[dim yellow]⚠ Sauvegarde impossible : {e}[/]")


def record_question(stats: dict, question_id: str, correct: bool, elapsed_ms: int):
    """
    Update per-question stats after an answer, then recompute difficulte_calculee.
    Stored structure per question:
    {
        "vues": 5,
        "erreurs": 3,
        "temps_moyen_ms": 28000,
        "difficulte_calculee": "hard"
    }
    """
    q = stats["questions"].setdefault(question_id, {
        "vues": 0,
        "erreurs": 0,
        "temps_moyen_ms": 0,
        "difficulte_calculee": "standard",
    })
    q["vues"] += 1
    if not correct:
        q["erreurs"] += 1
    # Rolling average of response time
    prev_avg = q["temps_moyen_ms"]
    q["temps_moyen_ms"] = int((prev_avg * (q["vues"] - 1) + elapsed_ms) / q["vues"])
    # Recompute and persist difficulty label
    score = difficulty_score(stats, question_id)
    q["difficulte_calculee"] = score_to_label(score)


def record_session(stats: dict, session: dict):
    """Append a session summary, keeping only the last MAX_SESSIONS."""
    stats["sessions"].append(session)
    stats["sessions"] = stats["sessions"][-MAX_SESSIONS:]


def score_to_label(score: float) -> str:
    """Convert numeric difficulty score to label per spec thresholds."""
    if score < THRESHOLD_STANDARD:
        return "standard"
    elif score < THRESHOLD_HARD:
        return "hard"
    return "piege"


def difficulty_score(stats: dict, question_id: str) -> float:
    """
    Dynamic difficulty score for smart question weighting.
    score = error_rate×0.5 + speed_norm×0.3 + views_norm×0.2
    Returns 0.0 (easy/unknown) → 1.0 (hardest).
    New questions return 0.5 (treated as medium until data exists).
    """
    q = stats["questions"].get(question_id)
    if not q or q["vues"] == 0:
        return 0.5  # unknown → treat as medium

    error_rate = q["erreurs"] / q["vues"]
    speed_norm = min(q["temps_moyen_ms"] / SPEED_MAX_MS, 1.0)
    views_norm = min(q["vues"] / VIEWS_MAX, 1.0)

    return error_rate * 0.5 + speed_norm * 0.3 + views_norm * 0.2


def is_first_launch(stats: dict) -> bool:
    return stats.get("first_launch", True)


def mark_launched(stats: dict):
    stats["first_launch"] = False


def difficulty_distribution(stats: dict) -> dict[str, int]:
    """Count questions per difficulty label — for startup display."""
    dist = {"standard": 0, "hard": 0, "piege": 0, "new": 0}
    for q in stats["questions"].values():
        label = q.get("difficulte_calculee", "standard")
        if q.get("vues", 0) == 0:
            dist["new"] += 1
        elif label in dist:
            dist[label] += 1
    return dist