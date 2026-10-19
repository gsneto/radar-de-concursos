"""Visão operacional dos quatro campos decisivos (Fase 33).

Lê o histórico documental e responde, por concurso, o que existe para:

A. vagas imediatas reservadas a indígenas;
B. aceitação formal do bacharelado em Sistemas de Informação;
C. prazos;
D. local de prova (distinto de lotação).

Regras de honestidade:

- total agregado **nunca** vira vaga indígena (estado ``agregado_sem_modalidade``);
- modalidade ausente **não** é zero: ``nao_mencionado`` ≠ ``explicito_sem_vaga_imediata``;
- prazo de documento de resultado não compete com o edital; retificação posterior é
  registrada como substituição, não como segundo valor válido;
- ``a_divulgar`` é declaração, não ausência; município de lotação nunca vira local de prova;
- nada é confirmado: todo item é candidato até decisão humana na fila de revisão.
"""

from __future__ import annotations

import json
import re
from contextlib import closing
from datetime import date

from radar import indigenous_scope, location, version_conflicts
from radar.document_store import connect_documents, is_readable_schema
from radar.edital_requirements import SI_STATES

DECISIVE_VERSION = "decisive_fields_v1"

INDIGENOUS_FIELDS = ("indigenous_vacancies", "indigenous_reserve_vacancies",
                     "indigenous_reserve_notation")
SI_FIELD = "si_compatibility"
DEADLINE_GROUPS = {
    "inscricao_inicio": ("registration_start",),
    "inscricao_fim": ("registration_end",),
    "isencao_inicio": ("exemption_start",),
    "isencao_fim": ("exemption_end",),
    "data_prova": ("exam_date",),
}
AUTHORITATIVE_DOC_TYPES = version_conflicts.AUTHORITATIVE_DOC_TYPES
EDITAL_TYPES = ("edital_abertura", "edital_retificado")

# Estados da visão de vagas indígenas (distintos de propósito).
INDIGENOUS_STATES = (
    "explicito_imediato",
    "apenas_reserva",
    "explicito_sem_vaga_imediata",
    "mencao_sem_quantidade",
    "reserva_combinada_com_outros_grupos",
    "mencao_fora_do_escopo_de_reserva",
    "agregado_sem_modalidade",
    "nao_mencionado",
    "nao_pesquisado",
)
INDIGENOUS_LABELS = {
    "explicito_imediato": "Vaga imediata indígena explícita",
    "apenas_reserva": "Apenas reserva indígena (sem vaga imediata)",
    "explicito_sem_vaga_imediata": "Modalidade indígena explícita, sem vaga imediata",
    "mencao_sem_quantidade": "Regra de reserva indígena sem quantidade extraída",
    "reserva_combinada_com_outros_grupos": ("Reserva indígena apenas em coluna combinada "
                                            "com outros grupos"),
    "mencao_fora_do_escopo_de_reserva": ("Palavra 'indígena' fora de regra de reserva "
                                         "(identificação, vestuário, conteúdo, procedimento)"),
    "agregado_sem_modalidade": "Apenas total agregado publicado (não distribuir)",
    "nao_mencionado": "Edital extraído sem menção a vaga indígena",
    "nao_pesquisado": "Sem edital extraído",
}

SI_VIEW_STATES = {
    "aceito_expressamente": "explicito",
    "nivel_minimo_sem_area": "nivel_minimo",
    "abrangido_por_categoria": "categoria_inclui_curso",
    "ambiguo": "area_correlata_interpretacao",
    "incompativel_com_requisito_explicito": "outras_formacoes",
    "nao_informado": "nao_encontrado",
    "nao_extraido": "extracao_incompleta",
}
SI_VIEW_LABELS = {
    "explicito": "Sistemas de Informação expressamente aceito",
    "nivel_minimo": ("Escolaridade mínima publicada, sem exigência de curso específico"),
    "categoria_inclui_curso": "Categoria de formação inclui o curso (com evidência)",
    "area_correlata_interpretacao": "Área correlata: exige interpretação humana",
    "outras_formacoes": "Enumera outras formações (SI não citado)",
    "nao_encontrado": "Requisito não encontrado no texto extraído",
    "extracao_incompleta": "Extração incompleta (edital não processado)",
}

_MENTION = re.compile(r"\bind[íi]gena?s?\b|\bpessoas\s+ind[íi]genas\b|\bPI\b", re.I)
_HEADER_HINT = re.compile(
    r"(?:\bPI\b|ind[íi]gena)[^.]{0,120}", re.I)


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _rows(db_path):
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = conn.execute("""
            SELECT p.id, p.contest_id, p.role_id, r.name, p.field_name, p.value_json,
                   p.extraction_method, p.ambiguity_reason,
                   d.id, d.title, d.tipo_documental, d.published_at, d.discovered_at,
                   v.id, e.page_number, e.quote,
                   (SELECT rv.decision FROM revisoes_campo rv WHERE rv.proposal_id=p.id
                    ORDER BY rv.reviewed_at DESC, rv.rowid DESC LIMIT 1)
            FROM propostas_campo p
            LEFT JOIN cargos_identidade r ON r.id=p.role_id
            JOIN evidencias e ON e.id=p.evidence_id
            JOIN versoes_documento v ON v.id=e.version_id
            JOIN documentos d ON d.id=v.document_id
            ORDER BY p.contest_id, p.field_name, d.published_at, d.discovered_at
            """).fetchall()
        contests = [row[0] for row in conn.execute(
            "SELECT id FROM concursos_identidade WHERE estado_identidade='certame' "
            "ORDER BY created_at, id")]
        # Texto por página para detectar menção sem quantidade e cabeçalho de modalidade.
        pages = {}
        for version_id, page, text in conn.execute(
                "SELECT version_id, page_number, text FROM blocos_documento "
                "WHERE page_number IS NOT NULL"):
            pages[(version_id, page)] = text
        analyzed = {row[0] for row in conn.execute(
            "SELECT DISTINCT d.contest_id FROM documentos d "
            "JOIN versoes_documento v ON v.document_id=d.id "
            "JOIN blocos_documento b ON b.version_id=v.id "
            "WHERE d.tipo_documental IN ('edital_abertura','edital_retificado')")}
        # Páginas de documentos autoritativos por concurso: permitem detectar menção a
        # indígena mesmo quando nenhuma proposta foi gerada.
        contest_pages = {}
        for contest_id, version_id, page, text in conn.execute(
                "SELECT d.contest_id, b.version_id, b.page_number, b.text "
                "FROM blocos_documento b "
                "JOIN versoes_documento v ON v.id=b.version_id "
                "JOIN documentos d ON d.id=v.document_id "
                "WHERE d.tipo_documental IN ('edital_abertura','edital_retificado',"
                "'retificacao','cronograma') AND b.page_number IS NOT NULL"):
            contest_pages.setdefault(contest_id, []).append((version_id, page, text))
    items = []
    for row in rows:
        try:
            value = json.loads(row[5])
        except (TypeError, ValueError):
            value = row[5]
        items.append({
            "proposal_id": row[0], "contest_id": row[1], "role_id": row[2],
            "role_name": row[3], "field_name": row[4], "value": value,
            "method": row[6], "ambiguity_reason": row[7],
            "document_id": row[8], "document_title": row[9], "document_type": row[10],
            "published_at": row[11], "discovered_at": row[12], "version_id": row[13],
            "page_number": row[14], "quote": row[15], "decision": row[16],
        })
    by_contest = {}
    for item in items:
        by_contest.setdefault(item["contest_id"], []).append(item)
    return {"contests": contests, "proposals": items, "by_contest": by_contest,
            "pages": pages, "analyzed": analyzed, "contest_pages": contest_pages}


def _authoritative(item) -> bool:
    return (item["document_type"] or "") in AUTHORITATIVE_DOC_TYPES


def _mention(data, item) -> dict | None:
    """Menção a indígena na mesma página do documento (contexto de modalidade)."""
    text = data["pages"].get((item["version_id"], item["page_number"])) or ""
    match = _HEADER_HINT.search(text)
    if not match:
        return None
    snippet = " ".join(match.group(0).split())[:200]
    return {"quote": snippet, "page_number": item["page_number"]}


def _indigenous(data, contest_id, conflict_fields):
    proposals = [item for item in data["by_contest"].get(contest_id, [])
                 if item["field_name"] in INDIGENOUS_FIELDS
                 and item["decision"] != "rejeitado"]
    immediate = [item for item in proposals if item["field_name"] == "indigenous_vacancies"]
    reserve = [item for item in proposals
               if item["field_name"] == "indigenous_reserve_vacancies"]
    notation = [item for item in proposals
                if item["field_name"] == "indigenous_reserve_notation"]
    aggregate = [item for item in data["by_contest"].get(contest_id, [])
                 if item["field_name"] == "vagas_total_publicado"]
    analyzed = contest_id in data["analyzed"]
    # A melhor janela (não a primeira página) define contexto e evidência: uma página de
    # conteúdo antes da regra de reserva não pode esconder a reserva.
    mentioned = None
    best_rank = -1
    for version_id, page, text in data["contest_pages"].get(contest_id, []):
        low = (text or "").lower()
        if "indígen" not in low and "indigen" not in low:
            continue
        context, position, strength = indigenous_scope.classify(text)
        if strength <= best_rank:
            continue
        best_rank = strength
        mentioned = {"quote": indigenous_scope.snippet(text, position, radius=60),
                     "page_number": page, "contexto": context,
                     "contexto_label":
                         indigenous_scope.MENTION_CONTEXT_LABELS[context]}
    if not analyzed and not proposals:
        state = "nao_pesquisado"
    elif any(field in INDIGENOUS_FIELDS for field in conflict_fields):
        state = "mencao_sem_quantidade"
    elif any(_num(item["value"]) > 0 for item in immediate):
        state = "explicito_imediato"
    elif any(_num(item["value"]) > 0 for item in reserve):
        state = "apenas_reserva"
    elif notation:
        # Reserva publicada por notacao (ex.: "CR*"), sem quantidade numerica.
        state = "apenas_reserva"
    elif immediate:
        state = "explicito_sem_vaga_imediata"
    elif mentioned:
        context = mentioned["contexto"]
        if context == "regra_de_reserva":
            state = "mencao_sem_quantidade"
        elif context == "regra_de_reserva_combinada":
            state = "reserva_combinada_com_outros_grupos"
        else:
            state = "mencao_fora_do_escopo_de_reserva"
    elif aggregate:
        state = "agregado_sem_modalidade"
    else:
        state = "nao_mencionado"
    return {
        "estado": state, "estado_label": INDIGENOUS_LABELS[state],
        "imediata": [_brief(item) for item in immediate],
        "reserva": [_brief(item) for item in reserve]
                    + [_brief(item) for item in notation],
        "total_agregado": [_brief(item) for item in aggregate],
        "mencao": mentioned,
        "derivado_de_agregado": False,
        "nota": ("Nenhuma vaga indígena é derivada de total agregado. Ausência de "
                 "modalidade não é zero; 'nao_mencionado' descreve o texto extraído."),
    }


def _num(value):
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return 0


def _brief(item):
    return {"proposal_id": item["proposal_id"], "value": item["value"],
            "role_id": item["role_id"], "role_name": item["role_name"],
            "page_number": item["page_number"], "quote": item["quote"],
            "document_title": item["document_title"],
            "document_type": item["document_type"],
            "decision": item["decision"]}


_LABEL = re.compile(r"cargo do documento não reconciliado:\s*(.+?)\s+—")


def _cargo_key(item):
    """Escopo do requisito: cargo reconciliado ou rótulo do próprio documento.

    Sem identidade canônica, o rótulo do edital é o único escopo honesto — agrupar todos
    os cargos do documento juntos faria um cargo de TI "contaminar" os demais.
    """
    if item["role_id"]:
        return ("role", item["role_id"]), item["role_name"]
    reason = item["ambiguity_reason"] or ""
    match = _LABEL.match(reason)
    if match:
        return ("label", match.group(1).strip()), match.group(1).strip()
    # Rótulo sem a anotação do extrator ("— motivo") continua sendo um rótulo de cargo.
    prefix = "cargo do documento não reconciliado:"
    if reason.startswith(prefix):
        label = reason[len(prefix):].strip()
        if label:
            return ("label", label), label
    return ("sem_cargo", None), None


def _si(data, contest_id):
    proposals = [item for item in data["by_contest"].get(contest_id, [])
                 if item["field_name"] == SI_FIELD
                 and item["decision"] != "rejeitado"]
    analyzed = contest_id in data["analyzed"]
    by_role = {}
    for item in proposals:
        key, label = _cargo_key(item)
        entry = by_role.setdefault(key, {"role_id": item["role_id"],
                                         "role_name": item["role_name"] or label,
                                         "estados": [], "itens": []})
        entry["estados"].append(item["value"])
        entry["itens"].append(_brief(item))
    roles = []
    for entry in by_role.values():
        raw = [state for state in entry["estados"] if state in SI_STATES]
        distinct = sorted(set(raw))
        if len(distinct) > 1:
            chosen = "ambiguo"
            view = "area_correlata_interpretacao"
        else:
            chosen = distinct[0] if distinct else "nao_informado"
            view = SI_VIEW_STATES.get(chosen, "area_correlata_interpretacao")
        roles.append({"role_id": entry["role_id"], "role_name": entry["role_name"],
                      "estado": view, "estado_label": SI_VIEW_LABELS[view],
                      "estado_extraido": chosen, "estados_encontrados": distinct,
                      "itens": entry["itens"]})
    if not roles:
        state = "nao_encontrado" if analyzed else "extracao_incompleta"
        return {"estado": state, "estado_label": SI_VIEW_LABELS[state], "cargos": [],
                "nota": ("Ausência de requisito extraído não prova incompatibilidade; "
                         "só a revisão do texto do edital decide.")}
    ranking = ("explicito", "categoria_inclui_curso", "area_correlata_interpretacao",
               "outras_formacoes")
    best = next((state for state in ranking
                 if any(role["estado"] == state for role in roles)), roles[0]["estado"])
    return {"estado": best, "estado_label": SI_VIEW_LABELS[best], "cargos": roles,
            "nota": ("Estado por cargo; 'outras_formacoes' não é incompatibilidade "
                     "definitiva, apenas ausência de citação de SI no requisito.")}


def _deadlines(data, contest_id):
    out = {}
    for key, fields in DEADLINE_GROUPS.items():
        items = [item for item in data["by_contest"].get(contest_id, [])
                 if item["field_name"] in fields
                 and item["decision"] != "rejeitado" and _authoritative(item)]
        if not items:
            state = "nao_localizado" if contest_id in data["analyzed"] else "nao_pesquisado"
            out[key] = {"estado": state, "vigente": None, "anteriores": []}
            continue
        dated = []
        for item in items:
            day = _day(item["published_at"] or item["discovered_at"])
            dated.append((item, day))
        if all(day is None for _, day in dated):
            out[key] = {"estado": "sem_data_documental", "vigente": None,
                        "anteriores": [_brief(item) for item in items]}
            continue
        latest = max(day for _, day in dated if day is not None)
        newest = [item for item, day in dated if day == latest]
        values = {json.dumps(item["value"], ensure_ascii=False) for item in newest}
        if len(values) > 1:
            # Valor repetido em mais páginas é candidato majoritário, mas continua ambíguo:
            # contagem de ocorrências não substitui a decisão humana.
            counts = {}
            for item in newest:
                counts[json.dumps(item["value"], ensure_ascii=False)] = counts.get(
                    json.dumps(item["value"], ensure_ascii=False), 0) + 1
            top = max(counts.values())
            majority_values = [value for value, count in counts.items() if count == top]
            majority = next((item for item in newest
                             if json.dumps(item["value"], ensure_ascii=False)
                             == majority_values[0]), None) if len(majority_values) == 1 else None
            out[key] = {"estado": "ambiguo", "vigente": None,
                        "candidatos": [_brief(item) for item in newest],
                        "candidato_majoritario": (
                            _brief(majority) if majority is not None and top > 1 else None),
                        "anteriores": [_brief(item) for item, day in dated if day != latest],
                        "motivo": "o documento mais recente traz mais de um valor"}
        else:
            out[key] = {"estado": "candidato", "vigente": _brief(newest[0]),
                        "anteriores": [_brief(item) for item, day in dated if day != latest]}
    return out


def _day(value):
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _location_items(data, contest_id):
    """Propostas de local normalizadas para o parser (UF recuperada do trecho literal)."""
    items = []
    for item in data["by_contest"].get(contest_id, []):
        if item["field_name"] not in ("exam_location", "exam_municipio", "exam_uf",
                                      "work_location", "work_municipio", "work_uf"):
            continue
        if item["decision"] == "rejeitado":
            continue
        value = item["value"]
        parsed = location.parse_location(value) if isinstance(value, str) else None
        if isinstance(value, str) and parsed and not parsed.get("uf"):
            # "Porto Alegre –" + trecho "cidade de Porto Alegre – RS": a UF está no trecho.
            tail = re.search(r"[/\-\u2013\u2014]\s*([A-Z]{2})\b", item["quote"] or "")
            if tail and location.valid_uf(tail.group(1)):
                value = f"{parsed['municipio']}/{tail.group(1)}"
        items.append({"field_name": item["field_name"], "value": value,
                      "state": ("validado" if item["decision"] == "validado"
                                else "ambiguo" if item["decision"] == "ambiguo"
                                else "extraido"),
                      "evidence": {"quote": item["quote"],
                                   "page_number": item["page_number"]}})
    return _dedupe_locations(items)


def _dedupe_locations(items):
    """"Salvador" e "Salvador/BA" são o mesmo local: a UF qualifica, não duplica."""
    grouped = {"exam_location": [], "work_location": []}
    other = []
    for item in items:
        if item["field_name"] in grouped:
            grouped[item["field_name"]].append(item)
        else:
            other.append(item)
    out = []
    for field, values in grouped.items():
        best = {}
        for item in values:
            parsed = location.parse_location(item["value"]) if isinstance(
                item["value"], str) else None
            key = ((parsed or {}).get("municipio") or str(item["value"])).lower()
            previous = best.get(key)
            if previous is None:
                best[key] = item
                continue
            prev_parsed = location.parse_location(previous["value"]) if isinstance(
                previous["value"], str) else None
            if (prev_parsed and not prev_parsed.get("uf")) and parsed and parsed.get("uf"):
                best[key] = item
        out.extend(best.values())
    return out + other


def _locations(data, contest_id):
    view = location.resolve_location(_location_items(data, contest_id),
                                     analyzed=contest_id in data["analyzed"])
    return {"prova": view["prova"], "lotacao": view["lotacao"],
            "nota": ("Prova e lotação são resolvidas separadamente; a lotação nunca "
                     "substitui o local de prova e 'a_divulgar' não é ausência.")}


def _conflict_map(report):
    by_contest = {}
    for item in report["itens"]:
        by_contest.setdefault(item["contest_id"], {})[item["field_name"]] = item["tipo"]
    return by_contest


def decisive_report(db_path, *, contest_ids=None, limit=200) -> dict:
    """Relatório dos quatro grupos, por concurso, com evidência e estado explícito."""
    data = _rows(db_path)
    conflicts = _conflict_map(version_conflicts.conflicts(db_path, limit=100000))
    wanted = set(contest_ids) if contest_ids else set(data["contests"])
    items = []
    for contest_id in data["contests"]:
        if contest_id not in wanted:
            continue
        items.append({
            "contest_id": contest_id,
            "indigenas": _indigenous(data, contest_id, conflicts.get(contest_id, {})),
            "sistemas_de_informacao": _si(data, contest_id),
            "prazos": _deadlines(data, contest_id),
            "local": _locations(data, contest_id),
            "conflitos": conflicts.get(contest_id, {}),
        })
    summary = {
        "indigenas": _count(items, lambda item: item["indigenas"]["estado"],
                            INDIGENOUS_STATES),
        "sistemas_de_informacao": _count(
            items, lambda item: item["sistemas_de_informacao"]["estado"],
            ("explicito", "categoria_inclui_curso", "area_correlata_interpretacao",
             "outras_formacoes", "nao_encontrado", "extracao_incompleta")),
        "sistemas_de_informacao_por_cargo": _count_roles(items),
        "prazos": _count(items,
                         lambda item: item["prazos"]["inscricao_fim"]["estado"],
                         ("candidato", "ambiguo", "nao_localizado", "nao_pesquisado",
                          "sem_data_documental")),
        "local_prova": _count(items, lambda item: item["local"]["prova"]["state"],
                              ("confirmado_documentalmente", "extraido_nao_revisado",
                               "ambiguo", "em_conflito", "nao_informado", "nao_extraido")),
    }
    return {"version": DECISIVE_VERSION, "generated_at": _now(),
            "universo": len(items), "resumo": summary,
            "itens": items[:max(0, int(limit))],
            "limitacao": ("Todos os valores são candidatos. Total agregado não é vaga "
                          "indígena; ausência de modalidade não é zero; prazo de resultado "
                          "não compete com edital; lotação não é local de prova.")}


def _count_roles(items):
    counts = {}
    total = 0
    for item in items:
        for role in item["sistemas_de_informacao"]["cargos"]:
            total += 1
            counts[role["estado"]] = counts.get(role["estado"], 0) + 1
    order = ("explicito", "categoria_inclui_curso", "area_correlata_interpretacao",
             "outras_formacoes", "nao_encontrado", "extracao_incompleta")
    return [{"estado": state, "quantidade": counts.get(state, 0), "de": total,
             "pct": round(100.0 * counts.get(state, 0) / total, 1) if total else None}
            for state in order]


def _count(items, key, order):
    counts = {}
    for item in items:
        value = key(item)
        counts[value] = counts.get(value, 0) + 1
    total = len(items)
    return [{"estado": state, "quantidade": counts.get(state, 0), "de": total,
             "pct": round(100.0 * counts.get(state, 0) / total, 1) if total else None}
            for state in order]
