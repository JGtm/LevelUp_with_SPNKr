# Roadmap IA Avancée - OpenSpartan Graph

> **Date** : 1 février 2026  
> **Objectif** : Documenter les architectures IA avancées à implémenter après le RAG local.

---

## Vue d'Ensemble

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ÉVOLUTION IA DU PROJET                                │
│                                                                              │
│   PHASE 1 (Actuel)         PHASE 2 (En cours)       PHASE 3 (Futur)         │
│   ┌──────────────┐         ┌──────────────┐         ┌──────────────┐        │
│   │ Pre-commit   │         │  RAG Local   │         │ Agents 24/7  │        │
│   │ Hooks basiq. │ ──────▶ │  ChromaDB    │ ──────▶ │ Long-Running │        │
│   │ + MCP DuckDB │         │  + Git Hooks │         │ + Multi-LLM  │        │
│   └──────────────┘         └──────────────┘         └──────────────┘        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Self-Evolving Codebase (Git Hooks + IA)

### Concept

Chaque `git commit` déclenche une analyse IA qui :
- Met à jour automatiquement `.ai/features/`
- Vérifie la cohérence avec le schéma DuckDB
- Génère/met à jour les tests manquants
- Bloque le commit si les règles `.cursorrules` ne sont pas respectées

### Architecture Cible

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           git commit                                         │
│                               │                                              │
│                               ▼                                              │
│   ┌───────────────────────────────────────────────────────────────────────┐ │
│   │                    PRE-COMMIT HOOKS                                    │ │
│   │                                                                        │ │
│   │   ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────────┐ │ │
│   │   │  HOOKS ACTUELS  │   │   HOOKS IA      │   │   VALIDATION        │ │ │
│   │   │                 │   │   (NOUVEAUX)    │   │                     │ │ │
│   │   │ • ruff          │   │                 │   │ • schema-check      │ │ │
│   │   │ • ruff-format   │   │ • ai-doc-update │   │ • cursorrules-lint  │ │ │
│   │   │ • detect-secrets│   │ • ai-test-gen   │   │ • coverage-gate     │ │ │
│   │   │ • check-yaml    │   │ • ai-review     │   │                     │ │ │
│   │   └─────────────────┘   └─────────────────┘   └─────────────────────┘ │ │
│   │                                                                        │ │
│   └───────────────────────────────────────────────────────────────────────┘ │
│                               │                                              │
│                               ▼                                              │
│                      ✓ Commit autorisé                                       │
│                      ✗ Commit bloqué + suggestions                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Hooks IA à Implémenter

#### 1.1 `ai-doc-update` - Mise à jour Documentation

```python
# hooks/ai_doc_update.py
"""
Hook pre-commit qui analyse les changements et met à jour .ai/features/
Utilise un LLM local (Ollama) ou API (Claude Haiku / GPT-4o-mini)
"""

import subprocess
import sys
from pathlib import Path

# Modèles recommandés (2026)
MODELS = {
    "local": "ollama/qwen2.5-coder:7b",      # Gratuit, rapide
    "cloud_cheap": "claude-3-5-haiku-latest", # ~$0.001/commit
    "cloud_smart": "claude-sonnet-4-20250514" # Pour gros refactoring
}

def get_changed_files():
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True
    )
    return [f for f in result.stdout.strip().split("\n") if f.endswith(".py")]

def analyze_and_update_docs(files: list[str], model: str = "local"):
    # 1. Lire les fichiers modifiés
    # 2. Appeler le LLM pour générer/mettre à jour la doc
    # 3. Écrire dans .ai/features/{module}.md
    pass

if __name__ == "__main__":
    files = get_changed_files()
    if files:
        analyze_and_update_docs(files)
    sys.exit(0)
```

#### 1.2 `ai-test-gen` - Génération de Tests

```python
# hooks/ai_test_gen.py
"""
Génère des tests pour les nouvelles fonctions publiques.
Bloque si couverture < seuil pour les fichiers modifiés.
"""

COVERAGE_THRESHOLD = 80  # %

def find_untested_functions(changed_files: list[str]) -> list[str]:
    """Identifie les fonctions sans tests correspondants."""
    pass

def generate_tests(functions: list[str], model: str = "local"):
    """Génère des tests avec LLM."""
    pass
```

#### 1.3 `schema-coherence` - Validation Schéma DuckDB

```python
# hooks/schema_coherence.py
"""
Vérifie que les modèles Pydantic correspondent au schéma DuckDB/SQLite.
"""

from src.data.domain.models import Match, Medal, Player
import duckdb

def validate_schema_coherence():
    """Compare les modèles Pydantic avec le schéma réel."""
    conn = duckdb.connect("data/warehouse/metadata.db")
    # Extraire les colonnes des tables
    # Comparer avec les champs Pydantic
    # Signaler les divergences
    pass
```

### Configuration `.pre-commit-config.yaml` (Extension)

```yaml
# À ajouter aux hooks existants
repos:
  # ... hooks actuels ...

  - repo: local
    hooks:
      - id: ai-doc-update
        name: AI Documentation Update
        entry: python hooks/ai_doc_update.py
        language: python
        stages: [commit]
        pass_filenames: false
        additional_dependencies:
          - httpx
          - ollama  # ou anthropic/openai

      - id: ai-test-gen
        name: AI Test Generation
        entry: python hooks/ai_test_gen.py
        language: python
        stages: [commit]
        pass_filenames: false
        
      - id: schema-coherence
        name: Schema Coherence Check
        entry: python hooks/schema_coherence.py
        language: python
        stages: [commit]
        types: [python]
        files: ^src/data/domain/models/
```

### Effort Estimé

| Tâche | Effort | Priorité |
|-------|--------|----------|
| `ai-doc-update` | 1 jour | P1 |
| `schema-coherence` | 0.5 jour | P1 |
| `ai-test-gen` | 2 jours | P2 |
| Integration Ollama | 0.5 jour | P1 |

---

## 2. Architecture Multi-LLM via Router

### Concept

Un routeur intelligent qui choisit le modèle optimal selon :
- La complexité de la tâche
- Le budget
- La latence requise

### Modèles Recommandés (Février 2026)

| Catégorie | Modèle | Coût | Latence | Usage |
|-----------|--------|------|---------|-------|
| **Raisonnement Complexe** | Claude Opus 4.5 | $$$$$ | Lent | Architecture, debugging complexe |
| **Raisonnement Avancé** | Claude Sonnet 4 | $$$ | Moyen | Codage, refactoring |
| **Codage Rapide** | Claude 3.5 Haiku | $ | Rapide | Auto-complétion, small fixes |
| **Tâches Simples** | GPT-4.1-mini | ¢ | Très rapide | Formatage, nettoyage |
| **Local (Gratuit)** | Qwen2.5-Coder 7B | 0 | Variable | CI/CD, hooks, batch |
| **Local Puissant** | DeepSeek-V3 | 0 | Lent | Analyse complexe offline |

> ⚠️ **Note** : GPT-4o est obsolète (2024). Utiliser GPT-4.1-mini ou GPT-4.1-turbo pour les tâches simples.

### Architecture Router

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LLM ROUTER                                      │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                       CLASSIFICATEUR                                 │   │
│   │                                                                      │   │
│   │   Analyse la requête :                                               │   │
│   │   • Complexité (tokens, contexte requis)                            │   │
│   │   • Type (code, doc, format, debug)                                 │   │
│   │   • Urgence (sync vs async)                                         │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                               │                                              │
│              ┌────────────────┼────────────────┬──────────────┐             │
│              ▼                ▼                ▼              ▼             │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│   │   TIER 1     │  │   TIER 2     │  │   TIER 3     │  │   LOCAL      │   │
│   │              │  │              │  │              │  │              │   │
│   │ Claude Opus  │  │ Claude Sonnet│  │ Claude Haiku │  │ Qwen2.5-Coder│   │
│   │ 4.5          │  │ 4            │  │ 3.5          │  │ 7B (Ollama)  │   │
│   │              │  │              │  │              │  │              │   │
│   │ • Architecture│  │ • Codage    │  │ • Quick fix  │  │ • Hooks CI   │   │
│   │ • Debugging  │  │ • Refactor  │  │ • Complétion │  │ • Batch      │   │
│   │ • Conception │  │ • Review    │  │ • Formatage  │  │ • Offline    │   │
│   └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Implémentation avec LiteLLM

```python
# src/ai/router.py
"""
Router Multi-LLM utilisant LiteLLM pour abstraction.
"""

from litellm import Router
from enum import Enum

class TaskComplexity(Enum):
    TRIVIAL = "trivial"      # Formatage, typos
    SIMPLE = "simple"        # Petits fixes, complétion
    MEDIUM = "medium"        # Fonctions, tests
    COMPLEX = "complex"      # Architecture, debugging
    EXPERT = "expert"        # Conception, refactoring majeur

# Configuration des modèles
MODEL_CONFIG = [
    {
        "model_name": "tier-1",  # Expert
        "litellm_params": {
            "model": "claude-opus-4-20250514",
            "api_key": "...",
        },
        "model_info": {"max_tokens": 32000}
    },
    {
        "model_name": "tier-2",  # Standard
        "litellm_params": {
            "model": "claude-sonnet-4-20250514",
            "api_key": "...",
        }
    },
    {
        "model_name": "tier-3",  # Rapide
        "litellm_params": {
            "model": "claude-3-5-haiku-latest",
            "api_key": "...",
        }
    },
    {
        "model_name": "local",  # Gratuit
        "litellm_params": {
            "model": "ollama/qwen2.5-coder:7b",
            "api_base": "http://localhost:11434",
        }
    },
]

router = Router(model_list=MODEL_CONFIG)

def classify_task(prompt: str) -> TaskComplexity:
    """Classifie la complexité d'une tâche."""
    keywords_expert = ["architecture", "design", "refactor", "migrate"]
    keywords_complex = ["debug", "fix bug", "investigate", "optimize"]
    keywords_simple = ["format", "rename", "add comment", "typo"]
    
    prompt_lower = prompt.lower()
    
    if any(kw in prompt_lower for kw in keywords_expert):
        return TaskComplexity.EXPERT
    elif any(kw in prompt_lower for kw in keywords_complex):
        return TaskComplexity.COMPLEX
    elif any(kw in prompt_lower for kw in keywords_simple):
        return TaskComplexity.TRIVIAL
    else:
        return TaskComplexity.MEDIUM

def route_request(prompt: str, prefer_local: bool = False) -> str:
    """Route la requête vers le modèle optimal."""
    complexity = classify_task(prompt)
    
    model_map = {
        TaskComplexity.EXPERT: "tier-1",
        TaskComplexity.COMPLEX: "tier-2",
        TaskComplexity.MEDIUM: "tier-2" if not prefer_local else "local",
        TaskComplexity.SIMPLE: "tier-3",
        TaskComplexity.TRIVIAL: "local",
    }
    
    model = model_map[complexity]
    
    response = router.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.choices[0].message.content
```

### Services Alternatifs

| Service | Description | Avantage |
|---------|-------------|----------|
| **LiteLLM** | Abstraction Python | Open source, simple |
| **OpenRouter** | API unifiée | Pas de config, 100+ modèles |
| **Portkey** | Gateway IA | Observabilité, fallbacks |
| **BrainTrust** | Évaluation + routing | Logs, A/B testing |

### Effort Estimé

| Tâche | Effort | Priorité |
|-------|--------|----------|
| Setup LiteLLM | 0.5 jour | P2 |
| Classificateur de tâches | 1 jour | P2 |
| Intégration scripts existants | 1 jour | P2 |
| Fallback automatique | 0.5 jour | P3 |

---

## 3. Agents Long-Running (24/7)

### Concept

Des agents autonomes qui tournent en continu pour :
- Surveiller l'API Halo pour nouveaux matchs
- Détecter anomalies (nouvelles médailles, maps, etc.)
- Générer du code automatiquement
- Notifier via Discord/Slack

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     SERVEUR / GITHUB ACTIONS                                 │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    HALO WATCHER AGENT                                │   │
│   │                                                                      │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │                   BOUCLE PRINCIPALE                          │   │   │
│   │   │                                                              │   │   │
│   │   │   while True:                                                │   │   │
│   │   │       # 1. Poll API Halo (toutes les 5 min)                 │   │   │
│   │   │       new_matches = check_for_new_matches()                 │   │   │
│   │   │                                                              │   │   │
│   │   │       # 2. Ingest si nouveaux matchs                        │   │   │
│   │   │       if new_matches:                                        │   │   │
│   │   │           run_ingest_delta()                                 │   │   │
│   │   │                                                              │   │   │
│   │   │       # 3. Analyse anomalies                                │   │   │
│   │   │       anomalies = detect_anomalies()                        │   │   │
│   │   │                                                              │   │   │
│   │   │       # 4. Actions automatiques                             │   │   │
│   │   │       for anomaly in anomalies:                             │   │   │
│   │   │           handle_anomaly(anomaly)  # PR, notification       │   │   │
│   │   │                                                              │   │   │
│   │   │       sleep(300)  # 5 minutes                               │   │   │
│   │   │                                                              │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                               │                                              │
│                               ▼                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    HANDLERS D'ANOMALIES                              │   │
│   │                                                                      │   │
│   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │   │
│   │   │ NEW_MEDAL    │  │ NEW_MAP      │  │ API_CHANGE               │  │   │
│   │   │              │  │              │  │                          │  │   │
│   │   │ • Git branch │  │ • Git branch │  │ • Alerte Discord         │  │   │
│   │   │ • Add to DB  │  │ • Add to DB  │  │ • Issue GitHub           │  │   │
│   │   │ • Gen icon   │  │ • Gen thumb  │  │ • Log détaillé           │  │   │
│   │   │ • PR auto    │  │ • PR auto    │  │                          │  │   │
│   │   │ • Discord    │  │ • Discord    │  │                          │  │   │
│   │   └──────────────┘  └──────────────┘  └──────────────────────────┘  │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Option 1 : GitHub Actions (Gratuit, Simple)

```yaml
# .github/workflows/halo-watcher.yml
name: Halo API Watcher

on:
  schedule:
    - cron: '*/15 * * * *'  # Toutes les 15 minutes
  workflow_dispatch:         # Déclenchement manuel

env:
  SPARTAN_TOKEN: ${{ secrets.SPARTAN_TOKEN }}
  CLEARANCE_TOKEN: ${{ secrets.CLEARANCE_TOKEN }}
  DISCORD_WEBHOOK: ${{ secrets.DISCORD_WEBHOOK }}

jobs:
  watch:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          
      - name: Install dependencies
        run: pip install -r requirements.txt
        
      - name: Check for new matches
        run: python scripts/watcher/check_new_matches.py
        
      - name: Detect anomalies
        run: python scripts/watcher/detect_anomalies.py
        
      - name: Create PR if needed
        uses: peter-evans/create-pull-request@v6
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          commit-message: "feat(auto): new content detected"
          title: "[Auto] New Halo content detected"
          body: |
            Detected by Halo Watcher Agent.
            
            Changes:
            - See commit details
          branch: auto/new-content
          
      - name: Notify Discord
        if: success()
        run: python scripts/watcher/notify_discord.py
```

### Option 2 : LangGraph (Puissant, Complexe)

```python
# agents/halo_watcher.py
"""
Agent long-running avec LangGraph pour surveillance Halo.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import TypedDict, Literal

class WatcherState(TypedDict):
    last_check: str
    new_matches: list
    anomalies: list
    actions_taken: list

def check_api(state: WatcherState) -> WatcherState:
    """Vérifie l'API pour nouveaux matchs."""
    # Appel API SPNKr
    return state

def analyze_data(state: WatcherState) -> WatcherState:
    """Analyse les données pour anomalies."""
    # Détection médailles/maps inconnues
    return state

def decide_action(state: WatcherState) -> Literal["create_pr", "notify", "end"]:
    """Décide de l'action à prendre."""
    if state["anomalies"]:
        return "create_pr"
    elif state["new_matches"]:
        return "notify"
    return "end"

def create_pr(state: WatcherState) -> WatcherState:
    """Crée une PR automatique."""
    # GitHub API
    return state

def notify(state: WatcherState) -> WatcherState:
    """Notifie via Discord."""
    # Discord webhook
    return state

# Graphe d'agent
workflow = StateGraph(WatcherState)
workflow.add_node("check_api", check_api)
workflow.add_node("analyze", analyze_data)
workflow.add_node("create_pr", create_pr)
workflow.add_node("notify", notify)

workflow.set_entry_point("check_api")
workflow.add_edge("check_api", "analyze")
workflow.add_conditional_edges("analyze", decide_action)
workflow.add_edge("create_pr", "notify")
workflow.add_edge("notify", END)

# Persistance avec SQLite
memory = SqliteSaver.from_conn_string("agents/watcher_memory.db")
app = workflow.compile(checkpointer=memory)

# Boucle infinie
while True:
    result = app.invoke({"last_check": "", "new_matches": [], "anomalies": [], "actions_taken": []})
    time.sleep(300)
```

### Frameworks Recommandés (2026)

| Framework | Complexité | Avantages | Inconvénients |
|-----------|------------|-----------|---------------|
| **GitHub Actions** | ⭐ | Gratuit, simple, intégré | Limité à 6h/job, pas de state |
| **Temporal** | ⭐⭐⭐ | Robuste, retry automatique | Complexe, infrastructure |
| **LangGraph** | ⭐⭐ | Flexible, checkpointing | Dépendance LangChain |
| **Prefect** | ⭐⭐ | UI, scheduling | Overhead pour petit projet |
| **Script + Cron** | ⭐ | Ultra simple | Pas de monitoring |

### Notifications Discord

```python
# scripts/watcher/notify_discord.py
import httpx
from datetime import datetime

WEBHOOK_URL = "https://discord.com/api/webhooks/..."

def send_notification(title: str, description: str, color: int = 0x00ff00):
    """Envoie une notification Discord."""
    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": "OpenSpartan Watcher Agent"}
    }
    
    httpx.post(WEBHOOK_URL, json={"embeds": [embed]})

# Exemples
send_notification(
    "🏅 Nouvelle médaille détectée !",
    "**Overkill Plus** a été ajoutée. PR automatique créée.",
    color=0xffd700
)

send_notification(
    "📊 Sync quotidien",
    "47 nouveaux matchs ingérés.\nVictoires: 28 | Défaites: 19",
    color=0x00bfff
)
```

### Effort Estimé

| Tâche | Effort | Priorité |
|-------|--------|----------|
| GitHub Actions watcher | 1 jour | P2 |
| Script détection anomalies | 1 jour | P2 |
| Notifications Discord | 0.5 jour | P2 |
| Auto-PR pour nouvelles entités | 1 jour | P3 |
| LangGraph (optionnel) | 3 jours | P4 |

---

## Priorités Globales

| Phase | Composant | Effort Total | Impact |
|-------|-----------|--------------|--------|
| **2.1** | RAG Local (ChromaDB) | 2-3 jours | ⭐⭐⭐⭐⭐ |
| **2.2** | Git Hooks IA | 2 jours | ⭐⭐⭐⭐ |
| **3.1** | GitHub Actions Watcher | 2 jours | ⭐⭐⭐⭐ |
| **3.2** | Multi-LLM Router | 2 jours | ⭐⭐⭐ |
| **4.0** | LangGraph Full Agent | 5+ jours | ⭐⭐⭐⭐⭐ |

---

## Sources Utiles

### Documentation API Grunt (Nouvelle Source)

> **URL** : https://github.com/dend/grunt  
> **Status** : Devenu public récemment (2026)  
> **À indexer** : Endpoints, structures, authentification

Le repo Grunt contient :
- Wrappers .NET et TypeScript pour l'API Halo Infinite
- Documentation des endpoints (`settings.svc.halowaypoint.com`)
- Modèles de données (matchs, stats, economy)
- Flux d'authentification Azure AD

### Autres Sources pour RAG

- `docs/API_GRUNT_RESEARCH.md` (local)
- SPNKr documentation (https://github.com/acurtis166/SPNKr)
- Halo Waypoint (scraping docs)
- Fichiers `.ai/` du projet

---

*Dernière mise à jour : 2026-02-01*
