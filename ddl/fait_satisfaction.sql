-- =============================================================================
-- [P3] DDL Fait_Satisfaction (tâche 869dfg1fa - Livrable 2)
-- Table de faits Satisfaction : 1 mesure (note), 2 FK (Temps, Établissement).
-- Modèle : docs/03-fait-satisfaction.md
-- Exécution : hive -f ddl/fait_satisfaction.sql
-- =============================================================================

USE chu_entrepot;

DROP TABLE IF EXISTS fait_satisfaction;

CREATE TABLE fait_satisfaction (
  date_id           INT           COMMENT 'FK -> dim_temps (YYYYMMDD), date de recueil',
  etab_id           STRING        COMMENT 'FK -> dim_etablissement (FINESS)',
  note_satisfaction DECIMAL(3,1)  COMMENT 'Note de satisfaction normalisee 0-10 (score e-Satis / 10)'
)
COMMENT 'Fait Satisfaction patients - grain : 1 note par etablissement et par date de recueil'
STORED AS ORC
TBLPROPERTIES ('orc.compress' = 'SNAPPY');

-- Vérification (Definition of Done)
DESCRIBE FORMATTED fait_satisfaction;
