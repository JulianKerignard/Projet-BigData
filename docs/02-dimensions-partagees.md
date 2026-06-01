# Dimensions partagées (conformes)

Modélisation des **dimensions conformes** réutilisées par plusieurs faits. Elles sont définies **une seule fois** en commun, avant le travail parallèle sur chaque fait, afin de garantir la cohérence des axes d'analyse de l'entrepôt.

> Premier jet à valider en équipe. Chaque membre s'appuie ensuite sur ces dimensions pour modéliser son fait.

## Matrice en bus (faits × dimensions)

Croisement des dimensions avec les 4 faits du projet.

| Dimension | Consultation | Hospitalisation | Satisfaction | Décès |
|-----------|:---:|:---:|:---:|:---:|
| Dim_Temps | ✅ | ✅ | ✅ | ✅ |
| Dim_Etablissement | ✅ | ✅ | ✅ | — |
| Dim_Geographie | ✅ | ✅ | ✅ | ✅ |
| Dim_Patient | ✅ | ✅ | — | — |
| Dim_Diagnostic | ✅ | ✅ | — | — |
| Dim_Professionnel | ✅ | — | — | — |

Dimensions **réellement partagées** (≥ 2 faits) : Temps, Établissement, Géographie, Patient, Diagnostic. `Dim_Professionnel` est spécifique aux consultations.

## Détail des dimensions

### Dim_Temps
Axe temporel commun à tous les faits (besoins « sur une période Y », « année 2019/2020 »).

| Attribut | Type | Description |
|----------|------|-------------|
| temps_key | INT (PK) | Clé technique (ex. AAAAMMJJ) |
| date | DATE | Date complète |
| jour | INT | Jour du mois |
| mois | INT | Numéro de mois |
| libelle_mois | STRING | Nom du mois |
| trimestre | INT | Trimestre (1-4) |
| annee | INT | Année |

### Dim_Etablissement
Référentiel des établissements de santé (source : CSV établissements de France).

| Attribut | Type | Description |
|----------|------|-------------|
| etablissement_key | INT (PK) | Clé technique |
| id_etablissement | STRING | Identifiant source (FINESS) |
| nom | STRING | Nom de l'établissement |
| type | STRING | Type (CHU, clinique, …) |
| region | STRING | Région |
| departement | STRING | Département |

### Dim_Geographie
Axe géographique pour les analyses par région (besoins décès / satisfaction par région).

| Attribut | Type | Description |
|----------|------|-------------|
| geographie_key | INT (PK) | Clé technique |
| code_region | STRING | Code région |
| region | STRING | Libellé région |
| code_departement | STRING | Code département |
| departement | STRING | Libellé département |
| commune | STRING | Commune |

### Dim_Patient
Caractéristiques patients (besoins par sexe / âge). **Pseudonymisée** dès la couche Silver.

| Attribut | Type | Description |
|----------|------|-------------|
| patient_key | INT (PK) | Clé technique |
| id_patient_anonyme | STRING | Identifiant pseudonymisé (hash) |
| sexe | STRING | Sexe |
| tranche_age | STRING | Tranche d'âge (regroupement) |

### Dim_Diagnostic
Référentiel des diagnostics (besoins « par diagnostic »).

| Attribut | Type | Description |
|----------|------|-------------|
| diagnostic_key | INT (PK) | Clé technique |
| code_diagnostic | STRING | Code (ex. CIM-10) |
| libelle | STRING | Libellé du diagnostic |
| categorie | STRING | Catégorie / chapitre |

### Dim_Professionnel
Professionnels de santé (besoin « taux de consultation par professionnel »). Spécifique aux consultations mais modélisée ici pour cohérence.

| Attribut | Type | Description |
|----------|------|-------------|
| professionnel_key | INT (PK) | Clé technique |
| id_professionnel | STRING | Identifiant source |
| specialite | STRING | Spécialité médicale |

## Conventions

- Toutes les dimensions utilisent une **clé technique de substitution** (`*_key`, surrogate key) distincte de l'identifiant source.
- Les libellés sont conservés en clair ; seules les données patients sont pseudonymisées.
- Les dimensions sont chargées **avant** les faits (intégrité référentielle).
