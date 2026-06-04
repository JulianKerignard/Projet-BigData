-- =============================================================================
-- [P3] Partitionnement Fait_Satisfaction (tâche 869dfg1g6 - Livrable 2)
-- Partition sur `annee` : le KPI 8 filtre "sur 2020" -> partition pruning très efficace
-- (1 partition = 1 répertoire HDFS, on ne lit que /annee=2020).
-- Exécution : hive -f partition/fait_satisfaction_partitioned.sql
-- =============================================================================

USE chu_entrepot;

-- -----------------------------------------------------------------------------
-- 1. Table partitionnée par année
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS fait_satisfaction_part;

CREATE TABLE fait_satisfaction_part (
  date_id           INT,
  etab_id           STRING,
  note_satisfaction DECIMAL(3,1)
)
PARTITIONED BY (annee INT)
STORED AS PARQUET
TBLPROPERTIES ('parquet.compression' = 'SNAPPY');

-- -----------------------------------------------------------------------------
-- 2. Rechargement avec partition dynamique (annee dérivée de date_id)
-- -----------------------------------------------------------------------------
SET hive.exec.dynamic.partition = true;
SET hive.exec.dynamic.partition.mode = nonstrict;

INSERT OVERWRITE TABLE fait_satisfaction_part PARTITION (annee)
SELECT
  date_id,
  etab_id,
  note_satisfaction,
  CAST(SUBSTR(CAST(date_id AS STRING), 1, 4) AS INT) AS annee
FROM fait_satisfaction;

-- -----------------------------------------------------------------------------
-- 3. Vérifications (Definition of Done)
-- -----------------------------------------------------------------------------
SHOW PARTITIONS fait_satisfaction_part;   -- au moins une partition annee=2020 attendue

-- =============================================================================
-- 4. EXPLAIN avant / après  -> à capturer pour les 2 livrables "capture EXPLAIN"
--    Observer la différence sur le volume scanné (TableScan) :
--    AVANT  : scan complet de fait_satisfaction
--    APRÈS  : partition pruning, seul annee=2020 est lu
-- =============================================================================

-- 4.1 AVANT (table non partitionnée) — capture EXPLAIN n°1
EXPLAIN
SELECT e.region, AVG(f.note_satisfaction) AS satisf_moy
FROM   fait_satisfaction f
JOIN   dim_etablissement e USING (etab_id)
WHERE  CAST(SUBSTR(CAST(f.date_id AS STRING), 1, 4) AS INT) = 2020
GROUP  BY e.region;

-- 4.2 APRÈS (table partitionnée, filtre sur la colonne de partition) — capture EXPLAIN n°2
EXPLAIN
SELECT e.region, AVG(f.note_satisfaction) AS satisf_moy
FROM   fait_satisfaction_part f
JOIN   dim_etablissement e USING (etab_id)
WHERE  f.annee = 2020
GROUP  BY e.region;
