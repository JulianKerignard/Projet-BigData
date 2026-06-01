-- =====================================================================
-- Profiling de la source Consultations (PostgreSQL)
-- Tâche : [P1] Profiling + mapping + cleaning Consultations
-- Objectif : mesurer la qualité de la table source avant chargement DWH
-- Exécution : sur la base PostgreSQL restaurée depuis le dump DATA2023
-- =====================================================================

-- 1. VOLUMÉTRIE des tables impliquées
SELECT 'Consultation'           AS table_name, COUNT(*) AS n FROM "Consultation"
UNION ALL SELECT 'Patient',                COUNT(*) FROM "Patient"
UNION ALL SELECT 'Professionnel_de_sante', COUNT(*) FROM "Professionnel_de_sante"
UNION ALL SELECT 'Diagnostic',             COUNT(*) FROM "Diagnostic"
UNION ALL SELECT 'Specialites',            COUNT(*) FROM "Specialites";

-- 2. COMPLÉTUDE : valeurs nulles et doublons sur la clé
SELECT
  COUNT(*)                                      AS total,
  COUNT(*) - COUNT("Num_consultation")          AS num_null,
  COUNT(*) - COUNT(DISTINCT "Num_consultation") AS num_doublons,
  COUNT(*) - COUNT("Id_patient")                AS patient_null,
  COUNT(*) - COUNT("Id_prof_sante")             AS prof_null,
  COUNT(*) - COUNT("Code_diag")                 AS diag_null,
  COUNT(*) - COUNT("Date")                      AS date_null,
  COUNT(*) - COUNT("Heure_debut")               AS hdebut_null,
  COUNT(*) - COUNT("Heure_fin")                 AS hfin_null,
  COUNT(*) - COUNT("Motif")                     AS motif_null
FROM "Consultation";

-- 3. COHÉRENCE temporelle : plage de dates et anomalies horaires
SELECT
  MIN("Date") AS date_min,
  MAX("Date") AS date_max,
  COUNT(*) FILTER (WHERE "Heure_fin" < "Heure_debut") AS heure_incoherente,
  COUNT(*) FILTER (WHERE "Heure_fin" = "Heure_debut") AS duree_zero
FROM "Consultation";

-- 4. INTÉGRITÉ RÉFÉRENTIELLE : FK orphelines vers les référentiels
SELECT
  (SELECT COUNT(*) FROM "Consultation" c
     LEFT JOIN "Patient" p ON p."Id_patient" = c."Id_patient"
     WHERE p."Id_patient" IS NULL)                  AS patient_orphelins,
  (SELECT COUNT(*) FROM "Consultation" c
     LEFT JOIN "Professionnel_de_sante" pr ON pr."Identifiant" = c."Id_prof_sante"
     WHERE pr."Identifiant" IS NULL)                AS prof_orphelins,
  (SELECT COUNT(*) FROM "Consultation" c
     LEFT JOIN "Diagnostic" d ON d."Code_diag" = c."Code_diag"
     WHERE d."Code_diag" IS NULL)                   AS diag_orphelins;

-- 5. CARDINALITÉS distinctes (dimensionnement des axes)
SELECT
  COUNT(DISTINCT "Id_patient")    AS patients_distincts,
  COUNT(DISTINCT "Id_prof_sante") AS profs_distincts,
  COUNT(DISTINCT "Code_diag")     AS diags_distincts,
  COUNT(DISTINCT "Motif")         AS motifs_distincts
FROM "Consultation";

-- 6. RÉPARTITION par année (planification du partitionnement)
SELECT EXTRACT(YEAR FROM "Date")::int AS annee, COUNT(*) AS nb
FROM "Consultation" GROUP BY 1 ORDER BY 1;

-- 7. QUALITÉ des attributs dimensionnels (Dim_Patient)
SELECT "Sexe", COUNT(*) FROM "Patient" GROUP BY "Sexe";
SELECT MIN("Age") AS age_min, MAX("Age") AS age_max,
       COUNT(*) FILTER (WHERE "Age" < 0 OR "Age" > 120) AS age_aberrant
FROM "Patient";
