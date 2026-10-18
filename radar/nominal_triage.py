"""Triagem de documentos nominais (Fase 34).

Documento nominal (lista de nomes, inscrições, notas, aprovados) **não** é regra do certame:
publicá-lo não alimenta campo do concurso e o processamento exporia dados pessoais sem ganho.
Este módulo não baixa nada e não apaga nada: ele explica, por documento, **por que** o
tratamento exige decisão humana e qual é a próxima ação.

Distingue explicitamente quatro coisas que costumam ser confundidas:

- **identificação**: o documento pertence a este certame?
- **natureza**: é lista nominal ou ato de regra?
- **acesso**: a fonte permite obter o arquivo?
- **armazenamento**: a política permite persistir o conteúdo?

Um documento pode ser identificado e continuar sem autorização de armazenamento; ou ter
acesso autorizado e não ser útil (lista nominal). Minimização: o relatório devolve título e
URL — nunca o conteúdo nem a lista de pessoas.
"""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone

from radar import source_catalog as catalog
from radar.coverage_states import _host, _source_for, _source_map
from radar.document_store import connect_documents, is_readable_schema
from radar.document_types import is_nominal_title

TRIAGE_VERSION = "nominal_triage_v1"

# Ações possíveis, todas de decisão humana (nenhuma executa download).
NEXT_ACTIONS = {
    "arquivar": "marcar como não aplicável ao Radar (lista nominal) e não reprocessar",
    "conferir_armazenamento": "conferir o conteúdo já armazenado antes de arquivar",
    "buscar_ato_de_regra": "buscar o ato de regra equivalente (edital/retificação/cronograma)",
    "reconciliar_identidade": "confirmar a qual certame o documento pertence",
    "revisar_politica": "revisar a política de acesso/persistência da fonte",
    "obter_autorizado": "obter pelo fluxo autorizado, se a política permitir",
    "sem_acao": "nada a fazer",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _policy(source_id) -> dict:
    """Decisão de persistência de **documento** para a fonte, com o motivo real."""
    if not source_id:
        return {"permitido": False, "acesso": "fonte_desconhecida",
                "motivo": "fonte fora do catálogo", "permission": None,
                "permission_label": None}
    from radar import source_catalog as catalog
    from radar import source_policy
    source = catalog.get_source(source_id)
    try:
        decision = source_policy.decision(source_id, "documento")
    except Exception:
        return {"permitido": False, "acesso": "nao_verificado",
                "motivo": "política indisponível", "permission": None,
                "permission_label": None}
    permission = decision["permission"]
    if decision["allowed"]:
        access = "permitido"
    elif permission == catalog.ACESSO_BLOQUEADO:
        access = "bloqueado"
    elif permission == catalog.PERSISTENCIA_NAO_VERIFICADA:
        access = "nao_verificado"
    else:
        access = "nao_autorizado"
    return {"permitido": bool(decision["allowed"]), "acesso": access,
            "motivo": decision["reason"], "permission": permission,
            "permission_label": catalog.PERMISSION_LABELS.get(permission)}


def _triage_state(*, nominal, policy, has_version, has_blocks, has_identity) -> tuple[str, str]:
    """Estado de triagem + próxima ação, separando os quatro eixos.

    Ordem: identidade → natureza → acesso → armazenamento. Um documento pode estar
    identificado e armazenado e continuar exigindo decisão humana por ser lista nominal.
    """
    if has_blocks:
        return "nominal_processado", "arquivar"
    if has_version:
        # Baixado sem texto extraído: há arquivo armazenado, nada foi extraído.
        return "nominal_baixado", "arquivar"
    if not has_identity:
        return "identidade_pendente", "reconciliar_identidade"
    if policy["acesso"] == "fonte_desconhecida":
        return "fonte_desconhecida", "revisar_politica"
    if policy["acesso"] == "nao_verificado":
        return "persistencia_nao_verificada", "revisar_politica"
    if not policy["permitido"]:
        return "persistencia_nao_autorizada", "revisar_politica"
    return "nominal_sem_conteudo", "arquivar"


def nominal_triage(db_path, *, limit=200, offset=0) -> dict:
    """Visão de triagem dos documentos nominais, com motivo e próxima ação.

    Só devolve metadados (título, URL, tipo, contagens). Nenhum trecho de lista de pessoas
    é copiado — minimização de dados pessoais.
    """
    limit = int(limit)
    offset = int(offset)
    if limit < 1 or limit > 500:
        raise ValueError("limite fora da faixa")
    if offset < 0:
        raise ValueError("deslocamento inválido")
    pairs = _source_map()
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = conn.execute("""
            SELECT d.id, d.contest_id, d.title, d.tipo_documental, d.official_url,
                   d.issuer, d.discovered_at, d.published_at,
                   (SELECT COUNT(*) FROM versoes_documento v WHERE v.document_id=d.id),
                   (SELECT COUNT(*) FROM blocos_documento b
                      JOIN versoes_documento v ON v.id=b.version_id
                     WHERE v.document_id=d.id)
            FROM documentos d ORDER BY d.discovered_at DESC""").fetchall()
        titles = {}
        for contest_id, title, tipo in conn.execute(
                "SELECT contest_id, title, tipo_documental FROM documentos "
                "WHERE contest_id IS NOT NULL ORDER BY discovered_at"):
            entry = titles.setdefault(contest_id, {"title": None, "edital": None})
            if entry["title"] is None:
                entry["title"] = title
            if tipo in ("edital_abertura", "edital_retificado") and entry["edital"] is None:
                entry["edital"] = title

    items = []
    for row in rows:
        title = row[2] or ""
        if not is_nominal_title(title):
            continue
        source = _source_for(_host(row[4]), pairs, row[5])
        policy = _policy(source["id"] if source else None)
        contest = titles.get(row[1]) or {}
        has_identity = bool(row[1] and (contest.get("title") or contest.get("edital")))
        state, action = _triage_state(nominal=True, policy=policy,
                                      has_version=bool(row[8]), has_blocks=bool(row[9]),
                                      has_identity=has_identity)
        items.append({
            "document_id": row[0], "contest_id": row[1],
            "contest_title": contest.get("edital") or contest.get("title"),
            "title": title, "tipo_documental": row[3], "official_url": row[4],
            "issuer": row[5], "discovered_at": row[6], "published_at": row[7],
            "source_id": source["id"] if source else None,
            "source_nature": source["nature"] if source else None,
            "source_status": source["status"] if source else None,
            # Quatro eixos separados: identificação, natureza, acesso e armazenamento.
            "identificacao": ("certame_identificado" if has_identity
                               else "sem_identidade"),
            "natureza": "lista_nominal",
            "acesso": policy["acesso"],
            "armazenamento": ("conteudo_extraido" if row[9] else
                               "arquivo_sem_extracao" if row[8] else "sem_conteudo"),
            "politica": policy,
            "tem_versao": bool(row[8]), "blocos": row[9],
            "estado": state,
            "proxima_acao": NEXT_ACTIONS[action],
            "alternativa_oficial": (contest.get("edital")
                                    if contest.get("edital") != title else None),
            "motivo": ("título indica lista de pessoas/notas (dado pessoal), não ato de "
                       "regra do certame"),
        })
    total = len(items)
    by_state = {}
    for item in items:
        by_state[item["estado"]] = by_state.get(item["estado"], 0) + 1
    return {
        "version": TRIAGE_VERSION, "generated_at": _now(),
        "total": total, "limit": limit, "offset": offset,
        "has_more": offset + len(items[offset:offset + limit]) < total,
        "por_estado": by_state,
        "itens": items[offset:offset + limit],
        "limitacao": ("Nenhum download é feito para exibir a fila. Metadados apenas; o "
                      "conteúdo nominal não é copiado para logs, painéis ou exportações. "
                      "Nominal não é autorização nem proibição permanente: é decisão humana."),
    }


def nominal_summary(db_path) -> dict:
    """Resumo sem paginação (para painel): contagens por estado e por fonte."""
    report = nominal_triage(db_path, limit=1, offset=0)
    with closing(connect_documents(db_path)) as conn:
        rows = conn.execute(
            "SELECT d.title, d.official_url, d.issuer FROM documentos d").fetchall()
    pairs = _source_map()
    by_source = {}
    for title, url, issuer in rows:
        if not is_nominal_title(title):
            continue
        source = _source_for(_host(url), pairs, issuer)
        key = source["id"] if source else "fonte_desconhecida"
        by_source[key] = by_source.get(key, 0) + 1
    return {"version": TRIAGE_VERSION, "generated_at": _now(),
            "total": report["total"], "por_estado": report["por_estado"],
            "por_fonte": by_source,
            "limitacao": report["limitacao"]}
