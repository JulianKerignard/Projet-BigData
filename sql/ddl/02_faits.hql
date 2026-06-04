-- =============================================================================
-- [COMMUN] DDL canonique des tables de FAITS — couche Gold (chu_entrepot)
-- Source unique de vérité pour les 4 faits. Conforme au MCD docs/mcd_constellation.png
-- et aux dimensions (sql/ddl/01_dimensions_partagees.hql).
--
-- CONVENTION DE CLÉS (identique dimensions <-> faits, corrige l'audit) :
--   date_id INT | patient_id STRING | prof_id STRING | diag_id STRING
--   etab_id STRING | geo_id STRING   (+ surrogate <fait>_key BIGINT)
-- Format : Parquet, partitionné par annee, bucketé sur la clé de jointure dominante.
--   hive -f sql/ddl/00_setup_hive.hql
--   hive -f sql/ddl/01_dimensions_partagees.hql
--   hive -f sql/ddl/02_faits.hql
-- =============================================================================
USE chu_entrepot;

-- -----------------------------------------------------------------------------
-- Fait_Consultation — grain : une ligne = une consultation (B2, B6)
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS fait_consultation;
CREATE TABLE fait_consultation (
  consultation_key  BIGINT,
  date_id           INT,      -- FK dim_temps
  patient_id        STRING,   -- FK dim_patient (pseudonymisé)
  prof_id           STRING,   -- FK dim_professionnel
  diag_id           STRING,   -- FK dim_diagnostic
  nb_consultation   INT,      -- mesure (= 1)
  duree_minutes     DOUBLE    -- mesure
)
PARTITIONED BY (annee INT)
CLUSTERED BY (prof_id) INTO 8 BUCKETS
STORED AS PARQUET;

-- -----------------------------------------------------------------------------
-- Fait_Hospitalisation — grain : une ligne = un séjour (B3, B4, B5)
-- (remplace l'ancien sql/L2_02_DDL_Fait_Hospitalisation.sql écrit en MySQL/T-SQL)
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS fait_hospitalisation;
CREATE TABLE fait_hospitalisation (
  hosp_key            BIGINT,
  date_id             INT,      -- FK dim_temps (date d'entrée)
  patient_id          STRING,   -- FK dim_patient (pseudonymisé) -> B5 sexe/âge
  etab_id             STRING,   -- FK dim_etablissement
  diag_id             STRING,   -- FK dim_diagnostic
  nb_hospitalisation  INT,      -- mesure (= 1)
  duree_sejour        INT       -- mesure (jours)
)
PARTITIONED BY (annee INT)
CLUSTERED BY (etab_id) INTO 8 BUCKETS
STORED AS PARQUET;

-- -----------------------------------------------------------------------------
-- Fait_Satisfaction — grain : une ligne = un établissement × campagne (B8)
-- geo_id (région) porté sur le fait : B7 (décès/région) et B8 (satisfaction/région)
-- partagent ainsi le MÊME axe dim_geographie -> indicateurs régionaux comparables.
-- (pas de patient : source déjà agrégée par établissement).
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS fait_satisfaction;
CREATE TABLE fait_satisfaction (
  satisfaction_key   BIGINT,
  date_id            INT,           -- FK dim_temps (AAAA0101, grain annuel)
  etab_id            STRING,        -- FK dim_etablissement
  geo_id             STRING,        -- FK dim_geographie (code région) -> axe B8 = axe B7
  note_satisfaction  DECIMAL(3,1)   -- mesure (score /10)
)
PARTITIONED BY (annee INT)
STORED AS PARQUET;

-- -----------------------------------------------------------------------------
-- Fait_Deces — grain : une ligne = un décès (B7)
-- sexe + tranche_age en dimensions dégénérées (pas de patient identifié).
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS fait_deces;
CREATE TABLE fait_deces (
  deces_key    BIGINT,
  date_id      INT,        -- FK dim_temps
  geo_id       STRING,     -- FK dim_geographie (code région)
  sexe         STRING,     -- M / F (dégénéré)
  tranche_age  STRING,     -- dégénéré
  nb_deces     INT         -- mesure (= 1)
)
PARTITIONED BY (annee INT)
CLUSTERED BY (geo_id) INTO 8 BUCKETS
STORED AS PARQUET;

SHOW TABLES IN chu_entrepot;
