from email.message import EmailMessage

import pytest

from app.errors import EmailError
from app.services import email_service


def _eml(html=False, attach=False):
    m = EmailMessage()
    m["Subject"], m["From"], m["To"] = "PO 4500123", "buyer@example.com", "orders@acme.com"
    if html:
        m.set_content("<html><style>p{}</style><body><p>Please ship <b>10</b> widgets.</p></body></html>", subtype="html")
    else:
        m.set_content("Please find our purchase order attached.")
    if attach:
        m.add_attachment(b"%PDF-1.4 fake", maintype="application", subtype="pdf", filename="po.pdf")
    return m.as_bytes()


def test_parse_plain_eml():
    p = email_service.parse_eml(_eml())
    assert p["subject"] == "PO 4500123"
    assert p["sender"] == "buyer@example.com"
    assert p["recipient"] == "orders@acme.com"
    assert "purchase order" in p["body"]


def test_parse_html_eml_strips_tags_and_styles():
    p = email_service.parse_eml(_eml(html=True))
    assert "ship 10 widgets" in " ".join(p["body"].split())
    assert "<" not in p["body"] and "p{}" not in p["body"]


def test_parse_eml_with_attachment():
    p = email_service.parse_eml(_eml(attach=True))
    assert [a[0] for a in p["attachments"]] == ["po.pdf"]


def test_garbage_is_rejected():
    with pytest.raises(EmailError):
        email_service.parse_eml(b"\x00\x01\x02 not an email")


def test_build_email_text():
    t = email_service.build_email_text("S", "a@b.c", "d@e.f", "  hello  ")
    assert t.startswith("Subject: S\nFrom: a@b.c\nTo: d@e.f") and t.endswith("hello")


def test_email_api():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app)
    r = c.post("/email/submit", json={"subject": "Hi", "sender": "a@b.c", "recipient": "d@e.f", "body": "Hello there"})
    assert r.status_code == 200 and r.json()["input_type"] == "email" and "Hello there" in r.json()["text"]
    assert c.post("/email/submit", json={"body": "   "}).status_code == 422
    up = c.post("/email/upload", files={"file": ("m.eml", _eml(), "message/rfc822")})
    assert up.status_code == 200 and "PO 4500123" in up.json()["text"]
    bad = c.post("/email/upload", files={"file": ("m.txt", b"hi", "text/plain")})
    assert bad.status_code == 415
