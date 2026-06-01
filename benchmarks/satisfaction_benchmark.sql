-- =============================================================================
-- [P3] Benchmark Satisfaction (tâche 869dfg1gt - Livrable 2)
-- 2 requêtes × 3 configurations = 6 cas ; 3 exécutions par cas, on garde la moyenne.
--
-- Les 3 configurations (tables) :
--   V1 = fait_satisfaction       (brute, ni partition ni bucket)
--   V2 = fait_satisfaction_part  (partitionnée sur annee)
--   V3 = fait_satisfaction_pb    (partitionnée + bucketée 8 sur etab_id)
--
-- Mode opératoire : exécuter ce script avec
--   hive -f benchmarks/satisfaction_benchmark.sql 2>&1 | tee benchmarks/run_$(date +%F).log
-- puis relever, pour chaque requête, le "Time taken" affiché par Hive et le reporter
-- dans benchmarks/satisfaction_results.csv (3 mesures -> moyenne).
-- =============================================================================

USE chu_entrepot;
SET hive.cli.print.header = true;

-- Désactiver le cache de résultats pour mesurer le coût réel à chaque exécution
SET hive.query.results.cache.enabled = false;

-- =============================================================================
-- REQUÊTE 1 — Satisfaction moyenne par région sur 2020 (KPI 8)
-- =============================================================================

-- R1 / V1 (brute)
SELECT e.region, AVG(f.note_satisfaction) AS satisf_moy
FROM fait_satisfaction f JOIN dim_etablissement e USING (etab_id)
WHERE CAST(SUBSTR(CAST(date_id AS STRING),1,4) AS INT) = 2020
GROUP BY e.region;

-- R1 / V2 (partitionnée)
SELECT e.region, AVG(f.note_satisfaction) AS satisf_moy
FROM fait_satisfaction_part f JOIN dim_etablissement e USING (etab_id)
WHERE f.annee = 2020
GROUP BY e.region;

-- R1 / V3 (partitionnée + bucketée)
SET hive.optimize.bucketmapjoin = true;
SELECT e.region, AVG(f.note_satisfaction) AS satisf_moy
FROM fait_satisfaction_pb f JOIN dim_etablissement e USING (etab_id)
WHERE f.annee = 2020
GROUP BY e.region;

-- =============================================================================
-- REQUÊTE 2 — Évolution mensuelle de la satisfaction nationale 2020
-- =============================================================================

-- R2 / V1 (brute)
SELECT CAST(SUBSTR(CAST(date_id AS STRING),5,2) AS INT) AS mois, AVG(note_satisfaction)
FROM fait_satisfaction
WHERE CAST(SUBSTR(CAST(date_id AS STRING),1,4) AS INT) = 2020
GROUP BY CAST(SUBSTR(CAST(date_id AS STRING),5,2) AS INT);

-- R2 / V2 (partitionnée)
SELECT CAST(SUBSTR(CAST(date_id AS STRING),5,2) AS INT) AS mois, AVG(note_satisfaction)
FROM fait_satisfaction_part
WHERE annee = 2020
GROUP BY CAST(SUBSTR(CAST(date_id AS STRING),5,2) AS INT);

-- R2 / V3 (partitionnée + bucketée)
SELECT CAST(SUBSTR(CAST(date_id AS STRING),5,2) AS INT) AS mois, AVG(note_satisfaction)
FROM fait_satisfaction_pb
WHERE annee = 2020
GROUP BY CAST(SUBSTR(CAST(date_id AS STRING),5,2) AS INT);
