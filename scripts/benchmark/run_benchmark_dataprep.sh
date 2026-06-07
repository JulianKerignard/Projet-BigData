#!/usr/bin/env bash
# =============================================================================
# Benchmark DATA-PREP décès : DuckDB streaming (VIEW) vs DuckDB matérialisé
# (CREATE TABLE) vs awk 1-passe. Mesure temps (real) + pic RAM (max RSS) sur
# deces.csv (1,9 Go, 25 M lignes). Tâche commune = 3 agrégats : histogramme
# année + histogramme longueur(code_lieu_deces) + répartition sexe 2019.
#
# Usage : bash scripts/benchmark/run_benchmark_dataprep.sh [N=3] [chemin_csv]
# Pré-requis : duckdb, awk, /usr/bin/time (macOS/BSD : flag -l pour le RSS).
# =============================================================================
set -uo pipefail
N=${1:-3}
F="${2:-DATA 2024/DECES EN FRANCE/deces.csv}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/dataprep_results.csv"
TMP=$(mktemp)

# Projection + agrégats communs (DuckDB)
SEL="SELECT substr(date_deces,1,4) y,count(*) FROM d GROUP BY y;
     SELECT length(code_lieu_deces) l,count(*) FROM d GROUP BY l;
     SELECT sexe,count(*) FROM d WHERE substr(date_deces,1,4)='2019' GROUP BY sexe;"
RD="read_csv('$F',header=true,sep=',',quote='\"',all_varchar=true,ignore_errors=true)"

echo "variante,run,temps_s,ram_mo" > "$OUT"
bench(){ # $1=label ; $2..=commande (moteur direct -> /usr/bin/time mesure le bon process)
  local label="$1"; shift
  for r in $(seq 1 "$N"); do
    /usr/bin/time -l "$@" >/dev/null 2>"$TMP" || true
    local t=$(awk '/ real/{print $1; exit}' "$TMP")
    local m=$(awk '/maximum resident set size/{printf "%.0f",$1/1048576; exit}' "$TMP")
    echo "$label,$r,${t:-NA},${m:-NA}" >> "$OUT"
    echo "  $label run $r : ${t}s, ${m} Mo"
  done
}

echo "▶ DuckDB streaming (VIEW)"
bench duckdb_stream duckdb -c "CREATE VIEW d AS SELECT sexe,date_deces,code_lieu_deces FROM $RD; $SEL"
echo "▶ DuckDB matérialisé (CREATE TABLE)"
bench duckdb_materialise duckdb -c "CREATE TABLE d AS SELECT sexe,date_deces,code_lieu_deces FROM $RD; $SEL"
echo "▶ awk 1-passe"
bench awk_1passe awk -F',' 'NR>1{y[substr($8,1,4)]++; l[length($9)]++; if(substr($8,1,4)=="2019")s[$3]++} END{}' "$F"

rm -f "$TMP"
echo
echo "=== moyennes ==="
awk -F',' 'NR>1 && $3!="NA"{ts[$1]+=$3; ms[$1]+=$4; n[$1]++} END{for(k in n)printf "  %-20s temps=%.2fs  ram=%.0f Mo (n=%d)\n",k,ts[k]/n[k],ms[k]/n[k],n[k]}' "$OUT" | sort
echo "✅ $OUT"
