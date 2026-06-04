#!/usr/bin/env bash
# =============================================================================
# [P4] Benchmark perf Décès — avant / après partition + bucketing (B7)
# Tâche ClickUp : 869dfg1ne
#
# Exécute chaque requête N fois sur bench_deces_pb (optimisée) et bench_deces_flat
# (baseline) — tables JETABLES, la Gold canonique fait_deces n'est JAMAIS touchée.
# Capture le temps Beeline ("(X.Y seconds)") et produit un CSV consommable par le
# rapport L2, plus un dump EXPLAIN (preuve reproductible du partition pruning).
#
# NB cache : en dev local le cache est CHAUD entre runs (pas de flush possible sans
# privilèges conteneur) -> seul le run 1 est "à froid". On garde N runs pour la
# dispersion et on retient la médiane (cf. docs/L2_Benchmark_Deces.md §3).
#
# Pré-requis :
#   - docker compose -f docker/docker-compose.hive.yml up -d
#   - fait_deces alimentée (sql/cleaning/deces_cleaning.hql)
#   - tables bench créées (sql/benchmark/00_create_bench_deces.hql)
#
# Usage (depuis n'importe quel cwd) :
#   bash scripts/benchmark/run_benchmark_deces.sh [N_runs=3]
# =============================================================================
set -uo pipefail   # pas de -e : on tolère un grep no-match sans tuer le script

N=${1:-3}
CONTAINER="chu-hive-server"
JDBC="jdbc:hive2://localhost:10000/chu_entrepot"
# Chemins ancrés sur l'emplacement du script (robuste au cwd)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_CSV="$HERE/benchmark_deces_results.csv"
EXPLAIN_OUT="$HERE/benchmark_deces_explain.txt"

QUERIES=(
  "Q1_filter_year|opt|SELECT SUM(nb_deces) FROM bench_deces_pb WHERE annee=2019"
  "Q1_filter_year|base|SELECT SUM(nb_deces) FROM bench_deces_flat WHERE annee=2019"
  "Q2_top_regions|opt|SELECT geo_id, SUM(nb_deces) AS nb FROM bench_deces_pb WHERE annee=2019 GROUP BY geo_id ORDER BY nb DESC LIMIT 5"
  "Q2_top_regions|base|SELECT geo_id, SUM(nb_deces) AS nb FROM bench_deces_flat WHERE annee=2019 GROUP BY geo_id ORDER BY nb DESC LIMIT 5"
  "Q3_join_geo|opt|SELECT g.region, SUM(f.nb_deces) AS nb FROM bench_deces_pb f JOIN dim_geographie g ON g.geo_id=f.geo_id WHERE f.annee=2019 GROUP BY g.region ORDER BY nb DESC LIMIT 5"
  "Q3_join_geo|base|SELECT g.region, SUM(f.nb_deces) AS nb FROM bench_deces_flat f JOIN dim_geographie g ON g.geo_id=f.geo_id WHERE f.annee=2019 GROUP BY g.region ORDER BY nb DESC LIMIT 5"
  "Q4_cube_sex_age|opt|SELECT sexe, tranche_age, SUM(nb_deces) FROM bench_deces_pb WHERE annee=2019 GROUP BY sexe, tranche_age"
  "Q4_cube_sex_age|base|SELECT sexe, tranche_age, SUM(nb_deces) FROM bench_deces_flat WHERE annee=2019 GROUP BY sexe, tranche_age"
)

echo "query,variant,run,duration_sec" > "$OUT_CSV"

for entry in "${QUERIES[@]}"; do
  IFS='|' read -r label variant sql <<< "$entry"
  echo "▶ $label / $variant"
  for run in $(seq 1 "$N"); do
    out=$(docker exec "$CONTAINER" beeline -u "$JDBC" -e "$sql;" 2>&1)
    # Capture le motif Beeline "(2.083 seconds)" en bas de chaque query
    dur=$(echo "$out" | grep -oE '\([0-9]+\.[0-9]+ seconds\)' | tail -1 | grep -oE '[0-9]+\.[0-9]+')
    dur=${dur:-NA}
    echo "  run $run : ${dur}s"
    echo "$label,$variant,$run,$dur" >> "$OUT_CSV"
  done
done

# Preuve reproductible du partition pruning (I/O lu) via EXPLAIN
echo "== EXPLAIN partition pruning (bench_deces_pb vs bench_deces_flat) ==" > "$EXPLAIN_OUT"
docker exec "$CONTAINER" beeline -u "$JDBC" \
  -e "EXPLAIN SELECT SUM(nb_deces) FROM bench_deces_pb WHERE annee=2019;" >> "$EXPLAIN_OUT" 2>&1
docker exec "$CONTAINER" beeline -u "$JDBC" \
  -e "EXPLAIN SELECT SUM(nb_deces) FROM bench_deces_flat WHERE annee=2019;" >> "$EXPLAIN_OUT" 2>&1

echo
echo "=== moyenne / min / max par requête × variant (dispersion) ==="
awk -F',' 'NR>1 && $4!="NA" {
    k=$1"|"$2; sum[k]+=$4; n[k]++;
    if (!(k in mn) || $4<mn[k]) mn[k]=$4;
    if (!(k in mx) || $4>mx[k]) mx[k]=$4
  } END {
    for (k in sum) printf "%-25s moy=%.3f min=%.3f max=%.3f (n=%d)\n", k, sum[k]/n[k], mn[k], mx[k], n[k]
  }' "$OUT_CSV" | sort

echo
echo "✅ Résultats : $OUT_CSV"
echo "✅ EXPLAIN   : $EXPLAIN_OUT"
