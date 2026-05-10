#!/usr/bin/env python3
"""
fix_label.py
Rewrite all labels in timeline_dataset.json using Claude Haiku.
Each label is rewritten to be concise (max 14 words) based on the explication field.

Usage:
    python fix_label.py
    python fix_label.py --input timeline_dataset.json
    python fix_label.py --output timeline_dataset_fixed.json
    python fix_label.py --dry-run
    python fix_label.py --limit 10
"""

import argparse
import json
import os
import sys

import anthropic


# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rewrite timeline labels using Claude Haiku."
    )
    parser.add_argument(
        "--input",
        default="timeline_dataset.json",
        help="Input file (default: timeline_dataset.json)",
    )
    parser.add_argument(
        "--output",
        default="timeline_dataset_fixed.json",
        help="Output file (default: timeline_dataset_fixed.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print rewrites without saving",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only first N entries (for testing)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Haiku label rewrite
# ---------------------------------------------------------------------------

def rewrite_label(
    entry: dict,
    client: anthropic.Anthropic,
) -> str:
    """
    Ask Haiku to produce a concise label (max 14 words) from the explication.
    Falls back to the original label if the call fails or returns empty.
    """
    year     = entry["year"]
    year_end = entry.get("year_end")
    period   = f"{year}–{year_end}" if year_end else str(year)

    explication = entry.get("explication", "")
    explications = entry.get("explications", [])

    # Build context block — prefer synthesised explication, supplement with raw list
    context_parts = []
    if explication:
        context_parts.append(explication)
    for e in explications:
        if e and e != explication:
            context_parts.append(e)
    context = "\n".join(f"• {p}" for p in context_parts) if context_parts else entry.get("label", "")

    prompt = (
        f"Tu es un assistant pédagogique pour l'examen civique français.\n\n"
        f"Période : {period}\n\n"
        f"Contexte :\n{context}\n\n"
        f"Écris un label court en français (maximum 14 mots) qui résume "
        f"l'événement ou le fait civique principal de cette période. "
        f"Le label doit être factuel, précis, et lisible comme un titre. "
        f"Réponds uniquement avec le label, sans ponctuation finale, "
        f"sans guillemets, sans explication."
    )

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            messages=[{"role": "user", "content": prompt}],
        )
        label = response.content[0].text.strip()
        # Strip any accidental quotes or trailing punctuation
        label = label.strip('"\'')
        label = label.rstrip(".")
        if label:
            return label
    except Exception as e:
        print(f"  [warn] Haiku error for {entry.get('year')}: {e}")

    return entry.get("label", "")  # fallback


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # Load input
    if not os.path.exists(args.input):
        print(f"[error] File not found: {args.input}")
        sys.exit(1)

    with open(args.input, encoding="utf-8") as f:
        entries: list[dict] = json.load(f)

    total = len(entries)
    if args.limit:
        entries = entries[: args.limit]
        print(f"[fix_label] --limit: processing {len(entries)}/{total} entries")
    else:
        print(f"[fix_label] Processing {total} entries")

    if args.dry_run:
        print("[fix_label] --dry-run: no file will be saved\n")

    client = anthropic.Anthropic()
    fixed  = []

    for i, entry in enumerate(entries):
        year     = entry["year"]
        year_end = entry.get("year_end")
        period   = f"{year}–{year_end}" if year_end else str(year)
        old_label = entry.get("label", "")

        new_label = rewrite_label(entry, client)

        changed = new_label != old_label
        status  = "fixed" if changed else "ok   "
        print(f"  [{status}] {period:<10}  {new_label[:70]}")
        if changed:
            print(f"            was : {old_label[:70]}")

        fixed.append({**entry, "label": new_label})

    # Summary
    n_changed = sum(1 for o, n in zip(entries, fixed) if o.get("label") != n.get("label"))
    print(f"\n[fix_label] {n_changed}/{len(entries)} labels rewritten")

    if args.dry_run:
        print("[fix_label] --dry-run: skipping save")
        return

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(fixed, f, ensure_ascii=False, indent=2)

    print(f"[fix_label] Saved → {args.output}")


if __name__ == "__main__":
    main()
