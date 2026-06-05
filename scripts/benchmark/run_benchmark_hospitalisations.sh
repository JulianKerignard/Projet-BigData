#!/usr/bin/env bash
# =============================================================================
# [P2] Benchmark perf Hospitalisations — avant / après partition + bucketing (B3/B4/B5)
# Tâche ClickUp : benchmark Hospitalisation avant/après + graphes
#
# Exécute Q1/Q2/Q3/Q4 N fois sur bench_hospitalisation_flat (baseline) et
# bench_hospitalisation_pb (optimisée) — tables JETABLES (cf.
# sql/benchmark/hospitalisations_benchmark.sql), la Gold fait_hospitalisation n'est
# jamais touchée. Capture le temps Beeline + l'I/O scanné (hdfs du).
#
# Pré-requis : fait_hospitalisation chargée + hospitalisations_benchmark.sql exécuté.
# Usage (depuis n'importe quel cwd) : bash scripts/benchmark/run_benchmark_hospitalisations.sh [N=3]
# =============================================================================
set -uo pipefail
N=${1:-3}
CONTAINER="chu-hive-server"
JDBC="jdbc:hive2://localhost:10000/chu_entrepot"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_CSV="$HERE/hospitalisation_results.csv"
IO_TXT="$HERE/hospitalisation_io.txt"

QUERIES=(
  "Q1_filter_year|base|SELECT SUM(nb_hospitalisation) FROM bench_hospitalisation_flat WHERE annee=2020"
  "Q1_filter_year|opt|SELECT SUM(nb_hospitalisation) FROM bench_hospitalisation_pb WHERE annee=2020"
  "Q2_by_diag|base|SELECT diag_id, SUM(nb_hospitalisation) AS nb FROM bench_hospitalisation_flat WHERE annee=2020 GROUP BY diag_id ORDER BY nb DESC LIMIT 10"
  "Q2_by_diag|opt|SELECT diag_id, SUM(nb_hospitalisation) AS nb FROM bench_hospitalisation_pb WHERE annee=2020 GROUP BY diag_id ORDER BY nb DESC LIMIT 10"
  "Q3_join_etab|base|SELECT e.nom_etab, SUM(f.nb_hospitalisation) AS nb, AVG(f.duree_sejour) AS dms FROM bench_hospitalisation_flat f JOIN dim_etablissement e ON e.etab_id=f.etab_id WHERE f.annee=2020 GROUP BY e.nom_etab ORDER BY nb DESC LIMIT 10"
  "Q3_join_etab|opt|SELECT e.nom_etab, SUM(f.nb_hospitalisation) AS nb, AVG(f.duree_sejour) AS dms FROM bench_hospitalisation_pb f JOIN dim_etablissement e ON e.etab_id=f.etab_id WHERE f.annee=2020 GROUP BY e.nom_etab ORDER BY nb DESC LIMIT 10"
  "Q4_by_sexe_age|base|SELECT p.sexe, p.tranche_age, SUM(f.nb_hospitalisation) AS nb FROM bench_hospitalisation_flat f JOIN dim_patient p ON p.patient_id=f.patient_id WHERE f.annee=2020 GROUP BY p.sexe, p.tranche_age"
  "Q4_by_sexe_age|opt|SELECT p.sexe, p.tranche_age, SUM(f.nb_hospitalisation) AS nb FROM bench_hospitalisation_pb f JOIN dim_patient p ON p.patient_id=f.patient_id WHERE f.annee=2020 GROUP BY p.sexe, p.tranche_age"
)

echo "query,variant,run,duration_sec" > "$OUT_CSV"
for entry in "${QUERIES[@]}"; do
  IFS='|' read -r label variant sql <<< "$entry"
  echo "▶ $label / $variant"
  for run in $(seq 1 "$N"); do
    out=$(docker exec "$CONTAINER" beeline -u "$JDBC" -e "$sql;" 2>&1)
    dur=$(echo "$out" | grep -oE '\([0-9]+\.[0-9]+ seconds\)' | tail -1 | grep -oE '[0-9]+\.[0-9]+')
    echo "  run $run : ${dur:-NA}s"
    echo "$label,$variant,$run,${dur:-NA}" >> "$OUT_CSV"
  done
done

# I/O scanné (Mo) : baseline = table flat entière ; opt Q1 = 1 partition (annee=2020).
b=$(docker exec "$CONTAINER" hdfs dfs -du -s /chu/gold/bench_hospitalisation_flat 2>/dev/null | awk '{print $1}')
o=$(docker exec "$CONTAINER" hdfs dfs -du -s /chu/gold/bench_hospitalisation_pb/annee=2020 2>/dev/null | awk '{print $1}')
if [ -n "${b:-}" ] && [ -n "${o:-}" ] && [ "$o" -gt 0 ]; then
  awk -v b="$b" -v o="$o" 'BEGIN{printf "%.3f,%.3f\n", b/1048576, o/1048576}' > "$IO_TXT"
  echo "I/O Mo (base,opt) -> $(cat "$IO_TXT")"
fi
echo "✅ $OUT_CSV"
