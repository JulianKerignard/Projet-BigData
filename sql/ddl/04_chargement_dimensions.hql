-- =============================================================================
-- [COMMUN] Alimentation des dimensions conformes — couche Gold
-- Corrige l'audit : les dimensions étaient créées (01_dimensions_partagees.hql)
-- mais JAMAIS peuplées -> aucun fait n'était requêtable.
--
-- dim_temps + dim_geographie : autonomes (générées / référentiel) -> exécutables tels quels.
-- dim_patient / professionnel / diagnostic / etablissement : alimentées depuis le
-- Bronze (PostgreSQL/CSV ingérés). Les blocs sont fournis ; ils requièrent les
-- tables Bronze correspondantes (cf. jobs ETL L1).
--   hive -f sql/ddl/00_setup_hive.hql ; 01_dimensions_partagees.hql ; 04_chargement_dimensions.hql
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
-- 3. Dimensions alimentées depuis le Bronze (requièrent l'ingestion L1)
--    Décommenter une fois les tables Bronze disponibles.
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

-- dim_diagnostic (depuis bronze Diagnostic) — chapitre_cim10 = 1re lettre du code
-- INSERT OVERWRITE TABLE dim_diagnostic
-- SELECT code_diag AS diag_id, code_diag AS code_cim10, diagnostic AS libelle,
--        upper(substr(code_diag,1,1)) AS chapitre_cim10
-- FROM staging.bronze_diagnostic;

-- dim_etablissement (depuis CSV établissements — FINESS site = clé de fusion
-- avec hospi.identifiant_organisation et satisfaction.finess_geo)
-- INSERT OVERWRITE TABLE dim_etablissement
-- SELECT finess_geo AS etab_id, raison_sociale_site AS nom_etab, categorie AS type_etab,
--        region, departement
-- FROM staging.bronze_etablissements;

-- Contrôles
SELECT 'dim_temps' AS dim, COUNT(*) AS n FROM dim_temps
UNION ALL SELECT 'dim_geographie', COUNT(*) FROM dim_geographie;
