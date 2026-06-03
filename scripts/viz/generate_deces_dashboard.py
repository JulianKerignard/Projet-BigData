#!/usr/bin/env python3
"""Dashboard Décès — style Power BI interactif (cross-filtering au clic).

Besoin imposé B7 : nombre de décès par région, focus 2019.
Visuels contextuels : tranche d'âge, sexe, évolution annuelle.

Table de faits unique [annee, region, sexe, age] -> moteur de cross-filter
de dashboard_common. Années >= 2000. Filtre initial : 2019 (B7).
-> viz/deces_dashboard.html
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dashboard_common as dc

ROOT = Path(__file__).resolve().parents[2]
SRC  = ROOT / "viz/data_deces.json"
OUT  = ROOT / "viz/deces_dashboard.html"

# ---- chargement des données (agrégats pré-calculés, JSON léger) ----
raw = json.loads(SRC.read_text(encoding="utf-8"))

# facts [annee:int, region:str, sexe:str, tranche_age:str, count:int]
# On garde uniquement >= 2000 ; année convertie en STRING (contrat moteur)
facts = [
    [str(r[0]), r[1], r[2], r[3], r[4]]
    for r in raw["facts"]
    if r[0] >= 2000
]

years = sorted({r[0] for r in facts})   # déjà des str après la conversion

AGE_ORDER = ["0-19", "20-39", "40-59", "60-74", "75-84", "85+", "Inconnu"]

SPEC = {
    "facts": facts,
    "dims": {"annee": 0, "region": 1, "sexe": 2, "age": 3},
    "dimLabels": {"annee": "Année", "region": "Région", "sexe": "Sexe", "age": "Tranche d'âge"},
    "measureIndex": 4,
    "initialState": {"annee": "2019"},
    "slicers": [
        {"dim": "annee", "label": "Année", "type": "select",
         "options": [[y, y] for y in years]},
        {"dim": "sexe", "label": "Sexe", "type": "tiles",
         "options": [["F", "Femmes"], ["H", "Hommes"]]},
    ],
    "kpis": [
        {"id": "k_total",  "label": "Décès",           "calc": "total",  "color": "#118dff"},
        {"id": "k_region", "label": "Région n°1",       "calc": "topDim", "dim": "region",
         "noteSuffix": "des décès", "color": "#e8590c"},
        {"id": "k_nreg",   "label": "Régions couvertes","calc": "nDim",   "dim": "region",
         "note": "métropole + DOM", "color": "#13a10e"},
        {"id": "k_age",    "label": "Tranche d'âge n°1","calc": "topDim", "dim": "age",
         "noteSuffix": "des décès", "color": "#7048e8"},
        {"id": "k_fem",    "label": "Part femmes",       "calc": "pctFem", "note": "des décès",
         "color": "#e64980"},
    ],
    "charts": [
        {"id": "c_map", "kind": "map", "dim": "region",
         "label": "Carte des décès par région",
         "tag": "Choroplèthe métropole — cliquez une région pour filtrer",
         "bcode": "B7", "clickable": True, "span": "col3", "tall": True},
        {"id": "c_region", "kind": "barh", "dim": "region",
         "label": "Décès par région (classement)",
         "tag": "Nombre de décès par région — DOM inclus · année sélectionnée",
         "bcode": "B7",
         "clickable": True, "sort": "desc", "span": "col3", "tall": True},
        {"id": "c_age", "kind": "bar", "dim": "age",
         "label": "Par tranche d'âge",
         "tag": "Répartition des décès par âge",
         "clickable": True, "order": AGE_ORDER, "color": "#7048e8", "span": "col2"},
        {"id": "c_sex", "kind": "pie", "dim": "sexe",
         "label": "Par sexe",
         "tag": "Répartition des décès par sexe",
         "clickable": True, "span": "col2"},
        {"id": "c_year", "kind": "line", "dim": "annee",
         "label": "Évolution annuelle",
         "tag": "Volume total de décès par année",
         "clickable": True, "order": years, "color": "#118dff", "span": "col2"},
    ],
    "narrative": "deces",
}

NARRATIVE = r"""
deces: function(){
  const r=rowsExcept(); const t=total(r);
  const reg=topOf('region'), age=topOf('age');
  const yr=state['annee'];
  const flt=Object.entries(state).filter(([d,v])=>v!==null)
    .map(([d,v])=>SPEC.dimLabels[d].toLowerCase()+' '+v).join(', ');
  const pc=v=>t?Math.round(100*v/t):0;
  return `<b>${fmt(t)}</b> décès`
    +(yr?` en <b>${yr}</b>`:'')
    +(flt && Object.values(state).filter(v=>v!==null).length>1
       ?' ('+Object.entries(state).filter(([d,v])=>v!==null && d!=='annee')
            .map(([d,v])=>SPEC.dimLabels[d].toLowerCase()+' '+v).join(', ')+')'
       :'')
    +`. Région la plus touchée : <b>${reg[0]}</b> (<b>${pc(reg[1])}%</b> des décès) ; `
    +`tranche d'âge dominante <b>${age[0]}</b> (${pc(age[1])}%).`;
}
"""

besoins = [
    {"code": "B7", "label": "Nombre de décès par région — focus 2019", "status": "ok"},
    {"code": "Ctx", "label": "Sexe / âge en contexte (hors besoin imposé)", "status": "ctx"},
]

GEOJSON = (ROOT / "scripts/viz/assets/fr_regions.geojson").read_text(encoding="utf-8")

html = dc.page(
    title="Décès",
    sub="Tableau de bord décisionnel · interactif",
    src="Source : deces.csv (25 M lignes, INSEE) · agrégats",
    active="deces",
    besoins=besoins,
    slicers=SPEC["slicers"],
    kpis=SPEC["kpis"],
    charts=SPEC["charts"],
    spec_json=json.dumps(SPEC, ensure_ascii=False),
    narrative_js=NARRATIVE,
    geojson=GEOJSON,
    foot="Cliquez n'importe quel graphique pour filtrer l'ensemble du rapport (cross-filtering). "
         "Région dérivée du code lieu de décès (département → région 2016). Carte = métropole. "
         "Prototype — sera reconstruit dans Power BI / Tableau sur Hive. Agrégats uniquement.",
)

OUT.write_text(html, encoding="utf-8")
y2019 = sum(r[4] for r in facts if r[0] == "2019")
print(f"Écrit : {OUT} ({len(html)//1024} Ko)")
print(f"Lignes de faits : {len(facts)} · Décès 2019 : {y2019:,} · Années : {len(years)}")
