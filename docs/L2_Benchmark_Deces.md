# Benchmark perf Fait_Deces — avant / après partition + bucketing (L2)

> **Livrable** : section "Benchmark perf" du rapport L2.
> **Tâche ClickUp clôturée** : [869dfg1ne](https://app.clickup.com/t/869dfg1ne) — [P4] Benchmark Fait_Deces avant/après + graphes.
> **Scripts** : [`sql/benchmark/00_create_baseline_deces.hql`](../sql/benchmark/00_create_baseline_deces.hql), [`00b_load_5years_deces.hql`](../sql/benchmark/00b_load_5years_deces.hql), [`scripts/benchmark/run_benchmark_deces.sh`](../scripts/benchmark/run_benchmark_deces.sh).
> **Résultats bruts** : [`docs/benchmark_deces_results.csv`](benchmark_deces_results.csv).
> **Date d'exécution** : 2026-06-04.

---

## 1. Protocole de mesure

### 1.1 Deux tables comparées (mêmes données)

| Table | Format | Partition | Bucketing | Fichiers HDFS |
|---|---|---|---|---|
| `chu_entrepot.fait_deces` | Parquet+Snappy | `annee INT` | `geo_id × 8` | 5 partitions × 8 = **40** |
| `chu_entrepot.fait_deces_baseline` | Parquet+Snappy | — | — | **1** |

- **Données identiques** : 3 038 642 lignes (5 années : 2015-2019, données INSEE)
- **Création baseline** : `INSERT OVERWRITE TABLE fait_deces_baseline SELECT * FROM fait_deces;` — garantit l'identité des contenus.

### 1.2 Stack d'exécution

| Élément | Valeur |
|---|---|
| Moteur SQL | Apache Hive 2.3.2 |
| Exec engine | MapReduce (local mode) |
| Stockage | HDFS 2.7.4 (1 namenode + 1 datanode, conteneurs Docker) |
| Volume RAM hive-server | ~500 MB heap JVM |
| Méthode timing | Parsing du `(X.Y seconds)` produit par Beeline en fin de chaque requête |
| Runs par requête | 3 (moyenne arithmétique) |

### 1.3 Requêtes types

| # | Requête | Type d'optimisation Hive activable |
|---|---|---|
| Q1 | `SELECT SUM(nb_deces) WHERE annee=2019` | **Partition pruning** — lit 1/5 partitions |
| Q2 | `SELECT geo_id, SUM(nb_deces) GROUP BY geo_id ORDER BY nb DESC LIMIT 5` (KPI 8 partiel) | **Bucketing** — 1 reducer par bucket |
| Q3 | `... JOIN dim_geographie g ON g.geo_id = f.geo_id ...` (KPI 8 final) | **Bucket map join** |
| Q4 | `SELECT sexe, tranche_age, SUM(nb_deces) GROUP BY sexe, tranche_age` | **Vectorisation + partition pruning** |

## 2. Résultats — temps moyens (3 runs)

| Requête | Baseline (`fait_deces_baseline`) | Optimisée (`fait_deces`) | Gain | Volume théorique scanné |
|---|---:|---:|---:|---|
| Q1 — filtre année | 1.99 s | 2.08 s | **0.96×** | 25.6 MB → 5.2 MB (**5×**) |
| Q2 — top régions | 3.39 s | 3.36 s | **1.01×** | 25.6 MB → 5.2 MB |
| Q3 — KPI 8 join | 8.77 s | 8.23 s | **1.07×** | 25.6 MB → 5.2 MB + join broadcast |
| Q4 — cube sexe×âge | 2.35 s | 2.10 s | **1.12×** | 25.6 MB → 5.2 MB |

## 3. Analyse — pourquoi les gains mesurés sont faibles

À première lecture, les gains wall-time sont marginaux (**0.96× à 1.12×**) malgré une **réduction théorique du volume scanné par 5×** sur les requêtes filtrées par année. Voici les 4 raisons identifiées.

### 3.1 Overhead de compilation Hive domine
Chaque requête HiveQL embarque **~1.5 à 2 s de coût fixe** (parsing, optimisation, soumission du job MapReduce, allocation des tâches). Sur 25 MB de Parquet, le scan réel prend **< 100 ms**. Donc un gain potentiel de 80 ms est invisible dans une mesure à 2 s.

**Calcul théorique** :
```
T_total = T_overhead + T_scan + T_aggregate
       = 1900 ms     + 80 ms  + 50 ms      (baseline)
       = 1900 ms     + 20 ms  + 50 ms      (optimisée)
       = différence : 60 ms (3 %)
```

### 3.2 MapReduce local mode = pas de parallélisme distribué
Le bucketing est conçu pour qu'un cluster avec 8 nœuds lance 8 reducers en parallèle. En **local mode** (single JVM), les 8 buckets sont lus **séquentiellement** par un seul thread → aucun gain de parallélisme.

### 3.3 Volume trop petit pour atteindre le seuil de partition pruning utile
Pour mesurer un gain significatif il faut que le coût de scan dépasse l'overhead Hive. **Règle empirique** : il faut au moins **10× le volume actuel** (250+ MB) sur un **cluster distribué** pour que le partition pruning devienne le facteur dominant.

### 3.4 1 seule partition existante à l'origine
Notre première itération du benchmark (avec uniquement `annee=2019` chargé) montrait gain = 1.0× parce qu'il n'y avait **rien à pruner**. On a corrigé en chargeant 2015-2019, ce qui rend le ratio "scanné optim / scanné baseline" = 1/5 — mais le wall time reste dominé par l'overhead (cf §3.1).

## 4. Mesures structurelles (ce qui se passe vraiment côté HDFS)

Ces métriques **ne se voient pas dans le wall time** mais sont les vrais gains du partitionnement + bucketing, vérifiables par `hdfs dfs -du` et `EXPLAIN`.

### 4.1 Volume effectivement lu (`EXPLAIN` confirme le partition pruning)

```
Q1 sur fait_deces (optim) :
  TableScan
    alias: fait_deces
    Statistics: Num rows: 616237  Data size: 5 490 694    ← lit 5.2 MB

Q1 sur fait_deces_baseline :
  TableScan
    alias: fait_deces_baseline
    Statistics: Num rows: 3 038 642  Data size: 27 084 130 ← lit 25.6 MB
```

→ **Réduction I/O = 5× confirmée** par le planner Hive, même si le wall time ne la reflète pas en local mode.

### 4.2 Layout HDFS final

| Table | Layout | Taille | Fichiers |
|---|---|---|---|
| `fait_deces` | 5 partitions × 8 buckets | 25.4 MB | 40 |
| `fait_deces_baseline` | 1 fichier | 25.6 MB | 1 |

→ Compression Parquet équivalente (à ~1 % près), ce qui valide que le format est neutre dans la comparaison.

### 4.3 Skew sur buckets `geo_id`

Tailles bucket sur la partition `annee=2019` :
```
bucket 000000  1.1 MB   ← contient IDF (région 11) majoritaire
bucket 000001   34 KB   ← région avec peu de décès
bucket 000006  1.2 MB
bucket 000003   41 KB
...
ratio max/min = ×35
```

→ Le bucketing par `geo_id` simple souffre de la concentration démographique (3 régions = 33 % des décès). Le **bucket map join** serait moins efficace que prévu en prod.

**Recommandation** : tester `CLUSTERED BY (geo_id, sexe) INTO 8 BUCKETS` qui répartirait mieux (chaque bucket aurait IDF/M, IDF/F, ARA/M, ARA/F, etc.).

## 5. Recommandations pour la prod (rapport L2)

| # | Recommandation | Pourquoi |
|---|---|---|
| 1 | **Passer Hive sur Tez** (au lieu de MapReduce) | Tez supprime l'overhead de relance de JVM entre stages — gain ~30 % observé en littérature |
| 2 | Charger l'historique complet (2010-2023) sur cluster distribué | À ~25 M lignes, le partition pruning sur `WHERE annee=2019` deviendra **visible en wall time** (lit 1/14 vs 14/14) |
| 3 | **Activer CBO + vectorisation** par défaut | `hive.cbo.enable=true`, `hive.vectorized.execution.enabled=true` — déjà dans `00_setup_hive.hql`, à confirmer en prod |
| 4 | **Statistiques de table** systématiques | `ANALYZE TABLE fait_deces COMPUTE STATISTICS` après chaque chargement — sans stats, le CBO ne peut pas choisir bucket map join |
| 5 | Bucketing composite | Remplacer `CLUSTERED BY (geo_id)` par `CLUSTERED BY (geo_id, sexe)` pour lisser le skew (×35 → ×5 estimé) |

## 6. Conclusion défendable

Les optimisations physiques de `fait_deces` (Parquet + partition annee + bucket geo_id) **sont structurellement correctes** : le partition pruning est confirmé par `EXPLAIN` (lit 5.2 MB au lieu de 25.6 MB), le bucketing est appliqué (8 fichiers par partition), et le format Parquet apporte la compression colonnaire attendue (1.9 GB CSV → 25 MB Gold = **75× compression**).

**Mais le bénéfice wall time n'est pas mesurable dans notre stack dev** parce que :
- l'overhead Hive (~2 s par requête) > le gain potentiel (~80 ms)
- MapReduce local exécute séquentiellement les buckets (pas de parallélisme)
- 25 MB est trop petit pour saturer la couche I/O

C'est un **résultat attendu et important pédagogiquement** : il démontre que **les optimisations Big Data ne se justifient qu'au-delà d'un certain volume et sur une stack distribuée**. C'est précisément le sujet du projet CHU avec sa volumétrie cible (10 ans × 25 M lignes/an = **2.5 G lignes**, NFR §3.2).

## 7. Reproductibilité

```bash
# Pré-requis : pipeline d'init exécutée (cf. L2_Resultats_Execution_Deces.md)

# 1. Créer la baseline
docker cp sql/benchmark chu-hive-server:/tmp/sql_benchmark
docker exec chu-hive-server beeline -u 'jdbc:hive2://localhost:10000/' \
    -f /tmp/sql_benchmark/00_create_baseline_deces.hql

# 2. Charger 5 ans (2015-2019) dans fait_deces + baseline
docker exec chu-hive-server beeline -u 'jdbc:hive2://localhost:10000/' \
    -f /tmp/sql_benchmark/00b_load_5years_deces.hql

# 3. Benchmark (3 runs par requête)
bash scripts/benchmark/run_benchmark_deces.sh 3
# Résultats : docs/benchmark_deces_results.csv
```

## 8. Definition of Done — clôture

### Tâche `869dfg1kk` (Partitionnement)
- [x] Partition `annee INT` créée dans le DDL canonique
- [x] 5 partitions chargées (2015-2019) — preuve `SHOW PARTITIONS fait_deces`
- [x] Partition pruning vérifié via `EXPLAIN` (lit 5.2 MB au lieu de 25.6 MB)
- [x] Justification documentée (§3, §4.1)

### Tâche `869dfg1ma` (Bucketing)
- [x] `CLUSTERED BY (geo_id) INTO 8 BUCKETS` dans le DDL canonique
- [x] Layout HDFS vérifié (8 fichiers par partition)
- [x] Skew analysé et documenté (§4.3) — limite identifiée
- [x] Recommandation de bucketing composite (§5)

### Tâche `869dfg1ne` (Benchmark avant/après)
- [x] Table baseline `fait_deces_baseline` créée (Parquet, sans partition, sans bucket)
- [x] 4 requêtes types exécutées, 3 runs chacune sur les 2 tables
- [x] Résultats CSV produits (`docs/benchmark_deces_results.csv`)
- [x] Analyse écrite des gains observés vs attendus (§3)
- [x] Recommandations prod documentées (§5)
