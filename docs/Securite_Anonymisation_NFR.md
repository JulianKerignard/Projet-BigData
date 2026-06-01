# Sécurité, Anonymisation & NFR - Projet CHU Big Data

**Tâche:** [COMMUN] Sécurité + NFR + règle d'anonymisation  
**Responsable:** Chloé  
**Date:** Juin 2026  
**Statut:** En cours

---

## 1. SPÉCIFICATIONS DE SÉCURITÉ

### 1.1 Classification des données

Les données du projet CHU sont classifiées comme **hautement sensibles** (Niveau 3/3) selon la réglementation RGPD et les lois de protection des données médicales:

- **Données médicales** (diagnostics, hospitalisations) → Données de santé (Article 9 RGPD)
- **Données personnelles identifiantes** (noms, prénoms, dates de naissance/décès) → PII
- **Données géographiques** (établissements, lieux de naissance/décès) → Données contextuelles

### 1.2 Exigences de sécurité globales

| Exigence | Description | Impact |
|----------|-------------|--------|
| **Contrôle d'accès** | Authentification forte + autorisation par rôle (RBAC) | Accès restreint aux données par profil utilisateur |
| **Chiffrement en transit** | TLS 1.3 obligatoire pour toute transmission | Protéger les données en mouvement |
| **Chiffrement au repos** | AES-256 pour données sensibles en base/stockage | Protéger données stockées |
| **Audit & Logging** | Trace complète des accès et modifications | Conformité légale + détection d'anomalies |
| **Backup sécurisé** | Sauvegardes chiffrées et géo-distribuées | Récupération en cas sinistre |
| **Conformité RGPD** | Droit à l'oubli, portabilité, consentement | Légalité du traitement |
| **Isolation des environnements** | Séparation dev/test/prod | Éviter contaminations données |

### 1.3 Profils d'accès proposés

```
┌─────────────────────────────────────────────────────────┐
│ Administrateur Data Warehouse                           │
│ ├─ Accès complet (données identifiées + pseudonymisées) │
│ └─ Gestion infrastructure, backups, audit               │
├─────────────────────────────────────────────────────────┤
│ Analystes / BI                                          │
│ ├─ Accès données pseudonymisées uniquement              │
│ ├─ Lecture seule requêtes de reporting                  │
│ └─ Pas accès données identifiantes brutes               │
├─────────────────────────────────────────────────────────┤
│ Praticiens / Cliniciens                                 │
│ ├─ Accès dashboards agrégés par région/service          │
│ ├─ Pas accès données patients individuels               │
│ └─ Filtrage automatique par périmètre d'activité        │
├─────────────────────────────────────────────────────────┤
│ Administrateurs métier                                  │
│ ├─ Accès données établissements + agrégats              │
│ ├─ Rapports gestion administrative                      │
│ └─ Pas accès données patients sensibles                 │
└─────────────────────────────────────────────────────────┘
```

---

## 2. RÈGLES D'ANONYMISATION

### 2.1 Architecture globale d'anonymisation

**Approche adoptée:** Pseudonymisation + Anonymisation par couches

```
Données brutes (identifiées)
    ↓
[COUCHE 1: Pseudonymisation] → Table intermédiaire avec mapping ID
    ↓
[COUCHE 2: Anonymisation] → Agrégation + Suppression infos sensibles
    ↓
Données accessibles au reporting/BI
```

### 2.2 Détail des règles par source de données

#### **A. TABLE: Hospitalisations**

| Champ | Type de donnée | Règle d'anonymisation | Justification |
|-------|---|---|---|
| `Num_Hospitalisation` | Identifiant | ❌ SUPPRIMER | Identifiant direct du séjour |
| `Id_patient` | Identifiant patient | 🔐 PSEUDONYMISER | Remplacer par hash PATIENT_ID (SHA-256) |
| `identifiant_organisation` | Code établissement | ✅ CONSERVER | Nécessaire pour axes d'analyse |
| `Code_diagnostic` | Donnée médicale | 🔒 GÉNÉRALISER | Grouper par catégorie (ex: "Fracture" au lieu du code spécifique) |
| `Suite_diagnostic_consultation` | Texte diagnostic | ❌ SUPPRIMER | Trop identifiant + informatif |
| `Date_Entree` | Date | 📅 ARRONDIR | Arrondir au 1er du mois (perte précision = + d'anonymité) |
| `Jour_Hospitalisation` | Durée | ✅ CONSERVER | Agrégation sans donner date exacte |

**Pseudonymisation ID_patient:**
```sql
-- Table de mapping sécurisée (accessible admin uniquement)
CREATE TABLE patient_mapping_secure (
    id_patient_original INT,
    id_patient_pseudo VARCHAR(64) UNIQUE,  -- SHA-256 hash
    salt VARCHAR(32),
    created_date TIMESTAMP
);

-- Exemple:
-- ID original: 29620 → Hash: 7a3f8e2c9d1b... (via SHA-256 + salt)
```

---

#### **B. TABLE: Décès**

| Champ | Règle | Justification |
|-------|-------|---|
| `nom`, `prenom` | ❌ SUPPRIMER | PII direct → Identification patient |
| `sexe` | ✅ CONSERVER | Nécessaire pour axes de reporting |
| `date_naissance` | 📅 ARRONDIR | Garder ANNÉE uniquement (cohorte d'âge) |
| `date_deces` | 📅 CONSERVER | Nécessaire pour analyses temporelles (année/mois) |
| `code_lieu_naissance` | ✅ CONSERVER | Données géographiques non identifiantes |
| `code_lieu_deces` | ✅ CONSERVER | Idem - analysable par région |
| `numero_acte_deces` | ❌ SUPPRIMER | Identifiant direct |

**Exemple de transformation:**
```
AVANT:  nom=LANGLET, prenom=ANTOINETTE, date_naissance=1903-11-11, date_deces=1983-04-11
APRÈS: sexe=F, annee_naissance=1903, mois_deces=04, annee_deces=1983, code_lieu_deces=02691
```

---

#### **C. TABLE: Établissements de Santé**

| Champ | Règle | Justification |
|-------|-------|---|
| `raison_sociale_site` | ✅ CONSERVER | Nécessaire pour reporting |
| `adresse`, `numero_voie`, `commune` | ✅ CONSERVER | Géolocalisation établissement OK (non patient) |
| `email`, `telephone`, `telecopie` | ❌ SUPPRIMER | Contact direct = risque sécurité |
| `siren_site`, `siret_site` | ✅ CONSERVER | ID établissement public |
| `finess_etablissement_juridique` | ✅ CONSERVER | Idem |

---

#### **D. TABLE: Satisfaction**

| Champ | Règle | Justification |
|-------|-------|---|
| Identifiant patient (si présent) | 🔐 PSEUDONYMISER | Idem table Hospitalisations |
| Notes textuelles (avis) | 🤐 RÉSUMER | Extraire sentiment (1-5★) au lieu de texte brut |
| Date avis | 📅 ARRONDIR | Arrondir au mois |
| Établissement | ✅ CONSERVER | Axes d'analyse |

---

### 2.3 Processus de pseudonymisation détaillé

**Étape 1: Génération clé maître**
```
clé_maître = KDF(mot_de_passe_admin, salt_global, 100000 itérations)
```

**Étape 2: Pseudonymisation ID patient**
```
patient_id_pseudo = SHA-256(patient_id_original + clé_maître + salt_patient)
Stockage: Table patient_mapping_secure (accès restreint ADMIN only)
```

**Étape 3: Suppression données originales**
```
DELETE FROM hospitalisations_source 
WHERE processed = TRUE  -- Après vérification copie
```

**Étape 4: Vérification intégrité**
```
-- Contrôle: aucun ID original dans tables de reporting
SELECT COUNT(*) FROM hospitalisations_anonymisees 
WHERE id_patient_original IS NOT NULL  -- Doit = 0
```

---

## 3. NON-FUNCTIONAL REQUIREMENTS (NFR)

### 3.1 Performance

| NFR | Objectif | Seuil acceptable |
|-----|----------|---|
| **Temps de requête analytique** | Requête dashboard utilisateur | ≤ 5 secondes (P95) |
| **Latence agrégation données** | ETL job quotidien | ≤ 2 heures (fenêtre de chargement) |
| **Throughput chargement** | Vitesse ETL pour 2M+ hospitalisations | ≥ 10K lignes/sec |
| **Temps scan table** | Query plein diagnostic | ≤ 3 secondes |

**Rationale:** Praticiens & administrateurs doivent exploiter dashboards en temps quasi-réel pour décisions opérationnelles.

### 3.2 Scalabilité & Capacité

| NFR | Objectif | Paramètre |
|-----|----------|---|
| **Croissance données** | Support volume futur | ≥ 10 ans historique (50M+ enregistrements) |
| **Utilisateurs concurrents** | Dashboards BI simultanés | ≥ 50 utilisateurs (pointe) |
| **Taille stockage** | Réserve espace | ≥ 500 GB (données + index + backup) |
| **Nœuds Hive** | Distribution calcul | ≥ 4 nœuds (extensible à 8) |

**Rationale:** CHU doit supporter croissance activité + historique réglementaire 10 ans.

### 3.3 Disponibilité & Fiabilité

| NFR | Objectif | SLA |
|-----|----------|---|
| **Disponibilité service** | Accessibilité des dashboards | 99.5% (hors maintenance) |
| **RTO (Recovery Time Objective)** | Temps restauration après incident | ≤ 4 heures |
| **RPO (Recovery Point Objective)** | Perte données acceptable | ≤ 24 heures (1 jour) |
| **Nombre défaillances tolérées** | Résilience cluster | ≥ 1 nœud can fail (3+ total) |

**Rationale:** Données médicales critiques = faible tolérance perte/indisponibilité.

### 3.4 Sécurité & Conformité

| NFR | Objectif | Exigence |
|-----|----------|---|
| **Conformité RGPD** | Traitement légal données personnelles | ✅ Audit annuel externe |
| **Contrôle accès** | Isolation données par profil | RBAC + contrôle grain fin |
| **Chiffrement données** | Protection données sensibles | AES-256 at-rest + TLS in-transit |
| **Audit trail** | Traçabilité actions | 100% logs accès ≥ 1 an archivé |
| **Conformité santé** | Standard secteur santé | HDS (Hébergement de Données de Santé) certifié |

**Rationale:** Données médicales = conformité légale non-négociable.

### 3.5 Maintenabilité & Opérabilité

| NFR | Objectif | Exigence |
|-----|----------|---|
| **Monitoring alertes** | Détection anomalies | ≥ 90% anomalies détectées < 1h |
| **Logs structures** | Traçabilité opérationnelle | Format JSON centralisé (ELK/Splunk) |
| **Documentation** | Maintenabilité code/architecture | ≥ 90% couverture (docstrings + runbooks) |
| **Backup automation** | Récupération données | Backups quotidiens automatisés (incrémentaux) |
| **Test data isolation** | Éviter contamination | Environnements dev/test/prod séparés |

**Rationale:** Équipe ops doit maintenir système sans dépendre d'experts.

### 3.6 Usabilité (BI/Reporting)

| NFR | Objectif | Métrique |
|-----|----------|---|
| **Temps charger dashboard** | Expérience utilisateur | ≤ 3 secondes |
| **Nombre filtres possibles** | Flexibilité analytique | ≥ 8 dimensions simultanées |
| **Drill-down profondeur** | Navigation données | Minimum 3 niveaux (région → établissement → unité) |
| **Export données** | Self-service analytics | ≥ 3 formats (Excel, CSV, PDF) |

**Rationale:** Praticiens = pas experts BI → interface intuitive obligatoire.

---

## 4. ARCHITECTURE DE SÉCURITÉ GLOBALE

### 4.1 Flux données sécurisé

```
┌──────────────────────────────────────────────────────────────────┐
│                       SOURCES EXTERNES                            │
│  (PostgreSQL / CSV / Fichiers plats)                             │
└────────────────────┬─────────────────────────────────────────────┘
                     │ [TLS 1.3 chiffré]
                     ↓
┌──────────────────────────────────────────────────────────────────┐
│           ZONE D'INTÉGRATION (Staging Layer)                    │
│  ├─ Ingestion données brutes (identifiées)                       │
│  ├─ Validation schéma + intégrité                                │
│  └─ [Accès: Admin + ETL Service Account only]                    │
└────────────────────┬─────────────────────────────────────────────┘
                     │
                     ↓
┌──────────────────────────────────────────────────────────────────┐
│      ANONYMISATION ENGINE (Secure Transformation)                │
│  ├─ Pseudonymisation ID patients (SHA-256 + salt)               │
│  ├─ Généralisation diagnoses                                     │
│  ├─ Arrondissement dates (année/mois)                            │
│  ├─ Suppression champs sensibles                                 │
│  └─ [Clés crypto: Key Management Service - jamais disque]       │
└────────────────────┬─────────────────────────────────────────────┘
                     │
                     ↓
┌──────────────────────────────────────────────────────────────────┐
│    DATA WAREHOUSE (Hive - Données pseudonymisées)               │
│  ├─ Hospitalisations_anonymisees                                 │
│  ├─ Deces_anonymisees                                            │
│  ├─ Etablissements_sanitaires                                    │
│  ├─ Satisfaction_anonymisees                                     │
│  └─ [AES-256 encryption at-rest]                                │
└────────────────────┬─────────────────────────────────────────────┘
                     │
                  [RBAC]
        ┌───────────┼───────────┬──────────────┐
        ↓           ↓           ↓              ↓
    Analysts    Clinicians  Admin      Business
    (Read)      (Filtered)  (Full)     (Aggregated)
        │           │           │              │
        └───────────┴───────────┴──────────────┘
                     │
                     ↓
┌──────────────────────────────────────────────────────────────────┐
│           BUSINESS INTELLIGENCE (Power BI)                       │
│  ├─ Dashboards côté utilisateur                                  │
│  ├─ Row-Level Security (RLS) par profil                          │
│  └─ [TLS 1.3 + authentification AD]                              │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 Table mapping sécurisée (Admin-only)

```
patient_mapping_table
├─ id_patient_original (INT) [PRIMARY KEY]
├─ id_patient_pseudo (VARCHAR 64) [UNIQUE]
├─ salt (VARCHAR 32)
├─ creation_date (TIMESTAMP)
├─ last_access (TIMESTAMP)
└─ accessed_by (VARCHAR 64)

[Stockage: Table cryptée séparée, audit complet, pas backup public]
```

---

## 5. CHECKLIST D'IMPLÉMENTATION

### Phase 1: Conception & Gouvernance
- [ ] Approver architecture anonymisation avec DPO/Legal
- [ ] Définir table mapping patients (clés, salts, stockage)
- [ ] Documenter profils accès utilisateurs
- [ ] Plan de test anonymisation (avant production)

### Phase 2: Développement
- [ ] Implémenter Anonymisation Engine (PySpark / Hive SQL)
  - [ ] Pseudonymisation ID patients (SHA-256 + salt)
  - [ ] Généralisation diagnoses
  - [ ] Arrondissement dates
  - [ ] Suppression champs PII
- [ ] Mettre en place Key Management Service (stockage clés)
- [ ] Implémenter RBAC dans Power BI + Hive
- [ ] Setup audit logging (100% accès tracés)

### Phase 3: Validation & Test
- [ ] Tester sur sample data (non-production)
- [ ] Vérifier aucun PII dans tables anonymisées
  - [ ] Regex pour noms français
  - [ ] Regex pour emails/phones
  - [ ] Manual spot-check 1000 lignes
- [ ] Test performance (NFR latence)
- [ ] Load test 50 utilisateurs concurrents
- [ ] Disaster recovery drill (RTO/RPO test)

### Phase 4: Production & Monitoring
- [ ] Audit de sécurité externe (avant go-live)
- [ ] Setup monitoring + alertes (performance + anomalies)
- [ ] Processus backup quotidien automatisé
- [ ] Formation utilisateurs (accès BI, no access PII)
- [ ] Documentation runbooks pour ops

---

## 6. RÉFÉRENCES & CONFORMITÉ

### Cadre légal
- **RGPD** (UE 2016/679) → Droit à l'oubli, traitement proportionné
- **Loi santé française** (ANSSI) → Protection données sensibles
- **HDS (Hébergement Données Santé)** → Certification obligatoire
- **ISO 27001** → Standard sécurité informatique

### Documents à produire
- [ ] Registre RGPD (traitements de données)
- [ ] Analyse Impact Vie Privée (DPIA)
- [ ] Plan de réponse incidents
- [ ] Guide sécurité utilisateurs

---

## 7. MATRICE RESPONSABILITÉS

| Tâche | Propriétaire | Validation |
|------|---|---|
| Architecture anonymisation | Chloé | Julian + Maxime |
| Implémentation ETL anonymisation | Chloé + Matthieu | Maxime (perf) |
| Setup RBAC / Accès | Julian | Chloé (conformité) |
| Testing anonymisation | Chloé + Matthieu | Maxime + Julian |
| Documentation sécurité | Chloé | Tous |
| Audit de conformité | Julian | Chloé |

---

**Version:** 1.0  
**Date création:** 01/06/2026  
**Dernier modifié:** 01/06/2026  
**Approuvé par:** [À valider]
