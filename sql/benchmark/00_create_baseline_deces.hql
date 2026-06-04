-- =============================================================================
-- [P4] Benchmark L2 — Création de la baseline pour comparaison perf
-- Tâche ClickUp : 869dfg1ne (Benchmark partitionnement+bucketing Fait_Deces)
--
-- Crée fait_deces_baseline : MÊMES données que fait_deces, mais SANS partition
-- ni bucketing. C'est l'ancrage du benchmark "avant/après" du L2.
--
-- Référence pour comparer :
--   - chu_entrepot.fait_deces           : PARTITIONED BY annee, BUCKETED geo_id ×8
--   - chu_entrepot.fait_deces_baseline  : aucune optimisation
--
-- Pré-requis : la table fait_deces doit être alimentée (cf. deces_cleaning.hql)
--   beeline -u jdbc:hive2://localhost:10000/ -f 00_create_baseline_deces.hql
-- =============================================================================
USE chu_entrepot;

-- Baseline : même schéma, mais sans PARTITIONED BY ni CLUSTERED BY
DROP TABLE IF EXISTS fait_deces_baseline;
CREATE TABLE fait_deces_baseline (
  deces_key    BIGINT,
  date_id      INT,
  geo_id       STRING,
  sexe         STRING,
  tranche_age  STRING,
  nb_deces     INT,
  annee        INT     -- colonne normale (vs partition col)
)
COMMENT 'Baseline non optimisée pour benchmark L2 — comparable à fait_deces'
STORED AS PARQUET;

-- Copie 1:1 depuis la table optimisée (mêmes lignes, juste sans partition/bucket)
INSERT OVERWRITE TABLE fait_deces_baseline
SELECT deces_key, date_id, geo_id, sexe, tranche_age, nb_deces, annee
FROM fait_deces;

-- Contrôles
SELECT 'fait_deces (optimisée)'   AS table_name, COUNT(*) AS n FROM fait_deces
UNION ALL
SELECT 'fait_deces_baseline',                    COUNT(*)      FROM fait_deces_baseline;

DESCRIBE FORMATTED fait_deces_baseline;
