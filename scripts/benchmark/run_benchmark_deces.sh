#!/usr/bin/env bash
# =============================================================================
# [P4] Benchmark perf Fait_Deces — avant / après partition + bucketing
# Tâche ClickUp : 869dfg1ne
#
# Exécute chaque requête N fois sur fait_deces (optimisée) et fait_deces_baseline
# (non optimisée), capture le temps Hive ("(X.Y seconds)"), et produit un CSV
# de résultats consommable par le rapport L2.
#
# Pré-requis :
#   - docker compose -f docker/docker-compose.hive.yml up -d
#   - fait_deces alimentée (deces_cleaning.hql)
#   - fait_deces_baseline créée (sql/benchmark/00_create_baseline_deces.hql)
#
# Usage :
#   bash scripts/benchmark/run_benchmark_deces.sh [N_runs=3]
# =============================================================================
set -uo pipefail   # pas de -e : on tolère un grep no-match sans tuer le script

N=${1:-3}
CONTAINER="chu-hive-server"
JDBC="jdbc:hive2://localhost:10000/chu_entrepot"
OUT_CSV="docs/benchmark_deces_results.csv"

QUERIES=(
  "Q1_filter_year|opt|SELECT SUM(nb_deces) FROM fait_deces WHERE annee=2019"
  "Q1_filter_year|base|SELECT SUM(nb_deces) FROM fait_deces_baseline WHERE annee=2019"
  "Q2_top_regions|opt|SELECT geo_id, SUM(nb_deces) AS nb FROM fait_deces WHERE annee=2019 GROUP BY geo_id ORDER BY nb DESC LIMIT 5"
  "Q2_top_regions|base|SELECT geo_id, SUM(nb_deces) AS nb FROM fait_deces_baseline WHERE annee=2019 GROUP BY geo_id ORDER BY nb DESC LIMIT 5"
  "Q3_join_geo|opt|SELECT g.region, SUM(f.nb_deces) AS nb FROM fait_deces f JOIN dim_geographie g ON g.geo_id=f.geo_id WHERE f.annee=2019 GROUP BY g.region ORDER BY nb DESC LIMIT 5"
  "Q3_join_geo|base|SELECT g.region, SUM(f.nb_deces) AS nb FROM fait_deces_baseline f JOIN dim_geographie g ON g.geo_id=f.geo_id WHERE f.annee=2019 GROUP BY g.region ORDER BY nb DESC LIMIT 5"
  "Q4_cube_sex_age|opt|SELECT sexe, tranche_age, SUM(nb_deces) FROM fait_deces WHERE annee=2019 GROUP BY sexe, tranche_age"
  "Q4_cube_sex_age|base|SELECT sexe, tranche_age, SUM(nb_deces) FROM fait_deces_baseline WHERE annee=2019 GROUP BY sexe, tranche_age"
)

echo "query,variant,run,duration_sec" > "$OUT_CSV"

for entry in "${QUERIES[@]}"; do
  IFS='|' read -r label variant sql <<< "$entry"
  echo "▶ $label / $variant"
  for run in $(seq 1 "$N"); do
    out=$(docker exec "$CONTAINER" beeline -u "$JDBC" -e "$sql;" 2>&1)
    # Capture le motif: "(2.083 seconds)" produit par beeline en bas de chaque query
    dur=$(echo "$out" | grep -oE '\([0-9]+\.[0-9]+ seconds\)' | tail -1 | grep -oE '[0-9]+\.[0-9]+')
    dur=${dur:-NA}
    echo "  run $run : ${dur}s"
    echo "$label,$variant,$run,$dur" >> "$OUT_CSV"
  done
done

echo
echo "=== résumé moyenne par requête × variant ==="
awk -F',' 'NR>1 && $4!="NA" {sum[$1"|"$2]+=$4; n[$1"|"$2]++} END {for (k in sum) printf "%-25s %.3f s (n=%d)\n", k, sum[k]/n[k], n[k]}' "$OUT_CSV" | sort

echo
echo "=== gain optimisation (base / opt) ==="
awk -F',' '
  NR>1 && $4!="NA" {sum[$1"|"$2]+=$4; n[$1"|"$2]++}
  END {
    for (k in sum) {
      split(k, p, "|"); q=p[1]; v=p[2]; avg[q"|"v]=sum[k]/n[k]
    }
    for (k in avg) {
      split(k, p, "|"); if (p[2]=="base" && (p[1]"|opt") in avg) {
        printf "  %-18s base=%.2fs opt=%.2fs gain=%.2fx\n", p[1], avg[k], avg[p[1]"|opt"], avg[k]/avg[p[1]"|opt"]
      }
    }
  }' "$OUT_CSV" | sort

echo
echo "✅ Résultats : $OUT_CSV"
