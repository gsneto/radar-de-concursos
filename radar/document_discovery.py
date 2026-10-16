"""Reconhece links documentais da página pública oficial, sem navegar neles."""

from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from radar.collector import SOURCE_URL
from radar.document_store import register_document


_AUTHORIZED_SOURCES = (
    ("guajaramirim.ro.gov.br", lambda path: path.lower().endswith((".pdf", ".html", ".htm"))),
    ("www.diariomunicipal.com.br", lambda path: path.startswith(
        ("/arom/materia/", "/arom/download/materia/", "/arom/download/edicao/"))),
    # Segunda fonte oficial: matérias do Diário Oficial da União (Imprensa Nacional).
    ("www.in.gov.br", lambda path: path.startswith("/web/dou/-/")),
)


def allowed_document_url(url: str) -> bool:
    parts = urlsplit(url)
    if (parts.scheme != "https" or not parts.hostname or parts.username
            or parts.password or parts.port is not None):
        return False
    return any(parts.hostname == host and check(parts.path) for host, check in _AUTHORIZED_SOURCES)


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.href = None
        self.words = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.words = []

    def handle_data(self, data):
        if self.href is not None:
            self.words.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href:
            self.links.append((self.href, " ".join(" ".join(self.words).split())))
            self.href = None


def discover_documents(article_html: str, article_url: str, observation_id: str) -> list[dict]:
    if article_url != SOURCE_URL:
        raise ValueError("página de descoberta não autorizada")
    parser = _Links()
    parser.feed(article_html)
    discovered_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    found = []
    for href, title in parser.links:
        url = urljoin(article_url, href)
        if url in seen or not allowed_document_url(url):
            continue
        label = title.lower()
        if "retifica" in label:
            kind = "retificacao"
        elif "edital" in label:
            kind = "edital"
        else:
            continue
        seen.add(url)
        found.append(dict(observation_id=observation_id, kind=kind, official_url=url,
                          title=title, discovery_url=article_url, discovery_method="automatico",
                          discovered_at=discovered_at))
    return found


def register_manual_url(db_path, observation_id: str, kind: str, official_url: str, title: str) -> str:
    if not allowed_document_url(official_url):
        raise ValueError("URL documental não autorizada")
    return register_document(db_path, dict(observation_id=observation_id, kind=kind,
             official_url=official_url, title=title, discovery_url=SOURCE_URL,
             discovery_method="manual", discovered_at=datetime.now(timezone.utc).isoformat()))
