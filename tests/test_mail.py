import email
import email.policy
from email.message import EmailMessage

from invoice_agent.mail import pdf_parts


def build(filename: str, ctype: str = "application/pdf") -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = "Factura octubre"
    msg.set_content("Adjunto factura")
    maintype, subtype = ctype.split("/")
    msg.add_attachment(b"%PDF-1.3 fake", maintype=maintype, subtype=subtype, filename=filename)
    # round-trip through bytes like a real IMAP fetch
    return email.message_from_bytes(msg.as_bytes(), policy=email.policy.default)


def test_accented_filename_is_detected():
    parts = pdf_parts(build("factura_año_2026.pdf"))
    assert [n for n, _ in parts] == ["factura_año_2026.pdf"]
    assert parts[0][1] == b"%PDF-1.3 fake"


def test_pdf_by_content_type_without_extension():
    assert len(pdf_parts(build("factura", ctype="application/pdf"))) == 1


def test_non_pdf_ignored():
    assert pdf_parts(build("foto.jpg", ctype="image/jpeg")) == []
