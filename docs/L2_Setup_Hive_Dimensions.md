# Setup environnement Hive + DDL dimensions partagées

**Livrable :** L2 — Modèle physique & optimisation
**Tâche :** [COMMUN] Setup environnement Hive + DDL dimensions partagées (869dfg187)
**Date :** Juin 2026

Scripts livrés :
- `sql/ddl/00_setup_hive.hql` — création des bases + paramètres de session
- `sql/ddl/01_dimensions_partagees.hql` — DDL des 6 dimensions conformes (Parquet)

Conforme au MCD : `docs/mcd_constellation.png`.

---

## 1. Convention de nommage (à respecter par toute l'équipe)

Architecture **médaillon** sur deux bases Hive :

| Base | Couche | Contenu | Emplacement HDFS |
|------|--------|---------|------------------|
| `staging` | Bronze + Silver | données brutes ingérées, puis nettoyées/anonymisées | `/chu/staging` (Silver), `/chu/bronze` (brut) |
| `chu_entrepot` | Gold | modèle en étoile : **dimensions + faits**, en Parquet | `/chu/gold` |

**Règles** :
- Toute table de l'entrepôt (Gold) est préfixée `chu_entrepot.` et **`STORED AS PARQUET`**.
- Les tables de travail (Bronze/Silver) vont dans `staging.`.
- Les dimensions : `dim_<nom>` ; les faits : `fait_<nom>` ; les rejets : `staging.rejets_<source>`.

> Cette convention **résout la divergence** constatée en review : Matthieu (satisfaction) utilisait déjà `staging.`/`chu_entrepot.`, le cleaning consultations utilisait des tables sans préfixe. **Action** : les jobs de cleaning doivent préfixer leurs tables (`staging.silver_consultation`, etc.) et écrire le fait final dans `chu_entrepot` en Parquet.

### Règles techniques validées sur cluster (audit cleaning)

- ⚠️ **Hive 2.x ne supporte pas les sous-requêtes scalaires en SELECT** (`SELECT (SELECT COUNT(*)…) AS x` → `Error 10249`). Pour les réconciliations de volumes, utiliser le pattern **`UNION ALL`** (corrigé dans les cleanings consultations / satisfaction / décès).
- ✅ **Cleaning hospitalisation porté en HiveQL** : `sql/cleaning/hospitalisations_cleaning.hql` (anonymisation §2.2.A, clés conformes, Parquet) remplace la partie *cleaning* du pipeline PySpark de P2 — validé sur Hive (2 479 séjours chargés, patient pseudonymisé, jointures dim OK) — pipeline 100 % HiveQL.
- ✅ **Chaîne Gold rendue exécutable de bout en bout** (corrections audit) :
  - `fait_consultation` est désormais **alimenté** (`consultations_cleaning.hql`, étape 4bis) — B2/B6 servis.
  - `fait_satisfaction` : INSERT corrigé (surrogate `satisfaction_key`, **`geo_id`** ajouté, `PARTITION (annee)`) ; `rejets_satisfaction` repassé en **Parquet**.
  - `dim_etablissement` (FINESS satisfaction + hospi) et `dim_diagnostic` (codes observés) **alimentées** (`04_chargement_dimensions.hql`) ; seules `dim_patient` / `dim_professionnel` restent des templates Bronze.
  - `fait_satisfaction.geo_id` aligne **B8 (satisfaction/région)** sur **B7 (décès/région)** : même axe `dim_geographie`.
- ✅ **Pipeline 100 % HiveQL** : profiling, chargement et benchmark assurés par `sql/cleaning/*.hql`, `sql/ddl/02_faits.hql` + `04_chargement_dimensions.hql` et `sql/benchmark/*` (partition/bucket déclarés dans `02_faits.hql`). L'ancien prototype PySpark a été retiré (cf. CHANGELOG v1.1.0) — stack « HiveQL batch, sans Spark » assumée.

---

## 2. Paramètres de session (00_setup_hive.hql)

- **Parquet + Snappy** par défaut (`hive.default.fileformat=Parquet`, `parquet.compression=SNAPPY`) — colonnaire et compressé.
- **Partitionnement dynamique** activé (chargement des faits par année).
- **Bucketing** activé.
- **CBO + vectorisation** activés — utiles pour le benchmark de performance L2.

---

## 3. Dimensions conformes (01_dimensions_partagees.hql)

Les 6 dimensions partagées du MCD, toutes en **Parquet**, avec clé primaire informative (`DISABLE NOVALIDATE` — Hive ne contraint pas, l'unicité est garantie par les jobs d'alimentation) :

| Dimension | Clé | Sert les besoins | Alimentée par (fusion) |
|-----------|-----|------------------|------------------------|
| `dim_temps` | `date_id` (AAAAMMJJ) | tous (axe période) | calendrier généré |
| `dim_patient` | `patient_id` (hash SHA-256) | B5 (sexe/âge) | PostgreSQL : consultations + hospitalisations |
| `dim_professionnel` | `prof_id` (ADELI) | B6 (par professionnel) | PostgreSQL : Professionnel_de_sante + Specialites |
| `dim_diagnostic` | `diag_id` (CIM-10) | B2, B4 (par diagnostic) | consultations + hospitalisations |
| `dim_etablissement` | `etab_id` (FINESS site) | B8 (+ hospi) | CSV établissements (maître) + hospi + satisfaction |
| `dim_geographie` | `geo_id` (région/dept 2016) | B7 (décès), B8 (satisfaction) | référentiel `ref_dept_region` |

**Points de conformité** :
- `dim_patient.patient_id` = **hash pseudonymisé** (§2.3 sécurité), jamais d'ID en clair.
- `dim_diagnostic.chapitre_cim10` = **généralisation** par chapitre (§2.2) — c'est l'axe utilisé par les dashboards.
- `dim_geographie` est **unique et partagée** : décès et satisfaction doivent s'y rattacher avec les **mêmes `geo_id`** (sinon « décès par région » et « satisfaction par région » ne seraient pas comparables).

---

## 4. Fusion des dimensions conformes (intégration source unique)

Le sujet impose « une source unique persistante ». Les dimensions ci-dessus sont le **point de fusion** des sources distribuées :

- **`dim_etablissement`** réconcilie le **FINESS** entre 3 sources (référentiel CSV maître, `identifiant_organisation` des hospi, `finess_geo` de la satisfaction).
- **`dim_geographie`** harmonise les **libellés de région** : la satisfaction 2020 écrit « Ile de France », l'INSEE « Île-de-France » → normalisation vers le référentiel `ref_dept_region` (découpage 2016). *(Écart déjà rencontré et corrigé côté dashboard.)*
- **`dim_patient`** : même `Id_patient` source (PostgreSQL) pour consultations et hospitalisations → un seul hash.

Les **jobs d'alimentation** de ces dimensions (dédup + réconciliation des clés) relèvent des tâches `[Px] Chargement` et de la description L1 des jobs.

---

## 5. Ordre d'exécution

`dim_etablissement` doit précéder le chargement des faits (la satisfaction la joint et
y résout `geo_id`) ; `dim_diagnostic` se dérive des faits → elle se peuple en relançant
`04` après les cleanings (INSERT OVERWRITE idempotents). D'où l'ordre en deux phases :

```
1. sql/ddl/00_setup_hive.hql                 -- bases + paramètres de session
2. sql/ddl/01_dimensions_partagees.hql       -- DDL des 6 dimensions (Gold, Parquet)
3. sql/ddl/02_faits.hql                      -- DDL des 4 faits (Gold, Parquet)
4. sql/ddl/04_chargement_dimensions.hql      -- PHASE 1 : dim_temps, dim_geographie, dim_etablissement
   (hive -hivevar annee_campagne=2020 -f ...)
5. Cleanings = chargement des faits :
   - consultations_cleaning.hql    (hivevar MASTER_KEY, SALT_SEED)   -> fait_consultation
   - hospitalisations_cleaning.hql (hivevar MASTER_KEY, SALT_SEED)   -> fait_hospitalisation
   - satisfaction_cleaning.hql     (hivevar annee_campagne=2020)     -> fait_satisfaction
   - deces_cleaning.hql                                              -> fait_deces
6. sql/ddl/04_chargement_dimensions.hql      -- relance => PHASE 2 : dim_diagnostic (codes observés)
```

> `dim_patient` / `dim_professionnel` restent en templates commentés (section 5 du script) :
> elles dépendent de l'ingestion Bronze PostgreSQL (tâches `[Px] Chargement` de l'équipe).

---

## 6. Validation (exécutée sur un vrai Hive)

Les scripts ont été **exécutés et validés** sur un cluster **Apache Hive 2.3.2** monté en local
via Docker (`docker/docker-compose.hive.yml` — Hadoop + metastore PostgreSQL + HiveServer2) :

| Vérification | Résultat |
|--------------|:--------:|
| `00_setup_hive.hql` → bases `staging` + `chu_entrepot` créées | ✅ |
| `01_dimensions_partagees.hql` → 6 dimensions créées sans erreur | ✅ |
| Format de stockage = **Parquet** (`ParquetHiveSerDe`) | ✅ |
| INSERT + SELECT sur `dim_temps` (lecture/écriture Parquet) | ✅ |

Reproduire :
```bash
docker compose -f docker/docker-compose.hive.yml up -d        # démarre la stack
docker cp sql/ddl/00_setup_hive.hql chu-hive-server:/tmp/ && \
docker exec chu-hive-server beeline -u jdbc:hive2://localhost:10000 -f /tmp/00_setup_hive.hql
# idem pour 01_dimensions_partagees.hql
docker compose -f docker/docker-compose.hive.yml down -v       # nettoyage
```

**Notes** :
- Les contraintes PK sont **informatives** (`DISABLE NOVALIDATE`, Hive ne les impose pas) ; l'unicité est assurée par les jobs d'alimentation (déduplication).
- Les types utilisent `STRING` (idiomatique Hive) plutôt que `VARCHAR(n)` : pas de troncature silencieuse, performance équivalente en Parquet.
- Cette stack Docker sert aussi au **benchmark L2** (comparer CSV/TEXTFILE vs Parquet partitionné/bucketé).
