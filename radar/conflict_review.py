"""Revisão assistida de conflitos entre propostas (Fase 35).

Um "conflito" na fila é apenas **valores diferentes no mesmo escopo**. A causa pode ser
muito diferente: retificação posterior, variação de extração, escopo distinto (local de
prova × "a divulgar") ou divergência real que exige decisão humana.

Este módulo classifica a causa com evidência (documento, data, versão, trecho) e propõe a
próxima ação. Não escolhe valor, não sobrescreve por recência e não apaga a proposta
anterior: a decisão continua em ``review.decide_proposal`` / ``review.select_current_value``.
"""

from __future__ import annotations

import json
import re
import unicodedata
from contextlib import closing
from datetime import datetime, timezone

from radar import review
from radar.document_store import connect_documents, is_readable_schema

CONFLICT_REVIEW_VERSION = "conflict_review_v1"

CAUSES = (
    "escopo_diferente",
    "cargos_diferentes_sem_identificacao",
    "variacao_de_extracao",
    "retificacao_posterior",
    "documentos_com_data_distinta",
    "documentos_diferentes_sem_ordem",
    "mesmo_documento_valores_distintos",
    "evidencia_insuficiente",
)
CAUSE_LABELS = {
    "escopo_diferente": "Escopos diferentes (ex.: 'a divulgar' × local concreto)",
    "cargos_diferentes_sem_identificacao":
        "Valores de cargos diferentes (propostas sem identificação de cargo)",
    "variacao_de_extracao": "Variação de extração do mesmo texto",
    "retificacao_posterior": "Documento posterior (retificação/edital retificado) altera o valor",
    "documentos_com_data_distinta": "Documentos diferentes com datas distintas",
    "documentos_diferentes_sem_ordem": "Documentos diferentes sem ordem temporal confiável",
    "mesmo_documento_valores_distintos": "O mesmo documento traz valores diferentes",
    "evidencia_insuficiente": "Evidência insuficiente para concluir",
}
NEXT_ACTIONS = {
    "escopo_diferente": "não é divergência de valor: registrar a distinção de escopo na revisão",
    "cargos_diferentes_sem_identificacao":
        "identificar o cargo de cada requisito antes de comparar (não são valores rivais)",
    "variacao_de_extracao": "escolher a extração fiel ao documento (o texto é o mesmo)",
    "retificacao_posterior": "confirmar o valor da retificação, mantendo o anterior como histórico",
    "documentos_com_data_distinta": "comparar os documentos e decidir qual sustenta o campo",
    "documentos_diferentes_sem_ordem": "revisar os documentos; sem ordem não há valor vigente",
    "mesmo_documento_valores_distintos": "revisar o documento: um dos valores está incorreto",
    "evidencia_insuficiente": "buscar evidência antes de decidir",
}

LOCATION_FIELDS = ("exam_location", "exam_municipio", "exam_uf", "work_location",
                   "work_municipio", "work_uf")
AUTHORITATIVE_TYPES = ("edital_abertura", "edital_retificado", "retificacao", "cronograma")

# Prioridade de revisão: o que muda a decisão do candidato primeiro.
FIELD_PRIORITY = {
    "indigenous_vacancies": 1, "indigenous_reserve_vacancies": 1,
    "education": 2, "accepted_courses": 2, "si_compatibility": 2,
    "registration_start": 3, "registration_end": 3, "exemption_start": 3,
    "exemption_end": 3, "exemption_appeal": 3, "exemption_result_preliminary": 3,
    "exam_location": 4, "exam_municipio": 4, "exam_uf": 4,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_value(value) -> str:
    """Normaliza para comparar texto extraído do mesmo trecho (não para decidir)."""
    if not isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    text = value.replace("[...]", " ").replace("…", " ")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text).strip(" .,;:-–—")
    return text.lower()


def _doc_day(row):
    for candidate in (row.get("published_at"), row.get("fetched_at")):
        if isinstance(candidate, str) and len(candidate) >= 10:
            try:
                return datetime.fromisoformat(candidate[:10]).date()
            except ValueError:
                continue
    return None


def classify_group(items: list[dict], field: str,
                   scope=None) -> tuple[str, list[str], dict]:
    """Causa do conflito + motivos + dados auxiliares (vigente candidato, quando houver)."""
    reasons = []
    extra = {}
    if not items:
        return "evidencia_insuficiente", ["grupo vazio"], extra
    values = [item["value_json"] for item in items]
    normalized = {_norm_value(json.loads(v)) for v in values}
    if any(not item.get("quote") for item in items):
        reasons.append("há proposta sem trecho literal")
        if any(not item.get("quote") for item in items):
            return "evidencia_insuficiente", reasons, extra

    if field in LOCATION_FIELDS:
        raw = [json.loads(v) for v in values]
        if any(isinstance(v, str) and v.strip().lower() in ("a_divulgar", "a divulgar")
               for v in raw):
            concrete = [v for v in raw if not (isinstance(v, str)
                                               and v.strip().lower() in ("a_divulgar",
                                                                          "a divulgar"))]
            if len({_norm_value(v) for v in concrete}) <= 1:
                reasons.append("um documento declara publicação futura e outro cita local")
                return "escopo_diferente", reasons, extra

    if len(normalized) == 1:
        reasons.append("os valores são o mesmo texto após normalização "
                       "(truncamento/[...] ou pontuação)")
        return "variacao_de_extracao", reasons, extra

    # Sem escopo de cargo e com requisitos distintos, os valores são de cargos diferentes:
    # comparar como se fossem o mesmo campo inventaria divergência.
    if not scope and field in ("education", "accepted_courses", "si_compatibility"):
        reasons.append("propostas sem cargo identificado; os trechos descrevem requisitos "
                       "distintos")
        return "cargos_diferentes_sem_identificacao", reasons, extra

    documents = {}
    for item in items:
        documents.setdefault(item["document_id"], {
            "document_id": item["document_id"], "title": item["document_title"],
            "tipo_documental": item["tipo_documental"],
            "published_at": item["published_at"], "version_id": item["version_id"],
            "sha256": item["sha256"],
        })
    if len(documents) == 1:
        reasons.append("todas as propostas vêm do mesmo documento")
        return "mesmo_documento_valores_distintos", reasons, extra

    # Ato posterior por natureza: retificação/edital retificado vêm depois do edital de
    # abertura, ainda que a data de publicação não esteja registrada. Continua candidato.
    types = {(doc["tipo_documental"] or "") for doc in documents.values()}
    if "edital_abertura" in types and types & {"retificacao", "edital_retificado"}:
        newer = [item for item in items
                 if (item["tipo_documental"] or "") in ("retificacao", "edital_retificado")]
        opening_values = {item["value_json"] for item in items
                          if (item["tipo_documental"] or "") == "edital_abertura"}
        retif_values = {item["value_json"] for item in newer}
        # Só há retificação posterior se o ato posterior **difere** do edital de abertura.
        # Repetir o mesmo valor não é alteração; a divergência está em outro documento.
        if newer and len(retif_values) == 1 and not (retif_values & opening_values):
            reasons.append("retificação posterior ao edital de abertura altera o valor do campo")
            extra["vigente_candidato"] = newer[0]["proposal_id"]
            extra["vigente_documento"] = newer[0]["document_title"]
            return "retificacao_posterior", reasons, extra
        reasons.append("ato posterior repete o valor do edital de abertura; a divergência "
                       "está nos demais documentos")

    dated = {doc_id: _doc_day(doc) for doc_id, doc in documents.items()}
    if all(day is not None for day in dated.values()):
        latest = max(dated.values())
        newest = [item for item in items if dated.get(item["document_id"]) == latest]
        newest_values = {item["value_json"] for item in newest}
        newest_doc = documents[newest[0]["document_id"]]
        if (len(newest_values) == 1
                and (newest_doc["tipo_documental"] or "") in AUTHORITATIVE_TYPES):
            reasons.append(f"documento mais recente ({newest_doc['title']}) é ato autoritativo "
                           "e traz um único valor")
            extra["vigente_candidato"] = newest[0]["proposal_id"]
            extra["vigente_documento"] = newest_doc["title"]
            # Só é retificação posterior quando o documento mais novo é, de fato, ato
            # retificatório; cronograma/comunicado mais novo é apenas documento com data.
            if (newest_doc["tipo_documental"] or "") in ("retificacao",
                                                            "edital_retificado"):
                return "retificacao_posterior", reasons, extra
            return "documentos_com_data_distinta", reasons, extra
        reasons.append("documentos têm datas distintas, mas o mais recente não é ato "
                       "autoritativo ou traz mais de um valor")
        return "documentos_com_data_distinta", reasons, extra

    reasons.append("documentos diferentes sem data de publicação confiável")
    return "documentos_diferentes_sem_ordem", reasons, extra


def _proposal_view(item) -> dict:
    return {
        "proposal_id": item["proposal_id"],
        "value": review._value_of(item["value_json"]),
        "state": review._state(item["last_decision"], item["selected"]),
        "document_id": item["document_id"],
        "document_title": item["document_title"],
        "tipo_documental": item["tipo_documental"],
        "published_at": item["published_at"],
        "version_id": item["version_id"],
        "sha256": item["sha256"],
        "page_number": item["page_number"],
        "quote": item["quote"],
        "extraction_method": item["extraction_method"],
        "fetched_at": item.get("fetched_at"),
    }


def conflict_groups(db_path, *, contest_id=None, field=None, cause=None, priority=None,
                    limit=100, offset=0) -> dict:
    """Grupos de conflito classificados, com evidência e próxima ação."""
    limit = int(limit)
    offset = int(offset)
    if limit < 1 or limit > 500:
        raise ValueError("limite fora da faixa")
    if offset < 0:
        raise ValueError("deslocamento inválido")
    if cause and cause not in CAUSES:
        raise ValueError("causa inválida")
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = review._rows(conn)
        reconciled = review._reconciled_map(conn)
    conflicts = review._conflicts(rows, reconciled)

    items = []
    for (cid, scope, field_name), group in conflicts.items():
        if contest_id and cid != contest_id:
            continue
        if field and field_name != field:
            continue
        classified, reasons, extra = classify_group(group, field_name, scope)
        if cause and classified != cause:
            continue
        rank = FIELD_PRIORITY.get(field_name, 5)
        if priority is not None and rank != int(priority):
            continue
        documents = {}
        for proposal in group:
            documents.setdefault(proposal["document_id"], {
                "document_id": proposal["document_id"],
                "title": proposal["document_title"],
                "tipo_documental": proposal["tipo_documental"],
                "published_at": proposal["published_at"],
                "version_id": proposal["version_id"],
            })
        items.append({
            "contest_id": cid, "scope": scope, "field_name": field_name,
            "cause": classified, "cause_label": CAUSE_LABELS[classified],
            "motivos": reasons, "prioridade": rank,
            "proxima_acao": NEXT_ACTIONS[classified],
            "valores_distintos": len({proposal["value_json"] for proposal in group}),
            "propostas": [_proposal_view(proposal) for proposal in group],
            "documentos": list(documents.values()),
            "vigente_candidato": extra.get("vigente_candidato"),
            "vigente_documento": extra.get("vigente_documento"),
        })
    items.sort(key=lambda item: (item["prioridade"], item["cause"], item["contest_id"],
                                 str(item["scope"]), item["field_name"]))
    total = len(items)
    by_cause, by_priority = {}, {}
    for item in items:
        by_cause[item["cause"]] = by_cause.get(item["cause"], 0) + 1
        by_priority[str(item["prioridade"])] = by_priority.get(
            str(item["prioridade"]), 0) + 1
    return {
        "version": CONFLICT_REVIEW_VERSION, "generated_at": _now(),
        "total": total, "por_causa": by_cause, "por_prioridade": by_priority,
        "limit": limit, "offset": offset, "has_more": offset + limit < total,
        "itens": items[offset:offset + limit],
        "limitacao": ("Classificação por evidência (documento, data, tipo, trecho). "
                      "'retificacao_posterior' é candidato, não valor vigente: a decisão é "
                      "humana e a proposta anterior permanece no histórico."),
    }
