# Commande /rag-search

Recherche dans la base de connaissances RAG (documentation API Halo, code projet, repo Grunt).

## Prérequis
- MCP `halo-rag` activé dans `.cursor/mcp.json`
- Base indexée via `python scripts/index_knowledge_base.py`

## Usage
`/rag-search [question ou termes de recherche]`

## Outils MCP Disponibles

### 1. search_knowledge
Recherche sémantique générale dans la base.

```
CallMcpTool("halo-rag", "search_knowledge", {
    "query": "Comment fonctionne l'authentification Spartan Token?",
    "top_k": 5
})
```

### 2. get_api_doc
Recherche optimisée pour la documentation API Halo.

```
CallMcpTool("halo-rag", "get_api_doc", {
    "topic": "career rank endpoint"
})
```

### 3. get_context
Génère un contexte formaté pour enrichir un prompt.

```
CallMcpTool("halo-rag", "get_context", {
    "query": "Comment implémenter le refresh des matchs?",
    "max_tokens": 4000
})
```

### 4. get_stats
Affiche les statistiques de la base.

```
CallMcpTool("halo-rag", "get_stats", {})
```

## Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           /rag-search                                        │
│                               │                                              │
│                               ▼                                              │
│   ┌───────────────────────────────────────────────────────────────────────┐ │
│   │                    ANALYSE DE LA QUESTION                              │ │
│   │                                                                        │ │
│   │   Question API Halo?  ──────────▶  get_api_doc                        │ │
│   │   Question technique? ──────────▶  search_knowledge                   │ │
│   │   Besoin de contexte? ──────────▶  get_context                        │ │
│   │                                                                        │ │
│   └───────────────────────────────────────────────────────────────────────┘ │
│                               │                                              │
│                               ▼                                              │
│   ┌───────────────────────────────────────────────────────────────────────┐ │
│   │                    PRÉSENTATION RÉSULTATS                              │ │
│   │                                                                        │ │
│   │   • Résumer les documents pertinents                                  │ │
│   │   • Citer les sources (fichier local ou GitHub)                       │ │
│   │   • Proposer des actions concrètes si applicable                      │ │
│   │                                                                        │ │
│   └───────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Exemples

### Recherche API
```
/rag-search Comment obtenir les stats de match d'un joueur ?

→ Résultat:
  - Source: grunt/src/node/README.md
  - "Utiliser client.stats.getMatchStats(matchId)"
  - Endpoint: GET /hi/stats/matches/{matchId}
```

### Recherche code projet
```
/rag-search Comment fonctionne le cache Streamlit ?

→ Résultat:
  - Source: src/ui/cache.py
  - "@st.cache_data avec TTL pour éviter recalculs"
```

### Contexte pour implémentation
```
/rag-search get_context: authentification Azure AD

→ Retourne un bloc de contexte formaté prêt à être utilisé
```

## Sources Indexées

| Source | Type | Contenu |
|--------|------|---------|
| `docs/` | local | Documentation projet |
| `.ai/` | local | Contexte agentique |
| `src/` | local | Code source Python |
| `dend/grunt` | GitHub | API wrapper Halo (C#, TypeScript) |

## Fallback (si MCP indisponible)

```python
from src.ai.rag import HaloKnowledgeBase, RAGConfig

kb = HaloKnowledgeBase(RAGConfig())
results = kb.search("votre question")

for r in results:
    print(f"Score: {r.score:.2f}")
    print(f"Source: {r.source}")
    print(f"Contenu: {r.content[:300]}...")
```
