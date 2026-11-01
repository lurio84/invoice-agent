"""Generate synthetic Spanish invoices (PDF) + ground truth JSON. Fictitious companies, stamped as samples.

clean/  10 template invoices + 3 faulty ones (regression set)
hard/   real-world variants: IRPF withholding, mixed VAT rates, scans, other layout, EU supplier
"""
import io
import json
import random
from pathlib import Path

from PIL import Image, ImageFilter
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
import pypdfium2 as pdfium

ROOT = Path(__file__).parent
SUPPLIERS = ["Suministros Giralda SL", "Talleres Macarena SA", "Papelería Triana SL", "Limpiezas Aljarafe SL",
             "Café Alameda SL", "Imprenta Nervión SA", "Transportes Betis SL", "Informática Cartuja SL",
             "Frutas Guadalquivir SL", "Asesoría Santa Cruz SL"]
ITEMS = ["Material de oficina", "Mantenimiento mensual", "Servicio de limpieza", "Transporte de mercancía",
         "Licencia de software", "Impresión de folletos", "Reparación de equipo", "Consultoría"]
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre"]


def eur(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def cif(rng: random.Random) -> str:
    digits = f"{rng.randrange(10**7):07d}"
    even = sum(int(d) for d in digits[1::2])
    odd = sum(sum(divmod(int(d) * 2, 10)) for d in digits[0::2])
    return "B" + digits + str((10 - (even + odd) % 10) % 10)


def nif(rng: random.Random) -> str:
    n = rng.randrange(10**7, 10**8)
    return f"{n}{'TRWAGMYFPDXBNJZSQVHLCKE'[n % 23]}"


def write_pdf(path: Path, rows: list[tuple]) -> None:
    """rows: (text, x, size). Each row moves down one line; x=None continues on the previous line."""
    c = canvas.Canvas(str(path), pagesize=A4)
    c.saveState()
    c.setFont("Helvetica-Bold", 40)
    c.setFillGray(0.85)
    c.translate(300, 420)
    c.rotate(35)
    c.drawCentredString(0, 0, "MUESTRA FICTICIA / SAMPLE")
    c.restoreState()
    y = 800
    for text, x, size in rows:
        if x is None:
            y += 16
            x = 420
        c.setFont("Helvetica", size)
        c.drawString(x, y, text)
        y -= 16
    c.save()


def standard_rows(inv: dict, layout: int) -> list[tuple]:
    d = inv["date"]
    rows = [(inv["supplier"], 50, 14),
            (f"CIF: {inv['supplier_tax_id']}" if layout != 1 else f"NIF/CIF {inv['supplier_tax_id']}", 50, 10),
            ("C/ Ficticia 12, 41001 Sevilla", 50, 10), ("", 50, 10),
            (f"FACTURA Nº {inv['invoice_number']}" if layout != 2 else f"Factura: {inv['invoice_number']}", 50, 12),
            (f"Fecha: {d}" if layout == 0 else f"Fecha de emisión: {d[8:10]}/{d[5:7]}/{d[0:4]}", 50, 10),
            ("Cliente: Demo Cliente SL - CIF B00000000", 50, 10), ("", 50, 10)]
    for desc, amount, *rate in inv["lines"]:
        rows += [(desc + (f" (IVA {rate[0]}%)" if rate else ""), 50, 10), (f"{eur(amount)} EUR", None, 10)]
    rows.append(("", 50, 10))
    if inv["vat_rate"] is None:  # mixed rates: one VAT line per rate
        for r, (b, v) in inv["vat_breakdown"].items():
            rows.append((f"Base {r}%: {eur(b)}  IVA {r}%: {eur(v)} EUR", 260, 10))
    rows += [(f"Base imponible: {eur(inv['base'])} EUR", 300, 10)]
    if inv["vat_rate"] is not None:
        rows.append((f"IVA {inv['vat_rate']}%: {eur(inv['vat'])} EUR", 300, 10))
    else:
        rows.append((f"Total IVA: {eur(inv['vat'])} EUR", 300, 10))
    if inv.get("withholding"):
        rows.append((f"Retención IRPF {inv['withholding_rate']}%: -{eur(inv['withholding'])} EUR", 300, 10))
    rows.append((f"TOTAL: {eur(inv['total'])} EUR", 300, 12))
    return rows


def other_layout_rows(inv: dict) -> list[tuple]:
    y, m, d = inv["date"].split("-")
    return [("FACTURA", 50, 16), (f"Nº Fra.: {inv['invoice_number']}    {int(d)} de {MONTHS[int(m) - 1]} de {y}", 50, 10),
            ("", 50, 10), ("Emisor", 50, 11), (inv["supplier"], 50, 10), (f"Identificación fiscal {inv['supplier_tax_id']}", 50, 10),
            ("Destinatario", 300, 11), ("Demo Cliente SL  B00000000", 300, 10), ("", 50, 10),
            ("Concepto                                   Importe", 50, 10)] + \
           [(f"{desc}", 50, 10) for desc, *_ in inv["lines"]] + \
           [("", 50, 10), (f"Importe neto   {eur(inv['base'])}", 300, 10),
            (f"Cuota IVA ({inv['vat_rate']}%)   {eur(inv['vat'])}", 300, 10),
            (f"Total a pagar   {eur(inv['total'])} €", 300, 12)]


def scan(pdf: Path, rng: random.Random) -> None:
    """Rasterise, rotate slightly, blur and add noise, then save as an image-only PDF."""
    img = pdfium.PdfDocument(str(pdf))[0].render(scale=1.6).to_pil().convert("L")
    img = img.rotate(rng.uniform(-1.5, 1.5), expand=False, fillcolor=255).filter(ImageFilter.GaussianBlur(0.6))
    noise = Image.effect_noise(img.size, 18)
    img = Image.blend(img, noise, 0.08)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    c = canvas.Canvas(str(pdf), pagesize=A4)
    c.drawImage(ImageReader(io.BytesIO(buf.getvalue())), 0, 0, *A4)
    c.save()


def make_invoice(rng, supplier, tax_id, rates=(21,), withholding_rate=None, n_lines=None):
    lines = []
    for _ in range(n_lines or rng.randint(1, 4)):
        lines.append((rng.choice(ITEMS), round(rng.uniform(20, 900), 2), rng.choice(rates)))
    breakdown = {}
    for _, a, r in lines:
        b, _v = breakdown.get(r, (0, 0))
        breakdown[r] = (round(b + a, 2), 0)
    breakdown = {r: (b, round(b * r / 100, 2)) for r, (b, _) in sorted(breakdown.items(), reverse=True)}
    base = round(sum(b for b, _ in breakdown.values()), 2)
    vat = round(sum(v for _, v in breakdown.values()), 2)
    held = round(base * withholding_rate / 100, 2) if withholding_rate else None
    mixed = len(breakdown) > 1
    inv = {"supplier": supplier, "supplier_tax_id": tax_id, "invoice_number": f"F2026-{rng.randint(100, 999)}",
           "date": f"2026-{rng.randint(1, 10):02d}-{rng.randint(1, 28):02d}", "base": base,
           "vat_rate": None if mixed else lines[0][2], "vat": vat, "withholding_rate": withholding_rate,
           "withholding": held, "total": round(base + vat - (held or 0), 2), "currency": "EUR",
           "lines": lines if mixed else [l[:2] for l in lines], "vat_breakdown": breakdown}
    return inv


def clean_set(rng) -> dict:
    truth = {}
    for i, supplier in enumerate(SUPPLIERS):
        truth[f"{i:02d}-ok.pdf"] = make_invoice(rng, supplier, cif(rng), rates=(21, 21, 10, 4))
    first = truth["00-ok.pdf"]
    truth["90-bad-total.pdf"] = dict(first, invoice_number="F2026-001", total=round(first["total"] + 10, 2))
    truth["91-bad-cif.pdf"] = dict(truth["01-ok.pdf"], invoice_number="F2026-002", supplier_tax_id="B12345670")
    truth["92-duplicate.pdf"] = dict(truth["02-ok.pdf"])
    for name, inv in truth.items():
        inv["expected"] = "review" if name.startswith("9") else "ledger"
    return truth


def hard_set(rng) -> dict:
    t = {
        "h1-irpf-asesoria.pdf": make_invoice(rng, "Ana Ejemplo Ficticia - Asesoría fiscal", nif(rng), withholding_rate=15),
        "h2-mixed-vat.pdf": make_invoice(rng, "Catering Plaza Nueva SL", cif(rng), rates=(21, 10), n_lines=4),
        "h3-other-layout.pdf": make_invoice(rng, "Electricidad Los Remedios SL", cif(rng)),
        "h4-scan.pdf": make_invoice(rng, "Ferretería San Bernardo SL", cif(rng)),
        "h5-scan-irpf.pdf": make_invoice(rng, "Juan Muestra Demo - Diseño gráfico", nif(rng), withholding_rate=15),
        "h6-eu-supplier.pdf": make_invoice(rng, "Lisboa Digital Lda", "PT501234567"),
    }
    for name, inv in t.items():
        inv["expected"] = "review" if "eu-supplier" in name else "ledger"  # validator only knows Spanish tax IDs
    return t


def main() -> None:
    rng = random.Random(42)
    for set_name, truth in (("clean", clean_set(rng)), ("hard", hard_set(rng))):
        out = ROOT / set_name
        out.mkdir(exist_ok=True)
        for name, inv in truth.items():
            rows = other_layout_rows(inv) if "other-layout" in name else standard_rows(inv, int(name[1:2]) % 3)
            write_pdf(out / name, rows)
            if "scan" in name:
                scan(out / name, rng)
        for inv in truth.values():
            inv.pop("lines"), inv.pop("vat_breakdown")
        (ROOT / f"truth_{set_name}.json").write_text(json.dumps(truth, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{len(truth)} invoices in {out}")


if __name__ == "__main__":
    main()
