"""Fonte oficial piloto: IBFC (Instituto Brasileiro de Formação e Capacitação).

Motivo da escolha (Fase 27, medido e não presumido):

- o catálogo e as páginas de detalhe são **HTML estático** (sem JavaScript), o que dispensa
  navegador para descobrir editais;
- publica o edital de abertura **e** as retificações/comunicados com data, o que permite
  enriquecer concursos existentes além de descobrir novos;
- os anexos ficam em ``anexos-r2.selecao.net.br/uploads/``, host que o projeto **já** autoriza
  para download (mesma plataforma usada pelo Quadrix) — nenhuma nova autorização de rede;
- ``robots.txt`` do host permite ``/index/`` e ``/informacoes/`` (só bloqueia /admin, /painel e
  /uploads do próprio site);
- a identidade externa é **por certame** (``ibfc-<id>``), não por catálogo: um concurso da
  banca nunca agrupa editais de órgãos diferentes.

A fonte não confirma nada sozinha: cada documento entra como versão + propostas ambíguas no
pipeline existente.
"""

from __future__ import annotations

import html as _html
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

from radar import quadrix_source
from radar.document_types import classify_document, kind_for

IBFC_SOURCE_ID = "ibfc"
IBFC_SOURCE_NAME = "IBFC (Instituto Brasileiro de Formação e Capacitação)"
IBFC_AGENCY = "IBFC"
IBFC_HOST = "concursos.ibfc.org.br"
IBFC_BASE = "https://" + IBFC_HOST
# Dois CDNs de anexos são usados pela plataforma:
# - ``anexos-r2.selecao.net.br``: sem restrição em robots.txt -> autorizado (já usado no
#   projeto pelo Quadrix);
# - ``anexos.cdn.selecao.net.br``: robots.txt com ``Disallow: /`` -> **não** baixamos o byte.
#   O documento é registrado com URL e metadados (o usuário chega ao original), mas sem versão.
IBFC_ANEXOS_HOST = "anexos-r2.selecao.net.br"
IBFC_ANEXOS_BLOCKED_HOST = "anexos.cdn.selecao.net.br"
IBFC_ANEXOS_PREFIX = "/uploads/"

# Estados do catálogo: "abertos" (inscrições abertas), "1" (em andamento), "3" (finalizado).
IBFC_CATALOG_STATUSES = ("1", "abertos")
MAX_BYTES = 8 * 1024 * 1024
TIMEOUT_SECONDS = 30
USER_AGENT = quadrix_source.USER_AGENT

_ENTRY_MARKER = re.compile(
    r'<a href="/informacoes/(\d+)/" class="lista-concurso">')
_CLIENT_RE = re.compile(r'<span class="texto_cliente"[^>]*>(.*?)</span>', re.S)
_EDITAL_RE = re.compile(r"Edital\s*n[ºo°]\s*<b>([^<]+)</b>", re.I)
_INSC_RE = re.compile(
    r"Inscri[^<]*de\s*<b>([^<]+)</b>\s*a\s*<b>([^<]+)</b>", re.S)
_OPEN_STATUS = re.compile(r'class="inscricoesabertas"')
_H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S)
_PDF_BLOCK_RE = re.compile(r'<li class="pdf"[^>]*>(.*?)</li>', re.S)
_ANEXO_HREF_RE = re.compile(
    r'href="(https://anexos(?:-r2|\.cdn)\.selecao\.net\.br/uploads/[^"]+\.(?:pdf|zip))"', re.I)
_ANCHOR_LABEL_RE = re.compile(r"<a\b[^>]*>(.*?)</a>", re.S)
_DATE_RE = re.compile(r"<span>\s*(\d{2}/\d{2}/\d{4})\s*</span>")
_TAGS_RE = re.compile(r"<[^>]+>")


def _text(value: str) -> str:
    """Texto limpo: sem tags e com entidades HTML resolvidas (``&ccedil;`` → ``ç``)."""
    return " ".join(_html.unescape(_TAGS_RE.sub(" ", value or "")).split())


def _decode(body: bytes) -> str:
    """Páginas declaram ISO-8859-1, mas parte do conteúdo é UTF-8: tenta UTF-8 primeiro."""
    if not isinstance(body, (bytes, bytearray)) or not body:
        raise ValueError("corpo vazio")
    for encoding in ("utf-8", "cp1252"):
        try:
            return bytes(body).decode(encoding)
        except UnicodeDecodeError:
            continue
    return bytes(body).decode("utf-8", "replace")


def catalog_url(status: str = "1") -> str:
    if status not in ("abertos", "1", "3"):
        raise ValueError("estado de catálogo inválido")
    return f"{IBFC_BASE}/index/{status}"


def detail_url(contest_id: str) -> str:
    if not isinstance(contest_id, str) or not contest_id.isdigit():
        raise ValueError("identificador de concurso IBFC inválido")
    return f"{IBFC_BASE}/informacoes/{contest_id}/"


def competition_id(contest_id: str) -> str:
    """Identidade externa estável **por certame** (nunca por catálogo/banca)."""
    if not isinstance(contest_id, str) or not contest_id.isdigit():
        raise ValueError("identificador de concurso IBFC inválido")
    return f"ibfc-{contest_id}"


def parse_catalog(html: str) -> list[dict]:
    """Entradas do catálogo: ``{id, url, title, edital, inscricao_inicio, inscricao_fim}``."""
    if not isinstance(html, str) or not html.strip():
        raise ValueError("catálogo vazio")
    marks = list(_ENTRY_MARKER.finditer(html))
    entries, seen = [], set()
    for index, mark in enumerate(marks):
        contest_id = mark.group(1)
        if contest_id in seen:
            continue
        end = marks[index + 1].start() if index + 1 < len(marks) else len(html)
        # Entidades resolvidas antes das regexes: a página real mistura ``nº`` e ``n&ordm;``.
        block = _html.unescape(html[mark.end():end])
        client = _CLIENT_RE.search(block)
        title = _text(client.group(1)) if client else ""
        if not title:
            continue
        seen.add(contest_id)
        edital = _EDITAL_RE.search(block)
        insc = _INSC_RE.search(block)
        entries.append({
            "id": contest_id,
            "url": detail_url(contest_id),
            "title": title,
            "edital": _text(edital.group(1)) if edital else None,
            "inscricao_inicio": _text(insc.group(1)) if insc else None,
            "inscricao_fim": _text(insc.group(2)) if insc else None,
            "inscricoes_abertas": bool(_OPEN_STATUS.search(block)),
        })
    return entries


def parse_detail(html: str) -> dict:
    """Página do concurso: ``{title, documents: [{title, url, date, document_type, kind}]}``."""
    if not isinstance(html, str) or not html.strip():
        raise ValueError("página de detalhe vazia")
    title = ""
    for raw in _H2_RE.findall(html):
        candidate = _text(raw)
        if candidate and candidate.lower() != "concursos":
            title = candidate
            break

    documents, seen = [], set()
    for block in _PDF_BLOCK_RE.findall(html):
        href = _ANEXO_HREF_RE.search(block)
        if href is None:
            continue
        url = href.group(1)
        if url in seen:
            continue
        anchor = _ANCHOR_LABEL_RE.search(block)
        raw_label = anchor.group(1) if anchor else block
        # O rótulo do anexo é o texto do link SEM o <span> da data.
        raw_label = re.split(r"<span\b", raw_label, maxsplit=1)[0]
        label = _text(raw_label)
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


def _iso_date(value: str | None) -> str | None:
    if not value:
        return None
    match = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", value.strip())
    if match is None:
        return None
    return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"


def _fetch(url: str, opener=None) -> str:
    import urllib.request

    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"})
    if opener is None:
        opener = urllib.request.urlopen
    with opener(request, timeout=TIMEOUT_SECONDS) as response:
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("página excede o limite de bytes")
    return _decode(body)


def fetch_catalog(status: str = "1", opener=None) -> str:
    return _fetch(catalog_url(status), opener=opener)


def fetch_detail(contest_id: str, opener=None) -> str:
    return _fetch(detail_url(contest_id), opener=opener)


def _page_candidate(entry: dict, detail: dict, observation_id: str,
                    discovered_at: str) -> dict:
    """Página oficial do certame na banca (não é edital; âncora de identidade).

    O conteúdo é sintetizado a partir do detalhe já consultado e gravado como versão
    embutida: a página não é rebaixada (o host do site não é autorizado para download) e o
    ciclo não registra falha falsa.
    """
    parts = [f"<h1>{_html.escape(detail.get('title') or entry['title'])}</h1>"]
    if entry.get("edital"):
        parts.append(f"<p>Edital nº {_html.escape(str(entry['edital']))}</p>")
    for document in detail.get("documents", []):
        suffix = f" — {_html.escape(document['date'])}" if document.get("date") else ""
        parts.append(f"<p>{_html.escape(document['title'])}{suffix}</p>")
    return {
        "observation_id": observation_id,
        "kind": "outro",
        "official_url": entry["url"],
        "title": detail.get("title") or entry["title"],
        "discovery_url": entry["url"],
        "discovery_method": "automatico",
        "discovered_at": discovered_at,
        "issuer": IBFC_AGENCY,
        "published_at": _iso_date(entry.get("inscricao_inicio")),
        "source_identifier": competition_id(entry["id"]),
        "document_type": "pagina_banca",
        "inline_content": "".join(parts).encode("utf-8"),
        "inline_content_type": "text/html",
    }


def to_candidate(document: dict, entry: dict, observation_id: str,
                 discovered_at: str, *, attempt_blocked_hosts=()) -> dict:
    """Documento publicado (edital/retificação/comunicado) como candidato documental.

    ``attempt_blocked_hosts`` é a configuração **explícita** deste conector: hosts cujo
    ``robots.txt`` restringe a coleta, mas cuja URL pública foi descoberta e para os quais o
    operador autorizou tentativa de download normal. Sem ela, o comportamento é o anterior
    (registra metadados, não baixa). Nada aqui contorna autenticação, CAPTCHA ou bloqueio.
    """
    slug = document["url"].rsplit("/", 1)[-1]
    host = urlsplit(document["url"]).hostname or ""
    extra = tuple(attempt_blocked_hosts)
    on_extra = host in extra
    fetch_allowed = IBFC_ANEXOS_HOST in document["url"] or on_extra
    return {
        "observation_id": observation_id,
        "kind": document["kind"],
        "fetch_allowed": fetch_allowed,
        "fetch_blocked_reason": None if fetch_allowed else "robots_disallow_anexos_cdn",
        "download_allowed_hosts": list(extra) if on_extra else None,
        "robots_policy": None if fetch_allowed else "robots_disallow_anexos_cdn",
        "official_url": document["url"],
        "title": document["title"],
        "discovery_url": entry["url"],
        "discovery_method": "automatico",
        "discovered_at": discovered_at,
        "issuer": IBFC_AGENCY,
        "published_at": _iso_date(document.get("date")),
        "source_identifier": f"{competition_id(entry['id'])}:{slug}",
        "document_type": document["document_type"],
    }


def discover(db_path, catalog_html: str, *, catalog_fetcher=fetch_catalog,
             detail_fetcher=fetch_detail, statuses=IBFC_CATALOG_STATUSES,
             max_new_details: int = 5, max_refresh_details: int = 2,
             discovered_at: str | None = None, attempt_blocked_hosts=()) -> dict:
    """Descobre concursos e documentos do IBFC com identidade **por certame**.

    - certames novos: consulta a página de detalhe (até ``max_new_details``) e emite a página
      oficial + todos os documentos publicados;
    - certames conhecidos: reconsulta os mais antigos (até ``max_refresh_details``) para
      captar retificações; a idempotência por URL descarta os já registrados.
    """
    from contextlib import closing

    from radar.document_store import connect_documents, ensure_observation

    discovered_at = discovered_at or datetime.now(timezone.utc).isoformat()
    entries, seen, errors_catalog = [], set(), []
    for status in statuses:
        try:
            if status == statuses[0] and catalog_html:
                # O ciclo já buscou este catálogo: não repetir a requisição.
                page_html = catalog_html
            else:
                page_html = catalog_fetcher(status)
            parsed = parse_catalog(page_html)
        except Exception as error:
            errors_catalog.append({"status": status, "error": type(error).__name__})
            continue
        for entry in parsed:
            if entry["id"] in seen:
                continue
            seen.add(entry["id"])
            entries.append(entry)

    with closing(connect_documents(db_path)) as conn:
        known = {}
        for cid, observation_id, document_id, last_checked in conn.execute(
                """SELECT o.competition_id, o.id, d.id, d.last_checked_at
                   FROM observacoes_concurso o
                   LEFT JOIN documentos d ON d.observation_id=o.id
                        AND d.official_url=o.source_url
                   WHERE o.competition_id LIKE 'ibfc-%'"""):
            known[cid] = (observation_id, document_id, last_checked)

    candidates, new_fetched, refresh_fetched, pending_refresh = [], 0, 0, []
    errors = []
    for entry in entries:
        cid = competition_id(entry["id"])
        state = known.get(cid)
        if state is not None and state[1] is not None:
            pending_refresh.append((state[2] or "", entry, state))
            continue
        if new_fetched >= max_new_details:
            continue
        try:
            detail = parse_detail(detail_fetcher(entry["id"]))
        except Exception as error:
            errors.append({"contest": entry["id"], "error": type(error).__name__})
            continue
        new_fetched += 1
        observation_id = ensure_observation(db_path, entry["url"], cid)
        candidates.append(_page_candidate(entry, detail, observation_id, discovered_at))
        for document in detail["documents"]:
            candidates.append(to_candidate(document, entry, observation_id, discovered_at,
                                           attempt_blocked_hosts=attempt_blocked_hosts))

    pending_refresh.sort(key=lambda item: (item[0], item[1]["id"]))
    for _, entry, state in pending_refresh:
        if refresh_fetched >= max_refresh_details:
            break
        try:
            detail = parse_detail(detail_fetcher(entry["id"]))
        except Exception as error:
            errors.append({"contest": entry["id"], "error": type(error).__name__})
            continue
        refresh_fetched += 1
        observation_id, page_document_id, _ = state
        with closing(connect_documents(db_path)) as conn, conn:
            conn.execute("UPDATE documentos SET last_checked_at=? WHERE id=?",
                         (discovered_at, page_document_id))
        for document in detail["documents"]:
            candidates.append(to_candidate(document, entry, observation_id, discovered_at))

    return {
        "candidates": candidates,
        "summary": {
            "entries": len(entries),
            "new_details": new_fetched,
            "refresh_details": refresh_fetched,
            "documents": sum(1 for c in candidates if c["kind"] != "outro"
                             or c.get("document_type") != "pagina_banca"),
            "errors": errors + errors_catalog,
        },
        # Convenção do projeto (pci_source): parcial quando parte teve sucesso e parte falhou.
        "partial": bool(errors) and bool(candidates),
        "failed": not entries,
    }


def ibfc_source(*, catalog_fetcher=fetch_catalog, detail_fetcher=fetch_detail,
                attempt_blocked_hosts=()) -> dict:
    """Fonte de monitoramento do IBFC (multi-concurso: identidade por certame).

    ``attempt_blocked_hosts`` (ex.: ``("anexos.cdn.selecao.net.br",)``) é opt-in e vale
    somente para esta fonte: permite tentar o download normal de anexos públicos cujo host
    tem ``robots.txt`` restritivo. Falha de acesso é registrada, nunca contornada.
    """
    hosts = tuple(host for host in attempt_blocked_hosts if host)
    def fetch():
        # O ciclo recebe o catálogo "em andamento"; os demais estados são consultados no
        # discover, que sabe lidar com falha parcial de uma listagem.
        return catalog_fetcher("1")

    return {
        "id": IBFC_SOURCE_ID,
        "source_url": IBFC_BASE + "/index/1",
        "name": IBFC_SOURCE_NAME,
        "agency": IBFC_AGENCY,
        "multi_contest": True,
        "fetch": fetch,
        "download_allowed_hosts": list(hosts),
        "discover": lambda db_path, html: discover(
            db_path, html, catalog_fetcher=catalog_fetcher,
            detail_fetcher=detail_fetcher, attempt_blocked_hosts=hosts),
    }
