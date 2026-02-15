# Commande /orchestrate

Agent d'orchestration principal - Point d'entrée pour toute demande complexe.

## Rôle

L'orchestrateur analyse la demande et délègue aux agents spécialisés appropriés.
Il coordonne le flux de travail et assure la cohérence entre les étapes.

## Usage
`/orchestrate [demande en langage naturel]`

## Logique de Routage

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         /orchestrate                                         │
│                              │                                               │
│                              ▼                                               │
│                    ┌─────────────────┐                                       │
│                    │ ANALYSE DEMANDE │                                       │
│                    └────────┬────────┘                                       │
│                             │                                                │
│       ┌─────────────────────┼─────────────────────┐                         │
│       ▼                     ▼                     ▼                         │
│  ┌─────────┐          ┌─────────┐           ┌─────────┐                     │
│  │ FEATURE │          │  BUG    │           │ QUESTION│                     │
│  │ nouvelle│          │ à fixer │           │ exploration                   │
│  └────┬────┘          └────┬────┘           └────┬────┘                     │
│       │                    │                     │                          │
│       ▼                    ▼                     ▼                          │
│    /plan               /debug              /explore-feature                 │
│       │                    │                     │                          │
│       ▼                    ▼                     │                          │
│   /implement            /test                    │                          │
│       │                    │                     │                          │
│       ▼                    │                     │                          │
│    /test ◄─────────────────┘                     │                          │
│       │                                          │                          │
│       ▼                                          │                          │
│   /review                                        │                          │
│       │                                          │                          │
│       ▼                                          ▼                          │
│   /handoff ◄─────────────────────────────────────┘                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Étapes de l'Orchestrateur

### 1. Lecture du contexte
```
□ Lire .ai/project_map.md (architecture actuelle)
□ Lire .ai/thought_log.md (décisions récentes)
□ Lire .ai/current_plan.md (travail en cours)
□ Consulter RAG si question API Halo (via MCP halo-rag)
```

### 1b. Enrichissement RAG (si MCP halo-rag activé)

Pour les demandes liées à l'API Halo ou à des patterns du projet :

```
CallMcpTool("halo-rag", "get_context", {
    "query": "[résumé de la demande]",
    "max_tokens": 2000
})
```

Cela permet d'avoir le contexte pertinent AVANT de planifier l'implémentation.

### 2. Classification de la demande

| Type de demande | Mots-clés | Agent(s) à invoquer |
|-----------------|-----------|---------------------|
| Nouvelle feature | "ajouter", "créer", "implémenter" | /rag-search (contexte) → /plan → /implement → /test → /review |
| Bug fix | "bug", "erreur", "ne marche pas", "crash" | /debug → /test |
| Exploration | "comment", "où", "expliquer", "comprendre" | /rag-search → /explore-feature |
| Refactoring | "refactorer", "nettoyer", "optimiser" | /plan → /implement → /test |
| Données | "sync", "ingestion", "importer" | /ingest ou /query-halo |
| Vérification | "vérifier", "valider", "tester" | /verify-db ou /test |
| Question SQL | "requête", "stats", "combien" | /query-halo |
| Question API Halo | "endpoint", "API", "Grunt", "SPNKr" | /rag-search |

### 3. Exécution du workflow

Pour chaque agent invoqué :
1. Annoncer l'agent en cours
2. Exécuter le workflow de l'agent
3. Vérifier le succès avant de passer au suivant
4. En cas d'échec, router vers /debug

### 4. Suivi et documentation

```
□ Créer/mettre à jour .ai/current_plan.md
□ Logger les décisions dans .ai/thought_log.md
□ Proposer /handoff en fin de session
```

## Exemples de Routage

### Exemple 1: Nouvelle feature
```
Demande: "Ajoute un graphique des KDA par playlist"

Orchestration:
1. /plan "graphique KDA par playlist"
   → Génère le plan d'implémentation
2. /implement
   → Code le graphique
3. /test
   → Génère tests pour le nouveau composant
4. /review
   → Vérifie qualité du code
5. /handoff
   → Documente pour prochaine session
```

### Exemple 2: Bug fix
```
Demande: "Le sync delta ne fonctionne plus depuis hier"

Orchestration:
1. /debug "sync delta ne fonctionne plus"
   → Investigation systématique
2. /test "delta_sync"
   → Valide la correction
3. /handoff
   → Documente le fix
```

### Exemple 3: Question
```
Demande: "Comment fonctionne le cache dans l'app ?"

Orchestration:
1. /explore-feature "cache"
   → Documente le système de cache
2. (Pas de /handoff nécessaire - lecture seule)
```

## Gestion des erreurs

```
┌─────────────────────────────────────────────────────────────┐
│                     AGENT ÉCHOUE                            │
│                          │                                   │
│              ┌───────────┴───────────┐                      │
│              ▼                       ▼                      │
│     Erreur technique          Erreur logique                │
│     (import, syntax)          (test fail)                   │
│              │                       │                      │
│              ▼                       ▼                      │
│         Fix immédiat            /debug                      │
│              │                       │                      │
│              └───────────┬───────────┘                      │
│                          ▼                                   │
│                    Reprendre workflow                        │
└─────────────────────────────────────────────────────────────┘
```

## Parallélisation

L'orchestrateur peut lancer des sous-agents en parallèle quand possible :

```
Demande: "Explore le cache ET le système de sync"

Parallélisation:
┌─────────────┐     ┌─────────────┐
│ Task        │     │ Task        │
│ explore     │     │ explore     │
│ "cache"     │     │ "sync"      │
└──────┬──────┘     └──────┬──────┘
       │                   │
       └─────────┬─────────┘
                 ▼
          Résultats agrégés
```

## Checklist de sortie

- [ ] Demande analysée et classifiée
- [ ] Agents appropriés invoqués dans le bon ordre
- [ ] Chaque étape validée avant passage à la suivante
- [ ] Contexte .ai/ mis à jour
- [ ] Prochaines étapes claires pour l'utilisateur
