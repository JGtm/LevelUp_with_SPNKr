"""Vérifie que out/map_waypoint_links_merged.txt contient bien toutes les cartes des sources.

- Sources: out/map_waypoint_links_*.txt (sauf merged)
- Cible: out/map_waypoint_links_merged.txt

Produit un rapport:
- out/map_waypoint_links_merge_check.txt

La déduplication du merged est faite par map_name (case-insensitive). Ici on vérifie:
- noms présents dans les sources mais absents du merged
- noms présents dans le merged mais absents des sources (anormal)
- collisions (un même nom -> plusieurs map_id dans les sources)
"""

from __future__ import annotations

import re
from collections import defaultdict
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
    src: str


def _parse_file(path: Path) -> list[Row]:
    out: list[Row] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip("\n\r")
        if not line or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        map_name = (parts[0] if len(parts) > 0 else "").strip()
        map_id = (parts[1] if len(parts) > 1 else "").strip()
        url = (parts[2] if len(parts) > 2 else "").strip()
        thumb = (parts[3] if len(parts) > 3 else "").strip()
        if not map_name:
            continue
        out.append(Row(map_name=map_name, map_id=map_id, waypoint_url=url, thumb_suggested=thumb, src=path.name))
    return out


def main() -> int:
    out_dir = _repo_root() / "out"
    merged_path = out_dir / "map_waypoint_links_merged.txt"
    if not merged_path.exists():
        raise SystemExit(f"Fichier merged introuvable: {merged_path}")

    sources = sorted(out_dir.glob("map_waypoint_links_*.txt"))
    sources = [p for p in sources if p.name != merged_path.name]
    if not sources:
        raise SystemExit("Aucune source trouvée dans out/ (map_waypoint_links_*.txt).")

    src_rows: list[Row] = []
    for p in sources:
        src_rows.extend(_parse_file(p))

    merged_rows = _parse_file(merged_path)

    src_names = {_norm_name(r.map_name) for r in src_rows if _norm_name(r.map_name)}
    merged_names = {_norm_name(r.map_name) for r in merged_rows if _norm_name(r.map_name)}

    missing = sorted(src_names - merged_names)
    extra = sorted(merged_names - src_names)

    # Collisions: un même nom -> plusieurs map_id dans les sources
    ids_by_name: dict[str, set[str]] = defaultdict(set)
    examples_by_name: dict[str, list[Row]] = defaultdict(list)
    for r in src_rows:
        k = _norm_name(r.map_name)
        if not k:
            continue
        if r.map_id:
            ids_by_name[k].add(r.map_id)
        if len(examples_by_name[k]) < 6:
            examples_by_name[k].append(r)

    collisions = [(k, sorted(ids)) for k, ids in ids_by_name.items() if len(ids) >= 2]
    collisions.sort(key=lambda t: (-len(t[1]), t[0]))

    report_path = out_dir / "map_waypoint_links_merge_check.txt"
    lines: list[str] = []
    lines.append(f"# Sources: {', '.join(p.name for p in sources)}")
    lines.append(f"# Merged: {merged_path.name}")
    lines.append(f"# Lignes source: {len(src_rows)}")
    lines.append(f"# Lignes merged: {len(merged_rows)}")
    lines.append(f"# Noms uniques source: {len(src_names)}")
    lines.append(f"# Noms uniques merged: {len(merged_names)}")
    lines.append("")

    def _fmt_name(k: str) -> str:
        # retrouve un exemple “joli” (non normalisé)
        ex = examples_by_name.get(k)
        return ex[0].map_name if ex else k

    lines.append(f"## Manquants dans merged: {len(missing)}")
    for k in missing[:200]:
        lines.append(f"- {_fmt_name(k)}")
    if len(missing) > 200:
        lines.append(f"- ... ({len(missing) - 200} autres)")

    lines.append("")
    lines.append(f"## Présents dans merged mais absents des sources: {len(extra)}")
    for k in extra[:200]:
        lines.append(f"- {k}")
    if len(extra) > 200:
        lines.append(f"- ... ({len(extra) - 200} autres)")

    lines.append("")
    lines.append(f"## Collisions (même nom, plusieurs map_id): {len(collisions)}")
    for k, ids in collisions[:60]:
        pretty = _fmt_name(k)
        lines.append(f"- {pretty}\t{len(ids)} ids")
        for r in examples_by_name.get(k, [])[:6]:
            lines.append(f"  * {r.src}\t{r.map_id}\t{r.waypoint_url}")
    if len(collisions) > 60:
        lines.append(f"- ... ({len(collisions) - 60} autres collisions)")

    # Ciblage: Houseki
    lines.append("")
    hk = _norm_name("Houseki")
    lines.append("## Check: Houseki")
    lines.append(f"- dans sources: {'oui' if hk in src_names else 'non'}")
    lines.append(f"- dans merged: {'oui' if hk in merged_names else 'non'}")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK: {report_path}")
    print(f"Missing in merged: {len(missing)} | Extra in merged: {len(extra)} | Collisions: {len(collisions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
