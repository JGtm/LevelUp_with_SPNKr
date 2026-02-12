# P9 — Heatmap d'Impact & Cercle d'Amis

> **Sprint** : 12 (après S11)  
> **Date** : 2026-02-12  
> **Prérequis** : Sprints 0-11 livrés  
> **Durée estimée** : 2.5 jours  
>
> **Specification** : Ajouter une heatmap interactive montrant les moments clés par coéquipier (First Blood, Clutch Finisher, Last Casualty) + tableau de "taquinerie" avec scoring d'impact.

---

## 🎯 Objectif utilisateur

Dans l'onglet **Coéquipiers**, ajouter un nouvel onglet **"Impact & Taquinerie"** permettant de :
1. **Visualiser une heatmap** : Joueurs (Y-axis) × Matchs (X-axis)
2. **Identifier les événements clés** par couleur :
   - 🟢 **Premier Sang** (+1) : Premier kill du match par ce joueur
   - 🟡 **Finisseur** (+2) : Dernier kill sur victoire
   - 🔴 **Boulet** (-1) : Dernière mort sur défaite
3. **Afficher un ranking** avec scores de "taquinerie" :
   - 🏆 MVP de la soirée (score max)
   - 🍌 Maillon faible (score min)

---

## 📊 Pipeline de données

```
Highlight Events (table)
├─ event_type: "Kill" ou "Death"
├─ time_ms: timestamp en millisecondes
├─ xuid: identifiant joueur
├─ match_id: référence match
├─ gamertag: nom affichage
└─ ...

                 ↓↓↓

DuckDBRepository.load_friends_impact_data(
  match_ids=[...],           # Filtré par date/playlist/mode/map
  friend_xuids=[...],        # Amis sélectionnés dans teammates.py
)

                 ↓↓↓

friends_impact.py
├─ identify_first_blood() →     {match_id: (xuid, time_ms)}
├─ identify_clutch_finisher()→ {match_id: (xuid, time_ms)}
├─ identify_last_casualty() →  {match_id: (xuid, time_ms)}
└─ compute_impact_scores()  →  {xuid: score}  (trié DESC)

                 ↓↓↓

friends_impact_heatmap.py
├─ plot_friends_impact_heatmap()  → Figure Plotly
└─ build_impact_table()           → DataFrame rangés

                 ↓↓↓

teammates.py (nouvel onglet)
├─ Heatmap (full width)
├─ Tableau "Taquinerie" (dessous)
└─ Messages d'erreur graceful
```

---

## 🔧 Implémentation détaillée

### 1. `src/analysis/friends_impact.py` (NOUVEAU)

```python
"""
Module de calcul des événements d'impact coéquipiers.

Responsabilités:
- Identifier First Blood (premier kill du match)
- Identifier Clutch Finisher (dernier kill + victoire)
- Identifier Last Casualty (dernière mort + défaite)
- Calcul score de taquinerie (+2/+1/-1)
- Gestion des edge cases (zéro événement, joueurs absents)
"""

from typing import Dict, Tuple, List, Any
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


def identify_first_blood(
    match_events: Dict[str, List[Dict[str, Any]]],
    friend_xuids: set[str],
) -> Dict[str, Tuple[str, int]]:
    """
    Identifie le joueur qui a fait le premier kill de chaque match.

    Args:
        match_events: {match_id: [event1, event2, ...]}
                      où event = {"event_type": "Kill", "xuid": "...", "time_ms": 1234, ...}
        friend_xuids: Ensemble des XUIDs "amis" à filtrer

    Returns:
        {match_id: (xuid, time_ms)} ou {} si aucun kill trouvé
    """
    result = {}
    for match_id, events in match_events.items():
        # Filtrer les kills de la liste des amis
        kills = [
            e for e in events
            if e.get("event_type", "").lower() == "kill"
            and e.get("xuid") in friend_xuids
        ]
        if kills:
            # Trier par timestamp croissant, prendre le premier
            first_kill = min(kills, key=lambda e: e.get("time_ms", float("inf")))
            result[match_id] = (first_kill.get("xuid"), first_kill.get("time_ms", 0))
    return result


def identify_clutch_finisher(
    match_events: Dict[str, List[Dict[str, Any]]],
    match_outcomes: Dict[str, int],  # {match_id: outcome} où 2=Win
    friend_xuids: set[str],
) -> Dict[str, Tuple[str, int]]:
    """
    Identifie le joueur qui a fait le dernier kill sur une VICTOIRE.

    Args:
        match_events: {match_id: [event1, event2, ...]}
        match_outcomes: {match_id: outcome} où 2 = victoire
        friend_xuids: Ensemble des XUIDs "amis"

    Returns:
        {match_id: (xuid, time_ms)} (seulement matchs gagnés)
    """
    result = {}
    for match_id, events in match_events.items():
        # Vérifier que c'est une victoire (outcome=2)
        if match_outcomes.get(match_id) != 2:
            continue

        # Filtrer les kills de la liste des amis
        kills = [
            e for e in events
            if e.get("event_type", "").lower() == "kill"
            and e.get("xuid") in friend_xuids
        ]
        if kills:
            # Trier par timestamp décroissant, prendre le dernier
            last_kill = max(kills, key=lambda e: e.get("time_ms", 0))
            result[match_id] = (last_kill.get("xuid"), last_kill.get("time_ms", 0))
    return result


def identify_last_casualty(
    match_events: Dict[str, List[Dict[str, Any]]],
    match_outcomes: Dict[str, int],  # {match_id: outcome} où 3=Loss
    friend_xuids: set[str],
) -> Dict[str, Tuple[str, int]]:
    """
    Identifie le joueur qui a subit la dernière mort sur une DÉFAITE.

    Args:
        match_events: {match_id: [event1, event2, ...]}
        match_outcomes: {match_id: outcome} où 3 = défaite
        friend_xuids: Ensemble des XUIDs "amis"

    Returns:
        {match_id: (xuid, time_ms)} (seulement matchs perdus)
    """
    result = {}
    for match_id, events in match_events.items():
        # Vérifier que c'est une défaite (outcome=3)
        if match_outcomes.get(match_id) != 3:
            continue

        # Filtrer les deaths de la liste des amis
        deaths = [
            e for e in events
            if e.get("event_type", "").lower() == "death"
            and e.get("xuid") in friend_xuids
        ]
        if deaths:
            # Trier par timestamp décroissant, prendre la dernière
            last_death = max(deaths, key=lambda e: e.get("time_ms", 0))
            result[match_id] = (last_death.get("xuid"), last_death.get("time_ms", 0))
    return result


def compute_impact_scores(
    first_bloods: Dict[str, Tuple[str, int]],
    clutches: Dict[str, Tuple[str, int]],
    casualties: Dict[str, Tuple[str, int]],
) -> Dict[str, int]:
    """
    Calcule le score de taquinerie par joueur.

    Scoring:
    - +2 pour chaque Clutch Finisher
    - +1 pour chaque First Blood
    - -1 pour chaque Last Casualty

    Args:
        first_bloods: {match_id: (xuid, time_ms)}
        clutches: {match_id: (xuid, time_ms)}
        casualties: {match_id: (xuid, time_ms)}

    Returns:
        {xuid: score} trié par score (DESC)
    """
    scores = defaultdict(int)

    # +1 pour chaque First Blood
    for xuid, _ in first_bloods.values():
        scores[xuid] += 1

    # +2 pour chaque Clutch
    for xuid, _ in clutches.values():
        scores[xuid] += 2

    # -1 pour chaque Last Casualty
    for xuid, _ in casualties.values():
        scores[xuid] -= 1

    # Trier par score décroissant (puis par XUID pour stabilité)
    return dict(sorted(
        scores.items(),
        key=lambda x: (-x[1], x[0])  # Score DESC, XUID ASC
    ))


def _safe_int(val: Any, default: int = 0) -> int:
    """Convertir de manière sécurisée en int."""
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _safe_str(val: Any, default: str = "") -> str:
    """Convertir de manière sécurisée en str."""
    try:
        return str(val).strip()
    except (TypeError, AttributeError):
        return default
```

---

### 2. `src/data/repositories/duckdb_repo.py` - ADD METHOD

Ajouter cette méthode au `DuckDBRepository` :

```python
def load_friends_impact_data(
    self,
    match_ids: list[str],
    friend_xuids: list[str],
) -> tuple[dict[str, list[dict]], dict[str, int]]:
    """
    Charge les événements necessaires pour calculer l'impact des coéquipiers.

    Args:
        match_ids: Liste des IDs de matchs à analyser
        friend_xuids: Liste des XUIDs "amis" à filtrer

    Returns:
        Tuple (match_events, match_outcomes)
        - match_events: {match_id: [event1, event2, ...]}
        - match_outcomes: {match_id: outcome} où 2=Win, 3=Loss
    """
    if not match_ids or not friend_xuids:
        return {}, {}

    try:
        # Charger highlight_events
        placeholders_matches = ",".join(["?"] * len(match_ids))
        placeholders_xuids = ",".join(["?"] * len(friend_xuids))
        
        result_events = self._conn.execute(
            f"""
            SELECT match_id, event_type, time_ms, xuid, gamertag
            FROM highlight_events
            WHERE match_id IN ({placeholders_matches})
              AND xuid IN ({placeholders_xuids})
            ORDER BY match_id, time_ms ASC
            """,
            match_ids + friend_xuids,
        )
        
        # Organiser par match_id
        match_events = {}
        for row in result_events.fetchall():
            match_id = row[0]
            event = {
                "match_id": match_id,
                "event_type": row[1],
                "time_ms": row[2],
                "xuid": row[3],
                "gamertag": row[4],
            }
            if match_id not in match_events:
                match_events[match_id] = []
            match_events[match_id].append(event)
        
        # Charger match_outcomes
        result_outcomes = self._conn.execute(
            f"""
            SELECT match_id, outcome
            FROM match_stats
            WHERE match_id IN ({placeholders_matches})
            """,
            match_ids,
        )
        
        match_outcomes = {row[0]: row[1] for row in result_outcomes.fetchall()}
        
        return match_events, match_outcomes

    except Exception as e:
        logger.warning(f"Erreur load_friends_impact_data: {e}")
        return {}, {}
```

---

### 3. `src/visualization/friends_impact_heatmap.py` (NOUVEAU)

```python
"""
Visualisations pour l'heatmap d'impact & tableau de taquinerie.

Cohérence design avec plot_win_ratio_heatmap() existant.
"""

from typing import Dict, Tuple, List, Any
import logging
import plotly.graph_objects as go
import polars as pl

logger = logging.getLogger(__name__)

# Couleurs standards (à harmoniser avec distributions.py)
COLOR_FIRST_BLOOD = "#2ecc71"   # Vert
COLOR_CLUTCH = "#f39c12"        # Or/Orange
COLOR_CASUALTY = "#e74c3c"      # Rouge


def plot_friends_impact_heatmap(
    first_bloods: Dict[str, Tuple[str, int]],
    clutches: Dict[str, Tuple[str, int]],
    casualties: Dict[str, Tuple[str, int]],
    gamertag_lookup: Dict[str, str],  # {xuid: gamertag}
    match_ids: List[str],
) -> go.Figure:
    """
    Crée une heatmap Plotly : Joueurs (Y) × Matchs (X).

    Chaque cellule peut avoir jusqu'à 3 événements (multi-select):
    - 🟢 Premier Sang
    - 🟡 Finisseur
    - 🔴 Boulet

    Args:
        first_bloods: {match_id: (xuid, time_ms)}
        clutches: {match_id: (xuid, time_ms)}
        casualties: {match_id: (xuid, time_ms)}
        gamertag_lookup: {xuid: gamertag} pour affichage
        match_ids: Liste des matchs (ordonnés chronologiquement)

    Returns:
        Figure Plotly heatmap
    """
    if not match_ids or not (first_bloods or clutches or casualties):
        # Retourner figure vide avec message
        return _empty_heatmap("Aucun événement d'impact détecté.")

    # Collecter tous les joueurs uniques
    all_xuids = set()
    for fb, cl, cas in [
        (first_bloods, clutches, casualties),
    ]:
        for xuid, _ in fb.values():
            all_xuids.add(xuid)
        for xuid, _ in cl.values():
            all_xuids.add(xuid)
        for xuid, _ in cas.values():
            all_xuids.add(xuid)

    if not all_xuids:
        return _empty_heatmap("Aucun joueur sélectionné.")

    # Construire la matrice : Joueurs × Matchs
    sorted_xuids = sorted(all_xuids)  # Pour ordre stable
    sorted_matches = match_ids  # Déjà trié par date

    # Créer matrice de couleurs : chaque cellule est soit vert/or/rouge/gris
    # Pour gérer multi-événements, on utilisera des symboles/annotations
    z_values = []  # Matrice pour heatmap
    hover_texts = []  # Texte tooltip riche
    annotations_list = []  # Symboles visuels

    for xuid in sorted_xuids:
        row_z = []
        row_hover = []
        row_idx = len(z_values)

        for match_idx, match_id in enumerate(sorted_matches):
            events_in_match = []
            cell_color_val = 0  # 1=green, 2=orange, 3=red

            # Vérifier First Blood
            if match_id in first_bloods and first_bloods[match_id][0] == xuid:
                events_in_match.append("🟢 Premier Sang")
                cell_color_val = 1

            # Vérifier Clutch
            if match_id in clutches and clutches[match_id][0] == xuid:
                events_in_match.append("🟡 Finisseur")
                cell_color_val = max(cell_color_val, 2)

            # Vérifier Last Casualty
            if match_id in casualties and casualties[match_id][0] == xuid:
                events_in_match.append("🔴 Boulet")
                cell_color_val = max(cell_color_val, 3)

            row_z.append(cell_color_val)

            # Hover text
            if events_in_match:
                gamertag = gamertag_lookup.get(xuid, xuid)
                hover_txt = f"<b>{gamertag}</b><br>Match {match_id}<br>" + "<br>".join(
                    events_in_match
                )
            else:
                hover_txt = f"Match {match_id}"

            row_hover.append(hover_txt)

        z_values.append(row_z)
        hover_texts.append(row_hover)

    # Créer heatmap
    y_labels = [gamertag_lookup.get(xuid, xuid[:8]) for xuid in sorted_xuids]
    x_labels = [f"M{i+1}" for i in range(len(sorted_matches))]  # Abréger les IDs

    fig = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=x_labels,
            y=y_labels,
            colorscale=[
                [0, "#ecf0f1"],      # Gris (aucun événement)
                [0.33, COLOR_FIRST_BLOOD],  # Vert
                [0.66, COLOR_CLUTCH],       # Or
                [1.0, COLOR_CASUALTY],      # Rouge
            ],
            colorbar=dict(
                title="Événement",
                tickvals=[0, 1, 2, 3],
                ticktext=["Aucun", "Premier\nSang", "Finisseur", "Boulet"],
            ),
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_texts,
        )
    )

    fig.update_layout(
        title="Heatmap d'Impact — Événements clés par coéquipier",
        xaxis_title="Matchs (ordre chronologique)",
        yaxis_title="Coéquipiers",
        height=500,
        hovermode="closest",
    )

    return fig


def _empty_heatmap(message: str) -> go.Figure:
    """Retourner figure vide avec message."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=14, color="gray"),
    )
    fig.update_layout(
        title="Heatmap d'Impact",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        hovermode=False,
    )
    return fig


def build_impact_ranking_df(
    scores: Dict[str, int],
    gamertag_lookup: Dict[str, str],
) -> pl.DataFrame:
    """
    Construit un DataFrame de ranking pour affichage tableau.

    Args:
        scores: {xuid: score} (déjà trié)
        gamertag_lookup: {xuid: gamertag}

    Returns:
        Polars DataFrame avec colonnes: Rang, Joueur, Score, Badge
    """
    if not scores:
        return pl.DataFrame({
            "Rang": [],
            "Joueur": [],
            "Score": [],
            "Badge": [],
        })

    data = []
    for rank, (xuid, score) in enumerate(scores.items(), 1):
        gamertag = gamertag_lookup.get(xuid, xuid)
        
        # Badge spécial
        if rank == 1:
            badge = "🏆 MVP"
        elif rank == len(scores):
            badge = "🍌 Boulet"
        else:
            badge = ""

        data.append({
            "Rang": rank,
            "Joueur": gamertag,
            "Score": score,
            "Badge": badge,
        })

    return pl.DataFrame(data)
```

---

### 4. `src/ui/pages/teammates.py` - ADD TAB

Ajouter dans la fonction principale (environ ligne ~500) :

```python
# === Nouvel onglet: Impact & Taquinerie ===
with st.expander("⚡ Impact & Taquinerie"):
    if len(selected_friends) < 2:
        st.warning("⚠️ Veuillez sélectionner au moins 2 coéquipiers pour voir l'impact.")
    else:
        try:
            # Charger données d'impact
            match_events, match_outcomes = repo.load_friends_impact_data(
                match_ids=list(filtered_match_ids),
                friend_xuids=selected_friends,
            )

            if not match_events:
                st.info("Aucun événement détecté pour la période sélectionnée.")
            else:
                from src.analysis.friends_impact import (
                    identify_first_blood,
                    identify_clutch_finisher,
                    identify_last_casualty,
                    compute_impact_scores,
                )
                from src.visualization.friends_impact_heatmap import (
                    plot_friends_impact_heatmap,
                    build_impact_ranking_df,
                )

                # Convertir friend_xuids en set
                friend_xuids_set = set(selected_friends)

                # Calculer événements
                first_bloods = identify_first_blood(match_events, friend_xuids_set)
                clutches = identify_clutch_finisher(match_events, match_outcomes, friend_xuids_set)
                casualties = identify_last_casualty(match_events, match_outcomes, friend_xuids_set)

                # Scores
                scores = compute_impact_scores(first_bloods, clutches, casualties)

                # Gamertag lookup
                gamertag_lookup = {xuid: teammates_map.get(xuid, xuid) for xuid in selected_friends}

                # Vizualiser heatmap
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.subheader("Heatmap d'Impact")
                    fig = plot_friends_impact_heatmap(
                        first_bloods,
                        clutches,
                        casualties,
                        gamertag_lookup,
                        sorted(match_ids),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                # Tableau scoring
                with col2:
                    st.subheader("Taquinerie 🎯")
                    ranking_df = build_impact_ranking_df(scores, gamertag_lookup)
                    if not ranking_df.is_empty():
                        # Afficher avec streamlit
                        st.dataframe(
                            ranking_df.to_pandas(),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.write("Aucun score calculé.")

        except Exception as e:
            st.error(f"❌ Erreur lors du calcul d'impact: {e}")
            logger.exception(e)
```

---

### 5. `src/ui/translations.py` - ADD TRANSLATIONS

Ajouter au dictionnaire de traductions (environ ligne ~300) :

```python
# === Sprint 12: Friends Impact ===
"Impact & Taquinerie": "Impact & Taquinerie",
"First Blood": "Premier Sang",
"Clutch Finisher": "Finisseur",
"Last Casualty": "Boulet",
"MVP de la soirée": "MVP de la soirée",
"Maillon Faible": "Maillon Faible",
"⚡ Impact & Taquinerie": "⚡ Impact & Taquinerie",
"Heatmap d'Impact": "Heatmap d'Impact",
"Taquinerie 🎯": "Taquinerie 🎯",
"Veuillez sélectionner au moins 2 coéquipiers": "Veuillez sélectionner au moins 2 coéquipiers",
"Aucun événement détecté": "Aucun événement détecté pour la période sélectionnée.",
"🏆 MVP": "🏆 MVP",
"🍌 Boulet": "🍌 Boulet",
```

---

## 📝 Tests

### `tests/test_friends_impact.py`

```python
"""Tests pour src/analysis/friends_impact.py"""
import pytest
try:
    import polars as pl
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not POLARS_AVAILABLE, reason="Polars non disponible")


class TestFirstBlood:
    def test_identify_first_blood_basic(self):
        """Identifie correctement le premier kill."""
        match_events = {
            "match1": [
                {"event_type": "Kill", "xuid": "player1", "time_ms": 5000},
                {"event_type": "Kill", "xuid": "player2", "time_ms": 10000},
            ]
        }
        result = identify_first_blood(match_events, {"player1", "player2"})
        assert "match1" in result
        assert result["match1"][0] == "player1"
        assert result["match1"][1] == 5000

    def test_identify_first_blood_no_kills(self):
        """Retourne {} si aucun kill."""
        result = identify_first_blood({"match1": []}, {"player1"})
        assert result == {}


class TestClutchFinisher:
    def test_identify_clutch_finisher_win_only(self):
        """Clutch seulement si outcome=2 (victoire)."""
        match_events = {
            "match1": [
                {"event_type": "Kill", "xuid": "player1", "time_ms": 15000},
                {"event_type": "Kill", "xuid": "player2", "time_ms": 20000},
            ]
        }
        match_outcomes = {"match1": 2}
        result = identify_clutch_finisher(match_events, match_outcomes, {"player1", "player2"})
        assert "match1" in result
        assert result["match1"][0] == "player2"  # Dernier kill


class TestImpactScores:
    def test_compute_impact_scores(self):
        """Scoring correct: +2 clutch, +1 first blood, -1 casualty."""
        first_bloods = {"m1": ("p1", 5000)}
        clutches = {"m2": ("p1", 20000)}
        casualties = {"m3": ("p2", 30000)}
        scores = compute_impact_scores(first_bloods, clutches, casualties)
        assert scores["p1"] == 3  # +1 + 2
        assert scores["p2"] == -1  # -1
```

### `tests/test_friends_impact_viz.py`

```python
"""Tests pour src/visualization/friends_impact_heatmap.py"""
import pytest


class TestFriendsImpactHeatmap:
    def test_plot_friends_impact_heatmap_valid(self):
        """Heatmap valide avec données."""
        from src.visualization.friends_impact_heatmap import plot_friends_impact_heatmap
        
        first_bloods = {"m1": ("p1", 5000)}
        clutches = {"m2": ("p2", 20000)}
        casualties = {}
        gamertag_lookup = {"p1": "Player1", "p2": "Player2"}
        match_ids = ["m1", "m2"]
        
        fig = plot_friends_impact_heatmap(
            first_bloods, clutches, casualties,
            gamertag_lookup, match_ids
        )
        assert fig is not None
        assert len(fig.data) > 0

    def test_plot_friends_impact_heatmap_empty(self):
        """Gère données vides gracefully."""
        from src.visualization.friends_impact_heatmap import plot_friends_impact_heatmap
        
        fig = plot_friends_impact_heatmap({}, {}, {}, {}, [])
        assert fig is not None
```

---

## 🎨 Design & UX

### Palette de couleurs (cohérence)

Inspecter `src/visualization/distributions.py` + `plot_win_ratio_heatmap()` pour obtenir les palettes existantes.

**Proposé** :
- 🟢 Premier Sang : `#2ecc71` (Vert clair)
- 🟡 Finisseur : `#f39c12` (Orange/Or)
- 🔴 Boulet : `#e74c3c` (Rouge)
- ⚪ Aucun événement : `#ecf0f1` (Gris clair)

### Layout Streamlit

```
Tab "Impact & Taquinerie"
├─ Heatmap (full width, 500px height)
├─ Tableau "Taquinerie" (sidebar right)
│  ├─ Rang | Joueur | Score | Badge
│  └─ Couleur badge: Or pour MVP, rouge pour Boulet
└─ Messages d'erreur graceful (< 2 amis, pas de données)
```

---

## 📋 Checklist de livraison

- [ ] `src/analysis/friends_impact.py` créé avec 4 fonctions + docstrings FR
- [ ] `src/data/repositories/duckdb_repo.py` : méthode `load_friends_impact_data()` ajoutée
- [ ] `src/visualization/friends_impact_heatmap.py` créé avec heatmap + ranking
- [ ] `src/ui/pages/teammates.py` : nouvel onglet "Impact & Taquinerie" intégré
- [ ] `src/ui/translations.py` : traductions FR complètes
- [ ] `tests/test_friends_impact.py` : tests analyse créés
- [ ] `tests/test_friends_impact_viz.py` : tests vizualisation créés
- [ ] `pytest tests/test_friends_impact*.py -v` passe
- [ ] `pytest tests/ -v` passe sans régression
- [ ] Heatmap affiche 3 couleurs + multi-événements par cellule
- [ ] Tableau ranking avec MVP/Boulet en badges
- [ ] Filtres actifs appliqués (date, playlist, mode, map)
- [ ] Message d'erreur si < 2 amis sélectionnés

---

## ⚠️ Points d'attention

| Point | Solution |
|-------|----------|
| **Perf heatmap large** | Limiter à top 10 amis ; lazy load si besoin |
| **Multi-événements** | Un seul événement par joueur/match (priority: Clutch > First Blood > Casualty) |
| **Case-sensitive event_type** | Normaliser en `.lower()` lors du chargement |
| **Cohérence couleurs** | Vérifier `distributions.py` avant implémentation |
| **Données manquantes** | Graceful degradation (afficher ce qui existe) |

---

> **Écrit par** : Utilisateur Guillaume, 2026-02-12  
> **Sprint** : 12, après S11
