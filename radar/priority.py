"""Priorização de concursos: junta localização, compatibilidade e vagas ao ranking.

Lê o histórico documental (propostas, revisões, valores vigentes) e produz uma lista
ordenada de oportunidades com explicação. É a camada que conecta os módulos puros
(`location`, `geography`, `ranking`) aos dados reais, sem duplicar mecanismos já existentes
(estados de proposta, valores vigentes, evidências).

Precedência de leitura de um campo (a mesma regra documentada em `ops.py`):
**valor vigente** (`valores_atuais`) > proposta **validada** mais recente > proposta **mais
recente**. Nunca a mais antiga: uma retificação (documento mais novo) prevalece sobre o
edital. Quando há divergência **não resolvida por revisão**, o estado é tratado como ambíguo
(não se escolhe em silêncio) — nunca se apresenta um valor incerto como confirmado.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from radar import geography, location, ranking
from radar.document_store import connect_documents, is_readable_schema
from radar.edital_requirements import SI_STATES

# Campos decisivos para a priorização (contam para cobertura/confiança).
_DECISIVE = ("si_compatibility", "indigenous_vacancies", "exam_location", "work_location")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _parse_date(value):
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return datetime.fromisoformat(value[:10]).date()
    except ValueError:
        return None


def _urgency(deadlines, today, horizon_days):
    """Urgência operacional (dimensão independente da qualidade estrutural)."""
    best = None
    for kind, value in deadlines.items():
        day = _parse_date(value)
        if day is None:
            continue
        state = "expirado" if day < today else ("proximo" if (day - today).days <= horizon_days else None)
        if state is None:
            continue
        if best is None or state == "expirado":
            best = {"kind": kind, "date": day.isoformat(), "state": state,
                    "days": (day - today).days}
    return best


def _proposal_rows(conn):
    """Propostas por concurso/campo com estado (revisão > ambiguidade > extraído)."""
    rows = conn.execute(
        """SELECT p.id, p.contest_id, p.field_name, p.value_json, p.ambiguity_reason,
        (SELECT r.decision FROM revisoes_campo r WHERE r.proposal_id=p.id
         ORDER BY r.reviewed_at DESC, r.rowid DESC LIMIT 1) AS decision,
        e.version_id, e.page_number, e.quote, v.document_id
        FROM propostas_campo p
        LEFT JOIN evidencias e ON e.id=p.evidence_id
        LEFT JOIN versoes_documento v ON v.id=e.version_id
        ORDER BY p.extracted_at, p.id""").fetchall()
    out = []
    for (pid, contest_id, field_name, value_json, ambiguity, decision,
         version_id, page, quote, document_id) in rows:
        try:
            value = json.loads(value_json)
        except (TypeError, ValueError):
            value = None
        state = decision or ("ambiguo" if ambiguity else "extraido")
        out.append({"id": pid, "contest_id": contest_id, "field_name": field_name, "value": value,
                    "state": state, "ambiguity_reason": ambiguity,
                    "evidence": {"version_id": version_id, "page_number": page,
                                 "quote": quote, "document_id": document_id}})
    return out


def proposal_rows(conn):
    """API pública das propostas por concurso/campo (mesma semântica de ``_proposal_rows``).

    Reutilizada pela auditoria de cobertura para não duplicar o vocabulário de estados:
    ``revisoes_campo.decision`` > ``ambiguo`` (quando há ``ambiguity_reason``) > ``extraido``.
    """
    return _proposal_rows(conn)


def _current_values(conn):
    """Seleções vigentes (valores_atuais) por concurso/campo -> proposal_id."""
    out = {}
    for contest_id, field_name, proposal_id in conn.execute(
            "SELECT contest_id, field_name, proposal_id FROM valores_atuais ORDER BY selected_at, id"):
        out[(contest_id, field_name)] = proposal_id
    return out


def _has_analysis(conn):
    """Ids de concursos com pelo menos uma versão documental analisada."""
    return {row[0] for row in conn.execute(
        "SELECT DISTINCT d.contest_id FROM versoes_documento v JOIN documentos d ON d.id=v.document_id "
        "WHERE v.extraction_state IN ('parcial','concluida')").fetchall()}


def _choose(items, current_id):
    """Proposta escolhida: vigente > validada mais recente > mais recente (cronologia)."""
    if not items:
        return None
    if current_id:
        chosen = next((p for p in items if p["id"] == current_id), None)
        if chosen:
            return chosen
    validated = [p for p in items if p["state"] == "validado"]
    if validated:
        return validated[-1]
    return items[-1]


def _divergent(items):
    return len({json.dumps(p["value"], sort_keys=True, ensure_ascii=False) for p in items}) > 1


def _field_value(items, current_id):
    """``(valor, estado)`` do campo: ambíguo não conta como confirmado (valor ``None``)."""
    chosen = _choose(items, current_id)
    if chosen is None:
        return None, None
    if chosen["state"] == "ambiguo":
        return None, "ambiguo"
    return chosen["value"], chosen["state"]


def prioritize(db_path, preferences, *, now=None, limit=200, provider=None) -> dict:
    """Lista de oportunidades ordenada por prioridade explicável (determinística)."""
    now_dt = datetime.fromisoformat(now) if now else datetime.now(timezone.utc)
    today = now_dt.date()
    horizon_days = 7
    practical = preferences.get("practical_distance_km", 300)
    reference = {"municipio": preferences.get("reference_municipio"),
                 "uf": preferences.get("reference_uf")}
    interest = preferences.get("interest_states") or []
    if provider is None and preferences.get("coordinates_path"):
        provider = geography.load_provider(preferences["coordinates_path"])

    conn = connect_documents(db_path)
    try:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        contests = [row[0] for row in conn.execute(
            "SELECT id FROM concursos_identidade ORDER BY created_at, id").fetchall()]
        proposals = _proposal_rows(conn)
        current = _current_values(conn)
        analyzed_ids = _has_analysis(conn)
    finally:
        conn.close()

    by_contest = {}
    for item in proposals:
        by_contest.setdefault(item["contest_id"], []).append(item)

    items = []
    for contest_id in contests:
        props = by_contest.get(contest_id, [])
        analyzed = contest_id in analyzed_ids
        loc = location.resolve_location(props, analyzed=analyzed)

        si_items = [p for p in props if p["field_name"] == "si_compatibility"]
        si_value = None
        si_state = "nao_extraido"
        si_conflict = False
        if si_items:
            chosen = _choose(si_items, current.get((contest_id, "si_compatibility")))
            si_value = chosen["value"]
            si_conflict = _divergent(si_items) and chosen["state"] != "validado"
            if si_conflict:
                si_state = "ambiguo"  # divergência não resolvida por revisão
            elif si_value in SI_STATES:
                si_state = si_value
            elif chosen["state"] == "ambiguo":
                si_state = "ambiguo"

        indigenous_immediate, imm_state = _field_value(
            [p for p in props if p["field_name"] == "indigenous_vacancies"],
            current.get((contest_id, "indigenous_vacancies")))
        indigenous_reserve, _ = _field_value(
            [p for p in props if p["field_name"] == "indigenous_reserve_vacancies"],
            current.get((contest_id, "indigenous_reserve_vacancies")))

        deadlines = {}
        for field in ("exemption_end", "registration_end"):
            value, _ = _field_value([p for p in props if p["field_name"] == field],
                                    current.get((contest_id, field)))
            if isinstance(value, str):
                deadlines[field] = value
        urgency = _urgency(deadlines, today, horizon_days)

        # Distância da prova até a referência do usuário (linha reta, honesta).
        prova = loc["prova"]
        distance = geography.distance_from_reference(
            prova["municipios"][0] if prova["municipios"] else None, prova["uf"],
            reference=reference, provider=provider)

        decisive = [p for p in props if p["field_name"] in _DECISIVE]
        chosen_decisive = [_choose([p for p in props if p["field_name"] == f],
                                   current.get((contest_id, f)))
                           for f in _DECISIVE]
        chosen_decisive = [c for c in chosen_decisive if c is not None]
        confirmed = [c for c in chosen_decisive if c["state"] == "validado"]
        if chosen_decisive and len(confirmed) == len(chosen_decisive):
            confidence = "alta"
        elif chosen_decisive:
            confidence = "media"
        else:
            confidence = None

        result = ranking.score_contest(
            indigenous_immediate=indigenous_immediate, indigenous_reserve=indigenous_reserve,
            si_compatibility=si_state, distance_km=distance["distance_km"],
            practical_distance_km=practical, exam_uf=prova["uf"], interest_states=interest,
            evidence_confidence=confidence, confirmed_fields=len(confirmed),
            total_decisive=len(chosen_decisive))
        items.append({
            "contest_id": contest_id,
            "score": result["score"], "possible": result["possible"],
            "max_score": result["max_score"], "coverage": result["coverage"],
            "label": result["label"], "label_text": result["label_text"],
            "exceptional": result["exceptional"], "floor_applied": result["floor_applied"],
            "factors": result["factors"],
            "explain": result["explain"],
            "si_compatibility": {"state": si_state, "value": si_value, "conflict": si_conflict},
            "indigenous_immediate": indigenous_immediate,
            "indigenous_immediate_state": imm_state,
            "indigenous_reserve": indigenous_reserve,
            "location": {"prova": loc["prova"], "lotacao": loc["lotacao"]},
            "distance": distance,
            "urgency": urgency,
        })

    items.sort(key=lambda i: (-i["score"], _urgency_rank(i["urgency"]), i["contest_id"]))
    return {"version": ranking.RANKING_VERSION, "generated_at": now_dt.isoformat(),
            "preferences": preferences, "count": len(items), "items": items[:max(0, int(limit))]}


def _urgency_rank(urgency):
    """Desempate: expirado primeiro, depois proximidade crescente, depois sem prazo."""
    if not urgency:
        return (2, 0)
    if urgency["state"] == "expirado":
        return (0, urgency["days"])
    return (1, urgency["days"])
