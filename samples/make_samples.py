"""Generate FICTITIOUS sample trade documents (invoice + bill of lading) as PDFs.

Produces a clean matching pair and a pair with deliberate discrepancies.
All companies, numbers and people are invented for demo purposes.
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT = Path(__file__).parent

SHIPMENT = {
    "shipper": "Lionsgate Instruments Pte Ltd, 21 Tuas Ave 9, Singapore 639180",
    "consignee": "Hollandse Procestechniek B.V., Waalhaven 12, Rotterdam, NL",
    "notify": "Same as consignee",
    "container": "DEMU1234565",
    "seal": "SL889102",
    "packages": 24,
    "gross": 1850.0,
    "net": 1620.0,
    "pol": "Singapore (SGSIN)",
    "pod": "Rotterdam (NLRTM)",
    "goods": "Electromagnetic flow meters and pressure transmitters",
}

ITEMS = [
    ("Electromagnetic flow meter DN50", 40, 1150.00),
    ("Electromagnetic flow meter DN100", 20, 1680.00),
    ("Pressure transmitter 0-40 bar", 60, 420.00),
]


def _header(c, title, ref):
    c.setFillColor(colors.HexColor("#b00020"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, 815, "SAMPLE DOCUMENT - FICTITIOUS DATA FOR DEMO PURPOSES ONLY")
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, 785, title)
    c.setFont("Helvetica", 10)
    c.drawRightString(555, 788, ref)
    c.line(40, 775, 555, 775)


def _lines(c, rows, y):
    for label, value in rows:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, y, f"{label}:")
        c.setFont("Helvetica", 10)
        c.drawString(175, y, str(value))
        y -= 18
    return y


def make_invoice(path, s):
    c = canvas.Canvas(str(path), pagesize=A4)
    _header(c, "COMMERCIAL INVOICE", "Invoice No: LGI-INV-2026-0418")
    total = sum(q * p for _, q, p in ITEMS)
    y = _lines(c, [
        ("Invoice No", "LGI-INV-2026-0418"),
        ("Invoice Date", "2026-10-20"),
        ("Shipper", s["shipper"]),
        ("Consignee", s["consignee"]),
        ("Incoterms", "FOB Singapore"),
        ("Port of Loading", s["pol"]),
        ("Port of Discharge", s["pod"]),
        ("Country of Origin", "Singapore"),
        ("Container No", s["container"]),
        ("Packages", f"{s['packages']} pallets"),
        ("Gross Weight", f"{s['gross']:,.1f} kg"),
        ("Net Weight", f"{s['net']:,.1f} kg"),
        ("Description of Goods", s["goods"]),
    ], 750)
    y -= 10
    c.setFont("Helvetica-Bold", 10)
    for x, h in ((40, "Item"), (330, "Qty"), (400, "Unit Price"), (490, "Amount")):
        c.drawString(x, y, h)
    c.line(40, y - 4, 555, y - 4)
    c.setFont("Helvetica", 10)
    for desc, q, p in ITEMS:
        y -= 18
        c.drawString(40, y, desc)
        c.drawString(330, y, str(q))
        c.drawString(400, y, f"{p:,.2f}")
        c.drawString(490, y, f"{q * p:,.2f}")
    y -= 26
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, f"Total Value: USD {total:,.2f}")
    c.save()


def make_bl(path, s):
    c = canvas.Canvas(str(path), pagesize=A4)
    _header(c, "BILL OF LADING", "B/L No: OCNX-SIN-RTM-77310")
    _lines(c, [
        ("B/L No", "OCNX-SIN-RTM-77310"),
        ("Shipper", s["shipper"]),
        ("Consignee", s["consignee"]),
        ("Notify Party", s["notify"]),
        ("Vessel / Voyage", "MV DEMO HORIZON / 044W"),
        ("Port of Loading", s["pol"]),
        ("Port of Discharge", s["pod"]),
        ("Container No", s["container"]),
        ("Seal No", s["seal"]),
        ("Packages", f"{s['packages']} pallets"),
        ("Gross Weight", f"{s['gross']:,.1f} kg"),
        ("Description of Goods", s["goods"]),
    ], 750)
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(40, 480, "Shipped on board in apparent good order and condition. (Fictitious carrier: Oceanix Demo Lines)")
    c.save()


if __name__ == "__main__":
    make_invoice(OUT / "clean_invoice.pdf", SHIPMENT)
    make_bl(OUT / "clean_bl.pdf", SHIPMENT)
    bad = dict(SHIPMENT,
               consignee="Hollandse Prosestechniek B.V., Waalhaven 12, Rotterdam, NL",  # spelling
               container="DEMU1234556",  # transposed digits
               packages=22,              # count
               gross=1925.0)             # weight
    make_invoice(OUT / "mismatch_invoice.pdf", SHIPMENT)
    make_bl(OUT / "mismatch_bl.pdf", bad)
    print("wrote samples to", OUT)
