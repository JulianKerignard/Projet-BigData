#!/usr/bin/env python3
"""Extrait les agrégats Décès depuis deces.csv (1,9 Go, ~25 M lignes) en streaming.

Besoin B7 : nombre de décès par région (localisation) sur 2019.
Lecture par chunks pandas (4 colonnes utiles), dérivation département -> région,
âge au décès, puis agrégats compacts par (année, région, sexe, tranche d'âge).
Sortie : viz/data_deces.json (agrégats uniquement, aucune PII).
"""
import json
import pandas as pd
from pathlib import Path

SRC = Path("DATA 2024/DECES EN FRANCE/deces.csv")
OUT = Path("viz/data_deces.json")

# département (code INSEE) -> région (découpage 2016)
DEPT_REGION = {}
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
for region, depts in _R.items():
    for d in depts:
        DEPT_REGION[d] = region


def dept_of(code):
    if not isinstance(code, str) or len(code) < 2:
        return None
    if code[:2] in ("2A", "2B"):
        return code[:2]
    if code[:2] in ("97", "98"):
        return code[:3]
    return code[:2]


def age_group(a):
    if a is None or a < 0 or a > 120:
        return "Inconnu"
    for hi, lab in [(20, "0-19"), (40, "20-39"), (60, "40-59"),
                    (75, "60-74"), (85, "75-84")]:
        if a < hi:
            return lab
    return "85+"


trend = {}                # année -> nb décès
facts = {}                # (année, région, sexe, tranche) -> nb
cols = ["sexe", "date_naissance", "date_deces", "code_lieu_deces"]
rows = 0
for chunk in pd.read_csv(SRC, usecols=cols, dtype=str, chunksize=1_000_000,
                         na_filter=False, on_bad_lines="skip"):
    rows += len(chunk)
    yd = chunk["date_deces"].str.slice(0, 4)
    yn = chunk["date_naissance"].str.slice(0, 4)
    for sexe, yds, yns, lieu in zip(chunk["sexe"], yd, yn, chunk["code_lieu_deces"]):
        if not yds.isdigit():
            continue
        an = int(yds)
        trend[an] = trend.get(an, 0) + 1
        region = DEPT_REGION.get(dept_of(lieu), "Autre / étranger")
        age = (an - int(yns)) if yns.isdigit() else None
        sx = "H" if sexe == "1" else ("F" if sexe == "2" else "?")
        key = (an, region, sx, age_group(age))
        facts[key] = facts.get(key, 0) + 1

data = {
    "trend": sorted([[a, n] for a, n in trend.items()]),
    "regions": sorted({r for (_, r, _, _) in facts}),
    "facts": [[a, r, s, g, n] for (a, r, s, g), n in facts.items()],
}
OUT.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
print(f"Lignes lues : {rows:,}")
print(f"Années : {data['trend'][0][0]}–{data['trend'][-1][0]}")
y2019 = sum(n for a, r, s, g, n in data["facts"] if a == 2019)
print(f"Décès 2019 : {y2019:,} · régions : {len(data['regions'])} · facts : {len(data['facts'])} lignes")
print(f"Écrit : {OUT}")
