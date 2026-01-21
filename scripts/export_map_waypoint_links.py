"""Exporte une liste unique de cartes présentes dans l'historique et leurs liens HaloWaypoint.

Objectif:
- Parcourir l'historique de matchs d'un ou plusieurs profils (db_profiles.json)
- Garder une ligne par carte (map_id) et produire le lien Waypoint

Sortie:
- out/map_waypoint_links_<profil>.txt

Notes:
- SPNKr expose MatchInfo.MapVariant.AssetId (GUID). Sur HaloWaypoint, ces assets
  sont consultables via la section UGC: https://www.halowaypoint.com/halo-infinite/ugc/maps/<map_id>
- Si map_id est manquant, la ligne est ignorée (pas de lien fiable).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _repo_root() -> Path:
    # scripts/export_map_waypoint_links.py -> repo root
    return Path(__file__).resolve().parents[1]


# Permet `python scripts/...py` sans installer le package.
_ROOT = _repo_root()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


from src.db import load_matches  # noqa: E402
from src.db.profiles import load_profiles  # noqa: E402


def _waypoint_map_url(map_id: str) -> str:
    return f"https://www.halowaypoint.com/halo-infinite/ugc/maps/{map_id}"


def _export_one(*, profile_name: str, db_path: str, xuid: str, out_dir: Path) -> Path:
    matches = load_matches(db_path, xuid)

    # Une ligne par carte: key=map_id ; on garde le premier nom non vide rencontré.
    maps: dict[str, str] = {}
    for m in matches:
        mid = str(m.map_id or "").strip()
        if not mid:
            continue
        if mid not in maps:
            maps[mid] = str(m.map_name or mid).strip() or mid

    # Tri stable: par nom puis map_id
    rows = sorted(((name, mid) for mid, name in maps.items()), key=lambda t: (t[0].lower(), t[1]))

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"map_waypoint_links_{profile_name}.txt"

    lines: list[str] = []
    lines.append(f"# Profil: {profile_name}")
    lines.append(f"# DB: {db_path}")
    lines.append(f"# XUID: {xuid}")
    lines.append("# Format: map_name\tmap_id\thalowaypoint_url\tthumbnail_suggested")

    thumbs_dir = _repo_root() / "static" / "maps" / "thumbs"
    for name, mid in rows:
        url = _waypoint_map_url(mid)
        thumb = str((thumbs_dir / f"{mid}.jpg").as_posix())
        lines.append(f"{name}\t{mid}\t{url}\t{thumb}")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Exporte les liens HaloWaypoint des cartes (une ligne par carte)")
    ap.add_argument(
        "--profile",
        default=None,
        help="Nom de profil (db_profiles.json). Si absent, exporte tous les profils.",
    )
    ap.add_argument(
        "--out-dir",
        default=str(_repo_root() / "out"),
        help="Dossier de sortie (défaut: out/)",
    )
    args = ap.parse_args()

    profiles = load_profiles()
    if not profiles:
        raise SystemExit("Aucun profil trouvé (db_profiles.json vide ou absent).")

    out_dir = Path(args.out_dir)

    wanted = [args.profile] if args.profile else list(profiles.keys())
    wrote_any = False

    for name in wanted:
        p = profiles.get(name)
        if not p:
            raise SystemExit(f"Profil introuvable: {name}")
        db_path = str(p.get("db_path") or "").strip()
        xuid = str(p.get("xuid") or "").strip()
        if not db_path or not xuid:
            raise SystemExit(f"Profil invalide (db_path/xuid manquant): {name}")

        out_path = _export_one(profile_name=name, db_path=db_path, xuid=xuid, out_dir=out_dir)
        print(f"OK: {out_path}")
        wrote_any = True

    return 0 if wrote_any else 2


if __name__ == "__main__":
    raise SystemExit(main())
