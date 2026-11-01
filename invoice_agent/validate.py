"""Independent checks. Any failure sends the invoice to human review instead of the ledger."""
import re
from datetime import date

TOLERANCE = 0.02  # cents rounding
CIF_LETTERS = "JABCDEFGHI"
NIF_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"


def valid_spanish_tax_id(tax_id: str | None) -> bool:
    if not tax_id:
        return False
    s = re.sub(r"[\s-]", "", tax_id.upper()).removeprefix("ES")
    if re.fullmatch(r"\d{8}[A-Z]", s):  # NIF
        return NIF_LETTERS[int(s[:8]) % 23] == s[8]
    if re.fullmatch(r"[XYZ]\d{7}[A-Z]", s):  # NIE
        return NIF_LETTERS[int(str("XYZ".index(s[0])) + s[1:8]) % 23] == s[8]
    if re.fullmatch(r"[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]", s):  # CIF
        digits = s[1:8]
        even = sum(int(d) for d in digits[1::2])
        odd = sum(sum(divmod(int(d) * 2, 10)) for d in digits[0::2])
        ctrl = (10 - (even + odd) % 10) % 10
        return s[8] in (str(ctrl), CIF_LETTERS[ctrl])
    return False


def check(fields: dict, seen_keys: set[tuple]) -> list[str]:
    problems = []
    for k in ("supplier", "invoice_number", "date", "base", "vat", "total", "currency"):
        if fields.get(k) in (None, ""):
            problems.append(f"missing {k}")
    if not valid_spanish_tax_id(fields.get("supplier_tax_id")):
        problems.append(f"invalid tax id {fields.get('supplier_tax_id')!r}")
    try:
        base, vat, total = float(fields["base"]), float(fields["vat"]), float(fields["total"])
        held = abs(float(fields.get("withholding") or 0))
        if abs(base + vat - held - total) > TOLERANCE:
            problems.append(f"base + vat - withholding != total ({base} + {vat} - {held} != {total})")
        rate = fields.get("vat_rate")  # null when the invoice mixes VAT rates
        if rate is not None and abs(base * float(rate) / 100 - vat) > TOLERANCE:
            problems.append(f"vat != base x {rate}%")
        w_rate = fields.get("withholding_rate")
        if w_rate is not None and abs(base * float(w_rate) / 100 - held) > TOLERANCE:
            problems.append(f"withholding != base x {w_rate}%")
    except (TypeError, ValueError, KeyError):
        problems.append("amounts not numeric")
    try:
        if date.fromisoformat(str(fields.get("date"))) > date.today():
            problems.append("date in the future")
    except ValueError:
        problems.append(f"bad date {fields.get('date')!r}")
    key = (fields.get("supplier_tax_id"), fields.get("invoice_number"))
    if all(key) and key in seen_keys:
        problems.append("duplicate (same supplier and invoice number)")
    return problems
