#!/usr/bin/env python3
"""Dashboard Consultations — style Power BI interactif (cross-filtering au clic).

Besoins : B2 (par diagnostic), B6 (par professionnel/spécialité), période (année).
B1 (par établissement) : non applicable — source mono-établissement.

Table de faits unique [annee, specialite, sexe, categorie_CIM10] -> moteur de
cross-filter de dashboard_common. Agrégats uniquement (aucune donnée patient).
-> viz/consultations_dashboard.html
"""
import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dashboard_common as dc

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "viz/consultations_dashboard.html"
CONTAINER = "chu-pg"

CIM_CHAP = {
    "A": "Infectieuses", "B": "Infectieuses", "C": "Tumeurs", "D": "Tumeurs & sang",
    "E": "Endocrinien", "F": "Troubles mentaux", "G": "Système nerveux", "H": "Œil & oreille",
    "I": "Circulatoire", "J": "Respiratoire", "K": "Digestif", "L": "Peau",
    "M": "Ostéo-articulaire", "N": "Génito-urinaire", "O": "Grossesse", "P": "Périnatal",
    "Q": "Malformations", "R": "Symptômes", "S": "Lésions traumatiques",
    "T": "Traumatismes", "U": "Codes spéciaux", "V": "Causes externes", "W": "Causes externes",
    "X": "Causes externes", "Y": "Causes externes", "Z": "Recours aux soins",
}


def q(sql):
    res = subprocess.run(
        ["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "chu",
         "-t", "-A", "-F", "\t", "-c", sql],
        capture_output=True, text=True, check=True)
    return [l.split("\t") for l in res.stdout.strip().splitlines() if l]


# top 12 spécialités (le reste -> 'Autres'), pour garder la table de faits légère
top_spec = [r[0] for r in q("""
  SELECT sp."Specialite", COUNT(*) n FROM "Consultation" c
  JOIN "Professionnel_de_sante" pr ON pr."Identifiant"=c."Id_prof_sante"
  JOIN "Specialites" sp ON sp."Code_specialite"=pr."Code_specialite"
  GROUP BY 1 ORDER BY 2 DESC LIMIT 12;""")]
spec_in = ",".join("'" + s.replace("'", "''") + "'" for s in top_spec)

rows = q(f"""
  SELECT EXTRACT(YEAR FROM c."Date")::int AS annee,
         CASE WHEN sp."Specialite" IN ({spec_in}) THEN sp."Specialite" ELSE 'Autres' END AS spec,
         CASE WHEN LOWER(p2."Sexe")='male' THEN 'H' ELSE 'F' END AS sexe,
         UPPER(SUBSTRING(c."Code_diag" FROM 1 FOR 1)) AS cim,
         COUNT(*) AS n
  FROM "Consultation" c
  JOIN "Professionnel_de_sante" pr ON pr."Identifiant"=c."Id_prof_sante"
  JOIN "Specialites" sp ON sp."Code_specialite"=pr."Code_specialite"
  JOIN "Patient" p2 ON p2."Id_patient"=c."Id_patient"
  GROUP BY 1,2,3,4;""")

# facts [annee, spec, sexe, categorie, count]
facts = [[int(r[0]), r[1], r[2], CIM_CHAP.get(r[3], "Autres"), int(r[4])] for r in rows]
years = sorted({r[0] for r in facts})

SPEC = {
    "facts": facts,
    "dims": {"annee": 0, "spec": 1, "sexe": 2, "cat": 3},
    "dimLabels": {"annee": "Année", "spec": "Spécialité", "sexe": "Sexe", "cat": "Diagnostic"},
    "measureIndex": 4,
    "slicers": [
        {"dim": "annee", "label": "Année", "type": "select",
         "options": [[str(y), str(y)] for y in years]},
        {"dim": "sexe", "label": "Sexe", "type": "tiles",
         "options": [["F", "Femmes"], ["H", "Hommes"]]},
    ],
    "kpis": [
        {"id": "k_total", "label": "Consultations", "calc": "total", "color": "#118dff"},
        {"id": "k_spec", "label": "Spécialité n°1", "calc": "topDim", "dim": "spec",
         "noteSuffix": "des consultations", "color": "#13a10e"},
        {"id": "k_cat", "label": "1er motif (diagnostic)", "calc": "topDim", "dim": "cat",
         "noteSuffix": "des motifs", "color": "#e8590c"},
        {"id": "k_year", "label": "Année de pointe", "calc": "topDim", "dim": "annee",
         "noteSuffix": "du volume", "color": "#7048e8"},
        {"id": "k_fem", "label": "Part femmes", "calc": "pctFem", "note": "des consultations",
         "color": "#e64980"},
    ],
    "charts": [
        {"id": "c_year", "kind": "bar", "dim": "annee", "label": "Évolution par année",
         "tag": "Volume annuel · cliquez une année pour filtrer", "bcode": "Période",
         "clickable": True, "order": [str(y) for y in years], "span": "col6"},
        {"id": "c_spec", "kind": "barh", "dim": "spec", "label": "Par spécialité",
         "tag": "Taux de consultation par professionnel", "bcode": "B6",
         "clickable": True, "sort": "desc", "span": "col3", "tall": True},
        {"id": "c_cat", "kind": "barh", "dim": "cat", "label": "Par diagnostic (catégorie)",
         "tag": "Chapitres CIM-10 (généralisation §2.2)", "bcode": "B2",
         "clickable": True, "sort": "desc", "color": "#13a10e", "span": "col3", "tall": True},
        {"id": "c_sex", "kind": "pie", "dim": "sexe", "label": "Répartition par sexe",
         "tag": "Patients ayant consulté", "clickable": True, "span": "col2"},
    ],
    "narrative": "consult",
}

# années en chaîne pour cohérence des clés de dimension annee (le SQL renvoie int)
for f in SPEC["facts"]:
    f[0] = str(f[0])
SPEC["slicers"][0]["options"] = [[str(y), str(y)] for y in years]
SPEC["charts"][0]["order"] = [str(y) for y in years]

NARRATIVE = r"""
consult: function(){
  const r=rowsExcept(); const t=total(r);
  const sp=topOf('spec'), cat=topOf('cat');
  const flt=Object.entries(state).filter(([d,v])=>v!==null)
    .map(([d,v])=>SPEC.dimLabels[d].toLowerCase()+' '+v).join(', ');
  const pc=v=>t?Math.round(100*v/t):0;
  return `<b>${fmt(t)}</b> consultations`+(flt?` (${flt})`:' (toutes données)')
    +`. La <b>${sp[0]}</b> concentre <b>${pc(sp[1])}%</b> de l'activité ; `
    +`1er motif <b>${cat[0]}</b> (${pc(cat[1])}%).`;
}
"""

besoins = [
    {"code": "B1", "label": "Par établissement — N/A (mono-établissement)", "status": "ko"},
    {"code": "B2", "label": "Par diagnostic", "status": "ok"},
    {"code": "B6", "label": "Par professionnel", "status": "ok"},
]

html = dc.page(
    title="Consultations", sub="Tableau de bord décisionnel · interactif",
    src="1 027 157 consultations (2015–2023) · agrégats RGPD", active="consultations",
    besoins=besoins, slicers=SPEC["slicers"], kpis=SPEC["kpis"], charts=SPEC["charts"],
    spec_json=json.dumps(SPEC, ensure_ascii=False), narrative_js=NARRATIVE,
    foot="Cliquez n'importe quel graphique pour filtrer l'ensemble du rapport (cross-filtering). "
         "Prototype — sera reconstruit dans Power BI / Tableau sur Hive. Agrégats uniquement.",
)
OUT.write_text(html, encoding="utf-8")
print(f"Écrit : {OUT} ({len(html)//1024} Ko) · {len(facts)} lignes de faits · {len(years)} années")
