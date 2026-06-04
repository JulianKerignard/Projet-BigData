-- =============================================================================
-- [P3] Chargement Fait_Satisfaction + vérification (tâche 869dfg1fp - Livrable 2)
-- Charge fait_satisfaction depuis le staging HDFS, normalise le score 0-100 -> 0-10,
-- valide la plage et l'intégrité FINESS (site), isole les rejets.
--
-- Aligné sur le profiling réel (docs/L2_Profiling_Mapping_Cleaning_Satisfaction.md) :
--   - clé établissement = finess_geo (FINESS SITE), PAS finess (entité juridique, dupliquée)
--   - la source n'a AUCUNE colonne date  -> date_id dérivé de l'année de campagne
--   - schéma source = 23 ou 25 colonnes ; les colonnes utiles sont à positions stables
--     (finess #0, finess_geo #2, region #4, score #8)
-- Réutilise la table externe staging.satisfaction_raw et la table de rejets
--   staging.rejets_satisfaction définies par sql/cleaning/satisfaction_cleaning.hql.
--
-- Paramètre : année de campagne (un fichier = une campagne annuelle).
--   hive -hivevar annee_campagne=2020 -f etl/load_satisfaction.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 0. Table externe de staging (Bronze) sur les fichiers e-Satis ingérés.
--    Fichiers transcodés CP1252 -> UTF-8 et CRLF -> LF en amont (cf. ETL §4),
--    déposés sous /chu/staging/satisfaction/annee=YYYY/.
--    On ne déclare que les colonnes utiles à leurs positions stables ; les colonnes
--    supplémentaires des millésimes 25-colonnes sont ignorées (lues comme NULL).
--    Anonymisation (§2.2.D) : aucun champ de commentaire / avis en texte libre.
-- -----------------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS staging;

DROP TABLE IF EXISTS staging.satisfaction_raw;

CREATE EXTERNAL TABLE staging.satisfaction_raw (
  finess              STRING,   -- #0 entité juridique (NON utilisée comme clé)
  rs_finess           STRING,   -- #1
  finess_geo          STRING,   -- #2 entité géographique / site  -> etab_id
  rs_finess_geo       STRING,   -- #3
  region              STRING,   -- #4 (contrôle de cohérence uniquement)
  participation       STRING,   -- #5
  depot               STRING,   -- #6
  nb_rep_score_all    STRING,   -- #7 nb de répondants (non repris)
  score_all_rea_ajust STRING    -- #8 score global ajusté 0-100  -> note_satisfaction
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ';'
STORED AS TEXTFILE
LOCATION '/chu/staging/satisfaction/annee=${hivevar:annee_campagne}/'
TBLPROPERTIES ('skip.header.line.count' = '1');

USE chu_entrepot;

-- -----------------------------------------------------------------------------
-- 1. Chargement des lignes VALIDES
--    - date_id = année de campagne -> YYYY0101 (grain annuel : la source n'a pas
--      de date plus fine ; arrondi conforme §2.2.D)
--    - etab_id = finess_geo (FINESS site), avec intégrité référentielle sur la dim
--    - normalisation : virgule -> point, puis score/10 -> note 0-10
--    - validation plage : 0 <= score brut <= 100
--    NB : append (1 campagne = 1 exécution). Le contrôle 3.6 détecte un double chargement.
-- -----------------------------------------------------------------------------
INSERT INTO TABLE fait_satisfaction
SELECT
  CAST(CONCAT('${hivevar:annee_campagne}', '0101') AS INT)                        AS date_id,
  s.finess_geo                                                                   AS etab_id,
  ROUND(CAST(REPLACE(s.score_all_rea_ajust, ',', '.') AS DECIMAL(5,2)) / 10, 1)  AS note_satisfaction
FROM staging.satisfaction_raw s
JOIN dim_etablissement e
  ON s.finess_geo = e.etab_id
WHERE s.score_all_rea_ajust IS NOT NULL
  AND s.score_all_rea_ajust <> ''
  AND CAST(REPLACE(s.score_all_rea_ajust, ',', '.') AS DECIMAL(5,2)) BETWEEN 0 AND 100;

-- -----------------------------------------------------------------------------
-- 2. Capture des rejets (audit qualité) dans staging.rejets_satisfaction.
--    Motifs : NOTE_NULLE (dominant, 25-46 % : score non diffusé), NOTE_HORS_PLAGE,
--    ETAB_INCONNU (finess_geo absent de la dimension).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS staging.rejets_satisfaction (
  ligne_source   STRING,
  fichier_source STRING,
  raison_rejet   STRING,
  ts_rejet       TIMESTAMP
) STORED AS PARQUET;

INSERT INTO TABLE staging.rejets_satisfaction
SELECT
  CONCAT_WS(';', s.finess, s.finess_geo, s.region, s.score_all_rea_ajust)        AS ligne_source,
  CONCAT('esatis48h_', '${hivevar:annee_campagne}')                             AS fichier_source,
  CASE
    WHEN s.score_all_rea_ajust IS NULL OR s.score_all_rea_ajust = '' THEN 'NOTE_NULLE'
    WHEN CAST(REPLACE(s.score_all_rea_ajust, ',', '.') AS DECIMAL(5,2)) NOT BETWEEN 0 AND 100 THEN 'NOTE_HORS_PLAGE'
    WHEN e.etab_id IS NULL THEN 'ETAB_INCONNU'
  END                                                                            AS raison_rejet,
  CURRENT_TIMESTAMP()                                                            AS ts_rejet
FROM staging.satisfaction_raw s
LEFT JOIN dim_etablissement e ON s.finess_geo = e.etab_id
WHERE s.score_all_rea_ajust IS NULL
   OR s.score_all_rea_ajust = ''
   OR CAST(REPLACE(s.score_all_rea_ajust, ',', '.') AS DECIMAL(5,2)) NOT BETWEEN 0 AND 100
   OR e.etab_id IS NULL;

-- =============================================================================
-- 3. VÉRIFICATIONS (Definition of Done) — résultats à reporter dans le rapport L2
-- =============================================================================

-- 3.1 Volume chargé pour la campagne
SELECT COUNT(*) AS nb_lignes_fait
FROM fait_satisfaction
WHERE date_id = CAST(CONCAT('${hivevar:annee_campagne}', '0101') AS INT);

-- 3.2 Plage des notes : MIN/MAX doivent être dans [0,10]
SELECT MIN(note_satisfaction) AS note_min,
       MAX(note_satisfaction) AS note_max,
       ROUND(AVG(note_satisfaction), 2) AS note_moy
FROM fait_satisfaction
WHERE date_id = CAST(CONCAT('${hivevar:annee_campagne}', '0101') AS INT);

-- 3.3 Aucune note NULL (doit renvoyer 0)
SELECT COUNT(*) AS nb_notes_nulles
FROM fait_satisfaction
WHERE note_satisfaction IS NULL;

-- 3.4 Intégrité référentielle : tout etab_id du fait existe dans la dimension (doit = 0)
SELECT COUNT(*) AS nb_etab_orphelins
FROM fait_satisfaction f
LEFT JOIN dim_etablissement e USING (etab_id)
WHERE e.etab_id IS NULL;

-- 3.5 Volume et motifs de rejet de la campagne (NOTE_NULLE attendu dominant : 25-46 %)
SELECT raison_rejet, COUNT(*) AS nb
FROM staging.rejets_satisfaction
WHERE fichier_source = CONCAT('esatis48h_', '${hivevar:annee_campagne}')
GROUP BY raison_rejet ORDER BY nb DESC;

-- 3.6 Doublon sur la clé de grain (etab_id, date_id) : signale un double chargement (doit = 0)
SELECT etab_id, date_id, COUNT(*) AS n
FROM fait_satisfaction
GROUP BY etab_id, date_id HAVING COUNT(*) > 1;
