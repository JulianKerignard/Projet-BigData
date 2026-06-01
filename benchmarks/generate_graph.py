#!/usr/bin/env python3
"""
[P3] Benchmark Satisfaction — calcul des moyennes / gains et génération du graphe.

Usage :
    python3 benchmarks/generate_graph.py

Lit  benchmarks/satisfaction_results.csv (rempli avec les 3 mesures par cas issues de
hive -f benchmarks/satisfaction_benchmark.sql), recalcule moyenne_s + gain_pct_vs_v1,
réécrit le CSV, et produit benchmarks/satisfaction_graph.png (bar chart comparatif).

Dépendance optionnelle : matplotlib (pour le PNG). Sans elle, le script met quand même
le CSV à jour et affiche un tableau ASCII.
"""
import csv, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "satisfaction_results.csv")


def fnum(x):
    if x is None or str(x).strip() == "":
        return None
    return float(str(x).replace(",", "."))


def main():
    with open(CSV, newline="") as fh:
        rows = list(csv.DictReader(fh))

    # 1. moyenne des 3 runs
    for r in rows:
        runs = [fnum(r.get("run1_s")), fnum(r.get("run2_s")), fnum(r.get("run3_s"))]
        runs = [v for v in runs if v is not None]
        r["moyenne_s"] = round(sum(runs) / len(runs), 3) if runs else ""

    # 2. gain % vs V1 (même requête)
    base = {}
    for r in rows:
        if r["version"] == "V1" and r["moyenne_s"] != "":
            base[r["requete"]] = r["moyenne_s"]
    for r in rows:
        b = base.get(r["requete"])
        if b and r["moyenne_s"] != "":
            r["gain_pct_vs_v1"] = round((b - r["moyenne_s"]) / b * 100, 1)
        else:
            r["gain_pct_vs_v1"] = ""

    # 3. réécriture du CSV
    fields = ["requete", "version", "config", "run1_s", "run2_s", "run3_s",
              "moyenne_s", "gain_pct_vs_v1", "exemple"]
    with open(CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})

    # 4. tableau ASCII
    print(f"{'requete':32} {'ver':4} {'moy(s)':>8} {'gain%':>7}")
    for r in rows:
        print(f"{r['requete']:32} {r['version']:4} "
              f"{str(r['moyenne_s']):>8} {str(r['gain_pct_vs_v1']):>7}")

    if not any(r["moyenne_s"] != "" for r in rows):
        print("\n[!] Aucune mesure dans le CSV — remplis run1_s/run2_s/run3_s puis relance.")
        return

    # 5. graphe
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n[i] matplotlib absent : CSV mis à jour, PNG non généré.")
        print("    pip install matplotlib  (ou tracer le graphe depuis le CSV dans Excel).")
        return

    requetes = sorted({r["requete"] for r in rows})
    versions = ["V1", "V2", "V3"]
    labels = {"V1": "brute", "V2": "partition", "V3": "partition+bucket"}
    data = {q: {v: next((fnum(r["moyenne_s"]) for r in rows
                         if r["requete"] == q and r["version"] == v), None)
                for v in versions} for q in requetes}

    import numpy as np
    x = np.arange(len(requetes)); width = 0.25
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, v in enumerate(versions):
        vals = [data[q][v] or 0 for q in requetes]
        ax.bar(x + (i - 1) * width, vals, width, label=labels[v])
    ax.set_ylabel("Temps moyen (s)")
    ax.set_title("Benchmark Satisfaction — temps d'exécution par configuration")
    ax.set_xticks(x); ax.set_xticklabels(requetes, rotation=10, ha="right", fontsize=8)
    ax.legend()
    fig.tight_layout()
    out = os.path.join(HERE, "satisfaction_graph.png")
    fig.savefig(out, dpi=130)
    print(f"\n[ok] Graphe écrit : {out}")


if __name__ == "__main__":
    main()
