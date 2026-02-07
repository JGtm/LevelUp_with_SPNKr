#!/bin/bash
# Script d'activation de l'environnement virtuel Python pour LevelUp
# Usage: source activate_env.sh
#
# IMPORTANT: utilise .venv_windows (Python Windows) pour avoir DuckDB en wheels.
# Si .venv_windows n'existe pas: bash scripts/setup_env.sh

if [ -d ".venv_windows" ]; then
    export PATH="$(pwd)/.venv_windows/Scripts:$PATH"
    source .venv_windows/Scripts/activate 2>/dev/null || true
    echo "Environnement: .venv_windows ($(.venv_windows/Scripts/python.exe --version 2>&1))"
elif [ -d ".venv" ]; then
    source .venv/Scripts/activate
    echo "ATTENTION: .venv (MSYS2) - DuckDB peut echouer. Preferez: bash scripts/setup_env.sh"
    echo "Python: $(python --version)"
else
    echo "Aucun environnement. Creer avec: bash scripts/setup_env.sh"
fi
