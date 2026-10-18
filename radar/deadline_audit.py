"""Auditoria de conflitos de prazo (Fase 37).

Responde, para um conflito, **por que** os candidatos divergem — sem escolher vencedor e
sem alterar nada:

- o trecho fala de inscrição, isenção, prova ou recurso?
- o extrator **atual** ainda produz esse valor a partir deste bloco?
- o offset armazenado ainda aponta para o mesmo lugar?
- o documento/versão é o mesmo para todos os candidatos?

Classificações (exclusivas, por candidato):

``inscricao`` / ``isencao`` / ``prova`` / ``recurso`` / ``outro``
    evento a que o trecho se refere, pelo marcador mais próximo na mesma frase.

``reproduzido`` / ``reproduzido_em_outro_offset`` / ``nao_reproduzido`` / ``sem_extrator``
    o extrator atual reproduz o par (campo, valor) deste bloco?

A causa do conflito é derivada dos candidatos (``_cause``) e nunca resolve o conflito: a
decisão continua humana, pelo fluxo de revisão existente.
"""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from radar import deadline_calendar, deadline_review, document_fields, edital_requirements
from radar.document_store import connect_documents, is_readable_schema

AUDIT_VERSION = "deadline_audit_v1"

EVENT_LABELS = {
    "inscricao": "Período de inscrição",
    "isencao": "Pedido de isenção",
    "prova": "Data de prova",
    "recurso": "Prazo de recurso",
    "outro": "Outro ato",
}

REPRODUCIBILITY_LABELS = {
    "reproduzido": "Reproduzido pelo extrator atual no mesmo offset",
    "reproduzido_em_outro_offset": "Valor reproduzido, mas o offset da evidência mudou",
    "nao_reproduzido": "Não reproduzido pelo extrator atual",
    "sem_extrator": "Campo sem extrator dedicado para auditoria",
}

CAUSE_LABELS = {
    "coerente": "Candidatos concordam; não há conflito a resolver",
    "evento_diferente": "Candidatos vêm de eventos diferentes (isenção/prova em vez de inscrição)",
    "extracao_obsoleta": "Extração antiga: o extrator atual não produz esse valor",
    "evidencia_deslocada": "Valor válido, mas o offset da evidência está desatualizado",
    "divergencia_real": "Dois ou mais valores do evento esperado divergem",
    "indeterminado": "Sem evidência suficiente para classificar a causa",
}

# Campo de prazo -> eventos aceitáveis do trecho. Recurso e resultado são etapas da
# isenção: o texto costuma dizer "recurso contra o resultado da isenção", e o marcador mais
# próximo pode ser qualquer um dos dois.
FIELD_EVENTS = {
    "registration_start": ("inscricao",),
    "registration_end": ("inscricao",),
    "exemption_start": ("isencao",),
    "exemption_end": ("isencao",),
    "exemption_appeal": ("isencao", "recurso"),
    "exemption_result_preliminary": ("isencao", "recurso"),
    "exemption_result_final": ("isencao", "recurso"),
    "exam_date": ("prova",),
}

GROUP_FIELDS = deadline_review.DEADLINE_GROUPS

def _now(now=None) -> datetime:
    if isinstance(now, str):
        return datetime.fromisoformat(now)
    return now or datetime.now(timezone.utc)


def _event_of(text: str, start: int, quote=None) -> tuple[str, str | None]:
    """Evento do trecho — mesma classificação do extrator, em modo diagnóstico.

    O extrator é conservador (ambiguidade = não atribui); aqui o objetivo é explicar,
    então vale o marcador mais próximo e a ambiguidade é sinalizada à parte.
    """
    return document_fields.event_marker(text, start, quote, strict=False)


def _reproducibility(field: str, value, block_text: str | None, start_offset) -> tuple[str, str]:
    """O extrator atual produz (campo, valor) deste bloco? Em que offset?"""
    if block_text is None:
        return "sem_extrator", "bloco de evidência não encontrado"
    if field in ("registration_start", "registration_end"):
        produced = document_fields._registration_dates(block_text)
    elif field in ("exemption_start", "exemption_end"):
        block = {"text": block_text, "page_number": 0}
        produced = [(item["field_name"], json.loads(item["value_json"]),
                     item["evidence"].get("quote"), item["evidence"].get("start_offset"),
                     item["evidence"].get("end_offset"))
                    for item in edital_requirements.extract_exemption_dates([block], "audit")]
    else:
        return "sem_extrator", "campo sem extrator dedicado para auditoria"
    for produced_field, produced_value, _quote, produced_start, _end in produced:
        if produced_field == field and produced_value == value:
            if start_offset is not None and produced_start == start_offset:
                return "reproduzido", "mesmo offset"
            return "reproduzido_em_outro_offset", (
                f"offset atual {produced_start}, armazenado {start_offset}")
    return "nao_reproduzido", "o extrator atual não produz este par (campo, valor)"


def _candidate_rows(conn, contest_id: str, group: str, escopo=None) -> list[dict]:
    """Todas as propostas do grupo, inclusive rejeitadas e duplicadas."""
    reconciled = deadline_review.review._reconciled_map(conn)
    fields = GROUP_FIELDS[group]
    placeholders = ",".join("?" for _ in fields)
    rows = conn.execute(
        f"""SELECT p.id AS proposal_id, p.field_name, p.value_json, p.ambiguity_reason,
                   p.extraction_method, p.role_id, p.extracted_at,
                   e.id AS evidence_id, e.quote, e.page_number, e.locator,
                   e.start_offset, e.end_offset, e.block_id,
                   v.id AS version_id, v.sha256, v.fetched_at,
                   d.id AS document_id, d.title, d.tipo_documental, d.published_at,
                   d.official_url, d.issuer,
                   (SELECT r.decision FROM revisoes_campo r WHERE r.proposal_id=p.id
                     ORDER BY r.reviewed_at DESC, r.rowid DESC LIMIT 1) AS last_decision,
                   (SELECT COUNT(*) FROM valores_atuais va WHERE va.proposal_id=p.id
                     AND va.id = (SELECT v2.id FROM valores_atuais v2
                                  WHERE v2.contest_id=p.contest_id
                                    AND v2.role_id IS p.role_id
                                    AND v2.field_name=p.field_name
                                  ORDER BY v2.selected_at DESC, v2.rowid DESC
                                  LIMIT 1)) AS selected
            FROM propostas_campo p
            JOIN evidencias e ON e.id=p.evidence_id
            JOIN versoes_documento v ON v.id=e.version_id
            JOIN documentos d ON d.id=v.document_id
            WHERE p.contest_id=? AND p.field_name IN ({placeholders})
            ORDER BY d.published_at, e.page_number, e.start_offset""",
        [contest_id, *fields]).fetchall()
    out = []
    for row in rows:
        scope_ref, scope_label = deadline_review.review.role_scope(
            {"role_id": row["role_id"], "contest_id": contest_id,
             "ambiguity_reason": row["ambiguity_reason"]}, reconciled)
        if escopo and scope_ref != escopo:
            continue
        out.append({
            "proposal_id": row["proposal_id"], "field_name": row["field_name"],
            "value": json.loads(row["value_json"]) if row["value_json"] else None,
            "value_json": row["value_json"],
            "quote": row["quote"] or "", "page_number": row["page_number"],
            "locator": row["locator"],
            "start_offset": row["start_offset"], "end_offset": row["end_offset"],
            "block_id": row["block_id"], "evidence_id": row["evidence_id"],
            "version_id": row["version_id"], "sha256": row["sha256"],
            "fetched_at": row["fetched_at"],
            "document_id": row["document_id"], "document_title": row["title"],
            "tipo_documental": row["tipo_documental"],
            "published_at": row["published_at"], "official_url": row["official_url"],
            "issuer": row["issuer"], "extraction_method": row["extraction_method"],
            "extracted_at": row["extracted_at"],
            "scope": scope_ref, "scope_label": scope_label,
            "last_decision": row["last_decision"],
            "selected": bool(row["selected"]),
            "is_open": deadline_review.review._is_open(
                {"last_decision": row["last_decision"], "selected": bool(row["selected"])}),
        })
    return out


def _block_text(conn, block_id) -> str | None:
    if not block_id:
        return None
    row = conn.execute("SELECT text FROM blocos_documento WHERE id=?", (block_id,)).fetchone()
    return row[0] if row else None


def _cause(candidates: list[dict], expected_events) -> tuple[str, list[str]]:
    """Causa derivada dos candidatos. Nunca escolhe valor nem resolve o conflito."""
    if isinstance(expected_events, str):
        expected_events = (expected_events,)
    open_candidates = [item for item in candidates if item["is_open"]]
    if len(open_candidates) < 2:
        return "coerente", []
    # Sem valores distintos não há conflito: a ficha de um prazo limpo não deve sugerir
    # causa de conflito nem propor rejeição.
    if len({json.dumps(item["value"]) for item in open_candidates}) <= 1:
        return "coerente", []
    causes = []
    # Candidato de outro evento é o achado mais forte: o trecho não é deste prazo.
    wrong_event = [item for item in open_candidates
                   if item["event"] not in (*expected_events, "outro")]
    if wrong_event:
        causes.append("evento_diferente")
    # Sustentado = evento correto. Reprodutibilidade é qualidade da evidência, não
    # elegibilidade: o extrator pode não cobrir um formato e o valor continuar válido.
    supported = {json.dumps(item["value"]) for item in open_candidates
                 if item["event"] in expected_events}
    if len(supported) > 1:
        causes.append("divergencia_real")
    stale = [item for item in open_candidates
             if item["event"] in expected_events
             and item["reproducibility"] == "nao_reproduzido"]
    if stale:
        causes.append("extracao_obsoleta")
    displaced = [item for item in open_candidates
                 if item["reproducibility"] == "reproduzido_em_outro_offset"]
    if displaced and len(supported) <= 1:
        causes.append("evidencia_deslocada")
    if not causes:
        if len({json.dumps(item["value"]) for item in open_candidates}) <= 1:
            return "coerente", []
        return "indeterminado", ["candidatos sem classificação suficiente"]
    return causes[0], causes


def _explanation(candidates: list[dict], expected_events, cause: str) -> str:
    if isinstance(expected_events, str):
        expected_events = (expected_events,)
    open_candidates = [item for item in candidates if item["is_open"]]
    if cause == "evento_diferente":
        wrong = [item for item in open_candidates
                 if item["event"] not in (*expected_events, "outro")]
        events = sorted({EVENT_LABELS[item["event"]] for item in wrong})
        return ("Parte dos candidatos não é do prazo em questão: o trecho trata de "
                + ", ".join(events).lower() + ". O valor não foi escolhido; a proposta de "
                "correção precisa de decisão humana.")
    if cause == "extracao_obsoleta":
        return ("O extrator atual não reproduz parte dos candidatos a partir do mesmo bloco: "
                "são extrações antigas, anteriores à regra de contexto. Nenhuma proposta é "
                "apagada; rejeitar é decisão humana.")
    if cause == "evidencia_deslocada":
        return ("Os valores são reproduzíveis, mas o offset armazenado da evidência não "
                "corresponde ao trecho atual do bloco. A leitura vale; o localizador precisa "
                "de correção.")
    if cause == "divergencia_real":
        verified = {json.dumps(item["value"]) for item in open_candidates
                    if item["event"] in expected_events
                    and item["reproducibility"] in ("reproduzido",
                                                    "reproduzido_em_outro_offset")}
        base = ("Dois ou mais valores do evento esperado divergem entre documentos: há "
                "divergência documental real e ela permanece pendente de decisão humana.")
        if len(verified) < 2:
            base += (" A verificação automática do extrator cobre apenas parte dos valores; "
                     "conferir os trechos manualmente.")
        return base
    unclassified = [item for item in open_candidates if item["event"] == "outro"]
    if unclassified:
        return ("Há candidato cujo trecho não permite classificar o evento (linha de "
                "cronograma ou citação sem contexto). O valor não foi escolhido: conferir "
                "manualmente antes de decidir.")
    return "A evidência disponível não permite classificar a causa."


def case_file(db_path, *, contest_id: str, group: str, escopo=None, now=None) -> dict:
    """Ficha de decisão de um prazo: candidatos, evidência, causa e correção proposta."""
    if group not in GROUP_FIELDS:
        raise ValueError("grupo de prazo inválido")
    now_dt = _now(now)
    with closing(connect_documents(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        exists = conn.execute("SELECT 1 FROM concursos_identidade WHERE id=?",
                              (contest_id,)).fetchone()
        if not exists:
            raise ValueError("concurso inexistente")
        candidates = _candidate_rows(conn, contest_id, group, escopo)
        blocks = {}
        for item in candidates:
            if item["block_id"] not in blocks:
                blocks[item["block_id"]] = _block_text(conn, item["block_id"])
        revalidations = deadline_calendar._last_revalidations(conn)
        observations = [dict(source_url=row[0], competition_id=row[1])
                        for row in conn.execute(
                            "SELECT source_url, competition_id FROM observacoes_concurso "
                            "WHERE contest_id=? ORDER BY source_url", (contest_id,))]
        documents = [{"document_id": row[0], "title": row[1], "tipo_documental": row[2],
                      "published_at": row[3], "official_url": row[4],
                      "sha256": row[5], "versao": row[6]}
                     for row in conn.execute(
                         """SELECT d.id, d.title, d.tipo_documental, d.published_at,
                                   d.official_url, v.sha256, v.id
                            FROM documentos d
                            LEFT JOIN versoes_documento v ON v.document_id=d.id
                            WHERE d.contest_id=? ORDER BY d.published_at, d.discovered_at""",
                         (contest_id,))]

    expected_events = FIELD_EVENTS.get(GROUP_FIELDS[group][0], ("outro",))
    expected_event = expected_events[0]
    for item in candidates:
        text = blocks.get(item["block_id"])
        event, marker = (_event_of(text, item["start_offset"] or 0, item["quote"])
                         if text else ("outro", None))
        item["event"] = event
        item["event_label"] = EVENT_LABELS[event]
        item["event_marker"] = marker
        item["event_ambiguous"] = (document_fields.event_ambiguous(text, item["start_offset"] or 0,
                                                                 item["quote"])
                                   if text else False)
        if text:
            item["context_before"] = text[max(0, (item["start_offset"] or 0) - 300):
                                          (item["start_offset"] or 0)]
            item["context_after"] = text[(item["end_offset"] or 0):
                                         (item["end_offset"] or 0) + 300]
        else:
            item["context_before"] = item["context_after"] = None
        reproducibility, detail = _reproducibility(
            item["field_name"], item["value"], text, item["start_offset"])
        item["reproducibility"] = reproducibility
        item["reproducibility_label"] = REPRODUCIBILITY_LABELS[reproducibility]
        item["reproducibility_detail"] = detail
        # Escopo vazio ("") e nulo são o mesmo escopo de concurso.
        scope_key = item["scope"] or None
        item["revalidacao"] = revalidations.get(
            (contest_id, group, scope_key, item["version_id"]))

    cause, causes = _cause(candidates, expected_events)
    open_candidates = [item for item in candidates if item["is_open"]]
    wrong_event = [item for item in open_candidates
                   if item["event"] not in (*expected_events, "outro")]
    not_reproduced = [item for item in open_candidates
                      if item["event"] in expected_events
                      and item["reproducibility"] == "nao_reproduzido"]
    wrong = wrong_event + not_reproduced
    supported = sorted({json.dumps(item["value"]) for item in open_candidates
                        if item["event"] in expected_events})
    verified = sorted({json.dumps(item["value"]) for item in open_candidates
                       if item["event"] in expected_events
                       and item["reproducibility"] in ("reproduzido",
                                                       "reproduzido_em_outro_offset")})
    # Um valor já sustentado por outra proposta não é "não classificado".
    unclassified = sorted({json.dumps(item["value"]) for item in open_candidates
                           if item["event"] == "outro"} - set(supported))
    if cause == "evento_diferente":
        action = ("conferir o trecho de cada candidato e rejeitar, por decisão humana, as "
                  "propostas que pertencem a outro evento")
    elif cause == "extracao_obsoleta":
        action = ("reprocessar o documento ou rejeitar, por decisão humana, as propostas que "
                  "o extrator atual não reproduz")
    elif cause == "evidencia_deslocada":
        action = "atualizar o localizador da evidência mantendo o valor"
    elif cause == "divergencia_real":
        action = "comparar os documentos e decidir o valor com justificativa"
    else:
        action = "conferir manualmente os trechos antes de qualquer decisão"

    # Verificações registradas para as versões deste caso (qualquer escopo do grupo).
    version_ids = {item["version_id"] for item in candidates}
    verificacoes = [dict(revalidation, version_id=key[3])
                    for key, revalidation in revalidations.items()
                    if key[0] == contest_id and key[1] == group
                    and key[3] in version_ids]
    verificacoes.sort(key=lambda entry: entry["checked_at"], reverse=True)
    return {
        "version": AUDIT_VERSION, "generated_at": now_dt.isoformat(),
        "contest_id": contest_id, "grupo": group,
        "grupo_label": deadline_review.GROUP_LABELS[group],
        "escopo": escopo, "evento_esperado": expected_event,
        "evento_esperado_label": EVENT_LABELS[expected_event],
        "observacoes": observations, "documentos": documents,
        "verificacoes": verificacoes,
        "candidatos": candidates,
        "abertas": len(open_candidates), "rejeitadas": len(candidates) - len(open_candidates),
        "causa": cause, "causa_label": CAUSE_LABELS[cause], "causas": causes,
        "explicacao": _explanation(candidates, expected_events, cause),
        "eventos_aceitos": list(expected_events),
        "verificacao_manual": any(item["reproducibility"] == "sem_extrator"
                                  for item in open_candidates),
        "valores_sustentados": [json.loads(value) for value in supported],
        "valores_verificados": [json.loads(value) for value in verified],
        "valores_nao_classificados": [json.loads(value) for value in unclassified],
        "proposta_correcao": {
            "acao": action,
            "propostas_para_rejeitar": [item["proposal_id"] for item in wrong_event],
            "propostas_sem_reproducao": [item["proposal_id"] for item in not_reproduced],
            "requer_decisao_humana": True,
            "nao_executado": True,
            "nota": ("Proposta de correção não é decisão: nada é alterado até uma revisão "
                     "humana explícita no fluxo existente."),
        },
        "limitacao": ("Fonte inalterada não confirma prazo. A auditoria não escolhe valor, "
                      "não altera propostas e não cria decisões."),
    }


def audit_conflicts(db_path, *, contest_id=None, group=None, cause=None, limit=100,
                    offset=0, now=None) -> dict:
    """Todos os conflitos de prazo com causa auditada e contagens reconciliadas."""
    limit = int(limit)
    offset = int(offset)
    if limit < 1 or limit > 500:
        raise ValueError("limite fora da faixa")
    if offset < 0:
        raise ValueError("deslocamento inválido")
    if group and group not in GROUP_FIELDS:
        raise ValueError("grupo de prazo inválido")
    if cause and cause not in CAUSE_LABELS:
        raise ValueError("causa inválida")
    now_dt = _now(now)
    items, offset_cal = [], 0
    while True:
        page = deadline_calendar.calendar(db_path, limit=500, offset=offset_cal,
                                          now=now_dt)
        items.extend(item for item in page["itens"] if item["conflito"])
        if not page["has_more"] or offset_cal > 20000:
            break
        offset_cal += page["limit"]
    if contest_id:
        items = [item for item in items if item["contest_id"] == contest_id]
    if group:
        items = [item for item in items if item["grupo"] == group]
    audited = []
    for item in items:
        case = case_file(db_path, contest_id=item["contest_id"], group=item["grupo"],
                         escopo=item.get("escopo"), now=now_dt)
        audited.append({
            "contest_id": item["contest_id"], "grupo": item["grupo"],
            "grupo_label": item["grupo_label"],
            "escopo": item.get("escopo"), "escopo_rotulo": item.get("escopo_rotulo"),
            "estado_temporal": item["estado_temporal"],
            "valores": [candidate["valor"] for candidate in item["candidatos"]],
            "causa": case["causa"], "causa_label": case["causa_label"],
            "causas": case["causas"], "explicacao": case["explicacao"],
            "valores_sustentados": case["valores_sustentados"],
            "abertas": case["abertas"], "rejeitadas": case["rejeitadas"],
            "proxima_acao": case["proposta_correcao"]["acao"],
        })
    if cause:
        audited = [item for item in audited if item["causa"] == cause]
    audited.sort(key=lambda item: (item["estado_temporal"] != "futuro",
                                   item["contest_id"], item["grupo"]))
    total = len(audited)
    by_cause, by_temporal = {}, {}
    for item in audited:
        by_cause[item["causa"]] = by_cause.get(item["causa"], 0) + 1
        by_temporal[item["estado_temporal"]] = by_temporal.get(item["estado_temporal"], 0) + 1
    return {
        "version": AUDIT_VERSION, "generated_at": now_dt.isoformat(),
        "total": total, "por_causa": by_cause, "por_temporal": by_temporal,
        "limit": limit, "offset": offset, "has_more": offset + limit < total,
        "itens": audited[offset:offset + limit],
        "limitacao": ("Causa é diagnóstica: não escolhe valor nem resolve o conflito. "
                      "A correção exige decisão humana."),
    }
