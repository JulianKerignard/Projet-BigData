#!/usr/bin/env python3
"""Graphe du benchmark data-prep décès : temps + pic RAM par variante.
Lit scripts/benchmark/dataprep_results.csv (variante,run,temps_s,ram_mo)
-> scripts/benchmark/benchmark_dataprep.png. Échelle log (écarts x40 / x600)."""
import csv, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
LABELS = {"duckdb_stream": "DuckDB\nstreaming (VIEW)",
          "duckdb_materialise": "DuckDB\nmatérialisé",
          "awk_1passe": "awk\n1-passe"}
ORDER = ["duckdb_stream", "duckdb_materialise", "awk_1passe"]
C = {"duckdb_stream": "#2e7d9a", "duckdb_materialise": "#9aa7b4", "awk_1passe": "#e8590c"}

agg = {}
with open(os.path.join(HERE, "dataprep_results.csv")) as fh:
    for r in csv.DictReader(fh):
        if r["temps_s"] == "NA":
            continue
        agg.setdefault(r["variante"], {"t": [], "m": []})
        agg[r["variante"]]["t"].append(float(r["temps_s"]))
        agg[r["variante"]]["m"].append(float(r["ram_mo"]))

vs = [v for v in ORDER if v in agg]
mean = lambda xs: sum(xs) / len(xs)
times = [mean(agg[v]["t"]) for v in vs]
rams = [mean(agg[v]["m"]) for v in vs]
cols = [C[v] for v in vs]
labs = [LABELS[v] for v in vs]

fig, (axA, axB) = plt.subplots(1, 2, figsize=(11, 5))
fig.suptitle("Benchmark data-prep Décès (25 M lignes / 1,9 Go) — temps vs pic RAM",
             fontsize=14, fontweight="bold")

axA.bar(labs, times, color=cols, width=0.6)
axA.set_yscale("log")
axA.set_ylabel("Temps moyen (s) — échelle log")
axA.set_title("(A) Vitesse")
for i, t in enumerate(times):
    axA.text(i, t * 1.08, f"{t:.2f} s", ha="center", fontsize=10, fontweight="bold")
axA.grid(axis="y", alpha=0.3)

axB.bar(labs, rams, color=cols, width=0.6)
axB.set_yscale("log")
axB.set_ylabel("Pic RAM (Mo) — échelle log")
axB.set_title("(B) Mémoire")
for i, m in enumerate(rams):
    axB.text(i, m * 1.08, f"{m:.0f} Mo", ha="center", fontsize=10, fontweight="bold")
axB.grid(axis="y", alpha=0.3)

fig.text(0.5, 0.005,
         "Lecture : DuckDB streaming = meilleur compromis (RAM ÷4 vs matérialisé, ~250× plus rapide qu'awk). "
         "Matérialisé est le plus rapide mais consomme ~1,3 Go. awk = RAM minimale mais mono-thread (40 s).",
         ha="center", fontsize=8, style="italic", color="#444")
fig.tight_layout(rect=[0, 0.04, 1, 0.95])
out = os.path.join(HERE, "benchmark_dataprep.png")
fig.savefig(out, dpi=140)
print("[ok]", out)
