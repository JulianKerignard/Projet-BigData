# Description Job ETL - Consultations

**Livrable:** L1 - Référentiel de données
**Tâche:** [P1] Description job ETL Consultations (extraction PostgreSQL)
**Date:** Juin 2026
**Responsable:** Julian

---

## 1. OBJECTIF DU JOB

Alimenter la table de fait **Fait_Consultation** (voir `docs/03-fait-consultation.md`) et les dimensions associées à partir de la base **PostgreSQL** des soins médico-administratifs.

**Flux:** `Dump PostgreSQL (DATA2023)` → **Extraction** → `HDFS (Bronze)` → **HiveQL (Silver → Gold)** → `Hive Data Warehouse`

> Conforme au stack verrouillé : **HiveQL batch, sans Spark** (cf. `docs/01-architecture.md`). L'extraction s'appuie sur les outils PostgreSQL natifs (`pg_restore`, `COPY`).

---

## 2. SOURCES DE DONNÉES

### Source primaire : table `Consultation`

**Localisation:** `DATA 2024/BDD PostgreSQL/DATA2023` (dump custom PostgreSQL 14.4)
**Format:** dump binaire `pg_dump -Fc`
**Table:** `public."Consultation"`

**Colonnes source:**

| Colonne source | Type | Description |
|---|---|---|
| `Num_consultation` | INTEGER (NOT NULL) | ID unique de la consultation |
| `Id_mut` | INTEGER | Mutuelle (non utilisé dans le fait) |
| `Id_patient` | INTEGER | Identifiant patient → Dim_Patient |
| `Id_prof_sante` | VARCHAR | Identifiant professionnel → Dim_Professionnel |
| `Code_diag` | VARCHAR | Code diagnostic → Dim_Diagnostic |
| `Motif` | VARCHAR | Motif de consultation (dim. dégénérée) |
| `Date` | DATE | Date de la consultation → Dim_Temps |
| `Heure_debut` | TIME | Heure de début |
| `Heure_fin` | TIME | Heure de fin |

### Sources secondaires (référentiels → dimensions)

1. **`Patient`** (Id_patient, Sexe, Age, …) → Dim_Patient
2. **`Professionnel_de_sante`** (Identifiant, Code_specialite, …) → Dim_Professionnel
3. **`Diagnostic`** (Code_diag, Diagnostic) → Dim_Diagnostic
4. **`Specialites`** (Code_specialite, Specialite) → enrichit Dim_Professionnel
5. **Calendrier généré** → Dim_Temps

---

## 3. ARCHITECTURE DU JOB ETL

```
┌─────────────────────────────────┐
│ STAGE 1: EXTRACTION             │
├─────────────────────────────────┤
│  pg_restore du dump DATA2023    │
│  COPY tables → CSV              │
│  hdfs dfs -put → zone Bronze    │
│  Table externe Hive (Bronze)    │
└──────────────┬──────────────────┘
               ↓
┌─────────────────────────────────┐
│ STAGE 2: NETTOYAGE              │
├─────────────────────────────────┤
│  Déduplication Num_consultation │
│  Gestion NULL / champs vides    │
│  Validation Heure_debut/fin     │
│  Standardisation                │
└──────────────┬──────────────────┘
               ↓
┌─────────────────────────────────┐
│ STAGE 3: TRANSFORMATION         │
├─────────────────────────────────┤
│  Pseudonymisation Id_patient    │
│  Calcul duree_minutes           │
│  Lookup clés dimensions (FK)    │
│  Mesure nb_consultation = 1     │
└──────────────┬──────────────────┘
               ↓
┌─────────────────────────────────┐
│ STAGE 4: CHARGEMENT (LOAD)      │
├─────────────────────────────────┤
│  INSERT Fait_Consultation       │
│  Format Parquet                 │
│  Partition par annee            │
│  Bucketing professionnel_key    │
└──────────────┬──────────────────┘
               ↓
┌─────────────────────────────────┐
│ STAGE 5: QUALITÉ & CONTRÔLE     │
├─────────────────────────────────┤
│  Réconciliation count src/cible │
│  Contrôle intégrité FK          │
│  Audit trail / error logging    │
└─────────────────────────────────┘
```

---

## 4. DÉTAIL DES TRANSFORMATIONS

### 4.1 STAGE 1 : EXTRACTION

PostgreSQL n'étant pas la cible, on extrait la table vers un CSV plat, puis on dépose sur HDFS.

```bash
# 1. Restaurer le dump dans une instance PostgreSQL locale
pg_restore -d postgres -t Consultation "DATA 2024/BDD PostgreSQL/DATA2023"
pg_restore -d postgres -t Patient -t Professionnel_de_sante \
           -t Diagnostic -t Specialites "DATA 2024/BDD PostgreSQL/DATA2023"

# 2. Exporter la table Consultation en CSV (séparateur ;)
psql -d postgres -c "\COPY public.\"Consultation\" \
  TO '/tmp/consultation.csv' WITH (FORMAT csv, HEADER true, DELIMITER ';')"

# 3. Déposer dans la zone Bronze HDFS
hdfs dfs -mkdir -p /chu/bronze/consultation
hdfs dfs -put -f /tmp/consultation.csv /chu/bronze/consultation/
```

```sql
-- 4. Table externe Hive pointant sur la zone Bronze (données brutes, non typées)
CREATE EXTERNAL TABLE IF NOT EXISTS bronze_consultation (
    num_consultation  STRING,
    id_mut            STRING,
    id_patient        STRING,
    id_prof_sante     STRING,
    code_diag         STRING,
    motif             STRING,
    date_consultation STRING,
    heure_debut       STRING,
    heure_fin         STRING
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ';'
STORED AS TEXTFILE
LOCATION '/chu/bronze/consultation'
TBLPROPERTIES ('skip.header.line.count'='1');
```

**Validation:**
- ✅ Colonnes présentes et alignées
- ✅ Encodage UTF-8
- ✅ Volumétrie cohérente avec la source

---

### 4.2 STAGE 2 : NETTOYAGE (DATA CLEANSING)

#### 2.1 Déduplication

```sql
-- Garder une seule ligne par Num_consultation (clé naturelle unique)
CREATE TABLE silver_consultation_dedup AS
SELECT * FROM (
  SELECT *,
         ROW_NUMBER() OVER (PARTITION BY num_consultation
                            ORDER BY date_consultation) AS rn
  FROM bronze_consultation
) t
WHERE rn = 1;
```

#### 2.2 Gestion des valeurs manquantes

| Colonne | Stratégie | Raison |
|---------|-----------|--------|
| `num_consultation` | Rejeter la ligne | Clé obligatoire |
| `id_patient` | Rejeter la ligne | Lien dimension obligatoire |
| `date_consultation` | Rejeter la ligne | Clé temporelle obligatoire |
| `code_diag` | 'UNKNOWN' | Optionnel, garde la ligne |
| `id_prof_sante` | 'UNKNOWN' | Optionnel, garde la ligne |
| `heure_debut`/`heure_fin` | NULL → duree non calculée | Mesure dégradée tolérée |

```sql
-- Rejet des lignes sans clé obligatoire
CREATE TABLE silver_consultation_clean AS
SELECT *
FROM silver_consultation_dedup
WHERE num_consultation IS NOT NULL
  AND id_patient       IS NOT NULL
  AND date_consultation IS NOT NULL;
```

#### 2.3 Standardisation

```sql
-- Typage de la date et contrôle de plage raisonnable
SELECT
  num_consultation,
  CAST(date_consultation AS DATE) AS date_consultation,
  year(CAST(date_consultation AS DATE)) AS annee
FROM silver_consultation_clean
WHERE year(CAST(date_consultation AS DATE)) BETWEEN 2015 AND 2023;
```

---

### 4.3 STAGE 3 : TRANSFORMATION (BUSINESS LOGIC)

#### 3.1 Pseudonymisation de l'identifiant patient

Conformément à la règle d'anonymisation (cf. `docs/Securite_Anonymisation_NFR.md`), l'`Id_patient` est pseudonymisé par hachage avant tout stockage analytique.

```sql
-- Hachage SHA-256 avec sel (le sel est géré hors du dépôt)
SELECT
  num_consultation,
  sha2(concat(id_patient, '${hivevar:SALT}'), 256) AS id_patient_anonyme
FROM silver_consultation_clean;
```

#### 3.2 Calcul de la mesure `duree_minutes`

```sql
-- Durée de la consultation en minutes (mesure additive)
SELECT
  num_consultation,
  (unix_timestamp(heure_fin, 'HH:mm:ss')
   - unix_timestamp(heure_debut, 'HH:mm:ss')) / 60 AS duree_minutes
FROM silver_consultation_clean
WHERE heure_debut IS NOT NULL AND heure_fin IS NOT NULL;
```

#### 3.3 Lookup des clés de dimension (surrogate keys)

```sql
-- Résolution des FK vers les dimensions conformes
SELECT
  t.temps_key,
  p.patient_key,
  pr.professionnel_key,
  d.diagnostic_key,
  c.num_consultation,
  c.motif,
  1                AS nb_consultation,        -- mesure de comptage
  c.duree_minutes
FROM silver_consultation_clean c
LEFT JOIN dim_temps         t  ON t.date            = CAST(c.date_consultation AS DATE)
LEFT JOIN dim_patient       p  ON p.id_patient_anonyme = c.id_patient_anonyme
LEFT JOIN dim_professionnel pr ON pr.id_professionnel = c.id_prof_sante
LEFT JOIN dim_diagnostic    d  ON d.code_diagnostic   = c.code_diag;
```

> **Point d'attention (B1 — établissement)** : la source `Consultation` ne porte pas d'identifiant d'établissement (cf. `docs/03-fait-consultation.md`). La FK `etablissement_key` est laissée en attente de l'arbitrage d'équipe (établissement unique / dérivation via professionnel / hors périmètre).

---

### 4.4 STAGE 4 : CHARGEMENT (LOAD)

```sql
-- Table de fait cible : Parquet, partitionnée par année, bucketée
CREATE TABLE IF NOT EXISTS fait_consultation (
    temps_key          INT,
    patient_key        INT,
    professionnel_key  INT,
    diagnostic_key     INT,
    etablissement_key  INT,
    num_consultation   INT,
    motif              STRING,
    nb_consultation    INT,
    duree_minutes      DOUBLE
)
PARTITIONED BY (annee INT)
CLUSTERED BY (professionnel_key) INTO 8 BUCKETS
STORED AS PARQUET;

-- Insertion dynamique par partition (résultat du stage 3)
SET hive.exec.dynamic.partition = true;
SET hive.exec.dynamic.partition.mode = nonstrict;
SET hive.enforce.bucketing = true;

INSERT OVERWRITE TABLE fait_consultation PARTITION (annee)
SELECT
  temps_key, patient_key, professionnel_key, diagnostic_key,
  etablissement_key, num_consultation, motif,
  nb_consultation, duree_minutes,
  year(date_consultation) AS annee
FROM transformed_consultation;
```

- **Format Parquet** : colonnaire + compressé (coût ↓, perf ↑).
- **Partition `annee`** : élague les scans sur les besoins « par période » (B1, B2).
- **Bucket `professionnel_key`** : accélère les agrégats du besoin B6 (par professionnel).
- Chargement **après** les dimensions (intégrité référentielle).

---

### 4.5 STAGE 5 : QUALITÉ & CONTRÔLE

```sql
-- 1. Réconciliation des volumes source vs cible
SELECT
  (SELECT COUNT(*) FROM silver_consultation_clean) AS src_count,
  (SELECT COUNT(*) FROM fait_consultation)         AS tgt_count;

-- 2. Détection des FK orphelines (lookups non résolus)
SELECT COUNT(*) AS fk_temps_orphelines
FROM fait_consultation WHERE temps_key IS NULL;

SELECT COUNT(*) AS fk_patient_orphelines
FROM fait_consultation WHERE patient_key IS NULL;
```

| Contrôle | Seuil d'alerte |
|----------|----------------|
| Écart count source/cible | > 5 % (hors rejets justifiés) |
| FK temps orphelines | > 0 |
| FK patient orphelines | > 0 |
| `duree_minutes` négative | > 0 (incohérence horaire) |

---

## 5. ORCHESTRATION & DÉPENDANCES

| Ordre | Étape | Dépend de |
|-------|-------|-----------|
| 1 | Chargement des dimensions (Temps, Patient, Professionnel, Diagnostic) | — |
| 2 | Extraction Consultation → Bronze | Dump PostgreSQL disponible |
| 3 | Nettoyage → Silver | Étape 2 |
| 4 | Transformation + lookup FK | Étapes 1 et 3 |
| 5 | Chargement Fait_Consultation (Gold) | Étape 4 |
| 6 | Contrôles qualité | Étape 5 |

- **Rejouable** : chargement en `INSERT OVERWRITE` par partition → relance idempotente sur une année.
- **Reprise** : chaque stage matérialise une table intermédiaire (Bronze → Silver → Gold) permettant de repartir d'un point de contrôle.
