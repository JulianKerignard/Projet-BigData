-- =============================================================================
-- [P4] Benchmark L2 — Requêtes de comparaison perf
-- Tâche ClickUp : 869dfg1ne
--
-- 4 requêtes types qui mesurent l'effet du partitionnement et du bucketing.
-- À exécuter via scripts/benchmark/run_benchmark_deces.sh qui capture les temps.
--
-- À PROPOS DES MESURES :
--   - Hive 2.x renvoie le temps total en bas de stdout ("Time taken: X.Y sec").
--   - Pour comparer équitablement on lance chaque requête après FLUSH du cache
--     côté HDFS (datanode buffer). En dev local le warm cache fausse les comparaisons
--     successives — d'où plusieurs runs et la moyenne.
--
-- Le partition pruning et le bucket map join sont mis en évidence par EXPLAIN.
-- =============================================================================
USE chu_entrepot;

-- =============================================================================
-- Q1 — Filtre par année (test PARTITION PRUNING)
--   Optimisée  : lit 1 sous-dossier  /chu/gold/fait_deces/annee=2019/
--   Baseline   : full scan + filtre WHERE
-- =============================================================================

-- Q1.opt : sur table partitionnée
SELECT SUM(nb_deces) AS total_2019_opt FROM fait_deces WHERE annee = 2019;

-- Q1.base : sur table baseline (full scan)
SELECT SUM(nb_deces) AS total_2019_base FROM fait_deces_baseline WHERE annee = 2019;

-- =============================================================================
-- Q2 — Agrégation par région (KPI 8 — test bucket + colonnaire)
--   Optimisée : 1 reducer par bucket (8 reducers), pré-distribué sur geo_id
--   Baseline  : shuffle complet sur geo_id
-- =============================================================================

SELECT geo_id, SUM(nb_deces) AS nb FROM fait_deces
WHERE annee = 2019 GROUP BY geo_id ORDER BY nb DESC LIMIT 5;

SELECT geo_id, SUM(nb_deces) AS nb FROM fait_deces_baseline
WHERE annee = 2019 GROUP BY geo_id ORDER BY nb DESC LIMIT 5;

-- =============================================================================
-- Q3 — KPI 8 finalisé avec JOIN dim_geographie (test bucket map join)
-- =============================================================================

SELECT g.region, SUM(f.nb_deces) AS nb_deces
FROM fait_deces f
JOIN dim_geographie g ON g.geo_id = f.geo_id
WHERE f.annee = 2019
GROUP BY g.region ORDER BY nb_deces DESC LIMIT 5;

SELECT g.region, SUM(f.nb_deces) AS nb_deces
FROM fait_deces_baseline f
JOIN dim_geographie g ON g.geo_id = f.geo_id
WHERE f.annee = 2019
GROUP BY g.region ORDER BY nb_deces DESC LIMIT 5;

-- =============================================================================
-- Q4 — Croisement sexe × tranche d'âge sur 2019 (agrégation multi-axes)
-- =============================================================================

SELECT sexe, tranche_age, SUM(nb_deces) AS n FROM fait_deces
WHERE annee = 2019 GROUP BY sexe, tranche_age ORDER BY sexe, n DESC;

SELECT sexe, tranche_age, SUM(nb_deces) AS n FROM fait_deces_baseline
WHERE annee = 2019 GROUP BY sexe, tranche_age ORDER BY sexe, n DESC;

-- =============================================================================
-- Plans d'exécution (EXPLAIN) — preuves de partition pruning + bucketing
-- =============================================================================

EXPLAIN SELECT SUM(nb_deces) FROM fait_deces WHERE annee = 2019;
EXPLAIN SELECT SUM(nb_deces) FROM fait_deces_baseline WHERE annee = 2019;
