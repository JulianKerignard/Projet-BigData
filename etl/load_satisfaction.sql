-- =============================================================================
-- [P3] Chargement Fait_Satisfaction + vérification (tâche 869dfg1fp - Livrable 2)
-- Charge fait_satisfaction depuis le staging HDFS, normalise le score 0-100 -> 0-10,
-- valide la plage et l'intégrité FINESS, isole les rejets.
-- Job ETL : docs/04-etl-satisfaction.md
-- Exécution : hive -f etl/load_satisfaction.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 0. Table externe de staging (Bronze) sur les fichiers e-Satis ingérés
--    NB : fichiers transcodés CP1252 -> UTF-8 et CRLF -> LF en amont (cf. ETL §4).
--    Colonnes brutes utiles uniquement ; le score natif est sur 0-100.
-- -----------------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS staging;

DROP TABLE IF EXISTS staging.satisfaction;

CREATE EXTERNAL TABLE staging.satisfaction (
  finess              STRING,
  region              STRING,
  date_recueil        STRING,        -- ex. '2020-01-15'
  score_all_rea_ajust STRING         -- score global ajusté, échelle 0-100 (texte : virgule décimale possible)
  -- NB anonymisation (§2.2.D) : on ne déclare/projette QUE des colonnes non sensibles.
  -- Aucun champ de commentaire / avis en texte libre n'est ingéré.
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ';'
STORED AS TEXTFILE
LOCATION '/staging/satisfaction/'
TBLPROPERTIES ('skip.header.line.count' = '1');

USE chu_entrepot;

-- -----------------------------------------------------------------------------
-- 1. Chargement des lignes VALIDES
--    - anonymisation : date_id ARRONDI AU MOIS (YYYYMM01), aucune date au jour conservée (§2.2.D)
--    - normalisation : virgule -> point, puis score/10 -> note 0-10
--    - validation plage : 0 <= note <= 10
--    - intégrité référentielle : FINESS présent dans dim_etablissement
-- -----------------------------------------------------------------------------
INSERT OVERWRITE TABLE fait_satisfaction
SELECT
  CAST(CONCAT(SUBSTR(REPLACE(s.date_recueil, '-', ''), 1, 6), '01') AS INT) AS date_id,
  s.finess                                                              AS etab_id,
  ROUND(CAST(REPLACE(s.score_all_rea_ajust, ',', '.') AS DECIMAL(5,2)) / 10, 1) AS note_satisfaction
FROM staging.satisfaction s
JOIN dim_etablissement e
  ON s.finess = e.etab_id
WHERE s.score_all_rea_ajust IS NOT NULL
  AND s.score_all_rea_ajust <> ''
  AND CAST(REPLACE(s.score_all_rea_ajust, ',', '.') AS DECIMAL(5,2)) BETWEEN 0 AND 100;

-- -----------------------------------------------------------------------------
-- 2. Table des rejets (audit qualité) + alimentation par motif
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS satisfaction_rejets (
  finess              STRING,
  score_brut          STRING,
  date_recueil        STRING,
  motif               STRING
) STORED AS ORC;

INSERT OVERWRITE TABLE satisfaction_rejets
SELECT s.finess, s.score_all_rea_ajust, s.date_recueil,
       CASE
         WHEN s.score_all_rea_ajust IS NULL OR s.score_all_rea_ajust = '' THEN 'NOTE_NULLE'
         WHEN CAST(REPLACE(s.score_all_rea_ajust, ',', '.') AS DECIMAL(5,2)) NOT BETWEEN 0 AND 100 THEN 'NOTE_HORS_PLAGE'
         WHEN e.etab_id IS NULL THEN 'ETAB_INCONNU'
       END AS motif
FROM staging.satisfaction s
LEFT JOIN dim_etablissement e ON s.finess = e.etab_id
WHERE s.score_all_rea_ajust IS NULL
   OR s.score_all_rea_ajust = ''
   OR CAST(REPLACE(s.score_all_rea_ajust, ',', '.') AS DECIMAL(5,2)) NOT BETWEEN 0 AND 100
   OR e.etab_id IS NULL;

-- =============================================================================
-- 3. VÉRIFICATIONS (Definition of Done) — résultats à reporter dans le rapport L2
-- =============================================================================

-- 3.1 Volume chargé
SELECT COUNT(*) AS nb_lignes_fait FROM fait_satisfaction;

-- 3.2 Plage des notes : MIN/MAX doivent être dans [0,10], aucune NULL
SELECT MIN(note_satisfaction) AS note_min,
       MAX(note_satisfaction) AS note_max,
       ROUND(AVG(note_satisfaction), 2) AS note_moy
FROM fait_satisfaction;

-- 3.3 Aucune note NULL (doit renvoyer 0)
SELECT COUNT(*) AS nb_notes_nulles
FROM fait_satisfaction
WHERE note_satisfaction IS NULL;

-- 3.4 Intégrité référentielle : tout etab_id du fait existe dans la dimension (doit renvoyer 0)
SELECT COUNT(*) AS nb_etab_orphelins
FROM fait_satisfaction f
LEFT JOIN dim_etablissement e USING (etab_id)
WHERE e.etab_id IS NULL;

-- 3.5 Volume et motifs de rejet
SELECT motif, COUNT(*) AS nb FROM satisfaction_rejets GROUP BY motif;
