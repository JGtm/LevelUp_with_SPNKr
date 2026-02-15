#!/bin/bash
# Script d'activation de l'environnement virtuel Python pour LevelUp
# Usage: source activate_env.sh
#
# IMPORTANT: sur Windows, DuckDB nécessite généralement un venv créé avec le Python Windows
# (via `py` / python.org) pour bénéficier des wheels précompilées.
# Si l'environnement n'existe pas: bash scripts/setup_env.sh (ou .\scripts\setup_env.ps1)

if [ -d ".venv" ]; then
    # Venv Windows (structure Scripts/)
    if [ -d ".venv/Scripts" ] && [ -f ".venv/Scripts/python.exe" ]; then
        export PATH="$(pwd)/.venv/Scripts:$PATH"
        source .venv/Scripts/activate 2>/dev/null || true
        echo "Environnement: .venv ($(.venv/Scripts/python.exe --version 2>&1))"
        exit 0
    fi

    # Venv Unix/MSYS2 (structure bin/)
    if [ -f ".venv/bin/activate" ]; then
        # shellcheck disable=SC1091
        source .venv/bin/activate
        echo "ATTENTION: .venv (type Unix/MSYS2). Sur Windows, DuckDB peut échouer (wheels incompatibles)."
        echo "Conseil: recréer avec le Python Windows via: bash scripts/setup_env.sh"
        echo "Python: $(python --version)"
        exit 0
    fi

    echo "Environnement .venv présent mais format inconnu. Recréez-le avec: bash scripts/setup_env.sh"
    exit 1
fi

echo "Aucun environnement. Créez-le avec: bash scripts/setup_env.sh (ou .\\scripts\\setup_env.ps1)"
