-- =============================================================================
-- [P3] Bucketing Fait_Satisfaction (tâche 869dfg1gf - Livrable 2)
-- Partition (annee) + bucketing 8 buckets sur etab_id.
-- Le KPI 8 est "par région" : la région se déduit via la jointure sur etab_id (FINESS),
-- donc bucketer sur etab_id accélère le JOIN avec dim_etablissement (bucket map join)
-- et co-localise les notes d'un même établissement.
-- Exécution : hive -f bucket/fait_satisfaction_bucketed.sql
-- =============================================================================

USE chu_entrepot;

-- -----------------------------------------------------------------------------
-- 1. Table partitionnée + bucketée
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS fait_satisfaction_pb;

CREATE TABLE fait_satisfaction_pb (
  date_id           INT,
  etab_id           STRING,
  note_satisfaction DECIMAL(3,1)
)
PARTITIONED BY (annee INT)
CLUSTERED BY (etab_id) INTO 8 BUCKETS
STORED AS PARQUET
TBLPROPERTIES ('parquet.compression' = 'SNAPPY');

-- -----------------------------------------------------------------------------
-- 2. Activation + rechargement (depuis la table partitionnée)
-- -----------------------------------------------------------------------------
SET hive.enforce.bucketing = true;
SET hive.exec.dynamic.partition = true;
SET hive.exec.dynamic.partition.mode = nonstrict;

INSERT OVERWRITE TABLE fait_satisfaction_pb PARTITION (annee)
SELECT
  date_id,
  etab_id,
  note_satisfaction,
  annee
FROM fait_satisfaction_part;

-- -----------------------------------------------------------------------------
-- 3. Vérifications (Definition of Done)
-- -----------------------------------------------------------------------------
SHOW PARTITIONS fait_satisfaction_pb;

-- 8 fichiers attendus par partition. Vérification HDFS (hors Hive) :
--   hdfs dfs -ls /user/hive/warehouse/chu_entrepot.db/fait_satisfaction_pb/annee=2020
--   -> doit lister 8 fichiers (000000_0 .. 000007_0)

-- Pour profiter du bucket map join sur dim_etablissement (elle aussi bucketée sur etab_id) :
--   SET hive.optimize.bucketmapjoin = true;
--   SET hive.auto.convert.join = true;
