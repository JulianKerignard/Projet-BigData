#!/usr/bin/env python3
"""Génère le MCD (schéma en constellation) du CHU : PNG + source .drawio.

Une seule définition de structure -> deux sorties cohérentes :
- docs/mcd_constellation.png      (matplotlib, pour le rapport)
- docs/mcd_constellation.drawio   (source éditable draw.io)

Constellation corrigée (vs version initiale) :
- ajout Dim_Professionnel (besoin B6) et Dim_Geographie (B7 décès, B8 satisfaction) ;
- Fait_Consultation SANS établissement (source mono-établissement, B1 N/A) ;
- Fait_Satisfaction SANS patient (source agrégée par établissement) ;
- Fait_Deces relié à la géographie (B7) et non à un patient/établissement ;
- clés de substitution (surrogate keys) + patient pseudonymisé.
"""
from pathlib import Path
import xml.sax.saxutils as su
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[2]
PNG = ROOT / "docs/mcd_constellation.png"
DRAWIO = ROOT / "docs/mcd_constellation.drawio"

DIM, FACT = "dim", "fact"

# table = (id, type, titre, [attributs], x, y)  — x,y = coin haut-gauche (unités: 0..16 / 0..10)
TABLES = {
    # --- dimensions (gauche) ---
    "Dim_Temps": (DIM, "Dim_Temps", [
        "date_id : INT (YYYYMMDD) [PK]", "jour : INT", "mois : INT",
        "trimestre : INT", "annee : INT", "jour_semaine : VARCHAR"], 0.3, 8.6),
    "Dim_Patient": (DIM, "Dim_Patient", [
        "patient_id : VARCHAR(64) [PK]", "  (hash SHA-256, pseudonymisé)",
        "sexe : CHAR(1) (M/F)", "tranche_age : VARCHAR", "region_residence : VARCHAR"], 0.3, 5.0),
    "Dim_Professionnel": (DIM, "Dim_Professionnel", [
        "prof_id : VARCHAR [PK]", "specialite : VARCHAR",
        "categorie_prof : VARCHAR", "code_specialite : VARCHAR"], 0.3, 1.8),
    # --- dimensions (droite) ---
    "Dim_Diagnostic": (DIM, "Dim_Diagnostic", [
        "diag_id : VARCHAR(20) [PK]", "code_cim10 : VARCHAR(10)",
        "libelle : VARCHAR(255)", "chapitre_cim10 : VARCHAR"], 12.6, 8.6),
    "Dim_Etablissement": (DIM, "Dim_Etablissement", [
        "etab_id : VARCHAR(20) [PK]", "  (FINESS géographique)",
        "nom_etab : VARCHAR(255)", "type_etab : VARCHAR(50)", "region / departement : VARCHAR"], 12.6, 5.2),
    "Dim_Geographie": (DIM, "Dim_Geographie", [
        "geo_id : VARCHAR [PK]", "code_region : VARCHAR", "region : VARCHAR",
        "code_departement : VARCHAR", "departement : VARCHAR"], 12.6, 1.8),
    # --- faits (centre) ---
    "Fait_Consultation": (FACT, "Fait_Consultation", [
        "consultation_key [PK]", "FK → Temps, Patient,",
        "       Professionnel, Diagnostic", "Mesures : nb_consult, duree_min"], 6.4, 9.2),
    "Fait_Hospitalisation": (FACT, "Fait_Hospitalisation", [
        "hospitalisation_key [PK]", "FK → Temps, Patient,",
        "       Etablissement, Diagnostic", "Mesures : nb_hospi, duree_sejour"], 6.4, 6.9),
    "Fait_Satisfaction": (FACT, "Fait_Satisfaction", [
        "satisfaction_key [PK]", "FK → Temps, Etablissement,",
        "       Geographie", "Mesure : score_satisfaction"], 6.4, 4.6),
    "Fait_Deces": (FACT, "Fait_Deces", [
        "deces_key [PK]", "FK → Temps, Geographie",
        "sexe, tranche_age (dégénérés)", "Mesure : nb_deces"], 6.4, 2.3),
}

# liens fait -- dimension (constellation)
LINKS = [
    ("Fait_Consultation", "Dim_Temps"), ("Fait_Consultation", "Dim_Patient"),
    ("Fait_Consultation", "Dim_Professionnel"), ("Fait_Consultation", "Dim_Diagnostic"),
    ("Fait_Hospitalisation", "Dim_Temps"), ("Fait_Hospitalisation", "Dim_Patient"),
    ("Fait_Hospitalisation", "Dim_Diagnostic"), ("Fait_Hospitalisation", "Dim_Etablissement"),
    ("Fait_Satisfaction", "Dim_Temps"), ("Fait_Satisfaction", "Dim_Etablissement"),
    ("Fait_Satisfaction", "Dim_Geographie"),
    ("Fait_Deces", "Dim_Temps"), ("Fait_Deces", "Dim_Geographie"),
]

W = 3.4                       # largeur des boîtes
LINE_H = 0.34                 # hauteur par ligne d'attribut
HEAD_H = 0.5                  # hauteur de l'en-tête


def box_h(attrs):
    return HEAD_H + LINE_H * len(attrs) + 0.18


# ============================ PNG (matplotlib) ============================
def render_png():
    fig, ax = plt.subplots(figsize=(16, 10))
    ax.set_xlim(0, 16); ax.set_ylim(-0.4, 10); ax.axis("off")
    DIMC, DIMH = "#dbe8fb", "#4178c0"
    FACTC, FACTH = "#d7ecd9", "#3f9445"

    geom = {}
    for tid, (typ, title, attrs, x, y) in TABLES.items():
        h = box_h(attrs)
        geom[tid] = {"x": x, "y": y, "h": h, "cy": y - h / 2}

    # liens : ancrés sur les BORDS (le fait au centre, la dim à gauche/droite)
    for a, b in LINKS:                       # a = fait (centre), b = dimension
        fa, di = geom[a], geom[b]
        if di["x"] < fa["x"]:                # dimension à gauche
            x1, x2 = fa["x"], di["x"] + W
        else:                                # dimension à droite
            x1, x2 = fa["x"] + W, di["x"]
        ax.plot([x1, x2], [fa["cy"], di["cy"]], color="#aab0b8", lw=1.0, zorder=1)

    for tid, (typ, title, attrs, x, y) in TABLES.items():
        h = box_h(attrs)
        body, head = (FACTC, FACTH) if typ == FACT else (DIMC, DIMH)
        # corps
        ax.add_patch(FancyBboxPatch((x, y - h), W, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                     fc=body, ec=head, lw=1.4, zorder=2))
        # en-tête
        ax.add_patch(FancyBboxPatch((x, y - HEAD_H), W, HEAD_H, boxstyle="round,pad=0.02,rounding_size=0.08",
                     fc=head, ec=head, lw=1.4, zorder=3))
        ax.text(x + W / 2, y - HEAD_H / 2, title, ha="center", va="center",
                color="white", fontsize=11, fontweight="bold", zorder=4)
        for i, at in enumerate(attrs):
            ax.text(x + 0.16, y - HEAD_H - 0.07 - LINE_H * (i + 0.5), at,
                    ha="left", va="center", color="#252423", fontsize=8.3, zorder=4)

    ax.text(8, 9.78, "MCD — Schéma en constellation · Cloud Healthcare Unit (entrepôt décisionnel santé)",
            ha="center", va="center", fontsize=14, fontweight="bold", color="#1b1f27")
    ax.text(8, -0.15,
            "Bleu = dimension conforme   ·   Vert = table de fait   ·   "
            "B1 (consultation/établissement) non applicable : source mono-établissement",
            ha="center", va="center", fontsize=8.5, color="#605e5c", style="italic")
    fig.savefig(PNG, dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"PNG écrit : {PNG}")


# ============================ .drawio (XML) ============================
def render_drawio():
    px = 110  # échelle unités -> pixels
    cells = []
    cid = 10
    ids = {}
    for tid, (typ, title, attrs, x, y) in TABLES.items():
        h = box_h(attrs)
        gx, gy = x * px, (10 - y) * px            # drawio: origine en haut
        gw, gh = W * px, h * px
        fill, stroke = ("#d7ecd9", "#3f9445") if typ == FACT else ("#dbe8fb", "#4178c0")
        label = "<b>" + su.escape(title) + "</b><br/>" + "<br/>".join(su.escape(a) for a in attrs)
        ids[tid] = cid
        cells.append(
            f'<mxCell id="{cid}" value="{label}" style="rounded=1;whiteSpace=wrap;html=1;'
            f'fillColor={fill};strokeColor={stroke};align=left;verticalAlign=top;spacingLeft=8;'
            f'spacingTop=6;fontSize=10;" vertex="1" parent="1">'
            f'<mxGeometry x="{gx:.0f}" y="{gy:.0f}" width="{gw:.0f}" height="{gh:.0f}" as="geometry"/></mxCell>')
        cid += 1
    for a, b in LINKS:
        cells.append(
            f'<mxCell id="{cid}" style="endArrow=none;html=1;strokeColor=#9aa1ab;" edge="1" parent="1" '
            f'source="{ids[a]}" target="{ids[b]}"><mxGeometry relative="1" as="geometry"/></mxCell>')
        cid += 1
    title = ('<mxCell id="9" value="MCD - Schema en constellation - Cloud Healthcare Unit" '
             'style="text;html=1;fontSize=16;fontStyle=1;align=center;" vertex="1" parent="1">'
             '<mxGeometry x="380" y="10" width="900" height="30" as="geometry"/></mxCell>')
    xml = (
        '<mxfile host="app.diagrams.net" type="device">\n'
        '  <diagram name="MCD Constellation" id="mcd-constellation">\n'
        '    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" '
        'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1700" pageHeight="1100" '
        'math="0" shadow="0">\n      <root>\n'
        '        <mxCell id="0" />\n        <mxCell id="1" parent="0" />\n        '
        + title + "\n        " + "\n        ".join(cells)
        + "\n      </root>\n    </mxGraphModel>\n  </diagram>\n</mxfile>\n")
    DRAWIO.write_text(xml, encoding="utf-8")
    print(f"drawio écrit : {DRAWIO}")


if __name__ == "__main__":
    render_png()
    render_drawio()
