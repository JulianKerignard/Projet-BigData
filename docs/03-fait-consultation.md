# Fait_Consultation

Modélisation de la table de faits **Fait_Consultation** du schéma en étoile.

Couvre les besoins utilisateurs liés aux consultations :
- B1 — Taux de consultation par établissement sur une période
- B2 — Taux de consultation par diagnostic sur une période
- B6 — Taux de consultation par professionnel

## Source

Dump PostgreSQL (`DATA 2024/BDD PostgreSQL/DATA2023`), table opérationnelle `Consultation` :

```sql
CREATE TABLE public."Consultation" (
    "Num_consultation" integer NOT NULL,   -- identifiant unique de la consultation
    "Id_mut"           integer,            -- mutuelle
    "Id_patient"       integer,            -- -> Patient
    "Id_prof_sante"    varchar,            -- -> Professionnel_de_sante
    "Code_diag"        varchar,            -- -> Diagnostic
    "Motif"            varchar,            -- motif de consultation
    "Date"             date,               -- date de la consultation
    "Heure_debut"      time,
    "Heure_fin"        time
);
```

Tables de référence associées (alimentent les dimensions) : `Patient`, `Professionnel_de_sante`, `Diagnostic`, `Specialites`.

## Grain

**Une ligne = une consultation** (`Num_consultation` dans la source ; identifiée dans le fait par le surrogate `consultation_key`).

C'est le grain le plus fin possible et il permet d'agréger sur tous les axes (temps, patient, professionnel, diagnostic).

## Modèle de la table de faits

```
Fait_Consultation
├── consultation_key   (PK surrogate)               -- clé technique générée (grain)
├── temps_key          (FK -> Dim_Temps)            -- depuis Consultation.Date
├── patient_key        (FK -> Dim_Patient)          -- depuis Consultation.Id_patient (pseudonymisé)
├── professionnel_key  (FK -> Dim_Professionnel)    -- depuis Consultation.Id_prof_sante
├── diagnostic_key     (FK -> Dim_Diagnostic)       -- depuis Consultation.Code_diag
├── nb_consultation    (mesure)                     -- = 1, additive
└── duree_minutes      (mesure)                     -- Heure_fin - Heure_debut, additive
```

> **Conformité sécurité** (cf. `docs/Securite_Anonymisation_NFR.md`) : le modèle a été ajusté pour respecter le document d'anonymisation.
> - `num_consultation` (identifiant direct, §2.2) **retiré** → remplacé par le surrogate `consultation_key` qui préserve le grain sans exposer l'ID source.
> - `motif` (texte libre, §2.2) **retiré** (aucun besoin + risque PII, minimisation RGPD).
> - `Id_patient` **pseudonymisé** (SHA-256, §2.3) avant alimentation de Dim_Patient.

### Clés de dimension (FK)

| Clé | Dimension | Source |
|-----|-----------|--------|
| temps_key | Dim_Temps | `Consultation.Date` |
| patient_key | Dim_Patient | `Consultation.Id_patient` |
| professionnel_key | Dim_Professionnel | `Consultation.Id_prof_sante` |
| diagnostic_key | Dim_Diagnostic | `Consultation.Code_diag` |

### Mesures

| Mesure | Type | Calcul | Additivité |
|--------|------|--------|-----------|
| nb_consultation | Compteur | `1` par ligne | Additive (SUM) |
| duree_minutes | Numérique | `Heure_fin - Heure_debut` | Additive |

Le « taux de consultation » des besoins se calcule à partir de `SUM(nb_consultation)` rapporté à l'axe d'analyse (établissement, diagnostic, professionnel) sur la période.

### Clé de substitution

- `consultation_key` : surrogate key technique (générée au chargement) servant de clé primaire du fait et préservant le grain (une ligne = une consultation), sans exposer l'identifiant source `Num_consultation` (retiré pour conformité §2.2).

## Besoin établissement (B1) : non applicable aux consultations

**Conclusion (vérifiée sur la source)** : la base PostgreSQL des consultations est un système **mono-établissement**. Le besoin B1 (« taux de consultation par établissement ») n'est donc pas applicable à ce fait — il n'existe qu'un seul établissement.

Preuve (analyse des 12 tables du dump) :
- Aucune colonne établissement / FINESS / organisation dans aucune table.
- `Consultation` ne référence aucun établissement (ni directement, ni via `Patient`, `Mutuelle`, `Diagnostic`).
- `Professionnel_de_sante` est identifié par un numéro **ADELI** (annuaire national), sans affiliation d'établissement.
- `Salle` décrit des **blocs / étages / salles d'un même site** (7 blocs `Bloc-A`…`Bloc-F`), pas des établissements distincts.

→ L'axe établissement est porté par les **autres faits** qui disposent d'un code établissement : `Fait_Hospitalisation` (`identifiant_organisation`) et `Fait_Satisfaction` (`finess_geo`). La FK `etablissement_key` est donc retirée du modèle `Fait_Consultation` (pas de source pour l'alimenter).

## Correspondance besoins → modèle

| Besoin | Axes (dimensions) | Mesure | Couvert |
|--------|-------------------|--------|:-------:|
| B1 Consultation par établissement / période | Établissement + Temps | nb_consultation | N/A — source mono-établissement (porté par Hospitalisation / Satisfaction) |
| B2 Consultation par diagnostic / période | Diagnostic + Temps | nb_consultation | ✅ |
| B6 Consultation par professionnel | Professionnel | nb_consultation | ✅ |

## Notes d'implémentation (pour le Livrable 2)

- Table Hive en **Parquet**, **partitionnée par `annee`** (ou `annee/mois`) de la dimension Temps → élague les scans sur les requêtes « par période ».
- **Bucketing** envisageable sur `professionnel_key` ou `diagnostic_key` selon les requêtes les plus fréquentes (à valider en phase optimisation).
- Chargement **après** les dimensions (intégrité référentielle).
