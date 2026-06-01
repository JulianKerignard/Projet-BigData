#!/usr/bin/env python3
"""Génère le dashboard HTML interactif des consultations (style Power BI / Tableau).

Extrait des agrégats multi-dimensionnels (année × mois × spécialité × sexe) depuis
PostgreSQL (conteneur `chu-pg`) pour permettre un cross-filtering réel côté client,
puis écrit un dashboard HTML autonome (ECharts, thème clair BI) :
slicers (Année / Spécialité / Sexe) + KPI cards + graphiques liés.

Aucune donnée patient individuelle n'est exportée — uniquement des agrégats.
"""
import json
import subprocess
from pathlib import Path

CONTAINER = "chu-pg"
OUT = Path(__file__).resolve().parents[2] / "viz" / "consultations_dashboard.html"


def q(sql: str):
    res = subprocess.run(
        ["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "chu",
         "-t", "-A", "-F", "\t", "-c", sql],
        capture_output=True, text=True, check=True,
    )
    return [line.split("\t") for line in res.stdout.strip().splitlines() if line]


def esc(s):  # échappe les apostrophes pour les clauses IN
    return s.replace("'", "''")


# --- top spécialités / diagnostics (pour regrouper le reste en 'Autres') ---
TOP_SPEC = [r[0] for r in q("""SELECT sp."Specialite", COUNT(*) n FROM "Consultation" c
  JOIN "Professionnel_de_sante" p ON p."Identifiant"=c."Id_prof_sante"
  JOIN "Specialites" sp ON sp."Code_specialite"=p."Code_specialite"
  GROUP BY 1 ORDER BY 2 DESC LIMIT 12;""")]

spec_in = ",".join(f"'{esc(s)}'" for s in TOP_SPEC)
spec_case = f'CASE WHEN sp."Specialite" IN ({spec_in}) THEN sp."Specialite" ELSE \'Autres\' END'
sex_case = 'CASE WHEN lower(pa."Sexe")=\'male\' THEN \'M\' ELSE \'F\' END'

# Diagnostics généralisés par chapitre CIM-10 (1re lettre du code) — cf. §2.2
# Évite le "top diagnostics" inexploitable (15 487 codes ~uniformes -> 99,8% en Autres)
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

# --- fait principal : (annee, mois, specialite_grp, sexe) -> count, sum_duree ---
fact_main = q(f"""
SELECT EXTRACT(YEAR FROM c."Date")::int, EXTRACT(MONTH FROM c."Date")::int,
       {spec_case}, {sex_case}, COUNT(*),
       ROUND(SUM(EXTRACT(EPOCH FROM (c."Heure_fin"-c."Heure_debut"))/60)
             FILTER (WHERE c."Heure_fin">=c."Heure_debut")::numeric,0)
FROM "Consultation" c
JOIN "Professionnel_de_sante" p ON p."Identifiant"=c."Id_prof_sante"
JOIN "Specialites" sp ON sp."Code_specialite"=p."Code_specialite"
JOIN "Patient" pa ON pa."Id_patient"=c."Id_patient"
GROUP BY 1,2,3,4;""")

# --- fait diagnostic : (annee, specialite_grp, sexe, chapitre_CIM10) -> count ---
fact_diag_raw = q(f"""
SELECT EXTRACT(YEAR FROM c."Date")::int, {spec_case}, {sex_case},
       upper(substring(c."Code_diag" from 1 for 1)), COUNT(*)
FROM "Consultation" c
JOIN "Professionnel_de_sante" p ON p."Identifiant"=c."Id_prof_sante"
JOIN "Specialites" sp ON sp."Code_specialite"=p."Code_specialite"
JOIN "Patient" pa ON pa."Id_patient"=c."Id_patient"
GROUP BY 1,2,3,4;""")

# remappe la lettre de chapitre -> libellé (plusieurs lettres -> même catégorie)
diag_agg = {}
for r in fact_diag_raw:
    chap = CIM_CHAP.get(r[3], "Autres")
    key = (int(r[0]), r[1], r[2], chap)
    diag_agg[key] = diag_agg.get(key, 0) + int(r[4])

years = sorted({int(r[0]) for r in fact_main})
specs = TOP_SPEC + ["Autres"]

data = {
    "years": years,
    "specs": specs,
    # factMain: [year, month, spec, sex, count, sumDuree]
    "main": [[int(r[0]), int(r[1]), r[2], r[3], int(r[4]), int(r[5] or 0)] for r in fact_main],
    # factDiag: [year, spec, sex, categorie_CIM10, count]
    "diag": [[y, s, x, c, n] for (y, s, x, c), n in diag_agg.items()],
}

HTML = r"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CHU · Consultations</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#eef0f4;color:#252b36;font-family:'Segoe UI',system-ui,Arial,sans-serif;font-size:13px}
.app{max-width:1320px;margin:0 auto;padding:18px 20px}
.topbar{display:flex;align-items:baseline;gap:12px;border-bottom:2px solid #118dff;padding-bottom:10px;margin-bottom:14px}
.topbar h1{font-size:18px;font-weight:600;color:#1b1f27}
.topbar .sub{color:#6b7280;font-size:12px}
.topbar .src{margin-left:auto;color:#9aa1ab;font-size:11px}
.slicers{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.slicer{background:#fff;border:1px solid #d9dde3;border-radius:4px;padding:7px 10px;min-width:150px}
.slicer .lab{font-size:10.5px;text-transform:uppercase;letter-spacing:.5px;color:#8a909a;font-weight:600;margin-bottom:4px}
.slicer select{width:100%;border:none;font-size:13px;color:#252b36;background:transparent;outline:none;cursor:pointer}
.seg{display:flex;gap:4px}
.seg button{flex:1;border:1px solid #d9dde3;background:#fff;color:#4b5563;border-radius:3px;padding:5px 0;
font-size:12px;cursor:pointer;transition:all .12s}
.seg button.on{background:#118dff;border-color:#118dff;color:#fff;font-weight:600}
.reset{margin-left:auto;align-self:center;border:1px solid #d9dde3;background:#fff;color:#6b7280;
border-radius:4px;padding:8px 14px;font-size:12px;cursor:pointer}
.reset:hover{background:#f3f4f6}
.insight{background:#fff;border:1px solid #e2e5ea;border-left:4px solid #118dff;border-radius:5px;
padding:11px 16px;margin-bottom:14px;font-size:13.5px;color:#374151;line-height:1.5}
.insight b{color:#1b1f27}
.besoins{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.bes{background:#fff;border:1px solid #e2e5ea;border-radius:5px;padding:8px 12px;font-size:12px;display:flex;align-items:center;gap:8px;color:#4b5563}
.bes .dot{width:9px;height:9px;border-radius:50%;flex:none}
.bes b{color:#1b1f27}
.bes.ok .dot{background:#12b886}.bes.ko .dot{background:#e8590c}
.bcode{font-weight:700;color:#118dff;margin-right:4px}
.blocked{display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;height:285px;gap:12px}
.blocked .mark{width:42px;height:42px;border-radius:50%;border:2px solid #f1a661;color:#e8590c;
display:grid;place-items:center;font-size:22px;font-weight:700}
.blocked .t{font-size:12.5px;color:#6b7280;max-width:300px;line-height:1.55}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:14px}
.kpi{background:#fff;border:1px solid #e2e5ea;border-top:3px solid var(--c,#118dff);border-radius:5px;padding:13px 15px}
.kpi .lab{color:#8a909a;font-size:11px;text-transform:uppercase;letter-spacing:.4px;font-weight:600}
.kpi .val{font-size:24px;font-weight:700;margin-top:6px;color:#1b1f27}
.kpi .note{font-size:11px;color:#9aa1ab;margin-top:3px}
.grid{display:grid;grid-template-columns:1.5fr 1fr;gap:12px}
.card{background:#fff;border:1px solid #e2e5ea;border-radius:5px;padding:12px 14px}
.card h3{font-size:13px;font-weight:600;color:#374151}
.card .tag{color:#9aa1ab;font-size:11px;margin:2px 0 6px}
.chart{width:100%;height:285px}
.full{grid-column:1 / -1}
.foot{color:#9aa1ab;font-size:11px;margin-top:14px;text-align:center;line-height:1.6}
@media(max-width:1000px){.kpis{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}}
</style></head><body>
<div class="app">
<div class="topbar"><h1>Cloud Healthcare Unit — Consultations</h1>
  <span class="sub">Tableau de bord décisionnel</span>
  <span class="src">Source : 1 027 157 consultations (2015–2023) · agrégats RGPD</span></div>

<div class="besoins">
  <div class="bes ko"><span class="dot"></span><b>B1</b> Par établissement × période — <span style="color:#9aa1ab">consultations mono-établissement → porté par Hospi / Satisfaction</span></div>
  <div class="bes ok"><span class="dot"></span><b>B2</b> Par diagnostic × période</div>
  <div class="bes ok"><span class="dot"></span><b>B6</b> Par professionnel (spécialité)</div>
</div>

<div class="slicers">
  <div class="slicer"><div class="lab">Année</div>
    <select id="f_year"><option value="all">Toutes</option>__YEAR_OPTS__</select></div>
  <div class="slicer"><div class="lab">Spécialité</div>
    <select id="f_spec"><option value="all">Toutes</option>__SPEC_OPTS__</select></div>
  <div class="slicer" style="min-width:180px"><div class="lab">Sexe</div>
    <div class="seg" id="f_sex">
      <button data-v="all" class="on">Tous</button>
      <button data-v="F">Femmes</button>
      <button data-v="M">Hommes</button></div></div>
  <button class="reset" id="reset">Réinitialiser</button>
</div>

<div class="insight" id="insight">—</div>

<div class="kpis">
  <div class="kpi" style="--c:#118dff"><div class="lab">Consultations</div><div class="val" id="k_total">–</div><div class="note" id="k_total_n"></div></div>
  <div class="kpi" style="--c:#12b886"><div class="lab">Spécialité n°1</div><div class="val" id="k_spec" style="font-size:15px">–</div><div class="note" id="k_spec_n"></div></div>
  <div class="kpi" style="--c:#e8590c"><div class="lab">1er motif (catégorie)</div><div class="val" id="k_cat" style="font-size:15px">–</div><div class="note" id="k_cat_n"></div></div>
  <div class="kpi" style="--c:#7048e8"><div class="lab">Mois de pointe</div><div class="val" id="k_peak">–</div><div class="note" id="k_peak_n"></div></div>
  <div class="kpi" style="--c:#e64980"><div class="lab">Consultations / mois</div><div class="val" id="k_pm">–</div><div class="note">moyenne sur la sélection</div></div>
</div>

<div class="grid">
  <div class="card full"><h3><span class="bcode">Période</span>Évolution annuelle des consultations</h3><div class="tag">L'année sélectionnée est mise en évidence · filtré par spécialité / sexe</div><div id="c_trend" class="chart" style="height:230px"></div></div>
  <div class="card"><h3><span class="bcode">B6</span>Consultations par spécialité</h3><div class="tag">Taux de consultation par professionnel (agrégé par spécialité)</div><div id="c_spec" class="chart"></div></div>
  <div class="card"><h3><span class="bcode">B2</span>Diagnostics par catégorie</h3><div class="tag">Taux de consultation par diagnostic · chapitres CIM-10 (généralisation §2.2)</div><div id="c_diag" class="chart"></div></div>
  <div class="card"><h3><span class="bcode">B1</span>Consultations par établissement</h3><div class="tag">Taux de consultation par établissement × période</div>
    <div class="blocked"><div class="mark">i</div><div class="t"><b>Non applicable</b> — source mono-établissement.<br>L'axe établissement est porté par les faits <b>Hospitalisation</b> et <b>Satisfaction</b>.</div></div></div>
  <div class="card"><h3><span class="bcode">Période</span>Saisonnalité mensuelle</h3><div class="tag">Répartition des consultations par mois</div><div id="c_month" class="chart"></div></div>
  <div class="card"><h3>Répartition par sexe</h3><div class="tag">Contexte démographique · patients ayant consulté</div><div id="c_sex" class="chart"></div></div>
</div>
<div class="foot">Prototype de storytelling — sera reconstruit dans Power BI / Tableau branché sur Hive.
Données agrégées uniquement, conforme à Securite_Anonymisation_NFR.md.
La durée des consultations n'est pas exploitée (valeurs non réalistes dans le jeu source : médiane 240 min).</div>
</div>
<script>
const DATA = __DATA__;
const PAL=['#118dff','#12b886','#e8590c','#7048e8','#e64980','#15aabf','#fab005','#4263eb','#2f9e44','#d6336c','#1098ad','#5c940d','#868e96'];
const MONTHS=['Jan','Fév','Mar','Avr','Mai','Juin','Juil','Aoû','Sep','Oct','Nov','Déc'];
const AX={axisLine:{lineStyle:{color:'#ccd1d9'}},axisLabel:{color:'#6b7280'},axisTick:{show:false}};
const SPL={splitLine:{lineStyle:{color:'#eef0f4'}}};
const GRID={left:'3%',right:'4%',bottom:'3%',top:'14%',containLabel:true};
const state={year:'all',spec:'all',sex:'all'};
const charts={};
['c_trend','c_spec','c_diag','c_month','c_sex'].forEach(id=>charts[id]=echarts.init(document.getElementById(id)));
window.addEventListener('resize',()=>Object.values(charts).forEach(c=>c.resize()));
const fmt=n=>Math.round(n).toLocaleString('fr-FR');

// filtre factMain en excluant éventuellement certaines dimensions (cross-filter façon BI)
function fm(exclude=[]){return DATA.main.filter(r=>
  (exclude.includes('year')||state.year==='all'||r[0]==state.year)&&
  (exclude.includes('spec')||state.spec==='all'||r[2]===state.spec)&&
  (exclude.includes('sex') ||state.sex==='all' ||r[3]===state.sex));}
function fd(exclude=[]){return DATA.diag.filter(r=>
  (exclude.includes('year')||state.year==='all'||r[0]==state.year)&&
  (exclude.includes('spec')||state.spec==='all'||r[1]===state.spec)&&
  (exclude.includes('sex') ||state.sex==='all' ||r[2]===state.sex));}
function sumBy(rows,keyIdx,valIdx){const m={};rows.forEach(r=>m[r[keyIdx]]=(m[r[keyIdx]]||0)+r[valIdx]);return m;}

function render(){
  // ---- KPI (filtre complet) ----
  const f=fm();
  const total=f.reduce((s,r)=>s+r[4],0);
  const pct=v=>total?Math.round(v/total*100):0;
  // spécialité n°1
  const specMap=sumBy(f,2,4);
  const topSpec=Object.entries(specMap).sort((a,b)=>b[1]-a[1])[0]||['–',0];
  // 1er motif (catégorie diagnostic)
  const catMap=sumBy(fd(),3,4); const catTot=Object.values(catMap).reduce((s,v)=>s+v,0)||1;
  const topCat=Object.entries(catMap).sort((a,b)=>b[1]-a[1])[0]||['–',0];
  // mois de pointe
  const monMap=sumBy(f,1,4);
  const peak=Object.entries(monMap).sort((a,b)=>b[1]-a[1])[0]||[null,0];
  const activeMonths=Object.keys(monMap).length||1;

  document.getElementById('k_total').textContent=fmt(total);
  document.getElementById('k_total_n').textContent=state.year==='all'?'toutes années':('année '+state.year);
  document.getElementById('k_spec').textContent=topSpec[0];
  document.getElementById('k_spec_n').textContent=pct(topSpec[1])+' % des consultations';
  document.getElementById('k_cat').textContent=topCat[0];
  document.getElementById('k_cat_n').textContent=Math.round(topCat[1]/catTot*100)+' % des motifs';
  document.getElementById('k_peak').textContent=peak[0]?MONTHS[peak[0]-1]:'–';
  document.getElementById('k_peak_n').textContent=fmt(peak[1])+' consult.';
  document.getElementById('k_pm').textContent=fmt(total/activeMonths);

  // ---- bandeau narratif (storytelling) ----
  const scope=state.year==='all'?'sur 2015–2023':('en '+state.year);
  const flt=[state.spec!=='all'?('spécialité '+state.spec):null,
             state.sex!=='all'?(state.sex==='F'?'femmes':'hommes'):null]
            .filter(Boolean).join(', ');
  document.getElementById('insight').innerHTML=
    `<b>${fmt(total)}</b> consultations ${scope}${flt?(' ('+flt+')'):''}. `+
    `La <b>${topSpec[0]}</b> concentre <b>${pct(topSpec[1])}%</b> de l'activité ; `+
    `le 1er motif est <b>${topCat[0]}</b> (${Math.round(topCat[1]/catTot*100)}%) ; `+
    `pic d'activité en <b>${peak[0]?MONTHS[peak[0]-1]:'–'}</b>.`;

  // ---- tendance annuelle (filtré spec+sex, année surlignée) ----
  const ty=sumBy(fm(['year']),0,4);
  charts.c_trend.setOption({grid:{...GRID,top:'10%'},tooltip:{trigger:'axis'},
    xAxis:{type:'category',data:DATA.years,...AX},yAxis:{type:'value',...AX,...SPL},
    series:[{type:'bar',barWidth:'55%',data:DATA.years.map(y=>({value:ty[y]||0,
      itemStyle:{color:(state.year!=='all'&&y==state.year)?'#0b5cad':'#118dff',borderRadius:[3,3,0,0]}}))}]});

  // ---- par spécialité (filtré année+sexe ; barres horizontales) ----
  const sm=Object.entries(sumBy(fm(['spec']),2,4)).sort((a,b)=>a[1]-b[1]);
  charts.c_spec.setOption({grid:{...GRID,left:'3%'},tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
    xAxis:{type:'value',...AX,...SPL},
    yAxis:{type:'category',data:sm.map(d=>d[0]),...AX,axisLabel:{color:'#6b7280',width:115,overflow:'truncate'}},
    series:[{type:'bar',data:sm.map(d=>({value:d[1],
      itemStyle:{color:(state.spec!=='all'&&d[0]===state.spec)?'#0b5cad':'#118dff',borderRadius:[0,3,3,0]}}))}]});

  // ---- top diagnostics (filtré année+spec+sexe) ----
  const dm=Object.entries(sumBy(fd(),3,4)).sort((a,b)=>b[1]-a[1]).slice(0,12).reverse();
  charts.c_diag.setOption({grid:{...GRID,left:'3%'},tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
    xAxis:{type:'value',...AX,...SPL},
    yAxis:{type:'category',data:dm.map(d=>d[0]),...AX,axisLabel:{color:'#6b7280',width:130,overflow:'truncate',fontSize:10}},
    series:[{type:'bar',data:dm.map(d=>d[1]),itemStyle:{color:'#12b886',borderRadius:[0,3,3,0]}}]});

  // ---- saisonnalité (filtré complet) ----
  const mm=sumBy(f,1,4);
  charts.c_month.setOption({grid:GRID,tooltip:{trigger:'axis'},
    xAxis:{type:'category',data:MONTHS,...AX},yAxis:{type:'value',...AX,...SPL},
    series:[{type:'line',smooth:true,symbol:'circle',symbolSize:6,data:MONTHS.map((_,i)=>mm[i+1]||0),
      lineStyle:{width:2.5,color:'#7048e8'},itemStyle:{color:'#7048e8'},
      areaStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:'#7048e833'},{offset:1,color:'#7048e800'}])}}]});

  // ---- sexe (filtré année+spec) ----
  const xm=sumBy(fm(['sex']),3,4);
  charts.c_sex.setOption({tooltip:{trigger:'item',formatter:'{b}: {c} ({d}%)'},
    legend:{bottom:0,textStyle:{color:'#6b7280'}},
    series:[{type:'pie',radius:['48%','72%'],center:['50%','45%'],
      data:[{name:'Femmes',value:xm.F||0,itemStyle:{color:'#e64980'}},
            {name:'Hommes',value:xm.M||0,itemStyle:{color:'#118dff'}}],
      label:{color:'#4b5563',fontSize:12}}]});
}

document.getElementById('f_year').addEventListener('change',e=>{state.year=e.target.value;render();});
document.getElementById('f_spec').addEventListener('change',e=>{state.spec=e.target.value;render();});
document.querySelectorAll('#f_sex button').forEach(b=>b.addEventListener('click',()=>{
  document.querySelectorAll('#f_sex button').forEach(x=>x.classList.remove('on'));
  b.classList.add('on');state.sex=b.dataset.v;render();}));
document.getElementById('reset').addEventListener('click',()=>{
  state.year='all';state.spec='all';state.sex='all';
  document.getElementById('f_year').value='all';document.getElementById('f_spec').value='all';
  document.querySelectorAll('#f_sex button').forEach(x=>x.classList.toggle('on',x.dataset.v==='all'));
  render();});
render();
</script></body></html>"""

year_opts = "".join(f'<option value="{y}">{y}</option>' for y in years)
spec_opts = "".join(f'<option value="{s}">{s}</option>' for s in specs)
html = (HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__YEAR_OPTS__", year_opts)
            .replace("__SPEC_OPTS__", spec_opts))
OUT.write_text(html, encoding="utf-8")
print(f"Dashboard écrit : {OUT}  ({len(html)//1024} Ko)")
print(f"factMain: {len(data['main'])} lignes · factDiag: {len(data['diag'])} lignes")
