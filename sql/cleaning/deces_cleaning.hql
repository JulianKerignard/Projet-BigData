-- =============================================================================
-- [P4] Cleaning HiveQL — Décès (Bronze -> Gold fait_deces)
-- Tâche : profiling+mapping+cleaning Décès (complément du profiling awk existant).
-- Stack : HiveQL batch (cf. docs/01-architecture.md) — pas de Spark.
-- Source : répertoire INSEE deces.csv (25 M lignes), déposé en Bronze sur HDFS.
-- Besoin imposé B7 : nombre de décès par région (focus 2019).
--
-- CONFORMITÉ Securite_Anonymisation_NFR.md §2.2.B (table Décès) :
--   nom, prenom        -> SUPPRIMÉS (PII directe)
--   numero_acte_deces  -> SUPPRIMÉ (identifiant direct)
--   sexe               -> CONSERVÉ (axe d'analyse)
--   date_naissance     -> ARRONDIE (année seule -> tranche d'âge)
--   date_deces         -> CONSERVÉE (analyse temporelle)
--   code_lieu_deces    -> CONSERVÉ -> dérivation département -> région
--
--   hive -f sql/ddl/00_setup_hive.hql      (bases + paramètres)
--   hive -f sql/cleaning/deces_cleaning.hql
-- =============================================================================

SET hive.exec.dynamic.partition = true;
SET hive.exec.dynamic.partition.mode = nonstrict;

-- -----------------------------------------------------------------------------
-- 0. Bronze : table externe sur le CSV INSEE brut (séparateur ',')
-- -----------------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS staging;
DROP TABLE IF EXISTS staging.deces_raw;
CREATE EXTERNAL TABLE staging.deces_raw (
  nom                  STRING,
  prenom               STRING,
  sexe                 STRING,   -- '1' = homme, '2' = femme
  date_naissance       STRING,   -- AAAA-MM-JJ
  code_lieu_naissance  STRING,
  lieu_naissance       STRING,
  pays_naissance       STRING,
  date_deces           STRING,   -- AAAA-MM-JJ
  code_lieu_deces      STRING,   -- code commune INSEE (5 car.)
  numero_acte_deces    STRING
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '/chu/bronze/deces'
TBLPROPERTIES ('skip.header.line.count' = '1');

-- Référentiel département -> région (découpage 2016), déposé en Bronze
DROP TABLE IF EXISTS staging.ref_dept_region;
CREATE EXTERNAL TABLE staging.ref_dept_region (
  code_departement STRING,
  code_region      STRING,
  nom_region       STRING
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '/chu/ref/dept_region'
TBLPROPERTIES ('skip.header.line.count' = '1');

-- -----------------------------------------------------------------------------
-- 1. DDL du fait (Gold) : Parquet, partitionné par année
--    sexe + tranche_age = dimensions dégénérées (pas de patient identifié).
-- -----------------------------------------------------------------------------
USE chu_entrepot;
DROP TABLE IF EXISTS fait_deces;
CREATE TABLE fait_deces (
  deces_key    BIGINT,
  date_id      INT,        -- FK dim_temps (AAAAMMJJ)
  geo_id       STRING,     -- FK dim_geographie (code région)
  sexe         STRING,     -- H / F (dégénéré)
  tranche_age  STRING,     -- dégénéré
  nb_deces     INT         -- mesure (= 1)
)
PARTITIONED BY (annee INT)
STORED AS PARQUET;

-- -----------------------------------------------------------------------------
-- 2. Silver -> Gold : anonymisation + dérivation région + chargement
--    R1  : date_deces invalide / hors plage (>= 2000) -> rejet
--    R2  : dérivation département (DOM = 3 car., Corse 2A/2B, sinon 2 car.)
--    §2.2.B : nom/prenom/numero_acte JAMAIS sélectionnés
-- -----------------------------------------------------------------------------
INSERT OVERWRITE TABLE fait_deces PARTITION (annee)
SELECT
  ROW_NUMBER() OVER (ORDER BY d.date_deces, d.code_lieu_deces)  AS deces_key,
  CAST(regexp_replace(d.date_deces, '-', '') AS INT)            AS date_id,
  COALESCE(r.code_region, 'INCONNU')                            AS geo_id,
  CASE d.sexe WHEN '1' THEN 'H' WHEN '2' THEN 'F' ELSE '?' END  AS sexe,
  -- tranche d'âge (âge = année décès - année naissance, arrondi §2.2.B)
  CASE
    WHEN NOT d.date_naissance RLIKE '^[0-9]{4}' THEN 'Inconnu'
    WHEN (CAST(substr(d.date_deces,1,4) AS INT)
        - CAST(substr(d.date_naissance,1,4) AS INT)) < 20  THEN '0-19'
    WHEN (CAST(substr(d.date_deces,1,4) AS INT)
        - CAST(substr(d.date_naissance,1,4) AS INT)) < 40  THEN '20-39'
    WHEN (CAST(substr(d.date_deces,1,4) AS INT)
        - CAST(substr(d.date_naissance,1,4) AS INT)) < 60  THEN '40-59'
    WHEN (CAST(substr(d.date_deces,1,4) AS INT)
        - CAST(substr(d.date_naissance,1,4) AS INT)) < 75  THEN '60-74'
    WHEN (CAST(substr(d.date_deces,1,4) AS INT)
        - CAST(substr(d.date_naissance,1,4) AS INT)) < 85  THEN '75-84'
    ELSE '85+'
  END                                                          AS tranche_age,
  1                                                            AS nb_deces,
  CAST(substr(d.date_deces, 1, 4) AS INT)                      AS annee
FROM staging.deces_raw d
LEFT JOIN staging.ref_dept_region r
  ON r.code_departement = CASE
       WHEN substr(d.code_lieu_deces,1,2) IN ('97','98') THEN substr(d.code_lieu_deces,1,3)
       ELSE substr(d.code_lieu_deces,1,2)
     END
WHERE d.date_deces RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
  AND CAST(substr(d.date_deces,1,4) AS INT) >= 2000;

-- =============================================================================
-- 3. CONTRÔLES QUALITÉ + CONFORMITÉ
-- =============================================================================
-- 3.1 Décès 2019 par région (besoin B7) — top 5
SELECT geo_id, SUM(nb_deces) AS nb
FROM fait_deces WHERE annee = 2019
GROUP BY geo_id ORDER BY nb DESC LIMIT 5;

-- 3.2 Part de geo_id INCONNU (qualité de la dérivation région ; doit rester faible)
SELECT
  SUM(CASE WHEN geo_id = 'INCONNU' THEN nb_deces ELSE 0 END) AS deces_geo_inconnu,
  SUM(nb_deces)                                              AS total,
  ROUND(100 * SUM(CASE WHEN geo_id='INCONNU' THEN nb_deces ELSE 0 END) / SUM(nb_deces), 2) AS pct_inconnu
FROM fait_deces;

-- 3.3 Réconciliation Bronze (>=2000) vs Gold
--     (UNION ALL : Hive 2.x ne supporte pas les sous-requêtes scalaires en SELECT)
SELECT 'bronze_2000plus' AS etape, COUNT(*) AS lignes
FROM staging.deces_raw
WHERE date_deces RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
  AND CAST(substr(date_deces,1,4) AS INT) >= 2000
UNION ALL
SELECT 'gold_fait_deces', SUM(nb_deces) FROM fait_deces;

-- 3.4 Conformité §2.2.B : le fait ne contient AUCUNE colonne PII
--     (nom/prenom/numero_acte absents par construction — vérifiable via DESCRIBE)
DESCRIBE fait_deces;
