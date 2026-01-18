"""Requêtes SQL centralisées."""

# =============================================================================
# Requêtes pour les assets (Maps, Playlists, etc.)
# =============================================================================

LOAD_ASSET_NAMES = """
SELECT ResponseBody FROM {table}
"""

# =============================================================================
# Requêtes pour les matchs
# =============================================================================

LOAD_MATCH_STATS = """
SELECT ResponseBody FROM MatchStats
"""

# =============================================================================
# Requêtes pour les joueurs
# =============================================================================

LIST_OTHER_PLAYER_XUIDS = """
WITH base AS (
  SELECT json_extract(ResponseBody, '$.Players') AS Players
  FROM MatchStats
)
SELECT DISTINCT json_extract(j.value, '$.PlayerId') AS PlayerId
FROM base
JOIN json_each(base.Players) AS j
WHERE PlayerId IS NOT NULL
LIMIT ?;
"""

LIST_TOP_TEAMMATES = """
WITH p AS (
    SELECT
        json_extract(ResponseBody, '$.MatchId') AS MatchId,
        json_extract(j.value, '$.PlayerId') AS PlayerId,
        CAST(json_extract(j.value, '$.LastTeamId') AS INTEGER) AS TeamId
    FROM MatchStats
    JOIN json_each(json_extract(ResponseBody, '$.Players')) AS j
),
me AS (
    SELECT MatchId, TeamId
    FROM p
    WHERE PlayerId = ? AND TeamId IS NOT NULL
)
SELECT
    p.PlayerId,
    COUNT(DISTINCT p.MatchId) AS Matches
FROM p
JOIN me ON me.MatchId = p.MatchId AND me.TeamId = p.TeamId
WHERE p.PlayerId IS NOT NULL AND p.PlayerId <> ?
GROUP BY p.PlayerId
ORDER BY Matches DESC
LIMIT ?;
"""

# =============================================================================
# Requêtes pour les matchs partagés avec un ami
# =============================================================================

QUERY_MATCHES_WITH_FRIEND = """
WITH base AS (
    SELECT
        json_extract(ResponseBody, '$.MatchId') AS MatchId,
        json_extract(ResponseBody, '$.MatchInfo.StartTime') AS StartTime,
        json_extract(ResponseBody, '$.MatchInfo.Playlist.AssetId') AS PlaylistId,
        json_extract(ResponseBody, '$.MatchInfo.PlaylistMapModePair.AssetId') AS PairId,
        json_extract(ResponseBody, '$.Players') AS Players
    FROM MatchStats
),
p AS (
    SELECT
        b.MatchId AS MatchId,
        b.StartTime AS StartTime,
        b.PlaylistId AS PlaylistId,
        b.PairId AS PairId,
        json_extract(j.value, '$.PlayerId') AS PlayerId,
        CAST(json_extract(j.value, '$.LastTeamId') AS INTEGER) AS LastTeamId,
        CAST(json_extract(j.value, '$.Outcome') AS INTEGER) AS Outcome
    FROM base b
    JOIN json_each(b.Players) AS j
),
me AS (
    SELECT * FROM p WHERE PlayerId = ?
),
fr AS (
    SELECT * FROM p WHERE PlayerId = ?
)
SELECT
    me.MatchId,
    me.StartTime,
    me.PlaylistId,
    me.PairId,
    me.LastTeamId AS MyTeamId,
    me.Outcome AS MyOutcome,
    fr.LastTeamId AS FriendTeamId,
    fr.Outcome AS FriendOutcome,
    CASE WHEN me.LastTeamId = fr.LastTeamId THEN 1 ELSE 0 END AS SameTeam
FROM me
JOIN fr ON me.MatchId = fr.MatchId
ORDER BY me.StartTime DESC;
"""
