-- =============================================================================
-- [P4] Benchmark L2 Décès — tables de travail JETABLES (préfixe bench_, hors Gold)
-- Tâche ClickUp : 869dfg1ne
--
-- IMPORTANT : ce benchmark NE TOUCHE PAS la table Gold canonique
-- chu_entrepot.fait_deces (produite EXCLUSIVEMENT par sql/cleaning/deces_cleaning.hql).
-- Il dérive deux tables JETABLES depuis fait_deces — SANS re-nettoyer le Bronze ni
-- re-dériver les clés (pas de duplication de la logique de cleaning) :
--   bench_deces_flat : Parquet, NI partition NI bucket          ("avant" = référence)
--   bench_deces_pb   : Parquet + partition annee + bucket 8 geo_id ("après")
--
-- fait_deces ne contient localement qu'une campagne (annee=2019). Pour rendre le
-- PARTITION PRUNING mesurable, on EXPAND les données sur 5 années SYNTHÉTIQUES
-- (2015-2019) par simple décalage d'année. Ce sont des données factices de
-- VOLUMÉTRIE, à usage benchmark uniquement — JAMAIS exposées en KPI (le Gold B7 réel
-- reste 2019, cf. docs/L2_Resultats_Execution_Deces.md).
--
-- Pré-requis : fait_deces alimentée (sql/cleaning/deces_cleaning.hql).
-- Nettoyage : DROP des deux tables en fin de §3 (décommenter).
--   beeline -u jdbc:hive2://localhost:10000/ -f sql/benchmark/00_create_bench_deces.hql
-- =============================================================================
SET hive.exec.dynamic.partition = true;
SET hive.exec.dynamic.partition.mode = nonstrict;
USE chu_entrepot;

-- -----------------------------------------------------------------------------
-- 1. bench_deces_pb — partition (annee) + bucket 8 (geo_id), 5 années synthétiques.
--    2019 réel + 4 copies décalées (-1..-4 ans). date_id (AAAAMMJJ) et annee décalés
--    ensemble ; deces_key offsetté pour rester distinct. Dérivé de fait_deces (pas de
--    re-cleaning) -> reflète exactement les transformations canoniques.
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS bench_deces_pb;
CREATE TABLE bench_deces_pb (
  deces_key    BIGINT,
  date_id      INT,
  geo_id       STRING,
  sexe         STRING,
  tranche_age  STRING,
  nb_deces     INT
)
PARTITIONED BY (annee INT)
CLUSTERED BY (geo_id) INTO 8 BUCKETS
STORED AS PARQUET TBLPROPERTIES ('parquet.compression' = 'SNAPPY');

INSERT OVERWRITE TABLE bench_deces_pb PARTITION (annee)
SELECT
  f.deces_key + y.shift * 1000000000   AS deces_key,
  f.date_id   - y.shift * 10000        AS date_id,   -- AAAAMMJJ : recule l'année
  f.geo_id, f.sexe, f.tranche_age, f.nb_deces,
  f.annee     - y.shift                AS annee
FROM fait_deces f
LATERAL VIEW explode(array(0, 1, 2, 3, 4)) y AS shift;

-- -----------------------------------------------------------------------------
-- 2. bench_deces_flat — mêmes lignes, SANS partition ni bucket (référence "avant").
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS bench_deces_flat;
CREATE TABLE bench_deces_flat (
  deces_key    BIGINT,
  date_id      INT,
  geo_id       STRING,
  sexe         STRING,
  tranche_age  STRING,
  nb_deces     INT,
  annee        INT       -- colonne ordinaire (pas de partition -> pas de pruning)
)
STORED AS PARQUET TBLPROPERTIES ('parquet.compression' = 'SNAPPY');

INSERT OVERWRITE TABLE bench_deces_flat
SELECT deces_key, date_id, geo_id, sexe, tranche_age, nb_deces, annee
FROM bench_deces_pb;

-- -----------------------------------------------------------------------------
-- 3. Contrôles (et nettoyage)
-- -----------------------------------------------------------------------------
SHOW PARTITIONS bench_deces_pb;                 -- attendu : annee=2015..2019
SELECT annee, COUNT(*) AS n FROM bench_deces_pb GROUP BY annee ORDER BY annee;
SELECT 'bench_deces_pb' AS t, COUNT(*) AS n FROM bench_deces_pb
UNION ALL SELECT 'bench_deces_flat', COUNT(*) FROM bench_deces_flat;

-- Nettoyage post-benchmark (les tables bench_* sont jetables, hors Gold) :
-- DROP TABLE IF EXISTS bench_deces_pb;
-- DROP TABLE IF EXISTS bench_deces_flat;
