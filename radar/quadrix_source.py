"""Nova fonte oficial de confirmação: Quadrix (https://www.quadrix.org.br).

Banca organizadora com páginas de concurso **server-rendered** e documentos públicos
(edital, retificações, anexos, comunicados) em ``anexos-r2.selecao.net.br``. O parsing
é puro (testável); a rede é injetável. Somente páginas/arquivos públicos.

Escolhida na Fase 12 após auditoria das bancas (ver
``docs/superpowers/specs/2026-10-16-official-confirmation-expansion-design.md``):
Cebraspe só é alcançável por API interna não documentada ou navegador; Vunesp/AOCP/
Consulplan/IBFC bloqueiam acesso automatizado (403); Cesgranrio/IDECAN não expõem os
documentos publicamente.
"""

from __future__ import annotations

import html as _html
import re
import urllib.request
from datetime import datetime, timezone

QUADRIX_SOURCE_ID = "quadrix"
QUADRIX_SOURCE_NAME = "Quadrix"
QUADRIX_AGENCY = "Instituto Quadrix"
QUADRIX_HOST = "www.quadrix.org.br"
QUADRIX_CATALOG_URL = "https://www.quadrix.org.br/"
# Host/rota autorizados no download (ver document_discovery._AUTHORIZED_SOURCES).
QUADRIX_ANEXOS_HOST = "anexos-r2.selecao.net.br"
QUADRIX_ANEXOS_PREFIX = "/uploads/"

# Páginas de listagem por situação (a raiz já traz "Inscrições Abertas").
CATALOG_STATUSES = ("abertos", "1", "6")
ALL_CATALOG = "todos"
# Catálogo completo em uma única requisição (a listagem aceita page-size grande).
CATALOG_PAGE_SIZE = 1000

MAX_BYTES = 4 * 1024 * 1024
TIMEOUT_SECONDS = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_ITEM_RE = re.compile(r'<li class="item[^"]*">(.*?)</li>', re.S)
_H3_RE = re.compile(r'<h3>\s*<a href="/informacoes/(\d+)/"[^>]*>(.*?)</a>\s*</h3>', re.S)
_TIPO_RE = re.compile(r'<p class="tipo">(.*?)</p>', re.S)
_EDITAL_RE = re.compile(r'<p class="edital">(.*?)</p>', re.S)
_INSC_RE = re.compile(r"Inscri[^<]*de\s*<b>(.*?)</b>\s*a\s*<b>(.*?)</b>", re.S)
_H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S)
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
# Tabela de cargos da página: Cód. | Vaga | Escolaridade | Taxa de Inscrição.
_CARGO_TABLE_RE = re.compile(
    r"<th[^>]*>\s*C[óo]d\.?\s*</th>.*?<tbody>(.*?)</tbody>", re.I | re.S)
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_LI_PDF_RE = re.compile(r'<li class="pdf"[^>]*>(.*?)</li>', re.S)
_ASTV_RE = re.compile(r'data-astv="([^"]*)"')
_ANEXO_HREF_RE = re.compile(
    r'href="(https://anexos-r2\.selecao\.net\.br/[^"]+\.(?:pdf|zip))"', re.I)
_DATE_RE = re.compile(r"<span>\s*(\d{2}/\d{2}/\d{4})\s*</span>")
_TAGS_RE = re.compile(r"<[^>]+>")


def _text(value: str) -> str:
    return " ".join(_html.unescape(_TAGS_RE.sub(" ", value or "")).split())


def catalog_url(status: str = "abertos", page: int = 1, page_size: int = 10) -> str:
    """URL da listagem. ``todos`` usa o catálogo completo; demais usam /index/<situação>/."""
    if status == "abertos":
        base = QUADRIX_CATALOG_URL
    else:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", status or ""):
            raise ValueError("situação de catálogo inválida")
        base = f"{QUADRIX_CATALOG_URL}index/{status}/"
    if page < 1 or page_size < 1:
        raise ValueError("paginação inválida")
    return f"{base}?&ord=&dir=&pg={page}&q=&pp={page_size}"


def detail_url(contest_id: str) -> str:
    contest_id = str(contest_id or "").strip()
    if not re.fullmatch(r"\d+", contest_id):
        raise ValueError("id de concurso inválido")
    return f"{QUADRIX_CATALOG_URL}informacoes/{contest_id}/"


# Tipos documentais finos: regras compartilhadas em radar.document_types.
from radar.document_types import classify as _classify_type, kind_for as _kind_for


def classify_document(title: str) -> str:
    """Classificação fina pelo título. Nunca trata todo PDF como edital."""
    return _classify_type(_text(title))


def kind_for(document_type: str) -> str:
    """Bucket de armazenamento (`kind`) a partir do tipo fino."""
    return _kind_for(document_type)


def parse_catalog(html: str) -> list[dict]:
    """Entradas da listagem: ``{id, url, title, tipo, edital, inscricao_inicio, inscricao_fim}``."""
    if not isinstance(html, str) or not html.strip():
        raise ValueError("catálogo vazio")
    entries = []
    seen = set()
    for block in _ITEM_RE.findall(html):
        match = _H3_RE.search(block)
        if match is None:
            continue
        contest_id, raw_title = match.group(1), match.group(2)
        if contest_id in seen:
            continue
        title = _text(raw_title)
        if not title:
            continue
        seen.add(contest_id)
        tipo_match = _TIPO_RE.search(block)
        edital_match = _EDITAL_RE.search(block)
        insc_match = _INSC_RE.search(block)
        entries.append({
            "id": contest_id,
            "url": detail_url(contest_id),
            "title": title,
            "tipo": _text(tipo_match.group(1)) if tipo_match else None,
            "edital": _text(edital_match.group(1)) if edital_match else None,
            "inscricao_inicio": _text(insc_match.group(1)) if insc_match else None,
            "inscricao_fim": _text(insc_match.group(2)) if insc_match else None,
        })
    return entries


def parse_detail(html: str) -> dict:
    """Página do concurso: ``{title, documents: [{title, url, date, document_type, kind}]}``."""
    if not isinstance(html, str) or not html.strip():
        raise ValueError("página de detalhe vazia")
    heading = _H2_RE.search(html)
    title = _text(heading.group(1)) if heading else ""
    if not title:
        page_title = _TITLE_RE.search(html)
        title = _text(page_title.group(1)).split(" | ")[0] if page_title else ""

    documents = []
    seen = set()
    for block in _LI_PDF_RE.findall(html):
        href = _ANEXO_HREF_RE.search(block)
        if href is None:
            continue
        url = href.group(1)
        if url in seen:
            continue
        astv = _ASTV_RE.search(block)
        if astv:
            label = _text(astv.group(1))
        else:
            label = _text(block)
        if not label:
            continue
        date_match = _DATE_RE.search(block)
        document_type = classify_document(label)
        seen.add(url)
        documents.append({
            "title": label,
            "url": url,
            "date": date_match.group(1) if date_match else None,
            "document_type": document_type,
            "kind": kind_for(document_type),
        })
    return {"title": title, "documents": documents}


def parse_cargo_table(html: str) -> list[dict]:
    """Tabela de cargos da página oficial: ``[{code, name, education}]``.

    Estrutura observada (estável): ``Cód. | Vaga | Escolaridade | Taxa de Inscrição``.
    Devolve lista vazia quando a página não tem tabela de cargos.
    """
    if not isinstance(html, str) or not html.strip():
        return []
    table = _CARGO_TABLE_RE.search(html)
    if table is None:
        return []
    roles = []
    seen = set()
    for row in _ROW_RE.findall(table.group(1)):
        cells = _CELL_RE.findall(row)
        if len(cells) < 3:
            continue
        code = _text(cells[0])
        name = _text(cells[1])
        education = _text(cells[2])
        if not code.isdigit() or not name or code in seen:
            continue
        seen.add(code)
        roles.append({"code": code, "name": name, "education": education or None})
    return roles


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
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"})
    if opener is None:
        opener = urllib.request.urlopen
    with opener(request, timeout=TIMEOUT_SECONDS) as response:
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("página excede o limite de bytes")
    return _decode(body)


def fetch_catalog(status: str = "abertos", page: int = 1, page_size: int = 10, opener=None) -> str:
    return _fetch(catalog_url(status, page, page_size), opener=opener)


def fetch_detail(contest_id: str, opener=None) -> str:
    return _fetch(detail_url(contest_id), opener=opener)


def to_candidate(document: dict, entry: dict, observation_id: str, discovered_at: str) -> dict:
    """Candidato documental para ``register_document`` (um arquivo publicado pela banca)."""
    return {
        "observation_id": observation_id,
        "kind": document.get("kind") or kind_for(document.get("document_type")),
        "document_type": document.get("document_type"),
        "official_url": document["url"],
        "title": document["title"],
        "discovery_url": entry["url"],
        "discovery_method": "automatico",
        "discovered_at": discovered_at,
        "issuer": QUADRIX_AGENCY,
        "published_at": None,
        "source_identifier": f"quadrix:{entry['id']}:{document['title']}",
    }


def _page_candidate(entry: dict, detail: dict, observation_id: str, discovered_at: str) -> dict:
    """Página do concurso como evidência (proveniência + marcador de consulta)."""
    parts = [f"<h1>{_html.escape(detail['title'] or entry['title'])}</h1>"]
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
        "issuer": QUADRIX_AGENCY,
        "published_at": None,
        "source_identifier": f"quadrix:{entry['id']}:pagina",
        "inline_content": "".join(parts).encode("utf-8"),
        "inline_content_type": "text/html",
    }


def _catalog_entries(catalog_html, catalog_fetcher, statuses, page_size) -> list[dict]:
    """Une as entradas das listagens informadas, sem duplicar por id."""
    pages = [catalog_html]
    for status in statuses:
        try:
            pages.append(catalog_fetcher(status, 1, page_size))
        except Exception:
            continue
    entries = []
    seen = set()
    for index, page_html in enumerate(pages):
        try:
            page_entries = parse_catalog(page_html)
        except ValueError:
            if index == 0:
                raise
            continue
        if not page_entries and index == 0:
            raise ValueError("catálogo sem entradas")
        for entry in page_entries:
            if entry["id"] in seen:
                continue
            seen.add(entry["id"])
            entries.append(entry)
    return entries


def discover(db_path, catalog_html: str, *, catalog_fetcher=fetch_catalog, detail_fetcher=fetch_detail,
             statuses=CATALOG_STATUSES, page_size=10, max_new_details: int = 5,
             max_refresh_details: int = 3, discovered_at: str | None = None) -> dict:
    """Descobre concursos e documentos do Quadrix, com identidade por certame.

    - Concursos **novos**: consulta a página de detalhe (até ``max_new_details`` por ciclo)
      e emite a página + os documentos publicados.
    - Concursos **conhecidos**: reconsulta as páginas mais antigas por ``last_checked_at``
      (até ``max_refresh_details``), para captar retificações/anexos novos. A idempotência
      por URL descarta os já registrados; nada é apagado.

    Um catálogo sem entradas na primeira página é tratado como falha, não como "sem
    novidades".
    """
    from contextlib import closing
    from radar.document_store import connect_documents, ensure_observation

    discovered_at = discovered_at or datetime.now(timezone.utc).isoformat()
    entries = _catalog_entries(catalog_html, catalog_fetcher, statuses, page_size)

    # Estado conhecido em uma única consulta (evita uma conexão por entrada).
    with closing(connect_documents(db_path)) as conn:
        known = {}
        for competition_id, observation_id, document_id, last_checked in conn.execute(
                """SELECT o.competition_id, o.id, d.id, d.last_checked_at
                FROM observacoes_concurso o
                LEFT JOIN documentos d ON d.observation_id=o.id AND d.official_url=o.source_url
                WHERE o.competition_id LIKE 'quadrix-%'"""):
            known[competition_id] = (observation_id, document_id, last_checked)

    candidates = []
    new_fetched = 0
    refresh_fetched = 0
    pending_refresh = []
    for entry in entries:
        competition_id = f"quadrix-{entry['id']}"
        state = known.get(competition_id)
        if state is not None and state[1] is not None:
            pending_refresh.append((state[2] or "", entry, state))
            continue
        if new_fetched >= max_new_details:
            continue
        try:
            detail = parse_detail(detail_fetcher(entry["id"]))
        except Exception:
            continue
        new_fetched += 1
        observation_id = ensure_observation(db_path, entry["url"], competition_id)
        candidates.append(_page_candidate(entry, detail, observation_id, discovered_at))
        for document in detail["documents"]:
            candidates.append(to_candidate(document, entry, observation_id, discovered_at))

    # Revisão incremental: as páginas conhecidas mais antigas primeiro.
    pending_refresh.sort(key=lambda item: (item[0], item[1]["id"]))
    for _, entry, state in pending_refresh:
        if refresh_fetched >= max_refresh_details:
            break
        try:
            detail = parse_detail(detail_fetcher(entry["id"]))
        except Exception:
            continue
        refresh_fetched += 1
        observation_id, document_id, _ = state
        with closing(connect_documents(db_path)) as conn, conn:
            conn.execute("UPDATE documentos SET last_checked_at=? WHERE id=?",
                         (discovered_at, document_id))
        for document in detail["documents"]:
            candidates.append(to_candidate(document, entry, observation_id, discovered_at))
    return {
        "candidates": candidates,
        "summary": {"catalog_entries": len(entries), "new_details": new_fetched,
                    "refresh_details": refresh_fetched},
    }


def quadrix_source(*, catalog_fetcher=fetch_catalog, detail_fetcher=fetch_detail,
                   statuses=CATALOG_STATUSES, page_size=10,
                   max_new_details: int = 5, max_refresh_details: int = 3) -> dict:
    """Descritor da fonte Quadrix para o monitoramento (multi-concurso)."""
    return {
        "id": QUADRIX_SOURCE_ID,
        "source_url": QUADRIX_CATALOG_URL,
        "name": QUADRIX_SOURCE_NAME,
        "agency": QUADRIX_AGENCY,
        "multi_contest": True,
        "download_new_only": True,
        "fetch": lambda: catalog_fetcher("abertos", 1, page_size),
        "discover": lambda db_path, html: discover(
            db_path, html, catalog_fetcher=catalog_fetcher, detail_fetcher=detail_fetcher,
            statuses=statuses, page_size=page_size, max_new_details=max_new_details,
            max_refresh_details=max_refresh_details),
    }
