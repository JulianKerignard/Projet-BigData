-- =============================================================================
-- [P1] Benchmark Consultations — partition + bucketing (B2 diagnostic, B6 professionnel)
-- Tâche ClickUp : 869dfg1b1
--
-- Le benchmark NE TOUCHE PAS la Gold canonique chu_entrepot.fait_consultation
-- (produite par sql/cleaning/consultations_cleaning.hql). Il dérive deux tables
-- JETABLES depuis fait_consultation (les consultations couvrent naturellement
-- plusieurs années -> partition pruning mesurable sans données synthétiques) :
--   bench_consultation_flat : Parquet, ni partition ni bucket   (baseline)
--   bench_consultation_pb   : Parquet + partition annee + bucket 8 prof_id (optimisée)
--
-- Pré-requis : fait_consultation alimentée (consultations_cleaning.hql).
--   beeline -u jdbc:hive2://localhost:10000/ -f sql/benchmark/consultations_benchmark.sql
-- =============================================================================
USE chu_entrepot;
SET hive.exec.dynamic.partition       = true;
SET hive.exec.dynamic.partition.mode  = nonstrict;
SET hive.enforce.bucketing            = true;

-- -----------------------------------------------------------------------------
-- 1. bench_consultation_pb — partition (annee) + bucket 8 sur prof_id (axe B6).
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS bench_consultation_pb;
CREATE TABLE bench_consultation_pb (
  consultation_key BIGINT,
  date_id          INT,
  patient_id       STRING,
  prof_id          STRING,
  diag_id          STRING,
  nb_consultation  INT,
  duree_minutes    DOUBLE
)
PARTITIONED BY (annee INT)
CLUSTERED BY (prof_id) INTO 8 BUCKETS
STORED AS PARQUET TBLPROPERTIES ('parquet.compression' = 'SNAPPY');

INSERT OVERWRITE TABLE bench_consultation_pb PARTITION (annee)
SELECT consultation_key, date_id, patient_id, prof_id, diag_id, nb_consultation, duree_minutes, annee
FROM fait_consultation;

-- -----------------------------------------------------------------------------
-- 2. bench_consultation_flat — mêmes lignes, sans partition ni bucket (baseline).
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS bench_consultation_flat;
CREATE TABLE bench_consultation_flat (
  consultation_key BIGINT,
  date_id          INT,
  patient_id       STRING,
  prof_id          STRING,
  diag_id          STRING,
  nb_consultation  INT,
  duree_minutes    DOUBLE,
  annee            INT
)
STORED AS PARQUET TBLPROPERTIES ('parquet.compression' = 'SNAPPY');

INSERT OVERWRITE TABLE bench_consultation_flat
SELECT consultation_key, date_id, patient_id, prof_id, diag_id, nb_consultation, duree_minutes, annee
FROM bench_consultation_pb;

-- =============================================================================
-- 3. REQUÊTES (exécuter 3× chacune via run_benchmark_consultations.sh)
-- =============================================================================
-- Q1 — filtre année (PARTITION PRUNING)
SELECT SUM(nb_consultation) FROM bench_consultation_flat WHERE annee = 2020;
SELECT SUM(nb_consultation) FROM bench_consultation_pb   WHERE annee = 2020;

-- Q2 — par professionnel (B6, bucket sur prof_id)
SELECT prof_id, SUM(nb_consultation) AS nb FROM bench_consultation_flat
WHERE annee = 2020 GROUP BY prof_id ORDER BY nb DESC;
SELECT prof_id, SUM(nb_consultation) AS nb FROM bench_consultation_pb
WHERE annee = 2020 GROUP BY prof_id ORDER BY nb DESC;

-- Q3 — par diagnostic (B2)
SELECT diag_id, SUM(nb_consultation) AS nb FROM bench_consultation_flat
WHERE annee = 2020 GROUP BY diag_id ORDER BY nb DESC LIMIT 10;
SELECT diag_id, SUM(nb_consultation) AS nb FROM bench_consultation_pb
WHERE annee = 2020 GROUP BY diag_id ORDER BY nb DESC LIMIT 10;

-- =============================================================================
-- 4. EXPLAIN — preuve du partition pruning (I/O lu)
-- =============================================================================
EXPLAIN SELECT SUM(nb_consultation) FROM bench_consultation_flat WHERE annee = 2020;
EXPLAIN SELECT SUM(nb_consultation) FROM bench_consultation_pb   WHERE annee = 2020;

-- =============================================================================
-- 5. NETTOYAGE (tables bench_* jetables, hors Gold) — décommenter après mesure.
-- =============================================================================
-- DROP TABLE IF EXISTS bench_consultation_flat;
-- DROP TABLE IF EXISTS bench_consultation_pb;
