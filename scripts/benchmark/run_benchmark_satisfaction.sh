#!/usr/bin/env bash
# =============================================================================
# [P3] Benchmark perf Satisfaction — avant / après partition + bucketing (B8)
# Tâche ClickUp : 869dfg1gt
#
# Exécute R1/R2 N fois sur bench_satisfaction_flat (baseline) et bench_satisfaction_pb
# (optimisée) — tables JETABLES (cf. sql/benchmark/satisfaction_benchmark.sql), la Gold
# fait_satisfaction n'est jamais touchée. Capture le temps Beeline + l'I/O scanné (hdfs du).
#
# Pré-requis : fait_satisfaction chargée + sql/benchmark/satisfaction_benchmark.sql exécuté.
# Usage (depuis n'importe quel cwd) : bash scripts/benchmark/run_benchmark_satisfaction.sh [N=3]
# =============================================================================
set -uo pipefail
N=${1:-3}
CONTAINER="chu-hive-server"
JDBC="jdbc:hive2://localhost:10000/chu_entrepot"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_CSV="$HERE/satisfaction_results.csv"
IO_TXT="$HERE/satisfaction_io.txt"

QUERIES=(
  "R1_region_2020|base|SELECT e.region, AVG(f.note_satisfaction) FROM bench_satisfaction_flat f JOIN dim_etablissement e ON f.etab_id=e.etab_id WHERE f.annee=2020 GROUP BY e.region"
  "R1_region_2020|opt|SELECT e.region, AVG(f.note_satisfaction) FROM bench_satisfaction_pb f JOIN dim_etablissement e ON f.etab_id=e.etab_id WHERE f.annee=2020 GROUP BY e.region"
  "R2_region_all|base|SELECT geo_id, AVG(note_satisfaction) FROM bench_satisfaction_flat GROUP BY geo_id"
  "R2_region_all|opt|SELECT geo_id, AVG(note_satisfaction) FROM bench_satisfaction_pb GROUP BY geo_id"
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

# I/O scanné (Mo) : baseline = table flat entière ; opt R1 = 1 partition (annee=2020).
b=$(docker exec "$CONTAINER" hdfs dfs -du -s /chu/gold/bench_satisfaction_flat 2>/dev/null | awk '{print $1}')
o=$(docker exec "$CONTAINER" hdfs dfs -du -s /chu/gold/bench_satisfaction_pb/annee=2020 2>/dev/null | awk '{print $1}')
if [ -n "${b:-}" ] && [ -n "${o:-}" ] && [ "$o" -gt 0 ]; then
  awk -v b="$b" -v o="$o" 'BEGIN{printf "%.3f,%.3f\n", b/1048576, o/1048576}' > "$IO_TXT"
  echo "I/O Mo (base,opt) -> $(cat "$IO_TXT")"
fi
echo "✅ $OUT_CSV"
