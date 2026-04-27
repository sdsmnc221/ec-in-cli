"""
civique.cli — Command-line argument parsing.
"""

import argparse

DEFAULT_DATASET = "unified_dataset_complete.json"
SAMPLE_DATASET = "dataset_sample.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m civique",
        description="Simulateur CLI d'examen de naturalisation française",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python -m civique
  python -m civique --sample
  python -m civique --dataset mon_dataset.json
  python -m civique --mode marathon
  python -m civique --tutorial
        """
    )
    parser.add_argument(
        "--dataset", "-d",
        default=DEFAULT_DATASET,
        help=f"Chemin vers le fichier JSON (défaut : {DEFAULT_DATASET})"
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help=f"Utiliser le dataset d'exemple ({SAMPLE_DATASET}) — mode démo"
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["super-hard", "marathon"],
        default=None,
        help="Mode de simulation (défaut : sélection interactive)"
    )
    parser.add_argument(
        "--tutorial",
        action="store_true",
        help="Afficher le tutoriel même si déjà vu"
    )
    return parser.parse_args()
