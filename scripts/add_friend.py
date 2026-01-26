#!/usr/bin/env python3
"""Script pour ajouter un ami à la base de données unifiée.

Usage:
    python scripts/add_friend.py <gamertag> [--xuid XUID] [--profile] [--import] [--merge]
    python scripts/add_friend.py <gamertag> --from-match <match_id>

Exemples:
    # Ajouter avec XUID connu (alias seulement)
    python scripts/add_friend.py XxDaemonGamerxX --xuid 2533274833178266

    # Ajouter avec profil + import ses matchs + merge dans DB unifiée
    python scripts/add_friend.py XxDaemonGamerxX --xuid 2533274833178266 --profile --import --merge

    # Workflow complet simplifié (alias + profil + import + merge)
    python scripts/add_friend.py XxDaemonGamerxX --xuid 2533274833178266 --full

    # Trouver automatiquement le XUID depuis un match partagé
    python scripts/add_friend.py XxDaemonGamerxX --from-match 1e26f641-5570-475c-a52d-d7afc6b49fd8

    # Mode interactif (liste les joueurs inconnus d'un match)
    python scripts/add_friend.py --from-match 1e26f641-5570-475c-a52d-d7afc6b49fd8
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

# Ajouter le répertoire racine au path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ALIASES_FILE = ROOT / "xuid_aliases.json"
UNIFIED_DB = ROOT / "data" / "halo_unified.db"
PROFILES_FILE = ROOT / "db_profiles.json"
SCRIPTS_DIR = ROOT / "scripts"


def load_aliases() -> dict[str, str]:
    """Charge les alias existants."""
    if not ALIASES_FILE.exists():
        return {}
    with open(ALIASES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_aliases(aliases: dict[str, str]) -> None:
    """Sauvegarde les alias."""
    with open(ALIASES_FILE, "w", encoding="utf-8") as f:
        json.dump(aliases, f, indent=2, ensure_ascii=False)


def get_match_players(match_id: str, db_path: Path) -> list[dict]:
    """Récupère les joueurs d'un match depuis la DB."""
    if not db_path.exists():
        return []
    
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT ResponseBody FROM MatchStats").fetchall()
    conn.close()
    
    for row in rows:
        data = json.loads(row[0])
        if data.get("MatchId") == match_id:
            players = []
            for p in data.get("Players", []):
                pid = p.get("PlayerId", "")
                if isinstance(pid, str) and pid.startswith("xuid("):
                    xuid = pid[5:-1] if pid.endswith(")") else pid[5:]
                elif isinstance(pid, dict):
                    xuid = str(pid.get("Xuid", ""))
                else:
                    xuid = str(pid)
                
                # Récupérer les stats
                core = p.get("PlayerTeamStats", [{}])[0].get("Stats", {}).get("CoreStats", {})
                players.append({
                    "xuid": xuid,
                    "kills": core.get("Kills", 0),
                    "deaths": core.get("Deaths", 0),
                    "assists": core.get("Assists", 0),
                })
            return players
    return []


def find_unknown_players(match_id: str) -> list[dict]:
    """Trouve les joueurs inconnus d'un match."""
    aliases = load_aliases()
    players = get_match_players(match_id, UNIFIED_DB)
    
    unknown = []
    for p in players:
        xuid = p["xuid"]
        # Ignorer les bots
        if xuid.startswith("bid("):
            continue
        # Ignorer les joueurs connus
        if xuid in aliases:
            continue
        unknown.append(p)
    
    return unknown


def load_profiles() -> dict:
    """Charge les profils existants."""
    if not PROFILES_FILE.exists():
        return {"profiles": {}}
    with open(PROFILES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_profiles(data: dict) -> None:
    """Sauvegarde les profils."""
    with open(PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_friend(gamertag: str, xuid: str, *, create_profile: bool = False) -> bool:
    """Ajoute un ami aux alias et optionnellement crée un profil."""
    aliases = load_aliases()
    
    if xuid in aliases:
        existing = aliases[xuid]
        if existing.lower() == gamertag.lower():
            print(f"ℹ️  {gamertag} est déjà enregistré avec ce XUID")
        else:
            print(f"⚠️  XUID {xuid} existe déjà avec le gamertag '{existing}'")
            confirm = input(f"   Remplacer par '{gamertag}' ? [o/N] ").strip().lower()
            if confirm != "o":
                return False
            aliases[xuid] = gamertag
            save_aliases(aliases)
            print(f"✅ Alias mis à jour: {gamertag} (XUID: {xuid})")
    else:
        aliases[xuid] = gamertag
        save_aliases(aliases)
        print(f"✅ Alias ajouté: {gamertag} (XUID: {xuid})")
        print(f"   Total aliases: {len(aliases)}")
    
    # Créer un profil si demandé
    if create_profile:
        profiles = load_profiles()
        if gamertag in profiles.get("profiles", {}):
            print(f"ℹ️  Profil '{gamertag}' existe déjà")
        else:
            profiles.setdefault("profiles", {})[gamertag] = {
                "db_path": f"data/spnkr_gt_{gamertag}.db",
                "xuid": xuid,
                "waypoint_player": gamertag,
            }
            save_profiles(profiles)
            print(f"✅ Profil créé: {gamertag}")
            print(f"   DB: data/spnkr_gt_{gamertag}.db")
    
    return True


def import_matches(gamertag: str, max_matches: int = 500) -> bool:
    """Importe les matchs d'un joueur via SPNKr API."""
    db_path = ROOT / "data" / f"spnkr_gt_{gamertag}.db"
    script = SCRIPTS_DIR / "spnkr_import_db.py"
    
    if not script.exists():
        print(f"❌ Script d'import non trouvé: {script}")
        return False
    
    print(f"\n📥 Import des matchs de {gamertag}...")
    print(f"   DB: {db_path}")
    print(f"   Max: {max_matches} matchs")
    print()
    
    cmd = [
        sys.executable,
        str(script),
        "--player", gamertag,
        "--out-db", str(db_path),
        "--max-matches", str(max_matches),
        "--requests-per-second", "2",
    ]
    
    # Mode resume si la DB existe déjà
    if db_path.exists():
        cmd.append("--resume")
        cmd.append("--delta")
        print("   Mode: delta (mise à jour)")
    else:
        print("   Mode: import complet")
    
    print()
    
    try:
        result = subprocess.run(cmd, cwd=ROOT)
        if result.returncode == 0:
            # Compter les matchs
            if db_path.exists():
                conn = sqlite3.connect(db_path)
                count = conn.execute("SELECT COUNT(*) FROM MatchStats").fetchone()[0]
                conn.close()
                print(f"\n✅ Import terminé: {count} matchs")
            return True
        else:
            print(f"\n❌ Erreur lors de l'import (code {result.returncode})")
            return False
    except KeyboardInterrupt:
        print("\n⚠️  Import interrompu par l'utilisateur")
        return False
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        return False


def merge_databases() -> bool:
    """Fusionne toutes les DB dans la DB unifiée."""
    script = SCRIPTS_DIR / "merge_databases.py"
    
    if not script.exists():
        print(f"❌ Script de fusion non trouvé: {script}")
        return False
    
    print(f"\n🔄 Fusion des bases de données...")
    
    try:
        result = subprocess.run([sys.executable, str(script)], cwd=ROOT)
        if result.returncode == 0:
            print(f"✅ Fusion terminée")
            return True
        else:
            print(f"❌ Erreur lors de la fusion (code {result.returncode})")
            return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


def interactive_mode(match_id: str) -> None:
    """Mode interactif pour identifier les joueurs d'un match."""
    print(f"\n🔍 Analyse du match {match_id}...")
    
    unknown = find_unknown_players(match_id)
    
    if not unknown:
        print("✅ Tous les joueurs de ce match sont déjà connus !")
        return
    
    print(f"\n📋 {len(unknown)} joueur(s) inconnu(s) dans ce match:\n")
    print(f"{'#':<3} {'XUID':<20} {'K':<4} {'D':<4} {'A':<4}")
    print("-" * 40)
    
    for i, p in enumerate(unknown, 1):
        print(f"{i:<3} {p['xuid']:<20} {p['kills']:<4} {p['deaths']:<4} {p['assists']:<4}")
    
    print("\n💡 Pour ajouter un ami, entre son numéro puis son gamertag.")
    print("   Exemple: 1 XxDaemonGamerxX")
    print("   Tape 'q' pour quitter.\n")
    
    while True:
        try:
            line = input(">>> ").strip()
            if not line or line.lower() == "q":
                break
            
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                print("   ❌ Format: <numéro> <gamertag>")
                continue
            
            try:
                idx = int(parts[0]) - 1
                if idx < 0 or idx >= len(unknown):
                    print(f"   ❌ Numéro invalide (1-{len(unknown)})")
                    continue
            except ValueError:
                print("   ❌ Le premier argument doit être un numéro")
                continue
            
            gamertag = parts[1]
            xuid = unknown[idx]["xuid"]
            add_friend(gamertag, xuid)
            
        except KeyboardInterrupt:
            print("\n")
            break
        except EOFError:
            break


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ajouter un ami à la base de données unifiée",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("gamertag", nargs="?", help="Gamertag de l'ami")
    parser.add_argument("--xuid", help="XUID du joueur")
    parser.add_argument("--from-match", dest="match_id", help="ID d'un match partagé pour trouver le XUID")
    parser.add_argument("--profile", action="store_true", help="Créer aussi un profil (pour voir ses matchs)")
    parser.add_argument("--import", dest="do_import", action="store_true", help="Importer ses matchs via SPNKr API")
    parser.add_argument("--merge", action="store_true", help="Fusionner dans la DB unifiée après import")
    parser.add_argument("--full", action="store_true", help="Workflow complet: alias + profil + import + merge")
    parser.add_argument("--max-matches", type=int, default=500, help="Nombre max de matchs à importer (défaut: 500)")
    
    args = parser.parse_args()
    
    # --full active tout
    if args.full:
        args.profile = True
        args.do_import = True
        args.merge = True
    
    # Mode interactif si seulement --from-match
    if args.match_id and not args.gamertag:
        interactive_mode(args.match_id)
        return
    
    # Vérification des arguments
    if not args.gamertag:
        parser.print_help()
        sys.exit(1)
    
    if not args.xuid and not args.match_id:
        print("❌ Il faut soit --xuid soit --from-match pour identifier le joueur")
        sys.exit(1)
    
    # Si --from-match, chercher le XUID automatiquement
    if args.match_id and not args.xuid:
        unknown = find_unknown_players(args.match_id)
        if not unknown:
            print("❌ Aucun joueur inconnu dans ce match")
            sys.exit(1)
        
        if len(unknown) == 1:
            args.xuid = unknown[0]["xuid"]
            print(f"🔍 XUID trouvé automatiquement: {args.xuid}")
        else:
            print(f"⚠️  {len(unknown)} joueurs inconnus dans ce match:")
            for p in unknown:
                print(f"   - {p['xuid']} (K:{p['kills']} D:{p['deaths']} A:{p['assists']})")
            print("\nUtilise --xuid pour spécifier lequel, ou lance le mode interactif:")
            print(f"   python scripts/add_friend.py --from-match {args.match_id}")
            sys.exit(1)
    
    # 1. Ajouter l'alias (et profil si demandé)
    add_friend(args.gamertag, args.xuid, create_profile=args.profile or args.do_import)
    
    # 2. Importer les matchs si demandé
    if args.do_import:
        import_matches(args.gamertag, max_matches=args.max_matches)
    
    # 3. Fusionner si demandé
    if args.merge:
        merge_databases()


if __name__ == "__main__":
    main()
