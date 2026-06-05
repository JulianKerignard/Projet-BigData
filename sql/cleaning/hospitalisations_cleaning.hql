-- =============================================================================
-- [P2] Cleaning HiveQL — Hospitalisations (Bronze -> Silver -> Gold fait_hospitalisation)
-- Portage HiveQL du pipeline (les règles de nettoyage reprennent la logique du
-- profiling PySpark de P2, mais conformément au stack « HiveQL batch, sans Spark »).
-- Source : DATA 2024/Hospitalisation/Hospitalisations.csv (séparateur ';').
--
-- CONFORMITÉ Securite_Anonymisation_NFR.md §2.2.A (table Hospitalisations) :
--   Num_Hospitalisation             -> SUPPRIMÉ (identifiant direct -> surrogate hosp_key)
--   Id_patient                      -> PSEUDONYMISÉ (SHA-256 + sel, MÊME formule que consultations
--                                      => patient_id cohérent inter-faits)
--   identifiant_organisation        -> etab_id (conservé)
--   Code_diagnostic                 -> diag_id (généralisation via dim_diagnostic)
--   Suite_diagnostic_consultation   -> SUPPRIMÉ (texte libre, risque PII)
--   Date_Entree / Jour_Hospitalisation -> date_id / duree_sejour
--
-- Pré-requis : 02_faits.hql (DDL fait_hospitalisation). Secrets hors dépôt :
--   ${hivevar:MASTER_KEY} ${hivevar:SALT_SEED}
--   hive -hivevar MASTER_KEY=... -hivevar SALT_SEED=... -f sql/cleaning/hospitalisations_cleaning.hql
-- =============================================================================
SET hive.exec.dynamic.partition = true;
SET hive.exec.dynamic.partition.mode = nonstrict;

-- 0. Bronze : table externe sur le CSV (déposé sur HDFS)
CREATE DATABASE IF NOT EXISTS staging;
DROP TABLE IF EXISTS staging.hospitalisation_raw;
CREATE EXTERNAL TABLE staging.hospitalisation_raw (
  num_hospitalisation             STRING,
  id_patient                      STRING,
  identifiant_organisation        STRING,
  code_diagnostic                 STRING,
  suite_diagnostic_consultation   STRING,
  date_entree                     STRING,   -- JJ/MM/AAAA
  jour_hospitalisation            STRING
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ';'
STORED AS TEXTFILE
LOCATION '/chu/bronze/hospitalisation'
TBLPROPERTIES ('skip.header.line.count' = '1');

-- 1. Table de rejets (audit qualité, comme satisfaction)
CREATE TABLE IF NOT EXISTS staging.rejets_hospitalisation (
  ligne_source   STRING,
  raison_rejet   STRING,
  ts_rejet       TIMESTAMP
) STORED AS PARQUET;

-- 2. Silver : dédup + validation + parsing date
--    R1 dédup (id_patient, num_hospitalisation, date_entree)
--    R2 rejet clés obligatoires (id_patient, identifiant_organisation, date)
--    R3 date_entree non parseable (JJ/MM/AAAA) -> rejet
--    R4 jour_hospitalisation < 0 -> rejet ; plage 2015-2023
DROP TABLE IF EXISTS staging.hospitalisation_silver;
CREATE TABLE staging.hospitalisation_silver AS
SELECT * FROM (
  SELECT
    num_hospitalisation, id_patient, identifiant_organisation, code_diagnostic,
    to_date(from_unixtime(unix_timestamp(date_entree, 'dd/MM/yyyy'))) AS date_parsed,
    CAST(jour_hospitalisation AS INT)                                 AS jours,
    ROW_NUMBER() OVER (PARTITION BY id_patient, num_hospitalisation, date_entree
                       ORDER BY date_entree)                          AS rn
  FROM staging.hospitalisation_raw
) t
WHERE rn = 1
  AND id_patient IS NOT NULL
  AND identifiant_organisation IS NOT NULL
  AND date_parsed IS NOT NULL
  AND year(date_parsed) BETWEEN 2015 AND 2023
  AND (jours IS NULL OR jours >= 0);

-- 3. Gold : chargement fait_hospitalisation (clés conformes + pseudonymisation)
--    patient_id = SHA-256(id || MASTER_KEY || SHA-256(id || SALT_SEED))  [= formule consultations]
INSERT OVERWRITE TABLE chu_entrepot.fait_hospitalisation PARTITION (annee)
SELECT
  ROW_NUMBER() OVER (ORDER BY s.date_parsed, s.identifiant_organisation)         AS hosp_key,
  CAST(date_format(s.date_parsed, 'yyyyMMdd') AS INT)                            AS date_id,
  sha2(concat(s.id_patient, '${hivevar:MASTER_KEY}',
              sha2(concat(s.id_patient, '${hivevar:SALT_SEED}'), 256)), 256)     AS patient_id,
  s.identifiant_organisation                                                     AS etab_id,
  COALESCE(NULLIF(s.code_diagnostic, ''), 'UNKNOWN')                             AS diag_id,
  1                                                                              AS nb_hospitalisation,
  s.jours                                                                        AS duree_sejour,
  year(s.date_parsed)                                                            AS annee
FROM staging.hospitalisation_silver s;

-- 4. Capture des rejets (clés manquantes / date invalide / durée négative)
INSERT OVERWRITE TABLE staging.rejets_hospitalisation
SELECT
  CONCAT_WS(';', num_hospitalisation, id_patient, identifiant_organisation, date_entree),
  CASE
    WHEN id_patient IS NULL THEN 'PATIENT_NULL'
    WHEN identifiant_organisation IS NULL THEN 'ETAB_NULL'
    WHEN to_date(from_unixtime(unix_timestamp(date_entree,'dd/MM/yyyy'))) IS NULL THEN 'DATE_INVALIDE'
    WHEN CAST(jour_hospitalisation AS INT) < 0 THEN 'DUREE_NEGATIVE'
    ELSE 'HORS_PLAGE'
  END,
  current_timestamp()
FROM staging.hospitalisation_raw
WHERE id_patient IS NULL
   OR identifiant_organisation IS NULL
   OR to_date(from_unixtime(unix_timestamp(date_entree,'dd/MM/yyyy'))) IS NULL
   OR CAST(jour_hospitalisation AS INT) < 0
   OR year(to_date(from_unixtime(unix_timestamp(date_entree,'dd/MM/yyyy')))) NOT BETWEEN 2015 AND 2023;

-- =============================================================================
-- 5. CONTRÔLES QUALITÉ + CONFORMITÉ (UNION ALL — Hive 2.x : pas de sous-requête scalaire)
-- =============================================================================
-- 5.1 Réconciliation Bronze / Gold / rejets
SELECT 'bronze' AS etape, COUNT(*) AS lignes FROM staging.hospitalisation_raw
UNION ALL
SELECT 'gold',   SUM(nb_hospitalisation) FROM chu_entrepot.fait_hospitalisation
UNION ALL
SELECT 'rejets', COUNT(*) FROM staging.rejets_hospitalisation;

-- 5.2 Conformité : patient_id pseudonymisé (hash 64 car., jamais NULL)
SELECT COUNT(*) AS patient_id_invalides
FROM chu_entrepot.fait_hospitalisation
WHERE patient_id IS NULL OR length(patient_id) <> 64;

-- 5.3 Intégrité surrogate
SELECT COUNT(*) - COUNT(DISTINCT hosp_key) AS surrogate_doublons
FROM chu_entrepot.fait_hospitalisation;
