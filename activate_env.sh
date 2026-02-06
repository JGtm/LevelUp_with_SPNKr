#!/bin/bash
# Script d'activation de l'environnement virtuel Python Windows
# Usage: source activate_env.sh

if [ -d ".venv_windows" ]; then
    # Forcer l'utilisation du Python Windows
    export PATH="$(pwd)/.venv_windows/Scripts:$PATH"
    source .venv_windows/Scripts/activate 2>/dev/null || true
    echo "Environnement virtuel Windows active: .venv_windows"
    echo "Python: $(.venv_windows/Scripts/python.exe --version 2>&1)"
    echo "Pour utiliser Python directement: .venv_windows/Scripts/python.exe"
elif [ -d ".venv" ]; then
    source .venv/Scripts/activate
    echo "Environnement virtuel MSYS2 active: .venv"
    echo "Python: $(python --version)"
else
    echo "Aucun environnement virtuel trouve. Creer-en un avec:"
    echo "  python -m venv .venv_windows"
fi
