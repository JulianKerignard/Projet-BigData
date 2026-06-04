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
-- NB : pas de cache de résultats en Hive 2.3.2 (hive.query.results.cache.* = Hive 3.x).

-- -----------------------------------------------------------------------------
-- 1. bench_satisfaction_pb — partition (annee) + bucket 8 sur etab_id, 5 campagnes
--    SYNTHÉTIQUES. fait_satisfaction = 1 campagne (2020) ; pour rendre le partition
--    pruning mesurable on réplique sur 5 années (mêmes établissements -> jointures
--    dim_etablissement/dim_geographie conservées). Volumétrie factice, jamais en KPI
--    (la satisfaction réelle reste la campagne 2020 dans fait_satisfaction).
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
SELECT
  s.satisfaction_key + y.shift * 1000000000  AS satisfaction_key,
  s.date_id          - y.shift * 10000       AS date_id,
  s.etab_id, s.geo_id, s.note_satisfaction,
  s.annee            - y.shift               AS annee
FROM fait_satisfaction s
LATERAL VIEW explode(array(0, 1, 2, 3, 4)) y AS shift;

-- -----------------------------------------------------------------------------
-- 2. bench_satisfaction_flat — mêmes lignes, SANS partition ni bucket (référence).
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
FROM bench_satisfaction_pb;

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
