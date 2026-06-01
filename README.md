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
├── docs/                    # Documentation
│   ├── Securite_Anonymisation_NFR.md
│   └── ...
├── scripts/                 # ETL & deployment scripts
├── sql/                     # Database schemas & queries
├── config/                  # Configuration files
└── README.md
```

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
