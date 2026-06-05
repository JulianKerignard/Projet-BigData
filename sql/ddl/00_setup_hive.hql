-- =============================================================================
-- [COMMUN] Setup environnement Hive — Cloud Healthcare Unit
-- Tâche : 869dfg187 (Livrable 2)
-- Crée les bases (architecture médaillon) et fixe les paramètres de session.
-- À exécuter en premier, avant tout DDL/chargement.
--   hive -f sql/ddl/00_setup_hive.hql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Bases de données (convention d'équipe — voir docs/L2_Setup_Hive_Dimensions.md)
--    staging      : couches Bronze (brut) + Silver (nettoyé/anonymisé)
--    chu_entrepot : couche Gold (schéma en étoile : dimensions + faits, Parquet)
-- -----------------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS staging
  COMMENT 'Couches Bronze (brut) et Silver (nettoyé + anonymisé)'
  LOCATION '/chu/staging';

CREATE DATABASE IF NOT EXISTS chu_entrepot
  COMMENT 'Couche Gold : modèle en étoile (dimensions conformes + faits) en Parquet'
  LOCATION '/chu/gold';

-- Structure HDFS attendue (médaillon) :
--   /chu/bronze/<source>          -> données brutes ingérées (hdfs dfs -put)
--   /chu/staging/<source>         -> tables externes Silver (nettoyage HiveQL)
--   /chu/gold/<table>             -> dimensions + faits (Parquet, partition/bucket)

-- -----------------------------------------------------------------------------
-- 2. Paramètres de session (à charger au début de chaque job)
-- -----------------------------------------------------------------------------
-- Partitionnement dynamique (chargement des faits par année)
SET hive.exec.dynamic.partition       = true;
SET hive.exec.dynamic.partition.mode  = nonstrict;
-- Bucketing
SET hive.enforce.bucketing            = true;
-- Format & compression par défaut : Parquet + Snappy (cf. stack décidé)
SET hive.default.fileformat           = Parquet;
SET parquet.compression               = SNAPPY;
SET hive.exec.compress.output         = true;
-- Optimisations de requête (pour le benchmark L2)
SET hive.cbo.enable                   = true;
SET hive.vectorized.execution.enabled = true;
SET hive.vectorized.execution.reduce.enabled = true;
SET hive.exec.parallel                = true;

-- Vérification
SHOW DATABASES;
