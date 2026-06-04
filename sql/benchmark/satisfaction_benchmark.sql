-- =============================================================================
-- [P3] Benchmark Satisfaction — impact partition / bucket (Livrable 2, 869dfg1gt)
-- Compare 3 layouts physiques du fait Satisfaction sur 2 requêtes (axe KPI B8).
--
-- Toutes les tables dérivent du fait CANONIQUE chu_entrepot.fait_satisfaction
-- (5 colonnes : satisfaction_key, date_id, etab_id, geo_id, note_satisfaction ;
-- déjà partitionné par annee — cf. sql/ddl/02_faits.hql). Les tables bench_* sont
-- JETABLES (préfixe bench_, hors modèle Gold), à DROP après mesure (§5).
--
--   V1 = bench_satisfaction_flat  (Parquet, NI partition NI bucket = vraie référence)
--   V2 = fait_satisfaction        (canonique : Parquet + partition annee)
--   V3 = bench_satisfaction_pb    (Parquet + partition annee + bucket 8 sur etab_id)
--
-- Pré-requis : 02_faits.hql + satisfaction_cleaning.hql exécutés (fait_satisfaction peuplé).
-- Mode opératoire :
--   hive -f sql/benchmark/satisfaction_benchmark.sql 2>&1 | tee scripts/benchmark/run_$(date +%F).log
-- puis reporter les "Time taken" dans scripts/benchmark/satisfaction_results.csv
-- et lancer  python3 scripts/benchmark/generate_graph.py
-- =============================================================================
USE chu_entrepot;
SET hive.exec.dynamic.partition       = true;
SET hive.exec.dynamic.partition.mode  = nonstrict;
SET hive.enforce.bucketing            = true;
SET hive.query.results.cache.enabled  = false;   -- mesurer le coût réel à chaque run

-- -----------------------------------------------------------------------------
-- 1. V1 — table de RÉFÉRENCE non optimisée (ni partition ni bucket).
--    La canonique étant déjà partitionnée, on fabrique une vraie baseline « plate »
--    où `annee` est une colonne ORDINAIRE -> aucun partition pruning possible.
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS bench_satisfaction_flat;
CREATE TABLE bench_satisfaction_flat (
  satisfaction_key  BIGINT,
  date_id           INT,
  etab_id           STRING,
  geo_id            STRING,
  note_satisfaction DECIMAL(3,1),
  annee             INT
)
STORED AS PARQUET TBLPROPERTIES ('parquet.compression' = 'SNAPPY');

INSERT OVERWRITE TABLE bench_satisfaction_flat
SELECT satisfaction_key, date_id, etab_id, geo_id, note_satisfaction, annee
FROM fait_satisfaction;

-- -----------------------------------------------------------------------------
-- 2. V3 — partition (annee) + bucket 8 sur etab_id (clé de jointure dim_etablissement).
--    NB : le bucket map join complet suppose dim_etablissement AUSSI bucketée sur
--    etab_id ; ici le gain démontrable principal reste le partition pruning (R1).
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS bench_satisfaction_pb;
CREATE TABLE bench_satisfaction_pb (
  satisfaction_key  BIGINT,
  date_id           INT,
  etab_id           STRING,
  geo_id            STRING,
  note_satisfaction DECIMAL(3,1)
)
PARTITIONED BY (annee INT)
CLUSTERED BY (etab_id) INTO 8 BUCKETS
STORED AS PARQUET TBLPROPERTIES ('parquet.compression' = 'SNAPPY');

INSERT OVERWRITE TABLE bench_satisfaction_pb PARTITION (annee)
SELECT satisfaction_key, date_id, etab_id, geo_id, note_satisfaction, annee
FROM fait_satisfaction;

-- =============================================================================
-- 3. REQUÊTES (exécuter 3× chacune, relever "Time taken")
-- =============================================================================
-- R1 — satisfaction moyenne par région, campagne 2020 (jointure dim_etablissement).
--      Démontre le PARTITION PRUNING : V2/V3 ne lisent que annee=2020, V1 scanne tout.
SELECT e.region, AVG(f.note_satisfaction) AS satisf_moy   -- R1 / V1 (flat)
FROM bench_satisfaction_flat f JOIN dim_etablissement e ON f.etab_id = e.etab_id
WHERE f.annee = 2020 GROUP BY e.region;

SELECT e.region, AVG(f.note_satisfaction) AS satisf_moy   -- R1 / V2 (canonique partitionnée)
FROM fait_satisfaction f JOIN dim_etablissement e ON f.etab_id = e.etab_id
WHERE f.annee = 2020 GROUP BY e.region;

SET hive.optimize.bucketmapjoin = true;
SELECT e.region, AVG(f.note_satisfaction) AS satisf_moy   -- R1 / V3 (partition + bucket)
FROM bench_satisfaction_pb f JOIN dim_etablissement e ON f.etab_id = e.etab_id
WHERE f.annee = 2020 GROUP BY e.region;

-- R2 — satisfaction moyenne par région, TOUTES campagnes (pas de filtre annee).
--      Contraste : aucun pruning -> scan de toutes les partitions. Grain annuel =>
--      on agrège sur l'axe région (geo_id), jamais "par mois" (date_id = YYYY0101).
SELECT geo_id, AVG(note_satisfaction) AS satisf_moy       -- R2 / V1 (flat)
FROM bench_satisfaction_flat GROUP BY geo_id;

SELECT geo_id, AVG(note_satisfaction) AS satisf_moy       -- R2 / V2 (canonique)
FROM fait_satisfaction GROUP BY geo_id;

SELECT geo_id, AVG(note_satisfaction) AS satisf_moy       -- R2 / V3
FROM bench_satisfaction_pb GROUP BY geo_id;

-- =============================================================================
-- 4. EXPLAIN avant/après (capture pour le rapport) — partition pruning sur R1
-- =============================================================================
EXPLAIN                                                    -- V1 : scan complet
SELECT e.region, AVG(f.note_satisfaction)
FROM bench_satisfaction_flat f JOIN dim_etablissement e ON f.etab_id = e.etab_id
WHERE f.annee = 2020 GROUP BY e.region;

EXPLAIN                                                    -- V2 : partition pruning (annee=2020)
SELECT e.region, AVG(f.note_satisfaction)
FROM fait_satisfaction f JOIN dim_etablissement e ON f.etab_id = e.etab_id
WHERE f.annee = 2020 GROUP BY e.region;

-- =============================================================================
-- 5. NETTOYAGE — les tables bench_* sont jetables (hors Gold). Décommenter après mesure.
-- =============================================================================
-- DROP TABLE IF EXISTS bench_satisfaction_flat;
-- DROP TABLE IF EXISTS bench_satisfaction_pb;
