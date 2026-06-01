# Analyse du besoin — Personas & Mapping KPI

> **Livrable** : section "Besoins utilisateurs" du rapport L1, slides intro L3.
> **Tâche ClickUp** : [869dfg0zg](https://app.clickup.com/t/869dfg0zg) — [COMMUN] Recensement besoins utilisateurs + personas.

---

## 1. Contexte

Le groupe **CHU (Cloud Healthcare Unit)** souhaite mettre en place un entrepôt de données décisionnel pour exploiter les données médicales et administratives de ses établissements. Deux profils d'utilisateurs sont explicitement ciblés par le sujet :

- les **praticiens** (médecins, personnel infirmier) — usage clinique, suivi patients ;
- les **chefs d'établissement / administrateurs** — pilotage de l'activité, comparaison inter-établissements.

L'analyse du besoin ci-dessous formalise ces deux profils sous forme de personas, puis cartographie leurs besoins métier vers les 8 KPI identifiés dans le sujet et vers les 4 sources de données mises à disposition.

---

## 2. Personas

### Persona 1 — Dr Martin, praticien hospitalier

| Attribut | Détail |
|---|---|
| **Rôle** | Médecin généraliste / spécialiste exerçant en CHU |
| **Contexte d'usage** | Consultation et hospitalisation de patients sur des pathologies chroniques |
| **Objectifs métier** | Suivre l'évolution clinique de ses patients, comparer ses pratiques aux statistiques nationales/régionales, identifier les pics d'activité |
| **Douleurs actuelles** | Données éclatées entre la BDD de gestion des soins, les fichiers de satisfaction et les statistiques décès ; aucune vue consolidée sur plusieurs années |
| **Fréquence d'usage** | Hebdomadaire (revue d'activité) à mensuelle (bilan pathologique) |
| **Niveau de maîtrise data** | Faible à moyen — a besoin d'un dashboard prêt à l'emploi, pas d'un outil de requêtage |

**Besoins métier** :
- B1.1 — Connaître le **taux de consultation** de ses patients par établissement et par période.
- B1.2 — Suivre le **taux de consultation par diagnostic** sur une période donnée (évolution des pathologies).
- B1.3 — Comparer son **taux de consultation par professionnel** à celui de ses confrères.
- B1.4 — Connaître les **taux d'hospitalisation par sexe/âge** pour adapter sa prise en charge.

### Persona 2 — Mme Durand, directrice de CHU

| Attribut | Détail |
|---|---|
| **Rôle** | Directrice d'un établissement hospitalier (chef d'établissement) |
| **Contexte d'usage** | Pilotage stratégique : performance, qualité de service, comparaison inter-régionale |
| **Objectifs métier** | Mesurer la performance globale de son établissement, se comparer aux autres CHU, justifier les décisions auprès de l'ARS et du conseil de surveillance |
| **Douleurs actuelles** | Pas de vue agrégée multi-source ; les indicateurs satisfaction et décès régionaux ne sont pas croisés avec l'activité hospitalière |
| **Fréquence d'usage** | Mensuelle (comité de direction) à trimestrielle (rapport ARS) |
| **Niveau de maîtrise data** | Moyen — sait lire un dashboard exécutif, attend des KPI synthétiques et des comparaisons régionales |

**Besoins métier** :
- B2.1 — Suivre le **taux global d'hospitalisation** de son établissement sur une période.
- B2.2 — Décomposer le **taux d'hospitalisation par diagnostic** pour identifier les spécialités les plus sollicitées.
- B2.3 — Comparer le **taux de satisfaction** de sa région à la moyenne nationale (2020).
- B2.4 — Mettre en perspective les **décès par région** (2019) avec l'activité hospitalière locale.

---

## 3. Mapping Persona → Besoin → KPI

| # | Persona | Besoin métier | KPI couvert (sujet) | Sources requises |
|---|---|---|---|---|
| 1 | Dr Martin | Suivi consultations par établissement/période | Taux consultation par établissement X / période Y | PostgreSQL (soins) + CSV (établissements) |
| 2 | Dr Martin | Suivi pathologies des patients | Taux consultation par diagnostic X / période Y | PostgreSQL (soins) |
| 3 | Dr Martin | Comparaison pratiques entre praticiens | Taux consultation par professionnel | PostgreSQL (soins) |
| 4 | Dr Martin | Adaptation prise en charge | Taux hospitalisation par sexe / âge | PostgreSQL (soins) |
| 5 | Mme Durand | Pilotage performance globale | Taux global hospitalisation / période Y | PostgreSQL (soins) |
| 6 | Mme Durand | Identification spécialités sollicitées | Taux hospitalisation par diagnostic / période | PostgreSQL (soins) |
| 7 | Mme Durand | Comparaison régionale qualité | Taux global satisfaction par région / 2020 | Fichiers plats (satisfaction) + CSV (établissements) |
| 8 | Mme Durand | Mise en perspective mortalité régionale | Nb décès par région / 2019 | Fichiers décès + CSV (établissements) |

**Couverture** : 8/8 KPI du sujet adressés, répartis 4/4 entre les deux personas.

---

## 4. Validation — couverture par les 4 sources de données

| Source | Contenu | KPI alimentés |
|---|---|---|
| **PostgreSQL** (gestion soins médico-administratifs) | Patients, consultations, hospitalisations, diagnostics, professionnels | KPI 1, 2, 3, 4, 5, 6 |
| **CSV** (établissements de France) | Référentiel établissements, localisation, région | Dimension partagée — alimente KPI 1, 7, 8 |
| **Fichiers plats** (satisfaction patients) | Notes de satisfaction par établissement | KPI 7 |
| **Fichiers plats** (décès en France) | Répertoire des décès, localisation, date | KPI 8 |

> ✅ Les 4 sources sont nécessaires et suffisantes pour produire les 8 KPI ciblés.
> ⚠️ Le CSV "établissements" joue un rôle de **dimension partagée** (région, type d'établissement) — il doit être chargé en amont des autres jobs ETL.

---

## 5. Definition of Done

- [ ] 2 personas rédigés et validés en groupe
- [ ] Tableau mapping Persona → Besoin → KPI validé par les 4 membres
- [ ] Validation que les 4 sources produisent bien les 8 KPI
- [ ] Document partagé sur le drive
- [ ] Section "Besoins utilisateurs" prête pour intégration rapport L1 et slides L3
