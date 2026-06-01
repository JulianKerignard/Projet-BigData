#!/usr/bin/env bash
# Profiling rapide du fichier INSEE deces.csv
# Usage : ./profile_deces.sh <chemin_fichier_csv>

set -euo pipefail

FILE="${1:-}"

if [[ -z "$FILE" || ! -f "$FILE" ]]; then
    echo "Usage: $0 <path-to-deces.csv>" >&2
    exit 1
fi

echo "=========================================="
echo " Profiling : $FILE"
echo " Date : $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

echo
echo "--- 1. Format & encodage ---"
file "$FILE"
ls -lh "$FILE" | awk '{print "Taille brute : " $5}'

echo
echo "--- 2. Header (colonnes) ---"
head -1 "$FILE"
NCOLS=$(head -1 "$FILE" | awk -F',' '{print NF}')
echo "Nombre de colonnes : $NCOLS"

echo
echo "--- 3. Volumétrie totale ---"
NLINES=$(wc -l < "$FILE")
echo "Lignes totales (header inclus) : $NLINES"
echo "Lignes de données : $((NLINES - 1))"

echo
echo "--- 4. Cohérence du nombre de colonnes ---"
awk -F',' -v expected="$NCOLS" 'NR>1 && NF != expected {bad++} END {print "Lignes avec NF != " expected " : " (bad+0)}' "$FILE"

echo
echo "--- 5. Distribution par année de décès (top 5 + total 2019) ---"
awk -F',' 'NR>1 {print substr($8,1,4)}' "$FILE" \
    | sort | uniq -c | sort -rn | head -5
echo "..."
COUNT_2019=$(awk -F',' 'NR>1 && substr($8,1,4)=="2019"' "$FILE" | wc -l | tr -d ' ')
echo "Total 2019 : $COUNT_2019"

echo
echo "--- 6. Code lieu décès : longueurs observées ---"
awk -F',' 'NR>1 {print length($9)}' "$FILE" \
    | sort | uniq -c | sort -rn

echo
echo "--- 7. Codes département (2 premiers caractères de code_lieu_deces, sur 2019) ---"
echo "Top 10 :"
awk -F',' 'NR>1 && substr($8,1,4)=="2019" && length($9)==5 {print substr($9,1,2)}' "$FILE" \
    | sort | uniq -c | sort -rn | head -10
echo "..."
echo "DOM-TOM (codes 97x / 98x) :"
awk -F',' 'NR>1 && substr($8,1,4)=="2019" && length($9)==5 && (substr($9,1,2)=="97" || substr($9,1,2)=="98") {print substr($9,1,3)}' "$FILE" \
    | sort | uniq -c | sort -rn

echo
echo "--- 8. Sexe (sur 2019) ---"
awk -F',' 'NR>1 && substr($8,1,4)=="2019" {print $3}' "$FILE" \
    | sort | uniq -c | sort -rn

echo
echo "--- 9. Min / Max date_deces ---"
awk -F',' 'NR>1 && $8 != "" {print $8}' "$FILE" | sort | head -1 | awk '{print "Min : " $1}'
awk -F',' 'NR>1 && $8 != "" {print $8}' "$FILE" | sort | tail -1 | awk '{print "Max : " $1}'

echo
echo "=========================================="
echo " Profiling terminé"
echo "=========================================="
