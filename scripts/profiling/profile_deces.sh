#!/usr/bin/env bash
# Profiling rapide du fichier INSEE deces.csv — UNE SEULE PASSE.
# Usage : ./profile_deces.sh <chemin_fichier_csv>
#
# Optimisation : l'ancienne version relisait le fichier ~10 fois et triait 25 M
# lignes plusieurs fois (sort externe). Ici tout est agrégé en mémoire en UNE passe
# awk (histogrammes par tableaux associatifs ; min/max date par comparaison
# lexicographique car AAAA-MM-JJ se trie comme une chaîne -> aucun `sort` géant).
# Utilise mawk si disponible (2-5x plus rapide que gawk).

set -euo pipefail
FILE="${1:-}"
if [[ -z "$FILE" || ! -f "$FILE" ]]; then
    echo "Usage: $0 <path-to-deces.csv>" >&2
    exit 1
fi
AWK=$(command -v mawk || command -v gawk || command -v awk)

echo "=========================================="
echo " Profiling : $FILE"
echo " Date : $(date '+%Y-%m-%d %H:%M:%S')   (awk: $AWK)"
echo "=========================================="
echo
echo "--- 1. Format & taille ---"
file "$FILE"
ls -lh "$FILE" | awk '{print "Taille brute : " $5}'

# ---- UNE passe : tout est compté ici ----
"$AWK" -F',' '
NR==1 { ncols=NF; header=$0; next }
{
  data++
  if (NF != ncols) bad++
  y = substr($8,1,4); year[y]++
  l = length($9); len9[l]++
  if ($8 ~ /^[0-9]{4}-[0-9]{2}-[0-9]{2}/) { if (mn=="" || $8<mn) mn=$8; if ($8>mx) mx=$8 }
  else if ($8 != "") badcol++
  if (y=="2019") {
    c2019++; sexe[$3]++
    if (l==5) { d2=substr($9,1,2); dept[d2]++;
      if (d2=="97"||d2=="98") dom[substr($9,1,3)]++ }
  }
}
END {
  print "HEADER\t" header
  print "NCOLS\t" ncols
  print "DATA\t" data
  print "BAD\t" bad+0
  print "C2019\t" c2019+0
  print "MIN\t" mn
  print "MAX\t" mx
  print "BADCOL\t" badcol+0
  for (k in year) print "YEAR\t" k "\t" year[k]
  for (k in len9) print "LEN\t"  k "\t" len9[k]
  for (k in dept) print "DEPT\t" k "\t" dept[k]
  for (k in dom)  print "DOM\t"  k "\t" dom[k]
  for (k in sexe) print "SEXE\t" k "\t" sexe[k]
}' "$FILE" > /tmp/deces_prof.$$

# ---- restitution (les tableaux à trier sont minuscules : années ~20, dept ~100) ----
g(){ grep "^$1"$'\t' /tmp/deces_prof.$$; }
v(){ g "$1" | cut -f2; }

echo
echo "--- 2. Header & colonnes ---"
v HEADER
echo "Nombre de colonnes : $(v NCOLS)"
echo
echo "--- 3. Volumétrie ---"
echo "Lignes de données : $(v DATA)"
echo
echo "--- 4. Cohérence colonnes ---"
echo "Lignes avec NF != $(v NCOLS) : $(v BAD)"
echo
echo "--- 5. Distribution par année (top 5 + 2019) ---"
g YEAR | sort -t$'\t' -k3 -rn | head -5 | awk -F'\t' '{printf "%10d  %s\n",$3,$2}'
echo "..."
echo "Total 2019 : $(v C2019)"
echo
echo "--- 6. Longueurs de code_lieu_deces ---"
g LEN | sort -t$'\t' -k3 -rn | awk -F'\t' '{printf "%10d  longueur %s\n",$3,$2}'
echo
echo "--- 7. Départements (2019, top 10) ---"
g DEPT | sort -t$'\t' -k3 -rn | head -10 | awk -F'\t' '{printf "%10d  %s\n",$3,$2}'
echo "DOM-TOM (97x / 98x) :"
g DOM | sort -t$'\t' -k3 -rn | awk -F'\t' '{printf "%10d  %s\n",$3,$2}'
echo
echo "--- 8. Sexe (2019) ---"
g SEXE | sort -t$'\t' -k3 -rn | awk -F'\t' '{printf "%10d  %s\n",$3,$2}'
echo
echo "--- 9. Min / Max date_deces ---"
echo "Min : $(v MIN)"
echo "Max : $(v MAX)"
echo "Lignes à date non conforme (champ décalé) : $(v BADCOL)"

rm -f /tmp/deces_prof.$$
echo
echo "=========================================="
echo " Profiling terminé (1 passe)"
echo "=========================================="
