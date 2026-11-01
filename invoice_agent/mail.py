"""Download PDF attachments from matching emails (IMAP) into the inbox folder.

Only emails matching IMAP_SEARCH (default: unread with "factura" in the subject) in IMAP_FOLDER are read,
and only those that actually carry a PDF get marked as read. Everything else in the mailbox is left untouched.
"""
import email
import email.policy
import imaplib
import os
import re
from email.message import EmailMessage
from pathlib import Path

DEFAULT_SEARCH = '(UNSEEN SUBJECT "factura")'


def pdf_parts(msg: EmailMessage) -> list[tuple[str, bytes]]:
    """(filename, content) of every PDF attachment; handles RFC 2047-encoded names."""
    out = []
    for part in msg.walk():
        name = part.get_filename() or ""
        if name.lower().endswith(".pdf") or part.get_content_type() == "application/pdf":
            out.append((name or "attachment.pdf", part.get_payload(decode=True)))
    return out


def fetch_pdf_attachments(inbox: Path) -> list[Path]:
    inbox.mkdir(parents=True, exist_ok=True)
    saved = []
    with imaplib.IMAP4_SSL(os.environ["IMAP_HOST"]) as m:
        m.login(os.environ["IMAP_USER"], os.environ["IMAP_PASSWORD"])
        m.select(os.environ.get("IMAP_FOLDER", "INBOX"))
        _, uids = m.uid("search", None, os.environ.get("IMAP_SEARCH", DEFAULT_SEARCH))
        for uid in uids[0].split():  # UIDs are stable; sequence numbers get reused
            _, data = m.uid("fetch", uid, "(BODY.PEEK[])")  # PEEK: don't mark as read yet
            msg = email.message_from_bytes(data[0][1], policy=email.policy.default)
            parts = pdf_parts(msg)
            for i, (name, content) in enumerate(parts):
                path = inbox / f"uid{uid.decode()}-{i}-{re.sub(r'[^\w.-]', '_', name)}"
                path.write_bytes(content)
                saved.append(path)
            if parts:
                m.uid("store", uid, "+FLAGS", "\\Seen")
    return saved
