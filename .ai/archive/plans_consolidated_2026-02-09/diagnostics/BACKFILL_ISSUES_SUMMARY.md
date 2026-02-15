# Résumé des problèmes de logique de backfill

**Date** : 2026-02-09  
**Joueur testé** : Chocoboflor (228 matchs)

---

## ✅ Résultats pour Chocoboflor

La logique fonctionne **correctement** pour Chocoboflor car les tables contiennent déjà des données :

| Option | Matchs avec données | Matchs détectés | Statut |
|--------|---------------------|------------------|--------|
| `--events` | 223/228 | 5 | ✅ Correct |
| `--medals` | 187/228 | 41 | ✅ Correct |
| `--skill` | 228/228 | 0 | ✅ Correct |
| `--personal-scores` | 226/228 | 2 | ✅ Correct |
| `--participants` | 228/228 | 0 | ✅ Correct |

---

## ⚠️ Problèmes identifiés

### Problème principal : Options sans `--force-*` qui sélectionnent tous les matchs si table vide

#### 1. `--events` (ligne 772-777)
**Problème** : Pas d'option `--force-events` disponible.

**Comportement actuel** :
- Si `highlight_events` contient des données → fonctionne correctement ✅
- Si `highlight_events` est vide → sélectionne **TOUS** les matchs ⚠️

**Impact** : Pour JGtm (probablement 1000+ matchs), le backfill peut être très long si la table est vide.

**Recommandation** : Ajouter `--force-events` (comme `--force-medals`).

---

#### 2. `--skill` (ligne 779-785)
**Problème** : Pas d'option `--force-skill` disponible.

**Comportement actuel** :
- Si `player_match_stats` contient des données pour le joueur → fonctionne correctement ✅
- Si la table est vide pour le joueur → sélectionne **TOUS** les matchs ⚠️

**Recommandation** : Ajouter `--force-skill`.

---

#### 3. `--personal-scores` (ligne 787-793)
**Problème** : Pas d'option `--force-personal-scores` disponible.

**Comportement actuel** :
- Si `personal_score_awards` contient des données pour le joueur → fonctionne correctement ✅
- Si la table est vide pour le joueur → sélectionne **TOUS** les matchs ⚠️

**Recommandation** : Ajouter `--force-personal-scores`.

---

### Options qui fonctionnent correctement

#### ✅ Options avec `--force-*` disponible
- `--medals` → `--force-medals` ✅
- `--participants` → `--force-participants` ✅
- `--accuracy` → `--force-accuracy` ✅
- `--shots` → `--force-shots` ✅
- `--enemy-mmr` → `--force-enemy-mmr` ✅
- `--participants-shots` → `--force-participants-shots` ✅

#### ✅ Options utilisant `IS NULL` (pas de problème)
- `--accuracy` (vérifie `ms.accuracy IS NULL`)
- `--shots` (vérifie `ms.shots_fired IS NULL OR ms.shots_hit IS NULL`)
- `--performance-scores` (vérifie `performance_score IS NULL`)
- `--participants-scores` (vérifie `rank IS NULL OR score IS NULL`)
- `--participants-kda` (vérifie `kills IS NULL OR deaths IS NULL OR assists IS NULL`)
- `--participants-shots` (vérifie `shots_fired IS NULL OR shots_hit IS NULL`)

#### ✅ Options utilisant `IN` avec condition NULL (pas de problème)
- `--enemy-mmr` (utilise `IN` avec `enemy_mmr IS NULL`)
- `--participants-scores` (utilise `IN` avec `rank IS NULL OR score IS NULL`)
- `--participants-kda` (utilise `IN` avec `k/d/a IS NULL`)
- `--participants-shots` (utilise `IN` avec `shots IS NULL`)

---

## 📋 Recommandations

### Court terme
1. **Documenter le comportement** : Si une table est vide, tous les matchs seront traités (comportement attendu mais peut être surprenant)
2. **Ajouter les options `--force-*` manquantes** :
   - `--force-events`
   - `--force-skill`
   - `--force-personal-scores`

### Long terme
1. **Limiter par défaut** : Quand une table est vide, limiter automatiquement à un nombre raisonnable de matchs récents (ex: 50-100 derniers matchs) au lieu de tous les matchs
2. **Avertissement** : Afficher un avertissement si beaucoup de matchs seront traités (> 100)
3. **Utiliser `--max-matches` automatiquement** : Si plus de 100 matchs sont détectés, suggérer d'utiliser `--max-matches`

---

## 🔍 Diagnostic pour JGtm

Pour comprendre pourquoi tous les matchs sont sélectionnés pour JGtm avec `--events`, vérifier :

```sql
-- Compter les matchs avec highlight_events
SELECT COUNT(DISTINCT match_id) FROM highlight_events;

-- Si le résultat est 0 ou très faible, alors tous les matchs seront sélectionnés
-- C'est le comportement attendu mais peut être surprenant
```

**Hypothèse** : La table `highlight_events` de JGtm est probablement vide ou presque vide, ce qui explique pourquoi tous les matchs sont sélectionnés.

---

## 📝 Fichiers de diagnostic créés

1. `.ai/diagnostics/BACKFILL_EVENTS_ANALYSIS.md` - Analyse initiale du problème
2. `.ai/diagnostics/BACKFILL_LOGIC_COMPLETE_ANALYSIS.md` - Analyse complète de toutes les options
3. `scripts/verify_backfill_logic.py` - Script de vérification réutilisable
