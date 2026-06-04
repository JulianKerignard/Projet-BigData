-- =============================================================================
-- [COMMUN] Alimentation des dimensions conformes — couche Gold
-- Corrige l'audit : les dimensions étaient créées (01_dimensions_partagees.hql)
-- mais JAMAIS peuplées -> aucun fait n'était requêtable.
--
-- Deux phases (cf. ordre d'exécution, docs/L2_Setup_Hive_Dimensions.md) :
--   PHASE 1 (AVANT les faits) : dim_temps, dim_geographie, dim_etablissement
--     -> requises par les chargements de faits (satisfaction joint dim_etablissement
--        et dim_geographie pour résoudre geo_id).
--   PHASE 2 (APRÈS les faits) : dim_diagnostic (dérivée des codes observés).
--   En pratique : lancer 04 une 1re fois (phase 1), puis les cleanings, puis
--   relancer 04 (les INSERT OVERWRITE sont idempotents -> phase 2 peuplée sans
--   dupliquer la phase 1).
--
-- dim_patient / dim_professionnel : dépendent du Bronze PostgreSQL (tâches
--   [Px] Chargement L1 de l'équipe) -> fournies en templates commentés (section 5).
--   hive -hivevar annee_campagne=2020 -f sql/ddl/04_chargement_dimensions.hql
-- =============================================================================
SET hive.exec.dynamic.partition = true;
SET hive.exec.dynamic.partition.mode = nonstrict;
USE chu_entrepot;

-- -----------------------------------------------------------------------------
-- 1. dim_temps — calendrier généré 2015-2023 (autonome, sans source)
--    Astuce HiveQL : space()+split()+posexplode pour générer une séquence de jours.
-- -----------------------------------------------------------------------------
INSERT OVERWRITE TABLE dim_temps
SELECT
  CAST(regexp_replace(d, '-', '') AS INT)                      AS date_id,
  day(d)                                                        AS jour,
  month(d)                                                      AS mois,
  CASE month(d) WHEN 1 THEN 'Janvier' WHEN 2 THEN 'Février' WHEN 3 THEN 'Mars'
                WHEN 4 THEN 'Avril' WHEN 5 THEN 'Mai' WHEN 6 THEN 'Juin'
                WHEN 7 THEN 'Juillet' WHEN 8 THEN 'Août' WHEN 9 THEN 'Septembre'
                WHEN 10 THEN 'Octobre' WHEN 11 THEN 'Novembre' ELSE 'Décembre' END AS libelle_mois,
  quarter(d)                                                    AS trimestre,
  year(d)                                                       AS annee,
  CASE pmod(datediff(d, '2017-01-02'), 7)                       -- 2017-01-02 = lundi
       WHEN 0 THEN 'Lundi' WHEN 1 THEN 'Mardi' WHEN 2 THEN 'Mercredi'
       WHEN 3 THEN 'Jeudi' WHEN 4 THEN 'Vendredi' WHEN 5 THEN 'Samedi' ELSE 'Dimanche' END AS jour_semaine
FROM (
  SELECT date_add('2015-01-01', pe.pos) AS d
  FROM (SELECT split(space(3652), ' ') AS arr) s
  LATERAL VIEW posexplode(s.arr) pe AS pos, val
) g
WHERE g.d <= '2023-12-31';

-- -----------------------------------------------------------------------------
-- 2. dim_geographie — depuis le référentiel département->région (découpage 2016)
--    Grain région (geo_id = code_region) : axe de B7 (décès) et B8 (satisfaction).
-- -----------------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS staging;
DROP TABLE IF EXISTS staging.ref_dept_region;
CREATE EXTERNAL TABLE staging.ref_dept_region (
  code_departement STRING, code_region STRING, nom_region STRING
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '/chu/ref/dept_region'
TBLPROPERTIES ('skip.header.line.count' = '1');

INSERT OVERWRITE TABLE dim_geographie
SELECT DISTINCT
  code_region                       AS geo_id,
  code_region,
  nom_region                        AS region,
  CAST(NULL AS STRING)              AS code_departement,  -- grain région
  CAST(NULL AS STRING)              AS departement
FROM staging.ref_dept_region;

-- =============================================================================
-- 3. dim_etablissement — fusion FINESS site (PHASE 1, avant les faits)
--    Réconcilie les 2 sources qui portent un identifiant établissement :
--      - satisfaction (finess_geo + region)  -> apporte la RÉGION (=> geo_id B8)
--      - hospitalisations (identifiant_organisation) -> couverture des séjours
--    Param : -hivevar annee_campagne=2020 (campagne esatis de référence).
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS staging.satisfaction_etab_src;
CREATE EXTERNAL TABLE staging.satisfaction_etab_src (
  finess STRING, rs_finess STRING, finess_geo STRING, rs_finess_geo STRING,
  region STRING, participation STRING, depot STRING, nb_rep STRING, score STRING
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ';'
STORED AS TEXTFILE
LOCATION '/staging/satisfaction/annee=${hivevar:annee_campagne}/'
TBLPROPERTIES ('skip.header.line.count' = '1');

DROP TABLE IF EXISTS staging.hospitalisation_etab_src;
CREATE EXTERNAL TABLE staging.hospitalisation_etab_src (
  num_hospitalisation STRING, id_patient STRING, identifiant_organisation STRING,
  code_diagnostic STRING, suite_diagnostic_consultation STRING,
  date_entree STRING, jour_hospitalisation STRING
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ';'
STORED AS TEXTFILE
LOCATION '/chu/bronze/hospitalisation'
TBLPROPERTIES ('skip.header.line.count' = '1');

INSERT OVERWRITE TABLE dim_etablissement
SELECT
  etab_id,
  MAX(nom_etab)         AS nom_etab,
  CAST(NULL AS STRING)  AS type_etab,
  MAX(region)           AS region,
  CAST(NULL AS STRING)  AS departement
FROM (
  SELECT finess_geo AS etab_id, rs_finess_geo AS nom_etab, region
  FROM staging.satisfaction_etab_src
  WHERE finess_geo IS NOT NULL AND trim(finess_geo) <> ''
  UNION ALL
  SELECT identifiant_organisation AS etab_id, CAST(NULL AS STRING) AS nom_etab,
         CAST(NULL AS STRING) AS region
  FROM staging.hospitalisation_etab_src
  WHERE identifiant_organisation IS NOT NULL AND trim(identifiant_organisation) <> ''
) u
GROUP BY etab_id;

-- =============================================================================
-- 4. dim_diagnostic — CIM-10 minimal dérivé des codes OBSERVÉS (PHASE 2)
--    Pas de référentiel libellé CSV fourni -> libelle NULL ; chapitre = 1re lettre.
--    Source = faits déjà chargés -> EXÉCUTER APRÈS les cleanings (ou relancer 04).
-- -----------------------------------------------------------------------------
INSERT OVERWRITE TABLE dim_diagnostic
SELECT
  diag_id,
  diag_id                       AS code_cim10,
  CAST(NULL AS STRING)          AS libelle,
  upper(substr(diag_id, 1, 1))  AS chapitre_cim10
FROM (
  SELECT DISTINCT diag_id FROM fait_consultation    WHERE diag_id IS NOT NULL
  UNION
  SELECT DISTINCT diag_id FROM fait_hospitalisation WHERE diag_id IS NOT NULL
) d;

-- =============================================================================
-- 5. Dimensions dépendantes du Bronze PostgreSQL (tâches [Px] Chargement L1).
--    Décommenter une fois les tables Bronze patient/professionnel ingérées.
-- =============================================================================

-- dim_patient (depuis bronze PostgreSQL Patient) — patient_id PSEUDONYMISÉ
-- (le hash provient de patient_mapping_secure produit par les cleanings) ; sexe M/F
-- INSERT OVERWRITE TABLE dim_patient
-- SELECT m.id_patient_pseudo AS patient_id,
--        CASE WHEN lower(p.sexe) IN ('male','m','1') THEN 'M' ELSE 'F' END AS sexe,
--        p.tranche_age, p.region_residence
-- FROM staging.bronze_patient p
-- JOIN patient_mapping_secure m ON m.id_patient_original = p.id_patient;

-- dim_professionnel (depuis bronze Professionnel_de_sante + Specialites)
-- INSERT OVERWRITE TABLE dim_professionnel
-- SELECT DISTINCT pr.identifiant AS prof_id, sp.specialite,
--        pr.categorie_professionnelle AS categorie_prof, pr.code_specialite
-- FROM staging.bronze_professionnel pr
-- LEFT JOIN staging.bronze_specialites sp ON sp.code_specialite = pr.code_specialite;

-- Contrôles (dim_diagnostic = 0 tant que la PHASE 2 n'a pas été relancée)
SELECT 'dim_temps' AS dim, COUNT(*) AS n FROM dim_temps
UNION ALL SELECT 'dim_geographie',    COUNT(*) FROM dim_geographie
UNION ALL SELECT 'dim_etablissement', COUNT(*) FROM dim_etablissement
UNION ALL SELECT 'dim_diagnostic',    COUNT(*) FROM dim_diagnostic;
