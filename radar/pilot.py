"""Piloto de revisão humana do Anexo II da SEDUC-PA (Fase 43).

Seleciona **10–20 linhas** representativas do quadro, de forma determinística, e produz uma
ficha por linha: por que foi escolhida, qual documento/versão a sustenta, quais campos têm
evidência completa, quais têm incerteza, o estado da identidade e o efeito de cada decisão
possível.

O módulo **não decide nada**. Ele prepara candidatos; confirmar, rejeitar, marcar como
ambíguo ou selecionar valor vigente continua sendo ato humano na Mesa de Revisão.
"""

from __future__ import annotations

from contextlib import closing

from radar import identity_suggestions, review_groups
from radar.document_store import connect_documents, is_readable_schema

VERSION = "pilot_v1"
DEFAULT_SIZE = 16
MIN_SIZE = 10
MAX_SIZE = 20

FIELD_LABELS = {
    "immediate_vacancies": "Vagas imediatas (total publicado)",
    "indigenous_vacancies": "Indígenas (coluna exclusiva)",
    "unified_ppiq_vacancies": "PPIQ (vaga unificada)",
    "unified_pi_pq_vacancies": "PI/PQ (vaga unificada)",
}

EFFECTS = {
    "immediate_vacancies": {
        "validado": ("registra que o total publicado da linha foi conferido; **não** "
                     "confirma PI, PPIQ nem PI/PQ"),
        "rejeitado": ("mantém o total publicado no documento, marca a leitura como "
                      "incorreta e preserva a evidência"),
        "ambiguo": "sinaliza que o total não pôde ser lido com segurança",
        "adiado": "deixa o campo pendente para outra sessão",
    },
    "indigenous_vacancies": {
        "validado": ("registra a vaga **exclusiva** indígena da linha; as colunas "
                     "unificadas continuam pendentes"),
        "rejeitado": "marca a leitura como incorreta, sem apagar a evidência",
        "ambiguo": "sinaliza dúvida sobre a coluna PI desta linha",
        "adiado": "deixa o campo pendente para outra sessão",
    },
    "unified_ppiq_vacancies": {
        "validado": ("registra a vaga **unificada** (PP+PI+PQ); não é vaga exclusiva "
                     "indígena e não pode ser somada à coluna PI"),
        "rejeitado": "marca a leitura como incorreta, sem apagar a evidência",
        "ambiguo": "sinaliza dúvida sobre a coluna PPIQ",
        "adiado": "deixa o campo pendente para outra sessão",
    },
    "unified_pi_pq_vacancies": {
        "validado": ("registra a vaga **unificada** (PI+PQ); não é vaga exclusiva "
                     "indígena e não pode ser somada à coluna PI"),
        "rejeitado": "marca a leitura como incorreta, sem apagar a evidência",
        "ambiguo": "sinaliza dúvida sobre a coluna PI/PQ",
        "adiado": "deixa o campo pendente para outra sessão",
    },
}


def _bucket(item) -> list[dict]:
    """Casos representativos que a linha ilustra (motivos, não rótulos de aprovação).

    Só o quadro largo por colunas tem quantidades inteiras por modalidade. Notação
    ("CR*", "N+CR") e distribuição em texto **não** publicam zero nem coluna PI: são
    tratadas como casos próprios, sem inventar quantidade nem zero explícito.
    """
    context = item["contexto"] or {}
    values = context.get("valores") or {}
    reasons = []
    if context.get("tipo") == "colunas":
        numbers = {name: value for name, value in values.items()
                   if isinstance(value, int)}
        if numbers.get("PI", 0) > 0:
            reasons.append({"caso": "pi_exclusivo",
                            "motivo": "publica vaga exclusiva indígena (PI > 0)"})
        if numbers.get("PPIQ", 0) > 0:
            reasons.append({"caso": "ppiq",
                            "motivo": "publica vaga unificada PPIQ (PP+PI+PQ)"})
        if numbers.get("PI/PQ", 0) > 0:
            reasons.append({"caso": "pi_pq",
                            "motivo": "publica vaga unificada PI/PQ (PI+PQ)"})
        if all(name in numbers for name in ("PI", "PPIQ", "PI/PQ")) and all(
                numbers[name] == 0 for name in ("PI", "PPIQ", "PI/PQ")):
            reasons.append({"caso": "reserva_zero",
                            "motivo": "publica zero explícito nas três colunas indígenas"})
        nonzero = sum(1 for name in ("AC", "PcD", "PP", "PI", "PQ", "PPIQ", "PI/PQ")
                      if numbers.get(name))
        if nonzero >= 5:
            reasons.append({"caso": "modalidades_diversas",
                            "motivo": f"{nonzero} modalidades com quantidade na linha"})
        if numbers.get("Total") and numbers.get("Total") >= 20:
            reasons.append({"caso": "total_alto",
                            "motivo": f"total publicado alto ({numbers.get('Total')})"})
    elif any(proposal["field_name"] == "indigenous_reserve_notation"
             for proposal in item["propostas"]):
        reasons.append({"caso": "reserva_sem_quantidade",
                        "motivo": ("reserva indígena publicada por notação, sem quantidade "
                                   "numérica (não é zero nem vaga imediata)")})
    if context.get("rotulo_completado"):
        reasons.append({"caso": "multipagina",
                        "motivo": "rótulo completado a partir da página seguinte"})
    if item["validacao"] and item["validacao"].get("estado") == "divergente":
        reasons.append({"caso": "divergencia",
                        "motivo": "soma das colunas não fecha com o total publicado"})
    cargo = (context.get("cargo") or "").split()
    if cargo and cargo[-1].lower().strip(",;") in (
            "e", "de", "da", "do", "das", "dos", "em", "para", "a", "o"):
        reasons.append({"caso": "cargo_continuado",
                        "motivo": ("cargo termina em conectivo; a formação continua o nome "
                                    "do cargo e não é especialidade")})
    return reasons


def _identity_warning(item, suggestion):
    warnings = list((suggestion or {}).get("avisos") or [])
    if item["identidade"] != "reconciliado":
        warnings.append({"codigo": "identidade_pendente",
                         "texto": ("o rótulo do documento ainda não foi reconciliado com "
                                   "uma identidade canônica")})
    return warnings


def _fields(item):
    """Campos com evidência e incertezas, um por campo (correção não duplica)."""
    complete, uncertain = [], []
    context = item["contexto"] or {}
    by_field = {}
    for proposal in item["propostas"]:
        field = proposal["field_name"]
        if field not in FIELD_LABELS:
            continue
        current = by_field.get(field)
        if current is None or proposal["state"] == "selecionado" or (
                proposal.get("extraction_method") == "correcao_humana"):
            by_field[field] = proposal
    for field, proposal in by_field.items():
        entry = {"field_name": field, "field_label": FIELD_LABELS[field],
                 "value": proposal["value"], "state": proposal["state"],
                 "proposal_id": proposal["proposal_id"],
                 "page": proposal["evidence"]["page_number"],
                 "quote": proposal["evidence"]["quote"],
                 "evidence_sha256": proposal["evidence_sha256"]}
        if proposal["evidence"]["quote"]:
            complete.append(entry)
        else:
            uncertain.append({**entry, "motivo": "sem trecho literal registrado"})
    if context.get("escolaridade_completada"):
        uncertain.append({
            "field_name": "escolaridade", "field_label": "Escolaridade da linha",
            "motivo": ("célula completada a partir da página seguinte; conferir as páginas "
                       f"{context.get('paginas')}"),
            "value": context.get("escolaridade")})
    if not any(item["field_name"] == "education" for item in item["propostas"]):
        uncertain.append({
            "field_name": "education", "field_label": "Escolaridade",
            "motivo": ("o edital não publica requisito de escolaridade nesta linha; a "
                       "formação vem do cabeçalho da coluna")})
    return complete, uncertain


def _actions(item):
    actions = []
    for proposal in item["propostas"]:
        field = proposal["field_name"]
        if field not in EFFECTS:
            continue
        actions.append({"field_name": field,
                        "field_label": FIELD_LABELS[field],
                        "proposal_id": proposal["proposal_id"],
                        "efeito": EFFECTS[field]})
    return actions


def _spread(candidates, count, *, selected, seen, size, key, regional_counts,
            force=False):
    """Escolhe até ``count`` exemplos variando ``key`` e respeitando o teto por regional.

    ``force`` só é usado por caso obrigatório que não tem candidato fora das regionais
    saturadas: a exceção é registrada em ``compromissos`` pelo chamador, nunca silenciosa.
    """
    taken = []
    used = set()
    for item in candidates:
        if len(taken) >= count or len(selected) >= size:
            break
        value = (item["contexto"] or {}).get(key)
        regional = (item["contexto"] or {}).get("regional")
        if item["linha_id"] in seen or value in used:
            continue
        if not force and regional_counts().get(regional, 0) >= 2:
            continue
        used.add(value)
        seen.add(item["linha_id"])
        selected.append(item)
        taken.append(item)
    if not taken and force:
        for item in candidates:
            if len(taken) >= count or len(selected) >= size:
                break
            if item["linha_id"] in seen:
                continue
            seen.add(item["linha_id"])
            selected.append(item)
            taken.append(item)
    return taken


def all_groups(db_path, *, contest_id: str) -> list[dict]:
    """Todas as linhas com contexto do concurso (uma leitura paginada)."""
    items, offset = [], 0
    while True:
        page = review_groups.groups(db_path, contest_id=contest_id, contexto=True,
                                    state="todos", limit=500, offset=offset)
        items.extend(page["itens"])
        offset += page["limit"]
        if not page["has_more"]:
            break
    return items


def select(db_path, *, contest_id: str, size: int = DEFAULT_SIZE,
           items: list[dict] | None = None) -> dict:
    """Seleção determinística de linhas do quadro (10–20), com diversidade de casos."""
    size = max(MIN_SIZE, min(MAX_SIZE, int(size)))
    if items is None:
        items = all_groups(db_path, contest_id=contest_id)
    items.sort(key=lambda item: (item["page_number"] or 0, item["start_offset"] or 0))

    by_bucket = {}
    for item in items:
        for reason in _bucket(item):
            by_bucket.setdefault(reason["caso"], []).append(item)

    def regional_counts():
        counts = {}
        for item in selected:
            name = (item["contexto"] or {}).get("regional")
            counts[name] = counts.get(name, 0) + 1
        return counts

    selected, seen, compromissos = [], set(), []

    # 1) casos obrigatórios, do mais escasso ao mais comum. O caso escasso escolhe
    # primeiro para não ser "roubado" por um caso comum que compartilha a mesma linha.
    mandatory = {"pi_exclusivo": 1, "ppiq": 1, "pi_pq": 1, "multipagina": 2,
                 "reserva_zero": 2, "cargo_continuado": 1}
    for case in sorted(mandatory, key=lambda name: len(by_bucket.get(name, []))):
        quota = mandatory[case]
        added = _spread(by_bucket.get(case, []), quota, selected=selected, seen=seen,
                        size=size, key="regional", regional_counts=regional_counts)
        if len(added) < quota and by_bucket.get(case):
            forced = _spread(by_bucket.get(case, []), quota - len(added),
                             selected=selected, seen=seen, size=size, key="regional",
                             regional_counts=regional_counts, force=True)
            if forced:
                compromissos.append({
                    "caso": case,
                    "motivo": ("sem candidato fora das regionais já com duas linhas; "
                               "uma linha extra foi incluída para cobrir o caso"),
                    "linhas": [item["linha_id"] for item in forced]})
    # 2) diversidade de cargo/formação/regional, no máximo duas linhas por regional
    for key, quota in (("cargo", 6), ("formacao", 4), ("regional", 6)):
        present = {(item["contexto"] or {}).get(key) for item in selected}
        added = 0
        for item in items:
            if len(selected) >= size or added >= quota:
                break
            value = (item["contexto"] or {}).get(key)
            regional = (item["contexto"] or {}).get("regional")
            if (value in present or item["linha_id"] in seen
                    or regional_counts().get(regional, 0) >= 2):
                continue
            seen.add(item["linha_id"])
            selected.append(item)
            present.add(value)
            added += 1
    # 3) um exemplo dos casos restantes, se houver espaço
    for case in ("modalidades_diversas", "divergencia", "total_alto",
                 "reserva_sem_quantidade"):
        if len(selected) >= size:
            break
        _spread(by_bucket.get(case, []), 1, selected=selected, seen=seen, size=size,
                key="regional", regional_counts=regional_counts)
    # 4) completa com as primeiras linhas ainda não escolhidas, respeitando o teto
    for item in items:
        if len(selected) >= size:
            break
        if item["linha_id"] in seen:
            continue
        regional = (item["contexto"] or {}).get("regional")
        if regional_counts().get(regional, 0) >= 2:
            continue
        seen.add(item["linha_id"])
        selected.append(item)
    # 5) se o teto impediu completar, completa sem ele (registrando o compromisso)
    faltando = size - len(selected)
    if faltando > 0:
        extra = []
        for item in items:
            if len(selected) >= size:
                break
            if item["linha_id"] in seen:
                continue
            seen.add(item["linha_id"])
            selected.append(item)
            extra.append(item["linha_id"])
        if extra:
            compromissos.append({
                "caso": "tamanho",
                "motivo": ("o teto de duas linhas por regional impediria atingir o "
                           "tamanho mínimo do piloto"),
                "linhas": extra})

    selected.sort(key=lambda item: (item["page_number"] or 0, item["start_offset"] or 0))
    return {"linhas": selected, "universo": len(items),
            "por_caso": {case: len(by_bucket.get(case, [])) for case in
                         ("pi_exclusivo", "ppiq", "pi_pq", "multipagina",
                          "reserva_zero", "cargo_continuado",
                          "reserva_sem_quantidade", "modalidades_diversas",
                          "divergencia", "total_alto")},
            "compromissos": compromissos}


def available(db_path) -> dict:
    """Concursos que têm linhas de quadro prontas para o piloto (somente leitura)."""
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = conn.execute(
            "SELECT p.contest_id, COUNT(DISTINCT COALESCE(e.block_id,'') || '|' || "
            "e.page_number || '|' || e.start_offset || '|' || e.end_offset) AS linhas, "
            "COUNT(*) AS propostas, MIN(d.published_at), MAX(d.published_at) "
            "FROM propostas_campo p JOIN evidencias e ON e.id=p.evidence_id "
            "JOIN versoes_documento v ON v.id=e.version_id "
            "JOIN documentos d ON d.id=v.document_id "
            "WHERE p.extraction_method IN ('quadro-colunas-pdf','distribuicao-texto') "
            "GROUP BY p.contest_id ORDER BY linhas DESC, p.contest_id").fetchall()
        items = []
        for contest_id, linhas, propostas, first, last in rows:
            label = conn.execute(
                "SELECT title FROM documentos WHERE contest_id=? "
                "ORDER BY CASE tipo_documental WHEN 'edital_retificado' THEN 0 "
                "WHEN 'edital_abertura' THEN 1 ELSE 2 END, published_at DESC LIMIT 1",
                (contest_id,)).fetchone()
            items.append({"contest_id": contest_id,
                          "titulo": label[0] if label else None,
                          "linhas": linhas, "propostas": propostas,
                          "publicado_de": first, "publicado_ate": last})
    return {"version": VERSION, "itens": items, "total": len(items)}


def prewarm(db_path, *, contest_id: str) -> dict:
    """Aquece o cache de contexto de linha (somente leitura, sem gravar nada).

    O contexto do quadro é derivado da versão armazenada; o cache em processo evita
    reparsear o PDF a cada página da revisão. Esta função só lê.
    """
    from radar import review_groups
    before = review_groups.cache_stats()
    page = review_groups.groups(db_path, contest_id=contest_id, contexto=True,
                                state="todos", limit=1)
    after = review_groups.cache_stats()
    return {"version": VERSION, "contest_id": contest_id,
            "linhas_no_recorte": page["total"],
            "versoes_em_cache_antes": before["versoes"],
            "versoes_em_cache_depois": after["versoes"],
            "gravacoes": 0}


def report(db_path, *, contest_id: str, size: int = DEFAULT_SIZE) -> dict:
    """Relatório do piloto: seleção, fichas, distribuição e estado da revisão."""
    if not contest_id:
        raise ValueError("contest_id obrigatório")
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        decisions = conn.execute(
            "SELECT COUNT(*) FROM revisoes_campo WHERE proposal_id IN "
            "(SELECT p.id FROM propostas_campo p JOIN evidencias e ON e.id=p.evidence_id "
            " WHERE p.contest_id=?)", (contest_id,)).fetchone()[0]
        vigentes = conn.execute(
            "SELECT COUNT(*) FROM valores_atuais WHERE contest_id=?",
            (contest_id,)).fetchone()[0]

    items = all_groups(db_path, contest_id=contest_id)
    selection = select(db_path, contest_id=contest_id, size=size, items=items)
    suggestions = identity_suggestions.report(db_path, contest_id=contest_id,
                                              items=items)
    by_line = {linha: item for item in suggestions["itens"]
               for linha in item["linhas_ids"]}

    fichas = []
    for item in selection["linhas"]:
        context = item["contexto"] or {}
        suggestion = by_line.get(item["linha_id"])
        complete, uncertain = _fields(item)
        fichas.append({
            "linha_id": item["linha_id"],
            "pagina": item["page_number"],
            "paginas": context.get("paginas") or [item["page_number"]],
            "porque": _bucket(item),
            "documento": {"document_id": item["document_id"],
                          "titulo": item["document_title"],
                          "version_id": item["version_id"],
                          "sha256": item["sha256"],
                          "issuer": item["issuer"],
                          "tipo_documental": item["tipo_documental"],
                          "url": item.get("official_url")},
            "linha": {"scope": item["scope"],
                      "cargo": context.get("cargo"),
                      "formacao": context.get("formacao"),
                      "regional": context.get("regional"),
                      "escolaridade": context.get("escolaridade"),
                      "cabecalho": context.get("cabecalho"),
                      "trecho": context.get("trecho"),
                      "colunas": context.get("colunas"),
                      "total_publicado": (
                          (context.get("valores") or {}).get("Total")
                          if context.get("tipo") == "colunas"
                          else context.get("total")),
                      "notas": context.get("notas")},
            "validacao": item["validacao"],
            "campos_com_evidencia": complete,
            "campos_incertos": uncertain,
            "identidade": {"estado": item["identidade"],
                           "sugestao": None if suggestion is None else {
                               "cargo": suggestion["cargo"],
                               "especialidade": suggestion["especialidade"],
                               "acao_sugerida": suggestion["acao_sugerida"],
                               "linhas_na_identidade": suggestion["linhas"],
                               "regionais": suggestion["regionais"]},
                           "avisos": _identity_warning(item, suggestion)},
            "acoes_humanas": _actions(item),
            "estado_revisao": item["estado"],
            "proxima_acao": item["proxima_acao"],
        })

    # Só propostas reais entram no denominador; notas sintéticas (escolaridade
    # completada, requisito ausente) não são decidíveis e ficam à parte.
    campos = [entry for ficha in fichas
              for entry in (ficha["campos_com_evidencia"] + ficha["campos_incertos"])
              if entry.get("proposal_id")]
    notas_sem_proposta = sum(
        1 for ficha in fichas
        for entry in (ficha["campos_com_evidencia"] + ficha["campos_incertos"])
        if not entry.get("proposal_id"))
    campos_totais = len(campos)
    campos_decididos = sum(
        1 for entry in campos
        if entry["state"] in ("validado", "rejeitado", "corrigido", "selecionado"))
    linhas_decididas = sum(1 for ficha in fichas
                           if ficha["estado_revisao"] == "decidido")
    linhas_parciais = sum(1 for ficha in fichas
                          if ficha["estado_revisao"] == "parcial")
    proxima = next((ficha["linha_id"] for ficha in fichas
                    if ficha["estado_revisao"] != "decidido"), None)
    values_count = {}
    for ficha in fichas:
        for column in (ficha["linha"].get("colunas") or []):
            if column["sigla"] in ("PI", "PPIQ", "PI/PQ"):
                values_count[column["sigla"]] = values_count.get(column["sigla"], 0) + 1
    return {
        "version": VERSION, "contest_id": contest_id,
        "universo": selection["universo"],
        "linhas_selecionadas": len(fichas),
        "propostas_associadas": sum(
            1 for ficha in fichas
            for entry in (ficha["campos_com_evidencia"] + ficha["campos_incertos"])
            if entry.get("proposal_id")),
        "distribuicao": {
            "por_caso": selection["por_caso"],
            "colunas_indigenas_nas_linhas": values_count,
            "regionais": sorted({ficha["linha"]["regional"] for ficha in fichas
                                 if ficha["linha"]["regional"]}),
            "cargos": sorted({ficha["linha"]["cargo"] for ficha in fichas
                              if ficha["linha"]["cargo"]}),
        },
        "qualidade": {
            "linhas_com_evidencia_completa": sum(
                1 for ficha in fichas if ficha["campos_com_evidencia"]),
            "linhas_com_campo_incerto": sum(
                1 for ficha in fichas if ficha["campos_incertos"]),
            "linhas_com_divergencia": sum(
                1 for ficha in fichas
                if (ficha["validacao"] or {}).get("estado") == "divergente"),
            "identidades_pendentes": sum(
                1 for ficha in fichas if ficha["identidade"]["estado"] != "reconciliado"),
        },
        "revisao": {"decisoes_registradas": decisions, "valores_vigentes": vigentes,
                    "piloto_revisado": linhas_decididas == len(fichas) and bool(fichas),
                    "campos_totais": campos_totais,
                    "campos_decididos": campos_decididos,
                    "campos_pendentes": campos_totais - campos_decididos,
                    "notas_sem_proposta": notas_sem_proposta,
                    "linhas_decididas": linhas_decididas,
                    "linhas_parciais": linhas_parciais,
                    "proxima_linha_id": proxima},
        "fichas": fichas,
        "compromissos": selection["compromissos"],
        "aviso": (None if selection["universo"] else
                   {"codigo": "contexto_indisponivel",
                    "texto": ("nenhuma linha com contexto foi lida para este concurso; "
                               "confira o PDF armazenado e o extrator")}),
        "limitacao": ("Preparação de candidatos, não revisão. Nenhuma decisão humana é "
                      "criada por este relatório; confirmar/rejeitar/ambíguo/adiar e "
                      "selecionar valor vigente continuam sendo atos humanos."),
    }
