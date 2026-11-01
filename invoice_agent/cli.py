"""Process every PDF in a folder: extract -> LLM fields -> validate -> ledger or review queue."""
import argparse
from pathlib import Path

from dotenv import load_dotenv

from .extract import pdf_images, pdf_text
from .llm import extract_fields
from .mail import fetch_pdf_attachments
from .store import Store
from .validate import check


def run(inbox: Path, out: Path) -> None:
    store = Store(out / "invoices.db")
    for pdf in sorted(inbox.glob("*.pdf")):
        if store.processed(pdf.name):
            continue
        try:
            text = pdf_text(pdf)
            fields = extract_fields(text) if text else extract_fields(images=pdf_images(pdf))
            problems = check(fields, store.seen_keys())
        except Exception as e:  # one bad file must not stop the batch
            fields, problems = {}, [f"extraction error: {type(e).__name__}: {e}"]
        if problems:
            store.add_review(pdf.name, fields, problems)
            print(f"REVIEW  {pdf.name}: {'; '.join(problems)}")
        else:
            store.add_invoice(pdf.name, fields)
            print(f"OK      {pdf.name}: {fields['supplier']} {fields['total']} {fields['currency']}")
    store.export_csv(out / "invoices.csv")


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("inbox", type=Path, help="folder with invoice PDFs")
    p.add_argument("--out", type=Path, default=Path("output"))
    p.add_argument("--imap", action="store_true", help="first download PDF attachments from unread emails into inbox")
    args = p.parse_args()
    if args.imap:
        print(f"Downloaded {len(fetch_pdf_attachments(args.inbox))} PDF(s) from the mailbox")
    run(args.inbox, args.out)


if __name__ == "__main__":
    main()
