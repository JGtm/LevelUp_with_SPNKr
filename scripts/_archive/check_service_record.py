#!/usr/bin/env python3
"""Verifie le Service Record pour les stats d'armes."""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _load_dotenv():
    repo_root = Path(__file__).resolve().parent.parent
    for name in (".env.local", ".env"):
        p = repo_root / name
        if not p.exists():
            continue
        content = p.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if os.environ.get(k.strip()) is None:
                os.environ[k.strip()] = v.strip().strip('"')


async def main():
    _load_dotenv()

    from aiohttp import ClientSession, ClientTimeout

    from src.data.sync.api_client import get_tokens_from_env

    tokens = await get_tokens_from_env()

    gamertag = sys.argv[1] if len(sys.argv) > 1 else "JGtm"

    headers = {
        "x-343-authorization-spartan": tokens.spartan_token,
        "343-clearance": tokens.clearance_token,
        "Accept": "application/json",
    }

    async with ClientSession(timeout=ClientTimeout(total=60), headers=headers) as session:
        # 1. Resoudre XUID
        url = f"https://profile.svc.halowaypoint.com/users?gamertag={gamertag}"
        async with session.get(url) as resp:
            if resp.status >= 400:
                print(f"Erreur profil: {resp.status}")
                return
            profile = await resp.json()

        if isinstance(profile, list):
            xuid = profile[0].get("xuid") if profile else None
        else:
            xuid = profile.get("results", [{}])[0].get("xuid")
        print(f"XUID: {xuid}")

        # 2. Service Record (stats globales)
        url = f"https://halostats.svc.halowaypoint.com/hi/players/xuid({xuid})/matchmade/servicerecord"
        async with session.get(url) as resp:
            if resp.status >= 400:
                print(f"Erreur service record: {resp.status}")
                text = await resp.text()
                print(text[:500])
                return
            sr = await resp.json()

        # Sauvegarder
        out = Path(f"data/investigation/service_record_{gamertag}.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(sr, f, indent=2, ensure_ascii=False)
        print(f"Sauvegarde: {out}")

        # Afficher la structure
        print("\n=== Structure Service Record ===")

        def show_keys(d, prefix=""):
            if isinstance(d, dict):
                for k, v in d.items():
                    if isinstance(v, dict):
                        print(f"{prefix}{k}: dict")
                        if prefix.count("  ") < 2:
                            show_keys(v, prefix + "  ")
                    elif isinstance(v, list):
                        print(f"{prefix}{k}: list[{len(v)}]")
                        if v and isinstance(v[0], dict) and prefix.count("  ") < 2:
                            print(f"{prefix}  Premier item keys: {list(v[0].keys())[:5]}...")
                    else:
                        print(f"{prefix}{k}: {type(v).__name__}")

        show_keys(sr)

        # Chercher specifiquement Weapons/Breakdowns
        print("\n=== Recherche Weapons/Breakdowns ===")

        def find_weapons(d, path=""):
            if isinstance(d, dict):
                for k, v in d.items():
                    if "weapon" in k.lower() or "breakdown" in k.lower():
                        print(f"TROUVE: {path}.{k}")
                    find_weapons(v, f"{path}.{k}")
            elif isinstance(d, list):
                for i, item in enumerate(d[:2]):
                    find_weapons(item, f"{path}[{i}]")

        find_weapons(sr)


if __name__ == "__main__":
    asyncio.run(main())
