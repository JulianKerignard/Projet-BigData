# Changelog

Toutes les évolutions notables du projet **CHU Big Data** (entrepôt de données décisionnel santé).
Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/) · versionnage [SemVer](https://semver.org/lang/fr/).

## [1.1.1] — 2026-06-07

Cohérence documentaire (hygiène livrable — aucun changement de code/runtime).

- Purge des blocs **PySpark** résiduels de la doc ETL hospitalisation (→ HiveQL) et des références aux scripts supprimés ; stack « HiveQL sans Spark » désormais cohérente partout.
- Suppression du **doublon** `Livrable 1 Groupe -.docx` (seule la v2 corrigée est conservée).
- `README` aligné sur la réalité : dashboards **HTML/ECharts batch** (au lieu de « Power BI / real-time »), arbre de structure complété (`sql/dashboard/`).

## [1.1.0] — 2026-06-06

Améliorations de performance, nettoyage et cohérence (aucun changement fonctionnel de l'entrepôt).

### Performance
- Data-prep décès via **DuckDB en streaming** : pic RAM **÷4** (~1,3 Go → ~320 Mo), ~1 s, sortie **déterministe**.
- Benchmark data-prep (DuckDB streaming vs matérialisé vs awk) : runner + graphe + CSV.

### Nettoyage
- Suppression de **~1 390 lignes de code PySpark mort** (non référencé, contredisait le choix « HiveQL sans Spark »).

### Documentation
- Livrable 2 recalé sur le repo : **disclosure des benchmarks synthétiques** (décès/satisfaction), correction de l'année B7 (2019), note `dim_patient`.
- `CHANGELOG.md` + structure `README.md`.

## [1.0.0] — 2026-06-05

Première version complète : les 3 livrables sont couverts. Stack **HDFS + Hive 2.3.2 + Parquet** (entrepôt), **Python/SQL** (jobs et outils).

### Livrable 1 — Référentiel de données
- Architecture **médaillon** Bronze / Silver / Gold.
- Modèle en **constellation** : 4 faits (Consultation, Hospitalisation, Satisfaction, Décès) + 6 dimensions conformes (Temps, Patient, Diagnostic, Établissement, Professionnel, Géographie) — MCD (`docs/mcd_constellation.png`).
- Description des jobs ETL par source ; **pseudonymisation SHA-256** + minimisation (RGPD).
- Rapport Livrable 1 (`Livrable 1 Groupe - v2 corrigé.docx`) recalé sur l'énoncé (8 besoins) et sur le DDL réel.

### Livrable 2 — Modèle physique & optimisation
- DDL Gold (faits + dimensions) en **Parquet**, **partition par année** + **bucketing**.
- Cleaning **HiveQL** des 4 sources (Bronze → Silver → Gold) : tables de rejets, contrôles qualité, anonymisation.
- Alimentation des dimensions (Temps, Géographie).
- **Benchmarks partition/bucket** des 4 faits — SQL + runners + graphes + I/O mesuré (`hdfs du` / EXPLAIN) :
  - Consultations (B2/B6), Hospitalisations (B3/B4/B5), Décès (B7), Satisfaction (B8).

### Livrable 3 — Restitution
- 4 **dashboards décisionnels interactifs** façon Power BI (KPI à delta/sparkline, cross-filter, cartes choroplèthes France) couvrant B2–B8.
- **Reproductibles offline** (données agrégées figées dans `viz/`).

### Outils & performance
- Data-prep décès via **DuckDB** (`extract_deces.py`, profiling) : ~5 min → ~1 s, parsing quote-aware, sortie **déterministe**.
- Profiling `awk` 1-passe en **fallback zéro-dépendance** (~45 s).
- Stack Hive locale **dockerisée** (`docker/docker-compose.hive.yml`).

### Notes
- **B1** (consultation par établissement) : non applicable — la source consultations ne porte pas d'identifiant d'établissement.
- Entrepôt 100 % **Hive** ; DuckDB n'intervient que sur le data-prep local (hors entrepôt).

[1.1.1]: https://github.com/JulianKerignard/Projet-BigData/releases/tag/v1.1.1
[1.1.0]: https://github.com/JulianKerignard/Projet-BigData/releases/tag/v1.1.0
[1.0.0]: https://github.com/JulianKerignard/Projet-BigData/releases/tag/v1.0.0
