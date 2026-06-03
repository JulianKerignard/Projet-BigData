#!/usr/bin/env python3
"""Dashboard Hospitalisation — style Power BI interactif (cross-filtering au clic).

Besoins : B3 (par période/année), B4 (par diagnostic CIM-10), B5 (par sexe et âge).

Table de faits unique [annee, cat, sexe, age, count] -> moteur de cross-filter
de dashboard_common. Agrégats uniquement (aucune donnée patient individuelle).
-> viz/hospitalisation_dashboard.html
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dashboard_common as dc

ROOT = Path(__file__).resolve().parents[2]
HOSP = ROOT / "DATA 2024/Hospitalisation/Hospitalisations.csv"
PATIENT = Path("/tmp/patient.csv")
OUT = ROOT / "viz/hospitalisation_dashboard.html"

CIM_CHAP = {
    "A": "Infectieuses & parasitaires", "B": "Infectieuses & parasitaires",
    "C": "Tumeurs", "D": "Tumeurs & sang", "E": "Endocrinien & métabolique",
    "F": "Troubles mentaux", "G": "Système nerveux", "H": "Œil & oreille",
    "I": "Système circulatoire", "J": "Système respiratoire", "K": "Système digestif",
    "L": "Peau", "M": "Ostéo-articulaire", "N": "Génito-urinaire",
    "O": "Grossesse & accouchement", "P": "Période périnatale",
    "Q": "Malformations congénitales", "R": "Symptômes & signes",
    "S": "Lésions traumatiques", "T": "Traumatismes & empoisonnements",
    "U": "Codes spéciaux", "V": "Causes externes", "W": "Causes externes",
    "X": "Causes externes", "Y": "Causes externes", "Z": "Recours aux soins",
}

AGE_ORDER = ["0-19", "20-39", "40-59", "60-74", "75-84", "85+"]


def age_group(a):
    try:
        a = int(a)
    except (TypeError, ValueError):
        return "Inconnu"
    if a < 0 or a > 120:
        return "Inconnu"
    for hi, lab in [(20, "0-19"), (40, "20-39"), (60, "40-59"), (75, "60-74"), (85, "75-84")]:
        if a < hi:
            return lab
    return "85+"


# ---- Dimension Patient : id -> (sexe, tranche d'âge) ----
patient = {}
with open(PATIENT, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        sx = "F" if row["Sexe"].lower() == "female" else ("H" if row["Sexe"].lower() == "male" else "?")
        patient[row["Id_patient"]] = (sx, age_group(row["Age"]))

# ---- Agrégation : (annee, cat, sexe, tranche) -> count ----
agg = {}
with open(HOSP, encoding="utf-8") as f:
    for row in csv.DictReader(f, delimiter=";"):
        d = row.get("Date_Entree", "")
        parts = d.split("/")
        if len(parts) != 3:
            continue
        annee = str(int(parts[2]))  # str pour cohérence des clés de dim
        cat = CIM_CHAP.get((row.get("Code_diagnostic") or "")[:1].upper(), "Autres")
        sx, tr = patient.get(row.get("Id_patient", ""), ("?", "Inconnu"))
        key = (annee, cat, sx, tr)
        agg[key] = agg.get(key, 0) + 1

# facts : liste de [annee(str), cat(str), sexe(str), age(str), count(int)]
facts = [[a, c, s, g, n] for (a, c, s, g), n in agg.items()]
years = sorted({r[0] for r in facts})

SPEC = {
    "facts": facts,
    "dims": {"annee": 0, "cat": 1, "sexe": 2, "age": 3},
    "dimLabels": {"annee": "Année", "cat": "Diagnostic", "sexe": "Sexe", "age": "Tranche d'âge"},
    "measureIndex": 4,
    "slicers": [
        {"dim": "annee", "label": "Année", "type": "select",
         "options": [[y, y] for y in years]},
        {"dim": "sexe", "label": "Sexe", "type": "tiles",
         "options": [["F", "Femmes"], ["H", "Hommes"]]},
    ],
    "kpis": [
        {"id": "k_total", "label": "Hospitalisations", "calc": "total", "color": "#118dff"},
        {"id": "k_cat",   "label": "1er motif (diagnostic)", "calc": "topDim", "dim": "cat",
         "noteSuffix": "des hospitalisations", "color": "#e8590c"},
        {"id": "k_age",   "label": "Tranche d'âge n°1", "calc": "topDim", "dim": "age",
         "noteSuffix": "des séjours", "color": "#13a10e"},
        {"id": "k_fem",   "label": "Part femmes", "calc": "pctFem", "note": "des séjours",
         "color": "#e64980"},
        {"id": "k_year",  "label": "Année de pointe", "calc": "topDim", "dim": "annee",
         "noteSuffix": "du volume", "color": "#7048e8"},
    ],
    "charts": [
        {"id": "c_year", "kind": "bar", "dim": "annee",
         "label": "Hospitalisations par année",
         "tag": "Taux global d'hospitalisation × période · cliquez une année pour filtrer",
         "bcode": "B3", "clickable": True,
         "order": years, "span": "col6"},
        {"id": "c_cat",  "kind": "barh", "dim": "cat",
         "label": "Par diagnostic (catégorie CIM-10)",
         "tag": "Part de chaque chapitre CIM-10 (taux) · §2.2",
         "bcode": "B4", "clickable": True, "sort": "desc",
         "span": "col3", "tall": True, "showPct": True},
        {"id": "c_age",  "kind": "bar",  "dim": "age",
         "label": "Par tranche d'âge",
         "tag": "Part des hospitalisations par groupe d'âge (taux)",
         "bcode": "B5", "clickable": True,
         "order": AGE_ORDER, "span": "col3", "tall": True, "showPct": True},
        {"id": "c_sex",  "kind": "pie",  "dim": "sexe",
         "label": "Répartition par sexe",
         "tag": "Patients hospitalisés",
         "bcode": "B5", "clickable": True, "span": "col3"},
    ],
    "narrative": "hospi",
}

NARRATIVE = r"""
hospi: function(){
  const r=rowsExcept(); const t=total(r);
  const cat=topOf('cat'), ag=topOf('age');
  const flt=Object.entries(state).filter(([d,v])=>v!==null)
    .map(([d,v])=>SPEC.dimLabels[d].toLowerCase()+' '+v).join(', ');
  const pc=v=>t?Math.round(100*v/t):0;
  return `<b>${fmt(t)}</b> hospitalisations`+(flt?` (${flt})`:' (toutes données)')
    +`. 1er motif : <b>${cat[0]}</b> (<b>${pc(cat[1])}%</b>) ; `
    +`tranche d'âge dominante : <b>${ag[0]}</b> (${pc(ag[1])}%).`;
}
"""

besoins = [
    {"code": "B3", "label": "Taux global d'hospitalisation × période", "status": "ok"},
    {"code": "B4", "label": "Par diagnostic (catégorie CIM-10)", "status": "ok"},
    {"code": "B5", "label": "Par sexe et tranche d'âge", "status": "ok"},
]

total_hospi = sum(r[4] for r in facts)

html = dc.page(
    title="Hospitalisation", sub="Tableau de bord décisionnel · interactif",
    src=f"{total_hospi:,} hospitalisations ({years[0]}–{years[-1]}) · agrégats RGPD".replace(",", " "),
    active="hospitalisation",
    besoins=besoins,
    slicers=SPEC["slicers"],
    kpis=SPEC["kpis"],
    charts=SPEC["charts"],
    spec_json=json.dumps(SPEC, ensure_ascii=False),
    narrative_js=NARRATIVE,
    foot="Cliquez n'importe quel graphique pour filtrer l'ensemble du rapport (cross-filtering). "
         "Prototype — sera reconstruit dans Power BI / Tableau sur Hive. "
         "Sexe et âge issus de la jointure Patient. Agrégats uniquement.",
)
OUT.write_text(html, encoding="utf-8")
print(
    f"Écrit : {OUT} ({len(html) // 1024} Ko) · "
    f"{len(facts)} lignes de faits · "
    f"{total_hospi:,} hospitalisations · "
    f"{len(years)} années"
)
