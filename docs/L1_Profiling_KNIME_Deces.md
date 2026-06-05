# Profiling Décès en KNIME — Livrable L1 P4

> **Tâche** : profiling visuel du fichier INSEE `deces.csv` (1.9 Go, 25 M lignes).
> **Complément du profiling shell** : [`scripts/profiling/profile_deces.sh`](../scripts/profiling/profile_deces.sh).
> **Workflow** : [`knime/Deaths_Profiling.knwf`](../knime/Deaths_Profiling.knwf).
> **Résultats bruts** : [`knime/Deaths_Profiling/output/`](../knime/Deaths_Profiling/output/).

---

## 1. Pourquoi KNIME en plus du shell

Le profiling shell (`profile_deces.sh`) tourne en 5 min mais sort du texte stdout difficile à inclure dans le rapport et faillible sur le parsing CSV (split naïf sur la virgule). Le workflow KNIME apporte :

- **Parsing CSV correct** : respecte les guillemets, donc gère les noms composés avec virgules.
- **Visualisations** : Bar Chart + Pie Chart exportables en image pour le rapport.
- **Exports CSV** : résultats consommables par Excel ou Power BI.

Les deux outils sont complémentaires et donnent les mêmes décisions ETL en aval.

## 2. Structure du workflow

```
CSV Reader (deces.csv 1.9 Go)
  │
  ├─→ String Manipulation (extract annee_deces)
  │     │
  │     ├─→ GroupBy annee → Sorter → Column Renamer → CSV Writer
  │     │       └─→ Bar Chart (distribution annuelle)
  │     │
  │     ├─→ String Manipulation (length code_lieu_deces)
  │     │     └─→ GroupBy length → Column Renamer → CSV Writer
  │     │           └─→ Bar Chart (distribution longueur)
  │     │
  │     └─→ Row Filter (annee=2019)
  │           │
  │           ├─→ String Manipulation (extract code_dept, regex DOM-TOM)
  │           │     └─→ GroupBy dept → Sorter → Top K (10) → Column Renamer → CSV Writer
  │           │           └─→ Bar Chart (top 10 départements 2019)
  │           │
  │           └─→ GroupBy sexe → Column Renamer → CSV Writer
  │                 └─→ Pie Chart (répartition sexe 2019)
```

## 3. Résultats produits

### 3.1 Distribution annuelle ([CSV](../knime/Deaths_Profiling/output/distribution_annuelle.csv))

| Année | Nb_décès |
|---|---|
| 2016 | 602 285 |
| 2017 | 615 519 |
| 2018 | 618 433 |
| **2019** | **620 628** |
| 2020 | 156 857 (partiel) |

### 3.2 Distribution longueur `code_lieu_deces` ([CSV](../knime/Deaths_Profiling/output/distribution_longueur_code_lieu.csv))

| Longueur | Nb lignes | % |
|---|---|---|
| 5 | 25 077 272 | **99,96 %** |
| 2 | 2 | < 0,01 % |
| NULL | 10 934 | 0,04 % |

→ **Le filtre `LENGTH(code_lieu_deces) = 5` dans le cleaning Hive perd 0,04 %** (vs 0,3 % estimé au shell). Le fichier est plus propre que le shell ne le disait : le parsing KNIME (avec guillemets) ne se trompe pas sur les noms composés.

### 3.3 Top 10 départements 2019 ([CSV](../knime/Deaths_Profiling/output/top10_departements_2019.csv))

| Code | Département | Décès 2019 |
|---|---|---|
| 59 | Nord | 23 246 |
| 13 | Bouches-du-Rhône | 19 358 |
| 75 | Paris | 17 264 |
| 33 | Gironde | 15 053 |
| 69 | Rhône | 14 612 |
| 62 | Pas-de-Calais | 14 010 |
| 76 | Seine-Maritime | 12 967 |
| 44 | Loire-Atlantique | 12 429 |
| 06 | Alpes-Maritimes | 12 332 |
| 34 | Hérault | 11 615 |

### 3.4 Répartition sexe 2019 ([CSV](../knime/Deaths_Profiling/output/repartition_sexe_2019.csv))

| Sexe (code) | Décès | % |
|---|---|---|
| 1 (M) | 309 433 | 49,85 % |
| 2 (F) | 311 195 | 50,15 % |

## 4. Logique technique clé

### 4.1 Extraction de l'année
```
String Manipulation : substr($date_deces$, 0, 4) → annee_deces
```

### 4.2 Extraction du département avec gestion DOM-TOM
```
regexReplace($code_lieu_deces$,
             "^(9[78][0-9])[0-9]{2}$|^([0-9]{2})[0-9]{3}$",
             "$1$2")
```
- "02691" → "02" (métropole, 2 chars)
- "97411" → "974" (Réunion, 3 chars)
- "98701" → "987" (Polynésie, 3 chars)

## 5. Décisions ETL alimentées par ce profiling

| Constat KNIME | Décision en HiveQL aval |
|---|---|
| 25 M lignes, 10 colonnes, UTF-8 | Format `ROW FORMAT DELIMITED FIELDS TERMINATED BY ','` |
| 99,96 % des codes lieu font 5 chars | Filtre `LENGTH(code_lieu_deces) = 5` |
| DOM-TOM en codes 97x/98x (3 chars) | `CASE WHEN substr(...,1,2) IN ('97','98') THEN substr(...,1,3) ELSE substr(...,1,2)` |
| 620 628 décès 2019 ≈ cible KPI 8 | Validation aval du chargement Gold |
| ~10 k lignes avec `code_lieu_deces` NULL | Filtre `code_lieu_deces IS NOT NULL` ou COALESCE 'INCONNU' |

## 6. Reproductibilité

```bash
# 1. Ouvrir KNIME
# 2. Import workflow : knime/Deaths_Profiling.knwf
# 3. Configurer le chemin du CSV source dans le node CSV Reader
# 4. Execute all (F8)
# 5. Résultats dans knime/Deaths_Profiling/output/
```

## 7. Definition of Done

- [x] Workflow visuel produit 4 fichiers CSV de résultats
- [x] Distribution annuelle exportée
- [x] Distribution longueur code lieu exportée (justifie filtre LENGTH=5)
- [x] Top 10 départements 2019 exporté (incluant gestion DOM-TOM)
- [x] Répartition sexe 2019 exportée
- [x] Workflow exporté en .knwf pour reproductibilité
- [x] Doc d'accompagnement écrit
