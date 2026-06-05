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
/* =====================================================================
   CHU dashboards — « Power BI pro / SaaS analytics » (D3 + best of D1/D2)
   Classes / IDs preserves. Ajouts purement additifs : #scope, .kpi-top,
   .kpi-ic, .kpi-foot, .kpi-delta, .kpi-spark (rendus seulement si emis).
   ===================================================================== */
:root{
  --canvas:#eef1f6; --card:#ffffff; --ink:#252423; --muted:#605e5c;
  --line:#e9ebf0; --accent:#118dff; --accent-d:#0b5cad; --accent-soft:#e8f2ff;
  --pos:#1a9e57; --pos-bg:#e6f6ee; --neg:#e5484d; --neg-bg:#fde8e8; --neu-bg:#f1f2f5;
  --radius:12px; --radius-sm:8px; --gap:16px;
  --shadow-1:0 1px 2px rgba(16,24,40,.05),0 2px 6px rgba(16,24,40,.07);
  --shadow-2:0 10px 28px -8px rgba(16,24,40,.18),0 4px 10px -4px rgba(16,24,40,.10);
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:
    radial-gradient(1100px 560px at 100% -12%,#f4f7fc 0,transparent 60%),
    var(--canvas);
  color:var(--ink);font-family:'Segoe UI',system-ui,-apple-system,Inter,Arial,sans-serif;
  font-size:13px;line-height:1.45;-webkit-font-smoothing:antialiased}
.app{max-width:1340px;margin:0 auto;padding:22px 24px 40px}

/* ---- En-tete ---- */
.topbar{display:flex;align-items:center;gap:14px;margin-bottom:18px}
.topbar .mark{width:44px;height:44px;border-radius:13px;flex:none;
  background:linear-gradient(135deg,#3a96ff,#0857b8);display:grid;place-items:center;
  color:#fff;font-size:20px;font-weight:700;box-shadow:0 6px 14px -4px rgba(17,141,255,.5)}
.topbar h1{font-size:19px;font-weight:650;letter-spacing:.2px}
.topbar .sub{color:var(--muted);font-size:12px;margin-top:1px}
/* scope = rappel du filtre actif (optionnel, alimente par renderScope()) */
#scope{display:inline-flex;align-items:center;gap:6px;margin-top:5px;font-size:11.5px;
  color:var(--accent-d);background:var(--accent-soft);border-radius:20px;padding:2px 10px;font-weight:600}
#scope:empty{display:none}
#scope .dot{width:6px;height:6px;border-radius:50%;background:var(--accent)}
.topbar .src{margin-left:auto;color:#9aa1ab;font-size:11px;text-align:right;max-width:300px}

/* ---- Navigation : onglets soulignes ---- */
.nav{display:flex;gap:2px;margin-bottom:18px;border-bottom:1px solid var(--line)}
.nav a{text-decoration:none;font-size:13px;color:var(--muted);padding:9px 16px;
  border-bottom:2px solid transparent;margin-bottom:-1px;transition:color .12s,border-color .12s}
.nav a:hover{color:var(--ink)}
.nav a.on{color:var(--accent);border-bottom-color:var(--accent);font-weight:600}

/* ---- Bandeau besoins ---- */
.besoins{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px;font-size:12px;color:var(--muted)}
.bes{display:flex;align-items:center;gap:7px}
.bes .dot{width:8px;height:8px;border-radius:50%;flex:none}
.bes b{color:var(--ink);font-weight:650}
.bes.ok .dot{background:var(--pos)}.bes.ko .dot{background:var(--neg)}.bes.ctx .dot{background:#9aa1ab}

/* ---- Filter pane sticky : slicers + chips ---- */
.filterbar{position:sticky;top:10px;z-index:20;background:var(--card);border-radius:var(--radius);
  box-shadow:var(--shadow-1);border:1px solid var(--line);padding:11px 16px;margin-bottom:16px;
  display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.filterbar::before{content:"FILTRES";font-size:10px;letter-spacing:1px;color:#b3b8c2;
  font-weight:700;align-self:center}
.fb-label{font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;color:#9aa1ab;font-weight:700}
.slicer{display:flex;align-items:center;gap:8px}
.slicer select{border:1px solid #e3e6ea;border-radius:7px;padding:7px 11px;font-size:13px;
  color:var(--ink);background:#fff;outline:none;cursor:pointer;font-family:inherit;transition:border-color .12s}
.slicer select:hover{border-color:var(--accent)}
.slicer select:focus{outline:2px solid var(--accent);outline-offset:1px;border-color:var(--accent)}
.tiles{display:flex;gap:4px}
.tiles button{border:1px solid #e3e6ea;background:#fff;color:var(--muted);border-radius:7px;
  padding:6px 13px;font-size:12.5px;cursor:pointer;font-family:inherit;transition:all .12s}
.tiles button:hover{border-color:var(--accent);color:var(--ink)}
.tiles button:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.tiles button[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
.chips{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-left:auto}
.chip{display:inline-flex;align-items:center;gap:6px;background:var(--accent-soft);color:var(--accent-d);
  border:1px solid #cfe6ff;border-radius:14px;padding:4px 6px 4px 11px;font-size:12px;font-weight:600}
.chip .k{font-weight:400;color:#5b7aa0;font-size:10.5px;text-transform:uppercase;letter-spacing:.3px}
.chip .x{cursor:pointer;width:16px;height:16px;border-radius:50%;display:grid;place-items:center;
  background:#cfe6ff;color:var(--accent-d);font-size:12px;line-height:1;transition:.12s}
.chip .x:hover{background:var(--accent);color:#fff}
.clearall{border:none;background:none;color:var(--muted);font-size:12px;cursor:pointer;text-decoration:underline}
.clearall:hover{color:var(--neg)}
.chips-empty{margin-left:auto;color:#b7bcc4;font-size:12px;font-style:italic}

/* ---- Bandeau narratif (pull-quote) ---- */
.insight{background:linear-gradient(90deg,var(--accent-soft),#fff 62%);
  border-left:3px solid var(--accent);border-radius:var(--radius-sm);
  box-shadow:var(--shadow-1);padding:13px 18px;margin-bottom:16px;font-size:14px;color:#374151}
.insight b{color:var(--ink)}

/* ---- KPI : tiles enrichies (cartes en elevation) ---- */
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:var(--gap);margin-bottom:var(--gap)}
.kpi{background:var(--card);border:1px solid #f0f1f4;border-radius:var(--radius);box-shadow:var(--shadow-1);
  padding:14px 16px 12px;position:relative;overflow:hidden;display:flex;flex-direction:column;gap:2px;
  min-height:104px;transition:box-shadow .15s,transform .15s}
.kpi:hover{box-shadow:var(--shadow-2);transform:translateY(-3px)}
.kpi::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--c,var(--accent));opacity:.9}
/* ligne haut : libelle + icone (icone optionnelle) */
.kpi-top{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}
.kpi .lab{flex:1;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.4px;font-weight:650}
.kpi-ic{width:28px;height:28px;border-radius:9px;flex:none;display:grid;place-items:center;
  font-size:15px;line-height:1;color:var(--c,var(--accent));
  background:color-mix(in srgb,var(--c,var(--accent)) 12%,#fff)}
/* grand chiffre */
.kpi .val{font-size:27px;font-weight:760;letter-spacing:-.3px;margin-top:6px;color:var(--ink);
  line-height:1.1;font-variant-numeric:tabular-nums}
/* pied : delta pill + note */
.kpi .note{font-size:11px;color:#9aa1ab;margin-top:4px}
/* PASTILLE DELTA — cible le <span> inline emis par trendNote() (actif SANS modif JS),
   et aussi les classes .up/.down si un hook JS optionnel les pose plus tard */
.kpi .note span{display:inline-flex;align-items:center;gap:3px;padding:2px 7px;border-radius:11px;
  font-weight:700;font-size:11.5px;font-variant-numeric:tabular-nums;background:var(--neu-bg)}
.kpi .note span[style*="1a9e57"],.kpi .note span[style*="13a10e"],.kpi .note span[style*="107c10"],
.kpi .note span.up{background:var(--pos-bg)!important;color:var(--pos)!important}
.kpi .note span[style*="d13438"],.kpi .note span[style*="e5484d"],
.kpi .note span.down{background:var(--neg-bg)!important;color:var(--neg)!important}
/* structure enrichie optionnelle (si kpis_html emet .kpi-foot/.kpi-delta) */
.kpi-foot{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-top:4px;min-height:16px}
.kpi-foot .note{margin-top:0}
.kpi-delta{display:inline-flex;align-items:center;gap:3px;font-size:11.5px;font-weight:700;
  padding:2px 7px;border-radius:11px;font-variant-numeric:tabular-nums;line-height:1.4}
.kpi-delta.up{color:var(--pos);background:var(--pos-bg)}
.kpi-delta.down{color:var(--neg);background:var(--neg-bg)}
.kpi-delta.flat{color:var(--muted);background:var(--neu-bg)}
/* micro-sparkline (optionnelle, ancree bas-droite) */
.kpi-spark{position:absolute;right:14px;bottom:11px;width:80px;height:28px;opacity:.9;pointer-events:none}
.kpi-spark:empty{display:none}

/* ---- Grille de visuels ---- */
.report{display:grid;gap:var(--gap);grid-template-columns:repeat(6,1fr);grid-auto-rows:minmax(120px,auto)}
.card{background:var(--card);border:1px solid #f0f1f4;border-radius:var(--radius);box-shadow:var(--shadow-1);
  padding:14px 16px;display:flex;flex-direction:column;transition:box-shadow .15s,transform .15s}
.card:hover{box-shadow:var(--shadow-2);transform:translateY(-2px)}
.card h3{font-size:13.5px;font-weight:650;color:var(--ink);display:flex;align-items:center;gap:8px}
.card .tag{color:var(--muted);font-size:11px;margin:5px 0 8px;line-height:1.4} /* micro-legende contextuelle */
.card .chart{width:100%;flex:1;min-height:240px}
.bcode{font-weight:700;color:#fff;background:var(--accent);border-radius:5px;
  font-size:10.5px;padding:2px 7px;letter-spacing:.3px}
.hint{margin-left:auto;font-size:10.5px;color:#b7bcc4;font-weight:400;display:inline-flex;align-items:center;gap:4px}
.hint::before{content:"";width:5px;height:5px;border-radius:50%;background:var(--accent)}
.col2{grid-column:span 2}.col3{grid-column:span 3}.col4{grid-column:span 4}.col6{grid-column:span 6}
.tall .chart{min-height:330px}

.foot{color:#9aa1ab;font-size:11px;margin-top:18px;padding-top:14px;border-top:1px solid var(--line);
  text-align:center;line-height:1.6}

/* ---- Skeleton de chargement optionnel : .chart vide -> shimmer ---- */
.chart:empty{background:linear-gradient(100deg,#f4f6f9 30%,#eef1f6 50%,#f4f6f9 70%);
  background-size:200% 100%;animation:sh 1.3s infinite;border-radius:8px}
@keyframes sh{to{background-position:-200% 0}}

/* ---- Responsive ---- */
@media(max-width:1040px){
  .kpis{grid-template-columns:repeat(2,1fr)}
  .report{grid-template-columns:repeat(2,1fr)}
  .col2,.col3,.col4,.col6{grid-column:span 2}
  .filterbar{position:static}
  .filterbar::before{display:none}
  .kpi-spark{display:none}
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
  color:['#118dff','#1a9e57','#e8590c','#7048e8','#e64980','#15aabf','#fab005','#4263eb','#2f9e44','#d6336c','#1098ad','#5c940d'],
  textStyle:{fontFamily:"'Segoe UI',Inter,system-ui,sans-serif",color:'#605e5c'},
  backgroundColor:'transparent',
  title:{textStyle:{color:'#252423'}}
});
const PAL=['#118dff','#1a9e57','#e8590c','#7048e8','#e64980','#15aabf','#fab005','#4263eb','#2f9e44','#d6336c','#1098ad','#5c940d'];
const MONTHS=['Jan','Fév','Mar','Avr','Mai','Juin','Juil','Aoû','Sep','Oct','Nov','Déc'];
const AX={axisLine:{lineStyle:{color:'#dfe2e6'}},axisLabel:{color:'#605e5c',fontSize:11},axisTick:{show:false}};
const SPL={splitLine:{lineStyle:{color:'#eef0f4',type:'dashed'}}};
const GRID={left:'3%',right:'5%',bottom:'3%',top:'12%',containLabel:true};
const fmt=n=>Math.round(n).toLocaleString('fr-FR');
const TT={trigger:'axis',axisPointer:{type:'shadow'},backgroundColor:'#fff',borderWidth:0,
  textStyle:{color:'#252423'},extraCssText:'box-shadow:0 8px 24px rgba(16,24,40,.16);border-radius:10px;padding:9px 13px;'};
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

// tooltip enrichi : valeur + part (%) sur le total du visuel
function ttPct(sum){return Object.assign({},TT,{formatter:ps=>{
  const a=Array.isArray(ps)?ps:[ps];
  return a.map(p=>{const pct=sum?Math.round(100*p.value/sum):0;
    return `${p.marker||''}${p.axisValueLabel||p.name}: <b>${fmt(p.value)}</b> (${pct}%)`;}).join('<br>');}});}

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
  const sum=entries.reduce((s,e)=>s+e[1],0);                       // total du visuel -> %
  // couleur des barres : fusion estompage (selection) + degrade par valeur (hors selection)
  const vals=entries.map(e=>e[1]);
  const vmin=Math.min(...vals), vmax=Math.max(...vals);
  const lerp=(a,b,t)=>Math.round(a+(b-a)*t);
  const ramp=t=>{const t2=Math.max(0,Math.min(1,t));            // #cfe1f7 (faible) -> #118dff (fort)
    return `rgb(${lerp(0xcf,0x11,t2)},${lerp(0xe1,0x8d,t2)},${lerp(0xf7,0xff,t2)})`;};
  const barColor=v=>{
    if(sel) return v===sel?'#0b5cad':'#cdd9e8';                  // selectionnee foncee, autres estompees
    if(c.color) return c.color;                                  // couleur imposee par le SPEC -> mono
    const val=entries.find(e=>e[0]===v)?.[1]||0;
    return ramp(vmax===vmin?1:(val-vmin)/(vmax-vmin));};
  const pctLabel={show:!!c.showPct,position:c.kind==='barh'?'right':'top',
    color:'#605e5c',fontSize:10,formatter:o=>sum?Math.round(100*o.value/sum)+'%':''};
  // label de VALEUR (additif) : actif si c.showVal et pas de showPct (eviter le double label)
  const valLabel={show:!!c.showVal && !c.showPct,position:c.kind==='barh'?'right':'top',
    color:'#605e5c',fontSize:10,fontWeight:600,formatter:o=>fmt(o.value)};
  const barLabel=(c.showVal && !c.showPct)?valLabel:pctLabel;
  const barEmph={focus:'series',itemStyle:{shadowBlur:6,shadowColor:'rgba(17,141,255,.25)'}};

  if(c.kind==='bar'){
    ch.setOption({backgroundColor:'transparent',grid:{...GRID,top:(c.showVal?'14%':'10%')},tooltip:ttPct(sum),
      xAxis:{type:'category',data:entries.map(e=>e[0]),...AX},
      yAxis:{type:'value',...AX,...SPL,axisLine:{show:false}},
      series:[{type:'bar',barWidth:'58%',label:barLabel,data:entries.map(e=>({value:e[1],
        itemStyle:{color:barColor(e[0]),borderRadius:[5,5,0,0]}})),
        emphasis:barEmph}]},true);
  } else if(c.kind==='barh'){
    const e2=[...entries].reverse();
    ch.setOption({backgroundColor:'transparent',grid:{...GRID,left:'3%'},tooltip:ttPct(sum),
      xAxis:{type:'value',...AX,...SPL},
      yAxis:{type:'category',data:e2.map(e=>e[0]),...AX,
        axisLabel:{color:'#605e5c',width:140,overflow:'truncate',fontSize:11}},
      series:[{type:'bar',barWidth:'58%',label:barLabel,data:e2.map(e=>({value:e[1],
        itemStyle:{color:barColor(e[0]),borderRadius:[0,5,5,0]}})),
        emphasis:barEmph}]},true);
  } else if(c.kind==='line'){
    const lc=c.color||'#118dff';
    ch.setOption({backgroundColor:'transparent',grid:GRID,
      tooltip:Object.assign({},ttPct(sum),{axisPointer:{type:'line',lineStyle:{type:'dashed',color:'#c8c8c8'}}}),
      xAxis:{type:'category',data:entries.map(e=>e[0]),...AX,boundaryGap:false},
      yAxis:{type:'value',...AX,...SPL,axisLine:{show:false}},
      series:[{type:'line',smooth:true,symbol:'circle',symbolSize:6,
        data:entries.map(e=>e[1]),lineStyle:{width:2.5,color:lc},
        itemStyle:{color:lc},
        areaStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,
          [{offset:0,color:lc+'40'},{offset:1,color:lc+'04'}])}}]},true);
  } else if(c.kind==='pie'){
    ch.setOption({backgroundColor:'transparent',
      tooltip:Object.assign({},TTI,{formatter:'{b}: <b>{c}</b> ({d}%)'}),
      legend:{bottom:0,textStyle:{color:'#605e5c'}},
      series:[{type:'pie',radius:['48%','72%'],center:['50%','46%'],
        data:entries.map((e,i)=>({name:e[0],value:e[1],
          itemStyle:{color:sel?(e[0]===sel?PAL[i%PAL.length]:'#dde3ea'):PAL[i%PAL.length]}})),
        label:{color:'#605e5c'},emphasis:{focus:'self'}}]},true);
  } else if(c.kind==='map'){
    const data=entries.map(e=>({name:e[0],value:e[1]}));
    const max=Math.max(1,...entries.map(e=>e[1]));
    ch.setOption({backgroundColor:'transparent',
      tooltip:Object.assign({},TTI,{formatter:p=>{
        const pct=sum&&p.value?Math.round(100*p.value/sum):0;
        return `${p.name}: <b>${p.value!=null?fmt(p.value):'n/d'}</b>`+(p.value?` (${pct}%)`:'');}}),
      visualMap:{type:'continuous',min:0,max,left:8,bottom:8,calculable:true,
        inRange:{color:['#e7f0fb','#7db4ec','#118dff','#0b5cad']},
        textStyle:{color:'#605e5c',fontSize:10}},
      series:[{type:'map',map:'france',roam:false,data,
        itemStyle:{borderColor:'#fff',borderWidth:1,areaColor:'#f0f1f4'},
        emphasis:{label:{show:false},itemStyle:{areaColor:'#fab005'}},
        select:{itemStyle:{areaColor:'#0b5cad'},label:{show:false}}}]},true);
  }
}

// tendance du total vs année N-1 (si une année est filtrée et que N-1 existe)
function trendNote(){
  if(!('annee' in state) || state.annee===null) return null;
  const di=SPEC.dims['annee'], mi=SPEC.measureIndex;
  const y=parseInt(state.annee,10);
  const sumYear=yy=>SPEC.facts.filter(r=>parseInt(r[di],10)===yy
      && Object.entries(state).every(([d,v])=>v===null||d==='annee'||r[SPEC.dims[d]]===v))
    .reduce((s,r)=>s+r[mi],0);
  const cur=sumYear(y), prev=sumYear(y-1);
  if(!prev) return null;
  const d=Math.round(100*(cur-prev)/prev);
  const arrow=d>0?'▲':(d<0?'▼':'=');
  const col=d>0?'#1a9e57':(d<0?'#e5484d':'#605e5c');
  return `<span style="color:${col}">${arrow} ${d>0?'+':''}${d}%</span> vs ${y-1}`;
}

// % d'evolution N vs N-1 (null si pas d'annee filtree ou pas de N-1) — meme logique que trendNote
function trendPct(){
  if(!('annee' in state) || state.annee===null) return null;
  const di=SPEC.dims['annee'], mi=SPEC.measureIndex, y=parseInt(state.annee,10);
  const sumYear=yy=>SPEC.facts.filter(r=>parseInt(r[di],10)===yy
      && Object.entries(state).every(([d,v])=>v===null||d==='annee'||r[SPEC.dims[d]]===v))
    .reduce((s,r)=>s+r[mi],0);
  const cur=sumYear(y), prev=sumYear(y-1);
  if(!prev) return null;
  return Math.round(100*(cur-prev)/prev);
}

// mini area-line dans .kpi-spark via ECharts (theme 'chu'), sans axes ni tooltip
function renderSpark(k){
  const host=document.getElementById(k.id+'_spk');
  if(!host || !k.spark) return;
  const g=groupSum(rowsExcept(),k.spark);
  const xs=Object.keys(g).sort((a,b)=>(parseFloat(a)||a)>(parseFloat(b)||b)?1:-1);
  if(xs.length<2){host.style.display='none';return;}
  host.style.display='';
  const sp=echarts.getInstanceByDom(host)||echarts.init(host,'chu');
  const col=k.color||'#118dff';
  sp.setOption({backgroundColor:'transparent',grid:{left:0,right:0,top:2,bottom:2},
    xAxis:{type:'category',show:false,data:xs},yAxis:{type:'value',show:false},tooltip:{show:false},
    series:[{type:'line',data:xs.map(x=>g[x]),smooth:true,symbol:'none',
      lineStyle:{width:1.8,color:col},
      areaStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,
        [{offset:0,color:col+'33'},{offset:1,color:col+'00'}])}}]},true);
}

// rappel du filtre actif dans la topbar (optionnel, no-op si #scope absent)
function renderScope(){const el=document.getElementById('scope'); if(!el)return;
  const a=Object.entries(state).filter(([d,v])=>v!==null);
  el.innerHTML=a.length?('<span class="dot"></span>'+a.map(([d,v])=>(SPEC.dimLabels[d]||d)+' '+v).join(' · ')):'';}

function renderKpis(){
  SPEC.kpis.forEach(k=>{
    const el=document.getElementById(k.id); if(!el)return;
    let v='–', note=k.note||'';
    if(k.calc==='total'){v=fmt(total(rowsExcept()));
      const tn=trendNote(); if(tn)note=tn;}
    else if(k.calc==='topDim'){const t=topOf(k.dim);v=t[0];
      const tot=total(rowsExcept());note=tot?Math.round(100*t[1]/tot)+' % '+(k.noteSuffix||''):'';}
    else if(k.calc==='pctFem'){v=pctFem()+' %';}
    else if(k.calc==='nDim'){v=Object.keys(groupSum(rowsExcept(),k.dim)).length;}
    el.querySelector('.val').textContent=v;
    if(k.calc==='total'){el.querySelector('.note').innerHTML=note;}
    else if(k.calc==='topDim'){el.querySelector('.note').textContent=note;}
  });

  // --- enrichissements KPI (additifs, no-op si elements absents) ---
  SPEC.kpis.forEach(k=>{
    const el=document.getElementById(k.id); if(!el)return;
    // 1) delta -> pastille .kpi-delta pour le KPI total (route le calcul de trendPct)
    const badge=el.querySelector('.kpi-delta');
    if(badge && k.calc==='total'){
      const p=trendPct();
      if(p==null){badge.style.display='none';}
      else{badge.style.display='';
        badge.className='kpi-delta '+(p>0?'up':p<0?'down':'flat');
        badge.textContent=(p>0?'▲ +':p<0?'▼ ':'= ')+p+' %';
        const yEl=el.querySelector('.note');
        if(yEl){yEl.textContent='vs '+(parseInt(state.annee,10)-1);}
      }
    }
    // 2) sparkline si k.spark fourni (nom de dim temporelle, ex 'annee')
    if(k.spark){renderSpark(k);}
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
  renderKpis(); renderChips(); renderNarrative(); renderScope();
}

// ---- init ----
function initDashboard(){
  if(window.__FRGEO__){echarts.registerMap('france', window.__FRGEO__);}  // carte régions
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
  // observer aussi les sparklines KPI (creees au 1er render) — additif, no-op si absentes
  (SPEC.kpis||[]).forEach(k=>{ if(!k.spark)return;
    const h=document.getElementById(k.id+'_spk'); if(h)ro.observe(h); });
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
    """Cartes KPI. Conserve les hooks .lab/.val/.note (lus par renderKpis).
    Ajouts purement optionnels : icone (k['icon']) et sparkline (k['spark'])."""
    cards = []
    for k in kpis:
        c = k.get("color", "#118dff")
        ic = f'<span class="kpi-ic">{k["icon"]}</span>' if k.get("icon") else ""
        spark = f'<div class="kpi-spark" id="{k["id"]}_spk"></div>' if k.get("spark") else ""
        cards.append(
            f'<div class="kpi" id="{k["id"]}" style="--c:{c}">'
            f'<div class="kpi-top"><div class="lab">{k["label"]}</div>{ic}</div>'
            f'<div class="val">–</div>'
            f'<div class="kpi-foot"><span class="kpi-delta" style="display:none"></span>'
            f'<div class="note">{k.get("note", "")}</div></div>'
            f'{spark}</div>')
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
         spec_json=None, narrative_js="", custom_script=None, geojson=None):
    """Assemble une page dashboard complète.

    Deux modes :
    - moteur générique (défaut) : fournir `spec_json` (+ `narrative_js`). Le moteur
      de cross-filter pilote tout (clic-pour-filtrer, KPI, chips).
    - custom : fournir `custom_script` (JS). Le thème ECharts + helpers (JS_THEME)
      restent disponibles ; le script gère son propre rendu. Pour les dashboards
      dont l'agrégation n'est pas une simple somme (ex. moyenne de score).

    `geojson` (str JSON) : si fourni, injecté comme `window.__FRGEO__` et enregistré
    comme carte 'france' (pour les visuels `kind:'map'`).
    """
    geo = f"window.__FRGEO__ = {geojson};\n" if geojson else ""
    if custom_script is not None:
        js = geo + JS_THEME + "\n" + custom_script
    else:
        js = (geo + f"window.__SPEC__ = {spec_json};\n" + JS_THEME + JS_ENGINE
              + f"\nconst narrativeFns = {{ {narrative_js} }};\ninitDashboard();")
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CHU · {title}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"></script>
<style>{CSS}</style></head><body>
<div class="app">
<div class="topbar"><div class="mark">+</div>
  <div><h1>Cloud Healthcare Unit — {title}</h1><div class="sub">{sub}</div><span id="scope"></span></div>
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
