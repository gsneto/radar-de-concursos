"""Revisão de prazos candidatos (Fase 35).

Responde, por prazo: qual é o texto original, de que documento/versão/página ele veio, se há
retificação posterior que **efetivamente** toca o campo, e qual é a situação temporal em
relação ao relógio da consulta.

Regras de honestidade:

- data futura **não** comprova vigência: a fonte precisa sustentar a aplicabilidade;
- retificação que não menciona o campo **não** altera o prazo (`retificacao_sem_alteracao`);
- prazo passado não é apagado: fica como histórico, marcado como expirado;
- nada aqui confirma prazo: a decisão é humana e continua em ``review.decide_proposal``.
"""

from __future__ import annotations

import json
import re
from contextlib import closing
from datetime import date, datetime, timezone

from radar import review
from radar.document_store import connect_documents, is_readable_schema

DEADLINE_VERSION = "deadline_review_v1"

# Grupos de prazo e os campos que os compõem.
DEADLINE_GROUPS = {
    "inscricao_inicio": ("registration_start",),
    "inscricao_fim": ("registration_end",),
    "isencao_inicio": ("exemption_start",),
    "isencao_fim": ("exemption_end",),
    "recurso_isencao": ("exemption_appeal",),
    "resultado_isencao_preliminar": ("exemption_result_preliminary",),
    "resultado_isencao_final": ("exemption_result_final",),
    "data_prova": ("exam_date",),
}
GROUP_LABELS = {
    "inscricao_inicio": "Início das inscrições",
    "inscricao_fim": "Fim das inscrições",
    "isencao_inicio": "Início da isenção",
    "isencao_fim": "Fim da isenção",
    "recurso_isencao": "Recurso da isenção",
    "resultado_isencao_preliminar": "Resultado preliminar da isenção",
    "resultado_isencao_final": "Resultado final da isenção",
    "data_prova": "Data da prova",
}

# Estados temporais e de evidência.
STATES = (
    "futuro",
    "hoje",
    "expirado",
    "data_invalida",
    "sem_data",
)
STATE_LABELS = {
    "futuro": "Prazo futuro (vigência não comprovada)",
    "hoje": "Prazo vence hoje",
    "expirado": "Prazo passado (histórico preservado)",
    "data_invalida": "Data não interpretável",
    "sem_data": "Sem data extraída",
}
AUTHORITATIVE_TYPES = ("edital_abertura", "edital_retificado", "retificacao", "cronograma")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse(value):
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _publication(row):
    for candidate in (row.get("published_at"), row.get("fetched_at")):
        if isinstance(candidate, str) and len(candidate) >= 10:
            try:
                return datetime.fromisoformat(candidate[:10]).date()
            except ValueError:
                continue
    return None


def _mentions_field(quote: str, group: str) -> bool:
    """A retificação fala do prazo? Marcadores explícitos, não inferência.

    Início e fim têm marcadores próprios: "encerramento das inscrições" não é o início.
    """
    text = (quote or "").lower()
    markers = {
        "inscricao_inicio": ("início das inscri", "inicio das inscri",
                             "abertura das inscri", "período de inscri",
                             "periodo de inscri", "inscrições de", "inscricoes de"),
        "inscricao_fim": ("encerramento das inscri", "fim das inscri",
                          "término das inscri", "termino das inscri",
                          "último dia", "ultimo dia", "prazo de inscri",
                          "até o dia", "ate o dia"),
        "isencao_inicio": ("início da isen", "inicio da isen",
                           "isenção de", "isencao de", "período de isen",
                           "periodo de isen"),
        "isencao_fim": ("fim da isen", "encerramento da isen",
                        "término da isen", "termino da isen", "prazo da isen",
                        "isenção até", "isencao ate", "isenções até",
                        "isencoes ate"),
        "recurso_isencao": ("recurso", "isen"),
        "resultado_isencao_preliminar": ("resultado", "isen"),
        "resultado_isencao_final": ("resultado", "isen"),
        "data_prova": ("prova",),
    }.get(group, ())
    return any(marker in text for marker in markers)


def deadline_report(db_path, *, contest_id=None, group=None, state=None,
                    limit=200, offset=0, now=None) -> dict:
    """Relatório de prazos candidatos com evidência, retificação e situação temporal."""
    limit = int(limit)
    offset = int(offset)
    if limit < 1 or limit > 500:
        raise ValueError("limite fora da faixa")
    if offset < 0:
        raise ValueError("deslocamento inválido")
    if group and group not in DEADLINE_GROUPS:
        raise ValueError("grupo de prazo inválido")
    if state and state not in STATES:
        raise ValueError("estado temporal inválido")
    now_dt = datetime.fromisoformat(now) if isinstance(now, str) else (
        now or datetime.now(timezone.utc))
    # Mesma referência local do calendário operacional: uma data brasileira não expira
    # três horas antes por causa da meia-noite UTC.
    try:
        from zoneinfo import ZoneInfo
        today = (now_dt.astimezone(ZoneInfo("America/Recife")).date()
                 if now_dt.tzinfo else now_dt.date())
    except Exception:  # pragma: no cover - ambiente sem base IANA
        today = now_dt.astimezone().date() if now_dt.tzinfo else now_dt.date()

    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = review._rows(conn)
        reconciled = review._reconciled_map(conn)
        documents = {}
        for doc_contest_id, document_id, title, tipo, published in conn.execute(
                "SELECT contest_id, id, title, tipo_documental, published_at "
                "FROM documentos WHERE contest_id IS NOT NULL"):
            documents.setdefault(doc_contest_id, []).append(
                {"document_id": document_id, "title": title, "tipo_documental": tipo,
                 "published_at": published})
    by_contest = {}
    for row in rows:
        by_contest.setdefault(row["contest_id"], []).append(row)

    def _sem_data(cid, group_name, propostas, acao):
        return {
            "contest_id": cid, "grupo": group_name,
            "grupo_label": GROUP_LABELS[group_name],
            "estado": "sem_data", "estado_label": STATE_LABELS["sem_data"],
            "valor": None, "documento": None, "documento_id": None,
            "tipo_documental": None, "versao": None, "sha256": None, "pagina": None,
            "trecho": None, "publicado_em": None, "coletado_em": None,
            "escopo": None, "escopo_rotulo": None,
            "retificacao": None, "conflito": None, "propostas": propostas,
            "proxima_acao": acao, "decisao": None,
        }

    def _retificacao(cid, rows_group, group_name):
        """Atribui a alteração ao documento que de fato mudou o campo.

        Retificação posterior só altera quando a proposta **daquele documento** difere do
        edital de abertura do mesmo escopo. Documento que não fala do campo não é citado
        como causa da mudança.
        """
        abertura = [row for row in rows_group
                    if (row["tipo_documental"] or "") == "edital_abertura"]
        abertura.sort(key=lambda row: (_publication(row) or date.min, row["proposal_id"]))
        base_value = abertura[-1]["value_json"] if abertura else None
        retif_rows = [row for row in rows_group
                      if (row["tipo_documental"] or "") in
                      ("retificacao", "edital_retificado")]
        by_document = {}
        for row in retif_rows:
            by_document.setdefault(row["document_id"], []).append(row)
        changed, mentioned = [], []
        for document_rows in by_document.values():
            document_rows.sort(key=lambda row: (_publication(row) or date.min,
                                                row["proposal_id"]))
            representative = document_rows[-1]
            if base_value is not None and representative["value_json"] != base_value:
                changed.append(representative)
            elif any(_mentions_field(row["quote"], group_name) for row in document_rows):
                mentioned.append(representative)
        retif_documents = [doc for doc in documents.get(cid, [])
                           if (doc["tipo_documental"] or "") in
                           ("retificacao", "edital_retificado")]
        retif_documents.sort(key=lambda doc: (_parse(doc["published_at"]) or date.min,
                                              doc["document_id"]))
        if changed:
            changed.sort(key=lambda row: (_publication(row) or date.min,
                                          row["proposal_id"]))
            chosen = changed[-1]
            return {"documento": chosen["document_title"],
                    "documento_id": chosen["document_id"],
                    "publicado_em": chosen["published_at"],
                    "altera_o_prazo": True, "mencoes_ao_campo": True,
                    "valor_na_retificacao": json.loads(chosen["value_json"])
                    if chosen["value_json"] else None}
        if mentioned:
            mentioned.sort(key=lambda row: (_publication(row) or date.min,
                                            row["proposal_id"]))
            chosen = mentioned[-1]
            return {"documento": chosen["document_title"],
                    "documento_id": chosen["document_id"],
                    "publicado_em": chosen["published_at"],
                    "altera_o_prazo": False, "mencoes_ao_campo": True,
                    "valor_na_retificacao": None,
                    "leitura": ("retificação menciona o campo sem alterar o valor: "
                                "não há evidência de mudança")}
        if retif_documents:
            newest = retif_documents[-1]
            return {"documento": newest["title"],
                    "documento_id": newest["document_id"],
                    "publicado_em": newest["published_at"],
                    "altera_o_prazo": False, "mencoes_ao_campo": False,
                    "valor_na_retificacao": None,
                    "leitura": ("retificação do certame não menciona este prazo: "
                                "não há evidência de alteração")}
        return None

    items = []
    for cid, contest_rows in by_contest.items():
        if contest_id and cid != contest_id:
            continue
        for group_name, fields in DEADLINE_GROUPS.items():
            if group and group_name != group:
                continue
            proposals = [row for row in contest_rows if row["field_name"] in fields]
            if not proposals:
                continue
            # Proposta rejeitada não sustenta prazo; ela continua no histórico da revisão.
            open_proposals = [row for row in proposals if review._is_open(row)]
            authoritative = [row for row in open_proposals
                             if (row["tipo_documental"] or "") in AUTHORITATIVE_TYPES]
            if not authoritative:
                if open_proposals:
                    acao = ("nenhum documento autoritativo sustenta o prazo; "
                            "buscar edital/cronograma")
                else:
                    acao = ("todas as propostas deste prazo foram decididas; "
                            "buscar documento atualizado antes de usar")
                items.append(_sem_data(cid, group_name, len(proposals), acao))
                continue
            # Prazos de cargos diferentes não são o mesmo prazo: agrupa por escopo de cargo.
            by_scope = {}
            for row in authoritative:
                scope_ref, scope_label = review.role_scope(row, reconciled)
                by_scope.setdefault((scope_ref, scope_label), []).append(row)
            for (scope_ref, scope_label), scope_rows in by_scope.items():
                dated = sorted(
                    scope_rows,
                    key=lambda row: (_publication(row) or date.min, row["proposal_id"]))
                # Valor escolhido por humano vence a data de publicação.
                selected = [row for row in dated if row.get("selected")]
                vigente = selected[-1] if selected else dated[-1]
                value = json.loads(vigente["value_json"]) if vigente["value_json"] else None
                day = _parse(value) if isinstance(value, str) else None
                if day is None:
                    temporal = "data_invalida"
                elif day < today:
                    temporal = "expirado"
                elif day == today:
                    temporal = "hoje"
                else:
                    temporal = "futuro"

                retificacao = _retificacao(cid, scope_rows, group_name)
                conflict = None
                distinct = {row["value_json"] for row in scope_rows}
                if len(distinct) > 1:
                    # Divergência não escolhe vencedor: todas as leituras ficam visíveis.
                    by_value = {}
                    for row in scope_rows:
                        by_value.setdefault(row["value_json"], row)
                    conflict = {
                        "valores": len(distinct),
                        "propostas": len(scope_rows),
                        "candidatos": [
                            {
                                "valor": (json.loads(row["value_json"])
                                          if row["value_json"] else None),
                                "documento": row["document_title"],
                                "documento_id": row["document_id"],
                                "tipo_documental": row["tipo_documental"],
                                "publicado_em": row["published_at"],
                                "versao": row["version_id"],
                                "sha256": row["sha256"],
                                "pagina": row["page_number"],
                                "trecho": row["quote"],
                            }
                            for _, row in sorted(by_value.items(),
                                                 key=lambda pair: pair[1]["proposal_id"])
                        ],
                    }

                items.append({
                    "contest_id": cid, "grupo": group_name,
                    "grupo_label": GROUP_LABELS[group_name],
                    "estado": temporal, "estado_label": STATE_LABELS[temporal],
                    "valor": value,
                    "documento": vigente["document_title"],
                    "documento_id": vigente["document_id"],
                    "tipo_documental": vigente["tipo_documental"],
                    "versao": vigente["version_id"], "sha256": vigente["sha256"],
                    "pagina": vigente["page_number"], "trecho": vigente["quote"],
                    "publicado_em": vigente["published_at"],
                    "coletado_em": vigente.get("fetched_at"),
                    "official_url": vigente["official_url"],
                    "issuer": vigente["issuer"],
                    "escopo": scope_ref or None, "escopo_rotulo": scope_label,
                    "retificacao": retificacao, "conflito": conflict,
                    "propostas": len(scope_rows),
                    "proxima_acao": _next_action(temporal, retificacao, conflict),
                    "decisao": ({"decision": vigente["last_decision"],
                                 "reviewed_at": vigente["last_review_at"]}
                                if vigente["last_decision"] else None),
                })
    if state:
        items = [item for item in items if item["estado"] == state]
    items.sort(key=lambda item: (item["estado"] != "futuro", item["contest_id"],
                                 item["grupo"], item["escopo_rotulo"] or ""))
    total = len(items)
    by_state, by_group = {}, {}
    for item in items:
        by_state[item["estado"]] = by_state.get(item["estado"], 0) + 1
        by_group[item["grupo"]] = by_group.get(item["grupo"], 0) + 1
    return {
        "version": DEADLINE_VERSION, "generated_at": now_dt.isoformat(),
        "referencia": {"hoje": today.isoformat(), "agora": now_dt.isoformat()},
        "total": total, "por_estado": by_state, "por_grupo": by_group,
        "limit": limit, "offset": offset, "has_more": offset + limit < total,
        "itens": items[offset:offset + limit],
        "limitacao": ("Data futura não comprova vigência: a fonte precisa sustentar a "
                      "aplicabilidade. Retificação que não menciona o campo não altera o "
                      "prazo. Prazos de cargos diferentes são itens separados. Nada aqui "
                      "é confirmado automaticamente."),
    }


def _next_action(temporal, retificacao, conflict) -> str:
    if temporal == "expirado":
        if conflict:
            return "prazo passado com valores divergentes: revisar histórico e retificação"
        return "prazo passado: preservar como histórico; não usar como vigente"
    if temporal == "data_invalida":
        return "data não interpretável: conferir o trecho no documento"
    # Retificação que alterou o campo é a informação mais específica: vem antes do conflito.
    if retificacao and retificacao.get("altera_o_prazo"):
        if conflict:
            return ("retificação alterou o prazo; há valores divergentes: confirmar o "
                    "valor da retificação e resolver o conflito")
        return "retificação alterou o prazo: confirmar o valor da retificação"
    if conflict:
        return "resolver conflito entre documentos antes de usar o prazo"
    if retificacao and retificacao.get("mencoes_ao_campo"):
        return "retificação menciona o campo sem alterar o valor: confirmar leitura"
    if retificacao:
        return "retificação não menciona este prazo: candidato segue como está"
    return "revisar prazo no documento e confirmar"
