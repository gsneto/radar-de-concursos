"""Carteira operacional de oportunidades (Fase 36).

A mesa da Fase 34 agrupa por oportunidade e a Fase 35 reconciliou rótulos. Esta camada
responde a pergunta operacional: **o que merece atenção agora, com que evidência e qual a
próxima ação**.

Não cria cadastro paralelo: reutiliza ``opportunities`` (agrupamento e dossiê),
``decisive_fields`` (vagas indígenas, SI, prazos, local), ``deadline_calendar`` (situação
operacional do prazo) e ``coverage_states`` (estado documental). Não decide nada.

Regras de honestidade:

- prontidão é um estado determinístico com motivos, não uma pontuação única;
- candidato futuro não torna a oportunidade "ativa";
- ausência de informação não é resposta negativa: vira lacuna explícita;
- total agregado não vira vaga indígena; lotação não vira local de prova;
- só uma decisão humana válida produz ``informacao_confirmada``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from radar import (coverage_states, deadline_calendar, decisive_fields,
                   opportunities, preferences, role_identity)
from contextlib import closing

from radar.document_store import connect_documents, normalize_role

PORTFOLIO_VERSION = "portfolio_v1"

# Estados de prontidão, exclusivos, com a precedência declarada em ``_readiness``.
READINESS = (
    "documentacao_insuficiente",
    "edital_oficial_necessario",
    "identidade_cargo_pendente",
    "conflito_documental_pendente",
    "prazo_precisa_revalidacao",
    "oportunidade_historica",
    "campos_decisivos_ausentes",
    "candidatos_prontos_para_revisao",
    "dossie_revisado_campos_nao_confirmados",
    "informacao_confirmada",
)
READINESS_LABELS = {
    "documentacao_insuficiente": "Documentação insuficiente",
    "edital_oficial_necessario": "Edital oficial necessário",
    "identidade_cargo_pendente": "Identidade do cargo pendente",
    "conflito_documental_pendente": "Conflito documental pendente",
    "prazo_precisa_revalidacao": "Prazo precisa ser revalidado",
    "oportunidade_historica": "Oportunidade histórica, sem candidatura ativa",
    "campos_decisivos_ausentes": "Campos decisivos ausentes",
    "candidatos_prontos_para_revisao": "Candidatos com evidência, prontos para revisão",
    "dossie_revisado_campos_nao_confirmados": "Dossiê revisado, campos não confirmados",
    "informacao_confirmada": "Informação confirmada por decisão humana",
}

# Campos mínimos para avaliar uma oportunidade sem inventar o que falta.
CORE_FIELDS = ("education", "si_compatibility", "immediate_vacancies",
               "reserve_vacancies", "registration_end")

CONFIRMED_STATES = ("confirmado", "corrigido")

# Vocabulário de visão de `decisive_fields` (não o estado bruto da extração).
SI_RANK = {
    "explicito": 4,
    "categoria_inclui_curso": 3,
    "area_correlata_interpretacao": 2,
    "outras_formacoes": 1,
    "nao_encontrado": 0,
    "extracao_incompleta": 0,
}
SI_LABELS = {
    "explicito": "Sistemas de Informação expressamente aceito",
    "categoria_inclui_curso": "Categoria de formação inclui o curso (com evidência)",
    "area_correlata_interpretacao": "Área correlata: exige interpretação humana",
    "outras_formacoes": "Enumera outras formações (SI não citado)",
    "nao_encontrado": "Requisito não encontrado no texto extraído",
    "extracao_incompleta": "Extração incompleta",
}
INDIGENOUS_RANK = {
    "explicito_imediato": 4,
    "apenas_reserva": 3,
    "mencao_sem_quantidade": 2,
    "agregado_sem_modalidade": 1,
    "explicito_sem_vaga_imediata": 1,
    "nao_mencionado": 0,
    "nao_pesquisado": 0,
}

# Ordem de urgência usada na priorização (menor = mais urgente).
URGENCY_ORDER = {"hoje": 0, "ate_7_dias": 1, "ate_30_dias": 2, "futuro": 3,
                 "vencido": 4, "sem_data": 5}


def _now(now=None) -> datetime:
    if isinstance(now, str):
        return datetime.fromisoformat(now)
    return now or datetime.now(timezone.utc)


def _contest_pages(db_path) -> dict:
    """Título da página oficial do concurso, quando existe (não é o título do edital)."""
    pages = {}
    with closing(connect_documents(db_path)) as conn:
        for contest_id, title in conn.execute(
                "SELECT contest_id, title FROM documentos "
                "WHERE contest_id IS NOT NULL AND tipo_documental='pagina_concurso' "
                "ORDER BY discovered_at"):
            if contest_id not in pages and title:
                pages[contest_id] = title
    return pages


def _all_opportunities(db_path, now_dt) -> list[dict]:
    items, offset = [], 0
    while True:
        page = opportunities.opportunity_list(db_path, limit=200, offset=offset,
                                             now=now_dt)
        items.extend(page["itens"])
        if not page["has_more"] or offset > 5000:
            return items
        offset += page["limit"]


def _all_calendar(db_path, now_dt) -> list[dict]:
    items, offset = [], 0
    while True:
        page = deadline_calendar.calendar(db_path, limit=500, offset=offset, now=now_dt)
        items.extend(page["itens"])
        if not page["has_more"] or offset > 5000:
            return items
        offset += page["limit"]


def _field(item, name):
    return (item.get("campos") or {}).get(name) or {}


def _si_for_role(dec, item):
    """Compatibilidade do cargo, sem emprestar o estado de outro cargo.

    O relatório de campos decisivos tem um estado por cargo e um agregado do concurso. Usar
    o agregado quando o cargo não tem leitura faria um único cargo de TI "contaminar" todos
    os outros — exatamente o erro que a fase precisa evitar.
    """
    contest_si = (dec or {}).get("sistemas_de_informacao") or {}
    wanted = normalize_role(item.get("role_name") or "")
    if not wanted:
        if item.get("scope"):
            # Escopo de cargo sem nome legível: não emprestar o agregado do concurso.
            return {"estado": "nao_encontrado",
                    "estado_label": "Sem leitura de compatibilidade para este cargo",
                    "estado_extraido": None, "itens": [], "agregado": False}
        return {"estado": contest_si.get("estado"),
                "estado_label": ("Melhor estado entre cargos: "
                                 + (contest_si.get("estado_label") or "sem informação")),
                "estado_extraido": None, "itens": [], "agregado": True}
    cargos = contest_si.get("cargos") or []
    for cargo in cargos:
        if normalize_role(cargo.get("role_name") or "") == wanted:
            return {"estado": cargo.get("estado"),
                    "estado_label": cargo.get("estado_label"),
                    "estado_extraido": cargo.get("estado_extraido"),
                    "itens": cargo.get("itens") or [], "agregado": False}
    # Rótulo só com código ("400") casa com "400 Agente Fiscal" quando é único.
    prefix = [cargo for cargo in cargos
              if normalize_role(cargo.get("role_name") or "")
              and (wanted.startswith(normalize_role(cargo["role_name"]) + " ")
                   or normalize_role(cargo["role_name"]).startswith(wanted + " "))]
    if len(prefix) == 1:
        cargo = prefix[0]
        return {"estado": cargo.get("estado"),
                "estado_label": cargo.get("estado_label"),
                "estado_extraido": cargo.get("estado_extraido"),
                "itens": cargo.get("itens") or [], "agregado": False}
    return {"estado": "nao_encontrado",
            "estado_label": "Sem leitura de compatibilidade para este cargo",
            "estado_extraido": None, "itens": [], "agregado": False}


def _indigenous_for(dec, item):
    """Reserva/vaga indígena é do concurso: não se atribui a um cargo sem distribuição."""
    base = dict((dec or {}).get("indigenas") or {})
    base["ambito"] = "concurso"
    if item.get("scope"):
        base["nota_cargo"] = ("o quantitativo indígena é do concurso; não há distribuição "
                              "por cargo comprovada neste dado")
    return base


def _deadlines_for(calendar_items, contest_id, scope):
    """Prazos do concurso (escopo vazio) e do cargo (mesmo escopo)."""
    out = []
    for entry in calendar_items:
        if entry["contest_id"] != contest_id:
            continue
        if entry.get("escopo") in (None, "") or entry.get("escopo") == scope:
            out.append(entry)
    return out


def _readiness(item, dec, deadlines, si):
    doc = item.get("documental") or {}
    campos = item.get("campos") or {}
    reasons = []
    if doc.get("documentos", 0) == 0:
        reasons.append("nenhum documento associado ao concurso")
        return "documentacao_insuficiente", reasons
    if doc.get("documentos_oficiais", 0) == 0:
        reasons.append("só há documento não oficial (agregador) associado")
        return "edital_oficial_necessario", reasons
    # Conflito do próprio escopo é o sinal preciso; o mapa do concurso só entra no escopo
    # do concurso inteiro — não se atribui conflito de um cargo a outro.
    conflict_fields = sorted(
        field for field in CORE_FIELDS
        if campos.get(field, {}).get("estado") == "em_conflito")
    if not conflict_fields and not item.get("scope"):
        conflict_fields = sorted(
            field for field in CORE_FIELDS
            if (dec or {}).get("conflitos", {}).get(field))
    if conflict_fields:
        reasons.append("conflito documental em: " + ", ".join(conflict_fields))
        return "conflito_documental_pendente", reasons
    pending = [entry for entry in deadlines if entry["precisa_revalidacao"]]
    if pending:
        reasons.append(f"{len(pending)} prazo(s) futuro(s) sem verificação registrada")
        return "prazo_precisa_revalidacao", reasons
    dated = [entry for entry in deadlines
             if entry["estado_operacional"] in ("passado_com_evidencia",
                                                "alterado_por_retificacao")
             or entry["estado_temporal"] == "expirado"]
    active = [entry for entry in deadlines
              if entry["estado_temporal"] in ("futuro", "hoje")]
    if dated and not active:
        reasons.append("todos os prazos conhecidos já passaram")
        return "oportunidade_historica", reasons
    if not item.get("role_reconciliado") and str(item.get("scope") or "").startswith("label:"):
        reasons.append("o rótulo do documento não foi reconciliado com identidade canônica")
        return "identidade_cargo_pendente", reasons
    missing = [field for field in CORE_FIELDS
               if campos.get(field, {}).get("estado") in (None, "nao_extraido")]
    if missing:
        reasons.append("campos sem extração: " + ", ".join(missing))
        return "campos_decisivos_ausentes", reasons
    confirmed = [field for field in campos if campos[field].get("estado") in CONFIRMED_STATES]
    if confirmed and len(confirmed) >= len([f for f in campos if campos[f].get("propostas")]):
        reasons.append("todos os campos com proposta têm decisão humana")
        return "informacao_confirmada", reasons
    if confirmed:
        reasons.append(f"{len(confirmed)} campo(s) com decisão humana; os demais seguem "
                       "candidatos")
        return "dossie_revisado_campos_nao_confirmados", reasons
    if item.get("pendentes"):
        reasons.append(f"{item['pendentes']} proposta(s) aguardando revisão humana")
        return "candidatos_prontos_para_revisao", reasons
    reasons.append("não há proposta pendente nem campo confirmado")
    return "campos_decisivos_ausentes", reasons


def _priority(item, deadlines, si, indigenous, location=None, interest_states=None):
    """Ordem explicável: urgência, formação, reserva, documento, identidade e geografia.

    Geografia é desempate, nunca filtro: uma prova fora das UFs de interesse continua na
    carteira e apenas perde prioridade para outra equivalente mais próxima.
    """
    reasons = []
    active = [entry for entry in deadlines if entry["estado_temporal"] in ("futuro", "hoje")]
    urgency = min((URGENCY_ORDER.get(entry["urgencia"], 5) for entry in active), default=6)
    if active:
        soonest = min(active, key=lambda entry: entry["dias_restantes"]
                      if entry["dias_restantes"] is not None else 99999)
        reasons.append(f"prazo de {soonest['grupo_label'].lower()} em "
                       f"{soonest['dias_restantes']} dia(s)")
    else:
        reasons.append("sem prazo futuro identificado")
    si_rank = SI_RANK.get((si or {}).get("estado"), 0)
    if si_rank >= 3:
        reasons.append(SI_LABELS.get(si["estado"], "compatibilidade formal identificada"))
    elif si_rank == 2:
        reasons.append("compatibilidade com Sistemas de Informação exige interpretação")
    indig_rank = INDIGENOUS_RANK.get((indigenous or {}).get("estado"), 0)
    if not item.get("scope") and indig_rank >= 3:
        reasons.append((indigenous or {}).get("estado_label")
                       or "reserva indígena identificada")
    doc = item.get("documental") or {}
    official = 0 if doc.get("documentos_oficiais") else 1
    reconciled = 0 if item.get("role_reconciliado") else 1
    prova = ((location or {}).get("prova") or {})
    uf = (prova.get("uf") or "").upper()
    interest = {state.upper() for state in (interest_states or [])}
    if uf and interest and uf in interest:
        geo_rank = 0
        reasons.append(f"local de prova em {uf} (UF de interesse)")
    elif uf:
        geo_rank = 1
        reasons.append(f"local de prova em {uf} (fora das UFs de interesse)")
    else:
        geo_rank = 2
    return (urgency, -si_rank, -indig_rank, official, reconciled, geo_rank,
            item.get("contest_id") or "", item.get("scope") or ""), reasons


def _gaps(item, dec, deadlines, si):
    gaps = []
    doc = item.get("documental") or {}
    if doc.get("documentos_oficiais", 0) == 0:
        gaps.append("sem documento oficial")
    if (str(item.get("scope") or "").startswith("label:")
            and not item.get("role_reconciliado")):
        gaps.append("cargo não reconciliado")
    for field in CORE_FIELDS:
        state = (item.get("campos") or {}).get(field, {}).get("estado")
        if state in (None, "nao_extraido"):
            gaps.append(f"campo ausente: {field}")
    indigenous = (dec or {}).get("indigenas") or {}
    if indigenous.get("estado") in ("mencao_sem_quantidade", "agregado_sem_modalidade",
                                    "nao_mencionado", "nao_pesquisado"):
        prefixo = "no concurso, vagas indígenas: " if item.get("scope") \
            else "vagas indígenas: "
        gaps.append(prefixo + (indigenous.get("estado_label")
                               or indigenous.get("estado") or "sem informação"))
    if SI_RANK.get((si or {}).get("estado"), 0) <= 2:
        gaps.append("SI: " + (si.get("estado_label") or "sem informação"))
    for entry in deadlines:
        if entry["estado_operacional"] in ("nao_localizado", "conflito_documental",
                                           "data_ilegivel", "candidato_nao_revalidado"):
            gaps.append(f"{entry['grupo_label']}: {entry['estado_operacional_label']}")
    location = ((dec or {}).get("local") or {}).get("prova") or {}
    if location.get("state") in ("nao_informado", None):
        gaps.append("local de prova não informado")
    return gaps


def _next_action(readiness, item, deadlines, si, indigenous):
    if readiness == "documentacao_insuficiente":
        return "buscar edital oficial na fonte do órgão/banca"
    if readiness == "edital_oficial_necessario":
        return "localizar o edital oficial do concurso"
    if readiness == "identidade_cargo_pendente":
        return "confirmar a identidade do cargo"
    if readiness == "conflito_documental_pendente":
        return "resolver conflito entre versões antes de usar o valor"
    if readiness == "prazo_precisa_revalidacao":
        return "confirmar prazo na fonte oficial"
    if readiness == "oportunidade_historica":
        return "manter como histórica; acompanhar nova publicação"
    if SI_RANK.get((si or {}).get("estado"), 0) == 2:
        return "revisar requisito de formação (Sistemas de Informação)"
    if (indigenous or {}).get("estado") in ("mencao_sem_quantidade",
                                            "agregado_sem_modalidade"):
        return "revisar reserva de vagas indígenas no edital"
    if readiness == "campos_decisivos_ausentes":
        return "revisar candidatos dos campos decisivos"
    if readiness == "candidatos_prontos_para_revisao":
        return "revisar propostas na mesa de revisão"
    if readiness == "informacao_confirmada":
        return "acompanhar novas publicações"
    return item.get("proxima_acao") or "acompanhar novas publicações"


def _contest_label(item, pages):
    """Rótulo útil do certame: página oficial quando informativa, senão o identificador."""
    page = (pages or {}).get(item["contest_id"])
    if page and len(page.strip()) >= 20:
        return page
    return item.get("competition_id") or page or item.get("contest_title")


def _view(item, dec, calendar_items, now_dt, pages=None, interest_states=None):
    deadlines = _deadlines_for(calendar_items, item["contest_id"], item.get("scope"))
    si = _si_for_role(dec, item)
    indigenous = _indigenous_for(dec, item)
    readiness, readiness_reasons = _readiness(item, dec, deadlines, si)
    order, priority_reasons = _priority(item, deadlines, si, indigenous,
                                        (dec or {}).get("local"),
                                        interest_states)
    return {
        "contest_id": item["contest_id"],
        "competition_id": item.get("competition_id"),
        "contest_title": item.get("contest_title"),
        "contest_label": _contest_label(item, pages),
        "role_id": item.get("role_id"), "role_name": item.get("role_name"),
        "role_reconciliado": item.get("role_reconciliado"),
        "role_code": item.get("role_code"), "role_specialty": item.get("role_specialty"),
        "scope": item.get("scope"),
        "documental": item.get("documental"),
        "prontidao": {"estado": readiness, "estado_label": READINESS_LABELS[readiness],
                      "motivos": readiness_reasons},
        "prioridade": {"motivos": priority_reasons},
        "prazos": [{key: entry[key] for key in
                    ("grupo", "grupo_label", "valor", "estado_operacional",
                     "estado_operacional_label", "estado_temporal", "urgencia",
                     "urgencia_label", "dias_restantes", "documento", "pagina",
                     "precisa_revalidacao", "proxima_acao")}
                   for entry in deadlines],
        "si": si,
        "indigenas": indigenous,
        "formacao": {
            "requisito": _field(item, "education"),
            "cursos_aceitos": _field(item, "accepted_courses"),
            "si_compatibility": _field(item, "si_compatibility"),
        },
        "localizacao": (dec or {}).get("local"),
        "conflitos": {"campos": (dec or {}).get("conflitos") or {},
                      "oportunidade": item.get("conflitos")},
        "lacunas": _gaps(item, dec, deadlines, si),
        "proxima_acao": _next_action(readiness, item, deadlines, si, indigenous),
        "dossie": {"contest_id": item["contest_id"], "role_id": item.get("role_id"),
                   "scope": item.get("scope")},
        "propostas": item.get("propostas"), "pendentes": item.get("pendentes"),
        "ultima_atualizacao": item.get("ultima_atualizacao"),
        "_ordem": order,
    }


def portfolio(db_path, *, prontidao=None, prazo=None, si=None, indigena=None,
              documental=None, uf=None, conflito=None, search=None, contest_id=None,
              role_id=None, interest_states=None, limit=50, offset=0, now=None) -> dict:
    """Carteira operacional com prontidão, prioridade explicada e próxima ação."""
    limit = int(limit)
    offset = int(offset)
    if limit < 1 or limit > 200:
        raise ValueError("limite fora da faixa")
    if offset < 0:
        raise ValueError("deslocamento inválido")
    if prontidao and prontidao not in READINESS:
        raise ValueError("estado de prontidão inválido")
    if prazo and prazo not in deadline_calendar.URGENCIES:
        raise ValueError("filtro de prazo inválido")
    if documental and documental not in coverage_states.STATE_LABELS:
        raise ValueError("estado documental inválido")
    now_dt = _now(now)
    interest = (interest_states
                if interest_states is not None
                else preferences.DEFAULTS["interest_states"])
    dec = decisive_fields.decisive_report(db_path, limit=100000)
    dec_by = {entry["contest_id"]: entry for entry in dec["itens"]}
    calendar_items = _all_calendar(db_path, now_dt)
    pages = _contest_pages(db_path)
    items = []
    for raw in _all_opportunities(db_path, now_dt):
        if contest_id and raw["contest_id"] != contest_id:
            continue
        if role_id and raw.get("role_id") != role_id:
            continue
        view = _view(raw, dec_by.get(raw["contest_id"]), calendar_items, now_dt, pages,
                     interest)
        if prontidao and view["prontidao"]["estado"] != prontidao:
            continue
        if documental and (view["documental"] or {}).get("estado") != documental:
            continue
        if prazo and not any(entry["urgencia"] == prazo for entry in view["prazos"]):
            continue
        if si and (view["si"] or {}).get("estado") != si:
            continue
        if indigena and (view["indigenas"] or {}).get("estado") != indigena:
            continue
        if uf:
            prova = ((view["localizacao"] or {}).get("prova") or {})
            if (prova.get("uf") or "").upper() != uf.upper():
                continue
        if conflito is True and not (view["conflitos"]["campos"]
                                     or view["conflitos"]["oportunidade"]):
            continue
        if conflito is False and (view["conflitos"]["campos"]
                                  or view["conflitos"]["oportunidade"]):
            continue
        if search:
            needle = search.strip().lower()
            haystack = " ".join(str(view.get(key) or "") for key in
                                ("contest_title", "competition_id", "role_name",
                                 "role_specialty"))
            if needle not in haystack.lower():
                continue
        items.append(view)
    items.sort(key=lambda view: view["_ordem"])
    for view in items:
        view.pop("_ordem", None)
    total = len(items)
    by_readiness, by_urgency = {}, {}
    for view in items:
        state = view["prontidao"]["estado"]
        by_readiness[state] = by_readiness.get(state, 0) + 1
        for urgency in {entry["urgencia"] for entry in view["prazos"]}:
            by_urgency[urgency] = by_urgency.get(urgency, 0) + 1
    return {
        "version": PORTFOLIO_VERSION, "generated_at": now_dt.isoformat(),
        "referencia": {"agora_utc": now_dt.astimezone(timezone.utc).isoformat(),
                       "hoje_local": deadline_calendar._local_today(now_dt).isoformat(),
                       "fuso": "America/Recife"},
        "total": total, "por_prontidao": by_readiness, "por_urgencia": by_urgency,
        "limit": limit, "offset": offset, "has_more": offset + limit < total,
        "itens": items[offset:offset + limit],
        "limitacao": ("Prontidão é determinística e explicada; não é probabilidade. "
                      "Candidato futuro não é inscrição aberta. Ausência de informação "
                      "reduz a certeza e vira lacuna, nunca resposta negativa."),
    }


HIGHLIGHT_SI = ("explicito", "categoria_inclui_curso",
                "area_correlata_interpretacao")
HIGHLIGHT_INDIGENOUS = ("explicito_imediato", "apenas_reserva", "mencao_sem_quantidade")
MAX_PER_CONTEST = 2


def _inclusion_reasons(view):
    """Por que esta oportunidade entra na carteira inicial (nunca por similaridade)."""
    reasons = []
    doc = view.get("documental") or {}
    if not doc.get("documentos_oficiais"):
        return reasons
    role_name = view.get("role_name")
    if role_name and role_identity.classify_label(role_name) == "nao_e_cargo":
        # Rótulo que não é cargo não vira oportunidade de candidatura.
        return reasons
    active = [entry for entry in view["prazos"]
              if entry["estado_temporal"] in ("futuro", "hoje")]
    if active:
        soonest = min(active, key=lambda entry: entry["dias_restantes"]
                      if entry["dias_restantes"] is not None else 99999)
        reasons.append(f"prazo futuro de {soonest['grupo_label'].lower()} "
                       f"({soonest['valor']})")
    si_state = (view.get("si") or {}).get("estado")
    if si_state in HIGHLIGHT_SI:
        reasons.append(SI_LABELS.get(si_state, "compatibilidade com SI"))
    indig_state = (view.get("indigenas") or {}).get("estado")
    if not view.get("scope") and indig_state in HIGHLIGHT_INDIGENOUS:
        reasons.append((view.get("indigenas") or {}).get("estado_label")
                       or "reserva indígena identificada")
    return reasons


def portfolio_highlights(db_path, *, limit=12, interest_states=None, now=None) -> dict:
    """Carteira inicial: subconjunto controlado com edital oficial e sinal decisivo.

    A seleção é determinística e diversa por concurso: no máximo dois cargos do mesmo
    certame, para não transformar um edital grande na carteira inteira.
    """
    limit = int(limit)
    if limit < 1 or limit > 50:
        raise ValueError("limite fora da faixa")
    now_dt = _now(now)
    interest = (interest_states
                if interest_states is not None
                else preferences.DEFAULTS["interest_states"])
    dec = decisive_fields.decisive_report(db_path, limit=100000)
    dec_by = {entry["contest_id"]: entry for entry in dec["itens"]}
    calendar_items = _all_calendar(db_path, now_dt)
    pages = _contest_pages(db_path)
    candidates = []
    for raw in _all_opportunities(db_path, now_dt):
        view = _view(raw, dec_by.get(raw["contest_id"]), calendar_items, now_dt, pages,
                     interest)
        reasons = _inclusion_reasons(view)
        if not reasons:
            continue
        view["motivo_inclusao"] = reasons
        candidates.append(view)
    candidates.sort(key=lambda view: view["_ordem"])
    selected, per_contest = [], {}
    for view in candidates:
        contest = view["contest_id"]
        if per_contest.get(contest, 0) >= MAX_PER_CONTEST:
            continue
        per_contest[contest] = per_contest.get(contest, 0) + 1
        selected.append(view)
        if len(selected) >= limit:
            break
    for view in selected:
        view.pop("_ordem", None)
    return {
        "version": PORTFOLIO_VERSION, "generated_at": now_dt.isoformat(),
        "referencia": {"agora_utc": now_dt.astimezone(timezone.utc).isoformat(),
                       "hoje_local": deadline_calendar._local_today(now_dt).isoformat(),
                       "fuso": "America/Recife"},
        "total": len(selected), "candidatos": len(candidates),
        "concursos": len(per_contest), "limit": limit,
        "has_more": len(candidates) > len(selected),
        "criterio": ("Edital oficial identificado e ao menos um sinal: prazo futuro, "
                     "compatibilidade com Sistemas de Informação ou reserva indígena. "
                     "Rótulo que não é cargo fica fora. No máximo dois cargos por concurso. "
                     "A ordem prioriza urgência, formação, reserva, documento e identidade."),
        "itens": selected,
        "limitacao": ("Inclusão não é aprovação: cada item mantém suas lacunas e a próxima "
                      "ação. Cadastro de reserva e distância não excluem a oportunidade."),
    }


def portfolio_dossier(db_path, contest_id: str, *, role_id=None, scope=None,
                      now=None) -> dict:
    """Dossiê operacional: identidade, vagas, formação, prazos, local e próxima ação."""
    now_dt = _now(now)
    base = opportunities.opportunity_dossier(db_path, contest_id, role_id=role_id,
                                             scope=scope)
    dec = decisive_fields.decisive_report(db_path, contest_ids=[contest_id], limit=10)
    dec_item = dec["itens"][0] if dec["itens"] else {}
    calendar_items = _all_calendar(db_path, now_dt)
    deadlines = _deadlines_for(calendar_items, contest_id, scope)
    item = {
        "contest_id": contest_id, "role_id": role_id, "scope": scope,
        "role_name": (base.get("identidade") or {}).get("role_name"),
        "role_reconciliado": bool(role_id),
        "documental": base.get("documental") or {},
        "campos": {entry["campo"]: entry for entry in base.get("campos") or []},
        "conflitos": bool(base.get("conflitos")),
        "pendentes": (base.get("revisao") or {}).get("pendentes"),
        "proxima_acao": None,
    }
    if item["role_name"] is None and scope:
        if str(scope).startswith("label:"):
            item["role_name"] = str(scope)[len("label:"):]
        else:
            for cargo in (base.get("identidade") or {}).get("cargos") or []:
                if cargo.get("role_id") == scope:
                    item["role_name"] = cargo.get("name") or cargo.get("role_name")
                    break
    si = _si_for_role(dec_item, item)
    indigenous = _indigenous_for(dec_item, item)
    readiness, reasons = _readiness(item, dec_item, deadlines, si)
    documents = (base.get("documental") or {}).get("documentos") or []
    editais = [doc for doc in documents
               if doc.get("tipo") in ("edital_abertura", "edital_retificado")]
    retificacoes = [doc for doc in documents if doc.get("tipo") == "retificacao"]
    prazos = [dict(entry, pagamento=None) for entry in deadlines]
    prazos.append({
        "grupo": "pagamento", "grupo_label": "Pagamento da taxa",
        "valor": None, "estado_operacional": "nao_localizado",
        "estado_operacional_label": "O modelo não extrai prazo de pagamento",
        "estado_temporal": "sem_data", "urgencia": "sem_data",
        "urgencia_label": "Sem data", "dias_restantes": None,
        "documento": None, "pagina": None, "precisa_revalidacao": False,
        "proxima_acao": "conferir o prazo de pagamento no edital oficial",
    })
    pages = _contest_pages(db_path)
    return {
        "version": PORTFOLIO_VERSION, "generated_at": now_dt.isoformat(),
        "contest_id": contest_id, "role_id": role_id, "scope": scope,
        "identificacao": {
            "contest_title": base.get("identidade", {}).get("contest_title"),
            "contest_label": _contest_label(
                {"contest_id": contest_id,
                 "contest_title": base.get("identidade", {}).get("contest_title"),
                 "competition_id": (base.get("identidade", {}).get("observacoes") or [{}])[0].get("competition_id")},
                pages),
            "observacoes": (base.get("identidade") or {}).get("observacoes") or [],
            "role_name": item["role_name"], "role_reconciliado": item["role_reconciliado"],
            "documentos": len(documents), "edital_principal": editais[0] if editais else None,
            "retificacoes": retificacoes,
        },
        "vagas": {
            "total_publicado": item["campos"].get("vagas_total_publicado"),
            "imediatas": item["campos"].get("immediate_vacancies"),
            "reserva": item["campos"].get("reserve_vacancies"),
            "indigenas": indigenous,
            "nota": ("Total agregado é do edital e não é distribuído por modalidade. "
                     "Reserva mencionada não é quantidade comprovada."),
        },
        "formacao": {
            "requisito": item["campos"].get("education"),
            "cursos_aceitos": item["campos"].get("accepted_courses"),
            "si_compatibility": item["campos"].get("si_compatibility"),
            "si_por_cargo": si,
            "nota": ("Cargo de tecnologia não garante aceitação do Bacharelado em Sistemas "
                     "de Informação; só decisão humana com evidência confirma."),
        },
        "prazos": prazos,
        "localizacao": dec_item.get("local"),
        "conflitos": {"campos": dec_item.get("conflitos") or {},
                      "oportunidade": base.get("conflitos") or []},
        "prontidao": {"estado": readiness, "estado_label": READINESS_LABELS[readiness],
                      "motivos": reasons},
        "proxima_acao": _next_action(readiness, item, deadlines, si, indigenous),
        "lacunas": _gaps(item, dec_item, deadlines, si),
        "dossie": {"contest_id": contest_id, "role_id": role_id, "scope": scope},
        "limitacao": ("Dossiê operacional não é campo confirmado. Cada seção aponta para a "
                      "evidência na mesa; nada é decidido aqui."),
    }
