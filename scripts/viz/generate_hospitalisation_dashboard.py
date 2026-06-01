#!/usr/bin/env python3
"""Dashboard Hospitalisation — besoins B3 (période), B4 (diagnostic), B5 (sexe/âge).

Source : DATA 2024/Hospitalisation/Hospitalisations.csv (jointure Patient pour sexe/âge).
Agrégats uniquement -> viz/hospitalisation_dashboard.html
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


# dimension Patient : id -> (sexe, tranche)
patient = {}
with open(PATIENT, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        sx = "F" if row["Sexe"].lower() == "female" else ("H" if row["Sexe"].lower() == "male" else "?")
        patient[row["Id_patient"]] = (sx, age_group(row["Age"]))

trend = {}                       # année -> nb hospitalisations
facts = {}                       # (année, categorie, sexe, tranche) -> nb
duree = {}                       # année -> [somme jours, n]
with open(HOSP, encoding="utf-8") as f:
    for row in csv.DictReader(f, delimiter=";"):
        d = row.get("Date_Entree", "")
        parts = d.split("/")
        if len(parts) != 3:
            continue
        annee = int(parts[2])
        trend[annee] = trend.get(annee, 0) + 1
        cat = CIM_CHAP.get((row.get("Code_diagnostic") or "")[:1].upper(), "Autres")
        sx, tr = patient.get(row.get("Id_patient", ""), ("?", "Inconnu"))
        key = (annee, cat, sx, tr)
        facts[key] = facts.get(key, 0) + 1
        try:
            j = int(row.get("Jour_Hospitalisation", "") or 0)
            s = duree.get(annee, [0, 0]); s[0] += j; s[1] += 1; duree[annee] = s
        except ValueError:
            pass

years = sorted(trend)
data = {
    "years": years,
    "trend": [[a, trend[a]] for a in years],
    # facts: [annee, categorie, sexe, tranche, count]
    "facts": [[a, c, s, g, n] for (a, c, s, g), n in facts.items()],
    "duree": {str(a): round(duree[a][0] / duree[a][1], 1) if duree.get(a, [0, 0])[1] else 0 for a in years},
    "ages": ["0-19", "20-39", "40-59", "60-74", "75-84", "85+", "Inconnu"],
}

besoins = (
    '<div class="bes ok"><span class="dot"></span><b>B3</b> Taux global d\'hospitalisation × période</div>'
    '<div class="bes ok"><span class="dot"></span><b>B4</b> Par diagnostic × période</div>'
    '<div class="bes ok"><span class="dot"></span><b>B5</b> Par sexe / âge</div>'
)
slicers = (
    '<div class="slicer"><div class="lab">Année</div>'
    '<select id="f_year"><option value="all">Toutes</option>'
    + "".join(f'<option value="{y}">{y}</option>' for y in years) + '</select></div>'
    '<div class="slicer" style="min-width:180px"><div class="lab">Sexe</div>'
    '<div class="seg" id="f_sex"><button data-v="all" class="on">Tous</button>'
    '<button data-v="F">Femmes</button><button data-v="H">Hommes</button></div></div>'
    '<button class="reset" id="reset">Réinitialiser</button>'
)
kpis = (
    '<div class="kpi" style="--c:#118dff"><div class="lab">Hospitalisations</div><div class="val" id="k_total">–</div><div class="note" id="k_total_n"></div></div>'
    '<div class="kpi" style="--c:#12b886"><div class="lab">Durée moy. séjour</div><div class="val" id="k_dur">–</div><div class="note">jours</div></div>'
    '<div class="kpi" style="--c:#e8590c"><div class="lab">1er motif (catégorie)</div><div class="val" id="k_cat" style="font-size:15px">–</div><div class="note" id="k_cat_n"></div></div>'
    '<div class="kpi" style="--c:#7048e8"><div class="lab">Tranche d\'âge n°1</div><div class="val" id="k_age">–</div><div class="note" id="k_age_n"></div></div>'
    '<div class="kpi" style="--c:#e64980"><div class="lab">Part femmes</div><div class="val" id="k_fem">–</div><div class="note">des séjours</div></div>'
)
panels = (
    '<div class="card full"><h3><span class="bcode">B3</span>Hospitalisations par année</h3><div class="tag">Taux global d\'hospitalisation × période · année sélectionnée mise en évidence</div><div id="c_trend" class="chart" style="height:230px"></div></div>'
    '<div class="card"><h3><span class="bcode">B4</span>Diagnostics par catégorie</h3><div class="tag">Par diagnostic · chapitres CIM-10 (généralisation §2.2)</div><div id="c_diag" class="chart"></div></div>'
    '<div class="card"><h3><span class="bcode">B5</span>Répartition par tranche d\'âge</h3><div class="tag">Hospitalisations par âge · filtré par sexe</div><div id="c_age" class="chart"></div></div>'
    '<div class="card"><h3><span class="bcode">B5</span>Répartition par sexe</h3><div class="tag">Hospitalisations par sexe</div><div id="c_sex" class="chart"></div></div>'
    '<div class="card"><h3><span class="bcode">B3</span>Durée moyenne de séjour</h3><div class="tag">Jours d\'hospitalisation moyens par année</div><div id="c_dur" class="chart"></div></div>'
)

RENDER = r"""
const state={year:'all',sex:'all'};
const charts={};
['c_trend','c_diag','c_age','c_sex','c_dur'].forEach(id=>charts[id]=echarts.init(document.getElementById(id)));
window.addEventListener('resize',()=>Object.values(charts).forEach(c=>c.resize()));
function ff(excl=[]){return DATA.facts.filter(r=>
  (excl.includes('year')||state.year==='all'||r[0]==state.year)&&
  (excl.includes('sex') ||state.sex==='all' ||r[2]===state.sex));}

function render(){
  const f=ff();
  const total=f.reduce((s,r)=>s+r[4],0);
  const pct=v=>total?Math.round(v/total*100):0;
  const catMap=sumBy(f,1,4); const topCat=Object.entries(catMap).sort((a,b)=>b[1]-a[1])[0]||['–',0];
  const ageMap=sumBy(f,3,4); const topAge=Object.entries(ageMap).filter(e=>e[0]!=='Inconnu').sort((a,b)=>b[1]-a[1])[0]||['–',0];
  const fem=f.filter(r=>r[2]==='F').reduce((s,r)=>s+r[4],0);
  const dur=state.year==='all'
    ? (()=>{const v=Object.values(DATA.duree);return v.length?(v.reduce((a,b)=>a+b,0)/v.length):0;})()
    : (DATA.duree[state.year]||0);

  document.getElementById('k_total').textContent=fmt(total);
  document.getElementById('k_total_n').textContent=state.year==='all'?'toutes années':('année '+state.year);
  document.getElementById('k_dur').textContent=dur.toFixed(1);
  document.getElementById('k_cat').textContent=topCat[0];
  document.getElementById('k_cat_n').textContent=pct(topCat[1])+' % des séjours';
  document.getElementById('k_age').textContent=topAge[0];
  document.getElementById('k_age_n').textContent=pct(topAge[1])+' % des séjours';
  document.getElementById('k_fem').textContent=pct(fem)+' %';

  document.getElementById('insight').innerHTML=
    `<b>${fmt(total)}</b> hospitalisations ${state.year==='all'?'sur '+DATA.years[0]+'–'+DATA.years[DATA.years.length-1]:'en '+state.year}`
    +`${state.sex!=='all'?' ('+(state.sex==='F'?'femmes':'hommes')+')':''}. `
    +`1er motif <b>${topCat[0]}</b> (${pct(topCat[1])}%) ; tranche d'âge dominante <b>${topAge[0]}</b> ; `
    +`durée moyenne <b>${dur.toFixed(1)} j</b>.`;

  // B3 tendance
  const ty=sumBy(ff(['year']),0,4);
  charts.c_trend.setOption({grid:{...GRID,top:'10%'},tooltip:{trigger:'axis'},
    xAxis:{type:'category',data:DATA.years,...AX},yAxis:{type:'value',...AX,...SPL},
    series:[{type:'bar',barWidth:'55%',data:DATA.years.map(y=>({value:ty[y]||0,
      itemStyle:{color:(state.year!=='all'&&y==state.year)?'#0b5cad':'#118dff',borderRadius:[3,3,0,0]}}))}]});

  // B4 diagnostics
  const dm=Object.entries(catMap).sort((a,b)=>a[1]-b[1]);
  charts.c_diag.setOption({grid:{...GRID,left:'3%'},tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
    xAxis:{type:'value',...AX,...SPL},
    yAxis:{type:'category',data:dm.map(d=>d[0]),...AX,axisLabel:{color:'#6b7280',width:130,overflow:'truncate',fontSize:10}},
    series:[{type:'bar',data:dm.map(d=>d[1]),itemStyle:{color:'#12b886',borderRadius:[0,3,3,0]}}]});

  // B5 âge
  const ages=DATA.ages.filter(a=>a!=='Inconnu');
  charts.c_age.setOption({grid:GRID,tooltip:{trigger:'axis'},
    xAxis:{type:'category',data:ages,...AX},yAxis:{type:'value',...AX,...SPL},
    series:[{type:'bar',barWidth:'55%',data:ages.map(a=>ageMap[a]||0),itemStyle:{color:'#7048e8',borderRadius:[3,3,0,0]}}]});

  // B5 sexe
  const xm=sumBy(ff(['sex']),2,4);
  charts.c_sex.setOption({tooltip:{trigger:'item',formatter:'{b}: {c} ({d}%)'},legend:{bottom:0,textStyle:{color:'#6b7280'}},
    series:[{type:'pie',radius:['48%','72%'],center:['50%','45%'],
      data:[{name:'Femmes',value:xm.F||0,itemStyle:{color:'#e64980'}},{name:'Hommes',value:xm.H||0,itemStyle:{color:'#118dff'}}],
      label:{color:'#4b5563'}}]});

  // B3 durée
  charts.c_dur.setOption({grid:GRID,tooltip:{trigger:'axis'},
    xAxis:{type:'category',data:DATA.years,...AX},yAxis:{type:'value',...AX,...SPL},
    series:[{type:'line',smooth:true,symbol:'circle',symbolSize:6,data:DATA.years.map(y=>DATA.duree[y]||0),
      lineStyle:{width:2.5,color:'#12b886'},itemStyle:{color:'#12b886'}}]});
}
document.getElementById('f_year').addEventListener('change',e=>{state.year=e.target.value;render();});
document.querySelectorAll('#f_sex button').forEach(b=>b.addEventListener('click',()=>{
  document.querySelectorAll('#f_sex button').forEach(x=>x.classList.remove('on'));b.classList.add('on');state.sex=b.dataset.v;render();}));
document.getElementById('reset').addEventListener('click',()=>{state.year='all';state.sex='all';
  document.getElementById('f_year').value='all';
  document.querySelectorAll('#f_sex button').forEach(x=>x.classList.toggle('on',x.dataset.v==='all'));render();});
render();
"""

html = dc.page(
    title="Hospitalisation", sub="Tableau de bord décisionnel",
    src="Source : Hospitalisations.csv · agrégats RGPD", active="hospitalisation",
    besoins_html=besoins, slicers_html=slicers, kpis_html=kpis, panels_html=panels,
    data_json=json.dumps(data, ensure_ascii=False), render_js=RENDER,
    foot="Prototype de storytelling — sera reconstruit dans Power BI / Tableau branché sur Hive. "
         "Sexe et âge issus de la jointure avec la dimension Patient. Données agrégées uniquement.",
)
OUT.write_text(html, encoding="utf-8")
print(f"Écrit : {OUT} ({len(html)//1024} Ko) · {sum(trend.values()):,} hospitalisations · {len(years)} années")
