# CHU Big Data - Data Warehouse Project

Healthcare data warehouse solution for Cloud Healthcare Unit (CHU) group.

## Project Overview

This project implements a scalable, secure data warehouse for healthcare data analysis, enabling practitioners and administrators to access actionable insights from medical data.

### Key Objectives
- Extract and store data from multiple healthcare sources
- Implement secure, GDPR-compliant data warehouse
- Enable multi-dimensional analysis for clinical and administrative users
- Optimize performance for real-time dashboarding

## Project Structure

```
├── docs/            # Rapports & documentation (L1, L2, MCD, sécurité/RGPD)
├── sql/             # Jobs HiveQL
│   ├── ddl/             # Bases, dimensions conformes, tables de faits (Parquet)
│   ├── cleaning/        # Nettoyage Bronze→Silver→Gold + anonymisation
│   ├── benchmark/       # Requêtes de performance (partition / bucket)
│   └── profiling/       # Profiling qualité
├── scripts/         # Outils
│   ├── benchmark/       # Runners de benchmark + génération des graphes
│   ├── profiling/       # Profiling décès (DuckDB rapide / awk fallback)
│   ├── viz/             # Générateurs des dashboards (Python → HTML)
│   └── ref/             # Référentiels (département → région)
├── viz/             # Dashboards HTML interactifs + données agrégées
├── docker/          # Stack Hive locale (Hive 2.3.2 + HDFS, images bde2020)
├── CHANGELOG.md
└── README.md
```

> Note : les données brutes (`DATA 2024/`) ne sont pas versionnées (volumineuses, sensibles).

## Stack & prérequis

- **Entrepôt** : HDFS + Hive 2.3.2 + Parquet (Snappy). **Jobs** : HiveQL + Python.
- Prérequis : Docker (stack Hive), Python 3, et `duckdb` (data-prep décès — `brew install duckdb`).

## Data Sources

- PostgreSQL database (patient care management)
- CSV files (healthcare facilities)
- Flat files (patient satisfaction surveys)
- Flat files (French death registry)

## Team

- Chloé
- Julian Kerignard
- Matthieu
- Maxime

## Deliverables

1. **L1 - Data Referential** (Conceptual model + ETL jobs)
2. **L2 - Physical Model & Optimization** (Scripts + performance metrics)
3. **L3 - Results & Storytelling** (Presentation + Power BI dashboard)

## Getting Started

See `docs/` for detailed documentation on architecture, security, and implementation.

## License

Internal Use Only
