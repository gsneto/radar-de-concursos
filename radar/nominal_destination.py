"""Proposta de destino para documentos nominais (Fase 35).

Documento nominal (lista de nomes, inscrições, notas, aprovados) não alimenta campo do
concurso e expõe dados pessoais. A Fase 34 os triou em quatro eixos; esta fase propõe um
**destino individual**, com justificativa e consequência — e **não executa nada**.

Nenhuma ação destrutiva é oferecida aqui: o projeto não tem arquivamento reversível nem
remoção controlada com trilha de auditoria. A proposta é a decisão informada; aplicá-la exige
uma fase com modelo próprio (e autorização humana explícita).

Regras:

- manter metadados não é manter conteúdo: a proposta distingue os dois;
- documento com conteúdo já extraído é passivo a resolver, não a esconder;
- política não verificada não vira proibição nem autorização;
- nada de conteúdo nominal (nome, trecho, lista) sai deste módulo.
"""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone

from radar import source_catalog as catalog
from radar.coverage_states import _host, _source_for, _source_map
from radar.document_store import connect_documents, is_readable_schema
from radar.document_types import is_nominal_title

DESTINATION_VERSION = "nominal_destination_v1"

# Destinos propostos. Todos reversíveis por natureza (nenhum apaga conteúdo).
DESTINATIONS = (
    "manter_metadados_na_fila",
    "retirar_da_fila_operacional",
    "revisar_politica_antes_de_agir",
    "reconciliar_identidade",
)
DESTINATION_LABELS = {
    "manter_metadados_na_fila": "Manter apenas metadados na fila",
    "retirar_da_fila_operacional": "Retirar da fila operacional (arquivo permanece armazenado)",
    "revisar_politica_antes_de_agir": "Revisar a política da fonte antes de qualquer ação",
    "reconciliar_identidade": "Reconciliar a identidade documental primeiro",
}
CONSEQUENCES = {
    "manter_metadados_na_fila": "o documento continua visível na triagem, sem download novo",
    "retirar_da_fila_operacional": "sai da fila de trabalho; nada é apagado do banco",
    "revisar_politica_antes_de_agir": "nada muda até a política ser verificada",
    "reconciliar_identidade": "o documento fica pendente até saber a qual certame pertence",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _policy(source_id) -> dict:
    if not source_id:
        return {"acesso": "fonte_desconhecida", "permitido": False,
                "motivo": "fonte fora do catálogo"}
    from radar import source_policy
    try:
        decision = source_policy.decision(source_id, "documento")
    except Exception:
        return {"acesso": "nao_verificado", "permitido": False,
                "motivo": "política indisponível"}
    permission = decision["permission"]
    if decision["allowed"]:
        access = "permitido"
    elif permission == catalog.ACESSO_BLOQUEADO:
        access = "bloqueado"
    elif permission == catalog.PERSISTENCIA_NAO_VERIFICADA:
        access = "nao_verificado"
    else:
        access = "nao_autorizado"
    return {"acesso": access, "permitido": bool(decision["allowed"]),
            "motivo": decision["reason"], "permission": permission,
            "permission_label": catalog.PERMISSION_LABELS.get(permission)}


def _destination(*, has_identity, has_content, policy, title) -> tuple[str, str, str]:
    """Destino + justificativa + consequência, na ordem que evita decisão errada."""
    if not has_identity:
        return ("reconciliar_identidade",
                "o documento não está associado a um certame identificável; arquivar agora "
                "esconderia uma pendência de identidade",
                CONSEQUENCES["reconciliar_identidade"])
    if policy["acesso"] in ("nao_verificado", "fonte_desconhecida"):
        return ("revisar_politica_antes_de_agir",
                f"a política de persistência não está confirmada ({policy['motivo']}); "
                "nem proibir nem liberar sem verificação",
                CONSEQUENCES["revisar_politica_antes_de_agir"])
    if has_content:
        return ("retirar_da_fila_operacional",
                "lista nominal com arquivo já baixado: não alimenta campo do concurso e não deve "
                "ser reprocessada; o arquivo permanece armazenado com proveniência",
                CONSEQUENCES["retirar_da_fila_operacional"])
    return ("manter_metadados_na_fila",
            "somente metadados, sem conteúdo baixado: permanece visível na triagem e não "
            "precisa de download",
            CONSEQUENCES["manter_metadados_na_fila"])


def nominal_destinations(db_path, *, contest_id=None, destination=None,
                         limit=200, offset=0) -> dict:
    """Proposta individual de destino, em modo simulação (nenhuma escrita)."""
    limit = int(limit)
    offset = int(offset)
    if limit < 1 or limit > 500:
        raise ValueError("limite fora da faixa")
    if offset < 0:
        raise ValueError("deslocamento inválido")
    if destination and destination not in DESTINATIONS:
        raise ValueError("destino inválido")
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
                     WHERE v.document_id=d.id),
                   ci.estado_identidade
            FROM documentos d LEFT JOIN concursos_identidade ci ON ci.id=d.contest_id
            ORDER BY d.discovered_at DESC""").fetchall()
        titles = {}
        for cid, title, tipo in conn.execute(
                "SELECT contest_id, title, tipo_documental FROM documentos "
                "WHERE contest_id IS NOT NULL ORDER BY discovered_at"):
            entry = titles.setdefault(cid, {"title": None, "edital": None})
            if entry["title"] is None:
                entry["title"] = title
            if tipo in ("edital_abertura", "edital_retificado") and entry["edital"] is None:
                entry["edital"] = title
    items = []
    for row in rows:
        title = row[2] or ""
        if not is_nominal_title(title):
            continue
        if contest_id and row[1] != contest_id:
            continue
        source = _source_for(_host(row[4]), pairs, row[5])
        policy = _policy(source["id"] if source else None)
        has_identity = bool(row[1] and (row[10] or "") == "certame")
        has_content = bool(row[8]) or bool(row[9])
        destination_value, justification, consequence = _destination(
            has_identity=has_identity, has_content=has_content, policy=policy, title=title)
        if destination and destination_value != destination:
            continue
        contest = titles.get(row[1]) or {}
        items.append({
            "document_id": row[0], "contest_id": row[1],
            "contest_title": contest.get("edital") or contest.get("title"),
            "title": title, "tipo_documental": row[3], "official_url": row[4],
            "issuer": row[5], "discovered_at": row[6], "published_at": row[7],
            "tem_versao": bool(row[8]), "blocos": row[9],
            "source_id": source["id"] if source else None,
            "politica": policy,
            "destino": destination_value,
            "destino_label": DESTINATION_LABELS[destination_value],
            "justificativa": justification,
            "consequencia": consequence,
            "executado": False,
        })
    total = len(items)
    by_destination = {}
    for item in items:
        by_destination[item["destino"]] = by_destination.get(item["destino"], 0) + 1
    return {
        "version": DESTINATION_VERSION, "generated_at": _now(),
        "modo": "simulacao", "total": total,
        "por_destino": by_destination,
        "limit": limit, "offset": offset, "has_more": offset + limit < total,
        "itens": items[offset:offset + limit],
        "limitacao": ("Proposta em modo simulação: nenhum documento é arquivado, apagado ou "
                      "movido. O projeto ainda não tem arquivamento reversível com trilha de "
                      "auditoria; aplicar exige modelo próprio e autorização humana. "
                      "Metadados não são conteúdo pessoal; nenhum trecho nominal é retornado."),
    }
