-- ============================================================================
-- L2 - DDL Fait_Hospitalisation
-- Task: [P2] DDL Fait_Hospitalisation
--
-- Create the fact table for Hospitalisations with:
-- - Proper schema definition
-- - Partitioning by year
-- - Bucketing by patient ID
-- - Indexes for performance
-- ============================================================================

-- Drop if exists (for dev/testing)
DROP TABLE IF EXISTS Fait_Hospitalisation;

-- ============================================================================
-- CREATE FACT TABLE
-- ============================================================================

CREATE TABLE Fait_Hospitalisation (
  -- Foreign Keys (Dimensions)
  id_temps INT NOT NULL,                      -- FK: Dim_Temps (date entry)
  id_patient INT NOT NULL,                    -- FK: Dim_Patient (pseudonymized)
  id_etablissement INT NOT NULL,              -- FK: Dim_Etablissement
  id_diagnostic INT,                          -- FK: Dim_Diagnostic (nullable)
  id_type_sejour INT,                         -- FK: Dim_Type_Sejour

  -- Degenerate Dimensions
  num_hospitalisation_pseudo VARCHAR(64),     -- Pseudonymized hospitalization ID
  date_entree DATE NOT NULL,                  -- Entry date (denormalized for querying)
  date_sortie DATE,                           -- Exit date
  motif_sortie VARCHAR(100),                  -- Reason for discharge

  -- Measures (Facts)
  nb_hospitalisations INT DEFAULT 1,          -- Count (typically 1 per row)
  nb_jours_hospitalisation INT NOT NULL,      -- Length of stay in days
  dmos DECIMAL(7,2),                          -- Duration Mean Length of Stay
  cout_estime DECIMAL(12,2),                  -- Estimated cost (optional)

  -- Flags
  est_readmission BOOLEAN DEFAULT FALSE,      -- Readmission within 30 days
  est_deces BOOLEAN DEFAULT FALSE,            -- Patient death during stay
  est_sortie_contre_avis BOOLEAN DEFAULT FALSE,  -- Discharge against medical advice

  -- Data Quality
  date_chargement TIMESTAMP NOT NULL,         -- Load timestamp
  date_modification TIMESTAMP NOT NULL,       -- Last modification timestamp
  source_data VARCHAR(100) DEFAULT 'hospitalisations.csv'  -- Data source
)
COMMENT 'Fact table for hospitalisation events with dimensions for temporal, patient, facility and diagnostic analysis'
PARTITIONED BY (annee_entree INT)             -- Partition by year
CLUSTERED BY (id_patient) INTO 8 BUCKETS      -- Bucket by patient (for join optimization)
ROW FORMAT DELIMITED
  FIELDS TERMINATED BY '\001'
  ESCAPED BY '\\'
  NULL DEFINED AS '\N'
STORED AS PARQUET
TBLPROPERTIES (
  'compression'='snappy',
  'parquet.compression'='SNAPPY',
  'orc.compress'='SNAPPY'
);

-- ============================================================================
-- CREATE EXTERNAL TABLE (for raw data ingestion)
-- ============================================================================

DROP TABLE IF EXISTS Fait_Hospitalisation_Staging;

CREATE EXTERNAL TABLE Fait_Hospitalisation_Staging (
  id_temps INT,
  id_patient INT,
  id_etablissement INT,
  id_diagnostic INT,
  id_type_sejour INT,
  num_hospitalisation_pseudo VARCHAR(64),
  date_entree DATE,
  date_sortie DATE,
  motif_sortie VARCHAR(100),
  nb_hospitalisations INT,
  nb_jours_hospitalisation INT,
  dmos DECIMAL(7,2),
  cout_estime DECIMAL(12,2),
  est_readmission BOOLEAN,
  est_deces BOOLEAN,
  est_sortie_contre_avis BOOLEAN,
  date_chargement TIMESTAMP,
  date_modification TIMESTAMP
)
STORED AS PARQUET
LOCATION '/warehouse/staging/fait_hospitalisation'
TBLPROPERTIES ('external.table.purge'='true');

-- ============================================================================
-- CREATE INDEXES FOR COMMON QUERIES
-- ============================================================================

-- Index on foreign keys
CREATE INDEX idx_fait_hosp_temps
  ON TABLE Fait_Hospitalisation (id_temps)
  AS 'COMPACT' WITH DEFERRED REBUILD;

CREATE INDEX idx_fait_hosp_patient
  ON TABLE Fait_Hospitalisation (id_patient)
  AS 'COMPACT' WITH DEFERRED REBUILD;

CREATE INDEX idx_fait_hosp_etablissement
  ON TABLE Fait_Hospitalisation (id_etablissement)
  AS 'COMPACT' WITH DEFERRED REBUILD;

CREATE INDEX idx_fait_hosp_diagnostic
  ON TABLE Fait_Hospitalisation (id_diagnostic)
  AS 'COMPACT' WITH DEFERRED REBUILD;

-- Composite indexes for common join patterns
CREATE INDEX idx_fait_hosp_etab_diag
  ON TABLE Fait_Hospitalisation (id_etablissement, id_diagnostic)
  AS 'COMPACT' WITH DEFERRED REBUILD;

CREATE INDEX idx_fait_hosp_patient_temps
  ON TABLE Fait_Hospitalisation (id_patient, id_temps)
  AS 'COMPACT' WITH DEFERRED REBUILD;

-- Index on dates for temporal queries
CREATE INDEX idx_fait_hosp_date_entree
  ON TABLE Fait_Hospitalisation (date_entree)
  AS 'COMPACT' WITH DEFERRED REBUILD;

-- ============================================================================
-- CREATE MATERIALIZED VIEWS FOR COMMON AGGREGATIONS
-- ============================================================================

-- View 1: Hospitalisations by facility and year
CREATE VIEW v_hosp_by_etablissement_year AS
SELECT
  e.nom_region,
  e.nom as nom_etablissement,
  YEAR(f.date_entree) as annee,
  COUNT(*) as nb_hospitalisations,
  AVG(f.nb_jours_hospitalisation) as dmos_moyen,
  SUM(CASE WHEN f.est_deces THEN 1 ELSE 0 END) as nb_deces,
  ROUND(SUM(CASE WHEN f.est_deces THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as taux_mortalite_pct
FROM Fait_Hospitalisation f
JOIN Dim_Etablissement e ON f.id_etablissement = e.id_etablissement
GROUP BY e.nom_region, e.nom, YEAR(f.date_entree)
WITH READ ONLY;

-- View 2: Hospitalisations by diagnosis
CREATE VIEW v_hosp_by_diagnostic AS
SELECT
  d.code_cim10,
  d.libelle_court,
  d.groupe_diagnostic,
  COUNT(*) as nb_cas,
  AVG(f.nb_jours_hospitalisation) as dmos_moyen,
  MIN(f.nb_jours_hospitalisation) as dmos_min,
  MAX(f.nb_jours_hospitalisation) as dmos_max
FROM Fait_Hospitalisation f
JOIN Dim_Diagnostic d ON f.id_diagnostic = d.id_diagnostic
GROUP BY d.code_cim10, d.libelle_court, d.groupe_diagnostic
WITH READ ONLY;

-- View 3: Hospitalisations by patient demographics
CREATE VIEW v_hosp_by_demographics AS
SELECT
  p.sexe,
  p.groupe_age,
  t.annee,
  COUNT(*) as nb_hospitalisations,
  AVG(f.nb_jours_hospitalisation) as dmos_moyen,
  SUM(CASE WHEN f.est_readmission THEN 1 ELSE 0 END) as nb_readmissions
FROM Fait_Hospitalisation f
JOIN Dim_Patient p ON f.id_patient = p.id_patient
JOIN Dim_Temps t ON f.id_temps = t.id_temps
GROUP BY p.sexe, p.groupe_age, t.annee
WITH READ ONLY;

-- ============================================================================
-- TABLE STATISTICS
-- ============================================================================

-- Enable automatic statistics computation
ALTER TABLE Fait_Hospitalisation
SET TBLPROPERTIES (
  'numRows'='0',
  'totalSize'='0',
  'transient_lastDdlTime'='{current_timestamp}',
  'bucketing_version'='2'
);

-- ============================================================================
-- AUDIT LOGGING TABLE
-- ============================================================================

DROP TABLE IF EXISTS audit_fait_hospitalisation;

CREATE TABLE audit_fait_hospitalisation (
  audit_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  operation_type VARCHAR(10),              -- INSERT, UPDATE, DELETE
  num_rows_affected INT,
  operation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  user_name VARCHAR(100),
  operation_details VARCHAR(500),
  notes VARCHAR(500)
)
ROW FORMAT DELIMITED
  FIELDS TERMINATED BY '\001'
STORED AS PARQUET;

-- ============================================================================
-- DATA QUALITY CHECKS
-- ============================================================================

-- Procedure to validate fact table integrity
DELIMITER $$

CREATE PROCEDURE sp_validate_fait_hospitalisation()
BEGIN
  DECLARE v_error_count INT;
  DECLARE v_total_rows INT;

  SET v_total_rows = (SELECT COUNT(*) FROM Fait_Hospitalisation);

  -- Check 1: No NULL mandatory keys
  SET v_error_count = (
    SELECT COUNT(*) FROM Fait_Hospitalisation
    WHERE id_temps IS NULL
       OR id_patient IS NULL
       OR id_etablissement IS NULL
  );

  IF v_error_count > 0 THEN
    INSERT INTO audit_fait_hospitalisation
    VALUES (NULL, 'VALIDATE', v_error_count, NOW(), USER(), 'NULL_KEY_ERROR',
            CONCAT('Found ', v_error_count, ' rows with NULL mandatory keys'));
  END IF;

  -- Check 2: Date consistency (entry before exit)
  SET v_error_count = (
    SELECT COUNT(*) FROM Fait_Hospitalisation
    WHERE date_sortie IS NOT NULL AND date_entree > date_sortie
  );

  IF v_error_count > 0 THEN
    INSERT INTO audit_fait_hospitalisation
    VALUES (NULL, 'VALIDATE', v_error_count, NOW(), USER(), 'DATE_ORDER_ERROR',
            CONCAT('Found ', v_error_count, ' rows with entry date after exit date'));
  END IF;

  -- Check 3: Foreign key orphans
  SET v_error_count = (
    SELECT COUNT(*) FROM Fait_Hospitalisation f
    WHERE NOT EXISTS (SELECT 1 FROM Dim_Temps WHERE id_temps = f.id_temps)
  );

  IF v_error_count > 0 THEN
    INSERT INTO audit_fait_hospitalisation
    VALUES (NULL, 'VALIDATE', v_error_count, NOW(), USER(), 'FK_ORPHAN_TEMPS',
            CONCAT('Found ', v_error_count, ' orphan time references'));
  END IF;

  SELECT 'Validation complete' as status, v_total_rows as total_rows, v_error_count as errors;
END$$

DELIMITER ;

-- ============================================================================
-- EXECUTION
-- ============================================================================

-- Call validation
CALL sp_validate_fait_hospitalisation();

-- Display table info
SHOW CREATE TABLE Fait_Hospitalisation;

-- Display size estimates
EXPLAIN FORMATTED SELECT * FROM Fait_Hospitalisation LIMIT 1;

SHOW TBLPROPERTIES Fait_Hospitalisation;

-- ============================================================================
-- DOCUMENTATION
-- ============================================================================

/*
FACT TABLE: Fait_Hospitalisation

PURPOSE:
  Central fact table for hospital admissions analysis with support for:
  - Temporal analysis (by day, week, month, year)
  - Geographic analysis (by region, facility)
  - Medical analysis (by diagnosis, treatment type)
  - Patient demographics (age, sex)

PARTITIONING STRATEGY:
  - Primary: annee_entree (YEAR of admission)
  - Rationale: Enables efficient queries by year, supports retention policies

BUCKETING STRATEGY:
  - Bucketing key: id_patient (8 buckets)
  - Rationale: Improves join performance with Dim_Patient, enables sampling
  - Hash distribution for even data spread

COMPRESSION:
  - Format: Parquet with Snappy compression
  - Reduces storage by ~70% vs uncompressed
  - Maintains query performance

INDEXES:
  - Foreign key indexes: Fast joins with dimensions
  - Composite indexes: Optimize common query patterns
  - Data type: COMPACT for space efficiency

MEASURES:
  - nb_hospitalisations: Grain (typically 1)
  - nb_jours_hospitalisation: Length of stay
  - dmos: Duration Mean Length of Stay (derived measure)
  - cout_estime: Cost (for financial analysis)

FLAGS:
  - est_readmission: Readmission within 30 days of previous discharge
  - est_deces: Death during hospitalization
  - est_sortie_contre_avis: Discharge against medical advice

AUDIT:
  - date_chargement: When record was loaded
  - date_modification: Last update timestamp
  - source_data: Source system identifier

SIZE ESTIMATES:
  - Expected rows: 5-10 million (with historical data 2015-2023)
  - Row size: ~150 bytes (before compression)
  - Compressed size: ~50-60 GB
  - Growth rate: ~500K new records/year

REFRESH FREQUENCY:
  - Daily batch load after midnight
  - Incremental or full load (depends on source capability)
  - SLA: Load complete by 02:00 UTC

RETENTION POLICY:
  - Hot data: Current year + 2 years (PARQUET)
  - Cold data: 3-10 years (PARQUET, compressed further)
  - Archive: >10 years (if required by regulation)
*/
