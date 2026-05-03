"""
civique.outside — Convex sync client.

Mirrors the useStats.ts composable pattern exactly:
  push_session(syncKey, results) → recordSession mutation (delta)
  pull(syncKey)                  → getStats query (authoritative state)

Convex is the single source of truth when sync is ON.
No merge logic — push delta, pull authoritative, overwrite local.
"""

import os
import json
from pathlib import Path
from typing import Optional

from .ui import console, TRICOLOR

# ─── Config ───────────────────────────────────────────────────────────────────

def _get_convex_url() -> str:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    return os.getenv("CONVEX_URL", "").rstrip("/")

TIMEOUT = 10  # seconds


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def _url(path: str) -> str:
    url = _get_convex_url()
    if not url:
        raise RuntimeError(
            "CONVEX_URL manquant. "
            "Ajoutez CONVEX_URL=https://<deployment>.convex.cloud dans votre .env"
        )
    return f"{url}{path}"


def _query(function_name: str, args: dict) -> dict:
    """Call a Convex query function via HTTP API."""
    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx requis pour le sync — pip install httpx")
    resp = httpx.post(
        _url("/api/query"),
        json={"path": function_name, "args": args},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") == "error":
        raise RuntimeError(f"Convex query error: {data.get('errorMessage', data)}")
    return data.get("value", {})


def _mutation(function_name: str, args: dict) -> None:
    """Call a Convex mutation function via HTTP API."""
    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx requis pour le sync — pip install httpx")
    resp = httpx.post(
        _url("/api/mutation"),
        json={"path": function_name, "args": args},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") == "error":
        raise RuntimeError(f"Convex mutation error: {data.get('errorMessage', data)}")


# ─── Core sync operations ─────────────────────────────────────────────────────

def pull(sync_key: str) -> dict:
    """
    Fetch authoritative stats from Convex for this syncKey.
    Returns StatsMap: { questionId: {views, correct, attempts, totalTimeMs} }
    """
    return _query("stats:getStats", {"syncKey": sync_key})


def push_session(sync_key: str, results: list[dict]) -> None:
    """
    Push session results as a delta to Convex.
    results: [{ questionId, correct (bool), timeMs }]
    Mirrors useStats.ts pushSession call exactly.
    """
    _mutation("stats:recordSession", {
        "syncKey": sync_key,
        "results": results,
    })


# ─── Local ↔ Convex conversion ────────────────────────────────────────────────

def local_to_results(local_stats: dict, question_ids: list[str]) -> list[dict]:
    """
    Convert local AnswerSlot results (from a finished session) into the
    delta payload format expected by recordSession.

    Called by results.py after scoring, before push_session.
    """
    raise NotImplementedError(
        "Use build_results_payload() from results.py — "
        "this function is intentionally unused."
    )


def convex_to_local(remote: dict) -> dict:
    """
    Convert Convex StatsMap → our local stats['questions'] format.

    Convex:  { views, correct, attempts, totalTimeMs }
    Local:   { vues, erreurs, correct, temps_moyen_ms, difficulte_calculee }

    Notes:
    - erreurs = views - correct
    - temps_moyen_ms = totalTimeMs / views  (or 0 if views=0)
    - difficulte_calculee is recomputed locally after pull (never synced)
    """
    from . import stats as stats_module

    converted = {}
    for q_id, r in remote.items():
        views = r.get("views", 0)
        correct = r.get("correct", 0)
        total_ms = r.get("totalTimeMs", 0)

        avg_ms = total_ms // views if views > 0 else 0
        erreurs = views - correct

        # Build entry matching our local schema
        entry = {
            "vues":   views,
            "erreurs": erreurs,
            "correct": correct,
            "temps_moyen_ms": avg_ms,
            "difficulte_calculee": "standard",  # will be recomputed below
        }
        converted[q_id] = entry

    # Recompute difficulte_calculee for all entries using our local formula
    fake_stats = {"questions": converted}
    for q_id in converted:
        score = stats_module.difficulty_score(fake_stats, q_id)
        converted[q_id]["difficulte_calculee"] = stats_module.score_to_label(score)

    return converted


def build_results_payload(session_results: list) -> list[dict]:
    """
    Convert a list of QuestionResult (from results.py ScoredSession)
    into the delta payload for push_session.

    Each item: { questionId, correct (bool), timeMs (int) }
    """
    return [
        {
            "questionId": r.question.id,
            "correct":    r.correct,
            "timeMs":     r.time_spent_ms,
        }
        for r in session_results
    ]


# ─── Full sync cycle ──────────────────────────────────────────────────────────

def sync_after_session(
    sync_key: str,
    session_results: list,
    stats: dict,
) -> bool:
    """
    Full sync cycle after a completed exam session (mirrors useStats.ts recordSession):
      1. Push delta (session results) → Convex accumulates server-side
      2. Pull authoritative state → overwrite local questions stats
      3. Recompute difficulte_calculee for all pulled questions
      4. Return True on success, False on any network error.

    stats dict is mutated in-place.
    Caller (results.py / __main__.py) must call stats_module.save() after.
    """
    from . import stats as stats_module

    try:
        # 1. Push delta
        payload = build_results_payload(session_results)
        push_session(sync_key, payload)

        # 2. Pull authoritative
        remote = pull(sync_key)

        # 3. Convert + overwrite local question stats
        converted = convex_to_local(remote)
        stats["questions"].update(converted)

        return True

    except RuntimeError as e:
        console.print(f"\n  [yellow]⚠ Sync Convex échoué : {e}[/]")
        return False
    except httpx.RequestError as e:
        console.print(f"\n  [yellow]⚠ Sync réseau impossible : {e}[/]")
        return False
    except httpx.HTTPStatusError as e:
        console.print(
            f"\n  [yellow]⚠ Sync HTTP {e.response.status_code} : {e.response.text[:80]}[/]"
        )
        return False


def sync_pull_only(sync_key: str, stats: dict) -> bool:
    """
    Pull-only sync — used on startup when sync is enabled.
    Overwrites local question stats with Convex authoritative state.
    Returns True on success.
    """
    from . import stats as stats_module

    try:
        remote = pull(sync_key)
        converted = convex_to_local(remote)
        stats["questions"].update(converted)
        console.print(
            f"  [{TRICOLOR['green']}]↓[/] "
            f"[dim]Sync Convex : {len(converted)} questions récupérées[/]"
        )
        return True

    except RuntimeError as e:
        console.print(f"  [yellow]⚠ Sync Convex échoué : {e}[/]")
        return False
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        console.print(f"  [yellow]⚠ Sync réseau impossible : {e}[/]")
        return False
