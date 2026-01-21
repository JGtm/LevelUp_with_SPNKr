"""Fusionne les exports out/map_waypoint_links_*.txt et déduplique par nom de carte.

But:
- Regrouper plusieurs exports (par profil)
- Supprimer les doublons sur le NOM de carte (case-insensitive)

Sortie:
- out/map_waypoint_links_merged.txt

Règle de déduplication:
- clé = map_name normalisé (strip + espaces compressés + casefold)
- pour une même clé, on garde la ligne avec le plus petit map_id (ordre lexicographique)
  afin d'avoir un choix déterministe.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


_WS_RE = re.compile(r"\s+")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _norm_name(name: str) -> str:
    s = str(name or "").strip()
    s = _WS_RE.sub(" ", s)
    return s.casefold()


@dataclass(frozen=True)
class Row:
    map_name: str
    map_id: str
    waypoint_url: str
    thumb_suggested: str


def _parse_lines(path: Path) -> list[Row]:
    rows: list[Row] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip("\n\r")
        if not line or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        map_name = parts[0].strip()
        map_id = parts[1].strip() if len(parts) > 1 else ""
        url = parts[2].strip() if len(parts) > 2 else ""
        thumb = parts[3].strip() if len(parts) > 3 else ""
        if not map_name:
            continue
        rows.append(Row(map_name=map_name, map_id=map_id, waypoint_url=url, thumb_suggested=thumb))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Fusionne map_waypoint_links_*.txt et déduplique par nom de carte")
    ap.add_argument(
        "--in",
        dest="in_files",
        nargs="*",
        default=None,
        help="Fichiers d'entrée. Par défaut: out/map_waypoint_links_*.txt",
    )
    ap.add_argument(
        "--out",
        dest="out_file",
        default=str(_repo_root() / "out" / "map_waypoint_links_merged.txt"),
        help="Fichier de sortie (défaut: out/map_waypoint_links_merged.txt)",
    )
    args = ap.parse_args()

    repo = _repo_root()
    out_dir = repo / "out"

    in_paths: list[Path]
    if args.in_files:
        in_paths = [Path(p) for p in args.in_files]
    else:
        in_paths = sorted(out_dir.glob("map_waypoint_links_*.txt"))

    in_paths = [p for p in in_paths if p.exists()]
    if not in_paths:
        raise SystemExit("Aucun fichier d'entrée trouvé.")

    all_rows: list[Row] = []
    for p in in_paths:
        all_rows.extend(_parse_lines(p))

    # Déduplication par nom
    kept: dict[str, Row] = {}
    for r in all_rows:
        k = _norm_name(r.map_name)
        if not k:
            continue
        prev = kept.get(k)
        if prev is None:
            kept[k] = r
            continue
        # Choix déterministe: map_id lexicographiquement plus petit
        if (r.map_id or "") < (prev.map_id or ""):
            kept[k] = r

    merged = sorted(kept.values(), key=lambda r: (_norm_name(r.map_name), r.map_id))

    out_path = Path(args.out_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Sources: " + ", ".join(str(p.as_posix()) for p in in_paths))
    lines.append("# Déduplication: 1 ligne par map_name (case-insensitive)")
    lines.append("# Format: map_name\tmap_id\thalowaypoint_url\tthumbnail_suggested")
    for r in merged:
        lines.append(f"{r.map_name}\t{r.map_id}\t{r.waypoint_url}\t{r.thumb_suggested}")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OK: {out_path} ({len(merged)} cartes uniques, {len(all_rows)} lignes source)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
