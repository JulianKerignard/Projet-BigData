#!/usr/bin/env python3
"""
[P4] Benchmark Décès — figure de synthèse (temps wall-clock + I/O scanné).

Lit  scripts/benchmark/benchmark_deces_results.csv (mesures réelles, 3 runs/cas) et
produit scripts/benchmark/benchmark_deces.png : figure 2 panneaux qui raconte le
résultat honnête du benchmark —
  (A) le temps wall-clock baseline vs optimisée est ~à PARITÉ (overhead Hive + MR local),
  (B) mais l'I/O réellement scanné est divisé par 5 (partition pruning, preuve EXPLAIN).

Usage : python3 scripts/benchmark/generate_graph_deces.py
Dépendances : matplotlib, numpy.
"""
import csv, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "benchmark_deces_results.csv")
OUT = os.path.join(HERE, "benchmark_deces.png")

# Volume scanné (Mo) issu de l'EXPLAIN (cf. docs/L2_Benchmark_Deces.md §4.1) :
# baseline = full scan 5 ans ; optimisée = 1 partition (annee=2019) grâce au pruning.
IO_BASE_MB, IO_OPT_MB = 25.6, 5.2

QUERY_ORDER = ["Q1_filter_year", "Q2_top_regions", "Q3_join_geo", "Q4_cube_sex_age"]
QUERY_LABEL = {
    "Q1_filter_year": "Q1\nfiltre année",
    "Q2_top_regions": "Q2\ntop régions",
    "Q3_join_geo":    "Q3\njoin région",
    "Q4_cube_sex_age": "Q4\nsexe × âge",
}


def load():
    if not os.path.exists(CSV):
        sys.exit(f"[!] CSV introuvable : {CSV} — lance d'abord run_benchmark_deces.sh")
    agg = {}
    with open(CSV, newline="") as fh:
        for r in csv.DictReader(fh):
            d = r.get("duration_sec", "")
            if d in ("", "NA"):
                continue
            agg.setdefault((r["query"], r["variant"]), []).append(float(d))
    return agg


def stats(vals):
    m = sum(vals) / len(vals)
    return m, m - min(vals), max(vals) - m   # moyenne, err bas, err haut


def main():
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    agg = load()
    queries = [q for q in QUERY_ORDER if (q, "opt") in agg]
    base = [stats(agg[(q, "base")]) for q in queries]
    opt = [stats(agg[(q, "opt")]) for q in queries]

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(12, 5.2),
                                   gridspec_kw={"width_ratios": [2.3, 1]})
    fig.suptitle("Benchmark Décès (B7) — partition + bucketing sur Hive 2.3.2",
                 fontsize=14, fontweight="bold")

    # --- Panneau A : temps wall-clock (parité) ---
    x = np.arange(len(queries)); w = 0.38
    C_BASE, C_OPT = "#9aa7b4", "#2e7d9a"
    axA.bar(x - w/2, [b[0] for b in base], w, yerr=[[b[1] for b in base], [b[2] for b in base]],
            capsize=4, label="Baseline (sans partition/bucket)", color=C_BASE)
    axA.bar(x + w/2, [o[0] for o in opt], w, yerr=[[o[1] for o in opt], [o[2] for o in opt]],
            capsize=4, label="Optimisée (partition + bucket)", color=C_OPT)
    for i, (b, o) in enumerate(zip(base, opt)):
        axA.text(x[i] - w/2, b[0] + b[2] + 0.12, f"{b[0]:.2f}", ha="center", fontsize=8, color="#555")
        axA.text(x[i] + w/2, o[0] + o[2] + 0.12, f"{o[0]:.2f}", ha="center", fontsize=8, color="#1b4f63")
    axA.set_xticks(x); axA.set_xticklabels([QUERY_LABEL[q] for q in queries], fontsize=9)
    axA.set_ylabel("Temps moyen (s) — barres = min/max")
    axA.set_title("(A) Temps wall-clock : ~PARITÉ\n(overhead Hive ~2 s + MapReduce local séquentiel)", fontsize=10)
    axA.legend(fontsize=8, loc="upper left")
    axA.grid(axis="y", alpha=0.3)

    # --- Panneau B : I/O scanné (÷5) ---
    axB.bar(["Baseline", "Optimisée"], [IO_BASE_MB, IO_OPT_MB], color=[C_BASE, C_OPT], width=0.6)
    axB.set_ylim(0, IO_BASE_MB * 1.18)
    for i, v in enumerate([IO_BASE_MB, IO_OPT_MB]):
        axB.text(i, v + 0.7, f"{v} Mo", ha="center", fontsize=10, fontweight="bold")
    axB.annotate(f"÷ {IO_BASE_MB/IO_OPT_MB:.0f}", xy=(0.78, IO_OPT_MB + 1.2),
                 xytext=(0.42, IO_BASE_MB * 0.62), ha="center", fontsize=16,
                 fontweight="bold", color="#2e7d9a",
                 arrowprops=dict(arrowstyle="->", color="#2e7d9a", lw=1.6))
    axB.set_ylabel("Données scannées — Q1 (Mo, via EXPLAIN)")
    axB.set_title("(B) I/O réellement lu : ÷5\n(partition pruning, le vrai gain)", fontsize=10)
    axB.grid(axis="y", alpha=0.3)

    fig.text(0.5, 0.005,
             "Lecture : le partition pruning divise l'I/O par 5, mais sur ~25 Mo en MapReduce local "
             "le gain est masqué par l'overhead → bénéfice wall-clock visible seulement à grande échelle / sur cluster distribué.",
             ha="center", fontsize=8, style="italic", color="#444")
    fig.tight_layout(rect=[0, 0.04, 1, 0.95])
    fig.savefig(OUT, dpi=140)
    print(f"[ok] Graphe écrit : {OUT}")


if __name__ == "__main__":
    main()
