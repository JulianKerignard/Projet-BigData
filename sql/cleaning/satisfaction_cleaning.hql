-- =============================================================================
-- [P3] Cleaning HiveQL — Satisfaction (Bronze -> Silver / fait)  (tâche 869dh1d8b)
-- Source la plus salissante : encodage Latin-1, schéma variable, scores non
-- diffusés (NULL), pas de colonne date. Voir docs/L2_Profiling_Mapping_Cleaning_Satisfaction.md
--
-- Pré-ingestion (hors Hive, cf. ETL §4) : transcodage CP1252->UTF-8 (CSV) ou
-- conversion XLSX->CSV UTF-8, puis dépôt sous /staging/satisfaction/annee=YYYY/.
--
-- Paramètre : année de campagne (la source n'a pas de colonne date).
--   hive -hivevar annee_campagne=2020 -f sql/cleaning/satisfaction_cleaning.hql
-- Pré-requis : 02_faits.hql (DDL) + 04_chargement_dimensions.hql PHASE 1
--              (dim_etablissement + dim_geographie alimentées).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 0. Staging externe (Bronze). On ne déclare que les colonnes utiles, à leurs
--    positions stables (finess #0, finess_geo #2, region #4, score #8) ; les
--    colonnes supplémentaires des millésimes 25-colonnes sont ignorées.
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
LOCATION '/staging/satisfaction/annee=${hivevar:annee_campagne}/'
TBLPROPERTIES ('skip.header.line.count' = '1');

-- -----------------------------------------------------------------------------
-- 1. Table de rejets (audit qualité)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS staging.rejets_satisfaction (
  ligne_source   STRING,
  fichier_source STRING,
  raison_rejet   STRING,
  ts_rejet       TIMESTAMP
) STORED AS PARQUET;

USE chu_entrepot;

-- -----------------------------------------------------------------------------
-- 2. Couche Silver dédupliquée + normalisée (CTE réutilisée)
--    - R1 encodage : déjà normalisé en amont (UTF-8)
--    - score : virgule -> point, puis /10 -> note 0-10
--    - date_id : dérivé de l'année de campagne (YYYY0101), arrondi conforme §2.2.D
--    - R7 dédup défensif sur finess_geo (clé de grain)
--
-- Normalisation de libellé région LOCALE-INDÉPENDANTE : on plie les accents via
-- des classes regex en \uXXXX (ASCII pur -> insensibles à la locale du moteur,
-- contrairement à des littéraux accentués), puis on retire espaces/points/
-- apostrophes/tirets. Absorbe « Ile de France » vs « Île-de-France », ou
-- « Provence Alpes Cote d Azur » vs « Provence-Alpes-Côte d'Azur » (écart connu
-- côté dashboard). geo_id non résolu -> 'INCONNU' (surfacé par le contrôle 4.5).
-- -----------------------------------------------------------------------------
WITH norm AS (
  SELECT
    finess_geo                                                                AS etab_id,
    regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(
      lower(region),
      '[\\u00e0\\u00e1\\u00e2\\u00e4]','a'), '[\\u00e7]','c'),
      '[\\u00e8\\u00e9\\u00ea\\u00eb]','e'), '[\\u00ee\\u00ef]','i'),
      '[\\u00f4\\u00f6]','o'),               '[\\u00f9\\u00fb\\u00fc]','u'),
      '[ \\.\\u0027-]','')                                                     AS norm_region,
    CAST(CONCAT('${hivevar:annee_campagne}', '0101') AS INT)                  AS date_id,
    CASE WHEN score_all_rea_ajust IS NULL OR score_all_rea_ajust = '' THEN NULL
         ELSE CAST(REPLACE(score_all_rea_ajust, ',', '.') AS DECIMAL(5,2)) END AS score_brut,
    score_all_rea_ajust,
    ROW_NUMBER() OVER (PARTITION BY finess_geo ORDER BY finess_geo)            AS rn
  FROM staging.satisfaction_raw
)
-- 2a. INSERT des lignes VALIDES dans le fait (DDL 02_faits.hql : satisfaction_key
--     BIGINT + geo_id + PARTITION annee — aligné sur hospi/décès).
INSERT OVERWRITE TABLE fait_satisfaction PARTITION (annee = ${hivevar:annee_campagne})
SELECT
  ROW_NUMBER() OVER (ORDER BY n.etab_id)                       AS satisfaction_key,
  n.date_id,
  n.etab_id,
  COALESCE(g.geo_id, 'INCONNU')                                AS geo_id,
  ROUND(n.score_brut / 10, 1)                                  AS note_satisfaction
FROM norm n
JOIN dim_etablissement e ON n.etab_id = e.etab_id      -- R6 : FINESS site connu
LEFT JOIN (                                            -- résolution région -> geo_id (axe B8 = B7)
  SELECT geo_id,
         regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(
           lower(region),
           '[\\u00e0\\u00e1\\u00e2\\u00e4]','a'), '[\\u00e7]','c'),
           '[\\u00e8\\u00e9\\u00ea\\u00eb]','e'), '[\\u00ee\\u00ef]','i'),
           '[\\u00f4\\u00f6]','o'),               '[\\u00f9\\u00fb\\u00fc]','u'),
           '[ \\.\\u0027-]','')                   AS norm_region
  FROM dim_geographie
) g ON n.norm_region = g.norm_region
WHERE n.rn = 1                                          -- R7 : dédoublonnage
  AND n.score_brut IS NOT NULL                          -- R3 : score diffusé
  AND n.score_brut BETWEEN 0 AND 100;                   -- R5 : plage valide

-- -----------------------------------------------------------------------------
-- 3. Capture des REJETS par motif (R3, R4/R5, R6)
-- -----------------------------------------------------------------------------
INSERT INTO TABLE staging.rejets_satisfaction
SELECT
  CONCAT_WS(';', s.finess, s.finess_geo, s.region, s.score_all_rea_ajust)     AS ligne_source,
  CONCAT('esatis48h_', '${hivevar:annee_campagne}')                           AS fichier_source,
  CASE
    WHEN s.score_all_rea_ajust IS NULL OR s.score_all_rea_ajust = '' THEN 'NOTE_NULLE'
    WHEN CAST(REPLACE(s.score_all_rea_ajust, ',', '.') AS DECIMAL(5,2)) IS NULL THEN 'NOTE_NON_NUMERIQUE'
    WHEN CAST(REPLACE(s.score_all_rea_ajust, ',', '.') AS DECIMAL(5,2)) NOT BETWEEN 0 AND 100 THEN 'NOTE_HORS_PLAGE'
    WHEN e.etab_id IS NULL THEN 'ETAB_INCONNU'
  END                                                                          AS raison_rejet,
  CURRENT_TIMESTAMP()                                                          AS ts_rejet
FROM staging.satisfaction_raw s
LEFT JOIN dim_etablissement e ON s.finess_geo = e.etab_id
WHERE s.score_all_rea_ajust IS NULL OR s.score_all_rea_ajust = ''
   OR CAST(REPLACE(s.score_all_rea_ajust, ',', '.') AS DECIMAL(5,2)) IS NULL
   OR CAST(REPLACE(s.score_all_rea_ajust, ',', '.') AS DECIMAL(5,2)) NOT BETWEEN 0 AND 100
   OR e.etab_id IS NULL;

-- =============================================================================
-- 4. CONTRÔLES QUALITÉ post-nettoyage (doivent renvoyer 0 / écart justifié)
-- =============================================================================
-- 4.1 Doublons résiduels sur la clé (etab_id, date_id)
SELECT etab_id, date_id, COUNT(*) AS n
FROM fait_satisfaction GROUP BY etab_id, date_id HAVING COUNT(*) > 1;

-- 4.2 Notes hors [0,10] après normalisation (doit = 0)
SELECT COUNT(*) AS nb_notes_hors_plage
FROM fait_satisfaction WHERE note_satisfaction NOT BETWEEN 0 AND 10;

-- 4.3 Réconciliation des volumes (Bronze vs chargé vs rejeté)
--     (UNION ALL : Hive 2.x ne supporte pas les sous-requêtes scalaires en SELECT)
SELECT 'bronze' AS etape, COUNT(*) AS lignes FROM staging.satisfaction_raw
UNION ALL
SELECT 'charge', COUNT(*) FROM fait_satisfaction
 WHERE date_id = CAST(CONCAT('${hivevar:annee_campagne}','0101') AS INT)
UNION ALL
SELECT 'rejete', COUNT(*) FROM staging.rejets_satisfaction
 WHERE fichier_source = CONCAT('esatis48h_', '${hivevar:annee_campagne}');

-- 4.4 Top des motifs de rejet (R3 NOTE_NULLE attendu dominant : 25-46%)
SELECT raison_rejet, COUNT(*) AS nb
FROM staging.rejets_satisfaction
WHERE fichier_source = CONCAT('esatis48h_', '${hivevar:annee_campagne}')
GROUP BY raison_rejet ORDER BY nb DESC;

-- 4.5 Part de geo_id INCONNU (qualité de la résolution région ; doit rester faible)
SELECT
  SUM(CASE WHEN geo_id = 'INCONNU' THEN 1 ELSE 0 END) AS n_inconnu,
  COUNT(*)                                            AS total
FROM fait_satisfaction
WHERE date_id = CAST(CONCAT('${hivevar:annee_campagne}','0101') AS INT);
