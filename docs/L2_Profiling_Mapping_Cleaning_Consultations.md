# Profiling + Mapping + Cleaning - Consultations

**Livrable:** L2 - Modèle physique & optimisation
**Tâche:** [P1] Profiling + mapping + cleaning Consultations
**Date:** Juin 2026
**Responsable:** Julian

Scripts associés :
- Profiling reproductible : `sql/profiling/consultations_profiling.sql`
- Nettoyage HiveQL : `sql/cleaning/consultations_cleaning.hql`

---

## 1. PROFILING DE LA SOURCE

Profiling réalisé sur la base PostgreSQL réelle (dump `DATA2023` restauré), table `Consultation` et ses référentiels.

### 1.1 Volumétrie

| Table | Lignes |
|-------|-------:|
| Consultation | 1 027 157 |
| Patient | 100 000 |
| Professionnel_de_sante | 1 048 575 |
| Diagnostic | 15 490 |
| Specialites | 93 |

### 1.2 Complétude (table Consultation)

| Indicateur | Résultat |
|-----------|---------:|
| Valeurs nulles (toutes colonnes) | **0** |
| Doublons sur `Num_consultation` | **0** |

→ Source **complète**, clé naturelle propre.

### 1.3 Cohérence temporelle

| Indicateur | Résultat |
|-----------|---------:|
| Plage de dates | 2015-06-20 → 2023-03-31 |
| Heure incohérente (`fin < début`) | **10** |
| Durée nulle (`fin = début`) | 0 |

### 1.4 Intégrité référentielle (FK)

| Lookup | Orphelins |
|--------|----------:|
| Consultation → Patient | **0** |
| Consultation → Professionnel_de_sante | **0** |
| Consultation → Diagnostic | **0** |

→ Intégrité **parfaite** : tous les lookups de dimensions résoudront.

### 1.5 Cardinalités

| Axe | Valeurs distinctes |
|-----|-------------------:|
| Patients | 100 000 |
| Professionnels | 201 735 |
| Diagnostics | 15 487 |
| Motifs | 58 |

### 1.6 Qualité des attributs dimensionnels (Patient)

| Attribut | Constat |
|----------|---------|
| `Sexe` | 2 valeurs : `male` (40 781), `female` (59 219) — **en anglais, à standardiser** |
| `Age` | 0 → 100, **aucune valeur aberrante** |

### 1.7 Répartition par année (planification du partitionnement)

| Année | Consultations |
|------:|--------------:|
| 2015 | 33 896 |
| 2016 | 184 308 |
| 2017 | 133 403 |
| 2018 | 160 373 |
| 2019 | 87 497 |
| 2020 | 162 778 |
| 2021 | 145 883 |
| 2022 | 101 991 |
| 2023 | 17 028 |

→ Volume réparti sur **9 années** → le **partitionnement par `annee`** est pertinent (partitions de taille raisonnable, élagage efficace sur les requêtes « par période »).

### Synthèse profiling

La source Consultations est de **très bonne qualité** : aucune valeur manquante, aucune clé dupliquée, intégrité référentielle parfaite. Le nettoyage requis est donc **léger** et se limite à :
1. la correction de **10 lignes** à horaire incohérent ;
2. la **standardisation du sexe** patient (`male`/`female` → `M`/`F`).

---

## 2. MAPPING SOURCE → CIBLE

Correspondance entre les colonnes source (`Consultation`) et le modèle `Fait_Consultation` (cf. `docs/03-fait-consultation.md`).

| Colonne source | Type source | Cible (Fait_Consultation) | Transformation |
|----------------|-------------|---------------------------|----------------|
| `Num_consultation` | INTEGER | `num_consultation` (dim. dégénérée) | CAST INT |
| `Date` | DATE | `temps_key` (FK) | lookup Dim_Temps sur la date |
| `Id_patient` | INTEGER | `patient_key` (FK) | pseudonymisation puis lookup Dim_Patient |
| `Id_prof_sante` | VARCHAR | `professionnel_key` (FK) | lookup Dim_Professionnel |
| `Code_diag` | VARCHAR | `diagnostic_key` (FK) | NULL/'' → 'UNKNOWN', lookup Dim_Diagnostic |
| `Motif` | VARCHAR | `motif` (dim. dégénérée) | conservé tel quel |
| `Heure_debut`, `Heure_fin` | TIME | `duree_minutes` (mesure) | (fin - début) en minutes ; NULL si incohérent |
| — | — | `nb_consultation` (mesure) | constante = 1 |
| `Id_mut` | INTEGER | *(non repris)* | hors besoins |
| — | — | `etablissement_key` (FK) | ⚠️ source sans établissement (cf. B1) |

---

## 3. RÈGLES DE CLEANING

Implémentées dans `sql/cleaning/consultations_cleaning.hql` (Bronze → Silver).

| # | Règle | Action | Volume concerné |
|---|-------|--------|-----------------|
| R1 | Déduplication sur `num_consultation` | `ROW_NUMBER()`, garder 1 ligne | 0 (défensif) |
| R2 | Clé obligatoire manquante (`num`, `patient`, `date`) | rejet de la ligne | 0 (défensif) |
| R3 | `code_diag` NULL ou vide | remplacé par `'UNKNOWN'` | 0 constaté |
| R4 | Date hors plage 2015-2023 | rejet de la ligne | 0 constaté |
| R5 | Heure incohérente (`fin < début`) | `duree_minutes` mise à NULL | **10** |
| R6 | Sexe patient `male`/`female` | standardisé `M`/`F` (Dim_Patient) | 100 000 |

Règles R1, R2, R4 conservées comme **filets de sécurité** pour les rechargements futurs, même si le profiling n'a rien détecté actuellement.

### Contrôles qualité post-nettoyage

Le script se termine par 3 contrôles qui doivent renvoyer 0 / un écart justifié :
- doublons résiduels = 0
- durées négatives = 0
- réconciliation des volumes Bronze vs Silver (écart = lignes rejetées par R2/R4)

---

## 4. VALIDATION DU PIPELINE (test sur données réelles)

Les règles de nettoyage ont été **exécutées et vérifiées** sur les données réelles (dump `DATA2023` restauré). Pour tester les règles défensives (la source étant trop propre), **6 cas sales ont été injectés** dans la couche Bronze, puis le pipeline a été lancé.

| Règle | Cas testé | Résultat attendu | Vérifié |
|-------|-----------|------------------|:-------:|
| R1 déduplication | doublon d'une consultation existante | ligne dédupliquée (−1) | ✅ |
| R2 clés obligatoires | `id_patient` NULL + `date` NULL | 2 lignes rejetées | ✅ |
| R3 `code_diag` vide | `code_diag = ''` | valeur → `'UNKNOWN'` | ✅ |
| R4 date hors plage | date `2099-01-01` | ligne rejetée | ✅ |
| R5 horaire incohérent | `fin < début` (10 réelles + 1 injectée) | `duree_minutes` = NULL (11), 0 négative | ✅ |
| R6 sexe `male`/`female` | 100 000 patients | → `M`/`F`, 0 non mappé | ✅ |

**Réconciliation des volumes** (Bronze → Silver) :

| Étape | Lignes |
|-------|-------:|
| Bronze (avec 6 cas injectés) | 1 027 163 |
| Après R1 (déduplication) | 1 027 162 |
| Après R2 (clés obligatoires) | 1 027 160 |
| Silver final (après R4 plage de dates) | 1 027 159 |

**Contrôles qualité finaux** : doublons résiduels = 0, durées négatives = 0.

> Sur les données réelles seules (sans injection), le pipeline ne rejette aucune ligne et corrige uniquement les 10 horaires incohérents → cohérent avec un profiling de très bonne qualité.

---

## 5. POINT OUVERT

**Besoin B1 (établissement)** : la table source `Consultation` ne porte aucun identifiant d'établissement. La FK `etablissement_key` reste en attente de l'arbitrage d'équipe (cf. `docs/03-fait-consultation.md`). Ce point ne concerne pas le cleaning lui-même mais le mapping de cette FK.
