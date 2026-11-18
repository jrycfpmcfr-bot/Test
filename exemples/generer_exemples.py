"""Génère des P&ID d'exemple (rév. A et rév. B) en PDF, DEXPI XML et DXF.

    python exemples/generer_exemples.py

Différences volontaires entre A et B :
  - pompe de secours P-101B ajoutée (+ sa ligne 3"-P-1003-A1A)
  - transmetteur LT-102 supprimé
  - vanne HV-104 renommée en HV-105 (même emplacement)
  - instrument PI-103 déplacé
  - note modifiée
  - (DEXPI) pression de calcul de V-101, plage de PI-103 et position de sécurité
    de FV-101 modifiées ; nouvelle ligne raccordée sur la tubulure V-101/N1
"""

from __future__ import annotations

import os

ICI = os.path.dirname(os.path.abspath(__file__))


# ------------------------------------------------------------------ PDF

def _pdf(chemin: str, rev: str) -> None:
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.pdfgen import canvas

    L, H = landscape(A3)
    c = canvas.Canvas(chemin, pagesize=(L, H))
    c.setLineWidth(1)
    c.rect(20, 20, L - 40, H - 40)

    def texte(x, y, t, taille=9):
        c.setFont("Helvetica", taille)
        c.drawCentredString(x, y, t)

    def bulle(x, y, lettres, numero):
        c.circle(x, y, 16)
        texte(x, y + 2, lettres, 8)
        texte(x, y - 8, numero, 8)

    # Ballon V-101
    c.roundRect(150, 300, 90, 220, 40)
    texte(195, 280, "V-101", 10)
    # Ligne de sortie vers pompe
    c.line(195, 300, 195, 220)
    c.line(195, 220, 420, 220)
    texte(300, 228, '4"-P-1001-A1A', 8)
    # Pompe P-101A
    c.circle(440, 220, 20)
    texte(440, 185, "P-101A", 10)
    # Refoulement
    c.line(460, 220, 700, 220)
    c.line(700, 220, 700, 450)
    texte(600, 228, '3"-P-1002-A1A', 8)
    # Vanne de régulation FV-101
    c.line(690, 330, 710, 350)
    c.line(690, 350, 710, 330)
    texte(735, 337, "FV-101", 8)
    bulle(780, 400, "FIC", "101")
    c.setDash(3, 3)
    c.line(764, 400, 700, 345)
    c.setDash()

    # Indicateur de pression
    if rev == "A":
        bulle(520, 280, "PI", "103")
    else:
        bulle(560, 290, "PI", "103")
    # Niveau sur le ballon
    bulle(290, 450, "LIC", "101")
    if rev == "A":
        bulle(290, 380, "LT", "102")
    # Vanne manuelle
    c.line(240, 520, 300, 520)
    texte(270, 530, "HV-104" if rev == "A" else "HV-105", 8)

    # Pompe de secours
    if rev == "B":
        c.line(195, 220, 195, 140)
        c.line(195, 140, 420, 140)
        c.circle(440, 140, 20)
        texte(440, 105, "P-101B", 10)
        texte(300, 148, '3"-P-1003-A1A', 8)

    # Cartouche
    c.rect(L - 300, 20, 280, 90)
    texte(L - 160, 85, "UNITE 100 - BALLON DE CHARGE", 10)
    texte(L - 160, 65, f"PID-100-001 REV {rev}", 10)
    note = ("NOTE 1 : VANNE HV-104 CADENASSEE OUVERTE" if rev == "A"
            else "NOTE 1 : VANNE HV-105 CADENASSEE OUVERTE")
    c.setFont("Helvetica", 8)
    c.drawString(40, 60, note)
    c.drawString(40, 45, "NOTE 2 : PENTE 1% VERS V-101")
    c.showPage()
    c.save()


# ------------------------------------------------------------------ DEXPI

def _dexpi(chemin: str, rev: str) -> None:
    pression = "10" if rev == "A" else "12"

    def ga(nom, val, unite=None):
        from xml.sax.saxutils import quoteattr
        u = f" Units={quoteattr(unite)}" if unite else ""
        return f'<GenericAttribute Name={quoteattr(nom)} Value={quoteattr(val)}{u} Format="string"/>'

    def equip(ident, classe, tag, x, y, attrs="", nozzles=""):
        return (f'<Equipment ID="{ident}" ComponentClass="{classe}" TagName="{tag}">'
                f'<Position><Location X="{x}" Y="{y}" Z="0"/><Axis X="0" Y="0" Z="1"/>'
                f'<Reference X="1" Y="0" Z="0"/></Position>'
                f'<GenericAttributes Set="DexpiAttributes">{ga("TagNameAssignmentClass", tag)}{attrs}'
                f'</GenericAttributes>{nozzles}</Equipment>')

    def nozzle(ident, num):
        return (f'<Nozzle ID="{ident}" ComponentClass="Nozzle">'
                f'<GenericAttributes Set="DexpiAttributes">{ga("SubTagName", num)}</GenericAttributes></Nozzle>')

    items = [
        equip("V1", "Vessel", "V-101", 195, 400,
              ga("DesignPressure", pression, "bar") + ga("DesignTemperature", "120", "degC")
              + ga("Material", "A516-70"),
              nozzle("V1N1", "N1") + nozzle("V1N2", "N2")),
        equip("P1", "CentrifugalPump", "P-101A", 440, 220,
              ga("NominalCapacity", "50", "m3/h") + ga("Power", "15", "kW"), nozzle("P1N1", "N1")),
    ]
    if rev == "B":
        items.append(equip("P2", "CentrifugalPump", "P-101B", 440, 140,
                           ga("NominalCapacity", "50", "m3/h") + ga("Power", "15", "kW")))

    def ligne(ident, num, dn, frm, to):
        return (f'<PipingNetworkSystem ID="{ident}" ComponentClass="PipingNetworkSystem">'
                f'<GenericAttributes Set="DexpiAttributes">{ga("LineNumberAssignmentClass", num)}'
                f'{ga("NominalDiameterRepresentationAssignmentClass", dn)}'
                f'{ga("PipingClassCodeAssignmentClass", "A1A")}</GenericAttributes>'
                f'<PipingNetworkSegment ID="{ident}S1" ComponentClass="PipingNetworkSegment">'
                f'<Connection FromID="{frm}" ToID="{to}"/></PipingNetworkSegment>'
                f'</PipingNetworkSystem>')

    items.append(ligne("L1", '4"-P-1001-A1A', '4"', "V1N2", "P1N1"))
    items.append(ligne("L2", '3"-P-1002-A1A', '3"', "P1", "FV1"))
    if rev == "B":
        items.append(ligne("L3", '3"-P-1003-A1A', '3"', "V1N1", "P2"))

    def instr(ident, tag, classe, extra=""):
        return (f'<ProcessInstrumentationFunction ID="{ident}" ComponentClass="{classe}">'
                f'<GenericAttributes Set="DexpiAttributes">'
                f'{ga("ProcessInstrumentationFunctionNumber", tag)}{extra}</GenericAttributes>'
                f'</ProcessInstrumentationFunction>')

    items.append(instr("I1", "FIC-101", "ProcessInstrumentationFunction", ga("Range", "0-60 m3/h")))
    items.append(instr("I2", "LIC-101", "ProcessInstrumentationFunction"))
    if rev == "A":
        items.append(instr("I3", "LT-102", "ProcessInstrumentationFunction"))
    items.append(instr("I4", "PI-103", "ProcessInstrumentationFunction",
                       ga("Range", "0-16 bar" if rev == "A" else "0-25 bar")))
    items.append('<PipingComponent ID="FV1" ComponentClass="GlobeValve">'
                 '<GenericAttributes Set="DexpiAttributes">'
                 + ga("PipingComponentNumber", "FV-101") + ga("FailAction", "FC" if rev == "A" else "FO")
                 + '</GenericAttributes></PipingComponent>')

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<PlantModel xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
           '<PlantInformation SchemaVersion="4.1.1" OriginatingSystem="pid_diff exemples" '
           'Date="2026-11-18" Time="00:00:00" Is3D="no" Units="Millimetre" Discipline="PID"/>'
           '<Drawing Name="PID-100-001" Type="PID"><Extent><Min X="0" Y="0"/><Max X="1190" Y="842"/></Extent>'
           '</Drawing>' + "".join(items) + '</PlantModel>')
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(xml)


# ------------------------------------------------------------------ DXF

def _dxf(chemin: str, rev: str) -> None:
    import ezdxf

    doc = ezdxf.new()
    blk = doc.blocks.new("POMPE")
    blk.add_circle((0, 0), 20)
    blk.add_attdef("TAG", (0, -30), dxfattribs={"height": 5})
    blk.add_attdef("SERVICE", (0, -40), dxfattribs={"height": 3})
    msp = doc.modelspace()

    def pompe(tag, x, y, service):
        ref = msp.add_blockref("POMPE", (x, y))
        ref.add_auto_attribs({"TAG": tag, "SERVICE": service})

    pompe("P-101A", 440, 220, "CHARGE")
    if rev == "B":
        pompe("P-101B", 440, 140, "CHARGE SECOURS")
    msp.add_text("V-101", dxfattribs={"height": 6}).set_placement((180, 280))
    msp.add_text('4"-P-1001-A1A', dxfattribs={"height": 4}).set_placement((270, 228))
    msp.add_text("LIC-101", dxfattribs={"height": 4}).set_placement((280, 450))
    if rev == "A":
        msp.add_text("LT-102", dxfattribs={"height": 4}).set_placement((280, 380))
    msp.add_text("NOTE : REV " + rev, dxfattribs={"height": 4}).set_placement((40, 40))
    doc.saveas(chemin)


def main() -> None:
    for rev in ("A", "B"):
        _pdf(os.path.join(ICI, f"pid_rev{rev}.pdf"), rev)
        _dexpi(os.path.join(ICI, f"pid_rev{rev}.xml"), rev)
        try:
            _dxf(os.path.join(ICI, f"pid_rev{rev}.dxf"), rev)
        except ImportError:
            print("ezdxf absent : exemples DXF non générés")
    print("Exemples générés dans", ICI)


if __name__ == "__main__":
    main()
