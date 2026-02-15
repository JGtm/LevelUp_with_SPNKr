"""Vérifie que la couverture de code atteint un seuil minimal.

Usage :
    python scripts/check_coverage_threshold.py --min 65
    python scripts/check_coverage_threshold.py --min 65 --module src/data/sync

Utilise le fichier coverage.json généré par :
    python -m pytest --cov=src --cov-report=json --ignore=tests/integration --ignore=tests/e2e
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COVERAGE_FILE = PROJECT_ROOT / "coverage.json"


def load_coverage_data(coverage_file: Path) -> dict:
    """Charge le fichier coverage.json."""
    if not coverage_file.exists():
        print(f"❌ Fichier de couverture introuvable : {coverage_file}")
        print("   Générez-le avec : python -m pytest --cov=src --cov-report=json")
        sys.exit(2)

    with open(coverage_file, encoding="utf-8") as f:
        return json.load(f)


def compute_module_coverage(
    data: dict, module_filter: str | None = None
) -> tuple[float, dict[str, float]]:
    """Calcule la couverture globale et par fichier.

    Args:
        data: Données coverage.json.
        module_filter: Filtre optionnel (ex: 'src/data/sync').

    Returns:
        (couverture_globale_pct, {fichier: pct})
    """
    files_data = data.get("files", {})
    per_file: dict[str, float] = {}
    total_stmts = 0
    total_covered = 0

    for filepath, fdata in files_data.items():
        # Normaliser le chemin
        norm = filepath.replace("\\", "/")

        if module_filter and module_filter not in norm:
            continue

        summary = fdata.get("summary", {})
        stmts = summary.get("num_statements", 0)
        # Utiliser percent_covered directement
        pct = summary.get("percent_covered", 0.0)

        per_file[norm] = pct
        total_stmts += stmts
        total_covered += int(stmts * pct / 100) if stmts > 0 else 0

    global_pct = (total_covered / total_stmts * 100) if total_stmts > 0 else 0.0
    return global_pct, per_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Vérifie le seuil minimal de couverture.")
    parser.add_argument(
        "--min",
        type=float,
        default=65.0,
        help="Seuil minimal de couverture (%%) (défaut: 65)",
    )
    parser.add_argument(
        "--module",
        type=str,
        default=None,
        help="Filtrer sur un module (ex: src/data/sync)",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=str(DEFAULT_COVERAGE_FILE),
        help="Chemin du fichier coverage.json",
    )
    parser.add_argument(
        "--show-low",
        type=float,
        default=None,
        help="Afficher les fichiers sous ce seuil (ex: 50)",
    )
    args = parser.parse_args()

    data = load_coverage_data(Path(args.file))
    global_pct, per_file = compute_module_coverage(data, args.module)

    # Affichage
    scope = f" [{args.module}]" if args.module else ""
    print(f"\n📊 Couverture globale{scope} : {global_pct:.1f}%")
    print(f"   Seuil requis : {args.min}%")
    print(f"   Fichiers analysés : {len(per_file)}")

    if args.show_low is not None:
        low_files = {f: p for f, p in sorted(per_file.items()) if p < args.show_low}
        if low_files:
            print(f"\n⚠️  Fichiers sous {args.show_low}% :")
            for f, p in low_files.items():
                print(f"   {p:5.1f}%  {f}")
        else:
            print(f"\n✅ Tous les fichiers sont au-dessus de {args.show_low}%")

    # Top 5 pires
    if per_file:
        worst = sorted(per_file.items(), key=lambda x: x[1])[:5]
        print("\n📉 5 fichiers les moins couverts :")
        for f, p in worst:
            print(f"   {p:5.1f}%  {f}")

    # Verdict
    if global_pct >= args.min:
        print(f"\n✅ Couverture OK : {global_pct:.1f}% >= {args.min}%")
        sys.exit(0)
    else:
        print(f"\n❌ Couverture insuffisante : {global_pct:.1f}% < {args.min}%")
        sys.exit(1)


if __name__ == "__main__":
    main()
