# Score de performance (Comparaison de session)

Cette page documente le **score de performance** affiché dans l’onglet **Comparaison de session**.

- Calcul : [src/ui/components/performance.py](../src/ui/components/performance.py)
- UI (expander + affichage) : [src/ui/pages/session_compare.py](../src/ui/pages/session_compare.py)

## Objectif

Fournir une **note simple (0–100)** pour comparer deux sessions, basée sur quelques indicateurs robustes et disponibles sur la majorité des matchs.

> Important : ce score est un **heuristique** (pas un classement officiel). Il sert surtout à comparer *ta session A vs ta session B* avec les mêmes règles.

## Formule actuelle (v1)

Le score final est une moyenne pondérée de 4 composantes :

- **K/D normalisé** : 30%
- **Taux de victoire** : 25%
- **Précision** : 25%
- **Score moyen par partie** : 20%

### 1) K/D normalisé (30%)

- $KD = \frac{\sum kills}{\sum deaths}$ (si deaths=0, on utilise $\sum kills$)
- $S_{KD} = clamp(KD \times 50, 0, 100)$

Repères :
- $KD = 1.0 \Rightarrow 50$ points
- $KD = 2.0 \Rightarrow 100$ points

### 2) Taux de victoire (25%)

- `wins` = nombre de matchs où `outcome == 2`
- $win\_rate = \frac{wins}{n\_matches}$
- $S_{win} = win\_rate \times 100$

### 3) Précision (25%)

- Moyenne de `accuracy` (ou fallback `shots_accuracy`)
- Si la donnée n’existe pas, la composante est mise à **50 (neutre)**

> La précision est supposée être déjà sur une échelle 0–100.

### 4) Score moyen par partie (20%)

- Moyenne de `match_score`
- Normalisation : $S_{score} = clamp(avg\_score \times 5, 0, 100)$
- Si `match_score` est absent, la composante est mise à **50 (neutre)**

### Score final

$$score = 0.30 \cdot S_{KD} + 0.25 \cdot S_{win} + 0.25 \cdot S_{acc} + 0.20 \cdot S_{score}$$

## Ce qui est calculé mais non inclus

- **KDA / FDA** : $(kills + assists) / deaths$ est affiché dans les métriques détaillées, mais **n’entre pas** dans la formule du score.
- **MMR** : `team_mmr`, `enemy_mmr`, `delta_mmr_avg` sont calculés (si présents) et affichés dans la page, mais **n’entrent pas** dans le score.

## Limites connues

- **Biais “Slayer”** : la formule valorise surtout l’efficacité au combat et la victoire, moins l’impact objectif.
- **Modes objectifs variables** : on peut avoir des stats d’objectifs (CTF, Strongholds, Oddball, King of the Hill…), mais **elles ne sont pas toujours disponibles** selon les matchs / playlists / sources de données.
- **Sessions courtes** : sur 1–2 matchs, le score peut être instable (bruit).
- **Données manquantes** : certaines composantes retombent à 50, ce qui peut rendre le score plus “neutre” que nécessaire.

## Pistes d’amélioration (roadmap)

Voici des idées compatibles avec le projet (et généralement plus “justes”) :

1. **Normaliser par playlist/mode**
   - Utiliser des percentiles (ou z-score) *par mode* plutôt qu’une normalisation fixe pour `match_score` et parfois la précision.

2. **Ajouter une composante “Objectif” (si disponible)**
   - Pondération adaptative selon le type de mode.
   - Exemples de signaux : captures/holds/returns, time-on-objective, hill time, ball time…
   - Si absent : soit ignorer et renormaliser les poids, soit afficher “score partiel”.

3. **Prendre en compte la difficulté (MMR adverse / écart MMR)**
   - Bonus/malus léger en fonction de `delta_mmr_avg` (performance contre plus fort vs plus faible).

4. **Robustesse sessions courtes**
   - “Shrinkage” vers 50 quand `n_matches` est faible (ex : < 5).
   - Afficher un indicateur de confiance (faible / moyenne / élevée).

---

Si tu veux, je peux implémenter une **v2** (objectif + renormalisation + option MMR) tout en gardant la v1 en fallback, pour ne rien casser sur les données incomplètes.

## Formule v2 (modulaire)

La v2 est conçue pour être **réutilisable** et **robuste aux colonnes manquantes**.

Principes :

- Chaque composante calcule un sous-score 0–100.
- Si une composante n’a pas les données nécessaires, elle est **ignorée**.
- Les pondérations sont **renormalisées** sur les composantes restantes.
- Une composante **Objectif** est incluse automatiquement si des colonnes objectifs existent.

Composantes et poids de base (si toutes disponibles) :

- K/D : 25%
- Victoires : 20%
- Précision : 15%
- Kills/min : 15%
- Survie (durée de vie moyenne) : 10%
- Objectif : 15% (si colonnes présentes)

Optionnel : un ajustement léger selon l’**écart MMR moyen** peut être appliqué.

Implémentation : [src/analysis/performance_score.py](../src/analysis/performance_score.py)
