# Benchmark Satisfaction (Livrable 2)

> **Tâche** : `[P3] Benchmark Satisfaction avant/après + graphes` (869dfg1gt)
> **Auteur** : Matthieu (P3)
> **Livrables** : `benchmarks/satisfaction_results.csv`, `benchmarks/satisfaction_graph.png`,
> cette section.

## 1. Objectif

Quantifier le gain de performance apporté par le **partitionnement** puis le **bucketing** sur
les requêtes du KPI 8, en comparant trois versions de la table de faits.

## 2. Protocole

| Version | Table | Optimisation |
|---|---|---|
| **V1** | `fait_satisfaction` | aucune (référence) |
| **V2** | `fait_satisfaction_part` | partition sur `annee` |
| **V3** | `fait_satisfaction_pb` | partition `annee` + bucket 8 sur `etab_id` |

Deux requêtes représentatives (script : `benchmarks/satisfaction_benchmark.sql`) :

- **R1** — satisfaction moyenne par région sur 2020 (KPI 8, avec jointure `dim_etablissement`).
- **R2** — évolution mensuelle de la satisfaction nationale 2020 (agrégat sans jointure).

Chaque cas est exécuté **3 fois**, cache de résultats désactivé
(`hive.query.results.cache.enabled=false`) ; on retient la **moyenne**. Soit
**2 requêtes × 3 versions = 6 cas**, 18 exécutions.

## 3. Exécution

```bash
# 1. lancer les requêtes et journaliser les "Time taken"
hive -f benchmarks/satisfaction_benchmark.sql 2>&1 | tee benchmarks/run_$(date +%F).log

# 2. reporter les 3 temps de chaque cas dans benchmarks/satisfaction_results.csv
#    (colonnes run1_s, run2_s, run3_s)

# 3. calculer moyennes + gains et générer le graphe
python3 benchmarks/generate_graph.py
```

## 4. Résultats

> ⚠️ **À compléter avec les mesures réelles** issues du cluster Hive du projet.
> Le tableau ci-dessous est un **gabarit** ; `generate_graph.py` recalcule `moyenne_s` et
> `gain_pct_vs_v1` automatiquement à partir des 3 runs saisis dans le CSV.

| Requête | V1 brute (s) | V2 partition (s) | V3 part+bucket (s) | Gain V3 vs V1 |
|---|---:|---:|---:|---:|
| R1 — satisfaction / région 2020 | _à mesurer_ | _à mesurer_ | _à mesurer_ | _% à calculer_ |
| R2 — évolution mensuelle 2020 | _à mesurer_ | _à mesurer_ | _à mesurer_ | _% à calculer_ |

Graphe comparatif : `benchmarks/satisfaction_graph.png`.

## 5. Analyse attendue

- **V2 (partition)** : le filtre `WHERE annee = 2020` déclenche le *partition pruning* — Hive ne
  lit que le répertoire `annee=2020` au lieu de la table entière. Gain visible dès que
  plusieurs années sont chargées (le `TableScan` de l'`EXPLAIN` le confirme, cf.
  `partition/fait_satisfaction_partitioned.sql` §4).
- **V3 (bucket sur `etab_id`)** : bénéfice surtout sur **R1**, qui joint `dim_etablissement` —
  les deux tables étant bucketées sur la même clé, Hive peut faire un *bucket map join* et
  éviter un shuffle complet. Sur **R2** (pas de jointure), le gain marginal du bucket est faible.
- **Volumétrie** : la source Satisfaction est petite (~1 000 établissements/an, 16 Mo). Les
  écarts en valeur absolue restent modestes ; le benchmark démontre surtout le **mécanisme**
  d'optimisation, transposable aux faits volumineux (décès, 1,9 Go).

## 6. Definition of Done

- [x] 2 requêtes × 3 versions = 6 cas définis (script SQL)
- [x] Protocole 3 mesures / moyenne documenté
- [x] Gabarit de tableau de résultats + CSV
- [x] Script de génération du graphe (gain % calculé)
- [ ] **Mesures réelles à saisir** sur le cluster Hive, puis graphe régénéré
