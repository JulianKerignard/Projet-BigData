-- =============================================================================
-- [P4] Benchmark L2 Décès — requêtes de comparaison perf (B7 = décès par région)
-- Tâche ClickUp : 869dfg1ne
--
-- Compare 4 requêtes types sur deux tables JETABLES (cf. 00_create_bench_deces.hql),
-- SANS jamais toucher la Gold canonique fait_deces :
--   bench_deces_pb    = Parquet + partition annee + bucket 8 geo_id  (optimisée)
--   bench_deces_flat  = Parquet, ni partition ni bucket              (baseline)
--
-- MESURE : Beeline imprime "(X.Y seconds)" en fin de chaque requête (parsé par
-- scripts/benchmark/run_benchmark_deces.sh). En dev local le cache est CHAUD entre
-- runs successifs -> seul le 1er run est "à froid" ; on retient la médiane et on
-- documente la limite (cf. docs/L2_Benchmark_Deces.md §3). Le gain réel (I/O) se lit
-- via les EXPLAIN ci-dessous, pas dans le wall time.
-- =============================================================================
USE chu_entrepot;

-- =============================================================================
-- Q1 — Filtre par année (test PARTITION PRUNING) : opt lit 1/5, baseline full scan
-- =============================================================================
SELECT SUM(nb_deces) AS total_2019_opt  FROM bench_deces_pb   WHERE annee = 2019;
SELECT SUM(nb_deces) AS total_2019_base FROM bench_deces_flat WHERE annee = 2019;

-- =============================================================================
-- Q2 — Agrégation par région (test bucket + colonnaire)
-- =============================================================================
SELECT geo_id, SUM(nb_deces) AS nb FROM bench_deces_pb
WHERE annee = 2019 GROUP BY geo_id ORDER BY nb DESC LIMIT 5;

SELECT geo_id, SUM(nb_deces) AS nb FROM bench_deces_flat
WHERE annee = 2019 GROUP BY geo_id ORDER BY nb DESC LIMIT 5;

-- =============================================================================
-- Q3 — B7 finalisé avec JOIN dim_geographie (test bucket map join)
-- =============================================================================
SELECT g.region, SUM(f.nb_deces) AS nb_deces
FROM bench_deces_pb f JOIN dim_geographie g ON g.geo_id = f.geo_id
WHERE f.annee = 2019 GROUP BY g.region ORDER BY nb_deces DESC LIMIT 5;

SELECT g.region, SUM(f.nb_deces) AS nb_deces
FROM bench_deces_flat f JOIN dim_geographie g ON g.geo_id = f.geo_id
WHERE f.annee = 2019 GROUP BY g.region ORDER BY nb_deces DESC LIMIT 5;

-- =============================================================================
-- Q4 — Croisement sexe × tranche d'âge sur 2019 (agrégation multi-axes)
-- =============================================================================
SELECT sexe, tranche_age, SUM(nb_deces) AS n FROM bench_deces_pb
WHERE annee = 2019 GROUP BY sexe, tranche_age ORDER BY sexe, n DESC;

SELECT sexe, tranche_age, SUM(nb_deces) AS n FROM bench_deces_flat
WHERE annee = 2019 GROUP BY sexe, tranche_age ORDER BY sexe, n DESC;

-- =============================================================================
-- Plans d'exécution (EXPLAIN) — preuve du partition pruning (I/O lu 1/5 vs 5/5)
-- =============================================================================
EXPLAIN SELECT SUM(nb_deces) FROM bench_deces_pb   WHERE annee = 2019;
EXPLAIN SELECT SUM(nb_deces) FROM bench_deces_flat WHERE annee = 2019;
