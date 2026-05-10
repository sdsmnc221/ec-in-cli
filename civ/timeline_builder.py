"""
civique/timeline_builder.py
Extraction de dates depuis les explications du dataset civique.
Produit une liste d'entrées timeline triées chronologiquement.
Importable par civique/timeline.py pour build à la volée.
"""

import re
import os
import json
import anthropic
from typing import Optional

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Années plausibles pour l'histoire civique française
YEAR_MIN = 400
YEAR_MAX = 2030

# Mois français pour regex dates longues
_MOIS = (
    r"janvier|février|fevrier|mars|avril|mai|juin|"
    r"juillet|août|aout|septembre|octobre|novembre|décembre|decembre"
)

# Regex année isolée (4 chiffres, bordures de mot)
RE_YEAR = re.compile(r"\b(1[0-9]{3}|20[0-2][0-9])\b")

# Regex période explicite : "de 1914 à 1918" / "1914-1918" / "entre 1914 et 1918"
RE_PERIOD = re.compile(
    r"(?:de\s+|entre\s+)?"
    r"\b(1[0-9]{3}|20[0-2][0-9])\b"
    r"(?:\s*[-–]\s*|\s+à\s+|\s+et\s+)"
    r"\b(1[0-9]{3}|20[0-2][0-9])\b"
)

# Regex date longue : "10 mai 1981"
RE_DATE_LONG = re.compile(
    r"\b\d{1,2}\s+(?:" + _MOIS + r")\s+(1[0-9]{3}|20[0-2][0-9])\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Extraction de dates
# ---------------------------------------------------------------------------

def extract_dates(explication: str) -> tuple[Optional[int], Optional[int]]:
    """
    Extrait (year, year_end) depuis une explication.
    Priorité : période > date longue > année isolée.
    Retourne (None, None) si aucune date trouvée.
    """
    # 1. Cherche une période explicite en premier
    m_period = RE_PERIOD.search(explication)
    if m_period:
        y1, y2 = int(m_period.group(1)), int(m_period.group(2))
        if YEAR_MIN <= y1 <= YEAR_MAX and YEAR_MIN <= y2 <= YEAR_MAX and y2 > y1:
            return y1, y2

    # 2. Date longue → extrait l'année
    m_long = RE_DATE_LONG.search(explication)
    if m_long:
        y = int(m_long.group(1))
        if YEAR_MIN <= y <= YEAR_MAX:
            return y, None

    # 3. Première année isolée trouvée
    for m in RE_YEAR.finditer(explication):
        y = int(m.group(1))
        if YEAR_MIN <= y <= YEAR_MAX:
            return y, None

    return None, None


def extract_raw_label(explication: str, year: int) -> str:
    """
    Extrait un contexte brut ±10 mots autour de la première occurrence de year.
    Fallback : 15 premiers mots de l'explication.
    """
    words = explication.split()
    year_str = str(year)

    for i, word in enumerate(words):
        if year_str in word:
            start = max(0, i - 10)
            end = min(len(words), i + 11)
            snippet = " ".join(words[start:end]).strip()
            # Nettoie ponctuation en début/fin
            snippet = re.sub(r"^[,;:.\-–\s]+|[,;:\-–\s]+$", "", snippet)
            return snippet

    # Fallback
    return " ".join(words[:15])


# ---------------------------------------------------------------------------
# Label + Explication Haiku
# ---------------------------------------------------------------------------

def review_with_haiku(
    raw_labels: list[str],
    explications: list[str],
    year: int,
    year_end: Optional[int],
    client: anthropic.Anthropic,
) -> tuple[Optional[str], Optional[str]]:
    """
    Passe toutes les raw_labels et explications d'une même année à Haiku.
    Retourne (label, explication) en un seul appel API.
    - label       : 5–10 mots, factuel
    - explication : prose courte (2–3 phrases) synthétisant les explications sources
    Retourne (None, None) si l'appel échoue.
    """
    period_str = f"{year}–{year_end}" if year_end else str(year)

    raw_block  = "\n".join(f"- {lbl}" for lbl in raw_labels)
    expl_block = "\n\n".join(f"• {expl}" for expl in explications)

    prompt = (
        f"Tu es un assistant pédagogique pour l'examen civique français.\n"
        f"Voici des extraits liés à la période {period_str}.\n\n"
        f"Extraits courts :\n{raw_block}\n\n"
        f"Explications complètes :\n{expl_block}\n\n"
        f"Réponds UNIQUEMENT avec un objet JSON valide, sans markdown, sans backticks :\n"
        f'{{"label": "<5 à 10 mots, factuel, sans ponctuation finale>", '
        f'"explication": "<2 à 3 phrases en français synthétisant l\'événement>"}}'
    )

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        import json as _json
        raw = response.content[0].text.strip()
        data = _json.loads(raw)
        label      = data.get("label", "").strip() or None
        explication = data.get("explication", "").strip() or None
        # Validation label
        if label and len(label.split()) > 15:
            label = None
        return label, explication
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Build principal
# ---------------------------------------------------------------------------

def build_timeline_entries(
    questions: list[dict],
    use_haiku: bool = True,
    verbose: bool = False,
) -> list[dict]:
    """
    Pipeline complet :
    1. Extrait dates depuis chaque explication
    2. Groupe par année (déduplication)
    3. Collecte raw_labels par groupe
    4. Passe à Haiku (si use_haiku=True) → label final
    5. Retourne liste triée chronologiquement

    Chaque entrée :
    {
        "year": int,
        "year_end": int | null,
        "label": str,
        "raw_labels": [str],
        "theme": str,           # thème de la première question du groupe
        "question_ids": [str],
        "quiz_capable": true    # toujours true pour ce dataset
    }
    """
    # --- Étape 1 : extraction par question ---
    extracted: list[dict] = []
    skipped_no_date: list[str] = []

    for q in questions:
        qid = q.get("id", "?")
        explication = q.get("explication", "")

        if not explication:
            skipped_no_date.append(qid)
            if verbose:
                print(f"  [skip ] {qid:<14} — pas d'explication")
            continue

        year, year_end = extract_dates(explication)

        if year is None:
            skipped_no_date.append(qid)
            if verbose:
                print(f"  [skip ] {qid:<14} — aucune date détectée")
            continue

        raw_label = extract_raw_label(explication, year)

        if verbose:
            period_str = f"{year}–{year_end}" if year_end else str(year)
            print(f"  [found] {qid:<14} — {period_str:<10}  {raw_label[:50]}")

        extracted.append({
            "year": year,
            "year_end": year_end,
            "raw_label": raw_label,
            "theme": q.get("theme", ""),
            "question_id": qid,
            "explication": explication,
        })

    # --- Étape 2 : déduplication par année ---
    # Clé = (year, year_end) pour distinguer 1914 isolé de 1914-1918
    groups: dict[tuple, list[dict]] = {}
    for item in extracted:
        key = (item["year"], item["year_end"])
        groups.setdefault(key, []).append(item)

    # --- Étape 3 : construction des entrées + labels ---
    client = anthropic.Anthropic() if use_haiku else None
    entries: list[dict] = []

    for (year, year_end), items in groups.items():
        raw_labels = [it["raw_label"] for it in items]
        question_ids = [it["question_id"] for it in items if it["question_id"]]
        explications = [it["explication"] for it in items if it.get("explication")]
        theme = items[0]["theme"]  # thème de la première question

        # Label + explication : Haiku si dispo, sinon fallbacks
        label = None
        explication = None
        if use_haiku and client:
            label, explication = review_with_haiku(
                raw_labels, explications, year, year_end, client
            )
        if not label:
            label = raw_labels[0]
        if not explication:
            explication = explications[0] if explications else ""

        entries.append({
            "year": year,
            "year_end": year_end,
            "label": label,
            "explication": explication,
            "raw_labels": raw_labels,
            "explications": explications,
            "theme": theme,
            "question_ids": question_ids,
            "quiz_capable": True,
        })

    # --- Étape 4 : tri chronologique ---
    entries.sort(key=lambda e: e["year"])

    # --- Stats console ---
    n_dated = len(entries)
    n_periods = sum(1 for e in entries if e["year_end"])
    n_skipped = len(skipped_no_date)

    print(
        f"[timeline_builder] {n_dated} entrées | "
        f"{n_periods} périodes | "
        f"{n_skipped} questions sans date ignorées"
    )

    return entries


# ---------------------------------------------------------------------------
# Chargement dataset + timeline
# ---------------------------------------------------------------------------

def load_dataset(path: str) -> list[dict]:
    """Charge unified_dataset_complete.json → liste de questions."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # Support flat list ou {"questions": [...]}
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "questions" in data:
        return data["questions"]
    raise ValueError(f"Format dataset non reconnu dans {path}")


def load_timeline(path: str) -> Optional[list[dict]]:
    """
    Charge timeline_dataset.json.
    Retourne None si le fichier n'existe pas.
    """
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_timeline(entries: list[dict], path: str) -> None:
    """Sauvegarde timeline_dataset.json."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"[timeline_builder] Sauvegardé → {path}")