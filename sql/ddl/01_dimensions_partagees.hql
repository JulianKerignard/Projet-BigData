-- =============================================================================
-- [COMMUN] DDL des dimensions conformes (partagées) — couche Gold
-- Tâche : 869dfg187 (Livrable 2)
-- Conforme au MCD : docs/mcd_constellation.png
-- Format : Parquet (colonnaire + Snappy) — cf. stack décidé.
-- Les dimensions sont petites -> ni partitionnées ni bucketées.
-- Clés primaires déclarées en contraintes INFORMATIVES (Hive ne les impose pas :
-- DISABLE NOVALIDATE) ; l'unicité est garantie par les jobs d'alimentation.
--   hive -f sql/ddl/01_dimensions_partagees.hql   (après 00_setup_hive.hql)
-- =============================================================================
USE chu_entrepot;

-- -----------------------------------------------------------------------------
-- Dim_Temps — axe temporel commun aux 4 faits (B2,B3,B7,B8 « sur période »)
-- Clé = entier AAAAMMJJ (ex. 20190101)
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_temps;
CREATE TABLE dim_temps (
  date_id       INT     COMMENT 'Clé technique AAAAMMJJ',
  jour          INT,
  mois          INT,
  libelle_mois  STRING,
  trimestre     INT,
  annee         INT,
  jour_semaine  STRING,
  PRIMARY KEY (date_id) DISABLE NOVALIDATE
)
COMMENT 'Dimension Temps (conforme)'
STORED AS PARQUET;

-- -----------------------------------------------------------------------------
-- Dim_Patient — caractéristiques patient (B5 sexe/âge)
-- Alimentée par PostgreSQL (consultations + hospitalisations).
-- patient_id = hash SHA-256 PSEUDONYMISÉ (cf. Securite_Anonymisation_NFR §2.3) :
-- aucun identifiant patient en clair dans la couche analytique.
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_patient;
CREATE TABLE dim_patient (
  patient_id        STRING  COMMENT 'Hash SHA-256 (64 hex) — pseudonymisé',
  sexe              STRING  COMMENT 'M / F',
  tranche_age       STRING  COMMENT '0-19, 20-39, 40-59, 60-74, 75-84, 85+',
  region_residence  STRING,
  PRIMARY KEY (patient_id) DISABLE NOVALIDATE
)
COMMENT 'Dimension Patient (conforme, pseudonymisée)'
STORED AS PARQUET;

-- -----------------------------------------------------------------------------
-- Dim_Professionnel — professionnels de santé (B6 « par professionnel »)
-- Alimentée par PostgreSQL (Professionnel_de_sante + Specialites).
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_professionnel;
CREATE TABLE dim_professionnel (
  prof_id          STRING  COMMENT 'Identifiant ADELI source',
  specialite       STRING,
  categorie_prof   STRING,
  code_specialite  STRING,
  PRIMARY KEY (prof_id) DISABLE NOVALIDATE
)
COMMENT 'Dimension Professionnel de santé (conforme)'
STORED AS PARQUET;

-- -----------------------------------------------------------------------------
-- Dim_Diagnostic — référentiel CIM-10 (B2, B4 « par diagnostic »)
-- chapitre_cim10 = généralisation par chapitre (1re lettre du code, cf. §2.2).
-- Partagée consultations + hospitalisations.
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_diagnostic;
CREATE TABLE dim_diagnostic (
  diag_id         STRING  COMMENT 'Clé technique',
  code_cim10      STRING,
  libelle         STRING,
  chapitre_cim10  STRING  COMMENT 'Catégorie généralisée (§2.2)',
  PRIMARY KEY (diag_id) DISABLE NOVALIDATE
)
COMMENT 'Dimension Diagnostic (conforme, CIM-10)'
STORED AS PARQUET;

-- -----------------------------------------------------------------------------
-- Dim_Etablissement — référentiel établissements (B1 hospi, B8 satisfaction)
-- Clé = FINESS géographique (site). Fusionne : CSV établissements (maître),
-- hospi (identifiant_organisation), satisfaction (finess_geo).
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_etablissement;
CREATE TABLE dim_etablissement (
  etab_id       STRING  COMMENT 'FINESS géographique (site)',
  nom_etab      STRING,
  type_etab     STRING,
  region        STRING,
  departement   STRING,
  PRIMARY KEY (etab_id) DISABLE NOVALIDATE
)
COMMENT 'Dimension Établissement (conforme, FINESS site)'
STORED AS PARQUET;

-- -----------------------------------------------------------------------------
-- Dim_Geographie — axe régional (B7 décès/région, B8 satisfaction/région)
-- Alimentée via le référentiel ref_dept_region (découpage 2016).
-- Garantit que décès ET satisfaction pointent vers les MÊMES geo_id.
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_geographie;
CREATE TABLE dim_geographie (
  geo_id            STRING  COMMENT 'Clé technique (code région ou dept)',
  code_region       STRING,
  region            STRING,
  code_departement  STRING,
  departement       STRING,
  PRIMARY KEY (geo_id) DISABLE NOVALIDATE
)
COMMENT 'Dimension Géographie (conforme, découpage régional 2016)'
STORED AS PARQUET;

-- Vérification
SHOW TABLES IN chu_entrepot;
