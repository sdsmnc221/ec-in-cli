#!/usr/bin/env python3
"""
extract_timeline.py
Thin CLI wrapper pour civique/timeline_builder.py.
Produit timeline_dataset.json depuis unified_dataset_complete.json.

Usage :
    python extract_timeline.py
    python extract_timeline.py --dataset mon_dataset.json
    python extract_timeline.py --output ma_timeline.json
    python extract_timeline.py --no-haiku
    python extract_timeline.py --dry-run
    python extract_timeline.py --limit 20
"""

import argparse
import sys
import os

# Permet l'import du package civique depuis la racine du projet
sys.path.insert(0, os.path.dirname(__file__))

from civ.timeline_builder import (
    load_dataset,
    build_timeline_entries,
    save_timeline,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extrait une timeline civique depuis le dataset QCM."
    )
    parser.add_argument(
        "--dataset",
        default="unified_dataset_complete.json",
        help="Chemin vers le dataset QCM (défaut : unified_dataset_complete.json)",
    )
    parser.add_argument(
        "--output",
        default="timeline_dataset.json",
        help="Chemin de sortie (défaut : timeline_dataset.json)",
    )
    parser.add_argument(
        "--no-haiku",
        action="store_true",
        help="Désactive l'appel Haiku, utilise les raw_labels directement",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche les stats sans sauvegarder le fichier de sortie",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite le traitement aux N premières questions (pour test)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Affiche une ligne de log par question pendant l'extraction",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # --- Chargement dataset ---
    if not os.path.exists(args.dataset):
        print(f"[erreur] Dataset introuvable : {args.dataset}")
        sys.exit(1)

    print(f"[extract_timeline] Chargement → {args.dataset}")
    questions = load_dataset(args.dataset)

    if args.limit:
        questions = questions[: args.limit]
        print(f"[extract_timeline] Mode --limit : {len(questions)} questions")

    # --- Build timeline ---
    use_haiku = not args.no_haiku
    if not use_haiku:
        print("[extract_timeline] Mode --no-haiku : labels bruts uniquement")

    if args.verbose:
        print(f"\n--- Extraction (1 ligne / question) ---")

    entries = build_timeline_entries(questions, use_haiku=use_haiku, verbose=args.verbose)

    if args.verbose:
        print(f"--- Fin extraction ---\n")

    # --- Affichage résumé ---
    print(f"\n{'─'*50}")
    print(f"  Entrées timeline    : {len(entries)}")
    print(f"  Périodes (year_end) : {sum(1 for e in entries if e['year_end'])}")
    print(f"  Plage temporelle    : {entries[0]['year']} → {entries[-1]['year']}" if entries else "  (vide)")
    print(f"{'─'*50}\n")

    if args.dry_run:
        print("[extract_timeline] --dry-run : aucun fichier sauvegardé.")
        # Affiche les 5 premières entrées pour vérification
        for e in entries[:5]:
            period = f"–{e['year_end']}" if e["year_end"] else ""
            print(f"  {e['year']}{period:7} | {e['label'][:60]}")
        return

    # --- Sauvegarde ---
    save_timeline(entries, args.output)
    print(f"[extract_timeline] ✓ Terminé → {args.output}")


if __name__ == "__main__":
    main()
