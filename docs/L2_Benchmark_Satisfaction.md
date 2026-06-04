# Benchmark Satisfaction (Livrable 2)

> **Tâche** : `[P3] Benchmark Satisfaction avant/après + graphes` (869dfg1gt)
> **Auteur** : Matthieu (P3) · réconcilié sur le modèle canonique (geo_id, schéma 5 colonnes).
> **Livrables** : `scripts/benchmark/satisfaction_results.csv`, `scripts/benchmark/satisfaction_graph.png`,
> `sql/benchmark/satisfaction_benchmark.sql`, cette section.

## 1. Objectif

Quantifier le gain de performance apporté par le **partitionnement** puis le **bucketing** sur
les requêtes de l'axe KPI B8, en comparant trois layouts physiques du fait Satisfaction.

## 2. Protocole

Toutes les tables dérivent du fait **canonique** `chu_entrepot.fait_satisfaction`
(5 colonnes : `satisfaction_key, date_id, etab_id, geo_id, note_satisfaction`, **déjà partitionné**
par `annee`). Comme la canonique est déjà partitionnée, V1 est une **vraie baseline « plate »**
fabriquée pour la mesure (tables `bench_*` jetables, hors modèle Gold).

| Version | Table | Optimisation |
|---|---|---|
| **V1** | `bench_satisfaction_flat` | aucune (ni partition ni bucket) — **référence** |
| **V2** | `fait_satisfaction` (canonique) | partition sur `annee` |
| **V3** | `bench_satisfaction_pb` | partition `annee` + bucket 8 sur `etab_id` |

Deux requêtes représentatives (script : `sql/benchmark/satisfaction_benchmark.sql`) :

- **R1** — satisfaction moyenne **par région sur 2020** (filtre `annee = 2020`, jointure
  `dim_etablissement`) → exerce le **partition pruning**.
- **R2** — satisfaction moyenne **par région, toutes campagnes** (pas de filtre `annee`) → pas de
  pruning possible, scan de toutes les partitions. *(Grain annuel `YYYY0101` : on agrège sur l'axe
  région `geo_id`, jamais « par mois ».)*

Chaque cas est exécuté **3 fois**, cache de résultats désactivé
(`hive.query.results.cache.enabled=false`) ; on retient la **moyenne**. Soit
**2 requêtes × 3 versions = 6 cas**, 18 exécutions.

## 3. Exécution

```bash
# 1. créer les tables bench + lancer les requêtes, journaliser les "Time taken"
hive -f sql/benchmark/satisfaction_benchmark.sql 2>&1 | tee scripts/benchmark/run_$(date +%F).log

# 2. reporter les 3 temps de chaque cas dans scripts/benchmark/satisfaction_results.csv
#    (colonnes run1_s, run2_s, run3_s)

# 3. calculer moyennes + gains et générer le graphe
python3 scripts/benchmark/generate_graph.py
```

## 4. Résultats

> ⚠️ **À compléter avec les mesures réelles** issues du cluster Hive du projet.
> Le tableau ci-dessous est un **gabarit** ; `generate_graph.py` recalcule `moyenne_s` et
> `gain_pct_vs_v1` à partir des 3 runs saisis dans le CSV (et ne plante pas si le CSV est vide).

| Requête | V1 brute (s) | V2 partition (s) | V3 part+bucket (s) | Gain V3 vs V1 |
|---|---:|---:|---:|---:|
| R1 — satisfaction / région 2020 | _à mesurer_ | _à mesurer_ | _à mesurer_ | _% à calculer_ |
| R2 — satisfaction / région (toutes) | _à mesurer_ | _à mesurer_ | _à mesurer_ | _% à calculer_ |

Graphe comparatif : `scripts/benchmark/satisfaction_graph.png`.

## 5. Analyse attendue

- **V2 (partition)** : le filtre `WHERE annee = 2020` (R1) déclenche le *partition pruning* — Hive
  ne lit que le répertoire `annee=2020` au lieu de toute la table. Gain net dès que plusieurs
  campagnes sont chargées (visible sur le `TableScan` de l'`EXPLAIN`, §4 du script). Sur **R2**
  (pas de filtre `annee`), aucun pruning : le scan reste complet.
- **V3 (bucket sur `etab_id`)** : bénéfice attendu sur **R1**, qui joint `dim_etablissement`.
  ⚠️ Le **bucket map join complet** nécessite que `dim_etablissement` soit elle aussi bucketée sur
  `etab_id` (non fait actuellement) ; sans cela le gain du bucket reste marginal et le mécanisme
  démontrable principal est le **partition pruning**.
- **Volumétrie** : la source Satisfaction est petite (~1 000 établissements/campagne, ~16 Mo). Les
  écarts en valeur absolue restent **dans le bruit de mesure** ; le benchmark démontre surtout le
  **mécanisme** d'optimisation, transposable aux faits volumineux (décès, 1,9 Go).

## 6. Definition of Done

- [x] 2 requêtes × 3 versions = 6 cas définis (script SQL, schéma 5 colonnes canonique)
- [x] V1 = vraie baseline non partitionnée (la canonique étant déjà partitionnée)
- [x] Protocole 3 mesures / moyenne documenté ; cache désactivé
- [x] Gabarit CSV + script de génération du graphe (robuste, sans crash si CSV vide)
- [ ] **Mesures réelles à saisir** sur le cluster Hive, puis graphe régénéré
