"""Matriz de elegibilidade por cargo e escopo da reserva indígena (Fase 38).

Responde, **por cargo**, duas perguntas distintas que não podem ser misturadas:

1. o requisito formal de formação aceita o perfil pretendido (Bacharelado em Sistemas de
   Informação)?
2. existe vaga/reserva indígena documentada **para este cargo** ou apenas para o concurso?

Regras de honestidade aplicadas aqui:

- compatibilidade é do **cargo**: um cargo de tecnologia não herda o estado de outro, e um
  cargo não herda o estado agregado do concurso;
- reserva indígena do concurso **não** é distribuída por cargo sem tabela explícita;
- total agregado nunca vira vaga indígena; "CR" não é zero nem vaga imediata;
- ausência de leitura não é incompatibilidade;
- nada é confirmado: os estados são candidatos até decisão humana no fluxo de revisão.

Este módulo não escreve na base: lê propostas, evidências, reconciliações e o calendário.
"""

from __future__ import annotations

import json
import re
from contextlib import closing

from radar import (deadline_calendar, decisive_fields, edital_requirements,
                   portfolio, review, role_identity)
from radar.document_store import (connect_documents, is_readable_schema,
                                  normalize_role)

ELIGIBILITY_VERSION = "eligibility_v2"

# Perfil pretendido. Configurável; o padrão é o perfil prioritário da fase.
PROFILES = {
    "si_bacharelado": {
        "id": "si_bacharelado",
        "label": "Bacharelado em Sistemas de Informação",
        "aliases": ("sistemas de informa", "sistema de informa"),
    },
}
DEFAULT_PROFILE = "si_bacharelado"

# Estados de elegibilidade — exclusivos, com a precedência declarada em `_eligibility`.
ELIGIBILITY_STATES = (
    "incompativel_por_requisito",
    "compativel_com_vaga_indigena_cargo",
    "compativel_sem_vaga_indigena",
    "compativel_por_nivel_minimo",
    "compativel_por_interpretacao",
    "identidade_pendente",
    "informacao_insuficiente",
)
ELIGIBILITY_LABELS = {
    "incompativel_por_requisito": "Incompatível por requisito explícito",
    "compativel_com_vaga_indigena_cargo": ("Compatível, com vaga indígena do cargo "
                                           "explicitamente documentada"),
    "compativel_sem_vaga_indigena": ("Compatível; reserva indígena não quantificada ou "
                                     "não distribuída por cargo"),
    "compativel_por_nivel_minimo": ("Compatível por escolaridade mínima publicada "
                                    "(sem exigência de curso específico)"),
    "compativel_por_interpretacao": "Compatibilidade potencial (exige interpretação humana)",
    "identidade_pendente": "Identidade do cargo pendente",
    "informacao_insuficiente": "Informação insuficiente para avaliar",
}

# Estados do escopo indígena — exclusivos, por cargo.
INDIGENOUS_SCOPE_STATES = (
    "cargo_imediata",
    "cargo_sem_imediata_com_reserva",
    "cargo_explicito_zero",
    "distribuido_por_cargo",
    "concurso_imediata_sem_distribuicao",
    "reserva_sem_quantidade",
    "mencao_sem_quantidade",
    "ausente_no_documento",
    "nao_localizado",
    "conflito",
    "extracao_insuficiente",
)
INDIGENOUS_SCOPE_LABELS = {
    "cargo_imediata": "Vaga indígena imediata publicada para este cargo",
    "cargo_sem_imediata_com_reserva": ("Sem vaga imediata indígena; reserva indígena "
                                      "publicada para o cargo"),
    "cargo_explicito_zero": "Zero indígena publicado para este cargo (tabela completa)",
    "distribuido_por_cargo": ("Informação indígena publicada por cargo (ver cada cargo; "
                              "o total do concurso não é distribuído aqui)"),
    "concurso_imediata_sem_distribuicao": ("Vaga indígena imediata publicada apenas no "
                                           "âmbito do concurso"),
    "reserva_sem_quantidade": "Reserva indígena mencionada, sem quantidade comprovada",
    "mencao_sem_quantidade": "Menção a indígenas sem quantidade ou escopo suficiente",
    "ausente_no_documento": "Documento examinado não traz a modalidade indígena",
    "nao_localizado": "Informação indígena não localizada",
    "conflito": "Conflito documental na informação indígena",
    "extracao_insuficiente": "Documento ou extração insuficiente",
}

# Situação temporal (dimensão separada, nunca usada para "abrir" a oportunidade).
TEMPORAL_STATES = ("revalidado_na_fonte", "candidato", "conflito", "expirado",
                   "nao_localizado", "sem_candidatura")
TEMPORAL_LABELS = {
    "revalidado_na_fonte": "Prazo futuro com documento oficial inalterado",
    "candidato": "Prazo futuro candidato, ainda não revalidado",
    "conflito": "Prazo em conflito documental",
    "expirado": "Prazo expirado",
    "nao_localizado": "Prazo não localizado",
    "sem_candidatura": "Sem evento de prazo com candidatura ativa identificada",
}

ACTIONS = {
    "incompativel_por_requisito": ("não apresentar como elegível para este perfil; "
                                   "registrar o requisito literal"),
    "compativel_com_vaga_indigena_cargo": ("revisar requisito e vaga indígena do cargo; "
                                           "confirmar os dois na mesma decisão"),
    "compativel_sem_vaga_indigena": ("confirmar requisito; quantificar a reserva indígena "
                                     "do cargo no edital"),
    "compativel_por_nivel_minimo": ("confirmar que o edital não exige curso específico além "
                                     "do nível publicado"),
    "compativel_por_interpretacao": ("revisar o requisito literal e decidir se o curso é "
                                     "abrangido"),
    "identidade_pendente": "confirmar a identidade do cargo",
    "informacao_insuficiente": "buscar o requisito de formação no edital",
}


def _now(now=None):
    return portfolio._now(now)


def _value(row):
    try:
        return json.loads(row["value_json"])
    except (TypeError, ValueError, KeyError):
        return row.get("value_json")


def _si_view(raw):
    if raw in decisive_fields.SI_VIEW_STATES:
        return decisive_fields.SI_VIEW_STATES[raw]
    return "nao_encontrado"


def _norm_scope(scope_ref):
    """Escopo canônico: rótulo normalizado (caixa/acento/espaço), identidade à parte."""
    if isinstance(scope_ref, str) and scope_ref.startswith("label:"):
        return "label:" + normalize_role(scope_ref[len("label:"):])
    return scope_ref


def _cargolike_labels(rows, reconciled):
    """Rótulos de cargo do concurso (exclui rótulos de outro campo, ex.: escolaridade)."""
    labels = set()
    for row in rows:
        label = review._label_of(row)
        if not label:
            continue
        if role_identity.classify_label(label) == "nao_e_cargo":
            continue
        scope_ref, _ = review.role_scope(
            {"role_id": row["role_id"], "contest_id": row["contest_id"],
             "ambiguity_reason": row["ambiguity_reason"]}, reconciled)
        labels.add((row["contest_id"], scope_ref))
    return labels


def _scope_rows(rows, reconciled):
    """Agrupa propostas por (concurso, escopo) nas dimensões que a matriz usa."""
    data = {}
    for row in rows:
        if row["field_name"] not in ("si_compatibility", "indigenous_vacancies",
                                     "indigenous_reserve_vacancies",
                                     "immediate_vacancies", "reserve_vacancies",
                                     "vagas_total_publicado", "vaga_municipio"):
            continue
        scope_ref, scope_label = review.role_scope(
            {"role_id": row["role_id"], "contest_id": row["contest_id"],
             "ambiguity_reason": row["ambiguity_reason"]}, reconciled)
        key = (row["contest_id"], _norm_scope(scope_ref))
        entry = data.setdefault(key, {"si": [], "indigenous": [],
                                      "indigenous_reserve": [], "reserve": [],
                                      "immediate": [], "aggregate": [],
                                      "locality": [], "scope_label": scope_label})
        target = {"si_compatibility": "si", "indigenous_vacancies": "indigenous",
                  "indigenous_reserve_vacancies": "indigenous_reserve",
                  "immediate_vacancies": "immediate",
                  "reserve_vacancies": "reserve",
                  "vaga_municipio": "locality",
                  "vagas_total_publicado": "aggregate"}[row["field_name"]]
        if row["last_decision"] == "rejeitado":
            continue
        entry[target].append(row)
        label = review._label_of(row)
        if (target == "si" and label
                and role_identity.classify_label(label) == "nao_e_cargo"):
            # Leitura de formação declarada sem cargo ("escolaridade declarada (…)"):
            # pertence ao concurso, não ao rótulo onde o extrator a pendurou.
            contest = data.setdefault((row["contest_id"], ""), {})
            contest.setdefault("si_unscoped", []).append(row)
    return data


def _brief(row):
    try:
        value = json.loads(row["value_json"])
    except (TypeError, ValueError):
        value = row["value_json"]
    return {"proposal_id": row["proposal_id"], "value": value,
            "document_id": row["document_id"], "document_title": row["document_title"],
            "tipo_documental": row["tipo_documental"],
            "published_at": row["published_at"], "page_number": row["page_number"],
            "quote": row["quote"], "decision": row["last_decision"],
            "scope": row["scope"] if "scope" in row else None}


# Marcadores de que o trecho é realmente um requisito de formação.
_REQUIREMENT_MARKERS = re.compile(
    r"\b(?:cursos?|gradua[çc][ãa]o|bacharel(?:ado)?|licenciatura|diploma|"
    r"certificado|t[ée]cnic[oa]|ensino\s+m[ée]dio|n[íi]vel\s+superior)\b", re.I)


def _is_requirement_text(items) -> bool:
    """O trecho citado parece um requisito de formação?

    "Ambíguo" só é compatibilidade potencial quando o texto é de requisito. Um trecho
    que não fala de formação (ex.: currículo, ata) não sustenta nem potencial.
    """
    for row in items:
        if _REQUIREMENT_MARKERS.search(row.get("quote") or ""):
            return True
    return False


_COMPUTING_MARKERS = re.compile(
    r"\b(?:computa[çc][ãa]o|inform[áa]tica|tecnologia\s+da\s+informa[çc][ãa]o|"
    r"sistemas?\s+de\s+informa[çc][ãa]o|an[áa]lise\s+de\s+sistemas|"
    r"engenharia\s+de\s+software|redes\s+de\s+computadores|"
    r"processamento\s+de\s+dados|ci[êe]ncia\s+de\s+dados)\b", re.I)


_SKILL_CONTEXT = re.compile(
    r"(?:conhecimentos?|no[çc][õo]es|dom[íi]nio|familiaridade)\s+"
    r"(?:b[áa]sic[oa]s?\s+)?(?:de\s+|em\s+)?$", re.I)


def _is_correlate_text(items) -> bool:
    """O trecho cita área de computação/TI **como formação** (sem abertura explícita)?

    "Ambíguo" só é compatibilidade potencial quando o requisito é de formação na área.
    Requisito genérico ("nível médio", "superior em qualquer área") não sustenta potencial,
    e "conhecimentos básicos em informática" é habilidade, não curso.
    """
    for row in items:
        quote = row.get("quote") or ""
        for match in _COMPUTING_MARKERS.finditer(quote):
            prefix = quote[max(0, match.start() - 40):match.start()]
            if _SKILL_CONTEXT.search(prefix):
                continue
            return True
    return False


_CODE_PREFIX = re.compile(r"^\s*(\d{2,5})\b")


def _code_of(scope_ref) -> str | None:
    """Código do cargo a partir do escopo ("label:200 …" → "200")."""
    if not isinstance(scope_ref, str) or not scope_ref.startswith("label:"):
        return None
    match = _CODE_PREFIX.match(scope_ref[len("label:"):])
    return match.group(1) if match else None


def _is_code_label(scope_ref) -> bool:
    """Rótulo que é apenas um código ("200"), sem nome de cargo."""
    if not isinstance(scope_ref, str) or not scope_ref.startswith("label:"):
        return False
    rest = scope_ref[len("label:"):].strip()
    return bool(rest) and rest.isdigit()


def _family(label) -> str | None:
    """Título-base do cargo: rótulo original sem o código.

    A família é apenas uma leitura de apoio — nunca transfere requisito, vaga ou reserva
    entre códigos, e nunca substitui a identidade individual.
    """
    if not isinstance(label, str) or not label.strip():
        return None
    match = _CODE_PREFIX.match(label)
    if match:
        label = label[match.end():]
    label = " ".join(label.split())
    return label or None


def _derive_reading(row) -> dict:
    """Relê o requisito **do texto citado** com o classificador atual.

    A proposta guarda o valor do extrator da época; o texto é a evidência. Reclassificar
    a partir do trecho mantém o histórico intacto e permite corrigir a leitura sem
    reescrever proposta — o valor armazenado continua visível para auditoria.
    """
    quote = row.get("quote") or ""
    raw, reason = edital_requirements.classify_si_compatibility(quote)
    level = edital_requirements.education_level(quote)
    specific = edital_requirements.names_specific_area(quote)
    return {"raw": raw, "motivo": reason, "nivel": level,
            "area_especifica": specific,
            "kind": ("formacao_especifica" if specific and level != "indefinido"
                     else "nivel_minimo" if level != "indefinido" else "indefinido")}


def _reading_view(reading) -> str:
    """Estado de visão a partir da leitura derivada."""
    if reading["raw"] == "nivel_minimo_sem_area":
        return "nivel_minimo"
    return _si_view(reading["raw"])


VALIDATED_DECISIONS = ("validado", "corrigido")


def _combine(stored: str, derived: str | None, decision=None) -> str:
    """Combina leitura armazenada e derivada do texto.

    O **texto citado é a evidência**: quando ele contém marcadores de requisito, a leitura
    derivada pelo classificador atual prevalece sobre o valor armazenado (que é um retrato
    histórico e continua visível na ficha). Sem marcador de requisito no trecho, vale o
    valor armazenado. A regra de múltiplos candidatos (uma leitura ambígua não apaga uma
    incompatibilidade explícita) é aplicada em `_si_state`, sobre os candidatos do escopo.
    """
    if derived is None or decision in VALIDATED_DECISIONS:
        # Decisão humana vigente vale mais que a releitura automática.
        return stored
    return derived


def _education_for(items, readings, view):
    """Leitura educacional da evidência que sustenta o estado final."""
    for row, reading in zip(items, readings):
        if _reading_view(reading) == view:
            return reading
    return readings[0] if readings else None


def _si_state(items):
    """Estado de SI do escopo: relê o texto e trata divergência sem escolher vencedor."""
    if not items:
        return "nao_encontrado", [], None
    readings = [_derive_reading(row) for row in items]
    views = set()
    for row, reading in zip(items, readings):
        stored = _si_view(_value(row))
        derived = _reading_view(reading) if _is_requirement_text([row]) else None
        views.add(_combine(stored, derived, row.get("last_decision")))
    education = readings[0]
    if len(views) > 1:
        if "outras_formacoes" in views:
            # Uma leitura ambígua não apaga uma exclusão explícita.
            return "outras_formacoes", [_brief(row) for row in items], _education_for(
                items, readings, "outras_formacoes")
        if "explicito" in views:
            # Nem apaga uma aceitação explícita do curso.
            return "explicito", [_brief(row) for row in items], _education_for(
                items, readings, "explicito")
        if not _is_requirement_text(items) or not _is_correlate_text(items):
            return "nao_encontrado", [_brief(row) for row in items], _education_for(
                items, readings, "nao_encontrado")
        return "area_correlata_interpretacao", [_brief(row) for row in items], \
            _education_for(items, readings, "area_correlata_interpretacao")
    view = views.pop()
    if view == "area_correlata_interpretacao":
        if not _is_requirement_text(items) or not _is_correlate_text(items):
            return "nao_encontrado", [_brief(row) for row in items], education
    # A educação exibida é a da evidência que sustentou o estado final.
    for row, reading in zip(items, readings):
        if _reading_view(reading) == view:
            education = reading
            break
    return view, [_brief(row) for row in items], education


def _si_state_legacy(items):
    """Compatibilidade: leitura direta do valor armazenado (sem reclassificar)."""
    if not items:
        return "nao_encontrado", [], None
    """Estado de SI do escopo: conflito entre leituras vira interpretação, não escolha."""
    if not items:
        return "nao_encontrado", []
    views = {_si_view(_value(row)) for row in items}
    if len(views) > 1:
        if "outras_formacoes" in views:
            # Uma leitura ambígua não apaga uma exclusão explícita.
            return "outras_formacoes", [_brief(row) for row in items]
        if not _is_requirement_text(items) or not _is_correlate_text(items):
            return "nao_encontrado", [_brief(row) for row in items]
        return "area_correlata_interpretacao", [_brief(row) for row in items]
    view = views.pop()
    if view == "area_correlata_interpretacao":
        if not _is_requirement_text(items):
            return "nao_encontrado", [_brief(row) for row in items]
        if not _is_correlate_text(items):
            return "nao_encontrado", [_brief(row) for row in items]
    return view, [_brief(row) for row in items]


def _locality(entry) -> dict | None:
    """Município/lotação publicado para o código (não é local de prova)."""
    items = entry.get("locality") or []
    if not items:
        return None
    row = items[0]
    return {"valor": _value(row), "evidencia": _brief(row),
            "nota": "município/lotação associado ao código; não é local de prova"}


def _numbers(items):
    values = []
    for row in items:
        value = _value(row)
        try:
            values.append(int(value))
        except (TypeError, ValueError):
            continue
    return values


def _indigenous_state(cargo_items, cargo_reserve, contest_items, contest_reserve,
                      mention, analyzed):
    """Estado indígena do cargo, sem herdar a quantidade do concurso."""
    if cargo_items:
        values = _numbers(cargo_items)
        if any(value > 0 for value in values):
            return "cargo_imediata", [_brief(row) for row in cargo_items]
        if values:
            if cargo_reserve and any(value > 0 for value in _numbers(cargo_reserve)):
                return "cargo_sem_imediata_com_reserva", (
                    [_brief(row) for row in cargo_items]
                    + [_brief(row) for row in cargo_reserve])
            return "cargo_explicito_zero", [_brief(row) for row in cargo_items]
    if cargo_reserve and any(value > 0 for value in _numbers(cargo_reserve)):
        return "cargo_sem_imediata_com_reserva", [_brief(row) for row in cargo_reserve]
    if contest_items and any(value > 0 for value in _numbers(contest_items)):
        return "concurso_imediata_sem_distribuicao", [_brief(row) for row in contest_items]
    if contest_reserve:
        evidence = [_brief(row) for row in contest_reserve]
        return "reserva_sem_quantidade", evidence
    if mention:
        return "mencao_sem_quantidade", [mention]
    if not analyzed:
        return "nao_localizado", []
    return "ausente_no_documento", []


def _eligibility(si_view, indigenous_state, identity, has_scope):
    """Estado de elegibilidade com precedência explícita.

    Incompatibilidade primeiro; depois as compatibilidades sustentadas (expressa,
    categoria e nível mínimo); depois a interpretação; por último a falta de informação.
    """
    if si_view == "outras_formacoes":
        return "incompativel_por_requisito"
    if si_view in ("explicito", "categoria_inclui_curso"):
        if indigenous_state == "cargo_imediata":
            return "compativel_com_vaga_indigena_cargo"
        return "compativel_sem_vaga_indigena"
    if si_view == "nivel_minimo":
        return "compativel_por_nivel_minimo"
    if si_view == "area_correlata_interpretacao":
        return "compativel_por_interpretacao"
    if identity == "pendente":
        return "identidade_pendente"
    return "informacao_insuficiente"


def _temporal(deadlines):
    """Situação temporal agregada do cargo, separada da elegibilidade."""
    if not deadlines:
        return "nao_localizado"
    active = [entry for entry in deadlines
              if entry["estado_temporal"] in ("futuro", "hoje")]
    if active:
        if any(entry["estado_operacional"] == "conflito_documental" for entry in active):
            return "conflito"
        if any(entry["estado_operacional"] == "revalidado_na_fonte" for entry in active):
            return "revalidado_na_fonte"
        return "candidato"
    if any(entry["estado_temporal"] == "expirado" for entry in deadlines):
        return "expirado"
    return "sem_candidatura"


def _mention_for(rows, contest_id):
    """Primeira menção textual a indígena nas páginas do concurso (sem quantidade)."""
    for row in rows:
        if row["contest_id"] != contest_id:
            continue
        if row["field_name"] not in ("si_compatibility",):
            continue
        break
    return None


def _profile(profile):
    if profile is None:
        return PROFILES[DEFAULT_PROFILE]
    if profile not in PROFILES:
        raise ValueError("perfil inválido")
    return PROFILES[profile]


def matrix(db_path, *, profile=None, eligibility=None, indigenous=None,
           temporal=None, identity=None, si=None, uf=None, conflict=None,
           search=None, contest_id=None, role_id=None, limit=50, offset=0,
           now=None) -> dict:
    """Matriz de elegibilidade por concurso × cargo, com escopo indígena explícito."""
    limit = int(limit)
    offset = int(offset)
    if limit < 1 or limit > 200:
        raise ValueError("limite fora da faixa")
    if offset < 0:
        raise ValueError("deslocamento inválido")
    if eligibility and eligibility not in ELIGIBILITY_STATES:
        raise ValueError("estado de elegibilidade inválido")
    if indigenous and indigenous not in INDIGENOUS_SCOPE_STATES:
        raise ValueError("estado indígena inválido")
    if temporal and temporal not in TEMPORAL_STATES:
        raise ValueError("situação temporal inválida")
    if identity and identity not in ("reconciliado", "pendente"):
        raise ValueError("estado de identidade inválido")
    if si and si not in decisive_fields.SI_VIEW_STATES.values():
        raise ValueError("estado de SI inválido")
    profile_entry = _profile(profile)
    now_dt = _now(now)

    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = review._rows(conn)
        reconciled = review._reconciled_map(conn)
        analyzed = {row[0] for row in conn.execute(
            "SELECT DISTINCT d.contest_id FROM documentos d "
            "JOIN versoes_documento v ON v.document_id=d.id "
            "JOIN blocos_documento b ON b.version_id=v.id "
            "WHERE d.tipo_documental IN ('edital_abertura','edital_retificado')")}
        # Menção textual a indígenas no documento, sem quantidade extraída.
        mentions = {}
        for contest, page, text in conn.execute(
                "SELECT d.contest_id, b.page_number, b.text FROM blocos_documento b "
                "JOIN versoes_documento v ON v.id=b.version_id "
                "JOIN documentos d ON d.id=v.document_id "
                "WHERE d.tipo_documental IN ('edital_abertura','edital_retificado') "
                "AND b.page_number IS NOT NULL "
                "AND (lower(b.text) LIKE '%indígen%' OR lower(b.text) LIKE '%indigen%')"):
            if contest in mentions:
                continue
            low = (text or "").lower()
            index = low.find("indígen")
            if index < 0:
                index = low.find("indigen")
            snippet = " ".join((text or "")[max(0, index - 80):index + 160].split())
            mentions[contest] = {"quote": snippet[:200], "page_number": page}
    by_scope = _scope_rows(rows, reconciled)
    cargolike = _cargolike_labels(rows, reconciled)
    # Rótulos só com código ("200") e códigos dos rótulos nomeados, para a junção por
    # código. Um código ambíguo (dois nomes diferentes no mesmo concurso) não é usado.
    by_code = {}
    code_named = {}
    for key, value in by_scope.items():
        cid_, scope_ = key
        if not scope_ or not _is_code_label(scope_):
            continue
        code = _code_of(scope_)
        if code:
            by_code[(cid_, code)] = value
    # Cargos nomeados com código vêm de **todos** os rótulos de cargo, não só dos que
    # têm leitura de SI: dois nomes com o mesmo código tornam a junção insegura.
    for cid_, scope_ in cargolike:
        if not scope_ or _is_code_label(scope_):
            continue
        code = _code_of(scope_)
        if code:
            code_named.setdefault((cid_, code), set()).add(scope_)
    calendar_items = portfolio._all_calendar(db_path, now_dt)
    pages = portfolio._contest_pages(db_path)
    dec = decisive_fields.decisive_report(db_path, limit=100000)
    dec_by = {entry["contest_id"]: entry for entry in dec["itens"]}
    opportunities = portfolio._all_opportunities(db_path, now_dt)

    items = []
    seen = {}
    labels_by_key = {}
    for raw in opportunities:
        cid = raw["contest_id"]
        if contest_id and cid != contest_id:
            continue
        if role_id and raw.get("role_id") != role_id:
            continue
        scope = raw.get("scope") or ""
        if scope.startswith("label:"):
            label = scope[len("label:"):]
            nature = role_identity.classify_label(label)
            if nature in ("nao_e_cargo", "codigo_sem_nome"):
                # Rótulo de outro campo ou código sem nome não é cargo identificável:
                # não vira linha de elegibilidade (o cargo nomeado segue pendente).
                continue
        scope_key = _norm_scope(scope)
        dedupe_key = (cid, scope_key)
        if dedupe_key in seen:
            labels_by_key.setdefault(dedupe_key, set()).add(raw.get("role_name") or scope)
            continue
        entry = by_scope.get((cid, scope_key), {})
        contest_entry = by_scope.get((cid, ""), {})
        si_view, si_items, education = _si_state(entry.get("si") or [])
        atribuicao = "escopo_do_cargo" if entry.get("si") else None
        if not entry.get("si") and scope:
            # Sem leitura no cargo: não herda o agregado do concurso.
            si_view, education = "nao_encontrado", None
            # Junção por código: a leitura pendurada no rótulo "200" é do cargo "200 …"
            # quando o código é único entre os cargos nomeados do concurso.
            code = _code_of(scope_key)
            code_entry = by_code.get((cid, code)) if code else None
            named_with_code = code_named.get((cid, code), set()) if code else set()
            if code_entry and code_entry.get("si") and len(named_with_code) == 1:
                si_view, si_items, education = _si_state(code_entry.get("si") or [])
                atribuicao = "codigo_do_cargo"
            else:
                unscoped = contest_entry.get("si_unscoped") or []
                # Edital de cargo único: a formação declarada sem rótulo de cargo é do
                # único cargo do concurso. A atribuição fica registrada e é revisável.
                vacancy_scopes = {key for key, value in by_scope.items()
                                  if key[0] == cid and key[1] and value.get("immediate")}
                if (len(unscoped) == 1
                        and len([key for key in cargolike if key[0] == cid]) == 1
                        and len(vacancy_scopes) == 1):
                    si_view, si_items, education = _si_state(unscoped)
                    atribuicao = "unico_cargo_do_concurso"
        if not scope:
            unscoped = contest_entry.get("si_unscoped") or []
            labels_in_contest = len([key for key in cargolike if key[0] == cid])
            multi = labels_in_contest != 1
            if multi:
                # Vários cargos: a leitura do concurso é agregada, não é elegibilidade
                # de cargo nenhum. A linha do concurso serve só para diagnóstico.
                si_view, si_items = "nao_encontrado", si_items
                atribuicao = "agregado_do_concurso"
            elif unscoped and not (contest_entry.get("si")):
                si_view, si_items, education = _si_state(unscoped)
                atribuicao = "declaracao_do_concurso"
        identity_state = ("reconciliado" if raw.get("role_reconciliado")
                          else "pendente" if scope.startswith("label:")
                          else "reconciliado")
        if not scope:
            identity_state = "reconciliado"
        mention = mentions.get(cid)
        indigenous_state, indigenous_evidence = _indigenous_state(
            entry.get("indigenous") or [], entry.get("indigenous_reserve") or [],
            contest_entry.get("indigenous") or [],
            contest_entry.get("indigenous_reserve") or [],
            mention, cid in analyzed)
        if not scope:
            # Linha do concurso: se a informação está por cargo, não se distribui nem
            # se inventa um total; apenas se declara onde ela está.
            distributed = any(key[0] == cid and key[1]
                              and (value.get("indigenous")
                                   or value.get("indigenous_reserve"))
                              for key, value in by_scope.items())
            if distributed:
                indigenous_state = "distribuido_por_cargo"
                indigenous_evidence = []
        elig = _eligibility(si_view, indigenous_state, identity_state, bool(scope))
        deadlines = portfolio._deadlines_for(calendar_items, cid, scope)
        temporal_state = _temporal(deadlines)
        conflicts = bool(dec_by.get(cid, {}).get("conflitos"))
        view = {
            "contest_id": cid,
            "contest_label": portfolio._contest_label(raw, pages),
            "competition_id": raw.get("competition_id"),
            "role_id": raw.get("role_id"),
            "role_name": raw.get("role_name"),
            "scope": scope,
            "identity": identity_state,
            "profile": {"id": profile_entry["id"], "label": profile_entry["label"]},
            "si": {"estado": si_view,
                   "estado_label": decisive_fields.SI_VIEW_LABELS.get(
                       si_view, "Sem leitura de compatibilidade"),
                   "atribuicao": atribuicao,
                   "educacao": education,
                   "evidencias": si_items},
            "cargo": {
                "codigo": _code_of(scope_key),
                "familia": _family(raw.get("role_name") or scope),
                "localidade": _locality(entry),
                "rotulos": [],
            },
            "indigenous": {"estado": indigenous_state,
                           "estado_label": INDIGENOUS_SCOPE_LABELS[indigenous_state],
                           "ambito": ("cargo" if indigenous_state.startswith("cargo_")
                                      else "concurso" if indigenous_state in
                                      ("concurso_imediata_sem_distribuicao",
                                       "distribuido_por_cargo")
                                      else "indefinido"),
                           "evidencias": indigenous_evidence},
            "vacancies": {
                "immediate": [_brief(row) for row in (entry.get("immediate") or [])],
                "reserve": [_brief(row) for row in (entry.get("reserve") or [])],
                "indigenous_reserve": [_brief(row) for row in
                                       (entry.get("indigenous_reserve") or [])],
                "aggregate": [_brief(row) for row in (entry.get("aggregate") or [])],
            },
            "eligibility": {"estado": elig, "estado_label": ELIGIBILITY_LABELS[elig],
                            "motivo": _reason(elig, si_view, indigenous_state,
                                              identity_state, atribuicao)},
            "temporal": {"estado": temporal_state,
                         "estado_label": TEMPORAL_LABELS[temporal_state],
                         "prazos": [{key: entry_[key] for key in
                                     ("grupo", "grupo_label", "valor",
                                      "estado_operacional", "urgencia",
                                      "dias_restantes", "documento", "pagina")}
                                    for entry_ in deadlines]},
            "documental": raw.get("documental"),
            "conflitos": conflicts,
            "localizacao": (dec_by.get(cid, {}).get("local") or {}),
            "proxima_acao": ACTIONS[elig],
            "dossie": {"contest_id": cid, "role_id": raw.get("role_id"),
                       "scope": scope},
        }
        seen[dedupe_key] = view
        if eligibility and view["eligibility"]["estado"] != eligibility:
            continue
        if indigenous and view["indigenous"]["estado"] != indigenous:
            continue
        if temporal and view["temporal"]["estado"] != temporal:
            continue
        if identity and view["identity"] != identity:
            continue
        if si and view["si"]["estado"] != si:
            continue
        if uf:
            prova = ((view["localizacao"] or {}).get("prova") or {})
            if (prova.get("uf") or "").upper() != uf.upper():
                continue
        if conflict is True and not view["conflitos"]:
            continue
        if conflict is False and view["conflitos"]:
            continue
        if search:
            needle = search.strip().lower()
            haystack = " ".join(str(view.get(key) or "") for key in
                                ("contest_label", "competition_id", "role_name"))
            if needle not in haystack.lower():
                continue
        items.append(view)

    for view in items:
        key = (view["contest_id"], _norm_scope(view["scope"]))
        labels = labels_by_key.setdefault(key, set())
        labels.add(view.get("role_name") or view.get("scope") or "")
        view["rotulos"] = sorted(label for label in labels if label)
        view["cargo"]["rotulos"] = view["rotulos"]

    rank = {state: index for index, state in enumerate(ELIGIBILITY_STATES)}
    items.sort(key=lambda item: (rank[item["eligibility"]["estado"]],
                                 item["temporal"]["estado"] != "revalidado_na_fonte",
                                 item["contest_id"], item["scope"]))
    total = len(items)
    by_eligibility, by_indigenous, by_temporal, by_identity = {}, {}, {}, {}
    by_si, by_education = {}, {}
    for item in items:
        by_si[item["si"]["estado"]] = by_si.get(item["si"]["estado"], 0) + 1
        educacao = item["si"].get("educacao") or {}
        kind = educacao.get("kind") or "indefinido"
        by_education[kind] = by_education.get(kind, 0) + 1
        by_eligibility[item["eligibility"]["estado"]] = (
            by_eligibility.get(item["eligibility"]["estado"], 0) + 1)
        by_indigenous[item["indigenous"]["estado"]] = (
            by_indigenous.get(item["indigenous"]["estado"], 0) + 1)
        by_temporal[item["temporal"]["estado"]] = (
            by_temporal.get(item["temporal"]["estado"], 0) + 1)
        by_identity[item["identity"]] = by_identity.get(item["identity"], 0) + 1
    return {
        "version": ELIGIBILITY_VERSION, "generated_at": now_dt.isoformat(),
        "profile": {"id": profile_entry["id"], "label": profile_entry["label"]},
        "total": total,
        "por_elegibilidade": by_eligibility,
        "por_indigena": by_indigenous,
        "por_temporal": by_temporal,
        "por_identidade": by_identity,
        "por_si": by_si,
        "por_requisito_educacional": by_education,
        "denominador": {
            "unidade": "oportunidade (concurso × cargo/rótulo)",
            "universo": "todo grupo de oportunidades com propostas extraídas",
            "filtros": {"eligibility": eligibility, "indigenous": indigenous,
                        "temporal": temporal, "identity": identity, "si": si,
                        "uf": uf, "conflict": conflict, "search": search,
                        "contest_id": contest_id, "role_id": role_id},
            "precedencia": list(ELIGIBILITY_STATES),
            "indigena": ("cargo_* vem de tabela com linha por cargo; "
                         "concurso_imediata_sem_distribuicao nunca é distribuído por cargo"),
        },
        "limit": limit, "offset": offset, "has_more": offset + limit < total,
        "itens": items[offset:offset + limit],
        "limitacao": ("Elegibilidade é candidata, não confirmação. Requisito ausente não é "
                      "incompatibilidade. Reserva do concurso não é vaga do cargo. Nada é "
                      "decidido aqui."),
    }


def _reason(elig, si_view, indigenous_state, identity, atribuicao=None):
    if elig == "incompativel_por_requisito":
        if atribuicao == "unico_cargo_do_concurso":
            return ("requisito declarado no mesmo documento, atribuído ao único cargo do "
                    "concurso (revisável)")
        if atribuicao == "declaracao_do_concurso":
            return "requisito de formação declarado no âmbito do concurso"
        return "o requisito extraído aponta formação diferente do perfil"
    if elig == "compativel_com_vaga_indigena_cargo":
        return ("requisito sustenta o perfil e a tabela do edital publica vaga indígena "
                "para este cargo")
    if elig == "compativel_sem_vaga_indigena":
        return "requisito sustenta o perfil; a reserva indígena não está quantificada no cargo"
    if elig == "compativel_por_interpretacao":
        return "o requisito é de área correlata e exige interpretação humana"
    if elig == "identidade_pendente":
        return "o rótulo do documento não foi reconciliado com identidade canônica"
    return "não há leitura de compatibilidade para este cargo"

HIGHLIGHT_STATES = ("compativel_com_vaga_indigena_cargo", "compativel_sem_vaga_indigena",
                    "compativel_por_nivel_minimo", "compativel_por_interpretacao")
MAX_PER_CONTEST = 2


def highlights(db_path, *, profile=None, limit=12, now=None) -> dict:
    """Destaques por elegibilidade: só o que o requisito sustenta, com motivo legível.

    Cargo incompatível por requisito expresso **não** entra, ainda que tenha vaga indígena
    imediata: reserva não torna o cargo elegível para o perfil.
    """
    limit = int(limit)
    if limit < 1 or limit > 50:
        raise ValueError("limite fora da faixa")
    report = matrix(db_path, profile=profile, limit=200, offset=0, now=now)
    candidates = list(report["itens"])
    offset = report["limit"]
    while report["has_more"] and offset <= 5000:
        report = matrix(db_path, profile=profile, limit=200, offset=offset, now=now)
        candidates.extend(report["itens"])
        offset += report["limit"]
    selected, per_contest = [], {}
    for item in candidates:
        if not item.get("scope"):
            continue  # a linha do concurso não é cargo
        if item["eligibility"]["estado"] not in HIGHLIGHT_STATES:
            continue
        contest = item["contest_id"]
        if per_contest.get(contest, 0) >= MAX_PER_CONTEST:
            continue
        reasons = []
        if item["eligibility"]["estado"] == "compativel_com_vaga_indigena_cargo":
            reasons.append("requisito sustenta o perfil")
            reasons.append("vaga indígena imediata publicada para este cargo")
        elif item["eligibility"]["estado"] == "compativel_por_nivel_minimo":
            reasons.append("escolaridade mínima publicada, sem curso específico exigido")
            if item["si"].get("educacao"):
                reasons.append("nível " + item["si"]["educacao"]["nivel"])
        elif item["eligibility"]["estado"] == "compativel_sem_vaga_indigena":
            reasons.append("requisito sustenta o perfil")
            if item["indigenous"]["estado"] == "cargo_sem_imediata_com_reserva":
                reasons.append("reserva indígena do cargo sem vaga imediata")
            elif item["indigenous"]["estado"] == "cargo_explicito_zero":
                reasons.append("tabela do cargo publica zero indígena")
            else:
                reasons.append("reserva indígena não quantificada para o cargo")
        else:
            reasons.append("requisito de área correlata: exige interpretação humana")
        if item["temporal"]["estado"] == "revalidado_na_fonte":
            reasons.append("prazo futuro com documento oficial inalterado")
        elif item["temporal"]["estado"] == "candidato":
            reasons.append("prazo futuro candidato, ainda não revalidado")
        elif item["temporal"]["estado"] == "conflito":
            reasons.append("prazo em conflito documental")
        item["motivo_inclusao"] = reasons
        per_contest[contest] = per_contest.get(contest, 0) + 1
        selected.append(item)
        if len(selected) >= limit:
            break
    return {
        "version": ELIGIBILITY_VERSION, "generated_at": _now(now).isoformat(),
        "profile": report["profile"],
        "total": len(selected), "candidatos": len(candidates),
        "concursos": len(per_contest), "limit": limit,
        "has_more": len(candidates) > len(selected),
        "criterio": ("Somente cargo cujo requisito sustenta o perfil (expresso, categoria "
                     "ou correlato). Cargo incompatível por requisito expresso fica fora, "
                     "mesmo com vaga indígena. No máximo dois cargos por concurso."),
        "itens": selected,
        "limitacao": ("Destaque não é confirmação. Reserva do concurso não é vaga do cargo. "
                      "Nenhuma decisão humana é criada."),
    }

# Causas de identidade pendente. Cada rótulo recebe **uma** causa principal, com a
# evidência que a sustenta; a ordem é a da precedência aplicada em `_pending_cause`.
PENDING_CAUSES = (
    "duplicata_de_identidade",
    "codigo_sem_nome",
    "ambiguidade_entre_identidades",
    "sem_cargo_canonico",
    "evidencia_insuficiente",
    "aguarda_decisao_humana",
)
PENDING_CAUSE_LABELS = {
    "duplicata_de_identidade": ("Há duas identidades canônicas iguais no concurso: "
                                "consolidar exige decisão humana"),
    "codigo_sem_nome": "Rótulo é apenas um código, sem nome de cargo",
    "ambiguidade_entre_identidades": "Sugestão empata entre identidades distintas",
    "sem_cargo_canonico": "O concurso não tem identidade canônica para receber o rótulo",
    "evidencia_insuficiente": "Não há candidato estrutural sustentado",
    "aguarda_decisao_humana": ("Há candidato estrutural; falta decisão humana "
                              "(nada é confirmado automaticamente)"),
}


def _pending_cause(item) -> str:
    if item["state"] == "duplicata_de_identidade":
        return "duplicata_de_identidade"
    if item["nature"] == "codigo_sem_nome":
        return "codigo_sem_nome"
    if item["state"] == "ambigua":
        return "ambiguidade_entre_identidades"
    if item["cargo_count"] == 0:
        return "sem_cargo_canonico"
    if item["state"] == "evidencia_insuficiente":
        return "evidencia_insuficiente"
    return "aguarda_decisao_humana"


def pending_audit(db_path, *, contest_id=None, cause=None, limit=200, offset=0,
                  now=None) -> dict:
    """Auditoria dos rótulos com identidade pendente, por causa e por concurso.

    Diagnóstico puro: não cria decisão, não funde cargos e não altera propostas.
    """
    limit = int(limit)
    offset = int(offset)
    if limit < 1 or limit > 500:
        raise ValueError("limite fora da faixa")
    if offset < 0:
        raise ValueError("deslocamento inválido")
    if cause and cause not in PENDING_CAUSES:
        raise ValueError("causa inválida")
    now_dt = _now(now)
    inventory = role_identity.label_inventory(db_path, contest_id=contest_id,
                                              limit=100000)
    items = []
    for item in inventory["itens"]:
        if item["state"] in ("confirmada", "rejeitada", "nao_e_cargo"):
            continue
        if item["nature"] == "nao_e_cargo":
            continue
        cause_value = _pending_cause(item)
        if cause and cause_value != cause:
            continue
        top = item["suggestions"][0] if item["suggestions"] else None
        items.append({
            "contest_id": item["contest_id"], "label": item["label"],
            "nature": item["nature"], "nature_label": item["nature_label"],
            "state": item["state"], "state_label": item["state_label"],
            "cause": cause_value, "cause_label": PENDING_CAUSE_LABELS[cause_value],
            "codigo": _code_of("label:" + item["label"]),
            "familia": _family(item["label"]),
            "proposals": item["proposals"],
            "cargo_count": item["cargo_count"],
            "suggestions": [{"role_id": entry["role_id"],
                             "role_name": entry["role_name"],
                             "pontuacao": entry["pontuacao"],
                             "state": entry["state"]}
                            for entry in item["suggestions"][:3]],
            "sugestao": ({"role_name": top["role_name"], "pontuacao": top["pontuacao"],
                          "state": top["state"]} if top else None),
            "identidades_duplicadas": len(item["identidades_duplicadas"]),
            "evidencia": item["first_evidence"],
        })
    items.sort(key=lambda entry: (entry["contest_id"], entry["label"]))
    total = len(items)
    by_cause, by_contest, by_nature = {}, {}, {}
    for entry in items:
        by_cause[entry["cause"]] = by_cause.get(entry["cause"], 0) + 1
        by_contest[entry["contest_id"]] = by_contest.get(entry["contest_id"], 0) + 1
        by_nature[entry["nature"]] = by_nature.get(entry["nature"], 0) + 1
    return {
        "version": ELIGIBILITY_VERSION, "generated_at": now_dt.isoformat(),
        "total": total, "por_causa": by_cause, "por_concurso": by_contest,
        "por_natureza": by_nature,
        "com_sugestao": sum(1 for entry in items if entry["sugestao"]),
        "sem_sugestao": sum(1 for entry in items if not entry["sugestao"]),
        "limit": limit, "offset": offset, "has_more": offset + limit < total,
        "itens": items[offset:offset + limit],
        "limitacao": ("Diagnóstico de identidade: sugere causa, não confirma cargo. "
                      "Consolidar duplicatas e criar identidade são decisões humanas."),
    }


def compatibility_review(db_path, *, profile=None, limit=50, now=None) -> dict:
    """Fichas dos cargos com leitura de formação, para revisão humana.

    Cobre os estados que sustentam (ou quase sustentam) compatibilidade, incluindo nível
    mínimo. Mostra valor armazenado, leitura derivada do texto e a evidência.
    """
    limit = int(limit)
    if limit < 1 or limit > 200:
        raise ValueError("limite fora da faixa")
    now_dt = _now(now)
    report = matrix(db_path, profile=profile, limit=200, offset=0, now=now_dt)
    items = list(report["itens"])
    offset = report["limit"]
    while report["has_more"] and offset <= 5000:
        report = matrix(db_path, profile=profile, limit=200, offset=offset, now=now_dt)
        items.extend(report["itens"])
        offset += report["limit"]
    fichas = []
    for item in items:
        if item["si"]["estado"] == "nao_encontrado":
            continue
        evidencias = item["si"]["evidencias"]
        stored = sorted({entry["value"] for entry in evidencias})
        fichas.append({
            "contest_id": item["contest_id"], "contest_label": item["contest_label"],
            "role_name": item["role_name"], "scope": item["scope"],
            "codigo": item["cargo"]["codigo"], "familia": item["cargo"]["familia"],
            "localidade": item["cargo"]["localidade"],
            "identity": item["identity"],
            "eligibility": item["eligibility"],
            "si_estado": item["si"]["estado"], "si_label": item["si"]["estado_label"],
            "atribuicao": item["si"]["atribuicao"],
            "educacao": item["si"].get("educacao"),
            "valor_armazenado": stored,
            "evidencias": evidencias[:3],
            "indigena": {"estado": item["indigenous"]["estado"],
                         "ambito": item["indigenous"]["ambito"]},
            "pendencia": ("confirmar leitura do requisito e, se aplicável, a reserva "
                          "indígena do cargo"),
        })
    fichas.sort(key=lambda entry: (entry["si_estado"], entry["contest_id"],
                                   entry["scope"]))
    total = len(fichas)
    by_state = {}
    for entry in fichas:
        by_state[entry["si_estado"]] = by_state.get(entry["si_estado"], 0) + 1
    return {"version": ELIGIBILITY_VERSION, "generated_at": now_dt.isoformat(),
            "total": total, "por_si": by_state, "limit": limit,
            "itens": fichas[:limit],
            "limitacao": ("Ficha de revisão: o estado é candidato. Confirmar exige decisão "
                          "humana no fluxo existente.")}
