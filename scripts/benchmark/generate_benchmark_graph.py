#!/usr/bin/env python3
"""
[L2] Générateur de figure de synthèse d'un benchmark (commun décès & satisfaction).

Lit  scripts/benchmark/<bench>_results.csv  (format long : query,variant,run,duration_sec
avec variant ∈ {base, opt}) et produit  scripts/benchmark/<bench>.png : figure 2 panneaux —
  (A) temps wall-clock baseline vs optimisée (barres = min/max),
  (B) I/O réellement scanné (via EXPLAIN) -> le vrai gain du partition pruning.

Usage : python3 scripts/benchmark/generate_benchmark_graph.py <deces|satisfaction>
Dépendances : matplotlib, numpy.
"""
import csv, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))

CONFIG = {
    "deces": {
        "csv": "benchmark_deces_results.csv",
        "out": "benchmark_deces.png",
        "title": "Benchmark Décès (B7) — partition + bucketing sur Hive 2.3.2",
        "io_base_mb": 25.6, "io_opt_mb": 5.2,
        "io_label": "Données scannées — Q1 (Mo, via EXPLAIN)",
        "order": ["Q1_filter_year", "Q2_top_regions", "Q3_join_geo", "Q4_cube_sex_age"],
        "labels": {"Q1_filter_year": "Q1\nfiltre année", "Q2_top_regions": "Q2\ntop régions",
                   "Q3_join_geo": "Q3\njoin région", "Q4_cube_sex_age": "Q4\nsexe × âge"},
    },
    "satisfaction": {
        "csv": "satisfaction_results.csv",
        "out": "benchmark_satisfaction.png",
        "title": "Benchmark Satisfaction (B8) — partition + bucketing sur Hive 2.3.2",
        "io_base_mb": 0.028, "io_opt_mb": 0.016,  # mesuré via hdfs du (run 2026-06-04)
        "io_label": "Données scannées — R1 (Mo, hdfs du)",
        "order": ["R1_region_2020", "R2_region_all"],
        "labels": {"R1_region_2020": "R1\nrégion 2020", "R2_region_all": "R2\nrégion (toutes)"},
    },
    "consultation": {
        "csv": "consultation_results.csv",
        "out": "benchmark_consultation.png",
        "title": "Benchmark Consultations (B2/B6) — partition + bucketing sur Hive 2.3.2",
        "io_base_mb": 0.049, "io_opt_mb": 0.025,  # mesuré via hdfs du (run 2026-06-04)
        "io_label": "Données scannées — Q1 (Mo, hdfs du)",
        "order": ["Q1_filter_year", "Q2_by_prof", "Q3_by_diag"],
        "labels": {"Q1_filter_year": "Q1\nfiltre année", "Q2_by_prof": "Q2\npar prof (B6)",
                   "Q3_by_diag": "Q3\npar diag (B2)"},
    },
}

C_BASE, C_OPT = "#9aa7b4", "#2e7d9a"


def load(csv_path):
    if not os.path.exists(csv_path):
        sys.exit(f"[!] CSV introuvable : {csv_path} — lance d'abord le runner du benchmark.")
    agg = {}
    with open(csv_path, newline="") as fh:
        for r in csv.DictReader(fh):
            d = (r.get("duration_sec") or "").strip()
            if d in ("", "NA"):
                continue
            agg.setdefault((r["query"], r["variant"]), []).append(float(d))
    return agg


def stats(vals):
    m = sum(vals) / len(vals)
    return m, m - min(vals), max(vals) - m


def read_io(bench, cfg):
    """I/O en Mo : depuis <bench>_io.txt (base_mb,opt_mb) sinon valeurs du config."""
    p = os.path.join(HERE, f"{bench}_io.txt")
    if os.path.exists(p):
        with open(p) as fh:
            parts = fh.read().strip().split(",")
            if len(parts) == 2:
                return float(parts[0]), float(parts[1])
    return cfg["io_base_mb"], cfg["io_opt_mb"]


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in CONFIG:
        sys.exit("Usage: generate_benchmark_graph.py <deces|satisfaction>")
    bench = sys.argv[1]; cfg = CONFIG[bench]

    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    agg = load(os.path.join(HERE, cfg["csv"]))
    queries = [q for q in cfg["order"] if (q, "opt") in agg and (q, "base") in agg]
    if not queries:
        sys.exit(f"[!] aucune mesure exploitable dans {cfg['csv']}")
    base = [stats(agg[(q, "base")]) for q in queries]
    opt = [stats(agg[(q, "opt")]) for q in queries]
    io_base, io_opt = read_io(bench, cfg)
    has_io = io_base and io_opt

    ratios = [2.3, 1] if has_io else [1, 0.001]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw={"width_ratios": ratios})
    axA, axB = axes
    fig.suptitle(cfg["title"], fontsize=14, fontweight="bold")

    # Panneau A — temps wall-clock
    x = np.arange(len(queries)); w = 0.38
    axA.bar(x - w/2, [b[0] for b in base], w, yerr=[[b[1] for b in base], [b[2] for b in base]],
            capsize=4, label="Baseline (sans partition/bucket)", color=C_BASE)
    axA.bar(x + w/2, [o[0] for o in opt], w, yerr=[[o[1] for o in opt], [o[2] for o in opt]],
            capsize=4, label="Optimisée (partition + bucket)", color=C_OPT)
    for i, (b, o) in enumerate(zip(base, opt)):
        axA.text(x[i] - w/2, b[0] + b[2] + 0.06, f"{b[0]:.2f}", ha="center", fontsize=8, color="#555")
        axA.text(x[i] + w/2, o[0] + o[2] + 0.06, f"{o[0]:.2f}", ha="center", fontsize=8, color="#1b4f63")
    axA.set_xticks(x); axA.set_xticklabels([cfg["labels"][q] for q in queries], fontsize=9)
    axA.set_ylabel("Temps moyen (s) — barres = min/max")
    axA.set_title("(A) Temps wall-clock : ~PARITÉ\n(overhead Hive ~2 s + MapReduce local séquentiel)", fontsize=10)
    axA.set_ylim(0, max(b[0] + b[2] for b in base + opt) * 1.18)
    axA.legend(fontsize=8, loc="upper right"); axA.grid(axis="y", alpha=0.3)

    # Panneau B — I/O scanné (÷N)
    if has_io:
        axB.bar(["Baseline", "Optimisée"], [io_base, io_opt], color=[C_BASE, C_OPT], width=0.6)
        axB.set_ylim(0, io_base * 1.18)
        for i, v in enumerate([io_base, io_opt]):
            axB.text(i, v + io_base * 0.03, f"{v:g} Mo", ha="center", fontsize=10, fontweight="bold")
        axB.annotate(f"÷ {io_base/io_opt:.0f}", xy=(0.78, io_opt + io_base * 0.05),
                     xytext=(0.42, io_base * 0.62), ha="center", fontsize=16,
                     fontweight="bold", color=C_OPT, arrowprops=dict(arrowstyle="->", color=C_OPT, lw=1.6))
        axB.set_ylabel(cfg["io_label"])
        axB.set_title(f"(B) I/O réellement scanné : ÷ {io_base/io_opt:.0f}\n(partition pruning)", fontsize=10)
        axB.grid(axis="y", alpha=0.3)
    else:
        axB.axis("off")

    fig.text(0.5, 0.005,
             "Lecture : le partition pruning réduit l'I/O, mais à cette échelle (MapReduce local, faible volume) "
             "le gain est masqué par l'overhead Hive → bénéfice wall-clock visible seulement sur cluster distribué à grande échelle.",
             ha="center", fontsize=8, style="italic", color="#444")
    fig.tight_layout(rect=[0, 0.04, 1, 0.95])
    out = os.path.join(HERE, cfg["out"])
    fig.savefig(out, dpi=140)
    print(f"[ok] Graphe écrit : {out}")


if __name__ == "__main__":
    main()
