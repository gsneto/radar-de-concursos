"""Terceira fonte oficial: FGV Conhecimento (https://conhecimento.fgv.br/concursos).

Descobre concursos no catálogo público e recupera os documentos publicados nas
páginas individuais (edital, retificações, resultados). Somente páginas públicas;
nenhuma área autenticada. O parsing é puro (testável); a rede é injetável.
"""

from __future__ import annotations

import html as _html
import re
import urllib.request
from datetime import datetime, timezone

from radar.document_types import classify as _classify_type, kind_for as _kind_for

FGV_SOURCE_ID = "fgv-conhecimento"
FGV_SOURCE_NAME = "FGV Conhecimento"
FGV_AGENCY = "Fundação Getulio Vargas (FGV Conhecimento)"
FGV_HOST = "conhecimento.fgv.br"
FGV_CATALOG_URL = "https://conhecimento.fgv.br/concursos"
FGV_DETAIL_BASE = "https://conhecimento.fgv.br"
# Host/rotas autorizados no download (ver document_discovery._AUTHORIZED_SOURCES).
FGV_DOCUMENT_PREFIX = "/sites/default/files/concursos/"

MAX_BYTES = 4 * 1024 * 1024
TIMEOUT_SECONDS = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_SLUG_RE = re.compile(r'href="(?:https://conhecimento\.fgv\.br)?(/concursos/[A-Za-z0-9._-]+)"[^>]*>(.*?)</a>', re.S)
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
_STATUS_RE = re.compile(
    r'field--name-field-concurso-status.*?<small[^>]*>(.*?)</small>', re.S)
_PARAGRAPH_SPLIT = re.compile(r'class="paragraph paragraph--type--texto-data')
_TIME_RE = re.compile(r'<time[^>]*datetime="([^"]+)"', re.I)
_LINK_RE = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_TAGS_RE = re.compile(r"<[^>]+>")


def _text(value: str) -> str:
    return " ".join(_html.unescape(_TAGS_RE.sub(" ", value)).split())


def catalog_url(page: int = 0) -> str:
    if not isinstance(page, int) or page < 0:
        raise ValueError("página inválida")
    return FGV_CATALOG_URL if page == 0 else f"{FGV_CATALOG_URL}?page={page}"


def detail_url(slug: str) -> str:
    """URL canônica da página individual a partir do slug (sem o prefixo /concursos/)."""
    slug = (slug or "").strip()
    if slug.startswith("concursos/"):
        slug = slug[len("concursos/"):]
    if not re.fullmatch(r"[A-Za-z0-9._-]+", slug):
        raise ValueError("slug de concurso inválido")
    return f"{FGV_DETAIL_BASE}/concursos/{slug}"


def parse_catalog(html: str) -> list[dict]:
    """Entradas do catálogo: `{slug, url, title}` (só páginas sob /concursos/)."""
    if not isinstance(html, str) or not html.strip():
        raise ValueError("catálogo vazio")
    entries = []
    seen = set()
    for match in _SLUG_RE.finditer(html):
        path, raw_title = match.group(1), match.group(2)
        slug = path[len("/concursos/"):]
        if not slug or slug in seen:
            continue
        title = _text(raw_title)
        if not title:
            continue
        seen.add(slug)
        entries.append({"slug": slug, "url": FGV_DETAIL_BASE + path, "title": title})
    return entries


def classify_document(title: str) -> str:
    """Bucket de armazenamento (`kind`) pelo título. "Edital retificado" continua edital."""
    return _kind_for(_classify_type(_TAGS_RE.sub(" ", title or "")))


def document_type(title: str) -> str:
    """Tipo documental fino pelo título (edital_abertura, retificacao, anexo, ...)."""
    return _classify_type(_TAGS_RE.sub(" ", title or ""))


def parse_detail(html: str) -> dict:
    """Página individual: `{title, status, documents: [{title, url, date}]}`."""
    if not isinstance(html, str) or not html.strip():
        raise ValueError("página de detalhe vazia")
    h1 = _H1_RE.search(html)
    title = _text(h1.group(1)) if h1 else ""
    if not title:
        page_title = _TITLE_RE.search(html)
        title = _text(page_title.group(1)).split(" | ")[0] if page_title else ""
    status_match = _STATUS_RE.search(html)
    status = _text(status_match.group(1)) if status_match else None

    documents = []
    seen = set()
    segments = _PARAGRAPH_SPLIT.split(html)[1:]
    for segment in segments:
        link = _LINK_RE.search(segment)
        if link is None:
            continue
        url, raw_label = link.group(1), link.group(2)
        label = _text(raw_label)
        if not label or not url.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip")):
            continue
        time_match = _TIME_RE.search(segment)
        date = time_match.group(1)[:10] if time_match else None
        if url in seen:
            continue
        seen.add(url)
        documents.append({"title": label, "url": url, "date": date,
                          "document_type": document_type(label)})
    return {"title": title, "status": status, "documents": documents}


def _decode(body: bytes) -> str:
    if not isinstance(body, (bytes, bytearray)) or not body:
        raise ValueError("corpo vazio")
    for encoding in ("utf-8", "cp1252"):
        try:
            return bytes(body).decode(encoding)
        except UnicodeDecodeError:
            continue
    return bytes(body).decode("utf-8", "replace")


def _fetch(url: str, opener=None) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"})
    if opener is None:
        opener = urllib.request.urlopen
    with opener(request, timeout=TIMEOUT_SECONDS) as response:
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("página excede o limite de bytes")
    return _decode(body)


def fetch_catalog(page: int = 0, opener=None) -> str:
    return _fetch(catalog_url(page), opener=opener)


def fetch_detail(slug: str, opener=None) -> str:
    return _fetch(detail_url(slug), opener=opener)


def to_candidate(document: dict, entry: dict, observation_id: str, discovered_at: str) -> dict:
    """Candidato documental para `register_document` (um arquivo publicado pela FGV)."""
    url = document["url"]
    if url.startswith("/"):
        url = FGV_DETAIL_BASE + url
    doc_type = document.get("document_type") or document_type(document["title"])
    return {
        "observation_id": observation_id,
        "kind": _kind_for(doc_type),
        "document_type": doc_type,
        "official_url": url,
        "title": document["title"],
        "discovery_url": entry["url"],
        "discovery_method": "automatico",
        "discovered_at": discovered_at,
        "issuer": FGV_AGENCY,
        "published_at": document.get("date"),
        "source_identifier": f"{entry['slug']}:{document['title']}",
    }


def _page_candidate(entry: dict, detail: dict, observation_id: str, discovered_at: str) -> dict:
    """Candidato da própria página do concurso (proveniência + marcador de consulta).

    Registrar a página como documento (`outro`, com o conteúdo embutido) evita
    reconsultar o detalhe de concursos já vistos, sem schema novo; se a consulta
    falhar, nenhum documento é gravado e a página é tentada de novo no próximo ciclo.
    """
    parts = [f"<h1>{_html.escape(detail['title'] or entry['title'])}</h1>"]
    if detail.get("status"):
        parts.append(f"<p>{_html.escape(detail['status'])}</p>")
    for document in detail.get("documents", []):
        parts.append(f"<p>{_html.escape(document['title'])}"
                     + (f" — {_html.escape(document['date'])}" if document.get("date") else "")
                     + "</p>")
    return {
        "observation_id": observation_id,
        "kind": "outro",
        "document_type": "pagina_concurso",
        "official_url": entry["url"],
        "title": detail["title"] or entry["title"],
        "discovery_url": entry["url"],
        "discovery_method": "automatico",
        "discovered_at": discovered_at,
        "issuer": FGV_AGENCY,
        "published_at": None,
        "source_identifier": f"{entry['slug']}:pagina",
        "inline_content": "".join(parts).encode("utf-8"),
        "inline_content_type": "text/html",
    }


def discover(db_path, catalog_html: str, *, catalog_fetcher=fetch_catalog, detail_fetcher=fetch_detail,
             max_pages: int = 3, max_new_details: int = 3, max_refresh_details: int = 0,
             discovered_at: str | None = None) -> list[dict]:
    """Descobre concursos e documentos da FGV, com identidade por concurso.

    Percorre o catálogo (até o fim real ou `max_pages`), garante a observação de cada
    concurso e consulta a página de detalhe de **concursos novos** (até `max_new_details`
    por ciclo). Com `max_refresh_details > 0`, **reconsulta** as páginas conhecidas mais
    antigas por `last_checked_at` para captar retificações/anexos publicados depois — a
    idempotência por URL descarta os já registrados e nada é apagado. Um catálogo sem
    entradas na primeira página é tratado como falha (não como "sem novidades").
    """
    from contextlib import closing
    from radar.document_store import connect_documents, ensure_observation

    discovered_at = discovered_at or datetime.now(timezone.utc).isoformat()

    pages_html = [catalog_html]
    for page in range(1, max_pages):
        try:
            pages_html.append(catalog_fetcher(page))
        except Exception:
            break

    entries = []
    seen = set()
    for index, page_html in enumerate(pages_html):
        try:
            page_entries = parse_catalog(page_html)
        except ValueError:
            if index == 0:
                raise  # catálogo inválido na primeira página: falha, não "sem novidades"
            break
        if not page_entries:
            if index == 0:
                raise ValueError("catálogo sem entradas")
            break  # fim da paginação real
        for entry in page_entries:
            if entry["slug"] in seen:
                continue
            seen.add(entry["slug"])
            entries.append(entry)

    candidates = []
    details_fetched = 0
    refresh_fetched = 0
    pending_refresh = []
    for entry in entries:
        observation_id = ensure_observation(db_path, entry["url"], entry["slug"])
        with closing(connect_documents(db_path)) as conn:
            known = conn.execute(
                "SELECT count(*), coalesce(max(last_checked_at),'') FROM documentos WHERE observation_id=?",
                (observation_id,)).fetchone()
        if known[0]:
            pending_refresh.append((known[1], entry, observation_id))
            continue
        if details_fetched >= max_new_details:
            continue
        try:
            detail_html = detail_fetcher(entry["slug"])
        except Exception:
            continue
        details_fetched += 1
        detail = parse_detail(detail_html)
        candidates.append(_page_candidate(entry, detail, observation_id, discovered_at))
        for document in detail["documents"]:
            candidates.append(to_candidate(document, entry, observation_id, discovered_at))

    # Revisão incremental: as páginas conhecidas mais antigas primeiro.
    pending_refresh.sort(key=lambda item: (item[0], item[1]["slug"]))
    for _, entry, observation_id in pending_refresh:
        if refresh_fetched >= max_refresh_details:
            break
        try:
            detail_html = detail_fetcher(entry["slug"])
        except Exception:
            continue
        refresh_fetched += 1
        detail = parse_detail(detail_html)
        with closing(connect_documents(db_path)) as conn, conn:
            conn.execute(
                "UPDATE documentos SET last_checked_at=? WHERE observation_id=? AND official_url=?",
                (discovered_at, observation_id, entry["url"]))
        for document in detail["documents"]:
            candidates.append(to_candidate(document, entry, observation_id, discovered_at))
    return candidates


def fgv_source(*, catalog_fetcher=fetch_catalog, detail_fetcher=fetch_detail,
               max_pages: int = 3, max_new_details: int = 3, max_refresh_details: int = 2) -> dict:
    """Descritor da fonte FGV para o monitoramento (multi-concurso)."""
    return {
        "id": FGV_SOURCE_ID,
        "source_url": FGV_CATALOG_URL,
        "name": FGV_SOURCE_NAME,
        "agency": FGV_AGENCY,
        "multi_contest": True,
        "download_new_only": True,
        "fetch": lambda: catalog_fetcher(0),
        "discover": lambda db_path, html: discover(
            db_path, html, catalog_fetcher=catalog_fetcher, detail_fetcher=detail_fetcher,
            max_pages=max_pages, max_new_details=max_new_details,
            max_refresh_details=max_refresh_details),
    }
