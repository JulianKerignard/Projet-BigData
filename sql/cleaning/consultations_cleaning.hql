-- =====================================================================
-- Nettoyage des Consultations (Bronze -> Silver)
-- Tâche : [P1] Profiling + mapping + cleaning Consultations
-- Stack : HiveQL batch (cf. docs/01-architecture.md)
-- Pré-requis : table externe bronze_consultation chargée depuis HDFS
--              (cf. docs/L1_Description_Job_ETL_Consultations.md, Stage 1)
-- Principe : nettoyage léger — le profiling a montré une source de très
--            bonne qualité (0 null, 0 doublon, 0 FK orpheline).
-- =====================================================================

SET hive.exec.dynamic.partition = true;
SET hive.exec.dynamic.partition.mode = nonstrict;

-- ---------------------------------------------------------------------
-- Étape 1 : déduplication défensive sur la clé naturelle
-- (0 doublon constaté, mais on sécurise le pipeline pour les rechargements)
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS silver_consultation_dedup;
CREATE TABLE silver_consultation_dedup AS
SELECT num_consultation, id_mut, id_patient, id_prof_sante,
       code_diag, motif, date_consultation, heure_debut, heure_fin
FROM (
  SELECT *,
         ROW_NUMBER() OVER (PARTITION BY num_consultation
                            ORDER BY date_consultation) AS rn
  FROM bronze_consultation
) t
WHERE rn = 1;

-- ---------------------------------------------------------------------
-- Étape 2 : rejet des lignes sans clé obligatoire
-- (aucune attendue d'après le profiling ; filet de sécurité)
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS silver_consultation_valid;
CREATE TABLE silver_consultation_valid AS
SELECT *
FROM silver_consultation_dedup
WHERE num_consultation  IS NOT NULL
  AND id_patient        IS NOT NULL
  AND date_consultation IS NOT NULL;

-- ---------------------------------------------------------------------
-- Étape 3 : standardisation + correction des anomalies identifiées
--   - typage de la date, contrôle de plage (2015-2023)
--   - standardisation du sexe patient (male/female -> M/F) côté Dim_Patient
--   - correction des 10 lignes heure_fin < heure_debut : durée mise à NULL
--     (mesure dégradée plutôt que valeur négative)
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS silver_consultation;
CREATE TABLE silver_consultation AS
SELECT
  CAST(num_consultation AS INT)                          AS num_consultation,
  CAST(id_patient AS INT)                                AS id_patient,
  id_prof_sante,
  COALESCE(NULLIF(code_diag, ''), 'UNKNOWN')             AS code_diag,
  motif,
  CAST(date_consultation AS DATE)                        AS date_consultation,
  heure_debut,
  heure_fin,
  -- durée en minutes, NULL si incohérence horaire
  CASE
    WHEN heure_debut IS NULL OR heure_fin IS NULL THEN NULL
    WHEN unix_timestamp(heure_fin,  'HH:mm:ss')
       < unix_timestamp(heure_debut,'HH:mm:ss') THEN NULL
    ELSE (unix_timestamp(heure_fin,  'HH:mm:ss')
        - unix_timestamp(heure_debut,'HH:mm:ss')) / 60
  END                                                    AS duree_minutes
FROM silver_consultation_valid
WHERE year(CAST(date_consultation AS DATE)) BETWEEN 2015 AND 2023;

-- ---------------------------------------------------------------------
-- Étape 4 : contrôles qualité post-nettoyage (doivent tous renvoyer 0)
-- ---------------------------------------------------------------------
-- Doublons résiduels
SELECT COUNT(*) - COUNT(DISTINCT num_consultation) AS doublons_residuels
FROM silver_consultation;

-- Durées négatives résiduelles (doit être 0 par construction)
SELECT COUNT(*) AS durees_negatives
FROM silver_consultation
WHERE duree_minutes < 0;

-- Réconciliation des volumes (écart = lignes rejetées)
SELECT
  (SELECT COUNT(*) FROM bronze_consultation)  AS bronze,
  (SELECT COUNT(*) FROM silver_consultation)  AS silver;
