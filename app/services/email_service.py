"""Build email text from pasted input, or parse an .eml file."""
from email import message_from_bytes, policy
from html.parser import HTMLParser

from app.errors import EmailError

MAX_ATTACHMENTS = 5


class _TextFromHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in ("br", "p", "div", "tr", "li"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextFromHTML()
    parser.feed(html)
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line)


def build_email_text(subject: str | None, sender: str | None, recipient: str | None, body: str) -> str:
    header = [
        f"Subject: {subject or ''}".rstrip(),
        f"From: {sender or ''}".rstrip(),
        f"To: {recipient or ''}".rstrip(),
    ]
    return "\n".join(header) + "\n\n" + (body or "").strip()


def parse_eml(data: bytes) -> dict:
    """Return subject, sender, recipient, body and attachments [(filename, bytes)]."""
    try:
        msg = message_from_bytes(data, policy=policy.default)
    except Exception as exc:  # malformed input
        raise EmailError("Could not read this .eml file.") from exc

    subject, sender, recipient = msg.get("subject"), msg.get("from"), msg.get("to")

    body = ""
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is not None:
        try:
            content = part.get_content()
        except Exception:
            content = ""
        body = html_to_text(content) if part.get_content_type() == "text/html" else content

    attachments = []
    for att in msg.iter_attachments():
        name = att.get_filename()
        payload = att.get_payload(decode=True)
        if name and payload:
            attachments.append((name, payload))

    if not (subject or sender or recipient):
        raise EmailError("This file does not look like an email (.eml) message.")

    return {
        "subject": str(subject) if subject else "",
        "sender": str(sender) if sender else "",
        "recipient": str(recipient) if recipient else "",
        "body": body.strip(),
        "attachments": attachments[:MAX_ATTACHMENTS],
    }
