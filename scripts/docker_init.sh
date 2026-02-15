#!/usr/bin/env bash
# docker_init.sh — Prépare l'environnement hôte pour docker compose up.
#
# Usage:
#   bash scripts/docker_init.sh
#
# Ce script crée les fichiers et dossiers requis par les bind mounts
# de docker-compose.yml, pour éviter que Docker ne crée des DOSSIERS
# à la place des fichiers attendus (comportement par défaut si absents).
#
# Idempotent : peut être relancé sans risque.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Initialisation Docker pour LevelUp ==="

# --- Fichiers de configuration ---

if [ ! -f "$REPO_ROOT/db_profiles.json" ]; then
    echo '{"profiles": {}}' > "$REPO_ROOT/db_profiles.json"
    echo "✓ db_profiles.json créé (vide)"
else
    echo "· db_profiles.json existe déjà"
fi

if [ ! -f "$REPO_ROOT/app_settings.json" ]; then
    echo '{}' > "$REPO_ROOT/app_settings.json"
    echo "✓ app_settings.json créé (vide)"
else
    echo "· app_settings.json existe déjà"
fi

# --- Dossiers de données ---

mkdir -p "$REPO_ROOT/data/players"
mkdir -p "$REPO_ROOT/data/warehouse"
echo "· Dossiers data/players et data/warehouse OK"

# --- Fichiers de données optionnels ---

if [ ! -f "$REPO_ROOT/data/xuid_aliases.json" ]; then
    echo '{}' > "$REPO_ROOT/data/xuid_aliases.json"
    echo "✓ data/xuid_aliases.json créé (vide)"
else
    echo "· data/xuid_aliases.json existe déjà"
fi

echo ""
echo "=== Prêt ! Lancez : docker compose up --build ==="
