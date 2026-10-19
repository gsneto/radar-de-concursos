"""Mesa de revisão: oportunidades, dossiê e comparação de evidências (Fase 34).

O problema desta fase não é extrair mais: é permitir que uma pessoa revise **por
oportunidade** (concurso + cargo), com evidência localizável e estado explícito, em vez de
percorrer milhares de propostas desconexas.

Este módulo **não** decide nada e **não** cria um segundo fluxo de revisão:

- a decisão continua em ``review.decide_proposal`` / ``review.select_current_value``;
- a fila continua em ``review.review_queue`` (a mesa agrupa o resultado dela);
- o estado documental reutiliza ``coverage_states`` (mesma classificação de fonte);
- conflitos reutilizam ``version_conflicts``; campos decisivos reutilizam
  ``decisive_fields``.

Regras de honestidade aplicadas aqui:

- proposta não é campo confirmado; a mesa mostra o estado real de cada campo;
- ausência de campo não é zero nem resposta negativa;
- total agregado não vira vaga indígena, nem município de lotação vira local de prova;
- quando a evidência não permite localizar página/trecho, a limitação é exibida, nunca
  inventada.
"""

from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime, timezone

from radar import coverage_states, decisive_fields, review, version_conflicts
from radar.document_store import connect_documents, is_readable_schema
from radar.document_types import is_nominal_title

OPPORTUNITY_VERSION = "opportunities_v1"

# Campos que a mesa trata como decisivos, na ordem em que aparecem no dossiê.
DECISIVE_ORDER = (
    "immediate_vacancies", "reserve_vacancies", "indigenous_vacancies",
    "indigenous_reserve_vacancies", "vagas_total_publicado", "education",
    "accepted_courses", "si_compatibility", "registration_start", "registration_end",
    "exemption_start", "exemption_end", "exam_date", "exam_location", "exam_municipio",
    "exam_uf", "work_location", "work_municipio", "work_uf",
)
FIELD_LABELS = {
    "immediate_vacancies": "Vagas imediatas",
    "reserve_vacancies": "Cadastro de reserva",
    "indigenous_vacancies": "Vagas imediatas indígenas",
    "indigenous_reserve_vacancies": "Reserva indígena",
    "vagas_total_publicado": "Total agregado publicado",
    "education": "Escolaridade/requisito",
    "accepted_courses": "Cursos aceitos",
    "si_compatibility": "Compatibilidade com Sistemas de Informação",
    "registration_start": "Início das inscrições",
    "registration_end": "Fim das inscrições",
    "exemption_start": "Início da isenção",
    "exemption_end": "Fim da isenção",
    "exam_date": "Data da prova",
    "exam_location": "Local de prova",
    "exam_municipio": "Município de prova",
    "exam_uf": "UF da prova",
    "work_location": "Lotação",
    "work_municipio": "Município de lotação",
    "work_uf": "UF de lotação",
}

# Estados de campo na mesa (vocabulário do modelo existente, não um enum novo).
FIELD_STATES = ("confirmado", "corrigido", "em_conflito", "ambiguo", "candidato",
                "multiplo_por_cargo", "rejeitado", "nao_extraido")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _field_state(rows: list[dict], reconciled=None) -> str:
    """Estado de um campo a partir das propostas do mesmo escopo.

    Ordem de precedência: decisão humana > conflito de valor > ambiguidade > candidato.
    ``rejeitado`` só vale quando **todas** as propostas foram rejeitadas: uma rejeição
    isolada não apaga as demais.
    """
    active = [row for row in rows if row.get("last_decision") != "rejeitado"]
    if not active:
        return "rejeitado" if rows else "nao_extraido"
    decisions = {row.get("last_decision") for row in active}
    if "validado" in decisions:
        return "confirmado"
    if "corrigido" in decisions:
        return "corrigido"
    values = {row["value_json"] for row in active}
    if len(values) > 1 and rows[0]["field_name"] not in review.MULTI_VALUE_FIELDS:
        # "a_divulgar" + local concreto são escopos diferentes (etapas distintas), não dois
        # valores do mesmo campo — mesma regra da Fase 33.
        if rows[0]["field_name"] in ("exam_location", "exam_municipio", "exam_uf",
                                     "work_location", "work_municipio", "work_uf"):
            plain = {value for value in values
                     if json.loads(value) not in ("a_divulgar", "a divulgar")}
            if len(plain) <= 1:
                return "ambiguo"
        # Propostas de escopos de cargo diferentes não são divergência: são cargos
        # distintos (reconciliados ou não). Chamar de conflito inventaria erro.
        scopes = {_role_scope(row, reconciled)[0] for row in active}
        if len(scopes) > 1:
            return "multiplo_por_cargo"
        return "em_conflito"
    if "ambiguo" in decisions or any(_real_ambiguity(row.get("ambiguity_reason"))
                                     for row in active):
        return "ambiguo"
    return "candidato"


_LABEL_PREFIX = "cargo do documento não reconciliado: "


def _real_ambiguity(reason) -> str | None:
    """Motivo de ambiguidade do **valor**, ignorando o marcador de cargo não reconciliado.

    "Cargo não reconciliado" é pendência de identidade, não incerteza do valor: tratá-lo
    como ambiguidade faria todo campo de edital não reconciliado parecer duvidoso.
    """
    if not isinstance(reason, str) or not reason.strip():
        return None
    if not reason.startswith(_LABEL_PREFIX):
        return reason
    remainder = reason[len(_LABEL_PREFIX):]
    if " — " in remainder:
        remainder = remainder.split(" — ", 1)[1]
    else:
        remainder = ""
    return remainder.strip() or None


def _document_state(db_path, *, limit=100000) -> dict:
    """Estado documental por concurso, reutilizando a classificação de `coverage_states`."""
    report = coverage_states.coverage_report(db_path, limit=limit)
    return {item["contest_id"]: item for item in report["itens"]}


def _contest_titles(db_path) -> dict:
    """Título do certame: prefere edital, senão documento mais recente (nunca inventado)."""
    titles = {}
    with closing(connect_documents(db_path)) as conn:
        for contest_id, title, tipo, published, discovered in conn.execute(
                "SELECT contest_id, title, tipo_documental, published_at, discovered_at "
                "FROM documentos WHERE contest_id IS NOT NULL "
                "ORDER BY discovered_at"):
            entry = titles.setdefault(contest_id, {"title": None, "edital": None,
                                                   "discovered": None})
            if entry["title"] is None:
                entry["title"] = title
            if tipo in coverage_states.EDITAL_TYPES and entry["edital"] is None:
                entry["edital"] = title
            entry["discovered"] = discovered or entry["discovered"]
    return titles


def _roles(db_path) -> dict:
    roles = {}
    with closing(connect_documents(db_path)) as conn:
        for role_id, contest_id, name, specialty, code in conn.execute(
                "SELECT id, contest_id, name, specialty, code FROM cargos_identidade"):
            roles[role_id] = {"role_id": role_id, "contest_id": contest_id, "name": name,
                              "specialty": specialty, "code": code}
    return roles


def _next_action(item) -> str:
    """Próxima ação recomendada, derivada do estado documental e do que já existe."""
    doc = item["documental"]
    if doc["documentos"] == 0:
        return "buscar edital oficial na fonte do órgão/banca"
    if doc["estado"] in ("apenas_agregador", "fonte_nao_catalogada"):
        return "localizar edital oficial (o documento atual não é edital)"
    if doc["estado"] == "oficial_sem_edital":
        return "classificar/localizar o edital principal"
    if doc["estado"] == "oficial_nao_importado":
        return "executar aquisição controlada do edital"
    if item["conflitos"]:
        return "revisar conflito entre versões antes de usar o valor"
    if item["pendentes"]:
        return "revisar candidatos dos campos decisivos"
    # Fallback: a ação declarada pelo estado documental (uma única fonte de vocabulário).
    return doc.get("proxima_acao") or "acompanhar novas publicações"


def _role_scope(row, reconciled=None) -> tuple[str, str | None]:
    """Escopo de cargo para agrupamento (mesma regra da fila de revisão)."""
    return review.role_scope(row, reconciled)


def opportunity_list(db_path, *, field=None, conflict=None, document_state=None,
                     has_page=None, search=None, min_priority=None, contest_id=None,
                     limit=50, offset=0, now=None, bulk=False) -> dict:
    """Oportunidades agrupadas por concurso + cargo, com prioridade explicada.

    ``field`` filtra grupos que têm propostas daquele campo; ``conflict`` (True/False)
    filtra por conflito de valor; ``document_state`` filtra pelo estado documental;
    ``has_page`` filtra por evidência com página; ``search`` procura em título/órgão.
    """
    limit = int(limit)
    offset = int(offset)
    # `bulk` é uso interno da carteira: uma única varredura em vez de quatro páginas.
    if limit < 1 or limit > (5000 if bulk else 200):
        raise ValueError("limite fora da faixa")
    if offset < 0:
        raise ValueError("deslocamento inválido")
    if field and field not in FIELD_LABELS:
        raise ValueError("campo fora do escopo da mesa")
    now_dt = datetime.fromisoformat(now) if isinstance(now, str) else (
        now or datetime.now(timezone.utc))
    today = now_dt.date()

    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = review._rows(conn)
        editais = review._official_editais(conn)
    with closing(connect_documents(db_path)) as conn:
        reconciled = review._reconciled_map(conn)
    conflicts = review._conflicts(rows, reconciled)
    deadlines = review._deadlines(rows)
    duplicates = review._duplicate_members(rows)
    doc_state = _document_state(db_path)
    titles = _contest_titles(db_path)
    roles = _roles(db_path)

    grouped: dict[tuple, list[dict]] = {}
    labels: dict[tuple, str | None] = {}
    for row in rows:
        scope_id, scope_label = _role_scope(row, reconciled)
        key = (row["contest_id"], scope_id)
        grouped.setdefault(key, []).append(row)
        if scope_label:
            labels[key] = scope_label

    items = []
    for (cid, role_id), group in grouped.items():
        if contest_id and cid != contest_id:
            continue
        if field and not any(row["field_name"] == field for row in group):
            continue
        group_conflict = any(review._scope_key(row, reconciled) in conflicts
                             for row in group)
        if conflict is True and not group_conflict:
            continue
        if conflict is False and group_conflict:
            continue
        has_pages = any(row["page_number"] is not None for row in group)
        if has_page is True and not has_pages:
            continue
        if has_page is False and has_pages:
            continue
        doc = doc_state.get(cid) or {}
        if document_state and doc.get("estado") != document_state:
            continue
        title_entry = titles.get(cid) or {}
        role = roles.get(role_id) or {}
        role_label = labels.get((cid, role_id))
        row_role_id = None if str(role_id).startswith("label:") else (role_id or None)
        if role_label and not role:
            role = {"name": role_label, "code": None, "specialty": None}
        label = title_entry.get("edital") or title_entry.get("title") or ""
        haystack = " ".join([label, role.get("name") or "", doc.get("fontes") and
                             " ".join(doc["fontes"]) or ""]).lower()
        if search and search.lower() not in haystack:
            continue

        pending = [row for row in group
                   if review._state(row["last_decision"], row["selected"]) in
                   ("pendente", "adiado", "ambiguo", "nova_extracao")]
        scored = [(review._priority(row, editais=editais, deadlines=deadlines,
                                    conflicts=conflicts, duplicates=duplicates,
                                    today=today, reconciled=reconciled), row)
                  for row in pending]
        scored.sort(key=lambda pair: (-pair[0][0], pair[1]["field_name"],
                                      pair[1]["proposal_id"]))
        best_score, best_factors = scored[0][0] if scored else (0, [])
        if min_priority is not None and best_score < int(min_priority):
            continue

        by_field: dict[str, list[dict]] = {}
        for row in group:
            by_field.setdefault(row["field_name"], []).append(row)
        fields = {}
        for name in DECISIVE_ORDER:
            if name not in by_field:
                continue
            state = _field_state(by_field[name], reconciled)
            fields[name] = {
                "campo": name, "label": FIELD_LABELS.get(name, name), "estado": state,
                "valores": sorted({json.dumps(review._value_of(row["value_json"]),
                                              ensure_ascii=False)
                                   for row in by_field[name]}),
                "propostas": len(by_field[name]),
                "com_pagina": sum(1 for row in by_field[name]
                                  if row["page_number"] is not None),
            }
        # Conflito no escopo do grupo: mesma regra do estado de campo (evita contar
        # divergência entre cargos como conflito de valor).
        conflicts_here = sum(1 for entry in fields.values()
                             if entry["estado"] == "em_conflito")
        item = {
            "contest_id": cid,
            "competition_id": group[0]["competition_id"],
            "contest_title": title_entry.get("edital") or title_entry.get("title"),
            "role_id": row_role_id,
            "scope": role_id,
            "role_name": role.get("name"),
            "role_reconciliado": bool(row_role_id),
            "role_code": role.get("code"),
            "role_specialty": role.get("specialty"),
            "documental": {
                "estado": doc.get("estado"),
                "estado_label": doc.get("estado_label"),
                "documentos": doc.get("documentos", 0),
                "documentos_oficiais": doc.get("documentos_oficiais", 0),
                "editais": doc.get("editais", 0),
                "retificacoes": doc.get("retificacoes", 0),
                "proxima_acao": doc.get("proxima_acao"),
            },
            "campos": fields,
            "pendentes": len(pending),
            "propostas": len(group),
            "conflitos": conflicts_here,
            "tem_pagina": has_pages,
            "ultima_atualizacao": max((row["extracted_at"] or "" for row in group),
                                      default=None),
            "prioridade": best_score,
            "motivos": best_factors,
        }
        item["proxima_acao"] = _next_action(item)
        items.append(item)

    items.sort(key=lambda item: (-item["prioridade"], item["contest_id"],
                                 item["role_id"] or "", item["role_name"] or ""))
    total = len(items)
    page = items[offset:offset + limit]
    return {
        "version": OPPORTUNITY_VERSION, "generated_at": now_dt.isoformat(),
        "total": total, "limit": limit, "offset": offset,
        "has_more": offset + len(page) < total,
        "filtros": {"campo": field, "conflito": conflict, "estado_documental": document_state,
                    "com_pagina": has_page, "busca": search,
                    "prioridade_minima": min_priority},
        "itens": page,
        "limitacao": ("Agrupamento por concurso e cargo. Proposta não é campo confirmado; "
                      "ausência de campo não é zero. A ordem é reproduzível pela política "
                      "de prioridade documentada em radar/review.py."),
    }


def _evidence_view(row) -> dict:
    """Evidência para exibição, com minimização em documento nominal.

    Lista nominal (nomes/notas de candidatos) não reproduz trecho nem contexto: o valor
    extraído e a localização (documento, versão, página, hash) bastam para a decisão.
    """
    nominal = is_nominal_title(row.get("document_title"))
    quote = None if nominal else row["quote"]
    limitation = None
    if nominal:
        limitation = "documento nominal: trecho não reproduzido (dados pessoais)"
    elif not row["quote"]:
        limitation = "sem trecho literal registrado"
    return {
        "proposal_id": row["proposal_id"],
        "value": review._value_of(row["value_json"]),
        "state": review._state(row["last_decision"], row["selected"]),
        "document_id": row["document_id"], "document_title": row["document_title"],
        "tipo_documental": row["tipo_documental"],
        "official_url": row["official_url"], "version_id": row["version_id"],
        "sha256": row["sha256"], "page_number": row["page_number"],
        "quote": quote, "extraction_method": row["extraction_method"],
        "published_at": row["published_at"], "nominal": nominal,
        "limitation": limitation,
    }


def opportunity_dossier(db_path, contest_id: str, *, role_id=None, scope=None) -> dict:
    """Dossiê de uma oportunidade: identidade, documentos, campos, conflitos e lacunas.

    Não resume escondendo divergência: cada grupo traz os valores existentes, o estado e a
    evidência (documento, versão, página, trecho) que os sustenta.
    """
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        exists = conn.execute("SELECT 1 FROM concursos_identidade WHERE id=?",
                              (contest_id,)).fetchone()
        if not exists:
            raise ValueError("concurso inexistente")
        observations = [{"source_url": url, "competition_id": comp}
                        for url, comp in conn.execute(
                            "SELECT source_url, competition_id FROM observacoes_concurso "
                            "WHERE contest_id=? ORDER BY source_url", (contest_id,))]
        documents = []
        for row in conn.execute("""
                SELECT d.id, d.title, d.tipo_documental, d.official_url, d.issuer,
                       d.published_at, d.discovered_at, d.kind,
                       (SELECT COUNT(*) FROM versoes_documento v WHERE v.document_id=d.id),
                       (SELECT MAX(v.fetched_at) FROM versoes_documento v
                         WHERE v.document_id=d.id),
                       (SELECT COUNT(DISTINCT b.page_number) FROM blocos_documento b
                         JOIN versoes_documento v ON v.id=b.version_id
                        WHERE v.document_id=d.id)
                FROM documentos d WHERE d.contest_id=?
                ORDER BY CASE WHEN d.tipo_documental IN ('edital_abertura','edital_retificado')
                              THEN 0 ELSE 1 END, d.published_at, d.discovered_at""",
                (contest_id,)):
            documents.append({"document_id": row[0], "title": row[1], "tipo": row[2],
                              "official_url": row[3], "issuer": row[4],
                              "published_at": row[5], "discovered_at": row[6],
                              "kind": row[7], "versoes": row[8],
                              "ultima_versao": row[9], "paginas_extraidas": row[10]})
        roles = [{"role_id": row[0], "name": row[1], "specialty": row[2], "code": row[3]}
                 for row in conn.execute(
                     "SELECT id, name, specialty, code FROM cargos_identidade "
                     "WHERE contest_id=? ORDER BY name", (contest_id,))]

    doc_state = _document_state(db_path).get(contest_id) or {}
    scoped = decisive_fields.decisive_report(db_path, contest_ids=[contest_id], limit=10)
    decisive = scoped["itens"][0] if scoped["itens"] else {}
    conflicts = version_conflicts.conflicts(db_path, contest_id=contest_id, limit=100)

    with closing(connect_documents(db_path)) as conn:
        rows = [row for row in review._rows(conn) if row["contest_id"] == contest_id]
        reconciled = review._reconciled_map(conn)
    # Escopo do dossiê: identidade canônica, rótulo do documento ou nenhum (concurso).
    wanted = scope if scope is not None else (role_id or None)
    if wanted:
        rows = [row for row in rows if review.role_scope(row, reconciled)[0] == wanted]

    by_field: dict[str, list[dict]] = {}
    for row in rows:
        by_field.setdefault(row["field_name"], []).append(row)
    fields = []
    for name in DECISIVE_ORDER:
        group = by_field.get(name) or []
        if not group:
            fields.append({"campo": name, "label": FIELD_LABELS.get(name, name),
                           "estado": "nao_extraido", "valores": [], "propostas": 0,
                           "evidencias": []})
            continue
        fields.append({
            "campo": name, "label": FIELD_LABELS.get(name, name),
            "estado": _field_state(group, reconciled),
            "valores": sorted({json.dumps(review._value_of(row["value_json"]),
                                          ensure_ascii=False) for row in group}),
            "propostas": len(group),
            "evidencias": [_evidence_view(row)
                            for row in sorted(group, key=lambda r: (
                                r["published_at"] or "", r["proposal_id"]))],
        })

    missing = [entry["campo"] for entry in fields if entry["estado"] == "nao_extraido"]
    pending = [row for row in rows
               if review._state(row["last_decision"], row["selected"]) in
               ("pendente", "adiado", "ambiguo", "nova_extracao")]
    return {
        "version": OPPORTUNITY_VERSION, "generated_at": _now(),
        "contest_id": contest_id, "role_id": role_id, "scope": wanted,
        "identidade": {"observacoes": observations, "cargos": roles},
        "documental": {
            "estado": doc_state.get("estado"), "estado_label": doc_state.get("estado_label"),
            "documentos_oficiais": doc_state.get("documentos_oficiais", 0),
            "editais": doc_state.get("editais", 0),
            "retificacoes": doc_state.get("retificacoes", 0),
            "documentos": documents,
        },
        "campos": fields,
        "campos_ausentes": missing,
        "conflitos": conflicts["itens"],
        "conflitos_total": conflicts["total"],
        "prioritarios": {
            "indigenas": decisive.get("indigenas"),
            "sistemas_de_informacao": decisive.get("sistemas_de_informacao"),
            "prazos": decisive.get("prazos"),
            "local": decisive.get("local"),
        },
        "revisao": {"pendentes": len(pending),
                    "propostas": len(rows),
                    "conflitos": conflicts["total"]},
        "limitacao": ("Dossiê completo para revisão não significa campo confirmado. "
                      "Total agregado não é vaga indígena; lotação não é local de prova."),
    }


# Origem do conteúdo, pelo método de extração registrado na proposta.
_ORIGIN_LABELS = {
    "regex": "extração direta (regex)",
    "tabela": "extração direta (tabela)",
    "tabela-quadrix-pdf": "reconstrução de tabela (Quadrix)",
    "tabela-agregado": "tabela agregada",
    "quadro-vagas-agregado": "quadro com total agregado",
    "quadro-vagas-regional": "reconstrução regional (Fase 32)",
    "local-prova": "extração direta (local de prova)",
    "requisito-inline": "requisitos inline (texto corrido)",
    "requisitos-inline": "requisitos inline (texto corrido)",
    "requisitos-secao": "requisitos por seção (Anexo)",
    "requisitos-formacao": "requisitos de formação (Anexo)",
    "classificacao-si": "classificação de compatibilidade com SI",
    "escolaridade-rotulada": "escolaridade declarada no texto",
    "cronograma": "cronograma do edital",
    "conteudo-programatico": "conteúdo programático",
    "correcao_humana": "correção humana (proposta derivada)",
}


def _origin(method) -> str:
    if not isinstance(method, str):
        return "origem não declarada"
    if method.startswith("ocr"):
        return "texto reconhecido por OCR (conferir no original)"
    return _ORIGIN_LABELS.get(method, f"extração ({method})")


def proposal_evidence(db_path, proposal_id: str, *, context: int = 160) -> dict:
    """Comparação de evidências de uma proposta: contexto, origem, tabela e histórico.

    Amplia ``review.proposal_detail`` sem duplicar decisão: aqui só se **lê**. O contexto
    anterior/posterior vem do texto real do bloco; se o bloco não existir, a limitação é
    declarada em vez de inventar trecho.
    """
    detail = review.proposal_detail(db_path, proposal_id)
    nominal = is_nominal_title(detail["evidence"].get("document_title"))
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        row = conn.execute(
            "SELECT b.text, e.start_offset, e.end_offset, e.page_number, b.version_id "
            "FROM propostas_campo p JOIN evidencias e ON e.id=p.evidence_id "
            "JOIN blocos_documento b ON b.id=e.block_id WHERE p.id=?",
            (proposal_id,)).fetchone()
    if row is None:
        detail["context"] = {"before": None, "after": None,
                             "limitation": "bloco de origem indisponível"}
    else:
        text, start, end = row[0] or "", row[1] or 0, row[2] or 0
        before = text[max(0, start - context):start] if start <= len(text) else ""
        after = text[end:end + context] if end <= len(text) else ""
        detail["context"] = {
            "before": before or None, "after": after or None,
            "limitation": (None if text else "bloco sem texto"),
        }
    if nominal:
        # Minimização: documento nominal não reproduz trecho nem contexto.
        detail["evidence"]["quote"] = None
        detail["evidence"]["limitation"] = (
            "documento nominal: trecho não reproduzido (dados pessoais)")
        detail["context"] = {"before": None, "after": None,
                             "limitation": "documento nominal: contexto não reproduzido"}
        for other in detail.get("other_proposals", []):
            if is_nominal_title(other.get("document_title")):
                other["quote"] = None
    detail["nominal"] = nominal
    detail["origin"] = _origin(detail["proposal"].get("extraction_method"))
    detail["origin_method"] = detail["proposal"].get("extraction_method")
    detail["structural_confidence"] = _structural_confidence(db_path, detail)
    return detail


def _structural_confidence(db_path, detail) -> dict:
    """Confiança estrutural quando a evidência vem do quadro regional (Fase 32).

    Só se aplica ao método que produz o quadro reconstruído **e** quando a página da
    evidência pertence às páginas daquele quadro. Sem esse vínculo, seria atribuir a
    certeza de um quadro a uma linha de outra tabela.
    """
    method = detail["proposal"].get("extraction_method") or ""
    if method != "quadro-vagas-regional":
        return {"aplicavel": False,
                "motivo": ("evidência não vem do quadro regional reconstruído; a certeza "
                           "estrutural da Fase 32 não se aplica a esta linha")}
    from radar import regional_scope
    try:
        report = regional_scope.scope_report(db_path, detail["evidence"]["version_id"])
    except (ValueError, KeyError):
        return {"aplicavel": False, "motivo": "quadro não reconstruível nesta versão"}
    table = report.get("tabela") or {}
    pages = set(table.get("pages") or ())
    page = detail["evidence"].get("page_number")
    if not table or table.get("header_page") is None or (pages and page not in pages):
        return {"aplicavel": False,
                "motivo": ("esta evidência não pertence às páginas do quadro multipágina "
                           "reconstruído")}
    return {
        "aplicavel": True,
        "certeza": table.get("certeza"),
        "header_page": table.get("header_page"),
        "total_page": table.get("total_page"),
        "total_publicado": report.get("total_publicado"),
        "soma_ntes": report.get("soma_ntes"),
        "nota": ("Páginas de cabeçalho/linhas/total do quadro. Total agregado não é "
                 "vaga indígena."),
    }
