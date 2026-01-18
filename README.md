# OpenSpartan Graph (Halo Infinite)

Dashboard Streamlit + outils CLI pour analyser ta progression (frags/morts/ratio, précision, FDA, durée de vie moyenne, etc.) à partir de la base SQLite locale d’OpenSpartan Workshop.

## Prérequis

- Windows 10/11
- Python 3.10+ (idéalement 3.11)
- OpenSpartan Workshop installé (pour générer/mettre à jour la DB)

## Installation

Dans un terminal, à la racine du projet:

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -U pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Lancer le dashboard

Le plus simple:

- Double-clique sur `run_dashboard.bat`

Ou en ligne de commande:

```bash
.venv\Scripts\python.exe run_dashboard.py
```

Ou directement Streamlit:

```bash
.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

### Base de données

Par défaut, l’app essaye de trouver automatiquement la DB la plus récente dans:

- `%LOCALAPPDATA%\OpenSpartan.Workshop\data\*.db`

Tu peux aussi fournir un chemin de DB différent dans la sidebar.

## CLI (PNG)

Le script CLI peut générer un PNG statique:

```bash
.venv\Scripts\python.exe openspartan_graph.py --db "%LOCALAPPDATA%\OpenSpartan.Workshop\data\<ton_xuid>.db" --last 80 --out "out\kills_deaths_ratio.png"
```

## Notes

- Certaines stats (ex: temps joué) peuvent être absentes sur certains matchs; les métriques “par minute” ignorent les matchs sans durée valide.
- Le filtrage par défaut exclut Firefight et limite à certaines playlists (Quick Play / Ranked Slayer / Ranked Arena), mais tu peux le désactiver dans la sidebar.
