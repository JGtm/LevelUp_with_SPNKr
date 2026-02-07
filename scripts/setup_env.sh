#!/bin/bash
# Configuration de l'environnement Python pour LevelUp (Git Bash)
# Usage: bash scripts/setup_env.sh

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Convertir chemin Git Bash -> Windows pour cmd
to_win_path() {
    echo "$1" | sed 's|^/\([a-zA-Z]\)/|\1:/|' | sed 's|/|\\|g'
}
REPO_WIN=$(to_win_path "$REPO_ROOT")

# Trouver Python Windows via py (Launcher)
PY_EXE=""
for v in 3.12 3.11 3.10; do
    out=$(cmd //c "py -$v -c \"import sys; print(sys.executable)\"" 2>/dev/null | tr -d '\r\n')
    if [ -n "$out" ]; then
        PY_EXE="$out"
        break
    fi
done
[ -z "$PY_EXE" ] && PY_EXE=$(cmd //c "py -3 -c \"import sys; print(sys.executable)\"" 2>/dev/null | tr -d '\r\n')

# Fallback: chemins Windows typiques (Git Bash)
if [ -z "$PY_EXE" ]; then
    U="${USERNAME:-$USER}"
    for base in "/c/Users/$U/AppData/Local/Programs/Python" "/c/Python312" "/c/Python311" "/c/Python310"; do
        for p in Python312 Python311 Python310; do
            cand="$base/$p/python.exe"
            [ -f "$cand" ] && PY_EXE="$(to_win_path "$cand")" && break 2
        done
        [ -f "$base/python.exe" ] && PY_EXE="$(to_win_path "$base/python.exe")" && break
    done
fi

if [ -z "$PY_EXE" ]; then
    echo "ERREUR: Python Windows non trouvé."
    echo "Assurez-vous que Python (python.org) est installé et dans le PATH."
    echo "Ou créez .venv_windows manuellement avec le Python de votre choix."
    exit 1
fi

echo "Python: $PY_EXE"

VENV_DIR=".venv_windows"
[ -d "$VENV_DIR" ] && rm -rf "$VENV_DIR"

echo "Création du venv..."
cmd //c "cd /d $REPO_WIN && \"$PY_EXE\" -m venv $VENV_DIR"

echo "Installation des dépendances..."
"$REPO_ROOT/$VENV_DIR/Scripts/pip.exe" install --upgrade pip
"$REPO_ROOT/$VENV_DIR/Scripts/pip.exe" install -e ".[dev,spnkr]"

echo ""
echo "OK. Pour activer: source activate_env.sh"
