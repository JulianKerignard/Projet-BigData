-- =====================================================================
-- Nettoyage + pseudonymisation des Consultations (Bronze -> Silver)
-- Tâche : [P1] Profiling + mapping + cleaning Consultations
-- Stack : HiveQL batch (cf. docs/01-architecture.md)
-- CONFORMITÉ : docs/Securite_Anonymisation_NFR.md
--   §2.3 pseudonymisation Id_patient (SHA-256 + clé maître + sel par patient)
--   §4.2 table de mapping sécurisée (accès ADMIN uniquement)
--   §2.2 minimisation : suppression du texte libre non nécessaire
-- Pré-requis : table externe bronze_consultation chargée depuis HDFS
--              (cf. docs/L1_Description_Job_ETL_Consultations.md, Stage 1)
-- Secrets injectés hors dépôt :
--   ${hivevar:MASTER_KEY} -> clé maître (KMS, jamais sur disque)
--   ${hivevar:SALT_SEED}  -> graine de dérivation des sels par patient
-- =====================================================================

SET hive.exec.dynamic.partition = true;
SET hive.exec.dynamic.partition.mode = nonstrict;

-- ---------------------------------------------------------------------
-- Étape 1 : déduplication défensive sur la clé naturelle (R1)
-- (0 doublon constaté, mais on sécurise les rechargements)
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
-- Étape 2 : rejet des lignes sans clé obligatoire (R2)
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS silver_consultation_valid;
CREATE TABLE silver_consultation_valid AS
SELECT *
FROM silver_consultation_dedup
WHERE num_consultation  IS NOT NULL
  AND id_patient        IS NOT NULL
  AND date_consultation IS NOT NULL;

-- ---------------------------------------------------------------------
-- Étape 3 : PSEUDONYMISATION du patient (conforme §2.3 + §4.2)
--   - 1 sel par patient, dérivé de SALT_SEED (déterministe -> rechargements stables)
--   - id_patient_pseudo = SHA-256(id_original || MASTER_KEY || sel_patient)
--   - mapping stocké dans une table sécurisée séparée (accès ADMIN)
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS patient_mapping_secure;
CREATE TABLE patient_mapping_secure (
  id_patient_original INT,
  id_patient_pseudo   STRING,
  salt_patient        STRING,
  creation_date       TIMESTAMP
);
-- NB : en production cette table est chiffrée (AES-256 at-rest) et son accès
--      est restreint au rôle ADMIN via les ACL Hive/Ranger (cf. §1.2, §4.2).

INSERT OVERWRITE TABLE patient_mapping_secure
SELECT
  id_patient_original,
  sha2(concat(CAST(id_patient_original AS STRING),
              '${hivevar:MASTER_KEY}', salt_patient), 256) AS id_patient_pseudo,
  salt_patient,
  current_timestamp()
FROM (
  SELECT DISTINCT
    CAST(id_patient AS INT) AS id_patient_original,
    -- sel par patient (déterministe, dérivé de la graine secrète)
    sha2(concat(CAST(id_patient AS STRING), '${hivevar:SALT_SEED}'), 256) AS salt_patient
  FROM silver_consultation_valid
) p;

-- ---------------------------------------------------------------------
-- Étape 4 : standardisation + corrections, AVEC patient pseudonymisé
--   - R3 : code_diag NULL/'' -> 'UNKNOWN'
--   - R4 : date hors plage 2015-2023 -> rejet
--   - R5 : heure_fin < heure_debut -> duree_minutes = NULL
--   - §2.2 : 'motif' (texte libre) SUPPRIMÉ (aucun besoin + risque PII)
--   - id_patient en clair JAMAIS propagé : seul id_patient_pseudo subsiste
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS silver_consultation;
CREATE TABLE silver_consultation AS
SELECT
  CAST(c.num_consultation AS INT)                        AS num_consultation,
  m.id_patient_pseudo,                                   -- pseudonymisé (plus d'ID clair)
  c.id_prof_sante,
  COALESCE(NULLIF(c.code_diag, ''), 'UNKNOWN')           AS code_diag,
  CAST(c.date_consultation AS DATE)                      AS date_consultation,
  CASE
    WHEN c.heure_debut IS NULL OR c.heure_fin IS NULL THEN NULL
    WHEN unix_timestamp(c.heure_fin,  'HH:mm:ss')
       < unix_timestamp(c.heure_debut,'HH:mm:ss') THEN NULL
    ELSE (unix_timestamp(c.heure_fin,  'HH:mm:ss')
        - unix_timestamp(c.heure_debut,'HH:mm:ss')) / 60
  END                                                    AS duree_minutes
FROM silver_consultation_valid c
JOIN patient_mapping_secure m
  ON m.id_patient_original = CAST(c.id_patient AS INT)
WHERE year(CAST(c.date_consultation AS DATE)) BETWEEN 2015 AND 2023;

-- ---------------------------------------------------------------------
-- Étape 5 : contrôles qualité + CONFORMITÉ (doivent tous renvoyer 0)
-- ---------------------------------------------------------------------
-- Doublons résiduels
SELECT COUNT(*) - COUNT(DISTINCT num_consultation) AS doublons_residuels
FROM silver_consultation;

-- Durées négatives résiduelles (doit être 0 par construction)
SELECT COUNT(*) AS durees_negatives
FROM silver_consultation WHERE duree_minutes < 0;

-- CONTRÔLE CONFORMITÉ (§2.3 étape 4) : aucun identifiant patient en clair
-- dans la table analytique. id_patient_pseudo doit être un hash de 64 caractères.
SELECT COUNT(*) AS pseudo_invalides
FROM silver_consultation
WHERE id_patient_pseudo IS NULL OR length(id_patient_pseudo) <> 64;

-- Réconciliation des volumes (écart = lignes rejetées par R2/R4)
SELECT
  (SELECT COUNT(*) FROM bronze_consultation)  AS bronze,
  (SELECT COUNT(*) FROM silver_consultation)  AS silver;
