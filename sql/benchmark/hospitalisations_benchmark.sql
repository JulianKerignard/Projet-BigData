-- =============================================================================
-- [P2] Benchmark Hospitalisations — partition + bucketing (B3 période, B4 diagnostic, B5 sexe/âge)
-- Tâche ClickUp : benchmark Hospitalisation avant/après + graphes
--
-- Le benchmark NE TOUCHE PAS la Gold canonique chu_entrepot.fait_hospitalisation
-- (produite par sql/cleaning/hospitalisations_cleaning.hql). Il dérive deux tables
-- JETABLES depuis fait_hospitalisation (les séjours couvrent NATURELLEMENT 2015-2021
-- -> partition pruning mesurable sans données synthétiques, comme les consultations) :
--   bench_hospitalisation_flat : Parquet, ni partition ni bucket          (baseline)
--   bench_hospitalisation_pb   : Parquet + partition annee + bucket 8 etab_id (optimisée)
--
-- Pré-requis : fait_hospitalisation alimentée (hospitalisations_cleaning.hql).
--   beeline -u jdbc:hive2://localhost:10000/ -f sql/benchmark/hospitalisations_benchmark.sql
-- =============================================================================
USE chu_entrepot;
SET hive.exec.dynamic.partition       = true;
SET hive.exec.dynamic.partition.mode  = nonstrict;
SET hive.enforce.bucketing            = true;

-- -----------------------------------------------------------------------------
-- 1. bench_hospitalisation_pb — partition (annee) + bucket 8 sur etab_id.
--    Le bucket sur etab_id reprend la clé de bucketing de la Gold (02_faits.hql) :
--    co-localise les séjours d'un même établissement (Q3 = regroupement par etab_id).
--    NB : une vraie bucket-map join exigerait AUSSI la dimension bucketée (non visé ici) ;
--    le gain mesuré Q3 reflète surtout le partition pruning, pas une bucket-map join.
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS bench_hospitalisation_pb;
CREATE TABLE bench_hospitalisation_pb (
  hosp_key            BIGINT,
  date_id             INT,
  patient_id          STRING,
  etab_id             STRING,
  diag_id             STRING,
  nb_hospitalisation  INT,
  duree_sejour        INT
)
PARTITIONED BY (annee INT)
CLUSTERED BY (etab_id) INTO 8 BUCKETS
STORED AS PARQUET TBLPROPERTIES ('parquet.compression' = 'SNAPPY');

INSERT OVERWRITE TABLE bench_hospitalisation_pb PARTITION (annee)
SELECT hosp_key, date_id, patient_id, etab_id, diag_id, nb_hospitalisation, duree_sejour, annee
FROM fait_hospitalisation;

-- -----------------------------------------------------------------------------
-- 2. bench_hospitalisation_flat — mêmes lignes, sans partition ni bucket (baseline).
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS bench_hospitalisation_flat;
CREATE TABLE bench_hospitalisation_flat (
  hosp_key            BIGINT,
  date_id             INT,
  patient_id          STRING,
  etab_id             STRING,
  diag_id             STRING,
  nb_hospitalisation  INT,
  duree_sejour        INT,
  annee               INT
)
STORED AS PARQUET TBLPROPERTIES ('parquet.compression' = 'SNAPPY');

INSERT OVERWRITE TABLE bench_hospitalisation_flat
SELECT hosp_key, date_id, patient_id, etab_id, diag_id, nb_hospitalisation, duree_sejour, annee
FROM bench_hospitalisation_pb;

-- =============================================================================
-- 3. REQUÊTES (exécuter 3× chacune via run_benchmark_hospitalisations.sh)
-- =============================================================================
-- Q1 — taux global hospitalisations sur une periode (B3) -> PARTITION PRUNING
SELECT SUM(nb_hospitalisation) FROM bench_hospitalisation_flat WHERE annee = 2020;
SELECT SUM(nb_hospitalisation) FROM bench_hospitalisation_pb   WHERE annee = 2020;

-- Q2 — par diagnostic (B4)
SELECT diag_id, SUM(nb_hospitalisation) AS nb FROM bench_hospitalisation_flat
WHERE annee = 2020 GROUP BY diag_id ORDER BY nb DESC LIMIT 10;
SELECT diag_id, SUM(nb_hospitalisation) AS nb FROM bench_hospitalisation_pb
WHERE annee = 2020 GROUP BY diag_id ORDER BY nb DESC LIMIT 10;

-- Q3 — par établissement (jointure dim_etablissement, regroupement sur etab_id = clé de bucket)
--   Groupé sur etab_id (clé stable) et NON sur nom_etab : ce dernier est NULL pour les
--   établissements issus des seules hospitalisations (cf. 04_chargement_dimensions.hql),
--   ce qui replierait tous ces sites dans un unique bucket NULL.
SELECT f.etab_id, SUM(f.nb_hospitalisation) AS nb, AVG(f.duree_sejour) AS dms
FROM bench_hospitalisation_flat f JOIN dim_etablissement e ON e.etab_id = f.etab_id
WHERE f.annee = 2020 GROUP BY f.etab_id ORDER BY nb DESC LIMIT 10;
SELECT f.etab_id, SUM(f.nb_hospitalisation) AS nb, AVG(f.duree_sejour) AS dms
FROM bench_hospitalisation_pb   f JOIN dim_etablissement e ON e.etab_id = f.etab_id
WHERE f.annee = 2020 GROUP BY f.etab_id ORDER BY nb DESC LIMIT 10;

-- Q4 — par sexe et tranche age (B5, jointure dim_patient)
SELECT p.sexe, p.tranche_age, SUM(f.nb_hospitalisation) AS nb
FROM bench_hospitalisation_flat f JOIN dim_patient p ON p.patient_id = f.patient_id
WHERE f.annee = 2020 GROUP BY p.sexe, p.tranche_age;
SELECT p.sexe, p.tranche_age, SUM(f.nb_hospitalisation) AS nb
FROM bench_hospitalisation_pb   f JOIN dim_patient p ON p.patient_id = f.patient_id
WHERE f.annee = 2020 GROUP BY p.sexe, p.tranche_age;

-- =============================================================================
-- 4. EXPLAIN — preuve du partition pruning (I/O lu)
-- =============================================================================
EXPLAIN SELECT SUM(nb_hospitalisation) FROM bench_hospitalisation_flat WHERE annee = 2020;
EXPLAIN SELECT SUM(nb_hospitalisation) FROM bench_hospitalisation_pb   WHERE annee = 2020;

-- =============================================================================
-- 5. NETTOYAGE (tables bench_* jetables, hors Gold) — décommenter après mesure.
-- =============================================================================
-- DROP TABLE IF EXISTS bench_hospitalisation_flat;
-- DROP TABLE IF EXISTS bench_hospitalisation_pb;
