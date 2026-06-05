#!/usr/bin/env python3
"""Extrait les agrégats Décès depuis deces.csv (1,9 Go, ~25 M lignes) via DuckDB.

Remplace l'ancien streaming pandas (~5 min) : DuckDB lit le CSV en multi-thread
vectorisé (~quelques secondes) ET respecte les guillemets -> comptes corrects
(l'ancien split naïf sous-comptait ~4 k décès 2019). On garde le mapping
département -> région en Python (noms exacts requis par la carte choroplèthe),
injecté dans une table DuckDB. Sortie identique : viz/data_deces.json
(agrégats par (année, région, sexe, tranche d'âge) ; aucune PII).

Pré-requis : duckdb (brew install duckdb).
"""
import json
import subprocess
import sys
from pathlib import Path

SRC = Path("DATA 2024/DECES EN FRANCE/deces.csv")
OUT = Path("viz/data_deces.json")

# département (code INSEE) -> région (découpage 2016) — noms = clés de la carte
_R = {
    "Auvergne-Rhône-Alpes": "01 03 07 15 26 38 42 43 63 69 73 74".split(),
    "Bourgogne-Franche-Comté": "21 25 39 58 70 71 89 90".split(),
    "Bretagne": "22 29 35 56".split(),
    "Centre-Val de Loire": "18 28 36 37 41 45".split(),
    "Corse": "2A 2B 20".split(),
    "Grand Est": "08 10 51 52 54 55 57 67 68 88".split(),
    "Hauts-de-France": "02 59 60 62 80".split(),
    "Île-de-France": "75 77 78 91 92 93 94 95".split(),
    "Normandie": "14 27 50 61 76".split(),
    "Nouvelle-Aquitaine": "16 17 19 23 24 33 40 47 64 79 86 87".split(),
    "Occitanie": "09 11 12 30 31 32 34 46 48 65 66 81 82".split(),
    "Pays de la Loire": "44 49 53 72 85".split(),
    "Provence-Alpes-Côte d'Azur": "04 05 06 13 83 84".split(),
    "Guadeloupe": ["971"], "Martinique": ["972"], "Guyane": ["973"],
    "La Réunion": ["974"], "Mayotte": ["976"],
}


def sql_str(s):
    return "'" + s.replace("'", "''") + "'"


def build_sql():
    values = ",".join(
        f"({sql_str(d)},{sql_str(region)})"
        for region, depts in _R.items() for d in depts)
    src = str(SRC).replace("'", "''")
    return f"""
CREATE TABLE dr(dept VARCHAR, region VARCHAR);
INSERT INTO dr VALUES {values};

-- Agrégation EN STREAMING : f ne contient que ~13 k lignes agrégées (pas les 25 M
-- par-ligne) -> pic RAM /4 (la lecture CSV reste en flux multi-thread).
CREATE TABLE f AS
WITH base AS (
  SELECT
    CAST(substr(date_deces, 1, 4) AS INT)            AS annee,
    TRY_CAST(substr(date_naissance, 1, 4) AS INT)    AS an_naiss,
    CASE WHEN sexe = '1' THEN 'H' WHEN sexe = '2' THEN 'F' ELSE '?' END AS sx,
    CASE
      WHEN substr(code_lieu_deces, 1, 2) IN ('2A', '2B') THEN substr(code_lieu_deces, 1, 2)
      WHEN substr(code_lieu_deces, 1, 2) IN ('97', '98') THEN substr(code_lieu_deces, 1, 3)
      ELSE substr(code_lieu_deces, 1, 2)
    END AS dept
  FROM read_csv('{src}', header=true, sep=',', quote='"',
                all_varchar=true, ignore_errors=true)
  WHERE regexp_matches(date_deces, '^[0-9]{{4}}')
),
enr AS (
  SELECT
    base.annee,
    COALESCE(dr.region, 'Autre / étranger') AS region,
    base.sx,
    CASE
      WHEN an_naiss IS NULL OR (annee - an_naiss) < 0 OR (annee - an_naiss) > 120 THEN 'Inconnu'
      WHEN (annee - an_naiss) < 20 THEN '0-19'
      WHEN (annee - an_naiss) < 40 THEN '20-39'
      WHEN (annee - an_naiss) < 60 THEN '40-59'
      WHEN (annee - an_naiss) < 75 THEN '60-74'
      WHEN (annee - an_naiss) < 85 THEN '75-84'
      ELSE '85+'
    END AS age
  FROM base LEFT JOIN dr ON dr.dept = base.dept
)
SELECT annee, region, sx, age, count(*) AS n
FROM enr
GROUP BY annee, region, sx, age;

-- f est déjà agrégée (~13 k lignes) : on émet une ligne JSON par fait, et
-- Python assemble + trie (déterministe, et évite la macro json_group_array
-- qui n'accepte pas ORDER BY).
SELECT json_array(annee, region, sx, age, n) FROM f;
"""


def main():
    res = subprocess.run(["duckdb", "-noheader", "-list"],
                         input=build_sql(), capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit("DuckDB a échoué :\n" + res.stderr)
    # DuckDB émet une ligne JSON [annee, region, sexe, age, n] par fait agrégé.
    facts = [json.loads(l) for l in res.stdout.splitlines() if l.startswith("[")]
    facts.sort(key=lambda r: (r[0], r[1], r[2], r[3]))   # ordre déterministe
    trend = {}
    for a, r, s, g, n in facts:
        trend[a] = trend.get(a, 0) + n
    data = {
        "trend":   [[a, trend[a]] for a in sorted(trend)],
        "regions": sorted({r for _, r, _, _, _ in facts}),
        "facts":   facts,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    y2019 = sum(n for a, r, s, g, n in data["facts"] if a == 2019)
    print(f"Années : {data['trend'][0][0]}–{data['trend'][-1][0]}")
    print(f"Décès 2019 : {y2019:,} · régions : {len(data['regions'])} "
          f"· facts : {len(data['facts'])} lignes")
    print(f"Écrit : {OUT}")


if __name__ == "__main__":
    main()
