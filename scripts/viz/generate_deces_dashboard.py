#!/usr/bin/env python3
"""Dashboard Décès — besoin B7 (nombre de décès par région, focus 2019).

Lit viz/data_deces.json (agrégats produits par extract_deces.py sur les 1,9 Go).
-> viz/deces_dashboard.html
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dashboard_common as dc

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "viz/data_deces.json"
OUT = ROOT / "viz/deces_dashboard.html"

raw = json.loads(SRC.read_text(encoding="utf-8"))
# focus sur la fenêtre exploitable : on garde les années >= 2010 pour le slicer
years = sorted({a for a, _ in raw["trend"] if a >= 2000})
data = {
    "years": years,
    "default_year": 2019,                       # B7 cible l'année 2019
    "trend": [[a, n] for a, n in raw["trend"] if a >= 2000],
    "regions": raw["regions"],
    # facts: [annee, region, sexe, tranche, count]
    "facts": [r for r in raw["facts"] if r[0] >= 2000],
    "ages": ["0-19", "20-39", "40-59", "60-74", "75-84", "85+", "Inconnu"],
}

besoins = (
    '<div class="bes ok"><span class="dot"></span><b>B7</b> Nombre de décès par région — focus 2019</div>'
    '<div class="bes" style="border-style:dashed"><span class="dot" style="background:#9aa1ab"></span>'
    'Sexe / âge fournis en contexte (hors besoin imposé)</div>'
)
slicers = (
    '<div class="slicer"><div class="lab">Année</div>'
    '<select id="f_year">'
    + "".join(f'<option value="{y}"{" selected" if y == 2019 else ""}>{y}</option>' for y in years)
    + '</select></div>'
    '<div class="slicer" style="min-width:180px"><div class="lab">Sexe</div>'
    '<div class="seg" id="f_sex"><button data-v="all" class="on">Tous</button>'
    '<button data-v="F">Femmes</button><button data-v="H">Hommes</button></div></div>'
    '<button class="reset" id="reset">Réinitialiser (2019)</button>'
)
kpis = (
    '<div class="kpi" style="--c:#118dff"><div class="lab">Décès</div><div class="val" id="k_total">–</div><div class="note" id="k_total_n"></div></div>'
    '<div class="kpi" style="--c:#e8590c"><div class="lab">Région n°1</div><div class="val" id="k_reg" style="font-size:15px">–</div><div class="note" id="k_reg_n"></div></div>'
    '<div class="kpi" style="--c:#12b886"><div class="lab">Régions couvertes</div><div class="val" id="k_nreg">–</div><div class="note">métropole + DOM</div></div>'
    '<div class="kpi" style="--c:#7048e8"><div class="lab">Tranche d\'âge n°1</div><div class="val" id="k_age">–</div><div class="note" id="k_age_n"></div></div>'
    '<div class="kpi" style="--c:#e64980"><div class="lab">Part femmes</div><div class="val" id="k_fem">–</div><div class="note">des décès</div></div>'
)
panels = (
    '<div class="card full"><h3><span class="bcode">B7</span>Décès par région</h3><div class="tag">Nombre de décès par localisation (région) — année sélectionnée</div><div id="c_region" class="chart" style="height:330px"></div></div>'
    '<div class="card"><h3><span class="bcode">Contexte</span>Répartition par tranche d\'âge</h3><div class="tag">Décès par âge · filtré par sexe</div><div id="c_age" class="chart"></div></div>'
    '<div class="card"><h3><span class="bcode">Contexte</span>Répartition par sexe</h3><div class="tag">Décès par sexe</div><div id="c_sex" class="chart"></div></div>'
    '<div class="card full"><h3><span class="bcode">Tendance</span>Évolution annuelle des décès</h3><div class="tag">Volume total par année (toutes régions) · année sélectionnée mise en évidence</div><div id="c_trend" class="chart" style="height:200px"></div></div>'
)

RENDER = r"""
const state={year:String(DATA.default_year),sex:'all'};
const charts={};
['c_region','c_age','c_sex','c_trend'].forEach(id=>charts[id]=echarts.init(document.getElementById(id)));
window.addEventListener('resize',()=>Object.values(charts).forEach(c=>c.resize()));
function ff(excl=[]){return DATA.facts.filter(r=>
  (excl.includes('year')||r[0]==state.year)&&
  (excl.includes('sex') ||state.sex==='all'||r[2]===state.sex));}

function render(){
  const f=ff();
  const total=f.reduce((s,r)=>s+r[4],0);
  const pct=v=>total?Math.round(v/total*100):0;
  const regMap=sumBy(f,1,4);
  const topReg=Object.entries(regMap).sort((a,b)=>b[1]-a[1])[0]||['–',0];
  const ageMap=sumBy(f,3,4);
  const topAge=Object.entries(ageMap).filter(e=>e[0]!=='Inconnu').sort((a,b)=>b[1]-a[1])[0]||['–',0];
  const fem=f.filter(r=>r[2]==='F').reduce((s,r)=>s+r[4],0);

  document.getElementById('k_total').textContent=fmt(total);
  document.getElementById('k_total_n').textContent='année '+state.year;
  document.getElementById('k_reg').textContent=topReg[0];
  document.getElementById('k_reg_n').textContent=fmt(topReg[1])+' décès ('+pct(topReg[1])+'%)';
  document.getElementById('k_nreg').textContent=Object.keys(regMap).length;
  document.getElementById('k_age').textContent=topAge[0];
  document.getElementById('k_age_n').textContent=pct(topAge[1])+' % des décès';
  document.getElementById('k_fem').textContent=pct(fem)+' %';

  document.getElementById('insight').innerHTML=
    `<b>${fmt(total)}</b> décès en <b>${state.year}</b>${state.sex!=='all'?' ('+(state.sex==='F'?'femmes':'hommes')+')':''}. `
    +`Région la plus touchée : <b>${topReg[0]}</b> (${pct(topReg[1])}%) ; `
    +`classe d'âge dominante <b>${topAge[0]}</b>.`;

  // B7 régions (barres horizontales triées)
  const rm=Object.entries(regMap).sort((a,b)=>a[1]-b[1]);
  charts.c_region.setOption({grid:{...GRID,left:'3%'},tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
    xAxis:{type:'value',...AX,...SPL},
    yAxis:{type:'category',data:rm.map(d=>d[0]),...AX,axisLabel:{color:'#6b7280',width:160,overflow:'truncate'}},
    series:[{type:'bar',data:rm.map(d=>({value:d[1],itemStyle:{color:d[0]===topReg[0]?'#0b5cad':'#118dff',borderRadius:[0,3,3,0]}}))}]});

  // âge
  const ages=DATA.ages.filter(a=>a!=='Inconnu');
  charts.c_age.setOption({grid:GRID,tooltip:{trigger:'axis'},
    xAxis:{type:'category',data:ages,...AX},yAxis:{type:'value',...AX,...SPL},
    series:[{type:'bar',barWidth:'55%',data:ages.map(a=>ageMap[a]||0),itemStyle:{color:'#7048e8',borderRadius:[3,3,0,0]}}]});

  // sexe
  const xm=sumBy(ff(['sex']),2,4);
  charts.c_sex.setOption({tooltip:{trigger:'item',formatter:'{b}: {c} ({d}%)'},legend:{bottom:0,textStyle:{color:'#6b7280'}},
    series:[{type:'pie',radius:['48%','72%'],center:['50%','45%'],
      data:[{name:'Femmes',value:xm.F||0,itemStyle:{color:'#e64980'}},{name:'Hommes',value:xm.H||0,itemStyle:{color:'#118dff'}}],
      label:{color:'#4b5563'}}]});

  // tendance annuelle (toutes régions)
  const ty={};DATA.trend.forEach(([a,n])=>ty[a]=n);
  charts.c_trend.setOption({grid:{...GRID,top:'10%'},tooltip:{trigger:'axis'},
    xAxis:{type:'category',data:DATA.years,...AX},yAxis:{type:'value',...AX,...SPL},
    series:[{type:'bar',data:DATA.years.map(y=>({value:ty[y]||0,
      itemStyle:{color:(y==state.year)?'#0b5cad':'#a9c7e8',borderRadius:[2,2,0,0]}}))}]});
}
document.getElementById('f_year').addEventListener('change',e=>{state.year=e.target.value;render();});
document.querySelectorAll('#f_sex button').forEach(b=>b.addEventListener('click',()=>{
  document.querySelectorAll('#f_sex button').forEach(x=>x.classList.remove('on'));b.classList.add('on');state.sex=b.dataset.v;render();}));
document.getElementById('reset').addEventListener('click',()=>{state.year=String(DATA.default_year);state.sex='all';
  document.getElementById('f_year').value=String(DATA.default_year);
  document.querySelectorAll('#f_sex button').forEach(x=>x.classList.toggle('on',x.dataset.v==='all'));render();});
render();
"""

html = dc.page(
    title="Décès", sub="Tableau de bord décisionnel",
    src="Source : deces.csv (25 M lignes, INSEE) · agrégats", active="deces",
    besoins_html=besoins, slicers_html=slicers, kpis_html=kpis, panels_html=panels,
    data_json=json.dumps(data, ensure_ascii=False), render_js=RENDER,
    foot="Prototype de storytelling — sera reconstruit dans Power BI / Tableau branché sur Hive. "
         "Région dérivée du code lieu de décès (département → région 2016). Données agrégées uniquement.",
)
OUT.write_text(html, encoding="utf-8")
y2019 = sum(r[4] for r in data["facts"] if r[0] == 2019)
print(f"Écrit : {OUT} ({len(html)//1024} Ko) · décès 2019 = {y2019:,} · {len(data['regions'])} régions")
