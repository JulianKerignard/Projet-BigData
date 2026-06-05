#!/usr/bin/env bash
# =============================================================================
# [P1] Benchmark perf Consultations — avant / après partition + bucketing (B2/B6)
# Tâche ClickUp : 869dfg1b1
#
# Exécute Q1/Q2/Q3 N fois sur bench_consultation_flat (baseline) et
# bench_consultation_pb (optimisée) — tables JETABLES (cf.
# sql/benchmark/consultations_benchmark.sql), la Gold fait_consultation n'est jamais
# touchée. Capture le temps Beeline + l'I/O scanné (hdfs du).
#
# Pré-requis : fait_consultation chargée + consultations_benchmark.sql exécuté.
# Usage (depuis n'importe quel cwd) : bash scripts/benchmark/run_benchmark_consultations.sh [N=3]
# =============================================================================
set -uo pipefail
N=${1:-3}
CONTAINER="chu-hive-server"
JDBC="jdbc:hive2://localhost:10000/chu_entrepot"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_CSV="$HERE/consultation_results.csv"
IO_TXT="$HERE/consultation_io.txt"

QUERIES=(
  "Q1_filter_year|base|SELECT SUM(nb_consultation) FROM bench_consultation_flat WHERE annee=2020"
  "Q1_filter_year|opt|SELECT SUM(nb_consultation) FROM bench_consultation_pb WHERE annee=2020"
  "Q2_by_prof|base|SELECT prof_id, SUM(nb_consultation) AS nb FROM bench_consultation_flat WHERE annee=2020 GROUP BY prof_id ORDER BY nb DESC"
  "Q2_by_prof|opt|SELECT prof_id, SUM(nb_consultation) AS nb FROM bench_consultation_pb WHERE annee=2020 GROUP BY prof_id ORDER BY nb DESC"
  "Q3_by_diag|base|SELECT diag_id, SUM(nb_consultation) AS nb FROM bench_consultation_flat WHERE annee=2020 GROUP BY diag_id ORDER BY nb DESC LIMIT 10"
  "Q3_by_diag|opt|SELECT diag_id, SUM(nb_consultation) AS nb FROM bench_consultation_pb WHERE annee=2020 GROUP BY diag_id ORDER BY nb DESC LIMIT 10"
)

echo "query,variant,run,duration_sec" > "$OUT_CSV"
for entry in "${QUERIES[@]}"; do
  IFS='|' read -r label variant sql <<< "$entry"
  echo "▶ $label / $variant"
  for run in $(seq 1 "$N"); do
    out=$(docker exec "$CONTAINER" beeline -u "$JDBC" -e "$sql;" 2>&1)
    dur=$(echo "$out" | grep -oE '\([0-9]+\.[0-9]+ seconds\)' | tail -1 | grep -oE '[0-9]+\.[0-9]+')
    echo "$label,$variant,$run,${dur:-NA}" >> "$OUT_CSV"
  done
done

# I/O scanné (Mo) : baseline = table flat entière ; opt Q1 = 1 partition (annee=2020).
b=$(docker exec "$CONTAINER" hdfs dfs -du -s /chu/gold/bench_consultation_flat 2>/dev/null | awk '{print $1}')
o=$(docker exec "$CONTAINER" hdfs dfs -du -s /chu/gold/bench_consultation_pb/annee=2020 2>/dev/null | awk '{print $1}')
if [ -n "${b:-}" ] && [ -n "${o:-}" ] && [ "$o" -gt 0 ]; then
  awk -v b="$b" -v o="$o" 'BEGIN{printf "%.3f,%.3f\n", b/1048576, o/1048576}' > "$IO_TXT"
  echo "I/O Mo (base,opt) -> $(cat "$IO_TXT")"
fi
echo "✅ $OUT_CSV"
