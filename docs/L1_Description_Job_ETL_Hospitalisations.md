# Description Job ETL - Hospitalisations

**Livrable:** L1 - Référentiel de données  
**Tâche:** [P2] Description job ETL Hospitalisations  
**Date:** Juin 2026  
**Responsable:** Chloé

---

## 1. OBJECTIF DU JOB

Alimenter la table de fait **Fait_Hospitalisation** et les dimensions associées à partir de la source de données CSV `Hospitalisations.csv` du répertoire DATA 2024.

**Flux:** `Hospitalisations.csv` → **ETL Process** → `Hive Data Warehouse`

---

## 2. SOURCES DE DONNÉES

### Source primaire: Hospitalisations.csv

**Localisation:** `DATA 2024/Hospitalisation/Hospitalisations.csv`  
**Format:** CSV délimité par `;`  
**Taille:** ~250 KB  
**Nombre de lignes:** ~5000 enregistrements

**Colonnes source:**

| Colonne source | Type | Description |
|---|---|---|
| `Num_Hospitalisation` | VARCHAR | ID unique séjour hospitalier |
| `Id_patient` | INT | Identifiant patient (source) |
| `identifiant_organisation` | VARCHAR | Code établissement |
| `Code_diagnostic` | VARCHAR | Code diagnostic CIM-10 |
| `Suite_diagnostic_consultation` | VARCHAR | Libellé diagnostic |
| `Date_Entree` | DATE | Date d'entrée (format JJ/MM/YYYY) |
| `Jour_Hospitalisation` | INT | Durée séjour (jours) |

### Sources secondaires (pour enrichissement):

1. **Établissements (establishment_sante.csv)** → Dim_Etablissement
2. **Décès (deces.csv)** → Flag est_deces
3. **Temps (calendrier généré)** → Dim_Temps

---

## 3. ARCHITECTURE DU JOB ETL

```
┌─────────────────────────────────┐
│ STAGE 1: EXTRACTION             │
├─────────────────────────────────┤
│  Lecture CSV Hospitalisations   │
│  Validation schéma              │
│  Détection format dates         │
└──────────────┬──────────────────┘
               ↓
┌─────────────────────────────────┐
│ STAGE 2: NETTOYAGE              │
├─────────────────────────────────┤
│  Suppression doublon            │
│  Gestion NULL/vides             │
│  Standardisation formats        │
│  Validation données             │
└──────────────┬──────────────────┘
               ↓
┌─────────────────────────────────┐
│ STAGE 3: TRANSFORMATION         │
├─────────────────────────────────┤
│  Pseudonymisation ID patient    │
│  Enrichissement diagnostics     │
│  Détection décès                │
│  Calcul réadmission             │
│  Lookup dimensions              │
└──────────────┬──────────────────┘
               ↓
┌─────────────────────────────────┐
│ STAGE 4: CHARGEMENT (LOAD)      │
├─────────────────────────────────┤
│  Insertion Fait_Hospitalisation │
│  Update dimensions              │
│  Partitionnement/bucketing      │
└──────────────┬──────────────────┘
               ↓
┌─────────────────────────────────┐
│ STAGE 5: QUALITÉ & CONTRÔLE     │
├─────────────────────────────────┤
│  Count validation               │
│  Audit trail                    │
│  Error logging                  │
└─────────────────────────────────┘
```

---

## 4. DÉTAIL DES TRANSFORMATIONS

### 4.1 STAGE 1: EXTRACTION

**Input:** `Hospitalisations.csv`

```python
# PySpark / Hive SQL
df_hosp_raw = spark.read \
  .option("delimiter", ";") \
  .option("header", "true") \
  .option("encoding", "UTF-8") \
  .option("inferSchema", "false") \
  .csv("path/to/Hospitalisations.csv")

# Schema mapping
schema = StructType([
  StructField("Num_Hospitalisation", StringType()),
  StructField("Id_patient", IntegerType()),
  StructField("identifiant_organisation", StringType()),
  StructField("Code_diagnostic", StringType()),
  StructField("Suite_diagnostic_consultation", StringType()),
  StructField("Date_Entree", StringType()),  # Parse manually
  StructField("Jour_Hospitalisation", IntegerType())
])
```

**Validation:**
- ✅ Colonnes présentes
- ✅ Types compatibles
- ✅ Pas de corruption fichier

---

### 4.2 STAGE 2: NETTOYAGE (DATA CLEANSING)

#### 2.1 Suppression doublons

```sql
-- Identifier doublons par (Id_patient, Num_Hospitalisation, Date_Entree)
SELECT 
  Id_patient, 
  Num_Hospitalisation, 
  Date_Entree,
  COUNT(*) as nb_occurrences
FROM hosp_raw
GROUP BY Id_patient, Num_Hospitalisation, Date_Entree
HAVING COUNT(*) > 1;

-- Garder un seul par groupe
INSERT INTO hosp_cleaned
SELECT * FROM (
  SELECT 
    *,
    ROW_NUMBER() OVER (PARTITION BY Id_patient, Num_Hospitalisation ORDER BY Date_Entree) as rn
  FROM hosp_raw
) t
WHERE rn = 1;
```

#### 2.2 Gestion valeurs manquantes

| Colonne | Stratégie | Raison |
|---------|-----------|--------|
| `Id_patient` | Rejeter lignes | Identifiant patient obligatoire |
| `Date_Entree` | Rejeter lignes | Clé temporelle obligatoire |
| `Code_diagnostic` | 'Unknown' / Skip | Optionnel en source, peut être NULL |
| `Jour_Hospitalisation` | Recalculer ou 0 | Peut être inféré |
| `identifiant_organisation` | Rejeter lignes | Clé établissement obligatoire |

```sql
-- Nettoyage complet
DELETE FROM hosp_raw WHERE Id_patient IS NULL;
DELETE FROM hosp_raw WHERE Date_Entree IS NULL;
DELETE FROM hosp_raw WHERE identifiant_organisation IS NULL;

-- Remplir Code_diagnostic si NULL
UPDATE hosp_raw 
SET Code_diagnostic = 'UNKNOWN' 
WHERE Code_diagnostic IS NULL OR Code_diagnostic = '';
```

#### 2.3 Standardisation dates

```sql
-- Parser Date_Entree (format DD/MM/YYYY en source)
SELECT 
  Num_Hospitalisation,
  STR_TO_DATE(Date_Entree, '%d/%m/%Y') as date_entree_parsed,
  EXTRACT(YEAR FROM STR_TO_DATE(Date_Entree, '%d/%m/%Y')) as annee,
  EXTRACT(MONTH FROM STR_TO_DATE(Date_Entree, '%d/%m/%Y')) as mois
FROM hosp_raw;

-- Validation plages raisonnables (2015-2023)
WHERE YEAR(date_entree_parsed) BETWEEN 2015 AND 2023;
```

---

### 4.3 STAGE 3: TRANSFORMATION (BUSINESS LOGIC)

#### 3.1 Pseudonymisation ID_patient

```python
# Utiliser clé maître depuis Key Management Service
salt_per_patient = hashlib.sha256(
  f"{id_patient}_{GLOBAL_SALT}".encode()
).hexdigest()

id_patient_pseudo = hashlib.sha256(
  f"{id_patient}_{MASTER_KEY}_{salt_per_patient}".encode()
).hexdigest()

# Insérer dans table mapping (admin access only)
INSERT INTO patient_mapping_secure 
VALUES (id_patient, id_patient_pseudo, salt_per_patient, NOW());
```

#### 3.2 Enrichissement diagnostics

```sql
-- Lookup dimension diagnostic
SELECT 
  h.Num_Hospitalisation,
  h.Id_patient,
  d.id_diagnostic,  -- FK vers Dim_Diagnostic
  d.libelle_court,
  d.groupe_diagnostic,
  COALESCE(d.dms_moyen, 0) as dms_estime
FROM hosp_cleaned h
LEFT JOIN Dim_Diagnostic d ON h.Code_diagnostic = d.code_cim10
WHERE h.Code_diagnostic != 'UNKNOWN';
```

#### 3.3 Détection décès

```sql
-- Jointure avec registre décès pour détecter si patient décédé
SELECT 
  h.Num_Hospitalisation,
  h.Id_patient,
  h.date_entree,
  CASE 
    WHEN deces.date_deces IS NOT NULL 
      AND deces.date_deces >= h.date_entree 
      AND deces.date_deces <= (h.date_entree + INTERVAL '30' DAY)
    THEN 1
    ELSE 0
  END as est_deces_dans_sejour
FROM hosp_cleaned h
LEFT JOIN deces ON h.Id_patient = deces.id_patient_pseudo
ORDER BY h.date_entree;
```

#### 3.4 Détection réadmission

```sql
-- Réadmission = nouvelle hospitalisation <30j après sortie
WITH hosp_with_dates AS (
  SELECT 
    id_patient_pseudo,
    date_entree,
    date_entree + INTERVAL '0' DAY + Jour_Hospitalisation as date_sortie,
    ROW_NUMBER() OVER (PARTITION BY id_patient_pseudo ORDER BY date_entree) as sejour_num
  FROM hosp_cleaned
)
SELECT 
  a.Num_Hospitalisation as sejour_actuel,
  CASE 
    WHEN b.date_entree <= a.date_sortie + INTERVAL '30' DAY 
      AND b.date_entree > a.date_sortie
    THEN 1
    ELSE 0
  END as est_readmission
FROM hosp_with_dates a
LEFT JOIN hosp_with_dates b 
  ON a.id_patient_pseudo = b.id_patient_pseudo 
  AND b.sejour_num = a.sejour_num + 1
ORDER BY a.date_entree;
```

#### 3.5 Lookup dimensions

```sql
-- Joindre toutes les dimensions
SELECT 
  h.Num_Hospitalisation,
  t.id_temps,                    -- Dim_Temps
  h.id_patient_pseudo,           -- Dim_Patient
  e.id_etablissement,            -- Dim_Etablissement
  d.id_diagnostic,               -- Dim_Diagnostic
  s.id_type_sejour,              -- Dim_Type_Sejour
  1 as nb_hospitalisations,
  h.Jour_Hospitalisation as dmos,
  h.Jour_Hospitalisation as nb_jours_hospitalisation,
  h.Num_Hospitalisation,
  h.date_entree,
  h.date_entree + INTERVAL h.Jour_Hospitalisation DAY as date_sortie,
  'Sortie standard' as motif_sortie,
  h.est_readmission,
  h.est_deces_dans_sejour as est_deces,
  NOW() as date_chargement,
  NOW() as date_modification
FROM hosp_cleaned h
INNER JOIN Dim_Temps t ON h.date_entree = t.date_entree
INNER JOIN Dim_Patient p ON h.id_patient_pseudo = p.id_patient
INNER JOIN Dim_Etablissement e ON h.identifiant_organisation = e.code_finess
LEFT JOIN Dim_Diagnostic d ON h.Code_diagnostic = d.code_cim10
LEFT JOIN Dim_Type_Sejour s ON CASE 
  WHEN h.Jour_Hospitalisation < 1 THEN 'Ambulatoire'
  WHEN h.Jour_Hospitalisation BETWEEN 1 AND 2 THEN 'Court séjour'
  ELSE 'Séjour standard'
END = s.libelle_type;
```

---

### 4.4 STAGE 4: CHARGEMENT (LOAD)

#### 4.4.1 Insert dans Fait_Hospitalisation

```sql
INSERT OVERWRITE TABLE Fait_Hospitalisation
PARTITION BY (id_temps)
CLUSTERED BY (id_patient) INTO 8 BUCKETS
SELECT 
  id_temps,
  id_patient_pseudo as id_patient,
  id_etablissement,
  id_diagnostic,
  id_type_sejour,
  nb_hospitalisations,
  dmos,
  nb_jours_hospitalisation,
  Num_Hospitalisation_pseudo,
  date_entree,
  date_sortie,
  motif_sortie,
  est_readmission,
  est_deces,
  date_chargement,
  date_modification
FROM hosp_transformed;
```

#### 4.4.2 Update dimensions

```sql
-- Mettre à jour statistiques Dim_Diagnostic
UPDATE Dim_Diagnostic d
SET dms_moyen = (
  SELECT AVG(nb_jours_hospitalisation)
  FROM Fait_Hospitalisation f
  WHERE f.id_diagnostic = d.id_diagnostic
)
WHERE EXISTS (
  SELECT 1 FROM Fait_Hospitalisation f WHERE f.id_diagnostic = d.id_diagnostic
);
```

---

### 4.5 STAGE 5: QUALITÉ & CONTRÔLE

#### 5.5.1 Count validation

```sql
-- Comparer avant/après
SELECT 
  'Source' as phase,
  COUNT(*) as nb_lignes,
  COUNT(DISTINCT Id_patient) as nb_patients,
  COUNT(DISTINCT identifiant_organisation) as nb_etablissements
FROM hosp_raw
UNION ALL
SELECT 
  'Fait_Hospitalisation' as phase,
  COUNT(*) as nb_lignes,
  COUNT(DISTINCT id_patient) as nb_patients,
  COUNT(DISTINCT id_etablissement) as nb_etablissements
FROM Fait_Hospitalisation;

-- Validation: should be approximately equal
-- (sauf doublons supprimés et lignes invalides rejetées)
```

#### 5.5.2 Audit trail

```sql
-- Tracer chargement
INSERT INTO audit_etl_log (job_name, phase, nb_inserted, status, timestamp)
VALUES (
  'ETL_Hospitalisations',
  'Fait_Hospitalisation_Load',
  (SELECT COUNT(*) FROM Fait_Hospitalisation WHERE date_chargement = NOW()),
  'SUCCESS',
  NOW()
);
```

#### 5.5.3 Error handling

```python
try:
  # Job ETL execution
  spark.sql("""
    INSERT INTO Fait_Hospitalisation ...
  """)
  
  # Validation
  count_result = spark.sql("""
    SELECT COUNT(*) as cnt FROM Fait_Hospitalisation
  """).collect()[0][0]
  
  if count_result > 0:
    print(f"✅ SUCCESS: {count_result} rows loaded")
  else:
    raise Exception("No rows loaded!")
    
except Exception as e:
  print(f"❌ FAILURE: {str(e)}")
  # Log error + alert
  insert_audit_log('ETL_Hospitalisations', 'FAILED', str(e))
  raise
```

---

## 5. PLANNING & SCHEDULING

### Fréquence d'exécution
- **Mode:** Quotidien (daily batch)
- **Horaire:** 02:00 UTC (creux de charge)
- **Dépendances:** Après chargement Dim_Temps, Dim_Etablissement, Dim_Patient

### SLA du job
- **Durée attendue:** < 30 minutes
- **Tolerance:** ≤ 1 heure
- **Retry:** 2 tentatives auto (si timeout)

### Arrêt du job
- [ ] Si source CSV invalide (validation échoue)
- [ ] Si < 80% des lignes source chargées
- [ ] Si rejoins vers dimensions < 90% match rate

---

## 6. OUTILS & TECHNOLOGIE

| Composant | Technologie | Raison |
|-----------|---|---|
| **Orchestration** | Apache Airflow | Scheduling + dependency management |
| **Computation** | PySpark + Hive SQL | Parallélisation données massives |
| **Stockage** | Hive (HDFS) | Data warehouse distribué |
| **Logging** | ELK Stack / Splunk | Centralized logs + monitoring |
| **KMS** | AWS KMS / HashiCorp Vault | Gestion clés cryptage |

---

## 7. CONSIDÉRATIONS DE SÉCURITÉ

✅ **Mesures implémentées:**
- Pseudonymisation ID patient (SHA-256 + salt)
- Suppression données identifiantes (noms, prénoms, etc.)
- Audit trail complet (qui, quand, quoi)
- Séparation rôles (dev ≠ prod ≠ admin)
- Chiffrement en transit (TLS)
- Chiffrement au repos (AES-256)

🔐 **Données sensibles:**
- Table mapping patients → Access restreint ADMIN only
- Logs ETL → Pas d'affichage patient IDs
- Erreurs → Loggées sans données sensibles

---

## 8. MONITORING & ALERTES

```yaml
Alertes configurées:
  - Job timeout (> 1h): Alert OPS team
  - Match rate < 90%: Alert Data Engineering
  - Row count variance > 10%: Alert Product
  - Data quality fail: Alert Data Steward
```

Dashboard Grafana:
- Nombre d'enregistrements chargés (daily)
- Durée exécution (trend)
- Match rate par dimension (%)
- Error rate (%)

---

## 9. DOCUMENTATION & RUNBOOK

### Runbook: Restart du job en cas d'erreur

```bash
# 1. Vérifier logs dernière exécution
airflow logs dag_id ETL_Hospitalisations

# 2. Vérifier source données
ls -la /data/raw/Hospitalisations.csv

# 3. Vérifier connectivité Hive
beeline -u jdbc:hive2://hive-server:10000

# 4. Redémarrer job
airflow dags trigger ETL_Hospitalisations

# 5. Valider résultat
hive> SELECT COUNT(*) FROM Fait_Hospitalisation WHERE DATE(date_chargement) = TODAY();
```

---

## 10. AMÉLIORATION FUTURES

- [ ] Incremental load (CDC) au lieu de full reload
- [ ] Validation schéma DataContract
- [ ] Machine Learning: détection anomalies
- [ ] Real-time streaming au lieu de batch daily

---

**Version:** 1.0  
**Date création:** 01/06/2026  
**Prochaine révision:** Après implémentation L2  
**Statut:** ✅ Complété
