"""Calendário operacional de prazos (Fase 36).

O relatório da Fase 35 responde "que prazos existem e qual a situação temporal". Esta camada
responde "o que fazer com cada prazo agora", sem transformar candidato em fato:

- data futura continua sendo **candidato**, não prova de inscrição aberta;
- prazo com valores divergentes **não recebe um valor único** — todos os candidatos ficam
  visíveis com evidência e a decisão permanece humana;
- retificação que alterou o campo é estado próprio, não "prazo atual";
- verificação contra a fonte oficial só é registrada quando o documento servido hoje é
  byte-idêntico ao da coleta, e isso **não** confirma o prazo.

Nada aqui escreve na base. A única escrita da fase é ``deadline_revalidation``, append-only.
"""

from __future__ import annotations

from contextlib import closing
from datetime import date, datetime, timedelta, timezone

from radar import coverage_states, deadline_review, source_catalog, source_policy
from radar.document_store import connect_documents, is_readable_schema

CALENDAR_VERSION = "deadline_calendar_v1"

try:  # Windows sem tzdata usa o deslocamento fixo de Recife (sem horário de verão).
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("America/Recife")
except Exception:  # pragma: no cover - ambiente sem base IANA
    LOCAL_TZ = timezone(timedelta(hours=-3))

# Estados operacionais. Exclusivos, com precedência declarada em ``_operational_state``.
OPERATIONAL_STATES = (
    "nao_localizado",
    "data_ilegivel",
    "conflito_documental",
    "alterado_por_retificacao",
    "passado_com_evidencia",
    "revalidado_na_fonte",
    "fonte_nao_confirmada",
    "candidato_nao_revalidado",
)
STATE_LABELS = {
    "nao_localizado": "Prazo não localizado na documentação disponível",
    "data_ilegivel": "Data ilegível ou não interpretável",
    "conflito_documental": "Conflito documental: valores divergentes, decisão pendente",
    "alterado_por_retificacao": "Retificação alterou o prazo: confirmar leitura",
    "passado_com_evidencia": "Prazo passado, preservado como histórico",
    "revalidado_na_fonte": "Documento oficial inalterado desde a coleta (prazo não confirmado)",
    "fonte_nao_confirmada": "Fonte ou identidade não confirmada",
    "candidato_nao_revalidado": "Candidato futuro, ainda não revalidado na fonte",
}

URGENCIES = ("vencido", "hoje", "ate_7_dias", "ate_30_dias", "futuro", "sem_data")
URGENCY_LABELS = {
    "vencido": "Vencido",
    "hoje": "Vence hoje",
    "ate_7_dias": "Até 7 dias",
    "ate_30_dias": "Até 30 dias",
    "futuro": "Futuro (mais de 30 dias)",
    "sem_data": "Sem data",
}

# Ordem de prioridade operacional: fechar inscrição impede candidatura hoje.
GROUP_PRIORITY = {
    "inscricao_fim": 1,
    "isencao_fim": 2,
    "isencao_inicio": 3,
    "recurso_isencao": 4,
    "inscricao_inicio": 5,
    "resultado_isencao_preliminar": 6,
    "resultado_isencao_final": 6,
    "data_prova": 7,
}

ACTION_BY_STATE = {
    "nao_localizado": "buscar edital/cronograma que traga o prazo",
    "data_ilegivel": "conferir o trecho no documento e corrigir a leitura",
    "conflito_documental": "comparar os valores divergentes e decidir com evidência",
    "alterado_por_retificacao": "confirmar o valor da retificação antes de usar",
    "passado_com_evidencia": "preservar como histórico; não usar como prazo vigente",
    "revalidado_na_fonte": "documento inalterado; confirmar a leitura do prazo",
    "fonte_nao_confirmada": "confirmar a fonte oficial antes de revalidar",
    "candidato_nao_revalidado": "revalidar na fonte oficial antes de tratar como aberto",
}


def _now(now=None) -> datetime:
    if isinstance(now, str):
        return datetime.fromisoformat(now)
    return now or datetime.now(timezone.utc)


def _local_today(now_dt: datetime) -> date:
    if now_dt.tzinfo is None:
        return now_dt.date()
    return now_dt.astimezone(LOCAL_TZ).date()


def _days(value, today: date):
    day = deadline_review._parse(value) if isinstance(value, str) else None
    return (day - today).days if day else None


def _urgency(temporal: str, days):
    if temporal == "sem_data":
        return "sem_data"
    if days is None:
        return "sem_data"
    if days < 0:
        return "vencido"
    if days == 0:
        return "hoje"
    if days <= 7:
        return "ate_7_dias"
    if days <= 30:
        return "ate_30_dias"
    return "futuro"


def _source_info(official_url, issuer, pairs):
    source = coverage_states._source_for(coverage_states._host(official_url), pairs, issuer)
    if not source:
        return {"id": None, "label": None, "policy": None}
    try:
        policy = source_policy.decision(source["id"], "documento")
    except Exception:
        policy = None
    return {"id": source["id"], "label": source.get("label"),
            "policy": policy}


def _last_revalidations(conn) -> dict:
    """Última verificação por (concurso, grupo, escopo, versão)."""
    present = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='revalidacoes_prazo'"
    ).fetchone()
    if not present:
        return {}
    latest = {}
    for row in conn.execute(
            """SELECT contest_id,grupo,escopo,version_id,checked_at,result,
                      stored_sha256,observed_sha256,http_status
               FROM revalidacoes_prazo ORDER BY checked_at, rowid"""):
        latest[(row[0], row[1], row[2], row[3])] = {
            "checked_at": row[4], "result": row[5], "stored_sha256": row[6],
            "observed_sha256": row[7], "http_status": row[8],
        }
    return latest


def _operational_state(item, revalidation, source) -> str:
    if item["estado"] == "sem_data":
        return "nao_localizado"
    if item["estado"] == "data_invalida":
        return "data_ilegivel"
    retif_changes = bool(item["retificacao"]
                         and item["retificacao"].get("altera_o_prazo"))
    distinct = (item["conflito"] or {}).get("valores", 0)
    # Retificação resolve a divergência apenas quando o único valor anterior é o edital de
    # abertura. Com três leituras (abertura + retificação + outro ato), há conflito real.
    if retif_changes and distinct <= 2:
        return "alterado_por_retificacao"
    if item["conflito"]:
        return "conflito_documental"
    if item["estado"] == "expirado":
        return "passado_com_evidencia"
    if (revalidation and revalidation["result"] == "fonte_inalterada"
            and revalidation["observed_sha256"] == item.get("sha256")):
        return "revalidado_na_fonte"
    policy = (source or {}).get("policy") or {}
    if not source or not source.get("id") or not policy.get("allowed"):
        return "fonte_nao_confirmada"
    return "candidato_nao_revalidado"


def _item_view(item, today: date, revalidation, source) -> dict:
    state = _operational_state(item, revalidation, source)
    resolved = state != "conflito_documental"
    days = _days(item["valor"], today) if resolved else None
    urgency = _urgency(item["estado"], days)
    conflict = item["conflito"] or {}
    return {
        "contest_id": item["contest_id"],
        "grupo": item["grupo"], "grupo_label": item["grupo_label"],
        "prioridade_grupo": GROUP_PRIORITY.get(item["grupo"], 9),
        "escopo": item.get("escopo"), "escopo_rotulo": item.get("escopo_rotulo"),
        "estado_operacional": state, "estado_operacional_label": STATE_LABELS[state],
        "estado_temporal": item["estado"],
        "valor": item["valor"] if resolved else None,
        "valor_candidato": None if state == "conflito_documental" else item["valor"],
        "dias_restantes": days,
        "urgencia": urgency, "urgencia_label": URGENCY_LABELS[urgency],
        "documento": item["documento"], "documento_id": item.get("documento_id"),
        "tipo_documental": item.get("tipo_documental"),
        "versao": item.get("versao"), "sha256": item.get("sha256"),
        "pagina": item.get("pagina"), "trecho": item.get("trecho"),
        "publicado_em": item.get("publicado_em"),
        "coletado_em": item.get("coletado_em"),
        "official_url": item.get("official_url"),
        "fonte": source,
        "retificacao": item.get("retificacao"),
        "conflito": conflict or None,
        "candidatos": (conflict.get("candidatos")
                       if conflict else ([{"valor": item["valor"],
                                           "documento": item.get("documento"),
                                           "documento_id": item.get("documento_id"),
                                           "tipo_documental": item.get("tipo_documental"),
                                           "publicado_em": item.get("publicado_em"),
                                           "versao": item.get("versao"),
                                           "sha256": item.get("sha256"),
                                           "pagina": item.get("pagina"),
                                           "trecho": item.get("trecho")}]
                                        if item["valor"] is not None else [])),
        "propostas": item.get("propostas"),
        "revalidacao": revalidation,
        "precisa_revalidacao": (state in ("candidato_nao_revalidado",
                                          "fonte_nao_confirmada")
                                and item["estado"] in ("futuro", "hoje")),
        "precisa_revisao_humana": state in ("conflito_documental", "data_ilegivel",
                                           "nao_localizado", "alterado_por_retificacao"),
        "proxima_acao": ACTION_BY_STATE[state],
        # Dimensões independentes: cada uma soma o total sozinha. `estado_operacional`
        # acima é derivado delas para orientar a ação, não uma categoria temporal.
        "dimensoes": {
            "temporal": item["estado"],
            "revalidacao": (revalidation or {}).get("result") or "sem_verificacao",
            "conflito": "conflito" if item["conflito"] else "sem_conflito",
            "revisao": ((item.get("decisao") or {}).get("decision")
                        or "sem_decisao"),
        },
    }


def _all_items(db_path, *, now_dt, contest_id=None, group=None) -> list[dict]:
    items, offset = [], 0
    while True:
        report = deadline_review.deadline_report(
            db_path, contest_id=contest_id, group=group, limit=500, offset=offset,
            now=now_dt)
        items.extend(report["itens"])
        if not report["has_more"] or offset > 5000:
            return items
        offset += report["limit"]


def calendar(db_path, *, contest_id=None, group=None, groups=None, state=None,
             urgency=None, limit=100, offset=0, now=None) -> dict:
    """Calendário operacional: estado por prazo, candidatos e próxima ação.

    ``groups`` restringe a vários grupos de uma vez (recorte da interface); ``group``
    continua sendo o filtro único. Sem nenhum dos dois, o universo é completo.
    """
    limit = int(limit)
    offset = int(offset)
    if limit < 1 or limit > 500:
        raise ValueError("limite fora da faixa")
    if offset < 0:
        raise ValueError("deslocamento inválido")
    if group and group not in deadline_review.DEADLINE_GROUPS:
        raise ValueError("grupo de prazo inválido")
    groups = list(groups or [])
    invalidos = [item for item in groups if item not in deadline_review.DEADLINE_GROUPS]
    if invalidos:
        raise ValueError("grupo de prazo inválido")
    # `group` manda: quando presente, é o recorte exato.
    selecionados = {group} if group else set(groups)
    if state and state not in OPERATIONAL_STATES:
        raise ValueError("estado operacional inválido")
    if urgency and urgency not in URGENCIES:
        raise ValueError("urgência inválida")
    now_dt = _now(now)
    today = _local_today(now_dt)

    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        revalidations = _last_revalidations(conn)
    pairs = coverage_states._source_map()
    items = []
    for raw in _all_items(db_path, now_dt=now_dt, contest_id=contest_id, group=group):
        source = _source_info(raw.get("official_url"), raw.get("issuer"), pairs)
        key = (raw["contest_id"], raw["grupo"], raw.get("escopo"), raw.get("versao"))
        items.append(_item_view(raw, today, revalidations.get(key), source))
    if selecionados:
        items = [item for item in items if item["grupo"] in selecionados]
    if state:
        items = [item for item in items if item["estado_operacional"] == state]
    if urgency:
        items = [item for item in items if item["urgencia"] == urgency]
    # Urgência primeiro: um prazo vencido não deve encobrir o que vence esta semana.
    urgency_order = {"hoje": 0, "ate_7_dias": 1, "ate_30_dias": 2, "futuro": 3,
                     "vencido": 4, "sem_data": 5}
    items.sort(key=lambda item: (
        urgency_order.get(item["urgencia"], 9),
        item["prioridade_grupo"],
        item["dias_restantes"] if item["dias_restantes"] is not None else 99999,
        item["contest_id"], item["grupo"], item["escopo_rotulo"] or ""))
    total = len(items)
    by_state, by_group, by_urgency = {}, {}, {}
    by_temporal, by_revalidation, by_conflict, by_review = {}, {}, {}, {}
    for item in items:
        by_state[item["estado_operacional"]] = by_state.get(item["estado_operacional"], 0) + 1
        by_group[item["grupo"]] = by_group.get(item["grupo"], 0) + 1
        by_urgency[item["urgencia"]] = by_urgency.get(item["urgencia"], 0) + 1
        dims = item["dimensoes"]
        by_temporal[dims["temporal"]] = by_temporal.get(dims["temporal"], 0) + 1
        by_revalidation[dims["revalidacao"]] = by_revalidation.get(dims["revalidacao"], 0) + 1
        by_conflict[dims["conflito"]] = by_conflict.get(dims["conflito"], 0) + 1
        by_review[dims["revisao"]] = by_review.get(dims["revisao"], 0) + 1
    return {
        "version": CALENDAR_VERSION, "generated_at": now_dt.isoformat(),
        "referencia": {"hoje_local": today.isoformat(), "fuso": "America/Recife",
                       "agora_utc": now_dt.astimezone(timezone.utc).isoformat()},
        "total": total,
        # Cada dimensão é exclusiva e soma `total` sozinha.
        "por_temporal": by_temporal,
        "por_revalidacao": by_revalidation,
        "por_conflito": by_conflict,
        "por_revisao": by_review,
        # `por_situacao` é derivado (ação); `por_estado` fica como alias compatível.
        "por_situacao": by_state, "por_estado": by_state,
        "por_grupo": by_group, "por_urgencia": by_urgency,
        "denominador": {
            "unidade": "prazo (concurso × grupo × escopo de cargo)",
            "universo": ("todo grupo de prazo com ao menos uma proposta no concurso; "
                         "inclui passados e sem data"),
            "filtros": {"contest_id": contest_id, "group": group,
                        "groups": sorted(selecionados), "state": state,
                        "urgency": urgency},
            "referencia": {"hoje_local": today.isoformat(), "fuso": "America/Recife"},
            "rejeitados": ("proposta rejeitada não sustenta valor; o grupo continua "
                           "contado e aparece como `sem_data` quando nada resta"),
            "dimensoes": {
                "temporal": "futuro | hoje | expirado | data_invalida | sem_data",
                "revalidacao": ("fonte_inalterada | fonte_alterada | fonte_indisponivel | "
                                "sem_permissao | erro | sem_verificacao"),
                "conflito": "conflito | sem_conflito",
                "revisao": "decisão humana vigente por proposta ou sem_decisao",
                "situacao": "estado derivado, para orientar a próxima ação",
            },
        },
        "limit": limit, "offset": offset, "has_more": offset + limit < total,
        "itens": items[offset:offset + limit],
        "limitacao": ("Candidato futuro não é inscrição aberta. Conflito não escolhe valor. "
                      "Documento oficial inalterado não confirma prazo. Situação operacional "
                      "é derivada; as dimensões são independentes. Nada é alterado "
                      "automaticamente."),
    }


def revalidation_targets(db_path, *, limit=5, now=None) -> dict:
    """Prazos que valem uma verificação na fonte, na ordem de impacto na candidatura."""
    limit = int(limit)
    if limit < 1 or limit > 500:
        raise ValueError("limite fora da faixa")
    now_dt = _now(now)
    today = _local_today(now_dt)
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        revalidations = _last_revalidations(conn)
    pairs = coverage_states._source_map()
    targets = []
    for raw in _all_items(db_path, now_dt=now_dt):
        source = _source_info(raw.get("official_url"), raw.get("issuer"), pairs)
        key = (raw["contest_id"], raw["grupo"], raw.get("escopo"), raw.get("versao"))
        item = _item_view(raw, today, revalidations.get(key), source)
        if not item["precisa_revalidacao"]:
            continue
        if not item["official_url"] or not item["versao"]:
            continue
        targets.append({
            "contest_id": item["contest_id"], "grupo": item["grupo"],
            "grupo_label": item["grupo_label"],
            "escopo": item["escopo"], "escopo_rotulo": item["escopo_rotulo"],
            "valor": item["valor"], "urgencia": item["urgencia"],
            "dias_restantes": item["dias_restantes"],
            "documento": item["documento"], "documento_id": item["documento_id"],
            "versao": item["versao"], "sha256": item["sha256"],
            "official_url": item["official_url"], "fonte": item["fonte"],
            "motivo": ("fim de inscrição se aproxima" if item["grupo"] == "inscricao_fim"
                       else "prazo de isenção/recurso se aproxima"
                       if item["grupo"].startswith(("isencao", "recurso"))
                       else "prazo futuro sem verificação registrada"),
        })
    targets.sort(key=lambda target: (
        target["dias_restantes"] if target["dias_restantes"] is not None else 99999,
        GROUP_PRIORITY.get(target["grupo"], 9), target["contest_id"]))
    total = len(targets)
    return {
        "version": CALENDAR_VERSION, "generated_at": now_dt.isoformat(),
        "total": total, "limit": limit, "has_more": total > limit,
        "itens": targets[:limit],
        "limitacao": ("Verificar o documento oficial não confirma o prazo: confirma que o "
                      "ato servido hoje é o mesmo da coleta. Nenhuma proposta é alterada."),
    }
