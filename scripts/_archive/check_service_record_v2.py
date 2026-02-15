#!/usr/bin/env python3
"""Verifie le Service Record pour les stats d'armes."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.sync.api_client import SPNKrAPIClient, get_tokens_from_env


async def main():
    gamertag = sys.argv[1] if len(sys.argv) > 1 else "JGtm"

    tokens = await get_tokens_from_env()

    async with SPNKrAPIClient(tokens=tokens) as api_client:
        client = api_client.client

        # Obtenir le service record
        print(f"Recuperation du Service Record pour {gamertag}...")

        try:
            resp = await client.stats.get_service_record(gamertag, "matchmade")
            sr = await resp.json()
        except Exception as e:
            print(f"Erreur: {e}")
            return

        # Sauvegarder
        out = Path(f"data/investigation/service_record_{gamertag}.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(sr, f, indent=2, ensure_ascii=False)
        print(f"Sauvegarde: {out}")

        # Afficher les cles de premier niveau
        print("\n=== Cles de premier niveau ===")
        for k in sr.keys():
            v = sr[k]
            if isinstance(v, dict):
                print(f"  {k}: dict avec {len(v)} cles")
            elif isinstance(v, list):
                print(f"  {k}: list[{len(v)}]")
            else:
                print(f"  {k}: {type(v).__name__} = {str(v)[:50]}")

        # Chercher CoreStats
        print("\n=== CoreStats ===")
        core = sr.get("CoreStats", {})
        for k, v in core.items():
            if isinstance(v, dict):
                print(f"  {k}: dict")
                for k2 in v.keys():
                    print(f"    - {k2}")
            elif isinstance(v, list):
                print(f"  {k}: list[{len(v)}]")
            else:
                print(f"  {k}: {v}")

        # Chercher Breakdowns
        print("\n=== Recherche Breakdowns/Weapons ===")

        def search(d, path="root"):
            if isinstance(d, dict):
                for k, v in d.items():
                    lower_k = k.lower()
                    if "weapon" in lower_k or "breakdown" in lower_k:
                        print(f"  TROUVE: {path}.{k}")
                        if isinstance(v, list) and v:
                            print(
                                f"    Premier element: {list(v[0].keys()) if isinstance(v[0], dict) else v[0]}"
                            )
                    search(v, f"{path}.{k}")
            elif isinstance(d, list) and d:
                search(d[0], f"{path}[0]")

        search(sr)


if __name__ == "__main__":
    asyncio.run(main())
