"""SQLite ledger + review queue, with CSV export."""
import csv
import json
import sqlite3
from pathlib import Path

from .llm import FIELDS

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS invoices (file TEXT PRIMARY KEY, {", ".join(f"{f} TEXT" for f in FIELDS)});
CREATE TABLE IF NOT EXISTS review (file TEXT PRIMARY KEY, fields TEXT, problems TEXT);
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def processed(self, file: str) -> bool:
        q = "SELECT 1 FROM invoices WHERE file=? UNION SELECT 1 FROM review WHERE file=?"
        return self.db.execute(q, (file, file)).fetchone() is not None

    def seen_keys(self) -> set[tuple]:
        return set(self.db.execute("SELECT supplier_tax_id, invoice_number FROM invoices"))

    def add_invoice(self, file: str, fields: dict) -> None:
        cols = ["file", *FIELDS]
        self.db.execute(
            f"INSERT INTO invoices ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            [file, *(None if fields[f] is None else str(fields[f]) for f in FIELDS)],
        )
        self.db.commit()

    def add_review(self, file: str, fields: dict, problems: list[str]) -> None:
        self.db.execute("INSERT INTO review VALUES (?, ?, ?)", (file, json.dumps(fields), "; ".join(problems)))
        self.db.commit()

    def export_csv(self, path: Path) -> None:
        cur = self.db.execute("SELECT * FROM invoices ORDER BY date")
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(d[0] for d in cur.description)
            w.writerows(cur)
