# Job ETL Satisfaction (Livrable 1)

> **Tâche** : `[P3] Description job ETL Satisfaction` (869dfg12k)
> **Auteur** : Matthieu (P3)
> **Prérequis** : [Modélisation Fait_Satisfaction](L1_Modelisation_Fait_Satisfaction.md) + `Dim_Etablissement` chargée

## 1. Contexte et spécificité

La source Satisfaction est constituée de **fichiers plats déposés sur le FTP CESI** (open data
e-Satis / IQSS, un fichier par campagne annuelle). Contrairement aux autres axes (extraction
SQL homogène depuis PostgreSQL), ces fichiers sont **hétérogènes d'une année à l'autre** :
encodage, séparateur, nombre de colonnes et libellés varient. Une étape de **profiling** est
donc **obligatoire avant l'ingestion** — sans elle, le parsing casse silencieusement
(mojibake sur les régions, colonnes décalées).

## 2. Vue d'ensemble du job

```mermaid
flowchart LR
    FTP[FTP CESI\nfichiers e-Satis / IQSS] -->|curl / lftp| LOCAL[Atterrissage local]
    LOCAL -->|profiling : encoding, sep, header| PROF{Profil OK ?}
    PROF -->|non : transcodage| LOCAL
    PROF -->|oui| PUT[hdfs dfs -put]
    PUT --> BRONZE["Staging HDFS\n/staging/satisfaction/"]
    BRONZE -->|EXTERNAL TABLE| STG[(staging.satisfaction)]
    STG -->|transform + validation 0-10\n+ lookup FINESS| FACT[(fait_satisfaction)]
    STG -->|notes hors plage\nFINESS inconnu| ERR[(satisfaction_rejets)]
```

## 3. Étape 1 — Profiling du fichier (obligatoire)

Résultats du profiling réel sur `DATA 2024/Satisfaction/` (à refaire à chaque nouvelle
campagne) :

| Caractéristique | Constat | Action ETL |
|---|---|---|
| **Encoding** | **ISO-8859-1 / CP1252** (Latin-1), *pas* UTF-8 — les libellés régions ressortent en mojibake si lus en UTF-8 (`Auvergne-Rh�ne-Alpes`) | Transcodage systématique `iconv -f CP1252 -t UTF-8` avant ingestion |
| **Séparateur** | point-virgule `;` | `FIELDS TERMINATED BY ';'` |
| **Fin de ligne** | CRLF (`\r\n`) | normaliser en `\n` (`tr -d '\r'`) |
| **En-tête** | présent (1 ligne) | `tblproperties("skip.header.line.count"="1")` |
| **Colonnes clés** | `finess`, `region`, `score_all_rea_ajust`, `participation` (23 à 25 colonnes selon l'année) | ne charger que les colonnes utiles |
| **Échelle mesure** | score global **0–100** (moy. ≈ 73.7) | normaliser `/10` → 0–10 |

Commande de profiling reproductible :

```bash
F=resultats-esatis48h-mco-open-data-2020.csv
file "$F"                      # encoding + terminaison de ligne
head -1 "$F" | tr ';' '\n'     # liste des colonnes
iconv -f CP1252 -t UTF-8 "$F" | head -10   # échantillon lisible
```

## 4. Étape 2 — Ingestion FTP → Staging HDFS

> **Chiffrement en transit obligatoire** (sécurité §1.2 / NFR §3.4 : TLS 1.3). Le FTP en clair
> est **interdit** : on utilise **FTPS explicite** (`--ssl-reqd`, TLS ≥ 1.2, idéalement 1.3) ou
> SFTP. Les identifiants ne sont **jamais** passés en clair sur la ligne de commande (visibles
> dans `ps`/logs) : ils sont lus depuis un `~/.netrc_cesi` à droits `600` (ou un secret manager).

```bash
# 2.1 Récupération depuis le FTP CESI — FTPS explicite (TLS 1.3), credentials via .netrc 600
curl --ssl-reqd --tlsv1.3 --netrc-file ~/.netrc_cesi \
     "ftps://ftp.cesi.fr/satisfaction/resultats-esatis48h-mco-open-data-2020.csv" \
     -o /tmp/satisfaction_2020.csv
# (alternative : sftp -i ~/.ssh/cesi_key user@ftp.cesi.fr:/satisfaction/...)

# 2.2 Normalisation encoding + fins de ligne (issu du profiling §3)
iconv -f CP1252 -t UTF-8 /tmp/satisfaction_2020.csv | tr -d '\r' \
     > /tmp/satisfaction_2020_utf8.csv

# 2.3 Dépôt en zone de staging HDFS (Bronze) — accès restreint ETL/Admin (sécurité §4.1)
hdfs dfs -mkdir -p /staging/satisfaction/
hdfs dfs -chmod 700 /staging/satisfaction/
hdfs dfs -put -f /tmp/satisfaction_2020_utf8.csv /staging/satisfaction/

# 2.4 Effacement sécurisé de la copie locale en clair après ingestion
shred -u /tmp/satisfaction_2020.csv /tmp/satisfaction_2020_utf8.csv
```

## 5. Étape 3 — Transformation et alimentation du fait

La table externe de staging et l'`INSERT` de chargement sont détaillés dans
[`etl/load_satisfaction.sql`](../etl/load_satisfaction.sql) (Livrable 2). Logique :

1. **Parsing** via `EXTERNAL TABLE` pointant sur `/staging/satisfaction/annee=YYYY/`.
2. **Sélection minimale (anonymisation §2.2.D)** : on ne projette **que** `finess_geo` (clé site),
   `region` (contrôle de cohérence) et le score numérique. La source ne contient **aucune date**
   ni aucun **commentaire / avis en texte libre** — la satisfaction est réduite à sa mesure chiffrée.
3. **Dérivation de la date (anonymisation §2.2.D)** : la source n'ayant pas de colonne date, la
   période est l'**année de campagne** (nom de fichier) → `date_id = YYYY0101` (grain annuel, déjà
   plus grossier qu'un arrondi au mois).
4. **Validation** : ne garder que les scores bruts dans `[0, 100]`, normalisés `/10` → note `[0, 10]`.
5. **Lookup `Dim_Etablissement`** : `etab_id` (= `finess_geo`, FINESS **site**) doit exister dans la
   dimension — sinon la ligne part en rejet.
6. **`INSERT INTO fait_satisfaction`** des lignes valides.

## 6. Gestion d'erreurs

| Cas d'erreur | Détection | Traitement |
|---|---|---|
| Note hors plage `[0,10]` (ou score brut hors `[0,100]`) | `WHERE note BETWEEN 0 AND 10` | rejet → table `satisfaction_rejets`, motif `NOTE_HORS_PLAGE` |
| Note manquante / non numérique | `note IS NULL` après `CAST` | rejet → motif `NOTE_NULLE` |
| FINESS absent de `Dim_Etablissement` | `LEFT JOIN ... WHERE e.etab_id IS NULL` | rejet → motif `ETAB_INCONNU` |
| Doublon établissement × date | `GROUP BY` / `ROW_NUMBER` | conservation de la dernière, log du doublon |

Les rejets sont **comptés et tracés** (le rapport de vérification du chargement reprend ces
volumes). Un taux de rejet anormal (> quelques %) signale un problème de profiling en amont.

## 7. Conformité sécurité & anonymisation

Alignement avec [`Securite_Anonymisation_NFR.md`](Securite_Anonymisation_NFR.md) :

| Règle | Application dans ce job |
|---|---|
| Identifiant patient → pseudonymiser | **Sans objet** : la source e-Satis est agrégée par établissement, aucun identifiant patient n'est ingéré (cf. modélisation D-S1). |
| Notes textuelles → résumer | Les commentaires en **texte libre sont exclus** ; seul le score chiffré est conservé (§5.2). |
| Date avis → arrondir | aucune date dans la source : `date_id` = **année de campagne** `YYYY0101` (grain annuel, plus grossier qu'un arrondi au mois) (§5.3). |
| Établissement → conserver | `etab_id` (FINESS) conservé comme axe d'analyse. |
| Chiffrement en transit (TLS 1.3) | Récupération en **FTPS/SFTP**, credentials hors ligne de commande (§4). |
| Accès staging restreint | `/staging/satisfaction/` en `700` (ETL/Admin), copies locales `shred` après usage (§4). |

**Prérequis de déploiement (hors périmètre HQL, responsabilité infra/Hive)** : chiffrement
**au repos AES-256** (HDFS TDE / chiffrement de zone), **RBAC** Hive + Row-Level Security côté
Power BI, et **audit logging** des accès — conformément aux NFR §3.4 et §4.1.

## 8. Definition of Done

- [x] Étape de profiling documentée (encoding, séparateur, header, échantillon)
- [x] Schéma du job dessiné (§2)
- [x] Étapes détaillées (profiling → ingestion → transformation)
- [x] Gestion d'erreurs documentée (§6)
- [x] Conformité sécurité / anonymisation vérifiée (§7)

## 9. Dépendances

- **Prérequis** : modèle `Fait_Satisfaction` + `Dim_Etablissement` chargée (FINESS).
- **Bloque** : [`[P3] Chargement Fait_Satisfaction`](../etl/load_satisfaction.sql) (869dfg1fp).
