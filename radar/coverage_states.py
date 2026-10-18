"""Diagnóstico de cobertura documental por certame (Fase 33).

Responde, com denominador explícito, **o que a base realmente cobre** — sem inflar
"cobertura" com páginas de agregador. Cada certame recebe **um** estado documental e uma
próxima ação recomendada.

Estados (mutuamente exclusivos, do mais completo ao menos completo):

| Estado | Significado |
|---|---|
| ``campos_confirmados`` | há campo validado por revisão humana (ou valor vigente) |
| ``conflito`` | há divergência documental registrada entre versões/documentos |
| ``campos_candidatos`` | há proposta de campo decisivo com evidência por página |
| ``edital_extraido`` | edital principal identificado e extraído, sem campo decisivo |
| ``oficial_sem_extracao`` | documento oficial importado, ainda sem extração |
| ``oficial_sem_edital`` | documento oficial importado, mas nenhum classificado como edital |
| ``identidade_pendente`` | documento/observação candidata sem identidade de certame |
| ``obtencao_nao_autorizada`` | fonte existe, mas a política não autoriza obter/persistir |
| ``oficial_nao_importado`` | fonte oficial habilitada conhecida, documento não importado |
| ``apenas_agregador`` | só há página de agregador/notícia, nenhum documento oficial |
| ``sem_documento`` | nenhum documento e nenhuma fonte oficial conhecida |

O estado ``historico`` existe no vocabulário do projeto, mas **não é atribuído
automaticamente**: encerramento de certame não é comprovável com os dados atuais (não há
campo de situação do certame), então presumi-lo seria inventar.

Nada é gravado aqui: o diagnóstico é somente leitura.
"""

from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime, timezone

from radar import source_catalog as catalog
from radar import version_conflicts
from radar.document_types import is_nominal_title
from radar.document_store import connect_documents, is_readable_schema

COVERAGE_VERSION = "coverage_states_v1"

STATE_ORDER = (
    "campos_confirmados",
    "conflito",
    "campos_candidatos",
    "edital_extraido",
    "oficial_sem_extracao",
    "oficial_sem_edital",
    "identidade_pendente",
    "obtencao_nao_autorizada",
    "oficial_nao_importado",
    "apenas_agregador",
    "fonte_nao_catalogada",
    "sem_documento",
)

STATE_LABELS = {
    "campos_confirmados": "Campos revisados e confirmados",
    "conflito": "Documentação conflitante ou incompleta",
    "campos_candidatos": "Campos candidatos disponíveis para revisão",
    "edital_extraido": "Edital principal identificado e extraído",
    "oficial_sem_extracao": "Documento oficial importado, ainda sem extração",
    "oficial_sem_edital": "Documento oficial importado, sem edital classificado",
    "identidade_pendente": "Documento candidato encontrado, identidade pendente",
    "obtencao_nao_autorizada": "Fonte conhecida, obtenção não autorizada",
    "oficial_nao_importado": "Documento oficial acessível, ainda não importado",
    "apenas_agregador": "Apenas notícia/registro de agregador",
    "fonte_nao_catalogada": "Documento de fonte fora do catálogo",
    "sem_documento": "Nenhum documento localizado",
}

NEXT_ACTIONS = {
    "campos_confirmados": "manter; revisar apenas campos obrigatórios pendentes",
    "conflito": "revisar conflito entre versões antes de usar o valor",
    "campos_candidatos": "revisar propostas dos campos decisivos",
    "edital_extraido": "extrair requisitos, prazos e local de prova",
    "oficial_sem_extracao": "extrair texto do documento oficial",
    "oficial_sem_edital": "localizar/classificar o edital principal do certame",
    "identidade_pendente": "reconciliar identidade do documento com o certame",
    "obtencao_nao_autorizada": "não obter; registrar limitação de política",
    "oficial_nao_importado": "executar aquisição controlada do documento oficial",
    "apenas_agregador": "buscar edital oficial na fonte do órgão/banca",
    "fonte_nao_catalogada": "identificar a fonte do documento e catalogá-la (ou descartar a pista)",
    "sem_documento": "descobrir fonte oficial do certame",
}

# Tipos que representam o edital principal.
EDITAL_TYPES = ("edital_abertura", "edital_retificado")
# Campos decisivos para o Radar (quatro grupos da fase).
DECISIVE_FIELDS = ("immediate_vacancies", "reserve_vacancies", "indigenous_vacancies",
                   "indigenous_reserve_vacancies", "education", "accepted_courses",
                   "si_compatibility", "exam_location", "exam_municipio", "exam_uf",
                   "registration_start", "registration_end", "exemption_start",
                   "exemption_end")
# Campos de prova × lotação que **não** são intercambiáveis.
EXAM_FIELDS = ("exam_location", "exam_municipio", "exam_uf")
WORK_FIELDS = ("work_location", "work_municipio", "work_uf")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _host(url) -> str:
    if not isinstance(url, str):
        return ""
    rest = url.split("//", 1)[-1]
    return rest.split("/", 1)[0].split(":", 1)[0].lower()


def _pct(part, total):
    return round(100.0 * part / total, 1) if total else None


def _source_map() -> list[tuple[str, dict]]:
    """(domínio, fonte) do catálogo, do mais específico ao mais genérico."""
    pairs = []
    for source in catalog.catalog():
        for domain in source.get("domains") or ():
            pairs.append((domain.lower(), source))
    pairs.sort(key=lambda pair: len(pair[0]), reverse=True)
    return pairs


def _source_for(host: str, pairs, issuer=None) -> dict | None:
    """Fonte do catálogo dona do host, com desempate por emissor quando o host é compartilhado.

    ``anexos-r2.selecao.net.br`` é usado por mais de uma banca. Sem desempate, o documento
    apareceria como sendo da primeira fonte do catálogo — atribuição errada. O emissor
    declarado no documento decide; se não decidir, devolve ``None`` (fonte ambígua) em vez de
    escolher uma.
    """
    if not host:
        return None
    matched = [source for domain, source in pairs
               if host == domain or host.endswith("." + domain)]
    if not matched:
        return None
    # Mantém apenas os domínios de comprimento máximo (o mais específico).
    best_length = max(len(domain) for domain, source in pairs
                      if host == domain or host.endswith("." + domain))
    matched = [source for domain, source in pairs
               if (host == domain or host.endswith("." + domain))
               and len(domain) == best_length]
    unique = {source["id"]: source for source in matched}
    if len(unique) == 1:
        return next(iter(unique.values()))
    if issuer:
        norm_issuer = _norm_text(issuer)
        for source in unique.values():
            names = {_norm_text(source.get("name") or ""), _norm_text(source.get("vendor") or ""),
                     _norm_text(source.get("id") or "")}
            if any(name and name in norm_issuer for name in names):
                return source
    return None


def _norm_text(value) -> str:
    import unicodedata
    if not isinstance(value, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    return " ".join("".join(ch for ch in decomposed
                            if not unicodedata.combining(ch)).lower().split())


def _is_aggregator_source(source) -> bool:
    return bool(source) and source.get("nature") == "agregador"


def _is_official_source(source) -> bool:
    return bool(source) and source.get("nature") in ("oficial", "institucional")


def _authorized(source) -> bool:
    """Autorização real: a fonte está habilitada **e** a política permite persistir documento."""
    if not source or source.get("status") != "habilitada":
        return False
    try:
        from radar import source_policy
        return bool(source_policy.decision(source["id"], "documento")["allowed"])
    except Exception:  # política indisponível não autoriza nada
        return False


def _load(db_path):
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        contests = [row[0] for row in conn.execute(
            "SELECT id FROM concursos_identidade WHERE estado_identidade='certame' "
            "ORDER BY created_at, id")]
        containers = [row[0] for row in conn.execute(
            "SELECT id FROM concursos_identidade WHERE estado_identidade='container_fonte'")]
        observations = {}
        for contest_id, url, competition_id in conn.execute(
                "SELECT contest_id, source_url, competition_id FROM observacoes_concurso"):
            observations.setdefault(contest_id, []).append(
                {"source_url": url, "competition_id": competition_id})
        documents = []
        for row in conn.execute("""
                SELECT d.id, d.contest_id, d.tipo_documental, d.official_url, d.issuer,
                       d.published_at, d.discovered_at, d.title,
                       (SELECT COUNT(*) FROM versoes_documento v WHERE v.document_id=d.id
                         AND v.extraction_state IN ('parcial','concluida')),
                       (SELECT COUNT(*) FROM blocos_documento b
                         JOIN versoes_documento v ON v.id=b.version_id
                        WHERE v.document_id=d.id),
                       (SELECT COUNT(*) FROM versoes_documento v WHERE v.document_id=d.id
                         AND v.error_code IS NOT NULL)
                FROM documentos d ORDER BY d.discovered_at"""):
            documents.append({
                "id": row[0], "contest_id": row[1], "tipo": row[2], "url": row[3],
                "issuer": row[4], "published_at": row[5], "discovered_at": row[6],
                "title": row[7], "extracted_versions": row[8], "blocks": row[9],
                "errors": row[10],
            })
        proposals = {}
        for contest_id, field_name, page in conn.execute("""
                SELECT p.contest_id, p.field_name, e.page_number
                FROM propostas_campo p LEFT JOIN evidencias e ON e.id=p.evidence_id"""):
            if field_name in DECISIVE_FIELDS:
                proposals.setdefault(contest_id, []).append(
                    {"field_name": field_name, "page": page})
        decisions = {}
        for contest_id, decision in conn.execute("""
                SELECT p.contest_id, r.decision FROM revisoes_campo r
                JOIN propostas_campo p ON p.id=r.proposal_id"""):
            decisions.setdefault(contest_id, set()).add(decision)
        confirmed = {row[0] for row in conn.execute("SELECT DISTINCT contest_id FROM valores_atuais")}
        pending_associations = [row[0] for row in conn.execute(
            "SELECT document_id FROM associacoes_documento WHERE state='pendente'")]
        # Observações sem documento: a fonte informada é a pista para a próxima ação.
        doc_contests = {doc["contest_id"] for doc in documents}
    return {"contests": contests, "containers": containers, "observations": observations,
            "documents": documents, "proposals": proposals, "decisions": decisions,
            "confirmed": confirmed, "pending_associations": pending_associations,
            "doc_contests": doc_contests}


def _contest_view(contest_id, data, pairs, conflict_ids):
    docs = [doc for doc in data["documents"] if doc["contest_id"] == contest_id]
    official, aggregator, unknown, edital, edital_extracted, official_without_blocks = (
        [], [], [], [], [], [])
    classified = []
    for doc in docs:
        source = _source_for(_host(doc["url"]), pairs, doc.get("issuer"))
        doc = dict(doc, source_id=source["id"] if source else None,
                   source_nature=source["nature"] if source else None,
                   source_status=source["status"] if source else None)
        classified.append(doc)
        if _is_aggregator_source(source) or doc["tipo"] == "pagina_agregador":
            aggregator.append(doc)
        elif _is_official_source(source):
            official.append(doc)
            if doc["tipo"] in EDITAL_TYPES:
                edital.append(doc)
                if doc["blocks"]:
                    edital_extracted.append(doc)
            if doc["blocks"] == 0 and doc["extracted_versions"] == 0:
                official_without_blocks.append(doc)
        else:
            # Host fora do catálogo (ou compartilhado sem emissor que decida): não é oficial
            # nem agregador conhecido. Contar como oficial inflaria a cobertura.
            unknown.append(doc)
    decisive = data["proposals"].get(contest_id, [])
    decisive_with_page = [item for item in decisive if item["page"] is not None]
    confirmed = (contest_id in data["confirmed"]
                 or "validado" in data["decisions"].get(contest_id, set())
                 or "corrigido" in data["decisions"].get(contest_id, set()))
    has_conflict = contest_id in conflict_ids

    if confirmed:
        state = "campos_confirmados"
    elif has_conflict:
        state = "conflito"
    elif decisive_with_page:
        state = "campos_candidatos"
    elif edital_extracted:
        state = "edital_extraido"
    elif official_without_blocks:
        state = "oficial_sem_extracao"
    elif unknown and not official:
        state = "fonte_nao_catalogada"
    elif docs and not official:
        state = "apenas_agregador"
    elif official:
        # Há documento oficial (ex.: resultado/homologação), mas nenhum edital.
        state = "oficial_sem_edital"
    else:
        # Sem documento: classificar pela pista de observação (fonte oficial conhecida).
        state = "sem_documento"
        for observation in data["observations"].get(contest_id, []):
            source = _source_for(_host(observation["source_url"]), pairs)
            if source is None:
                continue
            if not _authorized(source):
                # Fonte conhecida (oficial ou não) que a política não autoriza obter.
                state = "obtencao_nao_autorizada"
            elif _is_official_source(source):
                state = "oficial_nao_importado"
            else:
                state = "sem_documento"
            break
    return {
        "contest_id": contest_id, "estado": state, "estado_label": STATE_LABELS[state],
        "proxima_acao": NEXT_ACTIONS[state],
        "documentos": len(docs), "documentos_oficiais": len(official),
        "documentos_agregador": len(aggregator),
        "documentos_nao_catalogados": len(unknown),
        "editais": len(edital), "editais_extraidos": len(edital_extracted),
        "retificacoes": sum(1 for doc in official
                            if doc["tipo"] in ("retificacao", "edital_retificado")),
        "campos_decisivos": sorted({item["field_name"] for item in decisive}),
        "campos_decisivos_com_pagina": len(decisive_with_page),
        "conflito": has_conflict,
        "fontes": sorted({doc["source_id"] for doc in classified
                           if doc.get("source_id")}),
        "ultima_descoberta": max((doc["discovered_at"] or "" for doc in docs), default=None),
    }


def nominal_documents(db_path, *, limit=200) -> dict:
    """Documentos cujo título indica lista nominal (nomes/notas de candidatos).

    Não são apagados (política do projeto), mas ficam visíveis para decisão humana e não
    entram como insumo de campo. Aquisição nova já os ignora por título.
    """
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = conn.execute("""
            SELECT d.id, d.contest_id, d.title, d.tipo_documental, d.official_url,
                   d.discovered_at,
                   (SELECT COUNT(DISTINCT b.page_number) FROM blocos_documento b
                     JOIN versoes_documento v ON v.id=b.version_id
                    WHERE v.document_id=d.id)
            FROM documentos d ORDER BY d.discovered_at DESC""").fetchall()
    items = [{"document_id": row[0], "contest_id": row[1], "title": row[2],
              "tipo_documental": row[3], "official_url": row[4],
              "discovered_at": row[5], "paginas_extraidas": row[6]}
             for row in rows if is_nominal_title(row[2])]
    return {"version": COVERAGE_VERSION, "total": len(items),
            "itens": items[:max(0, int(limit))],
            "limitacao": ("Documento mantido por política de não exclusão. Não é insumo de "
                          "campo e não deve ser reprocessado; decisão humana pode arquivá-lo.")}


def coverage_report(db_path, *, limit=5000) -> dict:
    """Relatório completo: estados por certame, funil, fontes e causas."""
    data = _load(db_path)
    pairs = _source_map()
    conflict_ids = version_conflicts.contest_conflict_ids(db_path)
    items = [_contest_view(contest_id, data, pairs, conflict_ids)
             for contest_id in data["contests"]]
    total = len(items)
    counts = {}
    for item in items:
        counts[item["estado"]] = counts.get(item["estado"], 0) + 1
    states = [{"estado": state, "label": STATE_LABELS[state],
               "quantidade": counts.get(state, 0), "de": total,
               "pct": _pct(counts.get(state, 0), total),
               "proxima_acao": NEXT_ACTIONS[state]}
              for state in STATE_ORDER]

    with_any_doc = sum(1 for item in items if item["documentos"])
    with_official = sum(1 for item in items if item["documentos_oficiais"])
    with_edital = sum(1 for item in items if item["editais"])
    with_edital_extracted = sum(1 for item in items if item["editais_extraidos"])
    with_candidates = sum(1 for item in items if item["campos_decisivos_com_pagina"])
    with_confirmed = sum(1 for item in items if item["estado"] == "campos_confirmados")
    with_conflict = sum(1 for item in items if item["conflito"])
    funnel = [
        {"etapa": "certames", "quantidade": total, "de": total, "pct": _pct(total, total)},
        {"etapa": "com_documento_qualquer", "quantidade": with_any_doc, "de": total,
         "pct": _pct(with_any_doc, total)},
        {"etapa": "com_documento_oficial", "quantidade": with_official, "de": total,
         "pct": _pct(with_official, total)},
        {"etapa": "com_edital_oficial", "quantidade": with_edital, "de": total,
         "pct": _pct(with_edital, total)},
        {"etapa": "com_edital_extraido", "quantidade": with_edital_extracted, "de": total,
         "pct": _pct(with_edital_extracted, total)},
        {"etapa": "com_campos_candidatos", "quantidade": with_candidates, "de": total,
         "pct": _pct(with_candidates, total)},
        {"etapa": "com_campos_confirmados", "quantidade": with_confirmed, "de": total,
         "pct": _pct(with_confirmed, total)},
    ]

    # Fontes que efetivamente trouxeram documento, e fontes que exigem ação do operador.
    by_source = {}
    for doc in data["documents"]:
        source = _source_for(_host(doc["url"]), pairs, doc.get("issuer"))
        key = source["id"] if source else "fonte_desconhecida"
        entry = by_source.setdefault(key, {
            "source_id": key,
            "nature": source["nature"] if source else "desconhecida",
            "status": source["status"] if source else None,
            "documentos": 0, "concursos": set()})
        entry["documentos"] += 1
        if doc["contest_id"]:
            entry["concursos"].add(doc["contest_id"])
    fontes = [dict(item, concursos=len(item["concursos"]))
              for item in sorted(by_source.values(), key=lambda item: -item["documentos"])]
    restritas = [{"source_id": source["id"], "name": source["name"],
                  "status": source["status"],
                  "credential_env": source.get("credential_env"),
                  "motivo": ("exige credencial" if source.get("credential_env")
                             else "acesso bloqueado" if source.get("status") == "bloqueada"
                             else "aguarda validação de uso")}
                 for source in catalog.catalog()
                 if source.get("status") in ("aguardando_credencial",
                                             "aguardando_validacao_de_uso",
                                             "bloqueada")]

    return {
        "version": COVERAGE_VERSION, "generated_at": _now(),
        "universo": {"certames": total, "containers": len(data["containers"]),
                     "documentos": len(data["documents"])},
        "estados": states,
        "funil": funnel,
        "fontes": fontes,
        "fontes_restritas": restritas,
        "documentos_sem_identidade": len(set(data["pending_associations"])),
        "documentos_nominais": sum(1 for doc in data["documents"]
                                   if is_nominal_title(doc.get("title"))),
        "itens": items[:max(0, int(limit))],
        "limitacoes": [
            "Container de fonte não entra no denominador de certames (é área de retenção).",
            "Página de agregador não é documento oficial: cobertura oficial usa apenas "
            "documentos de fonte oficial/banca.",
            "Estado 'historico' não é atribuído automaticamente: não há prova de "
            "encerramento do certame no modelo.",
            "Campo candidato não é campo confirmado; revisão humana é o único caminho.",
        ],
    }


def contests_in_state(db_path, state, *, limit=200) -> dict:
    """Certames em um estado específico, com a próxima ação."""
    if state not in STATE_ORDER:
        raise ValueError("estado desconhecido")
    report = coverage_report(db_path, limit=100000)
    items = [item for item in report["itens"] if item["estado"] == state]
    return {"version": COVERAGE_VERSION, "estado": state,
            "estado_label": STATE_LABELS[state], "total": len(items),
            "de": report["universo"]["certames"],
            "proxima_acao": NEXT_ACTIONS[state],
            "itens": items[:max(0, int(limit))]}
