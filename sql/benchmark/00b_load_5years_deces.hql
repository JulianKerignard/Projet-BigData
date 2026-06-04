-- =============================================================================
-- [P4] Benchmark L2 — Charger 5 années (2015-2019) pour partition pruning visible
-- Tâche ClickUp : 869dfg1ne
--
-- Avec une seule partition existante, le partition pruning ne se mesure pas
-- (lire 1/1 = lire tout). En chargeant 5 ans, on rend "WHERE annee=2019"
-- comparable : 1/5 des données scannées vs 5/5 en baseline.
-- =============================================================================
SET hive.exec.dynamic.partition = true;
SET hive.exec.dynamic.partition.mode = nonstrict;
USE chu_entrepot;

-- Re-cleaning Bronze -> Gold sur 5 années (2015-2019)
INSERT OVERWRITE TABLE fait_deces PARTITION (annee)
SELECT
  ROW_NUMBER() OVER (ORDER BY d.date_deces, d.code_lieu_deces)  AS deces_key,
  CAST(regexp_replace(d.date_deces, '-', '') AS INT)            AS date_id,
  COALESCE(r.code_region, 'INCONNU')                            AS geo_id,
  CASE d.sexe WHEN '1' THEN 'M' WHEN '2' THEN 'F' ELSE '?' END  AS sexe,
  CASE
    WHEN NOT d.date_naissance RLIKE '^[0-9]{4}' THEN 'Inconnu'
    WHEN (CAST(substr(d.date_deces,1,4) AS INT) - CAST(substr(d.date_naissance,1,4) AS INT)) < 20 THEN '0-19'
    WHEN (CAST(substr(d.date_deces,1,4) AS INT) - CAST(substr(d.date_naissance,1,4) AS INT)) < 40 THEN '20-39'
    WHEN (CAST(substr(d.date_deces,1,4) AS INT) - CAST(substr(d.date_naissance,1,4) AS INT)) < 60 THEN '40-59'
    WHEN (CAST(substr(d.date_deces,1,4) AS INT) - CAST(substr(d.date_naissance,1,4) AS INT)) < 75 THEN '60-74'
    WHEN (CAST(substr(d.date_deces,1,4) AS INT) - CAST(substr(d.date_naissance,1,4) AS INT)) < 85 THEN '75-84'
    ELSE '85+'
  END                                                          AS tranche_age,
  1                                                            AS nb_deces,
  CAST(substr(d.date_deces, 1, 4) AS INT)                      AS annee
FROM staging.deces_raw d
LEFT JOIN staging.ref_dept_region r
  ON r.code_departement = CASE
       WHEN substr(d.code_lieu_deces,1,2) IN ('97','98') THEN substr(d.code_lieu_deces,1,3)
       ELSE substr(d.code_lieu_deces,1,2)
     END
WHERE d.date_deces RLIKE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
  AND substr(d.date_deces,1,4) IN ('2015','2016','2017','2018','2019');

-- Re-INSERT baseline (mêmes 5 ans, sans partition/bucket)
INSERT OVERWRITE TABLE fait_deces_baseline
SELECT deces_key, date_id, geo_id, sexe, tranche_age, nb_deces, annee
FROM fait_deces;

-- Vérifications
SHOW PARTITIONS fait_deces;
SELECT annee, COUNT(*) AS n FROM fait_deces GROUP BY annee ORDER BY annee;
SELECT COUNT(*) AS total_baseline FROM fait_deces_baseline;
