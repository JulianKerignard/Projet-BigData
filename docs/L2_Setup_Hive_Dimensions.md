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

```
1. sql/ddl/00_setup_hive.hql              -- bases + paramètres
2. sql/ddl/01_dimensions_partagees.hql    -- DDL des 6 dimensions (Gold, Parquet)
3. (par fait) DDL + chargement des faits  -- fait_consultation, fait_hospitalisation, …
4. Chargement des dimensions (jobs d'alimentation, réconciliation des clés)
5. Chargement des faits (après les dimensions — intégrité référentielle)
```

---

## 6. Limites / validation

- Les scripts sont **prêts** mais **non exécutés** : aucun cluster Hive n'est disponible dans l'environnement courant (Hive tourne sur les VM). Ils ont été relus pour cohérence avec le MCD et le stack (Parquet).
- Les contraintes PK sont **informatives** (Hive ne les impose pas) ; l'unicité est assurée par les jobs d'alimentation (déduplication).
- Les types utilisent `STRING` (idiomatique Hive) plutôt que `VARCHAR(n)` : pas de troncature silencieuse, performance équivalente en Parquet.
