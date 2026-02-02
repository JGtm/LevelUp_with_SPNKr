#!/usr/bin/env python3
"""Debug: affiche la structure brute d'un match."""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _load_dotenv_if_present() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    for name in (".env.local", ".env"):
        p = repo_root / name
        if not p.exists():
            continue
        content = p.read_text(encoding="utf-8")
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and os.environ.get(key) is None:
                os.environ[key] = value


async def main():
    _load_dotenv_if_present()

    from src.data.sync.api_client import SPNKrAPIClient

    match_id = sys.argv[1] if len(sys.argv) > 1 else "7f1bbf06-d54d-4434-ad80-923fcabe8b1b"

    async with SPNKrAPIClient() as client:
        match_data = await client.get_match_stats(match_id)

    if not match_data:
        print("Pas de données")
        return

    # Sauvegarder le JSON brut
    out_path = Path(f"data/investigation/{match_id[:8]}_raw.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(match_data, f, ensure_ascii=False, indent=2)
    print(f"Sauvegardé: {out_path}")

    # Afficher la structure du premier joueur
    players = match_data.get("Players", [])
    if players:
        p = players[0]
        stats = p.get("PlayerTeamStats", [{}])[0].get("Stats", {})
        core = stats.get("CoreStats", {})

        print("\n=== Structure CoreStats ===")
        for key in core.keys():
            val = core[key]
            if isinstance(val, dict):
                print(f"  {key}: dict avec {list(val.keys())}")
            elif isinstance(val, list):
                print(f"  {key}: list[{len(val)}]")
            else:
                print(f"  {key}: {type(val).__name__}")

        breakdowns = core.get("Breakdowns", {})
        if breakdowns:
            print("\n=== Breakdowns ===")
            for k, v in breakdowns.items():
                if isinstance(v, list):
                    print(f"  {k}: {len(v)} items")
                    if v:
                        print(
                            f"    Premier: {list(v[0].keys()) if isinstance(v[0], dict) else v[0]}"
                        )


if __name__ == "__main__":
    asyncio.run(main())
