"""Central de revisão humana: fila priorizada, evidências, decisões e lotes.

Regras de domínio que este módulo respeita:

- proposta extraída **não** é valor confirmado; só uma decisão humana registrada muda o estado;
- toda decisão é *append-only* (nova linha em ``revisoes_campo``, com estado anterior, canal e
  impressão da evidência revisada) — nada é sobrescrito nem apagado;
- corrigir um valor cria uma proposta derivada (``extraction_method='correcao_humana'``) que
  aponta para a **evidência original**; a proposta original continua existindo;
- o lote é ferramenta de navegação, **não** autorização de aprovação em massa;
- decisão importada de arquivo só é aceita se a evidência e o valor não mudaram desde a
  exportação; caso contrário vai para nova revisão.
"""

from __future__ import annotations

import json
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

from radar.document_store import connect_documents, is_readable_schema
from radar.document_types import is_nominal_title

REVIEW_VERSION = "review_v1"

DECISIONS = ("validado", "rejeitado", "adiado", "ambiguo", "nova_extracao", "reaberto",
             "corrigido")
# Decisões que encerram a pendência do item.
DECIDED_STATES = ("validado", "rejeitado", "corrigido")
ORIGINS = ("interface", "cli", "importacao")

STATE_LABELS = {
    "pendente": "Pendente de revisão",
    "validado": "Validado por humano",
    "rejeitado": "Rejeitado por humano",
    "adiado": "Adiado",
    "ambiguo": "Marcado como ambíguo",
    "nova_extracao": "Nova extração solicitada",
    "corrigido": "Corrigido por humano",
    "selecionado": "Valor vigente",
}

# Campos cuja revisão muda a decisão prática do candidato.
# Campos que legitimamente têm vários valores no mesmo escopo (por cargo/localidade):
# não são "conflito escalar". `vagas_total_publicado` é o total de **cada linha** do quadro.
MULTI_VALUE_FIELDS = {"vagas_total_publicado", "conteudo_secao", "conteudo_disciplina",
                      "conteudo_topico", "conteudo_subtopico", "accepted_courses"}

DECISIVE_FIELDS = (
    "immediate_vacancies", "indigenous_vacancies", "indigenous_reserve_vacancies",
    "education", "si_compatibility", "exam_location", "registration_end", "exemption_end",
)

DEADLINE_FIELDS = ("registration_end", "exemption_end")

# Pontuação declarada, não opaca: cada fator aparece na resposta com o motivo.
FACTOR_POINTS = {
    "edital_oficial": 2,
    "prazo_proximo": 3,
    "campo_decisivo": 3,
    "conflito": 2,
    "evidencia_curta": 1,
    "documento_mais_recente": 1,
    # Fase 31: erro em vaga indígena cria falsa oportunidade; formação decide elegibilidade.
    "vaga_indigena": 4,
    "formacao_si": 3,
    "duplicata": 1,
    "trecho_fraco": -2,
    "sem_pagina": -1,
}

FACTOR_LABELS = {
    "edital_oficial": "Concurso com edital oficial registrado",
    "prazo_proximo": "Prazo documentado nos próximos 30 dias",
    "campo_decisivo": "Campo decisivo para a decisão do candidato",
    "conflito": "Há valores divergentes para o mesmo campo",
    "evidencia_curta": "Trecho curto: revisão rápida",
    "documento_mais_recente": "Documento mais recente do conflito",
    "vaga_indigena": "Vaga reservada a indígena: erro cria falsa oportunidade",
    "formacao_si": "Formação/aceitação de Sistemas de Informação: decide elegibilidade",
    "duplicata": "Proposta em grupo de duplicidade textual",
    "trecho_fraco": "Trecho muito curto: evidência fraca",
    "sem_pagina": "Evidência sem número de página",
}

SHORT_QUOTE = 240
WEAK_QUOTE = 20
DEADLINE_WINDOW_DAYS = 30
MAX_BATCH_SIZE = 100


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_text(value, message):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(message)
    return value.strip()


def _parse_date(value):
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _evidence_hash(value_json, quote, version_id, start_offset, end_offset) -> str:
    """Impressão estável da evidência + valor revisado (detecta versão desatualizada)."""
    payload = json.dumps([value_json, quote, version_id, start_offset, end_offset],
                         ensure_ascii=False, sort_keys=True)
    return sha256(payload.encode("utf-8")).hexdigest()


OPEN_STATES = ("pendente", "adiado", "ambiguo", "nova_extracao")


def _state(last_decision, selected: bool) -> str:
    # "Selecionado" só vale se a decisão mais recente ainda é validada: uma proposta
    # rejeitada depois de selecionada não é o valor vigente.
    if selected and last_decision == "validado":
        return "selecionado"
    if not last_decision or last_decision == "reaberto":
        return "pendente"
    return last_decision


def _is_open(row) -> bool:
    return _state(row["last_decision"], row["selected"]) in OPEN_STATES


def _value_of(value_json):
    try:
        return json.loads(value_json)
    except (TypeError, ValueError):
        return value_json


def _rows(conn) -> list[dict]:
    rows = []
    query = """
        SELECT p.id, p.contest_id, p.role_id, p.field_name, p.value_json, p.value_type,
               p.extraction_method, p.ambiguity_reason, p.extracted_at,
               e.id, e.quote, e.page_number, e.locator, e.start_offset, e.end_offset,
               v.id, v.sha256, v.fetched_at, v.published_at,
               d.id, d.title, d.official_url, d.issuer, d.published_at, d.tipo_documental,
               d.kind, o.competition_id,
               (SELECT r.decision FROM revisoes_campo r WHERE r.proposal_id=p.id
                ORDER BY r.reviewed_at DESC, r.rowid DESC LIMIT 1) AS last_decision,
               (SELECT r.reviewed_at FROM revisoes_campo r WHERE r.proposal_id=p.id
                ORDER BY r.reviewed_at DESC, r.rowid DESC LIMIT 1) AS last_review_at,
               (SELECT COUNT(*) FROM valores_atuais va WHERE va.proposal_id=p.id
                AND va.id = (SELECT v2.id FROM valores_atuais v2
                             WHERE v2.contest_id=p.contest_id
                               AND v2.role_id IS p.role_id
                               AND v2.field_name=p.field_name
                             ORDER BY v2.selected_at DESC, v2.rowid DESC LIMIT 1)) AS selected,
               e.block_id
        FROM propostas_campo p
        JOIN evidencias e ON e.id=p.evidence_id
        JOIN versoes_documento v ON v.id=e.version_id
        JOIN documentos d ON d.id=v.document_id
        LEFT JOIN observacoes_concurso o ON o.id=d.observation_id
        JOIN concursos_identidade c ON c.id=p.contest_id
        WHERE c.estado_identidade='certame'
        ORDER BY p.id
    """
    for row in conn.execute(query):
        rows.append({
            "proposal_id": row[0], "contest_id": row[1], "role_id": row[2],
            "field_name": row[3], "value_json": row[4], "value_type": row[5],
            "extraction_method": row[6], "ambiguity_reason": row[7], "extracted_at": row[8],
            "evidence_id": row[9], "quote": row[10] or "", "page_number": row[11],
            "locator": row[12], "start_offset": row[13], "end_offset": row[14],
            "version_id": row[15], "sha256": row[16], "fetched_at": row[17],
            "version_published_at": row[18],
            "document_id": row[19], "document_title": row[20], "official_url": row[21],
            "issuer": row[22], "published_at": row[23], "tipo_documental": row[24],
            "kind": row[25], "competition_id": row[26],
            "last_decision": row[27], "last_review_at": row[28], "selected": bool(row[29]),
            "block_id": row[30],
        })
    return rows


def _official_editais(conn) -> set[str]:
    return {row[0] for row in conn.execute(
        "SELECT DISTINCT contest_id FROM documentos "
        "WHERE tipo_documental IN ('edital_abertura','edital_retificado')")}


def _deadlines(rows) -> dict[str, date]:
    """Prazo documentado mais próximo por concurso (só propostas abertas e com data legível)."""
    out = {}
    for row in rows:
        if row["field_name"] not in DEADLINE_FIELDS or not _is_open(row):
            continue
        when = _parse_date(_value_of(row["value_json"]))
        if when is None:
            continue
        current = out.get(row["contest_id"])
        if current is None or when < current:
            out[row["contest_id"]] = when
    return out


def _reconciled_map(conn) -> dict:
    """Mapa (concurso, rótulo) → cargo, a partir da reconciliação humana registrada.

    A reconciliação não reescreve propostas antigas; sem consultar este mapa, o mesmo cargo
    apareceria em dois escopos (rótulo e identidade) e um conflito real ficaria invisível.
    """
    mapping = {}
    for contest_id, label, role_id in conn.execute(
            "SELECT contest_id, label, role_id FROM reconciliacoes_cargo"
            " ORDER BY reconciled_at, id"):
        mapping[(contest_id, label)] = role_id
    return mapping


def _label_of(row) -> str | None:
    reason = row.get("ambiguity_reason") or ""
    prefix = "cargo do documento não reconciliado: "
    if not reason.startswith(prefix):
        return None
    label = reason[len(prefix):].split(" — ")[0].strip()
    return label or None


def role_scope(row, reconciled=None) -> tuple[str, str | None]:
    """Escopo de cargo: identidade reconciliada ou rótulo do próprio documento.

    Sem identidade canônica, o rótulo do edital é o único escopo honesto. Sem isso, todos os
    cargos de um mesmo documento seriam tratados como um só e valores de cargos diferentes
    apareceriam como conflito — divergência que não existe. Quando o rótulo já foi
    reconciliado por decisão humana, o escopo é a identidade canônica.
    """
    if row.get("role_id"):
        return row["role_id"], None
    label = _label_of(row)
    if not label:
        return "", None
    mapped = (reconciled or {}).get((row["contest_id"], label))
    if mapped:
        return mapped, label
    return f"label:{label}", label


def _scope_key(row, reconciled=None) -> tuple:
    return (row["contest_id"], role_scope(row, reconciled)[0], row["field_name"])


def _conflicts(rows, reconciled=None) -> dict[tuple, list[dict]]:
    """Conflito só entre propostas abertas do **mesmo escopo** de cargo."""
    groups = {}
    for row in rows:
        if not _is_open(row):
            continue
        if row["field_name"] in MULTI_VALUE_FIELDS:
            continue  # vários valores por cargo/localidade: não é conflito escalar
        groups.setdefault(_scope_key(row, reconciled), []).append(row)
    conflicts = {}
    for key, items in groups.items():
        values = {item["value_json"] for item in items}
        if len(values) > 1:
            conflicts[key] = items
    return conflicts


INDIGENOUS_FIELDS = ("indigenous_vacancies", "indigenous_reserve_vacancies")
FORMATION_FIELDS = ("education", "accepted_courses", "si_compatibility")


def _priority(row, *, editais, deadlines, conflicts, duplicates, today,
              reconciled=None) -> tuple[int, list[dict]]:
    factors = []

    def add(name, motivo=None):
        factors.append({"fator": name, "pontos": FACTOR_POINTS[name],
                        "motivo": motivo or FACTOR_LABELS[name]})

    if row["contest_id"] in editais:
        add("edital_oficial")
    deadline = deadlines.get(row["contest_id"])
    if deadline is not None and today <= deadline <= today + timedelta(days=DEADLINE_WINDOW_DAYS):
        add("prazo_proximo", f"prazo documentado em {deadline.isoformat()}")
    if row["field_name"] in DECISIVE_FIELDS:
        add("campo_decisivo", f"campo decisivo: {row['field_name']}")
    if row["field_name"] in INDIGENOUS_FIELDS:
        add("vaga_indigena", f"vaga reservada a indígena: {row['field_name']}")
    if row["field_name"] in FORMATION_FIELDS:
        add("formacao_si", f"formação/elegibilidade: {row['field_name']}")
    if row["proposal_id"] in duplicates:
        add("duplicata", "mesma evidência/valor aparece mais de uma vez")
    group = conflicts.get(_scope_key(row, reconciled))
    if group:
        add("conflito", f"{len({i['value_json'] for i in group})} valores distintos no mesmo campo")
        dates = [i["published_at"] for i in group if i["published_at"]]
        if dates and row["published_at"] == max(dates):
            add("documento_mais_recente")
    quote = row["quote"] or ""
    if len(quote) <= SHORT_QUOTE:
        add("evidencia_curta", f"trecho de {len(quote)} caractere(s)")
    if len(quote) < WEAK_QUOTE:
        add("trecho_fraco", f"trecho de apenas {len(quote)} caractere(s)")
    if row["page_number"] is None:
        add("sem_pagina")
    score = sum(item["pontos"] for item in factors)
    return score, factors


def _matches(row, *, state, conflict, filters, conflicts, reconciled=None) -> bool:
    if filters["contest_id"] and row["contest_id"] != filters["contest_id"]:
        return False
    if filters["role_id"] and row["role_id"] != filters["role_id"]:
        return False
    if filters["field_name"] and row["field_name"] != filters["field_name"]:
        return False
    if filters["document_id"] and row["document_id"] != filters["document_id"]:
        return False
    if filters["source"]:
        needle = filters["source"].lower()
        if needle not in (row["issuer"] or "").lower() and needle not in (row["official_url"] or "").lower():
            return False
    if filters["since"] and (row["published_at"] or "") < filters["since"]:
        return False
    if filters["until"] and (row["published_at"] or "") > filters["until"]:
        return False
    if filters["reviewed_since"] and (row["last_review_at"] or "") < filters["reviewed_since"]:
        return False
    if filters["reviewed_until"] and (row["last_review_at"] or "") > filters["reviewed_until"]:
        return False
    if filters.get("search"):
        needle = filters["search"].lower()
        haystack = " ".join([row["document_title"] or "", row["issuer"] or "",
                              row["field_name"] or "", str(row["value_json"] or "")]).lower()
        if needle not in haystack:
            return False
    has_conflict = _scope_key(row, reconciled) in conflicts
    if conflict is True and not has_conflict:
        return False
    if conflict is False and has_conflict:
        return False
    current = _state(row["last_decision"], row["selected"])
    if state == "pendente" and current != "pendente":
        return False
    if state == "decidido" and current not in DECIDED_STATES:
        return False
    if state == "adiado" and current != "adiado":
        return False
    if state == "selecionado" and current != "selecionado":
        return False
    if state == "aberto" and current in DECIDED_STATES:
        return False
    return True


def _duplicate_members(rows) -> set:
    """Ids de propostas cuja (escopo, campo, valor, bloco, citação) aparece mais de uma vez."""
    groups = {}
    for row in rows:
        key = (row["contest_id"], row["role_id"], row["field_name"], row["value_json"],
               row["block_id"], row["quote"], row["start_offset"], row["end_offset"])
        groups.setdefault(key, []).append(row["proposal_id"])
    members = set()
    for ids in groups.values():
        if len(ids) > 1:
            members.update(ids)
    return members


def duplicate_groups(db_path, *, contest_id=None, field_name=None, limit=50) -> dict:
    """Grupos de propostas com a **mesma evidência e o mesmo valor** (duplicidade textual).

    Distingue duplicidade de conflito: aqui o valor é igual; conflito é valor diferente.
    Nada é apagado — a decisão (rejeitar a redundante) é humana e append-only.
    """
    limit = int(limit)
    if limit < 1 or limit > 200:
        raise ValueError("limite fora da faixa")
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = _rows(conn)
    groups = {}
    for row in rows:
        if contest_id and row["contest_id"] != contest_id:
            continue
        if field_name and row["field_name"] != field_name:
            continue
        key = (row["contest_id"], row["role_id"], row["field_name"], row["value_json"],
               row["block_id"], row["quote"], row["start_offset"], row["end_offset"])
        groups.setdefault(key, []).append(row)
    # Mesmo valor em **spans diferentes** é repetição legítima (sumário x corpo, tabela
    # repetida): não é duplicidade e não deve ser consolidada.
    by_value = {}
    for row in rows:
        if contest_id and row["contest_id"] != contest_id:
            continue
        if field_name and row["field_name"] != field_name:
            continue
        by_value.setdefault((row["contest_id"], row["role_id"], row["field_name"],
                             row["value_json"]), set()).add(
            (row["block_id"], row["start_offset"], row["end_offset"]))
    legítimas = sum(1 for spans in by_value.values() if len(spans) > 1)

    items = []
    for key, members in groups.items():
        if len(members) < 2:
            continue
        # Representante: preferir proposta ainda aberta (rejeitada não é bom ponto de partida).
        ordered = sorted(members, key=lambda m: (
            0 if _state(m["last_decision"], m["selected"]) in OPEN_STATES else 1,
            m["extracted_at"] or "", m["proposal_id"]))
        first = ordered[0]
        members = ordered
        items.append({
            "contest_id": first["contest_id"],
            "role_id": first["role_id"],
            "field_name": first["field_name"],
            "value": _value_of(first["value_json"]),
            "tipo": "duplicidade_textual",
            "motivo": "mesma evidência (bloco e citação) e mesmo valor",
            "representante": members[0]["proposal_id"],
            "membros": [{
                "proposal_id": member["proposal_id"],
                "state": _state(member["last_decision"], member["selected"]),
                "document_id": member["document_id"],
                "document_title": member["document_title"],
                "page_number": member["page_number"],
                "quote": (member["quote"] or "")[:160],
                "extracted_at": member["extracted_at"],
                "extraction_method": member["extraction_method"],
            } for member in members],
        })
    items.sort(key=lambda item: (-len(item["membros"]), item["field_name"]))
    return {"version": REVIEW_VERSION, "total": len(items),
            "propostas_envolvidas": sum(len(item["membros"]) for item in items),
            "excedentes": sum(len(item["membros"]) - 1 for item in items),
            "repeticao_legitima": legítimas,
            "itens": items[:limit],
            "limitacao": ("Duplicidade textual (mesmo trecho e mesmo valor) não é conflito. "
                          "Mesmo valor em trechos diferentes é repetição legítima "
                          "(sumário/corpo) e não deve ser consolidada. Nada é apagado: "
                          "rejeitar a redundante é decisão humana.")}


def review_queue(db_path, *, contest_id=None, role_id=None, field_name=None, document_id=None,
                 source=None, state="pendente", conflict=None, min_priority=None,
                 since=None, until=None, reviewed_since=None, reviewed_until=None,
                 search=None, limit=25, offset=0, now=None) -> dict:
    """Fila priorizada e paginada de propostas, com evidência e fatores explicados.

    ``state`` aceita ``pendente`` (padrão), ``aberto`` (pendente + adiado),
    ``decidido``, ``adiado``, ``selecionado`` ou ``todos``.
    """
    if state not in ("pendente", "aberto", "decidido", "adiado", "selecionado", "todos"):
        raise ValueError("estado de fila inválido")
    limit = int(limit)
    offset = int(offset)
    if limit < 1 or limit > 200:
        raise ValueError("limite fora da faixa")
    if offset < 0:
        raise ValueError("deslocamento inválido")
    now_dt = datetime.fromisoformat(now) if isinstance(now, str) else (now or datetime.now(timezone.utc))
    today = now_dt.date()
    filters = {"contest_id": contest_id, "role_id": role_id, "field_name": field_name,
               "document_id": document_id, "source": source, "since": since, "until": until,
               "reviewed_since": reviewed_since, "reviewed_until": reviewed_until,
               "search": search}

    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = _rows(conn)
        editais = _official_editais(conn)
        reconciled = _reconciled_map(conn)
    conflicts = _conflicts(rows, reconciled)
    deadlines = _deadlines(rows)
    duplicates = _duplicate_members(rows)

    selected = []
    for row in rows:
        if not _matches(row, state=state, conflict=conflict, filters=filters,
                        conflicts=conflicts, reconciled=reconciled):
            continue
        score, factors = _priority(row, editais=editais, deadlines=deadlines,
                                   conflicts=conflicts, duplicates=duplicates, today=today,
                                   reconciled=reconciled)
        if min_priority is not None and score < int(min_priority):
            continue
        selected.append((score, factors, row))

    selected.sort(key=lambda item: (-item[0], item[2]["field_name"], item[2]["proposal_id"]))
    total = len(selected)
    page = selected[offset:offset + limit]

    items = []
    for score, factors, row in page:
        group = conflicts.get(_scope_key(row, reconciled), [])
        items.append({
            "proposal_id": row["proposal_id"],
            "contest_id": row["contest_id"],
            "competition_id": row["competition_id"],
            "role_id": row["role_id"],
            "field_name": row["field_name"],
            "value": _value_of(row["value_json"]),
            "value_type": row["value_type"],
            "state": _state(row["last_decision"], row["selected"]),
            "ambiguity_reason": row["ambiguity_reason"],
            "extraction_method": row["extraction_method"],
            "extracted_at": row["extracted_at"],
            "priority": score,
            "factors": factors,
            "evidence": {
                "quote": (None if is_nominal_title(row["document_title"])
                           else row["quote"]),
                "page_number": row["page_number"],
                "locator": row["locator"],
                "start_offset": row["start_offset"],
                "end_offset": row["end_offset"],
                "document_id": row["document_id"],
                "document_title": row["document_title"],
                "official_url": row["official_url"],
                "issuer": row["issuer"],
                "published_at": row["published_at"],
                "version_id": row["version_id"],
                "sha256": row["sha256"],
                "tipo_documental": row["tipo_documental"],
                "nominal": is_nominal_title(row["document_title"]),
                "limitation": ("documento nominal: trecho não reproduzido (dados pessoais)"
                                if is_nominal_title(row["document_title"])
                                else None if row["quote"]
                                else "sem trecho literal registrado"),
            },
            "conflicts": [
                {"proposal_id": other["proposal_id"],
                 "value": _value_of(other["value_json"]),
                 "document_title": other["document_title"],
                 "published_at": other["published_at"],
                 "state": _state(other["last_decision"], other["selected"])}
                for other in group if other["proposal_id"] != row["proposal_id"]
            ],
            "last_review": ({"decision": row["last_decision"],
                             "reviewed_at": row["last_review_at"]}
                            if row["last_decision"] else None),
            # Impressão estável da evidência: a sessão usa este valor como snapshot para
            # detectar alteração posterior (nova versão/proposta) na retomada.
            "evidence_sha256": _evidence_hash(
                row["value_json"], row["quote"], row["version_id"],
                row["start_offset"], row["end_offset"]),
        })

    by_field = {}
    for _, _, row in selected:
        by_field[row["field_name"]] = by_field.get(row["field_name"], 0) + 1
    by_state = {}
    for _, _, row in selected:
        key = _state(row["last_decision"], row["selected"])
        by_state[key] = by_state.get(key, 0) + 1
    return {
        "version": REVIEW_VERSION,
        "generated_at": now_dt.isoformat(),
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
        "filters": {key: value for key, value in filters.items() if value is not None}
                   | {"state": state, "conflict": conflict},
        "resumo": {"por_campo": by_field, "por_estado": by_state,
                   "com_conflito": sum(1 for _, _, row in selected
                                       if _scope_key(row, reconciled) in conflicts)},
        "items": items,
        "limitacao": ("Prioridade é heurística determinística e explicada; não é probabilidade "
                      "de aprovação. Nenhum item entra como confirmado sem decisão humana."),
    }


def proposal_detail(db_path, proposal_id: str) -> dict:
    """Comparação completa: valor, evidência, conflitos, histórico e valor vigente."""
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = _rows(conn)
        target = next((row for row in rows if row["proposal_id"] == proposal_id), None)
        if target is None:
            raise ValueError("proposta inexistente ou sem evidência válida")
        reviews = [
            {"decision": row[0], "reviewed_at": row[1], "reviewer": row[2], "reason": row[3],
             "previous_decision": row[4], "origin": row[5], "value": _value_of(row[6])
             if row[6] else None, "evidence_sha256": row[7]}
            for row in conn.execute(
                "SELECT decision,reviewed_at,reviewer,reason,previous_decision,origin,value_json,"
                "evidence_sha256 FROM revisoes_campo WHERE proposal_id=? "
                "ORDER BY reviewed_at, rowid", (proposal_id,))]
        current = conn.execute(
            "SELECT proposal_id,selected_at,selected_by,reason FROM valores_atuais "
            "WHERE contest_id=? AND role_id IS ? AND field_name=? "
            "ORDER BY selected_at DESC, rowid DESC LIMIT 1",
            (target["contest_id"], target["role_id"], target["field_name"])).fetchone()
        versions = [
            {"version_id": row[0], "sha256": row[1], "fetched_at": row[2],
             "content_type": row[3], "extraction_state": row[4]}
            for row in conn.execute(
                "SELECT id,sha256,fetched_at,content_type,extraction_state FROM versoes_documento "
                "WHERE document_id=? ORDER BY fetched_at DESC, id DESC",
                (target["document_id"],))]

    group = [row for row in rows
             if (row["contest_id"], row["role_id"], row["field_name"])
             == (target["contest_id"], target["role_id"], target["field_name"])]
    return {
        "version": REVIEW_VERSION,
        "proposal": {
            "proposal_id": target["proposal_id"],
            "contest_id": target["contest_id"],
            "competition_id": target["competition_id"],
            "role_id": target["role_id"],
            "field_name": target["field_name"],
            "value": _value_of(target["value_json"]),
            "value_type": target["value_type"],
            "state": _state(target["last_decision"], target["selected"]),
            "ambiguity_reason": target["ambiguity_reason"],
            "extraction_method": target["extraction_method"],
            "extracted_at": target["extracted_at"],
        },
        "evidence": {
            "quote": (None if is_nominal_title(target["document_title"])
                       else target["quote"]),
            "page_number": target["page_number"],
            "locator": target["locator"],
            "start_offset": target["start_offset"],
            "end_offset": target["end_offset"],
            "document_id": target["document_id"],
            "document_title": target["document_title"],
            "official_url": target["official_url"],
            "issuer": target["issuer"],
            "published_at": target["published_at"],
            "version_id": target["version_id"],
            "sha256": target["sha256"],
            "tipo_documental": target["tipo_documental"],
            "nominal": is_nominal_title(target["document_title"]),
            "limitation": ("documento nominal: trecho não reproduzido (dados pessoais)"
                            if is_nominal_title(target["document_title"])
                            else None if target["quote"]
                            else "sem trecho literal registrado"),
        },
        "other_proposals": [
            {"proposal_id": row["proposal_id"], "value": _value_of(row["value_json"]),
             "state": _state(row["last_decision"], row["selected"]),
             "document_title": row["document_title"], "published_at": row["published_at"],
             "quote": (None if is_nominal_title(row["document_title"]) else row["quote"]),
             "page_number": row["page_number"],
             "sha256": row["sha256"]}
            for row in group if row["proposal_id"] != proposal_id],
        "current_value": ({"proposal_id": current[0], "selected_at": current[1],
                           "selected_by": current[2], "reason": current[3]}
                          if current else None),
        "reviews": reviews,
        "document_versions": versions,
        "evidence_sha256": _evidence_hash(target["value_json"], target["quote"],
                                          target["version_id"], target["start_offset"],
                                          target["end_offset"]),
        "limitacao": ("Proposta não é valor confirmado. Corrigir mantém a evidência original e "
                      "cria proposta derivada identificada como correção humana."),
    }


def _decide_on(conn, proposal_id: str, decision: str, *, reviewer: str, reason: str,
               origin: str, value, expected_evidence_sha256, lote_id, at: str) -> dict:
    """Núcleo da decisão, sobre uma conexão/transação já aberta (usado pela importação)."""
    if not is_readable_schema(conn):
        raise ValueError("migração documental pendente")
    row = conn.execute("""
        SELECT p.contest_id,p.role_id,p.field_name,p.value_json,p.evidence_id,
               e.quote,e.version_id,e.start_offset,e.end_offset,p.ambiguity_reason
        FROM propostas_campo p JOIN evidencias e ON e.id=p.evidence_id
        JOIN versoes_documento v ON v.id=e.version_id
        JOIN documentos d ON d.id=v.document_id
        WHERE p.id=? AND d.contest_id=p.contest_id""", (proposal_id,)).fetchone()
    if not row:
        raise ValueError("proposta sem evidência válida")
    (contest_id, role_id, field_name, value_json, evidence_id, quote, version_id, start, end,
     ambiguity_reason) = row
    fingerprint = _evidence_hash(value_json, quote, version_id, start, end)
    if expected_evidence_sha256 and expected_evidence_sha256 != fingerprint:
        raise ValueError("evidência mudou desde a exportação")
    if lote_id:
        # Retomada de sessão não presume base estática: se a evidência mudou desde a
        # abertura, a decisão precisa ser reavaliada (não se sobrescreve o que o operador
        # não viu).
        item = conn.execute(
            "SELECT snapshot_sha256 FROM lote_revisao_itens WHERE lote_id=? AND proposal_id=?",
            (lote_id, proposal_id)).fetchone()
        if item is None:
            raise ValueError("proposta não pertence ao lote")
        if item[0] and item[0] != fingerprint:
            raise ValueError("evidência mudou desde a abertura da sessão; reavalie o item")
        scope_row = conn.execute(
            "SELECT scope_snapshot FROM lote_revisao_itens WHERE lote_id=? AND proposal_id=?",
            (lote_id, proposal_id)).fetchone()
        if scope_row is None or not scope_row[0]:
            # Lote anterior à v19: não há registro do que o operador viu ao abrir.
            raise ValueError(
                "sessão aberta antes da atualização; reabra o lote para revisar este item")
        try:
            before = set(json.loads(scope_row[0]))
        except ValueError:
            before = None
        if before is None:
            raise ValueError(
                "sessão aberta antes da atualização; reabra o lote para revisar este item")
        reconciled = _reconciled_map(conn)
        scope_name = role_scope({"contest_id": contest_id, "role_id": role_id,
                                 "ambiguity_reason": ambiguity_reason}, reconciled)[0]
        current = {pid for pid, other_role, reason in conn.execute(
            "SELECT id, role_id, ambiguity_reason FROM propostas_campo "
            "WHERE contest_id=? AND field_name=?", (contest_id, field_name))
            if role_scope({"contest_id": contest_id, "role_id": other_role,
                           "ambiguity_reason": reason}, reconciled)[0] == scope_name}
        if current != before:
            raise ValueError(
                "surgiu nova proposta para o mesmo campo desde a abertura da sessão; "
                "reavalie o item")
    last = conn.execute(
        "SELECT decision,reason,origin,value_json FROM revisoes_campo WHERE proposal_id=? "
        "ORDER BY reviewed_at DESC, rowid DESC LIMIT 1", (proposal_id,)).fetchone()
    previous = last[0] if last else None
    corrected_json = json.dumps(value, ensure_ascii=False) if decision == "corrigido" else None
    same = (last is not None and last[0] == decision and last[1] == reason
            and last[2] == origin and last[3] == corrected_json)
    if same:
        derived = conn.execute(
            "SELECT id FROM propostas_campo WHERE evidence_id=? AND field_name=? "
            "AND extraction_method='correcao_humana' AND value_json=? "
            "ORDER BY extracted_at DESC, id DESC LIMIT 1",
            (evidence_id, field_name, corrected_json)).fetchone()
        return {"version": REVIEW_VERSION, "review_id": None, "proposal_id": proposal_id,
                "decision": decision, "previous_decision": previous, "duplicada": True,
                "derived_proposal_id": derived[0] if derived else None,
                "evidence_sha256": fingerprint}

    review_id = str(uuid4())
    conn.execute(
        "INSERT INTO revisoes_campo (id,proposal_id,decision,reviewed_at,reviewer,reason,"
        "previous_decision,origin,value_json,evidence_sha256) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (review_id, proposal_id, decision, at, reviewer, reason, previous, origin,
         corrected_json, fingerprint))
    conn.execute(
        "INSERT INTO eventos_documentais (id,document_id,version_id,event_type,occurred_at,note)"
        " SELECT ?,d.id,v.id,'revisao',?,? FROM propostas_campo p "
        "JOIN evidencias e ON e.id=p.evidence_id JOIN versoes_documento v ON v.id=e.version_id "
        "JOIN documentos d ON d.id=v.document_id WHERE p.id=?",
        (str(uuid4()), at, f"{decision} ({origin})", proposal_id))
    if lote_id:
        conn.execute(
            "UPDATE lote_revisao_itens SET state='decidido', decided_at=? "
            "WHERE lote_id=? AND proposal_id=?", (at, lote_id, proposal_id))

    derived_id = None
    if decision == "corrigido":
        # Correção repetida (mesmo valor) reusa a derivada: não cria duas propostas idênticas.
        existing = conn.execute(
            "SELECT id FROM propostas_campo WHERE evidence_id=? AND field_name=? "
            "AND extraction_method='correcao_humana' AND value_json=? "
            "ORDER BY extracted_at DESC, id DESC LIMIT 1",
            (evidence_id, field_name, corrected_json)).fetchone()
        if existing:
            derived_id = existing[0]
        else:
            derived_id = str(uuid4())
            value_type = ("boolean" if isinstance(value, bool)
                          else "integer" if isinstance(value, int)
                          else "number" if isinstance(value, float) else "string")
            conn.execute(
                "INSERT INTO propostas_campo (id,contest_id,role_id,field_name,value_json,"
                "value_type,evidence_id,extraction_method,ambiguity_reason,extracted_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (derived_id, contest_id, role_id, field_name, corrected_json, value_type,
                 evidence_id, "correcao_humana",
                 f"correção humana de {proposal_id}: {reason}"[:500], at))
            conn.execute(
                "INSERT INTO revisoes_campo (id,proposal_id,decision,reviewed_at,reviewer,reason,"
                "previous_decision,origin,value_json,evidence_sha256) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (str(uuid4()), derived_id, "validado", at, reviewer,
                 f"correção humana registrada em {proposal_id}: {reason}", None, origin, None,
                 fingerprint))
    return {"version": REVIEW_VERSION, "review_id": review_id, "proposal_id": proposal_id,
            "decision": decision, "previous_decision": previous, "duplicada": False,
            "derived_proposal_id": derived_id, "evidence_sha256": fingerprint}


def decide_proposal(db_path, proposal_id: str, decision: str, *, reviewer: str, reason: str,
                    origin: str = "interface", value=None, expected_evidence_sha256=None,
                    lote_id=None, now=None) -> dict:
    """Registra decisão humana append-only. Idempotente para repetição idêntica."""
    if decision not in DECISIONS:
        raise ValueError("decisão inválida")
    reviewer = _require_text(reviewer, "revisor obrigatório")
    reason = _require_text(reason, "justificativa obrigatória")
    if origin not in ORIGINS:
        raise ValueError("origem da decisão inválida")
    if decision == "corrigido":
        if isinstance(value, str):
            if not value.strip():
                raise ValueError("correção exige valor não vazio")
        elif isinstance(value, bool):
            pass
        elif not isinstance(value, (int, float)):
            raise ValueError("correção exige valor escalar")
    at = now or _now()
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        return _decide_on(conn, proposal_id, decision, reviewer=reviewer, reason=reason,
                          origin=origin, value=value,
                          expected_evidence_sha256=expected_evidence_sha256,
                          lote_id=lote_id, at=at)


def select_current_value(db_path, proposal_id: str, reviewer: str, reason: str, *,
                         origin: str = "interface", now=None) -> dict:
    """Seleciona o valor vigente. Idempotente: repetir não cria outra seleção."""
    reviewer = _require_text(reviewer, "revisor obrigatório")
    reason = _require_text(reason, "justificativa obrigatória")
    if origin not in ORIGINS:
        raise ValueError("origem da decisão inválida")
    at = now or _now()
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("""
            SELECT p.contest_id,p.role_id,p.field_name,p.ambiguity_reason
            FROM propostas_campo p JOIN evidencias e ON e.id=p.evidence_id
            JOIN versoes_documento v ON v.id=e.version_id
            JOIN documentos d ON d.id=v.document_id
            WHERE p.id=? AND d.contest_id=p.contest_id""", (proposal_id,)).fetchone()
        if not row:
            raise ValueError("proposta sem evidência válida")
        last = conn.execute(
            "SELECT decision FROM revisoes_campo WHERE proposal_id=? "
            "ORDER BY reviewed_at DESC,rowid DESC LIMIT 1", (proposal_id,)).fetchone()
        if not last or last[0] != "validado":
            raise ValueError("proposta exige revisão validada mais recente")
        contest_id, role_id, field_name, ambiguity_reason = row
        if role_id is None:
            from radar.document_fields import label_from_ambiguity
            label = label_from_ambiguity(ambiguity_reason)
            if label:
                reconciled = conn.execute(
                    "SELECT role_id FROM reconciliacoes_cargo WHERE contest_id=? AND label=? "
                    "ORDER BY reconciled_at DESC,id DESC LIMIT 1",
                    (contest_id, label)).fetchone()
                if reconciled:
                    role_id = reconciled[0]
        prior = conn.execute(
            "SELECT id,proposal_id FROM valores_atuais WHERE contest_id=? AND role_id IS ? "
            "AND field_name=? ORDER BY selected_at DESC,id DESC LIMIT 1",
            (contest_id, role_id, field_name)).fetchone()
        if prior and prior[1] == proposal_id:
            return {"version": REVIEW_VERSION, "selection_id": prior[0], "duplicada": True,
                    "contest_id": contest_id, "role_id": role_id, "field_name": field_name}
        selection_id = str(uuid4())
        conn.execute(
            "INSERT INTO valores_atuais VALUES (?,?,?,?,?,?,?,?,?)",
            (selection_id, contest_id, role_id, field_name, proposal_id, at, reviewer,
             prior[0] if prior else None, reason))
    return {"version": REVIEW_VERSION, "selection_id": selection_id, "duplicada": False,
            "contest_id": contest_id, "role_id": role_id, "field_name": field_name}


# --- lotes de revisão -------------------------------------------------------

def _batch(db_path, lote_id):
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        row = conn.execute(
            "SELECT id,created_at,created_by,origin,filters_json,size,state,cursor,note "
            "FROM lotes_revisao WHERE id=?", (lote_id,)).fetchone()
        if not row:
            raise ValueError("lote inexistente")
        items = conn.execute(
            "SELECT i.position,i.proposal_id,i.state,i.decided_at,p.field_name,p.value_json,"
            "p.contest_id,p.role_id,"
            "(SELECT r.decision FROM revisoes_campo r WHERE r.proposal_id=p.id "
            " ORDER BY r.reviewed_at DESC,r.rowid DESC LIMIT 1),"
            "i.snapshot_sha256,p.value_json,e.quote,e.version_id,e.start_offset,e.end_offset,"
            "p.extracted_at,i.scope_snapshot,p.ambiguity_reason "
            "FROM lote_revisao_itens i JOIN propostas_campo p ON p.id=i.proposal_id "
            "JOIN evidencias e ON e.id=p.evidence_id "
            "WHERE i.lote_id=? ORDER BY i.position", (lote_id,)).fetchall()
        created_at = row[1]
        reconciled = _reconciled_map(conn)
        # Propostas por escopo no momento da leitura: a mudança é detectada por **conjunto de
        # ids**, não por relógio nem por valor. Uma proposta nova conta mesmo que repita um
        # valor já existente; e o escopo usa o rótulo (ou a identidade reconciliada), não o
        # role_id bruto — senão cargos diferentes cairiam no mesmo conjunto.
        scope_ids = {}
        for proposal_id, contest_id, role_id, field_name, reason in conn.execute(
                "SELECT p.id, p.contest_id, p.role_id, p.field_name, p.ambiguity_reason "
                "FROM propostas_campo p WHERE p.contest_id IN ("
                " SELECT p2.contest_id FROM lote_revisao_itens i "
                " JOIN propostas_campo p2 ON p2.id=i.proposal_id WHERE i.lote_id=?)",
                (lote_id,)):
            scope = role_scope({"contest_id": contest_id, "role_id": role_id,
                                "ambiguity_reason": reason}, reconciled)[0]
            scope_ids.setdefault((contest_id, scope, field_name), set()).add(proposal_id)
    lote = {"lote_id": row[0], "created_at": created_at, "created_by": row[2],
            "origin": row[3], "filters": json.loads(row[4]), "size": row[5],
            "state": row[6], "cursor": row[7], "note": row[8]}
    lote["itens"] = []
    for item in items:
        snapshot = item[9]
        scope_snapshot = item[16]
        live = _evidence_hash(item[10], item[11], item[12], item[13], item[14])
        change = None
        if snapshot is None:
            # Lote aberto antes da v19: não há impressão do que o operador viu.
            change = "sem_snapshot"
        elif snapshot != live:
            change = "evidencia"
        else:
            scope = role_scope({"contest_id": item[6], "role_id": item[7],
                                "ambiguity_reason": item[17]}, reconciled)[0]
            current = sorted(scope_ids.get((item[6], scope, item[4])) or ())
            try:
                before = json.loads(scope_snapshot) if scope_snapshot else None
            except ValueError:
                before = None
            if before is None:
                change = "sem_snapshot"
            elif current != sorted(before):
                change = "nova_proposta"
        lote["itens"].append({
            "position": item[0], "proposal_id": item[1], "batch_state": item[2],
            "decided_at": item[3], "field_name": item[4], "value": _value_of(item[5]),
            "contest_id": item[6], "role_id": item[7],
            "state": _state(item[8], False) if item[8] else "pendente",
            "alterado": change is not None,
            "motivo_alteracao": change,
            "snapshot_sha256": snapshot,
            "evidence_sha256": live,
        })
    lote["progresso"] = {
        "total": len(lote["itens"]),
        "decididos": sum(1 for item in lote["itens"]
                         if item["state"] in DECIDED_STATES or item["batch_state"] == "decidido"),
        "alterados": sum(1 for item in lote["itens"] if item["alterado"]),
    }
    lote["item_atual"] = next(
        (item for item in lote["itens"] if item["position"] == (lote["cursor"] or 1)), None)
    return lote


def open_batch(db_path, *, created_by: str, filters: dict | None = None, size: int = 20,
               origin: str = "interface", note=None, now=None) -> dict:
    """Abre lote pequeno e persistido. Não aprova nada: só enfileira para navegação."""
    created_by = _require_text(created_by, "responsável obrigatório")
    if origin not in ORIGINS:
        raise ValueError("origem do lote inválida")
    size = int(size)
    if size < 1 or size > MAX_BATCH_SIZE:
        raise ValueError("tamanho de lote fora da faixa")
    filters = dict(filters or {})
    allowed = {"contest_id", "role_id", "field_name", "document_id", "source", "state",
               "conflict", "min_priority", "since", "until", "reviewed_since",
               "reviewed_until", "search"}
    unknown = set(filters) - allowed
    if unknown:
        raise ValueError(f"filtro de lote inválido: {', '.join(sorted(unknown))}")
    filters.setdefault("state", "pendente")
    if "conflict" in filters:
        # A interface manda string ("1"/"0"); sem converter, o filtro seria ignorado.
        value = filters["conflict"]
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("1", "true", "yes"):
                filters["conflict"] = True
            elif lowered in ("0", "false", "no"):
                filters["conflict"] = False
            elif lowered == "":
                filters.pop("conflict")
            else:
                raise ValueError("filtro de conflito inválido")
        elif not isinstance(value, bool):
            raise ValueError("filtro de conflito inválido")
    queue = review_queue(db_path, limit=size, offset=0, now=now, **filters)
    if not queue["items"]:
        raise ValueError("nenhuma proposta pendente para os filtros")
    at = now or _now()
    lote_id = str(uuid4())
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        reconciled = _reconciled_map(conn)
        conn.execute(
            "INSERT INTO lotes_revisao (id,created_at,created_by,origin,filters_json,size,state,"
            "cursor,note) VALUES (?,?,?,?,?,?,?,?,?)",
            (lote_id, at, created_by, origin, json.dumps(filters, ensure_ascii=False, sort_keys=True),
             size, "aberto", 1, note))
        for position, item in enumerate(queue["items"], start=1):
            # Snapshot da evidência no momento da abertura: permite detectar, na retomada,
            # que o candidato mudou (nova versão/proposta) desde que a sessão começou.
            snapshot = item.get("evidence_sha256")
            row = conn.execute(
                "SELECT p.value_json,e.quote,e.version_id,e.start_offset,e.end_offset,"
                "p.contest_id,p.role_id,p.field_name,p.ambiguity_reason "
                "FROM propostas_campo p JOIN evidencias e ON e.id=p.evidence_id "
                "WHERE p.id=?", (item["proposal_id"],)).fetchone()
            if row is None:
                continue
            if not snapshot:
                snapshot = _evidence_hash(*row[:5])
            scope_name = role_scope({"contest_id": row[5], "role_id": row[6],
                                     "ambiguity_reason": row[8]}, reconciled)[0]
            scope = sorted(
                pid for pid, role_id, reason in conn.execute(
                    "SELECT id, role_id, ambiguity_reason FROM propostas_campo "
                    "WHERE contest_id=? AND field_name=?", (row[5], row[7]))
                if role_scope({"contest_id": row[5], "role_id": role_id,
                               "ambiguity_reason": reason}, reconciled)[0] == scope_name)
            conn.execute(
                "INSERT INTO lote_revisao_itens (lote_id,position,proposal_id,state,"
                "snapshot_sha256,scope_snapshot) VALUES (?,?,?,'pendente',?,?)",
                (lote_id, position, item["proposal_id"], snapshot,
                 json.dumps(scope, ensure_ascii=False)))
    return _batch(db_path, lote_id)


def batch_status(db_path, lote_id: str) -> dict:
    return _batch(db_path, lote_id)


def batch_step(db_path, lote_id: str, action: str, *, now=None) -> dict:
    """Navega no lote: ``proximo``, ``anterior``, ``pausar``, ``retomar``, ``concluir``."""
    if action not in ("proximo", "anterior", "pausar", "retomar", "concluir"):
        raise ValueError("ação de lote inválida")
    at = now or _now()
    lote = _batch(db_path, lote_id)
    if lote["state"] == "concluido" and action not in ("retomar",):
        raise ValueError("lote concluído")
    cursor = lote["cursor"] or 1
    if action == "proximo":
        cursor = min(len(lote["itens"]), cursor + 1)
    elif action == "anterior":
        cursor = max(1, cursor - 1)
    state = {"pausar": "pausado", "retomar": "aberto", "concluir": "concluido"}.get(
        action, "aberto")
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute("UPDATE lotes_revisao SET cursor=?, state=? WHERE id=?",
                     (cursor, state, lote_id))
    return _batch(db_path, lote_id)


# --- exportação e importação de decisões ------------------------------------

def export_batch(db_path, lote_id: str, *, now=None) -> dict:
    """Exporta o lote com identificadores estáveis e impressão de evidência."""
    lote = _batch(db_path, lote_id)
    export = {"version": REVIEW_VERSION, "lote_id": lote_id,
              "exported_at": now or _now(), "filters": lote["filters"],
              "itens": []}
    with closing(connect_documents(db_path)) as conn:
        for item in lote["itens"]:
            row = conn.execute("""
                SELECT p.value_json,p.field_name,p.contest_id,p.role_id,e.quote,e.version_id,
                       e.start_offset,e.end_offset,
                       (SELECT r.decision FROM revisoes_campo r WHERE r.proposal_id=p.id
                        ORDER BY r.reviewed_at DESC,r.rowid DESC LIMIT 1)
                FROM propostas_campo p JOIN evidencias e ON e.id=p.evidence_id
                WHERE p.id=?""", (item["proposal_id"],)).fetchone()
            if not row:
                continue
            export["itens"].append({
                "proposal_id": item["proposal_id"],
                "field_name": row[1],
                "contest_id": row[2],
                "role_id": row[3],
                "value": _value_of(row[0]),
                "evidence_sha256": _evidence_hash(row[0], row[4], row[5], row[6], row[7]),
                "state": _state(row[8], False) if row[8] else "pendente",
                "decision": None,
                "reason": None,
            })
    export["limitacao"] = ("Exportação é cópia de trabalho. Decisão importada só é aceita se "
                           "valor e evidência não mudaram; nada é aprovado por estar no arquivo.")
    return export


def import_decisions(db_path, payload: dict, *, reviewer: str, reason: str,
                     origin: str = "importacao", dry_run: bool = True, now=None) -> dict:
    """Importa decisões de um lote exportado, rejeitando evidência desatualizada.

    Duas fases: valida **todos** os itens e só então grava, numa única transação. Um item
    repetido no arquivo é rejeitado, e erro inesperado desfaz a importação inteira.
    """
    reviewer = _require_text(reviewer, "revisor obrigatório")
    reason = _require_text(reason, "justificativa obrigatória")
    if origin not in ORIGINS:
        raise ValueError("origem da decisão inválida")
    if not isinstance(payload, dict) or payload.get("version") != REVIEW_VERSION:
        raise ValueError("arquivo de revisão inválido")
    items = payload.get("itens")
    if not isinstance(items, list):
        raise ValueError("arquivo de revisão inválido")
    at = now or _now()
    report = {"version": REVIEW_VERSION, "dry_run": bool(dry_run), "aplicados": 0,
              "rejeitados": [], "ignorados": 0}
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        current = {row["proposal_id"]: row for row in _rows(conn)}

    planned, seen = [], set()
    for item in items:
        if not isinstance(item, dict):
            report["rejeitados"].append({"proposal_id": None, "motivo": "item inválido"})
            continue
        proposal_id = item.get("proposal_id")
        decision = item.get("decision")
        if not decision:
            report["ignorados"] += 1
            continue
        if decision not in DECISIONS or decision == "corrigido":
            report["rejeitados"].append({"proposal_id": proposal_id,
                                         "motivo": "decisão não importável"})
            continue
        if not isinstance(proposal_id, str) or proposal_id in seen:
            report["rejeitados"].append({"proposal_id": proposal_id,
                                         "motivo": "proposta repetida no arquivo"})
            continue
        seen.add(proposal_id)
        row = current.get(proposal_id)
        if row is None:
            report["rejeitados"].append({"proposal_id": proposal_id,
                                         "motivo": "proposta inexistente"})
            continue
        fingerprint = _evidence_hash(row["value_json"], row["quote"], row["version_id"],
                                     row["start_offset"], row["end_offset"])
        if item.get("evidence_sha256") != fingerprint:
            report["rejeitados"].append({"proposal_id": proposal_id,
                                         "motivo": "evidência desatualizada"})
            continue
        if _state(row["last_decision"], row["selected"]) not in OPEN_STATES:
            report["rejeitados"].append({"proposal_id": proposal_id, "motivo": "já decidido"})
            continue
        item_reason = item.get("reason") or reason
        try:
            item_reason = _require_text(item_reason, "justificativa obrigatória")
        except ValueError:
            report["rejeitados"].append({"proposal_id": proposal_id,
                                         "motivo": "justificativa inválida"})
            continue
        planned.append((proposal_id, decision, item_reason))

    if dry_run:
        report["aplicados"] = len(planned)
        return report
    try:
        with closing(connect_documents(db_path)) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            for proposal_id, decision, item_reason in planned:
                _decide_on(conn, proposal_id, decision, reviewer=reviewer,
                           reason=item_reason, origin=origin, value=None,
                           expected_evidence_sha256=None, lote_id=None, at=at)
    except Exception as error:  # rollback automático: nada fica aplicado pela metade
        report["erro"] = type(error).__name__
        report["aplicados"] = 0
        return report
    report["aplicados"] = len(planned)
    return report
