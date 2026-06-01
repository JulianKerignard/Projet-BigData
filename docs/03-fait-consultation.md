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

**Une ligne = une consultation** (identifiée par `Num_consultation`).

C'est le grain le plus fin possible et il permet d'agréger sur tous les axes (temps, patient, professionnel, diagnostic).

## Modèle de la table de faits

```
Fait_Consultation
├── temps_key          (FK -> Dim_Temps)            -- depuis Consultation.Date
├── patient_key        (FK -> Dim_Patient)          -- depuis Consultation.Id_patient
├── professionnel_key  (FK -> Dim_Professionnel)    -- depuis Consultation.Id_prof_sante
├── diagnostic_key     (FK -> Dim_Diagnostic)       -- depuis Consultation.Code_diag
├── etablissement_key  (FK -> Dim_Etablissement)    -- ⚠️ voir note ci-dessous
├── num_consultation   (dimension dégénérée)        -- traçabilité vers la source
├── motif              (dimension dégénérée)         -- motif textuel
├── nb_consultation    (mesure)                     -- = 1, additive
└── duree_minutes      (mesure)                     -- Heure_fin - Heure_debut, additive
```

### Clés de dimension (FK)

| Clé | Dimension | Source |
|-----|-----------|--------|
| temps_key | Dim_Temps | `Consultation.Date` |
| patient_key | Dim_Patient | `Consultation.Id_patient` |
| professionnel_key | Dim_Professionnel | `Consultation.Id_prof_sante` |
| diagnostic_key | Dim_Diagnostic | `Consultation.Code_diag` |
| etablissement_key | Dim_Etablissement | ⚠️ non présent dans la source |

### Mesures

| Mesure | Type | Calcul | Additivité |
|--------|------|--------|-----------|
| nb_consultation | Compteur | `1` par ligne | Additive (SUM) |
| duree_minutes | Numérique | `Heure_fin - Heure_debut` | Additive |

Le « taux de consultation » des besoins se calcule à partir de `SUM(nb_consultation)` rapporté à l'axe d'analyse (établissement, diagnostic, professionnel) sur la période.

### Dimensions dégénérées

- `num_consultation` : conservée dans le fait (pas de dimension dédiée), pour la traçabilité.
- `motif` : texte libre, conservé comme attribut dégénéré (pas d'axe d'analyse demandé dessus).

## ⚠️ Point d'attention : besoin établissement (B1)

La table source `Consultation` **ne contient aucun identifiant d'établissement**. Le besoin B1 (« taux de consultation par établissement ») ne peut donc pas être satisfait en l'état directement depuis cette source.

Hypothèses à trancher en équipe :
1. **Établissement unique** : les consultations relèvent du seul CHU → `etablissement_key` pointe vers un établissement par défaut.
2. **Dérivation** : rattacher la consultation à un établissement via le professionnel de santé (si un mapping prof → établissement existe).
3. **Hors périmètre consultation** : l'axe établissement concerne surtout les hospitalisations ; B1 serait alors traité côté `Fait_Hospitalisation`.

> À valider lors de la review croisée. La FK `etablissement_key` est modélisée par anticipation mais son alimentation dépend de l'hypothèse retenue.

## Correspondance besoins → modèle

| Besoin | Axes (dimensions) | Mesure | Couvert |
|--------|-------------------|--------|:-------:|
| B1 Consultation par établissement / période | Établissement + Temps | nb_consultation | ⚠️ (voir note) |
| B2 Consultation par diagnostic / période | Diagnostic + Temps | nb_consultation | ✅ |
| B6 Consultation par professionnel | Professionnel | nb_consultation | ✅ |

## Notes d'implémentation (pour le Livrable 2)

- Table Hive en **Parquet**, **partitionnée par `annee`** (ou `annee/mois`) de la dimension Temps → élague les scans sur les requêtes « par période ».
- **Bucketing** envisageable sur `professionnel_key` ou `diagnostic_key` selon les requêtes les plus fréquentes (à valider en phase optimisation).
- Chargement **après** les dimensions (intégrité référentielle).
