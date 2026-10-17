"""IBGE Localidades: fonte auxiliar oficial para validar município/UF.

Uso concreto: conferir `exam_location`/`exam_municipio`/`exam_uf` propostos contra a lista
oficial de municípios do IBGE. **Nunca** confirma campo: o resultado é um parecer
(`confere_ibge`, `uf_divergente`, `nao_encontrado`, `sem_snapshot`) para a revisão humana.

Licença: dados abertos governamentais; persistência permitida (catálogo `ibge-localidades`).
"""

from __future__ import annotations

import gzip
import io
import json
import urllib.request
from contextlib import closing
from datetime import datetime, timezone, timedelta
from unicodedata import normalize as _unorm

from radar.connectors import Connector
from radar.document_store import connect_documents, is_readable_schema

IBGE_SOURCE_ID = "ibge-localidades"
MUNICIPIOS_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
SNAPSHOT_TTL_DAYS = 30
MAX_BYTES = 8 * 1024 * 1024
TIMEOUT_SECONDS = 30


class IBGEError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


ALLOWED_HOSTS = ("servicodados.ibge.gov.br",)


class _SameHostRedirects(urllib.request.HTTPRedirectHandler):
    """Segue redirect apenas para o mesmo host oficial e sem mudar de esquema."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        from urllib.parse import urlsplit
        parts = urlsplit(newurl)
        if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
            raise IBGEError("redirecionamento_nao_autorizado",
                            f"redirecionamento não autorizado: {parts.hostname}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(url: str = MUNICIPIOS_URL, *, timeout: int = TIMEOUT_SECONDS) -> bytes:
    from urllib.parse import urlsplit
    if urlsplit(url).hostname not in ALLOWED_HOSTS:
        raise IBGEError("url_nao_autorizada", "host do IBGE não autorizado")
    request = urllib.request.Request(
        url, headers={"User-Agent": "radar-de-concursos/0.1",
                      "Accept": "application/json", "Accept-Encoding": "identity"})
    opener = urllib.request.build_opener(_SameHostRedirects)
    with opener.open(request, timeout=timeout) as response:
        if response.status != 200:
            raise IBGEError("http_invalido", f"IBGE respondeu {response.status}")
        final_host = urlsplit(response.geturl()).hostname
        if final_host not in ALLOWED_HOSTS:
            raise IBGEError("redirecionamento_nao_autorizado", "destino final não autorizado")
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise IBGEError("resposta_grande", "resposta do IBGE excede o limite")
        if response.headers.get("Content-Encoding") == "gzip":
            # O limite vale para o conteúdo **descomprimido**: gzip bomb é recusado.
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
                raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise IBGEError("resposta_grande", "resposta descomprimida excede o limite")
    return raw


def parse_municipios(raw: bytes) -> list[dict]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise IBGEError("resposta_invalida", "JSON do IBGE inválido") from error
    if not isinstance(payload, list) or not payload:
        raise IBGEError("resposta_invalida", "lista de municípios vazia")
    municipios = []
    for item in payload:
        try:
            uf = item["microrregiao"]["mesorregiao"]["UF"]["sigla"]
            municipios.append({"codigo": str(item["id"]), "municipio": item["nome"],
                               "uf": uf})
        except (KeyError, TypeError):
            continue
    if not municipios:
        raise IBGEError("resposta_invalida", "nenhum município utilizável")
    return municipios


def sync_snapshot(db_path, *, transport=None, force: bool = False,
                  now: str | None = None) -> dict:
    """Atualiza o snapshot local (TTL 30 dias). Idempotente dentro do TTL."""
    at = now or _now()
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        row = conn.execute("SELECT COUNT(*), MAX(atualizado_em) FROM localidades_ibge").fetchone()
    total, updated = row
    if total and updated and not force:
        try:
            age = datetime.fromisoformat(at) - datetime.fromisoformat(updated)
        except ValueError:
            age = timedelta(days=SNAPSHOT_TTL_DAYS + 1)
        if age < timedelta(days=SNAPSHOT_TTL_DAYS):
            return {"version": "ibge_v1", "atualizado": False, "municipios": total,
                    "atualizado_em": updated}
    raw = (transport or _fetch)()
    municipios = parse_municipios(raw)
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute("DELETE FROM localidades_ibge")
        conn.executemany(
            "INSERT INTO localidades_ibge (codigo,municipio,uf,atualizado_em) "
            "VALUES (?,?,?,?)",
            [(item["codigo"], item["municipio"], item["uf"], at) for item in municipios])
    return {"version": "ibge_v1", "atualizado": True, "municipios": len(municipios),
            "atualizado_em": at}


def _norm(value: str) -> str:
    return " ".join(_unorm("NFKD", (value or "")).encode("ascii", "ignore")
                    .decode("ascii").lower().split())


def validate_location(db_path, municipio: str, uf: str | None = None) -> dict:
    """Parecer de validação. Não grava nada e não confirma campo."""
    if not isinstance(municipio, str) or not municipio.strip():
        raise IBGEError("municipio_invalido", "município obrigatório")
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        total = conn.execute("SELECT COUNT(*) FROM localidades_ibge").fetchone()[0]
        if not total:
            return {"version": "ibge_v1", "status": "sem_snapshot", "municipio": municipio,
                    "uf": uf, "limitacao": "snapshot do IBGE não carregado"}
        rows = conn.execute(
            "SELECT municipio, uf FROM localidades_ibge WHERE municipio=?",
            (municipio,)).fetchall()
        if not rows:
            rows = conn.execute(
                "SELECT municipio, uf FROM localidades_ibge WHERE municipio=?",
                (municipio.strip().title(),)).fetchall()
        if not rows:
            target = _norm(municipio)
            rows = [(nome, sigla) for nome, sigla in conn.execute(
                "SELECT municipio, uf FROM localidades_ibge") if _norm(nome) == target]
    if not rows:
        return {"version": "ibge_v1", "status": "nao_encontrado", "municipio": municipio,
                "uf": uf, "limitacao": "município não consta na lista oficial do IBGE"}
    ufs = {sigla for _, sigla in rows}
    if uf:
        if uf.upper() in ufs:
            return {"version": "ibge_v1", "status": "confere_ibge", "municipio": municipio,
                    "uf": uf.upper(), "ufs_encontradas": sorted(ufs)}
        return {"version": "ibge_v1", "status": "uf_divergente", "municipio": municipio,
                "uf": uf.upper(), "ufs_encontradas": sorted(ufs),
                "limitacao": "município existe, mas em outra UF"}
    return {"version": "ibge_v1", "status": "confere_ibge", "municipio": municipio,
            "uf": None, "ufs_encontradas": sorted(ufs)}


def validate_proposals(db_path, *, limit: int = 100, contest_id=None) -> dict:
    """Confere propostas de local de prova contra o IBGE (somente leitura das propostas)."""
    limit = int(limit)
    if limit < 1 or limit > 1000:
        raise ValueError("limite fora da faixa")
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = conn.execute("""
            SELECT p.id, p.contest_id, p.field_name, p.value_json, p.role_id
            FROM propostas_campo p
            JOIN concursos_identidade c ON c.id=p.contest_id
            WHERE c.estado_identidade='certame'
              AND p.field_name IN ('exam_municipio','exam_uf','exam_location')
              AND (? IS NULL OR p.contest_id=?)
            ORDER BY p.contest_id, p.field_name, p.id LIMIT ?""",
            (contest_id, contest_id, limit)).fetchall()
    results = []
    counters = {}
    for proposal_id, contest, field, value_json, role in rows:
        try:
            value = json.loads(value_json)
        except (TypeError, ValueError):
            value = value_json
        if not isinstance(value, str) or not value.strip():
            continue
        if field == "exam_uf":
            uf, municipio = value.strip().upper(), None
            if len(uf) != 2:
                continue
        elif field == "exam_municipio":
            municipio, uf = value.strip(), None
        else:
            parts = [part.strip() for part in value.split(";") if part.strip()]
            if len(parts) != 1 or "/" not in parts[0]:
                # Lista de cidades ou texto livre: não é um município único.
                counters["lista_ou_texto_livre"] = counters.get("lista_ou_texto_livre", 0) + 1
                continue
            municipio, uf = parts[0].rsplit("/", 1)
            uf = uf.strip().upper()
        if field == "exam_uf":
            with closing(connect_documents(db_path)) as conn:
                total_ufs = conn.execute(
                    "SELECT COUNT(*) FROM localidades_ibge").fetchone()[0]
                exists = conn.execute(
                    "SELECT COUNT(*) FROM localidades_ibge WHERE uf=?", (uf,)).fetchone()[0]
            if not total_ufs:
                status = {"status": "sem_snapshot", "municipio": None, "uf": uf}
            else:
                status = {"status": "confere_ibge" if exists else "nao_encontrado",
                          "municipio": None, "uf": uf}
        else:
            status = validate_location(db_path, municipio, uf)
        counters[status["status"]] = counters.get(status["status"], 0) + 1
        results.append({"proposal_id": proposal_id, "contest_id": contest,
                        "field_name": field, "value": value, "role_id": role,
                        "ibge": status})
    return {"version": "ibge_v1", "total": len(results), "por_status": counters,
            "itens": results,
            "limitacao": ("Parecer auxiliar: não confirma nem altera propostas. "
                          "Município ausente na lista do IBGE exige revisão humana.")}


class IBGEConnector(Connector):
    def __init__(self):
        super().__init__(
            id=IBGE_SOURCE_ID, category="auxiliar",
            capabilities=("metadados", "documento"),
            content_types=("metadados", "dado_aberto"),
            pagination={"tipo": "nenhuma"},
            notes="Lista oficial de municípios/UFs; valida local de prova sem confirmar campo.")

    def availability(self) -> dict:
        base = super().availability()
        base["implemented"] = True
        base["tested_with"] = "conexão real em 2026-10-17 (5571 municípios)"
        return base

    def discover(self, **kwargs) -> list:
        transport = kwargs.get("transport")
        return parse_municipios((transport or _fetch)())
