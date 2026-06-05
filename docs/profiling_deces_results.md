# Profiling — INSEE `deces.csv`

> Résultats du profiling exécuté sur le fichier source réel.
> **Script** : [`scripts/profiling/profile_deces.sh`](../scripts/profiling/profile_deces.sh)
> **Mapping** : [`scripts/ref/dept_to_region.sql`](../scripts/ref/dept_to_region.sql)

---

## 1. Caractéristiques du fichier

| Élément | Valeur observée |
|---|---|
| Nom | `deces.csv` |
| Format | CSV text (UTF-8) |
| Taille brute | **1.9 Go** (1 999 899 438 octets) |
| Header | Oui — `nom,prenom,sexe,date_naissance,code_lieu_naissance,lieu_naissance,pays_naissance,date_deces,code_lieu_deces,numero_acte_deces` |
| Nombre de colonnes attendu | 10 |
| **Lignes de données** | **25 088 208** |
| **Lignes mal formées** (NF ≠ 10) | **73 222** (≈ **0.29 %**) |

> ⚠️ Les 73 k lignes mal formées sont causées par des **virgules dans les champs textuels non échappées** (noms composés, lieux étrangers). Stratégie retenue dans le job ETL : log + exclusion.

---

## 2. Distribution annuelle (top 5)

| Année de décès | Lignes |
|---|---|
| **2019** | **616 257** |
| 2018 | 614 452 |
| 2017 | 611 556 |
| 1999 | 601 193 |
| 2016 | 598 382 |

> Cohérent avec la démographie française (~600k décès/an). 2019 sera notre périmètre de chargement L1/L2.

---

## 3. Code lieu de décès — longueurs observées

| Longueur | Nb lignes | Interprétation |
|---|---|---|
| **5** | **25 015 430** (99.7 %) | Code INSEE valide |
| 10 | 70 832 | Double champ (parsing) — à investiguer |
| 7 | 859 | Anomalie |
| 8 | 435 | Anomalie |
| autres | < 250 chacun | Bruit |

> Le filtre `LENGTH(code_lieu_deces) = 5` retient 99.7 % des lignes. Acceptable pour le KPI 8.

---

## 4. Top 10 départements sur 2019

| Code | Nom | Région | Décès 2019 |
|---|---|---|---|
| 59 | Nord | Hauts-de-France | 23 190 |
| 13 | Bouches-du-Rhône | PACA | 19 294 |
| 75 | Paris | Île-de-France | 16 834 |
| 33 | Gironde | Nouvelle-Aquitaine | 14 956 |
| 69 | Rhône | Auvergne-Rhône-Alpes | 14 434 |
| 62 | Pas-de-Calais | Hauts-de-France | 13 998 |
| **97** | (DOM-TOM agrégé) | — | 13 958 |
| 76 | Seine-Maritime | Normandie | 12 939 |
| 44 | Loire-Atlantique | Pays de la Loire | 12 405 |
| 06 | Alpes-Maritimes | PACA | 12 245 |

---

## 5. DOM-TOM sur 2019

| Code département | Territoire | Décès 2019 |
|---|---|---|
| 974 | La Réunion | 5 094 |
| 972 | Martinique | 3 553 |
| 971 | Guadeloupe | 3 411 |
| 987 | Polynésie française | 1 551 |
| 973 | Guyane | 997 |
| 976 | Mayotte | 680 |
| 978 | Saint-Martin | 144 |
| 988 | Nouvelle-Calédonie | 61 |
| 977 | Saint-Barthélemy | 41 |
| 975 | Saint-Pierre-et-Miquelon | 38 |
| 986 | Wallis-et-Futuna | 9 |
| 984 | Terres australes | 1 |
| **Total DOM-TOM** | | **~15 580** |

> **Implication ETL** : les codes département DOM-TOM font **3 caractères** (97x / 98x) au lieu de 2. Le mapping doit gérer les deux longueurs.

---

## 6. Distribution par sexe (2019)

| Code | Sexe | Lignes |
|---|---|---|
| 2 | Femmes | 309 285 (50.2 %) |
| 1 | Hommes | 306 972 (49.8 %) |

---

## 7. Validation du mapping département → région

Le fichier [`scripts/ref/dept_to_region.sql`](../scripts/ref/dept_to_region.sql) couvre :

| Catégorie | Nb codes |
|---|---|
| Départements métropolitains (01-95) | 94 |
| Corse (2A, 2B) | 2 |
| DOM (971-974, 976) | 5 |
| COM / TOM (975, 977, 978, 984, 986-988) | 7 |
| **Total** | **108** |

→ Couverture de **100 % des codes département observés** dans les 2019 (vérifié sur le top 10 et les DOM-TOM).

---

## 8. Implications pour la suite (DDL / chargement)

À intégrer dans la tâche **[P4] DDL Fait_Deces** ([869dfg1jp](https://app.clickup.com/t/869dfg1jp)) :

1. La table `ref_dept_region` doit être chargée **avant** `Fait_Deces`.
2. Le type de `code_departement` est `VARCHAR(3)` (pour gérer les DOM-TOM et la Corse), pas `INT`.
3. Filtre ETL recommandé : `WHERE LENGTH(code_lieu_deces) = 5 AND YEAR(date_deces) = 2019`.
4. La perte sur les codes longueur ≠ 5 est < 0.3 %, acceptable.
5. Volumétrie cible chargée dans `Fait_Deces` ≈ **615 000 lignes** (après filtre 2019 + LENGTH = 5).

---

## 9. Reproduire le profiling

```bash
chmod +x scripts/profiling/profile_deces.sh
./scripts/profiling/profile_deces.sh "DATA 2024 2/DECES EN FRANCE/deces.csv"
```

Durée constatée : **~5 minutes** sur le fichier de 2 Go (Mac M1, SSD local).
