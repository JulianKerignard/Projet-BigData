#!/usr/bin/env bash
# Profiling INSEE deces.csv via DuckDB (moteur vectorise multi-thread).
# Alternative ~3-4x plus rapide que la version awk 1-passe (profile_deces.sh),
# et parsing CSV correct (guillemets respectes -> pas de colonnes decalees).
# Usage : ./profile_deces_duckdb.sh <chemin_fichier_csv>
# Pre-requis : duckdb (brew install duckdb).

set -euo pipefail
FILE="${1:-}"
if [[ -z "$FILE" || ! -f "$FILE" ]]; then
    echo "Usage: $0 <path-to-deces.csv>" >&2; exit 1
fi
command -v duckdb >/dev/null || { echo "duckdb absent (brew install duckdb)" >&2; exit 1; }

echo "=========================================="
echo " Profiling DuckDB : $FILE"
echo " Date : $(date '+%Y-%m-%d %H:%M:%S')   (duckdb $(duckdb --version | awk '{print $1}'))"
echo "=========================================="

duckdb -box <<SQL
-- Une seule lecture du CSV -> table en memoire (3 colonnes utiles). Parsing
-- quote-aware (DuckDB respecte les guillemets, contrairement a awk -F','),
-- ignore_errors saute les lignes a nombre de champs incoherent.
CREATE TABLE d AS
  SELECT sexe, date_deces, code_lieu_deces
  FROM read_csv('${FILE}', header=true, sep=',', quote='"',
                all_varchar=true, ignore_errors=true);

SELECT '3. Volumetrie' AS section;
SELECT count(*) AS lignes_chargees FROM d;

SELECT '5. Distribution par annee (top 5)' AS section;
SELECT substr(date_deces,1,4) AS annee, count(*) AS n
FROM d GROUP BY annee ORDER BY n DESC LIMIT 5;
SELECT count(*) AS total_2019 FROM d WHERE substr(date_deces,1,4)='2019';

SELECT '6. Longueurs de code_lieu_deces' AS section;
SELECT length(code_lieu_deces) AS longueur, count(*) AS n
FROM d GROUP BY longueur ORDER BY n DESC;

SELECT '7. Departements (2019, top 10)' AS section;
SELECT substr(code_lieu_deces,1,2) AS dept, count(*) AS n
FROM d WHERE substr(date_deces,1,4)='2019' AND length(code_lieu_deces)=5
GROUP BY dept ORDER BY n DESC LIMIT 10;
SELECT '7b. DOM-TOM (97x/98x, 2019)' AS section;
SELECT substr(code_lieu_deces,1,3) AS dom, count(*) AS n
FROM d WHERE substr(date_deces,1,4)='2019' AND length(code_lieu_deces)=5
  AND substr(code_lieu_deces,1,2) IN ('97','98')
GROUP BY dom ORDER BY n DESC;

SELECT '8. Sexe (2019)' AS section;
SELECT sexe, count(*) AS n
FROM d WHERE substr(date_deces,1,4)='2019' GROUP BY sexe ORDER BY n DESC;

SELECT '9. Min / Max date_deces (dates conformes)' AS section;
SELECT min(date_deces) AS min_date, max(date_deces) AS max_date,
       sum(CASE WHEN regexp_matches(date_deces,'^[0-9]{4}-[0-9]{2}-[0-9]{2}') THEN 0 ELSE 1 END) AS lignes_date_non_conforme
FROM d;
SQL

echo "=========================================="
echo " Profiling DuckDB termine"
echo "=========================================="
