"""Canal complementar de descoberta: PCI Concursos via servidor MCP público.

A PCI é um **agregador não oficial**: os resultados são descobertas, não
comprovação documental. O conector consulta as ferramentas MCP públicas, registra
candidatos com proveniência e metadados mínimos, e nunca confirma fatos sozinho.

Somente as ferramentas de concursos são usadas (`buscar_apostilas` é ignorada).
Nenhum scraping do site é feito; apenas o MCP documentado é consultado.
"""

from __future__ import annotations

import html as _html
import json
import re
import unicodedata
import urllib.request
from datetime import datetime, timezone

PCI_SOURCE_ID = "pci"
PCI_SOURCE_NAME = "PCI Concursos (MCP)"
PCI_AGENCY = "PCI Concursos (agregador)"
PCI_ENDPOINT = "https://mcp.pciconcursos.com.br/mcp"
PCI_PROTOCOL_VERSION = "2025-06-18"
PCI_USER_AGENT = "radar-de-concursos/0.1 (+https://github.com/gsneto/radar-de-concursos)"
PCI_TIMEOUT_SECONDS = 45
PCI_MAX_BYTES = 8 * 1024 * 1024

# Conjunto versionado de consultas de descoberta (ordem de execução).
PCI_QUERIES_VERSION = 1
PCI_QUERIES = (
    ("listar_concursos", {}),
    ("buscar_por_cargo", {"cargo": "analista de sistemas"}),
    ("buscar_por_cargo", {"cargo": "técnico em informática"}),
    ("pesquisar_concursos", {"termo": "sistemas de informação"}),
)
# Ferramentas de concursos (a de apostilas não é usada).
PCI_CONCURSO_TOOLS = ("listar_concursos", "pesquisar_concursos", "buscar_por_cargo", "buscar_por_cidade")


class PciProtocolError(Exception):
    """Erro de protocolo/conexão MCP (handshake, transporte, JSON)."""


def _extract_sse_data(text: str) -> str:
    """Concatena os campos `data:` de uma resposta text/event-stream."""
    parts = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
    return "".join(parts) or text


class McpClient:
    """Cliente MCP mínimo (Streamable HTTP, JSON-RPC 2.0), sem dependências externas."""

    def __init__(self, endpoint: str = PCI_ENDPOINT, timeout: int = PCI_TIMEOUT_SECONDS,
                 opener=None, user_agent: str = PCI_USER_AGENT):
        self.endpoint = endpoint
        self.timeout = timeout
        self.user_agent = user_agent
        self._opener = opener or urllib.request.urlopen

    def _rpc(self, method: str, params: dict | None) -> dict:
        body = {"jsonrpc": "2.0", "method": method, "id": 1}
        if params is not None:
            body["params"] = params
        request = urllib.request.Request(
            self.endpoint, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream",
                     "User-Agent": self.user_agent,
                     "MCP-Protocol-Version": PCI_PROTOCOL_VERSION},
            method="POST")
        try:
            with self._opener(request, timeout=self.timeout) as response:
                raw = response.read(PCI_MAX_BYTES + 1)
        except Exception as error:  # rede/timeout/TLS: falha de conexão
            raise PciProtocolError(f"{type(error).__name__}: {error}") from error
        if len(raw) > PCI_MAX_BYTES:
            raise PciProtocolError("resposta MCP excede o limite de bytes")
        text = raw.decode("utf-8", "replace")
        if text.lstrip().startswith("event:") or "\ndata:" in text or text.startswith("data:"):
            text = _extract_sse_data(text)
        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            raise PciProtocolError("resposta MCP não é JSON") from error

    def initialize(self) -> dict:
        return self._rpc("initialize", {
            "protocolVersion": PCI_PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "radar-de-concursos", "version": "0.1"}})

    def list_tools(self) -> list[dict]:
        payload = self._rpc("tools/list", {})
        if "error" in payload:
            raise PciProtocolError(str(payload["error"])[:200])
        return payload.get("result", {}).get("tools", [])

    def call(self, name: str, arguments: dict) -> dict:
        return self._rpc("tools/call", {"name": name, "arguments": arguments})


def parse_tool_result(payload: dict) -> tuple[bool, dict | None, str, str | None]:
    """Interpreta a resposta de `tools/call`.

    Devolve ``(is_error, obj, text, reason)``. ``obj`` é o JSON (`meta`+`data`)
    quando interpretável. ``reason`` distingue: ``"rpc_error"`` (erro JSON-RPC),
    ``"tool_error"`` (isError da ferramenta), ``"unreadable"`` (texto não
    interpretável) ou ``None`` (sucesso). Erro de ferramenta ≠ erro de conexão.
    """
    if not isinstance(payload, dict):
        return True, None, "", "rpc_error"
    if "error" in payload:
        return True, None, json.dumps(payload["error"], ensure_ascii=False)[:500], "rpc_error"
    result = payload.get("result") or {}
    is_error = bool(result.get("isError"))
    content = result.get("content") or []
    text = ""
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text") or ""
            break
    if is_error:
        return True, None, text, "tool_error"
    obj = None
    if text.strip().startswith("{"):
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            obj = None
    if obj is None:
        return True, None, text, "unreadable"
    return False, obj, text, None


def _normalize(text) -> str:
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", ascii_text.lower()).split())


def _iso_date(value) -> str | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value.strip())
    return value.strip() if match else None


def normalize(item: dict, query_label: str, discovered_at: str) -> dict | None:
    """Normaliza um resultado da PCI para o candidato de descoberta (metadados mínimos)."""
    if not isinstance(item, dict):
        return None
    pci_id = item.get("id")
    noticia = item.get("noticia") or {}
    link = noticia.get("link")
    title = (item.get("titulo") or noticia.get("titulo") or "").strip()
    if not isinstance(pci_id, (int, str)) or not title or not isinstance(link, str) or not link.startswith("https://"):
        return None
    datas = item.get("datas") or {}
    return {
        "pci_id": pci_id,
        "competition_id": f"pci-{pci_id}",
        "title": title,
        "uf": item.get("uf"),
        "regiao": item.get("regiao"),
        "cargos_resumo": item.get("cargos_resumo"),
        "vagas_salario": item.get("vagas_salario"),
        "formacao": item.get("formacao"),
        "data_inicio": _iso_date(datas.get("inicio")),
        "data_fim": _iso_date(datas.get("fim")),
        "aberto": datas.get("aberto"),
        "dias_restantes": datas.get("dias_restantes"),
        "noticia_titulo": noticia.get("titulo"),
        "url": link,
        "query": query_label,
        "discovered_at": discovered_at,
    }


def _content_bytes(candidate: dict) -> bytes:
    """Conteúdo mínimo (metadados + proveniência), sem copiar o acervo."""
    rows = [
        ("Concurso", candidate["title"]),
        ("UF/Região", " / ".join(x for x in (candidate.get("uf"), candidate.get("regiao")) if x) or "desconhecido"),
        ("Cargos (resumo)", candidate.get("cargos_resumo") or "desconhecido"),
        ("Vagas/Salário (anúncio PCI)", candidate.get("vagas_salario") or "desconhecido"),
        ("Formação (anúncio PCI)", candidate.get("formacao") or "desconhecido"),
        ("Inscrições", " a ".join(x for x in (candidate.get("data_inicio"), candidate.get("data_fim")) if x) or "desconhecido"),
        ("Consulta PCI", candidate.get("query")),
    ]
    parts = ["<p>Descoberta pelo PCI Concursos (agregador não oficial; não confirmado).</p>"]
    for label, value in rows:
        parts.append(f"<p>{_html.escape(label)}: {_html.escape(str(value))}</p>")
    parts.append(f"<p>Fonte PCI: {_html.escape(candidate['url'])}</p>")
    return "".join(parts).encode("utf-8")


def to_candidate(candidate: dict, observation_id: str) -> dict:
    """Candidato documental para `register_document` (documento de descoberta)."""
    return {
        "observation_id": observation_id,
        "kind": "outro",
        "official_url": candidate["url"],
        "title": candidate["title"],
        "discovery_url": candidate["url"],
        "discovery_method": "automatico",
        "discovered_at": candidate["discovered_at"],
        "issuer": PCI_AGENCY,
        "published_at": candidate.get("data_inicio"),
        "source_identifier": candidate["competition_id"],
        # Metadados normalizados preservados para a fila de confirmação (a Fase 10
        # não os usa; `register_document` ignora chaves desconhecidas).
        "pci_meta": {key: candidate.get(key) for key in (
            "competition_id", "pci_id", "title", "url", "uf", "regiao", "cargos_resumo",
            "vagas_salario", "formacao", "data_inicio", "data_fim", "aberto",
            "dias_restantes", "query", "discovered_at")},
        "inline_content": _content_bytes(candidate),
        "inline_content_type": "text/html",
    }


def _other_source_titles(db_path) -> set[str]:
    """Títulos normalizados de concursos de OUTRAS fontes (métrica de sobreposição)."""
    from contextlib import closing
    from radar.document_store import connect_documents
    with closing(connect_documents(db_path)) as conn:
        rows = conn.execute(
            "SELECT title FROM documentos WHERE issuer IS NOT ?", (PCI_AGENCY,)).fetchall()
    return {_normalize(row[0]) for row in rows if row[0]}


def discover(db_path, *, caller, queries=PCI_QUERIES, max_new_concursos: int = 500,
             now=None) -> dict:
    """Executa o conjunto de consultas e registra descobertas do PCI.

    ``caller(tool, arguments) -> payload`` é injetável (testes). Devolve
    ``{candidates, summary, partial, failed}``: candidatos documentais, resumo
    operacional, indicador de execução parcial (alguma consulta falhou, mas houve
    sucesso) e de falha total (nenhuma consulta teve sucesso).
    """
    from contextlib import closing
    from radar.document_store import connect_documents, ensure_observation

    now = now or (lambda: datetime.now(timezone.utc).isoformat())
    discovered_at = now()

    seen: dict[str, dict] = {}
    query_log = []
    errors = []
    results_observed = 0
    calls = 0
    succeeded = 0
    for tool, arguments in queries:
        label = f"{tool}:{json.dumps(arguments, ensure_ascii=False, sort_keys=True)}"
        calls += 1
        try:
            payload = caller(tool, arguments)
            is_error, obj, text, reason = parse_tool_result(payload)
        except Exception as error:
            errors.append({"query": label, "error_code": type(error).__name__})
            query_log.append({"query": label, "state": "falhou", "results": 0})
            continue
        if is_error or obj is None:
            errors.append({"query": label, "error_code": reason or "resposta_invalida"})
            query_log.append({"query": label, "state": "falhou", "results": 0})
            continue
        succeeded += 1
        data = obj.get("data") or []
        results_observed += len(data)
        query_log.append({"query": label, "state": "concluido", "results": len(data)})
        for item in data:
            candidate = normalize(item, label, discovered_at)
            if candidate and candidate["competition_id"] not in seen:
                seen[candidate["competition_id"]] = candidate

    # Deduplicação por identidade estável (`competition_id`), independente do slug
    # mutável da notícia; e métrica de sobreposição calculada uma vez.
    with closing(connect_documents(db_path)) as conn:
        known_competitions = {row[0] for row in conn.execute(
            "SELECT DISTINCT competition_id FROM observacoes_concurso")}
    other_titles = _other_source_titles(db_path)

    candidates = []
    documents_new = 0
    overlap = 0
    for candidate in seen.values():
        if documents_new >= max_new_concursos:
            break
        if candidate["competition_id"] in known_competitions:
            continue  # já descoberto (mesmo se o slug mudar): não reemite
        observation_id = ensure_observation(db_path, candidate["url"], candidate["competition_id"])
        known_competitions.add(candidate["competition_id"])
        if _normalize(candidate["title"]) in other_titles:
            overlap += 1
        candidates.append(to_candidate(candidate, observation_id))
        documents_new += 1

    partial = succeeded > 0 and bool(errors)
    failed = bool(queries) and succeeded == 0 and bool(errors)
    summary = {
        "queries_version": PCI_QUERIES_VERSION,
        "queries": query_log,
        "calls": calls,
        "queries_ok": succeeded,
        "results_observed": results_observed,
        "unique_concursos": len(seen),
        "new_concursos": documents_new,
        "overlap_hint": overlap,
        "errors": errors,
    }
    return {"candidates": candidates, "summary": summary, "partial": partial, "failed": failed}


def pci_source(*, client=None, queries=PCI_QUERIES, max_new_concursos: int = 500) -> dict:
    """Descritor da fonte PCI para o monitoramento (multi-concurso)."""
    client = client or McpClient()

    def fetch():
        # Negociação inicial do protocolo + descoberta real das ferramentas.
        client.initialize()
        return json.dumps([t.get("name") for t in client.list_tools()])

    return {
        "id": PCI_SOURCE_ID,
        "source_url": PCI_ENDPOINT,
        "name": PCI_SOURCE_NAME,
        "agency": PCI_AGENCY,
        "multi_contest": True,
        "download_new_only": True,
        "fetch": fetch,
        "discover": lambda db_path, html: discover(
            db_path, caller=client.call, queries=queries, max_new_concursos=max_new_concursos),
    }
