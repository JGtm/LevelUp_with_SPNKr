# References - Documents de Référence

Ce dossier contient des documents de best practices vérifiés manuellement.

## Pourquoi ?

> "I don't like using blackbox mcp services and websearch results that I can't check before they're used"

Les résultats de recherche web et les services MCP externes ne sont pas vérifiables. Pour les implémentations critiques, on préfère :

1. Demander à ChatGPT/Claude (interface normale) un doc best practices
2. **Réviser manuellement** le contenu
3. Dropper dans ce dossier
4. Référencer dans les prompts de planning

## Contenu Suggéré

| Fichier | Sujet |
|---------|-------|
| `oauth2-best-practices.md` | Implémentation OAuth2 sécurisée |
| `polars-optimization.md` | Patterns Polars performants |
| `duckdb-partitioning.md` | Stratégies de partitionnement |
| `streamlit-caching.md` | Patterns de cache Streamlit |
| `pydantic-v2-patterns.md` | Validation Pydantic v2 |
| `pytest-fixtures.md` | Patterns de fixtures pytest |

## Utilisation dans les Prompts

```markdown
Avant d'implémenter OAuth :
1. Lis .ai/references/oauth2-best-practices.md
2. Suis les recommandations de sécurité
3. Valide avec security-specialist
```

## Qualité

- ✅ Vérifié manuellement avant commit
- ✅ Sources citées si applicable
- ✅ Date de création/mise à jour
- ❌ Pas de copier-coller aveugle
