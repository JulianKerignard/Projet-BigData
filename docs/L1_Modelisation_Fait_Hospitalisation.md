# Modélisation - Fait_Hospitalisation

**Livrable:** L1 - Référentiel de données  
**Tâche:** [P2] Modélisation Fait_Hospitalisation  
**Date:** Juin 2026  
**Responsable:** Chloé

---

## 1. OBJECTIFS DE LA TABLE DE FAIT

### Axes d'analyse (besoins utilisateurs)
- Taux de consultation/hospitalisation par établissement et période
- Taux par diagnostic (CIM-10)
- Taux par sexe et groupe d'âge
- Durée moyennes et distributions d'hospitalisation

### Mesures clés
- Nombre d'hospitalisations
- Durée moyenne de séjour (DMOS)
- Taux d'occupation lits
- Coûts associés (optionnel)

---

## 2. SCHÉMA EN ÉTOILE (STAR SCHEMA)

```
                    ┌─────────────────┐
                    │ Dim_Temps       │
                    ├─────────────────┤
                    │ id_temps        │◄─┐
                    │ date_entree     │  │
                    │ annee           │  │
                    │ mois            │  │
                    │ trimestre       │  │
                    │ jour_semaine    │  │
                    │ semaine_annee   │  │
                    └─────────────────┘  │
                                         │
        ┌────────────────┐               │           ┌──────────────────┐
        │ Dim_Diagnostic │◄──┐           │       ┌──►│ Dim_Etablissement│
        ├────────────────┤   │           │       │   ├──────────────────┤
        │ id_diagnostic  │   │           │       │   │ id_etablissement │
        │ code_cim10     │   │           │       │   │ nom              │
        │ libelle_court  │   │     ┌──────────────┐  │ code_region      │
        │ libelle_long   │   │     │ Fait_Hosp   │  │ nom_region       │
        │ categorie      │   └────►├──────────────┤◄─┤ code_commune     │
        │ groupe_diag    │         │ id_hosp     │  │ nom_commune      │
        └────────────────┘         │ id_temps    │  │ type_etablissement
                                   │ id_patient  │  │ capacite_lits     
        ┌──────────────────┐       │ id_diag     │  └──────────────────┘
        │ Dim_Patient      │◄─────►├──────────────┤
        ├──────────────────┤       │ nb_hospi    │
        │ id_patient       │       │ dmos        │
        │ annee_naissance  │       │ date_entree │
        │ groupe_age       │       │ date_sortie │
        │ sexe             │       │ motif       │
        │ code_region_naiss│       │ readmission │
        └──────────────────┘       │ cout        │
                                   └──────────────┘
                                         ▲
                              ┌──────────┴──────────┐
                              │ Dim_Type_Sejour    │
                              ├────────────────────┤
                              │ id_type_sejour     │
                              │ libelle_type       │
                              │ duree_moyenne      │
                              └────────────────────┘
```

---

## 3. DÉTAIL DES DIMENSIONS

### 3.1 Dim_Temps

| Colonne | Type | Description |
|---------|------|-------------|
| `id_temps` | INT | PK: YYYYMMDD (ex: 20200315) |
| `date_entree` | DATE | Date du jour |
| `annee` | INT | Année (2017-2023) |
| `mois` | INT | Mois (1-12) |
| `trimestre` | INT | Trimestre (1-4) |
| `jour_semaine` | INT | Jour semaine (1-7: lun-dim) |
| `semaine_annee` | INT | Numéro semaine ISO |
| `est_weekend` | BOOLEAN | true si samedi/dimanche |
| `est_jour_ferie` | BOOLEAN | true si jour férié |

**Rationale:** Permets analyses temporelles fine (trend par mois, saisonnalité par jour, etc.)

---

### 3.2 Dim_Patient

| Colonne | Type | Description | Anonymisation |
|---------|------|-------------|---|
| `id_patient` | INT | PK: Identifiant unique patient | ✅ Conserver (pseudo) |
| `annee_naissance` | INT | Année de naissance (1920-2023) | ✅ (année seulement) |
| `groupe_age` | VARCHAR | Groupes: [0-18], [19-35], [36-50], [51-65], [66+] | ✅ |
| `sexe` | CHAR(1) | 'H' (homme) ou 'F' (femme) | ✅ |
| `code_region_naissance` | VARCHAR(5) | Code région INSEE de naissance | ✅ |
| `nom_region_naissance` | VARCHAR(50) | Nom région | ✅ |

**Rationale:** Permet segmentation par profil patient pour analyses comparatives

---

### 3.3 Dim_Diagnostic

| Colonne | Type | Description |
|---------|------|-------------|
| `id_diagnostic` | INT | PK |
| `code_cim10` | VARCHAR(10) | Code diagnostic CIM-10 (ex: S02800) |
| `libelle_court` | VARCHAR(100) | Libellé court (ex: "Fracture dent") |
| `libelle_long` | VARCHAR(500) | Libellé détaillé |
| `categorie_principal` | VARCHAR(50) | Catégorie (ex: "Traumatismes") |
| `groupe_diagnostic` | VARCHAR(50) | Groupement (ex: "Traumatismes crânio-faciaux") |
| `dms_moyen` | INT | DMS moyen pour ce diagnostic (en jours) |

**Rationale:** Permet analyse par diagnostic, comparaison de DMS par type de cas

---

### 3.4 Dim_Etablissement

| Colonne | Type | Description | Anonymisation |
|---------|------|-------------|---|
| `id_etablissement` | INT | PK |
| `code_finess` | VARCHAR(9) | Code FINESS établissement | ✅ (public) |
| `nom` | VARCHAR(200) | Nom établissement | ✅ |
| `type_etablissement` | VARCHAR(50) | MCO, SSR, HAD, etc. | ✅ |
| `code_region` | VARCHAR(5) | Code région INSEE | ✅ |
| `nom_region` | VARCHAR(50) | Nom région | ✅ |
| `code_commune` | VARCHAR(5) | Code commune INSEE | ✅ |
| `nom_commune` | VARCHAR(50) | Nom commune | ✅ |
| `capacite_lits` | INT | Nombre de lits | ✅ |
| `secteur_activite` | VARCHAR(50) | Public, Privé lucratif, Privé non-lucratif | ✅ |

**Rationale:** Localisation géographique + caractérisation établissement pour analyses régionales/territoriales

---

### 3.5 Dim_Type_Sejour

| Colonne | Type | Description |
|---------|------|-------------|
| `id_type_sejour` | INT | PK |
| `libelle_type` | VARCHAR(50) | Full, Partial, Ambulatory, etc. |
| `duree_moyenne_jours` | INT | Moyenne statistique |
| `cout_moyen_estime` | DECIMAL(10,2) | Coût estimé |

**Rationale:** Permet comparaison coûts et durées par type de séjour

---

## 4. TABLE DE FAIT - Fait_Hospitalisation

### Structure détaillée

```sql
CREATE TABLE Fait_Hospitalisation (
  -- Clés étrangères (dimensions)
  id_temps INT,                    -- Clé vers Dim_Temps (date entrée)
  id_patient INT,                  -- Clé vers Dim_Patient (patient anonymisé)
  id_etablissement INT,            -- Clé vers Dim_Etablissement
  id_diagnostic INT,               -- Clé vers Dim_Diagnostic (diagnostic principal)
  id_type_sejour INT,              -- Clé vers Dim_Type_Sejour
  
  -- Mesures (facts)
  nb_hospitalisations INT,         -- Compteur (1 par enregistrement en général)
  dmos DECIMAL(5,2),               -- Durée Moyenne Occupation Lit
  nb_jours_hospitalisation INT,    -- Durée du séjour en jours
  
  -- Dimensions dégénérées (optionnel mais utile)
  num_hospitalisation VARCHAR(20), -- ID unique séjour (anonymisé)
  date_entree DATE,                -- Date d'entrée (doublon mais utile)
  date_sortie DATE,                -- Date de sortie
  motif_sortie VARCHAR(50),        -- Sortie normale, décès, sortie contre avis, etc.
  
  -- Flags
  est_readmission BOOLEAN,         -- Réadmission <30j
  est_deces BOOLEAN,               -- Patient décédé durante séjour
  
  -- Qualité données
  date_chargement TIMESTAMP,       -- Timestamp du chargement
  date_modification TIMESTAMP      -- Dernière modification
)
PARTITION BY (id_temps)            -- Partitionnement par année/mois
CLUSTERED BY (id_patient) INTO 8 BUCKETS;  -- Bucketing par patient
```

### Mesures clés

| Mesure | Formule | Granularité |
|--------|---------|---|
| **Nombre d'hospitalisations** | COUNT(*) | Par période, établissement, diagnostic |
| **Durée Moyenne Séjour (DMS)** | AVG(nb_jours_hospitalisation) | Par établissement, diagnostic |
| **Taux d'occupation lits** | SUM(nb_jours) / (capacite_lits × nb_jours_periode) | Par établissement |
| **Taux de réadmission** | COUNT(est_readmission=true) / COUNT(*) | Par établissement |
| **Taux de mortalité** | COUNT(est_deces=true) / COUNT(*) | Par établissement, diagnostic |

---

## 5. REQUÊTES DE VALIDATION

### 5.1 Nb hospitalisations par établissement/année

```sql
SELECT 
  e.nom_region,
  e.nom,
  t.annee,
  COUNT(*) as nb_hospitalisations,
  AVG(f.nb_jours_hospitalisation) as dms_moyen
FROM Fait_Hospitalisation f
JOIN Dim_Temps t ON f.id_temps = t.id_temps
JOIN Dim_Etablissement e ON f.id_etablissement = e.id_etablissement
GROUP BY e.nom_region, e.nom, t.annee
ORDER BY t.annee DESC, nb_hospitalisations DESC;
```

### 5.2 Top diagnostics par établissement

```sql
SELECT 
  e.nom,
  d.libelle_court,
  COUNT(*) as nb_cas,
  AVG(f.nb_jours_hospitalisation) as dms
FROM Fait_Hospitalisation f
JOIN Dim_Etablissement e ON f.id_etablissement = e.id_etablissement
JOIN Dim_Diagnostic d ON f.id_diagnostic = d.id_diagnostic
WHERE YEAR(f.date_entree) = 2023
GROUP BY e.nom, d.libelle_court
ORDER BY nb_cas DESC
LIMIT 20;
```

### 5.3 Hospitalisations par sexe et groupe d'âge

```sql
SELECT 
  p.sexe,
  p.groupe_age,
  t.annee,
  COUNT(*) as nb_hospitalisations
FROM Fait_Hospitalisation f
JOIN Dim_Patient p ON f.id_patient = p.id_patient
JOIN Dim_Temps t ON f.id_temps = t.id_temps
GROUP BY p.sexe, p.groupe_age, t.annee
ORDER BY t.annee DESC, p.groupe_age;
```

### 5.4 Taux de mortalité par établissement

```sql
SELECT 
  e.nom_region,
  e.nom,
  COUNT(*) as total_hospitalisations,
  SUM(CASE WHEN f.est_deces THEN 1 ELSE 0 END) as nb_deces,
  ROUND(SUM(CASE WHEN f.est_deces THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as taux_mortalite_pct
FROM Fait_Hospitalisation f
JOIN Dim_Etablissement e ON f.id_etablissement = e.id_etablissement
GROUP BY e.nom_region, e.nom
ORDER BY taux_mortalite_pct DESC;
```

---

## 6. CONSIDÉRATIONS DE PERFORMANCE

### Indexation proposée

```sql
-- Index sur clés étrangères
CREATE INDEX idx_fait_temps ON Fait_Hospitalisation (id_temps);
CREATE INDEX idx_fait_patient ON Fait_Hospitalisation (id_patient);
CREATE INDEX idx_fait_etablissement ON Fait_Hospitalisation (id_etablissement);
CREATE INDEX idx_fait_diagnostic ON Fait_Hospitalisation (id_diagnostic);

-- Index composés pour requêtes fréquentes
CREATE INDEX idx_fait_etab_diag ON Fait_Hospitalisation (id_etablissement, id_diagnostic);
CREATE INDEX idx_fait_patient_temps ON Fait_Hospitalisation (id_patient, id_temps);
```

### Stratégie de partitionnement

- **Partitionnement principal:** Par année (YEAR(id_temps))
- **Bucketing:** Par patient (id_patient) - 8 buckets pour parallélisation
- **Raison:** Améliore performance des requêtes temporelles + par patient

---

## 7. CONSIDÉRATIONS D'ANONYMISATION

✅ **Données conservées:**
- Code diagnostic (générique)
- Sexe, groupe d'âge (pas identifiant)
- Région/commune (géolocalisation OK)
- ID établissement (public)

🔐 **Données pseudonymisées:**
- ID patient → SHA-256 hash + salt

❌ **Données supprimées:**
- Num_Hospitalisation original
- Noms/prénoms
- Dates exactes (sauf année/mois pour analyses)

---

## 8. LIVRABLES ASSOCIÉS

- [x] Schéma logique (DDL SQL)
- [x] Requêtes d'analyse type
- [x] Plan d'indexation
- [ ] Implémentation en Hive (L2)
- [ ] Performance benchmark (L2)

---

**Version:** 1.0  
**Date:** 01/06/2026  
**Statut:** ✅ Complété
