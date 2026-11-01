"""Compare pipeline output with ground truth for one sample set.

Usage: python samples/evaluate.py clean|hard   (after: python -m invoice_agent.cli samples/<set> --out output/<set>)
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent
CHECKED = ["supplier", "supplier_tax_id", "invoice_number", "date", "base", "vat_rate", "vat",
           "withholding_rate", "withholding", "total", "currency"]


def same(a, b) -> bool:
    if a is None or b is None:
        return a in (None, "", 0) and b in (None, "", 0)
    try:
        return abs(float(a) - float(b)) < 0.005
    except (TypeError, ValueError):
        return str(a).strip().lower() == str(b).strip().lower()


def main(set_name: str) -> None:
    truth = json.loads((ROOT / f"truth_{set_name}.json").read_text(encoding="utf-8"))
    db = sqlite3.connect(ROOT.parent / "output" / set_name / "invoices.db")
    db.row_factory = sqlite3.Row
    ledger = {r["file"]: dict(r) for r in db.execute("SELECT * FROM invoices")}
    review = {r["file"]: (json.loads(r["fields"]), r["problems"]) for r in db.execute("SELECT * FROM review")}
    exact = routed = 0
    for name, t in truth.items():
        got, route = (ledger[name], "ledger") if name in ledger else (review[name][0], "review")
        wrong = [k for k in CHECKED if k in t and not same(got.get(k), t[k])]
        # Faulty-by-design invoices are "exact" if extraction matched what is printed; their check is the routing.
        exact += not wrong
        routed += route == t["expected"]
        note = f" -> review: {review[name][1]}" if route == "review" else ""
        print(f"{'OK ' if not wrong and route == t['expected'] else 'BAD'} {name:24} route={route:6} "
              f"(expected {t['expected']})" + (f" wrong={wrong}" if wrong else "") + note)
    print(f"\n[{set_name}] exact extraction {exact}/{len(truth)}, correct routing {routed}/{len(truth)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "clean")
