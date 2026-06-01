-- =============================================================================
-- [P3] Profiling HiveQL — source Satisfaction (e-Satis 48h MCO)
-- Tâche : 869dh1d8b. Reproduit sur le cluster le profiling Python
-- (scripts/satisfaction_profiling.py) une fois les fichiers ingérés en staging.
--
-- Prérequis : table externe staging.satisfaction_raw créée par
--             sql/cleaning/satisfaction_cleaning.hql (§0).
-- =============================================================================

USE staging;

-- 1. Volumétrie
SELECT COUNT(*) AS nb_lignes FROM satisfaction_raw;

-- 2. Complétude des colonnes clés (% de nulls / vides)
SELECT
  ROUND(100 * SUM(CASE WHEN finess_geo IS NULL OR finess_geo = '' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_finess_geo_null,
  ROUND(100 * SUM(CASE WHEN region      IS NULL OR region      = '' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_region_null,
  ROUND(100 * SUM(CASE WHEN score_all_rea_ajust IS NULL OR score_all_rea_ajust = '' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_score_null
FROM satisfaction_raw;

-- 3. Cardinalités : finess_geo (site, doit ≈ nb lignes) vs finess (juridique, dupliqué)
SELECT COUNT(DISTINCT finess_geo) AS finess_geo_distinct,
       COUNT(DISTINCT finess)     AS finess_juridique_distinct,
       COUNT(DISTINCT region)     AS region_distinct
FROM satisfaction_raw;

-- 4. Distribution du score (échelle source 0-100) + anomalies hors plage
SELECT
  MIN(CAST(REPLACE(score_all_rea_ajust, ',', '.') AS DECIMAL(5,2)))            AS score_min,
  MAX(CAST(REPLACE(score_all_rea_ajust, ',', '.') AS DECIMAL(5,2)))            AS score_max,
  ROUND(AVG(CAST(REPLACE(score_all_rea_ajust, ',', '.') AS DECIMAL(5,2))), 1)  AS score_moy,
  SUM(CASE WHEN CAST(REPLACE(score_all_rea_ajust, ',', '.') AS DECIMAL(5,2)) NOT BETWEEN 0 AND 100
           THEN 1 ELSE 0 END)                                                  AS nb_hors_plage
FROM satisfaction_raw
WHERE score_all_rea_ajust IS NOT NULL AND score_all_rea_ajust <> '';

-- 5. Doublons sur la clé de grain (finess_geo) au sein de la campagne
SELECT finess_geo, COUNT(*) AS n
FROM satisfaction_raw
GROUP BY finess_geo
HAVING COUNT(*) > 1;
