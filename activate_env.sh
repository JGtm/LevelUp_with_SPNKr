#!/bin/bash
# Script d'activation de l'environnement virtuel Python Windows
# Usage: source activate_env.sh

if [ -d ".venv_windows" ]; then
    source .venv_windows/Scripts/activate
    echo "Environnement virtuel Windows active: .venv_windows"
    echo "Python: $(python --version)"
elif [ -d ".venv" ]; then
    source .venv/Scripts/activate
    echo "Environnement virtuel MSYS2 active: .venv"
    echo "Python: $(python --version)"
else
    echo "Aucun environnement virtuel trouve. Creer-en un avec:"
    echo "  python -m venv .venv_windows"
fi
