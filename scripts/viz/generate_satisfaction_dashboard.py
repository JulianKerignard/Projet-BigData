#!/usr/bin/env python3
"""Dashboard Satisfaction — besoin B8 (taux global de satisfaction par région, 2020).

Source : DATA 2024/Satisfaction/2020/resultats-esatis48h-mco-open-data-2020.xlsx
(e-Satis 48h MCO). Score global ajusté 0-100 -> note /10, moyenné par région.
Aligné sur le profiling de P3 (Matthieu). -> viz/satisfaction_dashboard.html
"""
import json
import sys
from pathlib import Path
import openpyxl
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dashboard_common as dc

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "DATA 2024/Satisfaction/2020/resultats-esatis48h-mco-open-data-2020.xlsx"
OUT = ROOT / "viz/satisfaction_dashboard.html"

# sous-dimensions de satisfaction (libellé -> index colonne score)
SUBSCORES = {
    "Accueil": 12, "Prise en charge infirmiers": 14, "Prise en charge médecins": 16,
    "Chambre": 18, "Repas": 20, "Organisation sortie": 22,
}

wb = openpyxl.load_workbook(SRC, read_only=True, data_only=True)
ws = wb[wb.sheetnames[0]]
it = ws.iter_rows(values_only=True)
next(it)  # header

def num(x):
    if x is None:
        return None
    try:
        return float(str(x).replace(",", "."))
    except ValueError:
        return None

# agrégats par région : somme score global + n (établissements diffusés)
region_sum, region_n = {}, {}
sub_sum = {k: 0.0 for k in SUBSCORES}
sub_n = {k: 0 for k in SUBSCORES}
diffuses, total = 0, 0
for row in it:
    total += 1
    region = (row[4] or "").strip()
    sg = num(row[8])
    if region and sg is not None and 0 <= sg <= 100:
        diffuses += 1
        region_sum[region] = region_sum.get(region, 0.0) + sg
        region_n[region] = region_n.get(region, 0) + 1
        for k, idx in SUBSCORES.items():
            v = num(row[idx])
            if v is not None and 0 <= v <= 100:
                sub_sum[k] += v; sub_n[k] += 1

# moyenne par région, convertie en /10
regions = sorted(region_sum, key=lambda r: region_sum[r] / region_n[r], reverse=True)
data = {
    "annee": 2020,
    "regions": [[r, round(region_sum[r] / region_n[r] / 10, 2), region_n[r]] for r in regions],
    "subscores": [[k, round(sub_sum[k] / sub_n[k] / 10, 2)] for k in SUBSCORES if sub_n[k]],
    "national": round(sum(region_sum.values()) / sum(region_n.values()) / 10, 2),
    "diffuses": diffuses, "total": total,
}

besoins = (
    '<div class="bes ok"><span class="dot"></span><b>B8</b> Taux global de satisfaction par région — 2020</div>'
    '<div class="bes" style="border-style:dashed"><span class="dot" style="background:#9aa1ab"></span>'
    'Détail par dimension de satisfaction (contexte)</div>'
)
slicers = (
    '<div class="slicer" style="min-width:220px"><div class="lab">Campagne</div>'
    '<select id="f_year" disabled><option>2020 (e-Satis 48h MCO)</option></select></div>'
    '<div class="slicer" style="min-width:200px"><div class="lab">Trier les régions</div>'
    '<div class="seg" id="f_sort"><button data-v="desc" class="on">Meilleures</button>'
    '<button data-v="asc">À améliorer</button></div></div>'
)
kpis = (
    '<div class="kpi" style="--c:#118dff"><div class="lab">Satisfaction nationale</div><div class="val" id="k_nat">–</div><div class="note">moyenne /10</div></div>'
    '<div class="kpi" style="--c:#12b886"><div class="lab">Région n°1</div><div class="val" id="k_best" style="font-size:15px">–</div><div class="note" id="k_best_n"></div></div>'
    '<div class="kpi" style="--c:#e8590c"><div class="lab">Région à améliorer</div><div class="val" id="k_worst" style="font-size:15px">–</div><div class="note" id="k_worst_n"></div></div>'
    '<div class="kpi" style="--c:#7048e8"><div class="lab">Régions évaluées</div><div class="val" id="k_nreg">–</div><div class="note">campagne 2020</div></div>'
    '<div class="kpi" style="--c:#e64980"><div class="lab">Établissements diffusés</div><div class="val" id="k_diff">–</div><div class="note" id="k_diff_n"></div></div>'
)
panels = (
    '<div class="card full"><h3><span class="bcode">B8</span>Satisfaction par région (2020)</h3><div class="tag">Score global ajusté moyen, sur 10 · ligne = moyenne nationale</div><div id="c_region" class="chart" style="height:340px"></div></div>'
    '<div class="card"><h3><span class="bcode">Contexte</span>Satisfaction par dimension</h3><div class="tag">Score moyen national par axe de l\'expérience patient</div><div id="c_sub" class="chart" style="height:300px"></div></div>'
    '<div class="card"><h3><span class="bcode">Contexte</span>Établissements évalués par région</h3><div class="tag">Nombre d\'établissements diffusés (score publiable)</div><div id="c_nb" class="chart" style="height:300px"></div></div>'
)

RENDER = r"""
const state={sort:'desc'};
const charts={};
['c_region','c_sub','c_nb'].forEach(id=>charts[id]=echarts.init(document.getElementById(id)));
window.addEventListener('resize',()=>Object.values(charts).forEach(c=>c.resize()));

function render(){
  const regs=[...DATA.regions];  // [region, note/10, nb_etab] déjà triées desc
  const best=regs[0], worst=regs[regs.length-1];
  document.getElementById('k_nat').textContent=DATA.national.toFixed(2);
  document.getElementById('k_best').textContent=best[0];
  document.getElementById('k_best_n').textContent=best[1].toFixed(2)+' /10';
  document.getElementById('k_worst').textContent=worst[0];
  document.getElementById('k_worst_n').textContent=worst[1].toFixed(2)+' /10';
  document.getElementById('k_nreg').textContent=regs.length;
  document.getElementById('k_diff').textContent=fmt(DATA.diffuses);
  document.getElementById('k_diff_n').textContent='sur '+fmt(DATA.total)+' ('+Math.round(100*DATA.diffuses/DATA.total)+'%)';

  document.getElementById('insight').innerHTML=
    `Satisfaction nationale <b>${DATA.national.toFixed(2)}/10</b> en 2020 (${fmt(DATA.diffuses)} établissements diffusés). `
    +`Meilleure région : <b>${best[0]}</b> (${best[1].toFixed(2)}) ; à améliorer : <b>${worst[0]}</b> (${worst[1].toFixed(2)}).`;

  // B8 : régions triées + ligne nationale
  const asc=state.sort==='asc';
  const ordered=asc?[...regs].reverse():[...regs];
  const forBar=[...ordered].reverse();  // ECharts y-cat affiche de bas en haut
  charts.c_region.setOption({grid:{...GRID,left:'3%'},
    tooltip:{trigger:'axis',axisPointer:{type:'shadow'},valueFormatter:v=>v.toFixed(2)+' /10'},
    xAxis:{type:'value',max:10,...AX,...SPL},
    yAxis:{type:'category',data:forBar.map(d=>d[0]),...AX,axisLabel:{color:'#6b7280',width:170,overflow:'truncate'}},
    series:[{type:'bar',data:forBar.map(d=>({value:d[1],
        itemStyle:{color:d[0]===ordered[0][0]?'#0b5cad':'#118dff',borderRadius:[0,3,3,0]}})),
      markLine:{silent:true,symbol:'none',lineStyle:{color:'#e8590c',type:'dashed'},
        data:[{xAxis:DATA.national,label:{formatter:'Nat. '+DATA.national.toFixed(2),color:'#e8590c',position:'insideEndTop'}}]}}]});

  // dimensions
  const sub=[...DATA.subscores].sort((a,b)=>a[1]-b[1]);
  charts.c_sub.setOption({grid:{...GRID,left:'3%'},tooltip:{trigger:'axis',axisPointer:{type:'shadow'},valueFormatter:v=>v.toFixed(2)+' /10'},
    xAxis:{type:'value',max:10,...AX,...SPL},
    yAxis:{type:'category',data:sub.map(d=>d[0]),...AX,axisLabel:{color:'#6b7280',width:150,overflow:'truncate'}},
    series:[{type:'bar',data:sub.map(d=>d[1]),itemStyle:{color:'#7048e8',borderRadius:[0,3,3,0]}}]});

  // nb établissements par région
  const nb=[...regs].sort((a,b)=>a[2]-b[2]);
  charts.c_nb.setOption({grid:{...GRID,left:'3%'},tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
    xAxis:{type:'value',...AX,...SPL},
    yAxis:{type:'category',data:nb.map(d=>d[0]),...AX,axisLabel:{color:'#6b7280',width:150,overflow:'truncate',fontSize:10}},
    series:[{type:'bar',data:nb.map(d=>d[2]),itemStyle:{color:'#12b886',borderRadius:[0,3,3,0]}}]});
}
document.querySelectorAll('#f_sort button').forEach(b=>b.addEventListener('click',()=>{
  document.querySelectorAll('#f_sort button').forEach(x=>x.classList.remove('on'));b.classList.add('on');state.sort=b.dataset.v;render();}));
render();
"""

html = dc.page(
    title="Satisfaction", sub="Tableau de bord décisionnel",
    src="Source : e-Satis 48h MCO 2020 (open data) · agrégats", active="satisfaction",
    besoins_html=besoins, slicers_html=slicers, kpis_html=kpis, panels_html=panels,
    data_json=json.dumps(data, ensure_ascii=False), render_js=RENDER,
    foot="Prototype de storytelling — sera reconstruit dans Power BI / Tableau branché sur Hive. "
         "Score global ajusté converti sur 10. Établissements sous le seuil de diffusion exclus (cf. profiling P3).",
)
OUT.write_text(html, encoding="utf-8")
print(f"Écrit : {OUT} ({len(html)//1024} Ko) · national {data['national']}/10 · "
      f"{len(data['regions'])} régions · {data['diffuses']}/{data['total']} diffusés")
