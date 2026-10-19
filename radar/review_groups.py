"""Revisão agrupada por linha documental (Fase 42).

A fila da Mesa de Revisão é por proposta. Uma linha de quadro de vagas, porém, publica
vários campos no **mesmo trecho**: AC, PcD, PP, PI, PQ, PPIQ, PI/PQ e Total. Revisar isso
proposta a proposta perde o contexto (cabeçalho, total, regional, notas) e induz a decisões
isoladas sem ver a linha.

Este módulo agrupa propostas pela **identidade documental da linha** — versão, bloco,
página e offsets da evidência — nunca por valor igual nem por proximidade. Cada proposta do
grupo continua com o seu próprio estado, histórico e decisão: o grupo é navegação e
contexto, não aprovação conjunta.

O contexto da linha (cabeçalho, colunas, total, regional, notas) vem do parser atual, em
modo somente leitura, e é confrontado com o que está gravado. Divergência de rótulo é
exposta como `rotulo_divergente`; não é corrigida aqui.
"""

from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256

from radar import review
from radar.document_fields import LABEL_PREFIX
from radar.document_store import connect_documents, is_readable_schema

GROUP_VERSION = "review_groups_v1"
FIELD_ORDER = ("immediate_vacancies", "indigenous_vacancies", "unified_ppiq_vacancies",
               "unified_pi_pq_vacancies", "indigenous_reserve_notation",
               "indigenous_reserve_vacancies", "reserve_vacancies",
               "vagas_total_publicado", "vaga_municipio", "si_compatibility", "education")
FIELD_LABELS = {
    "immediate_vacancies": "Vagas imediatas (total publicado)",
    "indigenous_vacancies": "Indígenas (coluna exclusiva)",
    "unified_ppiq_vacancies": "PPIQ (vaga unificada)",
    "unified_pi_pq_vacancies": "PI/PQ (vaga unificada)",
    "indigenous_reserve_notation": "Reserva indígena (notação)",
    "indigenous_reserve_vacancies": "Reserva indígena (quantidade)",
    "reserve_vacancies": "Cadastro de reserva",
    "vagas_total_publicado": "Total agregado",
    "vaga_municipio": "Município/lotação",
    "si_compatibility": "Compatibilidade de formação",
    "education": "Escolaridade",
}
COLUMN_NATURE = {
    "AC": "ampla concorrência", "PcD": "pessoa com deficiência",
    "PP": "pretas e pardas", "PI": "indígena exclusiva", "PQ": "quilombola",
    "PPIQ": "unificada (PP+PI+PQ)", "PI/PQ": "unificada (PI+PQ)", "Total": "total publicado",
    "AMPLA": "ampla concorrência", "PCD": "pessoa com deficiência",
    "TOTAL": "total publicado",
}
TABLE_METHODS = ("quadro-colunas-pdf", "distribuicao-texto")

# Cache em processo do contexto de linha. A chave inclui a versão (imutável) e a versão do
# parser: mudar o parser invalida; a base não muda o resultado de uma versão já gravada.
_CONTEXT_CACHE: dict = {}


def _now(now=None):
    if isinstance(now, str):
        return datetime.fromisoformat(now)
    return now or datetime.now(timezone.utc)


def _key(row) -> tuple:
    """Identidade documental da linha: versão, bloco, página e offsets da evidência."""
    return (row["version_id"], row["block_id"] or "", row["page_number"],
            row["start_offset"], row["end_offset"])


def linha_id(key: tuple) -> str:
    raw = "|".join(str(part) for part in key)
    return sha256(raw.encode("utf-8")).hexdigest()[:16]


def _contexts(db_path, versions):
    """Contexto de linha por versão, lido do parser atual (somente leitura)."""
    from radar import modality_legend, reprocess, vacancy_columns, vacancy_inline

    parser_version = vacancy_columns.VERSION
    out = {}
    for version in versions:
        cache_key = (str(db_path), version, parser_version)
        if cache_key in _CONTEXT_CACHE:
            out[version] = _CONTEXT_CACHE[cache_key]
            continue
        with closing(connect_documents(db_path)) as conn:
            blocks = reprocess.stored_blocks(conn, version)
            artifact = reprocess._artifact_path(conn, version)
        definitions = {}
        for block in blocks:
            for key, value in modality_legend.parse_definitions(
                    block.get("text") or "").items():
                definitions.setdefault(key, value)
        wide = vacancy_columns.parse_wide_table(
            blocks, "", label_prefix=LABEL_PREFIX, pdf_path=artifact,
            definitions=definitions)
        notation = vacancy_columns.parse_notation_table(
            blocks, "", label_prefix=LABEL_PREFIX)
        inline = vacancy_inline.extract_distribution(
            blocks, "", label_prefix=LABEL_PREFIX)
        out[version] = {"definicoes": definitions, "wide": wide, "notation": notation,
                        "inline": inline}
        _CONTEXT_CACHE[cache_key] = out[version]
        if len(_CONTEXT_CACHE) > 8:
            _CONTEXT_CACHE.pop(next(iter(_CONTEXT_CACHE)))
    return out


def _wide_match(rows, values, label, quote=None):
    """Linha do quadro largo compatível com os quatro campos persistidos do grupo."""
    if quote:
        exact = [item for item in rows if item.get("quote") == quote]
        if len(exact) == 1:
            return exact[0]
    wanted = tuple(values.get(name) for name in ("PI", "PPIQ", "PI/PQ", "Total"))
    candidates = [item for item in rows
                  if tuple(item["valores"].get(name) for name in
                           ("PI", "PPIQ", "PI/PQ", "Total")) == wanted]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    from radar import vacancy_columns
    for item in candidates:
        composed = vacancy_columns.compose_label(item["cargo"], item["formacao"],
                                                 item["dre"])
        if composed == label:
            return item
    return None


def _match_page_rows(rows, page, quote, label):
    """Linha de notação/texto da página: casa pelo trecho e, sem ele, pelo cargo.

    Devolve no máximo uma linha; empate não é resolvido por adivinhação.
    """
    candidates = [item for item in rows if item["page"] == page]
    if quote:
        exact = [item for item in candidates if item.get("quote") == quote]
        if len(exact) == 1:
            return exact
    if label:
        by_label = [item for item in candidates
                    if (item.get("cargo") or "").strip().lower() == label.strip().lower()]
        if len(by_label) == 1:
            return by_label
    return []


def _validacao(context):
    """Validação aritmética publicada, sem inferir vagas."""
    if not context:
        return None
    kind = context.get("tipo")
    if kind == "colunas":
        values = context.get("valores") or {}
        total = values.get("Total")
        soma = sum(values.get(name) or 0 for name in
                   ("AC", "PcD", "PP", "PI", "PQ", "PPIQ", "PI/PQ"))
        return {"tipo": "colunas", "publicado": total, "soma": soma,
                "diferenca": None if total is None else total - soma,
                "estado": ("consistente" if total == soma else "divergente"),
                "regra": ("Anexo II: AC+PcD+PP+PI+PQ+PPIQ+PI/PQ = Total; as colunas "
                          "unificadas são posições distintas, não subconjuntos")}
    if kind == "notacao":
        total = context.get("total")
        return {"tipo": "notacao", "publicado": total,
                "soma": None, "diferenca": None,
                "estado": context.get("estado") or "nao_aplicavel",
                "regra": ("Células 'N+CR' publicam vagas imediatas e cadastro de reserva; "
                          "'CR*' é reserva sem quantidade")}
    if kind == "texto":
        itens = context.get("valores") or {}
        total = context.get("total")
        soma = sum(itens.values()) if itens else None
        estado = ("consistente" if total is not None and soma == total
                  else "divergente" if total is not None and soma is not None
                  else "nao_aplicavel")
        return {"tipo": "texto", "publicado": total,
                "soma": soma, "diferenca": None, "estado": estado,
                "regra": "Distribuição publicada no texto; percentual não vira quantidade"}
    return None


def _context_for(version_context, group_rows, label):
    """Contexto da linha: colunas, cabeçalho, páginas, notas e validação."""
    wide = version_context["wide"]
    values = {}
    field_column = {"immediate_vacancies": "Total", "indigenous_vacancies": "PI",
                    "unified_ppiq_vacancies": "PPIQ",
                    "unified_pi_pq_vacancies": "PI/PQ"}
    for row in group_rows:
        column = field_column.get(row["field_name"])
        if column is None:
            continue
        try:
            values[column] = json.loads(row["value_json"])
        except (TypeError, ValueError):
            values[column] = None
    page = group_rows[0]["page_number"]
    stored_quote = group_rows[0].get("quote") or ""
    match = _wide_match(wide["rows"], values, label, quote=stored_quote)
    if match:
        colunas = [{"sigla": name, "valor": match["valores"].get(name),
                    "natureza": COLUMN_NATURE.get(name, "outra")}
                   for name in ("AC", "PcD", "PP", "PI", "PQ", "PPIQ", "PI/PQ", "Total")]
        notas = []
        for sigla in ("PI", "PPIQ", "PI/PQ"):
            definition = version_context["definicoes"].get(sigla)
            if definition:
                notas.append({"sigla": sigla, "rotulo": definition["label"],
                              "trecho": definition["quote"]})
        from radar import vacancy_columns
        rotulo = vacancy_columns.compose_label(match["cargo"], match["formacao"],
                                               match["dre"])
        return {"tipo": "colunas", "paginas": match.get("pages") or [page],
                "cabecalho": "AC | PcD | PP | PI | PQ | PPIQ | PI/PQ | Total",
                "cargo": match["cargo"], "formacao": match["formacao"],
                "escolaridade": match["escolaridade"], "regional": match["dre"],
                "valores": match["valores"], "colunas": colunas, "notas": notas,
                "rotulo_parser": LABEL_PREFIX + rotulo,
                "rotulo_completado": bool(match.get("rotulo_completado")),
                "escolaridade_completada": bool(match.get("escolaridade_completada")),
                "trecho": match.get("quote")}
    for item in _match_page_rows(version_context["notation"]["rows"], page,
                                 stored_quote, label):
        celulas = item.get("celulas") or {}
        notas = []
        return {"tipo": "notacao", "paginas": [page], "cabecalho": " | ".join(celulas),
                "cargo": item.get("cargo"), "formacao": None, "escolaridade": None,
                "regional": None, "valores": celulas, "total": celulas.get("TOTAL"),
                "colunas": [{"sigla": name, "valor": value,
                             "natureza": COLUMN_NATURE.get(name, "outra")}
                            for name, value in celulas.items()],
                "notas": notas, "trecho": item.get("quote"),
                "estado": "consistente" if item.get("consistente") else "divergente"}
    for item in _match_page_rows(version_context["inline"]["rows"], page,
                                 stored_quote, label):
        itens = item.get("itens") or {}
        return {"tipo": "texto", "paginas": [page], "cabecalho": "distribuição em texto",
                "cargo": item.get("cargo"), "formacao": None, "escolaridade": None,
                "regional": None, "valores": itens, "total": item.get("total"),
                "colunas": [{"sigla": name, "valor": value, "natureza": "modalidade"}
                            for name, value in itens.items()],
                "notas": [], "trecho": item.get("quote"),
                "estado": "consistente" if item.get("consistente") else "divergente"}
    return None


def _next_action(group):
    if group["conflito"]:
        return "resolver o conflito entre as propostas antes de confirmar"
    if group["identidade"] == "pendente":
        return "reconciliar a identidade do cargo (Mesa de identidades)"
    if group["validacao"] and group["validacao"].get("estado") == "divergente":
        return "conferir a divergência aritmética contra o quadro publicado"
    if group["pendentes"] == 0:
        return "linha revisada; nada pendente"
    return "revisar campo a campo (cada decisão é independente)"


def groups(db_path, *, contest_id=None, document_id=None, version_id=None,
           state="aberto", field_name=None, contexto=None, limit=25, offset=0,
           now=None) -> dict:
    """Grupos de revisão por linha documental, com contexto e validação."""
    if state not in ("aberto", "pendente", "decidido", "todos"):
        raise ValueError("estado de grupo inválido")
    limit, offset = int(limit), int(offset)
    if limit < 1 or limit > 100:
        raise ValueError("limite fora da faixa")
    if offset < 0:
        raise ValueError("deslocamento inválido")
    now_dt = _now(now)

    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = review._rows(conn)
        reconciled = review._reconciled_map(conn)
        editais = review._official_editais(conn)
        totals = {
            "decisoes": conn.execute(
                "SELECT COUNT(*) FROM revisoes_campo").fetchone()[0],
            "vigentes": conn.execute(
                "SELECT COUNT(*) FROM valores_atuais").fetchone()[0],
            "lotes_abertos": conn.execute(
                "SELECT COUNT(*) FROM lotes_revisao WHERE state<>'concluido'").fetchone()[0],
            "lotes_alterados": conn.execute(
                "SELECT COUNT(*) FROM lote_revisao_itens WHERE state='decidido' "
                "AND snapshot_sha256 IS NOT NULL AND snapshot_sha256<>'' "
                "AND proposal_id IN (SELECT p.id FROM propostas_campo p "
                "JOIN evidencias e ON e.id=p.evidence_id "
                "WHERE e.version_id IS NOT NULL)").fetchone()[0],
        }
        by_decision = dict(conn.execute(
            "SELECT decision, COUNT(*) FROM revisoes_campo GROUP BY decision").fetchall())

    conflicts = review._conflicts(rows, reconciled)
    deadlines = review._deadlines(rows)
    duplicates = review._duplicate_members(rows)
    today = now_dt.date()

    filtered = []
    for row in rows:
        if contest_id and row["contest_id"] != contest_id:
            continue
        if document_id and row["document_id"] != document_id:
            continue
        if version_id and row["version_id"] != version_id:
            continue
        if field_name and row["field_name"] != field_name:
            continue
        filtered.append(row)

    grouped = {}
    for row in filtered:
        grouped.setdefault(_key(row), []).append(row)

    versions = sorted({row["version_id"] for row in filtered
                       if row["extraction_method"] in TABLE_METHODS})
    contexts = _contexts(db_path, versions) if versions else {}

    items = []
    for key, group_rows in grouped.items():
        scopes = {}
        for row in group_rows:
            scope = review.role_scope(row, reconciled)[0]
            scopes.setdefault(scope, []).append(row)
        states = {review._state(row["last_decision"], row["selected"])
                  for row in group_rows}
        open_rows = [row for row in group_rows if review._is_open(row)]
        if not open_rows:
            group_state = "decidido"
        elif len(open_rows) == len(group_rows):
            group_state = "pendente"
        else:
            group_state = "parcial"
        if state == "aberto" and not open_rows:
            continue
        if state == "pendente" and group_state != "pendente":
            continue
        if state == "decidido" and group_state != "decidido":
            continue
        scores = [review._priority(row, editais=editais, deadlines=deadlines,
                                   conflicts=conflicts, duplicates=duplicates,
                                   today=today, reconciled=reconciled)[0]
                  for row in group_rows]
        label = review._label_of(group_rows[0]) or ""
        context = None
        if group_rows[0]["extraction_method"] in TABLE_METHODS:
            context = _context_for(contexts[group_rows[0]["version_id"]], group_rows,
                                   label)
        rotulo_divergente = None
        if context and context.get("rotulo_parser"):
            current = context["rotulo_parser"][len(LABEL_PREFIX):].strip()
            if current and current != label:
                rotulo_divergente = {"armazenado": label, "parser": current}
        proposals = []
        for row in sorted(group_rows, key=lambda item: (
                FIELD_ORDER.index(item["field_name"])
                if item["field_name"] in FIELD_ORDER else 99, item["field_name"])):
            proposals.append({
                "proposal_id": row["proposal_id"],
                "field_name": row["field_name"],
                "field_label": FIELD_LABELS.get(row["field_name"], row["field_name"]),
                "value": review._value_of(row["value_json"]),
                "state": review._state(row["last_decision"], row["selected"]),
                "last_decision": row["last_decision"],
                "selected": bool(row["selected"]),
                "ambiguity_reason": row["ambiguity_reason"],
                "extraction_method": row["extraction_method"],
                "evidence_sha256": review._evidence_hash(
                    row["value_json"], row["quote"], row["version_id"],
                    row["start_offset"], row["end_offset"]),
                "evidence": {"quote": row["quote"], "page_number": row["page_number"],
                             "version_id": row["version_id"],
                             "start_offset": row["start_offset"],
                             "end_offset": row["end_offset"],
                             "document_id": row["document_id"]},
            })
        item = {
            "linha_id": linha_id(key),
            "contest_id": group_rows[0]["contest_id"],
            "competition_id": group_rows[0]["competition_id"],
            "document_id": group_rows[0]["document_id"],
            "document_title": group_rows[0]["document_title"],
            "tipo_documental": group_rows[0]["tipo_documental"],
            "issuer": group_rows[0]["issuer"],
            "version_id": group_rows[0]["version_id"],
            "sha256": group_rows[0]["sha256"],
            "page_number": group_rows[0]["page_number"],
            "block_id": group_rows[0]["block_id"],
            "start_offset": group_rows[0]["start_offset"],
            "end_offset": group_rows[0]["end_offset"],
            "scope": next(iter(scopes)),
            "scopes": sorted(scopes),
            "identidade": ("reconciliado" if group_rows[0]["role_id"] else "pendente"),
            "prioridade": max(scores),
            "estado": group_state,
            "estados": sorted(states),
            "pendentes": len(open_rows),
            "conflito": any(review._scope_key(row, reconciled) in conflicts
                             for row in group_rows),
            "contexto": context,
            "validacao": _validacao(context),
            "rotulo_divergente": rotulo_divergente,
            "propostas": proposals,
        }
        item["proxima_acao"] = _next_action(item)
        if contexto is True and item["contexto"] is None:
            continue
        if contexto is False and item["contexto"] is not None:
            continue
        items.append(item)

    # Prioridade manda; no empate, a linha com quadro vem antes (contexto mais rico).
    items.sort(key=lambda item: (-item["prioridade"], 0 if item["contexto"] else 1,
                                 item["contest_id"], item["page_number"] or 0,
                                 item["start_offset"] or 0))
    total = len(items)
    page = items[offset:offset + limit]
    summary = {
        "linhas": total,
        "linhas_com_contexto": sum(1 for item in items if item["contexto"]),
        "linhas_sem_contexto": sum(1 for item in items if not item["contexto"]),
        "linhas_pendentes": sum(1 for item in items if item["estado"] != "decidido"),
        "linhas_decididas": sum(1 for item in items if item["estado"] == "decidido"),
        "linhas_divergentes": sum(1 for item in items
                                  if item["validacao"]
                                  and item["validacao"].get("estado") == "divergente"),
        "linhas_rotulo_divergente": sum(1 for item in items
                                        if item["rotulo_divergente"]),
        "linhas_rotulo_completado": sum(
            1 for item in items if (item["contexto"] or {}).get("rotulo_completado")),
        "linhas_escolaridade_corrigida": sum(
            1 for item in items
            if (item["contexto"] or {}).get("escolaridade_completada")),
        "propostas": sum(len(item["propostas"]) for item in items),
        "propostas_pendentes": sum(item["pendentes"] for item in items),
        "com_conflito": sum(1 for item in items if item["conflito"]),
        "decisoes_registradas": totals["decisoes"],
        "por_decisao": by_decision,
        "valores_vigentes": totals["vigentes"],
        "lotes_abertos": totals["lotes_abertos"],
    }
    return {
        "version": GROUP_VERSION, "generated_at": now_dt.isoformat(),
        "total": total, "limit": limit, "offset": offset,
        "has_more": offset + len(page) < total,
        "filtros": {"contest_id": contest_id, "document_id": document_id,
                    "version_id": version_id, "state": state,
                    "field_name": field_name, "contexto": contexto},
        "resumo": summary,
        "denominador": {
            "unidade": "linha documental (versão × bloco × página × offsets)",
            "universo": "propostas do recorte, agrupadas pela evidência da linha",
            "referencia": now_dt.isoformat(),
            "observacao": ("Contagens de linhas, propostas, decisões e valores vigentes "
                           "são distintas e não se somam."),
        },
        "itens": page,
        "limitacao": ("Grupo é contexto de navegação, não decisão conjunta. Cada proposta "
                      "mantém estado e histórico próprios. Soma correta não confirma "
                      "interpretação; divergência não autoriza trocar o total publicado."),
    }


def repair_summary(db_path) -> dict:
    """Situação dos reparos de rótulo registrados (auditoria)."""
    with closing(connect_documents(db_path)) as conn:
        rows = conn.execute(
            "SELECT note FROM eventos_documentais WHERE event_type='analise' "
            "AND note LIKE '%label_repair%'").fetchall()
    return {"eventos": len(rows)}
