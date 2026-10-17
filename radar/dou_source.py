"""Segunda fonte oficial: Diário Oficial da União (Imprensa Nacional), Seção 3.

Acesso público à "Leitura do Jornal": a página diária da Seção 3 embute um JSON
oficial com as matérias do dia (título, órgão, tipo de ato, data e texto). O
adaptador lê esse JSON e produz candidatos documentais; a extração reutiliza as
regras conservadoras de ``document_fields`` e nunca confirma fatos sozinha.

A fonte é independente da já integrada (Guajará-Mirim/AROM) e não substitui a
publicação certificada. Este módulo não grava em ``concursos`` v1.
"""

from __future__ import annotations

import html as _html
import json
import re
import urllib.request
from datetime import date, datetime, timezone

DOU_SOURCE_ID = "dou-secao-3"
DOU_SOURCE_NAME = "Diário Oficial da União (Seção 3)"
DOU_AGENCY = "Imprensa Nacional"
DOU_SECTION = "do3"
DOU_EDITION_BASE = "https://www.in.gov.br/leiturajornal"
# Identidade estável da fonte no registro de observações (não é concurso nem documento).
DOU_SOURCE_URL = DOU_EDITION_BASE + "?secao=" + DOU_SECTION
DOU_COMPETITION_ID = "DOU-S3"
DOU_ARTICLE_BASE = "https://www.in.gov.br/web/dou/-/"

MAX_BYTES = 8 * 1024 * 1024
TIMEOUT_SECONDS = 60
# A fonte responde 403 a clientes sem cabeçalhos de navegador; usamos um UA
# identificado porém compatível com navegador e apenas leitura pública.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_KIND_RETIFICACAO = re.compile(r"retifica", re.IGNORECASE)
_KIND_EDITAL = re.compile(r"\bedital\b", re.IGNORECASE)


def edition_url(section: str = DOU_SECTION, day: str | None = None) -> str:
    """URL da edição diária. ``day`` no formato DD-MM-AAAA (padrão: hoje, UTC)."""
    if day is None:
        day = datetime.now(timezone.utc).strftime("%d-%m-%Y")
    if not re.fullmatch(r"\d{2}-\d{2}-\d{4}", day):
        raise ValueError("data da edição deve ser DD-MM-AAAA")
    return f"{DOU_EDITION_BASE}?data={day}&secao={section}"


def decode_body(body: bytes) -> str:
    """A página anuncia UTF-8, mas o corpo real é Windows-1252; decodifica com fallback."""
    if not isinstance(body, (bytes, bytearray)) or not body:
        raise ValueError("corpo vazio")
    for encoding in ("utf-8", "cp1252"):
        try:
            return bytes(body).decode(encoding)
        except UnicodeDecodeError:
            continue
    return bytes(body).decode("utf-8", "replace")


def _extract_json_array(text: str, start: int) -> list:
    """Extrai o array JSON balanceado a partir de ``text[start]`` (deve ser '[')."""
    depth = 0
    index = start
    in_string = False
    escaped = False
    while index < len(text):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
            elif char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start:index + 1])
        index += 1
    raise ValueError("array JSON não balanceado")


def parse_edition(html: str) -> dict:
    """Extrai o JSON oficial da edição embutido na página da Leitura do Jornal."""
    if not isinstance(html, str) or not html.strip():
        raise ValueError("HTML da edição ausente")
    best = None
    for match in re.finditer(r'"jsonArray"\s*:\s*\[', html):
        start = html.index("[", match.start())
        try:
            data = _extract_json_array(html, start)
        except (ValueError, json.JSONDecodeError):
            continue
        if data and (best is None or len(data) > len(best)):
            best = data
    if best is None:
        raise ValueError("JSON de matérias não encontrado na edição")
    section = None
    section_match = re.search(r'"section"\s*:\s*"([A-Za-z0-9]+)"', html)
    if section_match:
        section = section_match.group(1)
    return {"section": section, "items": best}


def item_text(item: dict) -> str:
    parts = [str(item.get(key) or "") for key in ("title", "subTitulo", "artType", "content")]
    return " ".join(" ".join(parts).split())


def is_relevant(item: dict) -> bool:
    """Relevante quando o texto oficial menciona concurso (prova por conteúdo)."""
    return "concurso" in item_text(item).lower()


def classify_kind(item: dict) -> str:
    label = f"{item.get('title', '')} {item.get('artType', '')}"
    if _KIND_RETIFICACAO.search(label):
        return "retificacao"
    if _KIND_EDITAL.search(label):
        return "edital"
    return "outro"


def article_url(item: dict) -> str:
    slug = item.get("urlTitle")
    if not isinstance(slug, str) or not slug.strip():
        raise ValueError("matéria sem urlTitle")
    return DOU_ARTICLE_BASE + slug.strip()


def _iso_date(value: str | None) -> str | None:
    if not value:
        return None
    match = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", value.strip())
    if match is None:
        return None
    try:
        return date(int(match.group(3)), int(match.group(2)), int(match.group(1))).isoformat()
    except ValueError:
        return None


def content_bytes(item: dict) -> bytes:
    """Renderiza o texto oficial como HTML mínimo para extração citável."""
    text = str(item.get("content") or "").strip()
    if not text:
        raise ValueError("matéria sem conteúdo textual")
    return ("<p>" + _html.escape(text) + "</p>").encode("utf-8")


def to_candidate(item: dict, observation_id: str, discovered_at: str) -> dict:
    """Candidato para ``register_document``, com conteúdo oficial embutido."""
    return {
        "observation_id": observation_id,
        "kind": classify_kind(item),
        "official_url": article_url(item),
        "title": str(item.get("title") or "").strip(),
        "discovery_url": DOU_SOURCE_URL,
        "discovery_method": "automatico",
        "discovered_at": discovered_at,
        "issuer": item.get("hierarchyStr"),
        "published_at": _iso_date(item.get("pubDate")),
        "source_identifier": item.get("urlTitle"),
        # Conteúdo oficial da matéria; usado para gravar a versão sem rebaixar a página.
        "inline_content": content_bytes(item),
        "inline_content_type": "text/html",
    }


def _balanced_div(html: str, start_tag_index: int) -> str:
    """Devolve o conteúdo interno de um `<div>` a partir do índice do seu `<`."""
    open_end = html.find(">", start_tag_index)
    depth = 1
    index = open_end + 1
    while index < len(html) and depth > 0:
        next_open = html.find("<div", index)
        next_close = html.find("</div", index)
        if next_close == -1:
            break
        if next_open != -1 and next_open < next_close:
            depth += 1
            index = next_open + 4
        else:
            depth -= 1
            index = next_close + 5
    return html[open_end + 1:next_close if depth == 0 else len(html)]


def extract_article_body(html: str) -> bytes:
    """Extrai o ato oficial completo de ``<div class="texto-dou">``.

    A página do artigo traz o texto integral do ato (a matéria do JSON é truncada);
    o conteúdo fica dentro de `div.texto-dou`. Falha fechado quando ausente.
    """
    if not isinstance(html, str) or not html:
        raise ValueError("página do artigo vazia")
    marker = html.find('class="texto-dou"')
    if marker == -1:
        raise ValueError("conteúdo oficial (texto-dou) ausente")
    div_start = html.rfind("<div", 0, marker)
    if div_start == -1:
        raise ValueError("conteúdo oficial (texto-dou) ausente")
    body = _balanced_div(html, div_start).strip()
    if not body:
        raise ValueError("conteúdo oficial vazio")
    return body.encode("utf-8")


def fetch_article(url: str, opener=None) -> bytes:
    """Baixa a página do artigo e devolve o ato oficial completo (texto-dou)."""
    if not isinstance(url, str) or not url.startswith(DOU_ARTICLE_BASE):
        raise ValueError("URL de artigo do DOU inválida")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"})
    if opener is None:
        opener = urllib.request.urlopen
    with opener(request, timeout=TIMEOUT_SECONDS) as response:
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("artigo excede o limite de bytes")
    return extract_article_body(decode_body(body))


def discover(html: str, observation_id: str, discovered_at: str | None = None,
             article_fetcher=None) -> list[dict]:
    """Matérias relevantes da edição como candidatos documentais (deduplicadas por URL).

    Quando ``article_fetcher`` é fornecido, busca o ato oficial completo de cada
    matéria e o usa como conteúdo; se a busca falhar, mantém o conteúdo do JSON.
    """
    discovered_at = discovered_at or datetime.now(timezone.utc).isoformat()
    edition = parse_edition(html)
    seen: set[str] = set()
    candidates = []
    for item in edition["items"]:
        if not is_relevant(item):
            continue
        try:
            candidate = to_candidate(item, observation_id, discovered_at)
        except ValueError:
            continue
        url = candidate["official_url"]
        if url in seen:
            continue
        seen.add(url)
        if article_fetcher is not None:
            try:
                candidate["inline_content"] = article_fetcher(url)
            except (OSError, ValueError):
                pass  # falha de rede/parse: mantém o conteúdo (truncado) do JSON
        candidates.append(candidate)
    return candidates


def fetch_edition(section: str = DOU_SECTION, day: str | None = None, opener=None) -> str:
    """Baixa a edição diária por HTTPS, com limite de bytes e decodificação robusta."""
    url = edition_url(section, day)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"})
    if opener is None:
        opener = urllib.request.urlopen
    with opener(request, timeout=TIMEOUT_SECONDS) as response:
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("edição excede o limite de bytes")
    return decode_body(body)


def dou_source(day: str | None = None, article_fetcher=None) -> dict:
    """Fonte de monitoramento do DOU (Seção 3), com identidade própria.

    Com ``article_fetcher`` (ex.: ``fetch_article``), cada matéria é enriquecida com
    o ato oficial completo; sem ele, usa o conteúdo (truncado) do JSON.
    """
    def fetch():
        return fetch_edition(DOU_SECTION, day)

    return {
        "id": DOU_SOURCE_ID,
        "source_url": DOU_SOURCE_URL,
        "competition_id": DOU_COMPETITION_ID,
        # A Seção 3 identifica uma PUBLICAÇÃO, não um certame: cada ato do dia é de um
        # órgão diferente. A fonte declara isso explicitamente para que o concurso criado
        # seja um container de retenção, nunca um "concurso" artificial.
        "tipo_identidade": "secao_publicacao",
        "name": DOU_SOURCE_NAME,
        "agency": DOU_AGENCY,
        "inline": True,
        "fetch": fetch,
        "discover": lambda html, observation_id: discover(
            html, observation_id, article_fetcher=article_fetcher),
    }
