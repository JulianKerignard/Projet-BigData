"""Briques communes des dashboards CHU (thème BI clair, ECharts).

Fournit le CSS partagé, le squelette HTML et les helpers JS, pour que les
dashboards par thématique (consultations, hospitalisation, décès, satisfaction)
soient cohérents visuellement.
"""

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#eef0f4;color:#252b36;font-family:'Segoe UI',system-ui,Arial,sans-serif;font-size:13px}
.app{max-width:1320px;margin:0 auto;padding:18px 20px}
.topbar{display:flex;align-items:baseline;gap:12px;border-bottom:2px solid #118dff;padding-bottom:10px;margin-bottom:14px}
.topbar h1{font-size:18px;font-weight:600;color:#1b1f27}
.topbar .sub{color:#6b7280;font-size:12px}
.topbar .src{margin-left:auto;color:#9aa1ab;font-size:11px}
.nav{display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap}
.nav a{text-decoration:none;font-size:12.5px;color:#4b5563;background:#fff;border:1px solid #d9dde3;
border-radius:5px;padding:6px 12px}
.nav a.on{background:#118dff;border-color:#118dff;color:#fff;font-weight:600}
.slicers{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.slicer{background:#fff;border:1px solid #d9dde3;border-radius:4px;padding:7px 10px;min-width:150px}
.slicer .lab{font-size:10.5px;text-transform:uppercase;letter-spacing:.5px;color:#8a909a;font-weight:600;margin-bottom:4px}
.slicer select{width:100%;border:none;font-size:13px;color:#252b36;background:transparent;outline:none;cursor:pointer}
.seg{display:flex;gap:4px}
.seg button{flex:1;border:1px solid #d9dde3;background:#fff;color:#4b5563;border-radius:3px;padding:5px 8px;
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
"""

# helpers JS communs (palette, axes, agrégation)
JS_HELPERS = """
const PAL=['#118dff','#12b886','#e8590c','#7048e8','#e64980','#15aabf','#fab005','#4263eb','#2f9e44','#d6336c','#1098ad','#5c940d','#868e96'];
const MONTHS=['Jan','Fév','Mar','Avr','Mai','Juin','Juil','Aoû','Sep','Oct','Nov','Déc'];
const AX={axisLine:{lineStyle:{color:'#ccd1d9'}},axisLabel:{color:'#6b7280'},axisTick:{show:false}};
const SPL={splitLine:{lineStyle:{color:'#eef0f4'}}};
const GRID={left:'3%',right:'4%',bottom:'3%',top:'14%',containLabel:true};
const fmt=n=>Math.round(n).toLocaleString('fr-FR');
function sumBy(rows,k,v){const m={};rows.forEach(r=>m[r[k]]=(m[r[k]]||0)+r[v]);return m;}
"""

# barre de navigation entre les 4 dashboards
def nav(active):
    items = [("consultations", "Consultations"), ("hospitalisation", "Hospitalisation"),
             ("deces", "Décès"), ("satisfaction", "Satisfaction")]
    links = "".join(
        f'<a href="{k}_dashboard.html" class="{"on" if k == active else ""}">{lbl}</a>'
        for k, lbl in items)
    return f'<div class="nav">{links}</div>'


def page(*, title, sub, src, active, besoins_html, slicers_html,
         kpis_html, panels_html, data_json, render_js, foot):
    """Assemble une page dashboard complète."""
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CHU · {title}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>{CSS}</style></head><body>
<div class="app">
<div class="topbar"><h1>Cloud Healthcare Unit — {title}</h1>
  <span class="sub">{sub}</span><span class="src">{src}</span></div>
{nav(active)}
<div class="besoins">{besoins_html}</div>
<div class="slicers">{slicers_html}</div>
<div class="insight" id="insight">—</div>
<div class="kpis">{kpis_html}</div>
<div class="grid">{panels_html}</div>
<div class="foot">{foot}</div>
</div>
<script>
const DATA = {data_json};
{JS_HELPERS}
{render_js}
</script></body></html>"""
