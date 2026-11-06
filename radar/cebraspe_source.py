"""Quarta fonte oficial: Cebraspe (https://www.cebraspe.org.br/concursos/).

Descobre certames no portal oficial do Cebraspe e recupera os editais, retificações
e comunicados públicos associados a cada concurso.
Somente páginas e documentos públicos; nenhuma área restrita. O parsing é puro.
"""

from __future__ import annotations

import html as _html
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

from radar.document_types import classify as _classify_type, kind_for as _kind_for

CEBRASPE_SOURCE_ID = "cebraspe"
CEBRASPE_SOURCE_NAME = "Cebraspe"
CEBRASPE_AGENCY = "Centro Brasileiro de Pesquisa em Avaliação e Seleção e de Promoção de Eventos (Cebraspe)"
CEBRASPE_HOST = "www.cebraspe.org.br"
CEBRASPE_BASE = f"https://{CEBRASPE_HOST}"
CEBRASPE_CATALOG_URL = f"{CEBRASPE_BASE}/concursos/"

MAX_BYTES = 8 * 1024 * 1024
TIMEOUT_SECONDS = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Slugs reservados de páginas de navegação que não são certames
_RESERVED_SLUGS = {
    "", "concursos", "page", "em-andamento", "encerrados", "inscricoes-abertas",
    "futuros", "avaliacao", "eventos", "sobre", "contato",
}

_SLUG_LINK_RE = re.compile(
    r'<a\b[^>]*href=["\'](?:https?://(?:www\.)?cebraspe\.org\.br)?/concursos/([a-zA-Z0-9_\-]+)/?["\'][^>]*>(.*?)</a>',
    re.I | re.S,
)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
_STATUS_RE = re.compile(
    r'<(?:span|div|p)\b[^>]*class=["\'][^"\']*(?:status|situacao)[^"\']*["\'][^>]*>(.*?)</(?:span|div|p)>',
    re.I | re.S,
)
_DATE_BR_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
_DATE_ISO_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_TAGS_RE = re.compile(r"<[^>]+>")


def _clean_text(value: str) -> str:
    if not value:
        return ""
    return " ".join(_html.unescape(_TAGS_RE.sub(" ", value)).split())


def _to_iso_date(text: str) -> str | None:
    iso_match = _DATE_ISO_RE.search(text)
    if iso_match:
        return iso_match.group(1)
    br_match = _DATE_BR_RE.search(text)
    if br_match:
        d, m, y = br_match.groups()
        return f"{y}-{m}-{d}"
    return None


def catalog_url() -> str:
    return CEBRASPE_CATALOG_URL


def detail_url(slug: str) -> str:
    slug = (slug or "").strip().strip("/")
    if slug.startswith("concursos/"):
        slug = slug[len("concursos/"):]
    if not re.fullmatch(r"[a-zA-Z0-9_\-]+", slug):
        raise ValueError(f"slug inválido: {slug}")
    return f"{CEBRASPE_BASE}/concursos/{slug}"


def parse_catalog(html: str) -> list[dict]:
    """Extrai concursos do catálogo Cebraspe."""
    if not isinstance(html, str) or not html.strip():
        raise ValueError("catálogo vazio")
    entries: list[dict] = []
    seen: set[str] = set()

    for match in _SLUG_LINK_RE.finditer(html):
        slug, raw_label = match.group(1), match.group(2)
        slug_clean = slug.strip().lower()
        if not slug_clean or slug_clean in _RESERVED_SLUGS or slug_clean in seen:
            continue
        title = _clean_text(raw_label)
        if not title or len(title) < 3:
            continue
        seen.add(slug_clean)
        entries.append({
            "slug": slug,
            "url": f"{CEBRASPE_BASE}/concursos/{slug}",
            "title": title,
        })
    return entries


def parse_detail(html: str) -> dict:
    """Extrai dados de certame e documentos da página individual Cebraspe."""
    if not isinstance(html, str) or not html.strip():
        raise ValueError("página de detalhe vazia")

    h1_match = _H1_RE.search(html)
    title = _clean_text(h1_match.group(1)) if h1_match else ""
    if not title:
        title_match = _TITLE_RE.search(html)
        if title_match:
            title = _clean_text(title_match.group(1))
            if " - Cebraspe" in title:
                title = title.split(" - Cebraspe")[0].strip()

    status_match = _STATUS_RE.search(html)
    status = _clean_text(status_match.group(1)) if status_match else ""

    # Extração de documentos publicados (links para .pdf)
    documents = []
    seen_urls = set()

    # Procura blocos ou links diretos
    doc_link_re = re.compile(
        r'<a\b[^>]*href=["\']([^"\']+\.pdf(?:[^"\']*)?)["\'][^>]*>(.*?)</a>',
        re.I | re.S,
    )

    # Varre blocos de documento ou itens
    block_re = re.compile(
        r'<div\b[^>]*class=["\'][^"\']*(?:documento|item|card|linha|publicacao)[^"\']*["\'][^>]*>(.*?)</div>',
        re.I | re.S,
    )

    blocks = list(block_re.finditer(html))
    if blocks:
        for block in blocks:
            b_text = block.group(1)
            date_found = _to_iso_date(b_text)
            for d_match in doc_link_re.finditer(b_text):
                href, raw_name = d_match.group(1), d_match.group(2)
                full_url = urljoin(CEBRASPE_BASE, href)
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)
                doc_title = _clean_text(raw_name)
                documents.append({
                    "title": doc_title,
                    "url": full_url,
                    "date": date_found or datetime.now(timezone.utc).date().isoformat(),
                })

    # Se não encontrou via blocos, varre links .pdf diretamente
    if not documents:
        for d_match in doc_link_re.finditer(html):
            href, raw_name = d_match.group(1), d_match.group(2)
            full_url = urljoin(CEBRASPE_BASE, href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            doc_title = _clean_text(raw_name)
            documents.append({
                "title": doc_title,
                "url": full_url,
                "date": datetime.now(timezone.utc).date().isoformat(),
            })

    return {
        "title": title,
        "status": status,
        "documents": documents,
    }


def classify_document(title: str) -> str:
    """Classifica em edital, retificacao ou outro."""
    return _kind_for(_classify_type(_clean_text(title)))


def document_type(title: str) -> str:
    """Tipo documental fino."""
    return _classify_type(_clean_text(title))


def cebraspe_source(*, transport=None) -> dict:
    """Descritor para inclusão no monitoramento contínuo (radar.monitoring)."""
    return {
        "id": CEBRASPE_SOURCE_ID,
        "source_id": CEBRASPE_SOURCE_ID,
        "source_name": CEBRASPE_SOURCE_NAME,
        "source_url": CEBRASPE_CATALOG_URL,
        "multi_contest": True,
        "discover": lambda html, obs_id: [],  # Tratado por collector / document_discovery
    }
