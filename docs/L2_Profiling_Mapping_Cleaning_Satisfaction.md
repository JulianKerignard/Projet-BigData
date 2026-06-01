# Profiling + Mapping + Cleaning — Satisfaction

**Livrable :** L2 — Modèle physique & optimisation
**Tâche :** [P3] Profiling + mapping + cleaning Satisfaction (869dh1d8b)
**Date :** Juin 2026
**Responsable :** Matthieu (P3)

Scripts associés :
- Profiling Python (encoding/séparateur fichiers plats) : `scripts/satisfaction_profiling.py`
- Profiling HiveQL (sur staging) : `sql/profiling/satisfaction_profiling.sql`
- Nettoyage HiveQL (Bronze → Silver + rejets) : `sql/cleaning/satisfaction_cleaning.hql`

> Source **la plus « salissante »** du projet (fichiers plats e-Satis / IQSS à encodage et
> schéma variables). Le profiling et le cleaning sont critiques : sans eux, le chargement plante.

---

## 1. PROFILING DE LA SOURCE

Profiling exécuté sur les fichiers réels `DATA 2024/Satisfaction/` (série **e-Satis 48h MCO**,
qui porte le score de satisfaction global ajusté `score_all_rea_ajust`) via
`scripts/satisfaction_profiling.py`.

### 1.1 Encodage & format (par fichier)

| Année (campagne) | Fichier | Format | Encodage réel | Séparateur | En-tête | Colonnes | Lignes |
|---|---|---|---|---|---:|---:|---:|
| 2017 | `ESATIS48H_MCO_recueil2017_donnees.csv` | CSV | **ISO-8859-1 / CP1252** | `;` | oui | **23** | 1157 |
| 2019 | `resultats-esatis48h-mco-open-data-2019.csv` | CSV | **ISO-8859-1 / CP1252** | `;` | oui | **25** | 1152 |
| 2020 | `resultats-esatis48h-mco-open-data-2020.xlsx` | XLSX | UTF-8 (interne au zip) | — (xlsx) | oui | **25** | 1150 |

Constats :
- **Encodage Latin-1/CP1252** sur les CSV : lus en UTF-8, les libellés régions ressortent en
  mojibake (`Auvergne-Rh�ne-Alpes`). La détection automatique (`chardet`) est **peu fiable** ici
  (confiance ≈ 0.01, étiquette `iso8859-2/3`) → on **force** `iconv -f CP1252 -t UTF-8`, validé
  par `file -i`. Lus en Latin-1, **0 mojibake** sur les 17 régions (encodage confirmé).
- **Dérive de schéma** : 2017 = 23 colonnes, 2019/2020 = 25 (ajout `taux_reco_brut`,
  `nb_reco_brut`). Les colonnes utiles restent aux **mêmes positions** (finess `#0`,
  finess_geo `#2`, region `#4`, score `#8`) → on sélectionne par **nom/position stable**.
- Le **2020** (cible du KPI 8) est en **.xlsx** → conversion en CSV UTF-8 à l'ingestion
  (openpyxl / export), pas de problème d'encodage texte.

### 1.2 Complétude & qualité des colonnes clés

| Année | `finess_geo` (site) distinct | `region` distinct | `score_all_rea_ajust` : nulls | score min–max (0-100) | score moy | hors [0-100] |
|---|---:|---:|---:|---:|---:|---:|
| 2017 | 1157 (= lignes) | 17 | **534 (46.2 %)** | 55.2 – 82.5 | 73.1 | 0 |
| 2019 | 1152 (= lignes) | 17 | **294 (25.5 %)** | 61.9 – 84.7 | 73.7 | 0 |
| 2020 | 1150 (= lignes) | 17 | **313 (27.2 %)** | 57.7 – 84.8 | 74.0 | 0 |

> `finess` (entité **juridique**) est dupliqué (ex. 986 distinct pour 1152 lignes en 2019) ;
> `finess_geo` (entité **géographique / site**) est **unique par ligne** → c'est la **clé de
> grain** et la bonne clé de jointure vers `Dim_Etablissement` (clée sur le **FINESS site**).

### 1.3 Anomalies détectées

| Anomalie | Constat réel | Impact |
|---|---|---|
| **Score NULL** (établissement sous le seuil de diffusion / trop peu de répondants) | **25 à 46 %** des lignes selon l'année | cause de rejet **dominante** et **attendue** (non-diffusable, pas un défaut de donnée) |
| Score hors plage [0-100] | **0** | règle défensive uniquement |
| `finess_geo` dupliqué dans une campagne | **0** | grain propre ; `DISTINCT` défensif |
| Mojibake région (si lu en UTF-8) | systématique | imposé : transcodage CP1252→UTF-8 |
| **Absence de colonne date** | confirmée (aucun champ date dans le fichier) | la période = **année de campagne** (nom de fichier) → `date_id` dérivé |

### Synthèse profiling

La source est **structurellement propre** (clé de site unique, 0 doublon, 17 régions complètes,
0 score hors plage) mais **techniquement piégeuse** : encodage Latin-1 non déclaré, format qui
change (CSV/XLSX, 23↔25 colonnes), **pas de date** et un **fort taux de scores non diffusés**
(25–46 %). Le nettoyage porte donc sur : (1) normalisation d'encodage, (2) sélection robuste par
nom, (3) rejet documenté des scores nuls, (4) dérivation de la date depuis la campagne.

---

## 2. MAPPING SOURCE → CIBLE

Correspondance fichier e-Satis 48h → `Fait_Satisfaction` (cf.
`docs/L1_Modelisation_Fait_Satisfaction.md`).

| Colonne source | Type source | Cible (Fait_Satisfaction) | Transformation |
|---|---|---|---|
| `finess_geo` | STRING | `etab_id` (FK) | **direct** + lookup `Dim_Etablissement` (FINESS site). **Pas `finess`** (juridique, non unique) |
| `score_all_rea_ajust` | STRING (0-100, virgule décimale) | `note_satisfaction` DECIMAL(3,1) | `,`→`.`, puis **`/10`** → 0-10, `ROUND(...,1)` |
| *(année de campagne, du nom de fichier)* | — | `date_id` INT | `CAST(CONCAT(annee_campagne,'0101') AS INT)` → `YYYY0101` (grain annuel, **arrondi conforme** §2.2.D) |
| `region` | STRING | *(non chargée)* | déduite via `Dim_Etablissement` ; sert uniquement au **contrôle de cohérence** au profiling |
| `nb_rep_score_all_rea_ajust` | STRING | *(non repris)* | nombre de répondants — non requis par le KPI 8 |
| *(commentaires / avis texte)* | — | *(absents / exclus)* | aucun texte libre n'est ingéré (anonymisation §2.2.D) |

> **Impact aval** : le job de chargement (`etl/load_satisfaction.sql`, tâche 869dfg1fp) doit
> utiliser **`finess_geo`** comme `etab_id` et dériver `date_id` de l'**année de campagne**
> (il n'existe pas de colonne `date_recueil` dans la source réelle).

---

## 3. RÈGLES DE CLEANING

Implémentées dans `sql/cleaning/satisfaction_cleaning.hql` (Bronze → Silver / fait).

| # | Règle | Action | Volume réel concerné |
|---|---|---|---|
| R1 | Normalisation **encodage** CP1252 → UTF-8 (CSV) ; XLSX → CSV UTF-8 | pré-ingestion (`iconv` / openpyxl) | tous les fichiers CSV |
| R2 | Sélection **par nom** des colonnes utiles (tolérance 23↔25 col.) | mapping | tous les fichiers |
| R3 | **Score NULL / vide** (sous seuil de diffusion) | rejet → `NOTE_NULLE` | **25–46 %** des lignes |
| R4 | Score non numérique | rejet → `NOTE_NON_NUMERIQUE` | 0 constaté |
| R5 | Score hors [0-100] | rejet → `NOTE_HORS_PLAGE` | 0 constaté (défensif) |
| R6 | `finess_geo` absent de `Dim_Etablissement` | rejet → `ETAB_INCONNU` | à mesurer au chargement |
| R7 | Doublon sur `finess_geo` (même campagne) | `ROW_NUMBER()`, garder 1 | 0 constaté (défensif) |

> **Alerte qualité** : le taux de rejet **dépasse le seuil de 10 %** prévu, à cause des scores
> non diffusés (R3, 25–46 %). C'est **attendu et documenté** : ces établissements n'ont pas
> atteint le nombre de répondants requis pour publication ; ce ne sont pas des erreurs. Le KPI 8
> se calcule sur les établissements **diffusés** (623 / 858 / 837 selon l'année).

### Conformité Securite_Anonymisation_NFR.md (§2.2.D Satisfaction)

| Règle du document | Verdict | Décision pipeline |
|---|---|---|
| Identifiant patient → 🔐 pseudonymiser | sans objet | la source est **agrégée par établissement**, aucun identifiant patient (cf. modélisation D-S1) |
| Notes textuelles → 🤐 résumer | appliqué | **aucun texte libre ingéré** ; seul le score chiffré est conservé |
| Date avis → 📅 arrondir au mois | appliqué (au-delà) | grain **annuel** `YYYY0101` (la source n'a pas de date plus fine) |
| Établissement → ✅ conserver | appliqué | `etab_id` = `finess_geo` (FINESS site) |
| Chiffrement en transit (TLS 1.3) | appliqué | récupération FTPS/SFTP (cf. `docs/L1_Description_Job_ETL_Satisfaction.md` §4) |

### Contrôles qualité post-nettoyage

Le script se termine par 3 contrôles (doivent renvoyer 0 / écart justifié) :
- doublons résiduels sur (`etab_id`, `date_id`) = 0
- notes hors [0,10] après normalisation = 0
- réconciliation des volumes Bronze vs Silver (écart = lignes rejetées R3..R7)

---

## 4. TABLE DE REJETS

```sql
CREATE TABLE rejets_satisfaction (
  ligne_source   STRING,
  fichier_source STRING,
  raison_rejet   STRING,
  ts_rejet       TIMESTAMP
) STORED AS ORC;
```

Alimentée par le script de cleaning, une ligne par enregistrement écarté avec son motif
(`NOTE_NULLE`, `NOTE_NON_NUMERIQUE`, `NOTE_HORS_PLAGE`, `ETAB_INCONNU`). Sert au rapport qualité
et à l'audit (un taux ou un motif anormal signale un problème de profiling en amont).

---

## 5. VALIDATION DU PIPELINE (sur données réelles)

Profiling **exécuté et vérifié** sur les 3 campagnes disponibles (2017, 2019, 2020) via
`scripts/satisfaction_profiling.py`. La partie HiveQL (`sql/cleaning/...hql`) est **prête mais
non exécutée** : aucun cluster Hive n'est disponible dans l'environnement courant (cf. note
ci-dessous).

| Vérification | Résultat |
|---|:---:|
| Encodage détecté & documenté par fichier | ✅ (Latin-1 CSV / UTF-8 xlsx) |
| Séparateur identifié | ✅ `;` |
| Clé de grain / jointure identifiée | ✅ `finess_geo` (unique, 0 doublon) |
| Distribution du score & anomalies | ✅ 0 hors plage, nulls quantifiés |
| Table de mapping complète | ✅ (§2) |
| **KPI 8 calculable** (satisfaction/région 2020) | ✅ 837 établissements diffusés, 17 régions, moy. 74.0/100 → **7.40/10** |

> **Limite résiduelle** : les règles HiveQL (`sql/cleaning/satisfaction_cleaning.hql`,
> `sql/profiling/satisfaction_profiling.sql`) reproduisent en HiveQL le profiling Python validé,
> mais ne s'exécutent réellement que sur le Hive des VM. Le taux de rejet R6 (`ETAB_INCONNU`)
> dépend de `Dim_Etablissement` chargée et reste à mesurer au chargement (869dfg1fp).

---

## 6. POINT OUVERT

**Jointure FINESS** : la satisfaction porte le `finess_geo` (site). `dimensions_partagees.md`
fixe `etab_id = finess_site` ; à confirmer que `Dim_Etablissement` est bien alimentée au grain
**site** (et non juridique), faute de quoi R6 rejettera massivement. À valider avec P2
(référentiel établissements) avant le chargement.
