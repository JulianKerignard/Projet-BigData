-- =====================================================================
-- Requêtes analytiques du dashboard Consultations (besoins B2, B6, période)
-- Tâche : Livrable 3 - dashboard consultations (prototype)
-- Données : agrégats uniquement (aucune donnée patient individuelle -> conforme
--           Securite_Anonymisation_NFR.md, accès analyste sur agrégats)
-- Exécutées sur la source PostgreSQL (transposables en HiveQL sur le DWH)
-- =====================================================================

-- KPI globaux (et déclinés par année pour le filtre)
SELECT EXTRACT(YEAR FROM "Date")::int AS annee,
       COUNT(*)                       AS total_consultations,
       COUNT(DISTINCT "Id_patient")   AS patients_distincts,
       COUNT(DISTINCT "Id_prof_sante") AS professionnels_distincts,
       COUNT(DISTINCT "Code_diag")    AS diagnostics_distincts,
       ROUND(AVG(EXTRACT(EPOCH FROM ("Heure_fin" - "Heure_debut"))/60)
             FILTER (WHERE "Heure_fin" >= "Heure_debut")::numeric, 1) AS duree_moyenne_min
FROM "Consultation"
GROUP BY 1 ORDER BY 1;

-- Évolution : consultations par année (tendance)
SELECT EXTRACT(YEAR FROM "Date")::int AS annee, COUNT(*) AS n
FROM "Consultation" GROUP BY 1 ORDER BY 1;

-- Saisonnalité : consultations par mois (par année)
SELECT EXTRACT(YEAR FROM "Date")::int AS annee,
       EXTRACT(MONTH FROM "Date")::int AS mois, COUNT(*) AS n
FROM "Consultation" GROUP BY 1, 2 ORDER BY 1, 2;

-- B2 : top diagnostics par année (top 15)
WITH agg AS (
  SELECT EXTRACT(YEAR FROM c."Date")::int AS annee, dg."Diagnostic" AS label, COUNT(*) AS n
  FROM "Consultation" c JOIN "Diagnostic" dg ON dg."Code_diag" = c."Code_diag"
  GROUP BY 1, 2),
d AS (
  SELECT annee, label, n, ROW_NUMBER() OVER (PARTITION BY annee ORDER BY n DESC) AS rn FROM agg)
SELECT annee, label, n FROM d WHERE rn <= 15 ORDER BY annee, n DESC;

-- B6 : consultations par spécialité de professionnel (top 12 par année)
WITH agg AS (
  SELECT EXTRACT(YEAR FROM c."Date")::int AS annee, sp."Specialite" AS label, COUNT(*) AS n
  FROM "Consultation" c
  JOIN "Professionnel_de_sante" p ON p."Identifiant" = c."Id_prof_sante"
  JOIN "Specialites" sp ON sp."Code_specialite" = p."Code_specialite"
  GROUP BY 1, 2),
s AS (
  SELECT annee, label, n, ROW_NUMBER() OVER (PARTITION BY annee ORDER BY n DESC) AS rn FROM agg)
SELECT annee, label, n FROM s WHERE rn <= 12 ORDER BY annee, n DESC;

-- Répartition par sexe du patient (par année)
SELECT EXTRACT(YEAR FROM c."Date")::int AS annee, p."Sexe" AS sexe, COUNT(*) AS n
FROM "Consultation" c JOIN "Patient" p ON p."Id_patient" = c."Id_patient"
GROUP BY 1, 2 ORDER BY 1, 2;
