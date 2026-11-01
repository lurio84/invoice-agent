"""Structured field extraction with an OpenAI-compatible LLM (DeepSeek by default)."""
import json
import os

from openai import OpenAI

FIELDS = ["supplier", "supplier_tax_id", "invoice_number", "date", "base", "vat_rate", "vat",
          "withholding_rate", "withholding", "total", "currency"]

PROMPT = """Extract the invoice data and answer with a single JSON object with exactly these keys:
supplier (string), supplier_tax_id (string, the ISSUER's NIF/CIF/VAT ID, not the customer's), invoice_number (string),
date (string, ISO YYYY-MM-DD), base (number, total taxable amount), vat_rate (number, percent; null if the invoice
uses more than one VAT rate), vat (number, total VAT amount), withholding_rate (number, IRPF/retention percent, null if none),
withholding (number, IRPF/retention amount as a positive number, null if none), total (number, amount payable),
currency (ISO code taken from the currency codes or symbols printed next to the amounts, e.g. EUR for "EUR" or "€").
Use null for anything not present. Do not compute or guess missing values; copy what the document says.
Numbers use a dot as decimal separator in your answer."""


def client() -> OpenAI:
    return OpenAI(
        api_key=os.environ.get("LLM_API_KEY") or os.environ["DEEPSEEK_API_KEY"],
        base_url=os.environ.get("LLM_BASE_URL", "https://api.deepseek.com"),
    )


def extract_fields(text: str = "", images: list[str] | None = None, llm: OpenAI | None = None) -> dict:
    """Pass the PDF text, or page images (base64 PNG) when there is no text layer."""
    if text:
        content = f"{PROMPT}\n\nInvoice text:\n---\n{text}\n---"
    else:
        content = [{"type": "text", "text": PROMPT}] + [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}} for b64 in images or []]
    resp = (llm or client()).chat.completions.create(
        model=os.environ.get("LLM_MODEL", "deepseek-flash"),
        messages=[{"role": "user", "content": content}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    data = json.loads(resp.choices[0].message.content)
    return {k: data.get(k) for k in FIELDS}
