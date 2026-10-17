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
                             ORDER BY v2.selected_at DESC, v2.rowid DESC LIMIT 1)) AS selected
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


def _conflicts(rows) -> dict[tuple, list[dict]]:
    """Conflito só entre propostas abertas: valor rejeitado/superado não é disputa."""
    groups = {}
    for row in rows:
        if not _is_open(row):
            continue
        key = (row["contest_id"], row["role_id"], row["field_name"])
        groups.setdefault(key, []).append(row)
    conflicts = {}
    for key, items in groups.items():
        values = {item["value_json"] for item in items}
        if len(values) > 1:
            conflicts[key] = items
    return conflicts


def _priority(row, *, editais, deadlines, conflicts, today) -> tuple[int, list[dict]]:
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
    group = conflicts.get((row["contest_id"], row["role_id"], row["field_name"]))
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


def _matches(row, *, state, conflict, filters, conflicts) -> bool:
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
    has_conflict = (row["contest_id"], row["role_id"], row["field_name"]) in conflicts
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


def review_queue(db_path, *, contest_id=None, role_id=None, field_name=None, document_id=None,
                 source=None, state="pendente", conflict=None, min_priority=None,
                 since=None, until=None, reviewed_since=None, reviewed_until=None,
                 limit=25, offset=0, now=None) -> dict:
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
               "reviewed_since": reviewed_since, "reviewed_until": reviewed_until}

    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = _rows(conn)
        editais = _official_editais(conn)
    conflicts = _conflicts(rows)
    deadlines = _deadlines(rows)

    selected = []
    for row in rows:
        if not _matches(row, state=state, conflict=conflict, filters=filters,
                        conflicts=conflicts):
            continue
        score, factors = _priority(row, editais=editais, deadlines=deadlines,
                                   conflicts=conflicts, today=today)
        if min_priority is not None and score < int(min_priority):
            continue
        selected.append((score, factors, row))

    selected.sort(key=lambda item: (-item[0], item[2]["field_name"], item[2]["proposal_id"]))
    total = len(selected)
    page = selected[offset:offset + limit]

    items = []
    for score, factors, row in page:
        group = conflicts.get((row["contest_id"], row["role_id"], row["field_name"]), [])
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
                "quote": row["quote"],
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
                "limitation": None if row["quote"] else "sem trecho literal registrado",
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
                                       if (row["contest_id"], row["role_id"],
                                           row["field_name"]) in conflicts)},
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
            "quote": target["quote"],
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
            "limitation": None if target["quote"] else "sem trecho literal registrado",
        },
        "other_proposals": [
            {"proposal_id": row["proposal_id"], "value": _value_of(row["value_json"]),
             "state": _state(row["last_decision"], row["selected"]),
             "document_title": row["document_title"], "published_at": row["published_at"],
             "quote": row["quote"], "page_number": row["page_number"],
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
               e.quote,e.version_id,e.start_offset,e.end_offset
        FROM propostas_campo p JOIN evidencias e ON e.id=p.evidence_id
        JOIN versoes_documento v ON v.id=e.version_id
        JOIN documentos d ON d.id=v.document_id
        WHERE p.id=? AND d.contest_id=p.contest_id""", (proposal_id,)).fetchone()
    if not row:
        raise ValueError("proposta sem evidência válida")
    contest_id, role_id, field_name, value_json, evidence_id, quote, version_id, start, end = row
    fingerprint = _evidence_hash(value_json, quote, version_id, start, end)
    if expected_evidence_sha256 and expected_evidence_sha256 != fingerprint:
        raise ValueError("evidência mudou desde a exportação")
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
            " ORDER BY r.reviewed_at DESC,r.rowid DESC LIMIT 1) "
            "FROM lote_revisao_itens i JOIN propostas_campo p ON p.id=i.proposal_id "
            "WHERE i.lote_id=? ORDER BY i.position", (lote_id,)).fetchall()
    lote = {"lote_id": row[0], "created_at": row[1], "created_by": row[2], "origin": row[3],
            "filters": json.loads(row[4]), "size": row[5], "state": row[6], "cursor": row[7],
            "note": row[8]}
    lote["itens"] = [
        {"position": item[0], "proposal_id": item[1], "batch_state": item[2],
         "decided_at": item[3], "field_name": item[4], "value": _value_of(item[5]),
         "contest_id": item[6], "role_id": item[7],
         "state": _state(item[8], False) if item[8] else "pendente"}
        for item in items]
    lote["progresso"] = {
        "total": len(lote["itens"]),
        "decididos": sum(1 for item in lote["itens"]
                         if item["state"] in DECIDED_STATES or item["batch_state"] == "decidido"),
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
               "reviewed_until"}
    unknown = set(filters) - allowed
    if unknown:
        raise ValueError(f"filtro de lote inválido: {', '.join(sorted(unknown))}")
    filters.setdefault("state", "pendente")
    queue = review_queue(db_path, limit=size, offset=0, now=now, **filters)
    if not queue["items"]:
        raise ValueError("nenhuma proposta pendente para os filtros")
    at = now or _now()
    lote_id = str(uuid4())
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO lotes_revisao (id,created_at,created_by,origin,filters_json,size,state,"
            "cursor,note) VALUES (?,?,?,?,?,?,?,?,?)",
            (lote_id, at, created_by, origin, json.dumps(filters, ensure_ascii=False, sort_keys=True),
             size, "aberto", 1, note))
        for position, item in enumerate(queue["items"], start=1):
            conn.execute(
                "INSERT INTO lote_revisao_itens (lote_id,position,proposal_id,state) "
                "VALUES (?,?,?,'pendente')", (lote_id, position, item["proposal_id"]))
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
