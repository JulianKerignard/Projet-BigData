"""Briques communes des dashboards CHU — style et interactivité « Power BI ».

Fournit :
- un thème CSS moderne (design tokens, cartes en élévation sans bordure, layout en
  grid-template-areas, filter pane sticky, chips de filtres actifs) ;
- un thème ECharts 'chu' (palette/typo cohérentes) ;
- un MOTEUR DE CROSS-FILTER générique : un dashboard déclare ses dimensions, ses mesures
  et ses visuels ; le moteur gère le clic-pour-filtrer, l'estompage du non-sélectionné,
  les KPI dynamiques, les chips et le bouton « Tout effacer ».

Chaque générateur de dashboard fournit un objet SPEC (JSON) décrivant données + visuels +
KPI, et le moteur (CFENGINE, JS) fait le reste. Rendu = HTML autonome, ECharts via CDN.
"""

# ---------------------------------------------------------------------------
# 1. CSS — thème clair "report canvas" facon Power BI
# ---------------------------------------------------------------------------
CSS = """
:root{
  --canvas:#f3f4f7; --card:#ffffff; --ink:#252423; --muted:#605e5c;
  --line:#edeef1; --accent:#118dff; --accent-d:#0b5cad;
  --radius:10px; --gap:16px;
  --shadow-1:0 1px 2px rgba(16,24,40,.06),0 1px 3px rgba(16,24,40,.10);
  --shadow-2:0 6px 16px -4px rgba(16,24,40,.14),0 3px 6px -3px rgba(16,24,40,.08);
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--canvas);color:var(--ink);
  font-family:'Segoe UI',system-ui,-apple-system,Inter,Arial,sans-serif;font-size:13px;line-height:1.45}
.app{max-width:1340px;margin:0 auto;padding:22px 24px 40px}

/* En-tête */
.topbar{display:flex;align-items:center;gap:14px;margin-bottom:18px}
.topbar .mark{width:40px;height:40px;border-radius:11px;flex:none;
  background:linear-gradient(135deg,#118dff,#0b5cad);display:grid;place-items:center;
  color:#fff;font-size:19px;font-weight:700;box-shadow:var(--shadow-1)}
.topbar h1{font-size:19px;font-weight:650;letter-spacing:.2px}
.topbar .sub{color:var(--muted);font-size:12px;margin-top:1px}
.topbar .src{margin-left:auto;color:#9aa1ab;font-size:11px;text-align:right;max-width:300px}

/* Navigation entre dashboards : onglets soulignés (pas de boîtes) */
.nav{display:flex;gap:2px;margin-bottom:18px;border-bottom:1px solid var(--line)}
.nav a{text-decoration:none;font-size:13px;color:var(--muted);padding:9px 16px;
  border-bottom:2px solid transparent;margin-bottom:-1px;transition:color .12s,border-color .12s}
.nav a:hover{color:var(--ink)}
.nav a.on{color:var(--accent);border-bottom-color:var(--accent);font-weight:600}

/* Bandeau besoins : pastilles discrètes en ligne, sans cartes */
.besoins{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px;font-size:12px;color:var(--muted)}
.bes{display:flex;align-items:center;gap:7px}
.bes .dot{width:8px;height:8px;border-radius:50%;flex:none}
.bes b{color:var(--ink);font-weight:650}
.bes.ok .dot{background:#13a10e}.bes.ko .dot{background:#d13438}.bes.ctx .dot{background:#9aa1ab}

/* Filter pane sticky : slicers + chips de filtres actifs */
.filterbar{position:sticky;top:10px;z-index:20;background:var(--card);border-radius:var(--radius);
  box-shadow:var(--shadow-1);padding:12px 14px;margin-bottom:16px;
  display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.fb-label{font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;color:#9aa1ab;font-weight:700}
.slicer{display:flex;align-items:center;gap:8px}
.slicer select{border:1px solid #e3e6ea;border-radius:7px;padding:7px 11px;font-size:13px;
  color:var(--ink);background:#fff;outline:none;cursor:pointer;font-family:inherit}
.slicer select:hover{border-color:var(--accent)}
.tiles{display:flex;gap:4px}
.tiles button{border:1px solid #e3e6ea;background:#fff;color:var(--muted);border-radius:7px;
  padding:6px 13px;font-size:12.5px;cursor:pointer;font-family:inherit;transition:all .12s}
.tiles button:hover{border-color:var(--accent);color:var(--ink)}
.tiles button[aria-pressed="true"]{background:var(--ink);border-color:var(--ink);color:#fff;font-weight:600}
.chips{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-left:auto}
.chip{display:inline-flex;align-items:center;gap:6px;background:#eaf4ff;color:var(--accent-d);
  border:1px solid #cfe6ff;border-radius:14px;padding:4px 6px 4px 11px;font-size:12px;font-weight:600}
.chip .x{cursor:pointer;width:16px;height:16px;border-radius:50%;display:grid;place-items:center;
  background:#cfe6ff;color:var(--accent-d);font-size:12px;line-height:1}
.chip .x:hover{background:var(--accent);color:#fff}
.chip .k{font-weight:400;color:#5b7aa0;font-size:10.5px;text-transform:uppercase;letter-spacing:.3px}
.clearall{border:none;background:none;color:var(--muted);font-size:12px;cursor:pointer;text-decoration:underline}
.clearall:hover{color:#d13438}
.chips-empty{margin-left:auto;color:#b7bcc4;font-size:12px;font-style:italic}

/* Bandeau narratif */
.insight{background:linear-gradient(90deg,#eaf4ff,#fff 60%);border-radius:var(--radius);
  box-shadow:var(--shadow-1);padding:13px 18px;margin-bottom:16px;font-size:14px;color:#374151}
.insight b{color:var(--ink)}

/* KPI : cartes en élévation, sans bordure */
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:var(--gap);margin-bottom:var(--gap)}
.kpi{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow-1);
  padding:15px 17px;position:relative;overflow:hidden;transition:box-shadow .15s,transform .15s}
.kpi:hover{box-shadow:var(--shadow-2);transform:translateY(-2px)}
.kpi::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--c,var(--accent))}
.kpi .lab{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.4px;font-weight:650}
.kpi .val{font-size:25px;font-weight:750;margin-top:7px;color:var(--ink);line-height:1.1}
.kpi .note{font-size:11px;color:#9aa1ab;margin-top:4px}

/* Layout des visuels : zones nommées -> tailles variables (visuel focal large) */
.report{display:grid;gap:var(--gap);grid-template-columns:repeat(6,1fr);
  grid-auto-rows:minmax(120px,auto)}
.card{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow-1);
  padding:14px 16px;transition:box-shadow .15s;display:flex;flex-direction:column}
.card:hover{box-shadow:var(--shadow-2)}
.card h3{font-size:13.5px;font-weight:650;color:var(--ink);display:flex;align-items:center;gap:8px}
.card .tag{color:#9aa1ab;font-size:11px;margin:3px 0 8px}
.card .chart{width:100%;flex:1;min-height:240px}
.bcode{font-weight:700;color:#fff;background:var(--accent);border-radius:5px;
  font-size:10.5px;padding:2px 7px;letter-spacing:.3px}
.hint{margin-left:auto;font-size:10.5px;color:#b7bcc4;font-weight:400}
/* spans de grille */
.col2{grid-column:span 2}.col3{grid-column:span 3}.col4{grid-column:span 4}.col6{grid-column:span 6}
.tall .chart{min-height:330px}

.foot{color:#9aa1ab;font-size:11px;margin-top:18px;text-align:center;line-height:1.6}
@media(max-width:1040px){
  .kpis{grid-template-columns:repeat(2,1fr)}
  .report{grid-template-columns:repeat(2,1fr)}
  .col2,.col3,.col4,.col6{grid-column:span 2}
  .filterbar{position:static}
}
"""

# ---------------------------------------------------------------------------
# 2. JS — thème ECharts + moteur de cross-filter générique
# ---------------------------------------------------------------------------
# Le générateur fournit un objet SPEC :
#   SPEC = {
#     facts: [[...dims, measure], ...],   // lignes d'agrégats
#     dims:  {nom: index, ...},           // position de chaque dimension dans facts
#     measureIndex: int,                  // index de la mesure (compteur) dans facts
#     slicers: [{dim, label, type:'select'|'tiles', options:[[value,label],...]}],
#     kpis:   [{id, label, note, calc}],  // calc = nom d'une fonction KPI (voir kpiFns)
#     charts: [{id, kind:'bar'|'barh'|'pie'|'line', dim, measure, label, tag, bcode,
#               clickable:bool, sort:'asc'|'desc'|'none', limit:int, order:[...], color}],
#     narrative: fn-name,                 // construit la phrase du bandeau
#   }
# JS_THEME : thème ECharts + helpers de style. TOUJOURS injecté (engine ou custom).
JS_THEME = r"""
echarts.registerTheme('chu', {
  color:['#118dff','#13a10e','#e8590c','#7048e8','#e64980','#15aabf','#fab005','#4263eb','#2f9e44','#d6336c','#1098ad','#5c940d'],
  textStyle:{fontFamily:"'Segoe UI',Inter,system-ui,sans-serif",color:'#605e5c'},
  backgroundColor:'transparent',
  title:{textStyle:{color:'#252423'}}
});
const PAL=['#118dff','#13a10e','#e8590c','#7048e8','#e64980','#15aabf','#fab005','#4263eb','#2f9e44','#d6336c','#1098ad','#5c940d'];
const MONTHS=['Jan','Fév','Mar','Avr','Mai','Juin','Juil','Aoû','Sep','Oct','Nov','Déc'];
const AX={axisLine:{lineStyle:{color:'#dfe2e6'}},axisLabel:{color:'#605e5c'},axisTick:{show:false}};
const SPL={splitLine:{lineStyle:{color:'#f0f1f4'}}};
const GRID={left:'3%',right:'5%',bottom:'3%',top:'12%',containLabel:true};
const fmt=n=>Math.round(n).toLocaleString('fr-FR');
const TT={trigger:'axis',axisPointer:{type:'shadow'},backgroundColor:'#fff',borderWidth:0,
  textStyle:{color:'#252423'},extraCssText:'box-shadow:0 4px 16px rgba(16,24,40,.16);border-radius:8px;padding:8px 12px;'};
const TTI=Object.assign({},TT,{trigger:'item'});
"""

# JS_ENGINE : moteur de cross-filter générique (mode 'engine').
JS_ENGINE = r"""
// ---- état + filtrage ----
const SPEC = window.__SPEC__;
const state = {};                       // {dimName: value|null}
Object.keys(SPEC.dims).forEach(d => state[d] = null);
if(SPEC.initialState){Object.assign(state, SPEC.initialState);}  // filtre par défaut éventuel
const charts = {};

function rowsExcept(exclDim){
  return SPEC.facts.filter(r =>
    Object.entries(state).every(([d,v]) =>
      v===null || d===exclDim || r[SPEC.dims[d]]===v));
}
function groupSum(rows, dimName){
  const di=SPEC.dims[dimName], mi=SPEC.measureIndex, m={};
  rows.forEach(r=>{const k=r[di]; m[k]=(m[k]||0)+r[mi];});
  return m;
}
function total(rows){const mi=SPEC.measureIndex;return rows.reduce((s,r)=>s+r[mi],0);}

// ---- KPI : helpers de calcul ----
function topOf(dim){const g=groupSum(rowsExcept(),dim);
  const e=Object.entries(g).sort((a,b)=>b[1]-a[1]); return e[0]||['–',0];}
function pctFem(){const rows=rowsExcept();const t=total(rows);if(!t)return 0;
  const di=SPEC.dims['sexe'],mi=SPEC.measureIndex;
  const f=rows.filter(r=>r[di]==='F').reduce((s,r)=>s+r[mi],0);return Math.round(100*f/t);}

// ---- rendu d'un visuel ----
function renderChart(c){
  const ch=charts[c.id];
  let entries=Object.entries(groupSum(rowsExcept(c.dim), c.dim));
  // ordre
  if(c.order){const idx={};c.order.forEach((o,i)=>idx[o]=i);
    entries.sort((a,b)=>(idx[a[0]]??99)-(idx[b[0]]??99));}
  else if(c.sort==='desc')entries.sort((a,b)=>b[1]-a[1]);
  else if(c.sort==='asc')entries.sort((a,b)=>a[1]-b[1]);
  if(c.limit)entries=entries.slice(0,c.limit);
  const sel=state[c.dim];
  const barColor=v=> sel? (v===sel?'#0b5cad':'#bcd6f0') : (c.color||'#118dff');

  if(c.kind==='bar'){
    ch.setOption({backgroundColor:'transparent',grid:{...GRID,top:'10%'},tooltip:TT,
      xAxis:{type:'category',data:entries.map(e=>e[0]),...AX},
      yAxis:{type:'value',...AX,...SPL},
      series:[{type:'bar',barWidth:'58%',data:entries.map(e=>({value:e[1],
        itemStyle:{color:barColor(e[0]),borderRadius:[5,5,0,0]}})),
        emphasis:{focus:'series'}}]},true);
  } else if(c.kind==='barh'){
    const e2=[...entries].reverse();
    ch.setOption({backgroundColor:'transparent',grid:{...GRID,left:'3%'},tooltip:TT,
      xAxis:{type:'value',...AX,...SPL},
      yAxis:{type:'category',data:e2.map(e=>e[0]),...AX,
        axisLabel:{color:'#605e5c',width:140,overflow:'truncate',fontSize:11}},
      series:[{type:'bar',data:e2.map(e=>({value:e[1],
        itemStyle:{color:barColor(e[0]),borderRadius:[0,5,5,0]}})),
        emphasis:{focus:'series'}}]},true);
  } else if(c.kind==='line'){
    ch.setOption({backgroundColor:'transparent',grid:GRID,tooltip:TT,
      xAxis:{type:'category',data:entries.map(e=>e[0]),...AX,boundaryGap:false},
      yAxis:{type:'value',...AX,...SPL},
      series:[{type:'line',smooth:true,symbol:'circle',symbolSize:6,
        data:entries.map(e=>e[1]),lineStyle:{width:2.5,color:c.color||'#7048e8'},
        itemStyle:{color:c.color||'#7048e8'},
        areaStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,
          [{offset:0,color:(c.color||'#7048e8')+'40'},{offset:1,color:(c.color||'#7048e8')+'04'}])}}]},true);
  } else if(c.kind==='pie'){
    ch.setOption({backgroundColor:'transparent',tooltip:TTI,
      legend:{bottom:0,textStyle:{color:'#605e5c'}},
      series:[{type:'pie',radius:['48%','72%'],center:['50%','46%'],
        data:entries.map((e,i)=>({name:e[0],value:e[1],
          itemStyle:{color:sel?(e[0]===sel?PAL[i%PAL.length]:'#dde3ea'):PAL[i%PAL.length]}})),
        label:{color:'#605e5c'},emphasis:{focus:'self'}}]},true);
  }
}

function renderKpis(){
  SPEC.kpis.forEach(k=>{
    const el=document.getElementById(k.id); if(!el)return;
    let v='–', note=k.note||'';
    if(k.calc==='total'){v=fmt(total(rowsExcept()));}
    else if(k.calc==='topDim'){const t=topOf(k.dim);v=t[0];
      const tot=total(rowsExcept());note=tot?Math.round(100*t[1]/tot)+' % '+(k.noteSuffix||''):'';}
    else if(k.calc==='pctFem'){v=pctFem()+' %';}
    else if(k.calc==='nDim'){v=Object.keys(groupSum(rowsExcept(),k.dim)).length;}
    el.querySelector('.val').textContent=v;
    if(k.calc==='topDim'){el.querySelector('.note').textContent=note;}
  });
}

function renderChips(){
  const box=document.getElementById('chips');
  const active=Object.entries(state).filter(([d,v])=>v!==null);
  if(!active.length){box.innerHTML='<span class="chips-empty">Aucun filtre actif — cliquez un graphique pour filtrer</span>';return;}
  box.className='chips';
  box.innerHTML=active.map(([d,v])=>
    `<span class="chip"><span class="k">${SPEC.dimLabels[d]||d}</span>${v}`
    +`<span class="x" data-dim="${d}">&times;</span></span>`).join('')
    +'<button class="clearall" id="clearall">Tout effacer</button>';
  box.querySelectorAll('.x').forEach(x=>x.onclick=()=>{state[x.dataset.dim]=null;syncSlicers();render();});
  const ca=document.getElementById('clearall'); if(ca)ca.onclick=clearAll;
}

function syncSlicers(){
  (SPEC.slicers||[]).forEach(s=>{
    if(s.type==='select'){const el=document.getElementById('sl_'+s.dim);
      if(el)el.value=state[s.dim]===null?'all':state[s.dim];}
    else if(s.type==='tiles'){document.querySelectorAll('#sl_'+s.dim+' button').forEach(b=>
      b.setAttribute('aria-pressed', String((state[s.dim]===null?'all':state[s.dim])===b.dataset.v)));}
  });
}
function clearAll(){Object.keys(state).forEach(d=>state[d]=null);syncSlicers();render();}

function renderNarrative(){
  const el=document.getElementById('insight'); if(!el||!SPEC.narrative)return;
  el.innerHTML = narrativeFns[SPEC.narrative]();
}

function render(){
  SPEC.charts.forEach(renderChart);
  renderKpis(); renderChips(); renderNarrative();
}

// ---- init ----
function initDashboard(){
  SPEC.charts.forEach(c=>{
    charts[c.id]=echarts.init(document.getElementById(c.id),'chu');
    if(c.clickable){
      charts[c.id].on('click',p=>{
        if(p.name==null)return;
        state[c.dim]=(state[c.dim]===p.name)?null:p.name;  // toggle
        syncSlicers(); render();
      });
      charts[c.id].getZr().on('click',e=>{ if(!e.target){ if(state[c.dim]!==null){state[c.dim]=null;syncSlicers();render();} } });
    }
  });
  // slicers
  (SPEC.slicers||[]).forEach(s=>{
    if(s.type==='select'){const el=document.getElementById('sl_'+s.dim);
      if(el)el.onchange=ev=>{state[s.dim]=ev.target.value==='all'?null:ev.target.value;render();};}
    else if(s.type==='tiles'){document.querySelectorAll('#sl_'+s.dim+' button').forEach(b=>
      b.onclick=()=>{state[s.dim]=b.dataset.v==='all'?null:b.dataset.v;syncSlicers();render();});}
  });
  // resize
  const ro=new ResizeObserver(es=>{for(const e of es){const i=echarts.getInstanceByDom(e.target);if(i)i.resize();}});
  Object.values(charts).forEach(c=>ro.observe(c.getDom()));
  syncSlicers();   // refléter l'état initial (SPEC.initialState) dans les slicers
  render();
}
"""


# ---------------------------------------------------------------------------
# 3. Helpers Python pour générer le HTML
# ---------------------------------------------------------------------------
def nav(active):
    items = [("consultations", "Consultations"), ("hospitalisation", "Hospitalisation"),
             ("deces", "Décès"), ("satisfaction", "Satisfaction")]
    links = "".join(
        f'<a href="{k}_dashboard.html" class="{"on" if k == active else ""}">{lbl}</a>'
        for k, lbl in items)
    return f'<div class="nav">{links}</div>'


def slicer_html(slicers):
    """Construit la barre de filtres (slicers + zone chips)."""
    parts = []
    for s in slicers or []:
        if s["type"] == "select":
            opts = '<option value="all">Toutes</option>' + "".join(
                f'<option value="{v}">{lbl}</option>' for v, lbl in s["options"])
            parts.append(
                f'<div class="slicer"><span class="fb-label">{s["label"]}</span>'
                f'<select id="sl_{s["dim"]}">{opts}</select></div>')
        elif s["type"] == "tiles":
            btns = '<button data-v="all" aria-pressed="true">Tous</button>' + "".join(
                f'<button data-v="{v}" aria-pressed="false">{lbl}</button>' for v, lbl in s["options"])
            parts.append(
                f'<div class="slicer"><span class="fb-label">{s["label"]}</span>'
                f'<div class="tiles" id="sl_{s["dim"]}">{btns}</div></div>')
    chips = '<div class="chips" id="chips"></div>'
    return f'<div class="filterbar">{"".join(parts)}{chips}</div>'


def kpis_html(kpis):
    cards = []
    for k in kpis:
        c = k.get("color", "#118dff")
        cards.append(
            f'<div class="kpi" id="{k["id"]}" style="--c:{c}">'
            f'<div class="lab">{k["label"]}</div><div class="val">–</div>'
            f'<div class="note">{k.get("note", "")}</div></div>')
    return f'<div class="kpis">{"".join(cards)}</div>'


def charts_html(charts):
    cards = []
    for c in charts:
        span = c.get("span", "col3")
        tall = " tall" if c.get("tall") else ""
        bcode = f'<span class="bcode">{c["bcode"]}</span>' if c.get("bcode") else ""
        hint = '<span class="hint">cliquable</span>' if c.get("clickable") else ""
        cards.append(
            f'<div class="card {span}{tall}"><h3>{bcode}{c["label"]}{hint}</h3>'
            f'<div class="tag">{c.get("tag", "")}</div>'
            f'<div class="chart" id="{c["id"]}"></div></div>')
    return f'<div class="report">{"".join(cards)}</div>'


def besoins_html(besoins):
    return '<div class="besoins">' + "".join(
        f'<div class="bes {b.get("status","ctx")}"><span class="dot"></span>'
        f'<b>{b["code"]}</b> {b["label"]}</div>' for b in besoins) + '</div>'


def page(*, title, sub, src, active, besoins, slicers, kpis, charts, foot,
         spec_json=None, narrative_js="", custom_script=None):
    """Assemble une page dashboard complète.

    Deux modes :
    - moteur générique (défaut) : fournir `spec_json` (+ `narrative_js`). Le moteur
      de cross-filter pilote tout (clic-pour-filtrer, KPI, chips).
    - custom : fournir `custom_script` (JS). Le thème ECharts + helpers (JS_THEME)
      restent disponibles ; le script gère son propre rendu. Pour les dashboards
      dont l'agrégation n'est pas une simple somme (ex. moyenne de score).
    """
    if custom_script is not None:
        js = JS_THEME + "\n" + custom_script
    else:
        js = (f"window.__SPEC__ = {spec_json};\n" + JS_THEME + JS_ENGINE
              + f"\nconst narrativeFns = {{ {narrative_js} }};\ninitDashboard();")
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CHU · {title}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"></script>
<style>{CSS}</style></head><body>
<div class="app">
<div class="topbar"><div class="mark">+</div>
  <div><h1>Cloud Healthcare Unit — {title}</h1><div class="sub">{sub}</div></div>
  <div class="src">{src}</div></div>
{nav(active)}
{besoins_html(besoins)}
{slicer_html(slicers)}
<div class="insight" id="insight">—</div>
{kpis_html(kpis)}
{charts_html(charts)}
<div class="foot">{foot}</div>
</div>
<script>
{js}
</script></body></html>"""
