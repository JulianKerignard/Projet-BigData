# Job ETL Décès (P4)

> **Livrable** : section "Job ETL Décès" du rapport L1.
> **Tâche ClickUp** : [869dfg13p](https://app.clickup.com/t/869dfg13p) — [P4] Description job ETL Décès.
> **Prérequis** : [Modélisation Fait_Deces](modelisation_fait_deces.md).
> **Cible** : alimenter `Fait_Deces` à partir du fichier INSEE pour répondre au KPI 8.

---

## 1. Source — fichier INSEE des décès

| Élément | Valeur observée |
|---|---|
| Nom du fichier | `deces.csv` |
| Format | **CSV** (séparateur `,`, guillemets sur les champs textuels avec espaces) |
| Encodage | **UTF-8** (vérifié : `file deces.csv` → *CSV text*) |
| Header | Oui, en première ligne |
| Volumétrie totale | **~25 millions** de lignes (historique complet INSEE) |
| Volumétrie 2019 | **616 257** lignes (vérifié sur fichier réel) |
| Taille brute | ~2 Go (1 999 899 438 octets) |
| Distribution | Mise à disposition par l'INSEE (open data) — récupération initiale via FTP/HTTP |

### Schéma du fichier source

| Colonne | Type | Exemple | Notes |
|---|---|---|---|
| `nom` | string | `LANGLET` | Donnée personnelle |
| `prenom` | string | `ANTOINETTE GERMAINE` | Donnée personnelle |
| `sexe` | int | `1` (H) / `2` (F) | Code INSEE |
| `date_naissance` | date `YYYY-MM-DD` | `1903-11-11` | |
| `code_lieu_naissance` | string(5) | `02383` | Code INSEE commune |
| `lieu_naissance` | string | `HOMBLIERES` | |
| `pays_naissance` | string | `""` (vide si France) | |
| `date_deces` | date `YYYY-MM-DD` | `1983-04-11` | **Clé de filtrage 2019** |
| `code_lieu_deces` | string(5) | `02691` | **Clé de jointure région** |
| `numero_acte_deces` | int | `369` | |

> ⚠️ **Donnée à caractère personnel** : nom, prénom et date de naissance ne sont pas nécessaires pour le KPI 8. **Le job ETL doit les écarter à l'ingestion** (RGPD, conformité avec le document Sécurité/Anonymisation du projet).

---

## 2. Architecture du job

```
┌─────────────────────────┐
│   INSEE                 │
│   deces.csv (~2 Go)     │
└────────────┬────────────┘
             │ (1) Ingestion
             ▼
┌─────────────────────────┐
│   HDFS staging          │
│   /staging/deces/       │
└────────────┬────────────┘
             │ (2) Profiling sur 1000 lignes
             ▼
┌─────────────────────────┐
│   Table externe Hive    │
│   staging_deces         │
└────────────┬────────────┘
             │ (3) Filtrage + transformation
             │     - WHERE YEAR(date_deces) = 2019
             │     - SUBSTR(code_lieu_deces,1,2) → dept
             │     - JOIN ref_dept_region
             │     - JOIN Dim_Temps
             │     - JOIN Dim_Localisation
             ▼
┌─────────────────────────┐
│   Fait_Deces            │
│   (date_id, region_id,  │
│    nb_deces)            │
└─────────────────────────┘
```

---

## 3. Étapes détaillées

### Étape 1 — Profiling (préalable obligatoire)

Avant tout chargement massif, on **valide le format sur un échantillon** pour éviter de découvrir un encoding ou un séparateur exotique après plusieurs minutes d'ingestion.

```bash
# Échantillon de 1000 lignes
head -1000 deces.csv > deces_sample.csv

# Vérifications rapides
file deces.csv                          # Confirme l'encodage
head -1 deces.csv                       # Vérifie le header
awk -F',' '{print NF}' deces_sample.csv | sort -u   # Nb colonnes constant ?
```

**Résultats attendus** :
- 10 colonnes par ligne
- Encodage UTF-8
- Aucune ligne vide

### Étape 2 — Ingestion HDFS

```bash
# Création du répertoire de staging
hdfs dfs -mkdir -p /staging/deces

# Upload du fichier (peut être chunké si besoin)
hdfs dfs -put -f deces.csv /staging/deces/

# Vérification
hdfs dfs -ls -h /staging/deces/
```

### Étape 3 — Table externe Hive (staging)

On crée une table **externe** pointant sur HDFS pour ne pas dupliquer la donnée et garder le fichier brut accessible.

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS staging_deces (
    nom                  STRING,
    prenom               STRING,
    sexe                 TINYINT,
    date_naissance       DATE,
    code_lieu_naissance  STRING,
    lieu_naissance       STRING,
    pays_naissance       STRING,
    date_deces           DATE,
    code_lieu_deces      STRING,
    numero_acte_deces    INT
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES (
    "separatorChar" = ",",
    "quoteChar"     = "\"",
    "escapeChar"    = "\\"
)
STORED AS TEXTFILE
LOCATION '/staging/deces/'
TBLPROPERTIES ("skip.header.line.count" = "1");
```

### Étape 4 — Transformation et chargement dans Fait_Deces

```sql
INSERT INTO TABLE Fait_Deces
SELECT
    t.date_id,
    l.region_id,
    1 AS nb_deces
FROM staging_deces s
JOIN Dim_Temps t
    ON t.date_complete = s.date_deces
JOIN ref_dept_region r
    ON r.code_departement = SUBSTR(s.code_lieu_deces, 1, 2)
JOIN Dim_Localisation l
    ON l.code_region = r.code_region
WHERE YEAR(s.date_deces) = 2019
  AND s.code_lieu_deces IS NOT NULL
  AND LENGTH(s.code_lieu_deces) = 5;
```

**Logique** :
- `SUBSTR(code_lieu_deces, 1, 2)` → code département (les 2 premiers caractères du code INSEE commune).
- Pour les départements d'outre-mer dont le code commence par "97x" ou "98x", le code département fait 3 caractères → cas à gérer (voir §5).
- Jointure via une table de référence `ref_dept_region` (département → région) — à intégrer dans les dimensions partagées.

---

## 4. Stratégie de test

| Phase | Périmètre | Objectif |
|---|---|---|
| **1. Smoke test** | 1 000 lignes (`head -1000`) | Valider format / encoding / parser |
| **2. Test 2019** | Filtre `WHERE YEAR(date_deces) = 2019` (~616k lignes) | Valider la logique de transformation et le mapping régions |
| **3. Run complet** | Fichier intégral (~25 M lignes) | Charger l'historique (post-MVP) |

> Pour le L1, seules les phases 1 et 2 sont attendues — l'objectif est de produire le KPI 8 sur 2019.

---

## 5. Gestion d'erreurs

| Cas d'erreur | Détection | Action |
|---|---|---|
| Ligne mal parsée (mauvais nombre de colonnes) | Hive renvoie `NULL` | Loguer le numéro de ligne, exclure du chargement |
| `code_lieu_deces` vide ou < 5 caractères | Filtre `WHERE LENGTH = 5` | Exclure, logguer le count |
| Département inconnu dans `ref_dept_region` | `LEFT JOIN` + `WHERE r.code_region IS NULL` | Table d'erreurs `err_deces_dept_inconnu` |
| Date `date_deces` non parseable | Hive renvoie `NULL DATE` | Exclure du filtre 2019, logguer |
| **DOM-TOM (codes 97x/98x)** | `SUBSTR(., 1, 2) = '97'` ou `'98'` | Gérer en `SUBSTR(., 1, 3)` ou créer un cas spécial |

---

## 6. RGPD / conformité

Conformément au document `Securite_Anonymisation_NFR.md` (à produire en parallèle) :

- ❌ `nom`, `prenom`, `date_naissance` **ne sont pas chargés** dans `Fait_Deces`
- ✅ Seules les dimensions agrégeables sont conservées : date du décès + localisation
- ✅ Pas de table intermédiaire persistante contenant les données personnelles (la table `staging_deces` peut être purgée après chargement)
- ✅ Granularité finale : 1 ligne = 1 décès anonyme

---

## 7. Volumétrie & performance

| Étape | Volume | Estimation durée |
|---|---|---|
| Upload HDFS (2 Go) | 1 fichier | ~2-5 min selon bande passante |
| Smoke test (1000 lignes) | ~50 Ko | <10 sec |
| Filtrage 2019 (`INSERT … SELECT`) | 616k lignes en sortie | 1-3 min sur cluster local |
| Load complet (post-MVP) | 25M lignes | ~20-40 min |

---

## 8. Definition of Done

- [x] Profiling effectué (format, encoding, volumétrie vérifiés sur fichier réel)
- [x] Schéma du job dessiné (architecture en 4 étapes)
- [x] Étape de filtrage 2019 explicite (`WHERE YEAR(date_deces) = 2019`)
- [x] Stratégie de test sur échantillon mentionnée (smoke 1k → 2019 → complet)
- [x] Gestion d'erreurs documentée (lignes mal parsées, DOM-TOM)
- [x] Aspect RGPD pris en compte (exclusion des PII)
- [ ] Section "Job ETL Décès" intégrée au rapport L1
- [ ] Relecture par l'équipe

---

## 9. Dépendances & suite

**Prérequis** :
- [Modélisation Fait_Deces](modelisation_fait_deces.md) ✅
- Table `ref_dept_region` (département → région INSEE) à intégrer dans les dimensions partagées ([869dfg0v4](https://app.clickup.com/t/869dfg0v4))

**Débloque** :
- `[P4] DDL Fait_Deces` ([869dfg1jp](https://app.clickup.com/t/869dfg1jp))
- `[P4] Chargement Fait_Deces + vérification` ([869dfg1k6](https://app.clickup.com/t/869dfg1k6))
