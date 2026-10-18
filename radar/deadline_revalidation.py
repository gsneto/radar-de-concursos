"""Revalidação de prazo contra a fonte oficial (Fase 36).

Uma verificação aqui responde uma pergunta estreita e verificável: **o documento oficial
servido hoje é o mesmo que originou o prazo extraído?** Ela não confirma o prazo, não altera
propostas e não substitui decisão humana.

- só usa o conector/fonte já catalogado e a política de persistência da Fase 29;
- baixa no máximo o documento já conhecido (nada de coleta massiva);
- guarda apenas metadados (URL, status, sha256, resultado) — nunca o conteúdo;
- é append-only: cada verificação é uma linha nova em ``revalidacoes_prazo``;
- se o conteúdo mudou, registra ``fonte_alterada`` e deixa a nova versão para o ciclo de
  monitoramento — não troca a evidência em silêncio.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from radar import deadline_calendar, deadline_review, source_policy
from radar.document_store import connect_documents, is_readable_schema

REVALIDATION_VERSION = "deadline_revalidation_v1"
USER_AGENT = "RadarDeConcursos/1.0 (verificacao local de documento oficial)"
MAX_BYTES = 25 * 1024 * 1024


def _now(now=None) -> datetime:
    if isinstance(now, str):
        return datetime.fromisoformat(now)
    return now or datetime.now(timezone.utc)


class _SameHostRedirect(urllib.request.HTTPRedirectHandler):
    """Redirecionamento só para o mesmo host e HTTPS (política da fonte vale no destino)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old = urllib.parse.urlsplit(req.full_url)
        new = urllib.parse.urlsplit(newurl)
        if new.scheme.lower() != "https" or new.hostname != old.hostname:
            raise urllib.error.HTTPError(newurl, code,
                                         "redirecionamento não permitido", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _default_fetcher(url: str, timeout: int = 20):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    opener = urllib.request.build_opener(_SameHostRedirect())
    with opener.open(request, timeout=timeout) as response:
        length = response.headers.get("Content-Length")
        if length and int(length) > MAX_BYTES:
            raise ValueError("documento maior que o limite de verificação")
        payload = response.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise ValueError("documento maior que o limite de verificação")
        return response.status, payload


def plan(db_path, *, limit=5, now=None) -> dict:
    """Alvos de verificação com a política de cada fonte, sem executar nada."""
    report = deadline_calendar.revalidation_targets(db_path, limit=limit, now=now)
    items = []
    for target in report["itens"]:
        source = target.get("fonte") or {}
        policy = source.get("policy") or {}
        items.append(dict(target, politica={
            "source_id": source.get("id"), "source_label": source.get("label"),
            "permission": policy.get("permission"),
            "permission_label": policy.get("permission_label"),
            "allowed": bool(policy.get("allowed")),
            "reason": policy.get("reason"),
        }))
    return {"version": REVALIDATION_VERSION, "generated_at": _now(now).isoformat(),
            "total": report["total"], "limit": report["limit"],
            "has_more": report["has_more"], "itens": items,
            "limitacao": ("Somente o documento oficial já conhecido é verificado; nenhuma "
                          "coleta nova é iniciada e nenhum conteúdo é armazenado.")}


def _record(db_path, target, *, result, checked_at, http_status=None,
            observed_sha=None, note=None, checked_by=None) -> str:
    record_id = str(uuid4())
    with closing(connect_documents(db_path)) as conn, conn:
        if not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='revalidacoes_prazo'").fetchone():
            raise ValueError("migração documental pendente (v21)")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """INSERT INTO revalidacoes_prazo
               (id,contest_id,grupo,escopo,valor,document_id,version_id,checked_at,
                official_url,http_status,stored_sha256,observed_sha256,result,note,
                checked_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (record_id, target["contest_id"], target["grupo"], target.get("escopo"),
             target.get("valor"), target.get("documento_id"), target.get("versao"),
             checked_at, target.get("official_url"), http_status, target.get("sha256"),
             observed_sha, result, note, checked_by))
    return record_id


def execute(db_path, *, limit=5, apply=False, now=None, fetcher=None,
            checked_by="operador local", only=None) -> dict:
    """Verifica os alvos em ordem de urgência. ``apply=False`` não grava.

    ``only`` restringe a um alvo específico (contest_id/grupo/escopo), usado pela interface
    para revalidar exatamente o prazo aberto — nunca um alvo diferente do clicado.
    """
    limit = int(limit)
    if limit < 1 or limit > 500:
        raise ValueError("limite fora da faixa")
    if not isinstance(checked_by, str) or not checked_by.strip():
        raise ValueError("responsável obrigatório")
    now_dt = _now(now)
    checked_at = now_dt.isoformat()
    fetch = fetcher or _default_fetcher
    report = plan(db_path, limit=500, now=now_dt)
    targets = report["itens"]
    if only:
        targets = [target for target in targets
                   if (not only.get("contest_id")
                       or target["contest_id"] == only["contest_id"])
                   and (not only.get("grupo") or target["grupo"] == only["grupo"])
                   and (not only.get("escopo") or target.get("escopo") == only["escopo"])]
        if not targets:
            raise ValueError("prazo não está entre os alvos de revalidação")
    targets = targets[:limit]
    if not apply:
        # Simulação não faz consulta externa: mostra exatamente o que seria verificado.
        return {
            "version": REVALIDATION_VERSION, "generated_at": checked_at,
            "dry_run": True, "limit": limit, "total": len(targets),
            "alvos_disponiveis": report["total"], "por_resultado": {},
            "itens": [dict(target, result=None, http_status=None, observed_sha256=None,
                           note="simulação: nenhuma consulta externa foi feita")
                      for target in targets],
            "limitacao": ("Simulação: nada é consultado, nada é gravado. Use apply para "
                          "verificar o documento oficial."),
        }
    results = []
    counts = {}
    for target in targets:
        policy = target["politica"]
        outcome = {"contest_id": target["contest_id"], "grupo": target["grupo"],
                   "escopo": target.get("escopo"), "valor": target.get("valor"),
                   "documento": target.get("documento"),
                   "versao": target.get("versao"),
                   "official_url": target.get("official_url"),
                   "politica": policy}
        if not policy["allowed"]:
            outcome.update(result="sem_permissao", http_status=None, observed_sha256=None,
                           note=policy.get("reason") or "política não autoriza a verificação")
        else:
            try:
                status, payload = fetch(target["official_url"])
                observed = hashlib.sha256(payload).hexdigest()
                unchanged = observed == target.get("sha256")
                outcome.update(
                    result="fonte_inalterada" if unchanged else "fonte_alterada",
                    http_status=status, observed_sha256=observed,
                    note=("documento servido hoje é idêntico ao da coleta; o prazo continua "
                          "candidato" if unchanged else
                          "documento oficial mudou; a nova versão cabe ao ciclo de "
                          "monitoramento e o prazo exige nova leitura"))
            except urllib.error.HTTPError as error:
                outcome.update(result="fonte_indisponivel", http_status=error.code,
                               observed_sha256=None,
                               note=f"HTTP {error.code} ao buscar o documento oficial")
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
                outcome.update(result="fonte_indisponivel", http_status=None,
                               observed_sha256=None,
                               note=f"fonte indisponível: {type(error).__name__}")
            except Exception as error:  # pragma: no cover - falha inesperada do conector
                outcome.update(result="erro", http_status=None, observed_sha256=None,
                               note=f"erro ao verificar: {type(error).__name__}")
        outcome["record_id"] = _record(
            db_path, target, result=outcome["result"], checked_at=checked_at,
            http_status=outcome.get("http_status"),
            observed_sha=outcome.get("observed_sha256"), note=outcome.get("note"),
            checked_by=checked_by.strip())
        counts[outcome["result"]] = counts.get(outcome["result"], 0) + 1
        results.append(outcome)
    return {
        "version": REVALIDATION_VERSION, "generated_at": checked_at,
        "dry_run": not apply, "limit": limit, "total": len(results),
        "alvos_disponiveis": report["total"],
        "por_resultado": counts, "itens": results,
        "limitacao": ("Verificação registra apenas que o documento oficial é o mesmo (ou "
                      "mudou). Não confirma prazo, não altera propostas e não substitui "
                      "decisão humana."),
    }


def verify_version(db_path, version_id: str, *, contest_id: str | None = None,
                   grupo: str | None = None, escopo=None, apply=False, now=None,
                   fetcher=None, checked_by="operador local") -> dict:
    """Verifica **uma versão específica**, inclusive de prazo em conflito.

    Serve ao caso auditado: a revalidação normal só olha prazos futuros sem conflito, mas
    um conflito também precisa saber se o documento armazenado ainda é o servido hoje.
    Compara sha256 e registra metadados; nunca escolhe valor nem altera propostas.
    """
    if not isinstance(checked_by, str) or not checked_by.strip():
        raise ValueError("responsável obrigatório")
    now_dt = _now(now)
    checked_at = now_dt.isoformat()
    fetch = fetcher or _default_fetcher
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        row = conn.execute(
            """SELECT v.id, v.sha256, v.document_id, d.contest_id, d.official_url,
                      d.title, d.issuer, d.tipo_documental
               FROM versoes_documento v JOIN documentos d ON d.id=v.document_id
               WHERE v.id=?""", (version_id,)).fetchone()
        if not row:
            raise ValueError("versão inexistente")
        version, stored_sha, document_id, doc_contest, url, title, issuer, tipo = row
        if contest_id and doc_contest and contest_id != doc_contest:
            raise ValueError("concurso não corresponde à versão")
        contest = contest_id or doc_contest
        if not contest:
            raise ValueError("versão sem concurso associado")
        if grupo is None:
            # Deriva o grupo do próprio prazo para que a verificação apareça na ficha.
            for candidate, fields in deadline_review.DEADLINE_GROUPS.items():
                placeholders = ",".join("?" for _ in fields)
                found = conn.execute(
                    f"SELECT 1 FROM propostas_campo WHERE contest_id=? "
                    f"AND field_name IN ({placeholders}) LIMIT 1",
                    [contest, *fields]).fetchone()
                if found:
                    grupo = candidate
                    break
    if grupo is not None and grupo not in deadline_review.DEADLINE_GROUPS \
            and grupo != "documento":
        raise ValueError("grupo de prazo inválido")
    target = {"contest_id": contest, "grupo": grupo or "documento", "escopo": escopo,
              "valor": None, "documento_id": document_id, "versao": version,
              "official_url": url, "sha256": stored_sha}
    source = deadline_calendar._source_info(url, issuer,
                                           deadline_calendar.coverage_states._source_map())
    policy = (source or {}).get("policy") or {}
    outcome = {"version_id": version, "document_id": document_id, "documento": title,
               "tipo_documental": tipo, "contest_id": contest,
               "official_url": url, "sha256_armazenado": stored_sha,
               "politica": {"source_id": (source or {}).get("id"),
                            "permission": policy.get("permission"),
                            "allowed": bool(policy.get("allowed")),
                            "reason": policy.get("reason")}}
    if not apply:
        # Mesmo contrato de execute: simulação não consulta a rede.
        outcome.update(result=None, http_status=None, sha256_observado=None,
                       note="simulação: nenhuma consulta externa foi feita")
        outcome["dry_run"] = True
        outcome["checked_at"] = checked_at
        outcome["limitacao"] = ("Simulação: nada é consultado nem gravado.")
        return outcome
    if not policy.get("allowed"):
        outcome.update(result="sem_permissao", http_status=None, sha256_observado=None,
                       note=policy.get("reason") or "política não autoriza a verificação")
    else:
        try:
            status, payload = fetch(url)
            observed = hashlib.sha256(payload).hexdigest()
            same = observed == stored_sha
            outcome.update(
                result="fonte_inalterada" if same else "fonte_alterada",
                http_status=status, sha256_observado=observed,
                note=("documento servido hoje é idêntico ao armazenado; isso não confirma "
                      "a interpretação do prazo" if same else
                      "documento servido hoje difere do armazenado; a nova versão cabe ao "
                      "ciclo de monitoramento"))
        except urllib.error.HTTPError as error:
            outcome.update(result="fonte_indisponivel", http_status=error.code,
                           sha256_observado=None,
                           note=f"HTTP {error.code} ao buscar o documento oficial")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            outcome.update(result="fonte_indisponivel", http_status=None,
                           sha256_observado=None,
                           note=f"fonte indisponível: {type(error).__name__}")
        except Exception as error:  # pragma: no cover
            outcome.update(result="erro", http_status=None, sha256_observado=None,
                           note=f"erro ao verificar: {type(error).__name__}")
    outcome["record_id"] = _record(
        db_path, target, result=outcome["result"], checked_at=checked_at,
        http_status=outcome.get("http_status"),
        observed_sha=outcome.get("sha256_observado"), note=outcome.get("note"),
        checked_by=checked_by.strip())
    outcome["dry_run"] = not apply
    outcome["checked_at"] = checked_at
    outcome["limitacao"] = ("Verificação de documento não confirma prazo: confirma apenas se "
                            "os bytes servidos hoje são os mesmos da coleta.")
    return outcome


def history(db_path, *, contest_id=None, grupo=None, limit=50, offset=0) -> dict:
    """Histórico append-only das verificações registradas."""
    limit = int(limit)
    offset = int(offset)
    if limit < 1 or limit > 200:
        raise ValueError("limite fora da faixa")
    if offset < 0:
        raise ValueError("deslocamento inválido")
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        present = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='revalidacoes_prazo'"
        ).fetchone()
        if not present:
            rows, total = [], 0
        else:
            where, params = [], []
            if contest_id:
                where.append("contest_id=?")
                params.append(contest_id)
            if grupo:
                where.append("grupo=?")
                params.append(grupo)
            clause = (" WHERE " + " AND ".join(where)) if where else ""
            total = conn.execute(
                f"SELECT COUNT(*) FROM revalidacoes_prazo{clause}", params).fetchone()[0]
            rows = conn.execute(
                f"""SELECT id,contest_id,grupo,escopo,valor,document_id,version_id,
                           checked_at,official_url,http_status,stored_sha256,
                           observed_sha256,result,note,checked_by
                    FROM revalidacoes_prazo{clause}
                    ORDER BY checked_at DESC, rowid DESC LIMIT ? OFFSET ?""",
                params + [limit, offset]).fetchall()
    items = [{"id": row[0], "contest_id": row[1], "grupo": row[2], "escopo": row[3],
              "valor": row[4], "document_id": row[5], "versao": row[6],
              "checked_at": row[7], "official_url": row[8], "http_status": row[9],
              "stored_sha256": row[10], "observed_sha256": row[11],
              "result": row[12], "note": row[13], "checked_by": row[14]}
             for row in rows]
    return {"version": REVALIDATION_VERSION, "total": total, "limit": limit,
            "offset": offset, "has_more": offset + limit < total, "itens": items}
