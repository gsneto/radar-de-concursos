"""Auditoria de cobertura e qualidade dos dados documentais (Fase 25).

Este módulo mede **o que a base realmente sabe** e **por que falta o resto**, sem inventar dado.

Não confundir com:

- ``auditorias_cobertura`` (``document_review.record_coverage``) — registro append-only de
  conferência humana de escopo documental;
- ``knowledge_store.preparation`` — cobertura de preparação do candidato sobre o programa.

Regras de honestidade aplicadas aqui:

- ``nao_pesquisado`` nunca entra no denominador nem é contado como zero;
- ``edital_oficial`` só considera documento de fato classificado como edital, nunca notícia de
  agregador;
- estado de campo é derivado do vocabulário existente (``revisoes_campo`` > ``ambiguo`` >
  ``extraido``), sem criar um segundo sistema de estados;
- dimensão sem campo no modelo (ex.: prazo de pagamento) é declarada ``nao_mapeado`` em vez de
  inventada.
"""

from __future__ import annotations

import json
from contextlib import closing
from datetime import date, datetime, timezone

from radar.document_fields import label_from_ambiguity
from radar.document_store import connect_documents, is_readable_schema
from radar.priority import proposal_rows

AUDIT_VERSION = "coverage_v1"

# Estados possíveis de uma dimensão, do mais forte ao mais fraco.
STATES = (
    "confirmado",
    "proposto",
    "ambiguo",
    "em_conflito",
    "nao_localizado",
    "falha_extracao",
    "nao_pesquisado",
    "nao_aplicavel",
    "nao_mapeado",
)

STATE_LABELS = {
    "confirmado": "Confirmado com evidência validada",
    "proposto": "Extraído, aguardando revisão",
    "ambiguo": "Extraído com ambiguidade declarada",
    "em_conflito": "Documentos divergentes sem decisão",
    "nao_localizado": "Pesquisado no edital, não localizado",
    "falha_extracao": "Falha técnica de extração",
    "nao_pesquisado": "Ainda não pesquisado (sem edital analisado)",
    "nao_aplicavel": "Comprovadamente não aplicável",
    "nao_mapeado": "Sem campo correspondente no modelo",
}

# Dimensões que descrevem disponibilidade documental (não campos extraídos).
_DOC_DIMENSIONS = (
    {"key": "edital_oficial", "label": "Edital oficial localizado", "group": "documento",
     "required": True},
    {"key": "retificacao", "label": "Retificação localizada", "group": "documento",
     "required": False},
)

# Dimensões de campo. ``fields`` usa os nomes reais gravados por ``document_fields`` e afins.
_FIELD_DIMENSIONS = (
    {"key": "cargos", "label": "Cargos identificados", "group": "estrutura",
     "fields": (), "required": True},
    {"key": "vagas_imediatas", "label": "Vagas imediatas", "group": "vagas",
     "fields": ("immediate_vacancies",), "required": True},
    {"key": "vagas_reserva", "label": "Cadastro de reserva", "group": "vagas",
     "fields": ("reserve_vacancies",), "required": False},
    {"key": "vagas_indigenas", "label": "Vagas indígenas imediatas", "group": "vagas",
     "fields": ("indigenous_vacancies",), "required": True},
    {"key": "vagas_indigenas_reserva", "label": "Vagas indígenas em reserva", "group": "vagas",
     "fields": ("indigenous_reserve_vacancies",), "required": False},
    {"key": "escolaridade", "label": "Escolaridade", "group": "requisitos",
     "fields": ("education",), "required": True},
    {"key": "cursos_aceitos", "label": "Cursos aceitos", "group": "requisitos",
     "fields": ("accepted_courses",), "required": False},
    {"key": "compatibilidade_si", "label": "Compatibilidade com Sistemas de Informação",
     "group": "requisitos", "fields": ("si_compatibility",), "required": True},
    {"key": "local_prova", "label": "Local de prova", "group": "localizacao",
     "fields": ("exam_location", "exam_municipio", "exam_uf"), "required": True},
    {"key": "lotacao", "label": "Local de lotação", "group": "localizacao",
     "fields": ("work_location",), "required": False},
    {"key": "prazo_inscricao", "label": "Prazo de inscrição", "group": "prazos",
     "fields": ("registration_start", "registration_end"), "required": True},
    {"key": "prazo_isencao", "label": "Prazo de isenção", "group": "prazos",
     "fields": ("exemption_start", "exemption_end"), "required": False},
    {"key": "resultado_isencao", "label": "Resultado da isenção", "group": "prazos",
     "fields": ("exemption_result_preliminary", "exemption_result_final", "exemption_appeal"),
     "required": False},
    {"key": "conteudo_programatico", "label": "Conteúdo programático", "group": "conteudo",
     "fields": ("conteudo_secao", "conteudo_disciplina", "conteudo_topico",
                "conteudo_subtopico"), "required": False},
)

# Dimensões ausentes do modelo atual, declaradas explicitamente.
_UNMAPPED_DIMENSIONS = (
    {"key": "prazo_pagamento", "label": "Prazo de pagamento", "group": "prazos",
     "motivo": "o pipeline não grava prazo de pagamento; ausência aqui não prova ausência no edital"},
)

# Causas de insuficiência, em ordem de precedência (a primeira que casar vence).
CAUSE_LABELS = {
    "confirmado": "Dados confirmados por revisão humana",
    "sem_documento": "Nenhum documento localizado para o concurso",
    "apenas_agregador": "Somente páginas de agregador/notícia; sem edital oficial",
    "documento_oficial_sem_edital": "Documento oficial localizado, mas nenhum classificado como edital",
    "edital_sem_processamento": "Edital localizado, ainda não processado",
    "falha_extracao": "Falha técnica de extração do edital",
    "edital_sem_campos": "Edital processado, nenhum campo reconhecido",
    "extraido_ambiguo": "Campos extraídos, todos ambíguos (revisão humana pendente)",
    "extraido_parcial": "Campos extraídos sem ambiguidade, revisão humana pendente",
    "inconclusivo": "Diagnóstico inconclusivo com os dados atuais",
}

# Ação recomendada por causa: distingue coleta automática de trabalho humano.
CAUSE_ACTIONS = {
    "confirmado": "nenhuma",
    "sem_documento": "coletar_documento_oficial",
    "apenas_agregador": "coletar_documento_oficial",
    "documento_oficial_sem_edital": "coletar_documento_oficial",
    "edital_sem_processamento": "processar_documento",
    "falha_extracao": "investigar_falha",
    "edital_sem_campos": "investigar_falha",
    "extraido_ambiguo": "revisar_proposta",
    "extraido_parcial": "revisar_proposta",
    "inconclusivo": "investigar_falha",
}

ACTION_LABELS = {
    "nenhuma": "Nenhuma ação necessária",
    "coletar_documento_oficial": "Buscar o edital oficial na fonte do órgão/banca",
    "processar_documento": "Processar o documento já baixado",
    "revisar_proposta": "Revisão humana das propostas",
    "reconciliar_cargo": "Reconciliar rótulo de cargo com identidade canônica",
    "investigar_falha": "Investigar falha de extração/associação",
}

_ACTION_KIND = {
    "nenhuma": "nenhuma",
    "coletar_documento_oficial": "coleta",
    "processar_documento": "coleta",
    "revisar_proposta": "revisao_humana",
    "reconciliar_cargo": "revisao_humana",
    "investigar_falha": "tecnica",
}

# Hosts de agregador/notícia: nunca são prova oficial de vaga, requisito ou prazo.
_AGGREGATOR_HOSTS = ("pciconcursos.com.br", "pciconcursos.com")

_EDITAL_KINDS = ("edital",)
_EDITAL_TIPOS = ("edital_abertura", "edital_retificado")
_RETIFICACAO_KINDS = ("retificacao",)
_RETIFICACAO_TIPOS = ("retificacao",)
_ANALYZED = ("parcial", "concluida")

_DECISIVE_FIELDS = ("si_compatibility", "indigenous_vacancies", "exam_location", "work_location")


def _now():
    return datetime.now(timezone.utc)


def _pct(part, total):
    if not total:
        return None
    return round(100.0 * part / total, 1)


def _parse_date(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _is_aggregator(url):
    """True quando o documento vem de agregador/notícia conhecido (não é prova oficial)."""
    if not isinstance(url, str):
        return False
    host = url.split("//", 1)[-1].split("/", 1)[0].lower()
    return any(host == known or host.endswith("." + known) for known in _AGGREGATOR_HOSTS)


def _is_edital(kind, tipo):
    return kind in _EDITAL_KINDS or tipo in _EDITAL_TIPOS


def _is_retificacao(kind, tipo):
    return kind in _RETIFICACAO_KINDS or tipo in _RETIFICACAO_TIPOS


class _Snapshot:
    """Leitura única e consistente do banco para a auditoria (sem N+1)."""

    def __init__(self, db_path):
        self.db_path = db_path
        with closing(connect_documents(db_path)) as conn:
            if not is_readable_schema(conn):
                raise ValueError("migração documental pendente")
            self.contests = [row[0] for row in conn.execute(
                "SELECT id FROM concursos_identidade ORDER BY created_at, id")]
            self.documents = {}
            for contest_id, doc_id, kind, tipo, url in conn.execute(
                    "SELECT contest_id, id, kind, tipo_documental, official_url FROM documentos"):
                self.documents.setdefault(contest_id, []).append(
                    {"id": doc_id, "kind": kind, "tipo": tipo, "url": url,
                     "edital": _is_edital(kind, tipo),
                     "retificacao": _is_retificacao(kind, tipo),
                     "agregador": _is_aggregator(url)})
            self.versions = {}
            for contest_id, state, error in conn.execute(
                    "SELECT d.contest_id, v.extraction_state, v.error_code "
                    "FROM versoes_documento v JOIN documentos d ON d.id=v.document_id"):
                self.versions.setdefault(contest_id, []).append(
                    {"state": state, "error": error})
            self.roles = {}
            for contest_id, count in conn.execute(
                    "SELECT contest_id, COUNT(*) FROM cargos_identidade GROUP BY contest_id"):
                self.roles[contest_id] = count
            self.reconciliations = {}
            for contest_id, count in conn.execute(
                    "SELECT contest_id, COUNT(*) FROM reconciliacoes_cargo GROUP BY contest_id"):
                self.reconciliations[contest_id] = count
            self.audits = {}
            for contest_id, state, checked_at in conn.execute(
                    "SELECT contest_id, state, checked_at FROM auditorias_cobertura "
                    "ORDER BY checked_at, id"):
                self.audits[contest_id] = {"state": state, "checked_at": checked_at}
            self.queue = {}
            for contest_id, state in conn.execute(
                    "SELECT o.contest_id, f.state FROM fila_confirmacao f "
                    "JOIN observacoes_concurso o ON o.id=f.observation_id"):
                self.queue[contest_id] = state
            self.proposals = {}
            for item in proposal_rows(conn):
                self.proposals.setdefault(item["contest_id"], []).append(item)
            self.sources = [dict(zip(("source_url", "state", "http_status",
                                      "documents_found", "documents_new", "checked_at"), row))
                            for row in conn.execute(
                "SELECT source_url, state, http_status, documents_found, documents_new, "
                "checked_at FROM ciclos_fontes ORDER BY checked_at, id")]

    # --- fatos por concurso -------------------------------------------------

    def facts(self, contest_id):
        docs = self.documents.get(contest_id, [])
        versions = self.versions.get(contest_id, [])
        props = self.proposals.get(contest_id, [])
        editais = [d for d in docs if d["edital"]]
        analyzed = [v for v in versions if v["state"] in _ANALYZED]
        failed = [v for v in versions if v["state"] == "falhou"]
        return {
            "contest_id": contest_id,
            "documentos": len(docs),
            "editais": len(editais),
            "retificacoes": sum(1 for d in docs if d["retificacao"]),
            "documentos_agregador": sum(1 for d in docs if d["agregador"]),
            "documentos_oficiais_sem_edital": sum(
                1 for d in docs if not d["edital"] and not d["agregador"]),
            "versoes": len(versions),
            "versoes_analisadas": len(analyzed),
            "versoes_falhas": len(failed),
            "propostas": len(props),
            "cargos": self.roles.get(contest_id, 0),
            "reconciliacoes": self.reconciliations.get(contest_id, 0),
            "auditoria_humana": self.audits.get(contest_id),
            "fila": self.queue.get(contest_id),
            "rotulos_cargo": sorted({label_from_ambiguity(p["ambiguity_reason"])
                                     for p in props
                                     if label_from_ambiguity(p["ambiguity_reason"])}),
            "tem_edital_analisado": bool(editais) and bool(analyzed),
        }


def _field_state(proposals):
    """Estado de um conjunto de propostas da mesma dimensão (vocabulário existente).

    - ``rejeitado`` pela revisão humana não conta como dado;
    - conflito só existe quando o **mesmo campo** tem valores divergentes (dimensões como
      ``local_prova`` agregam município e UF, que são complementares, não conflitantes).
    """
    active = [p for p in proposals if p["state"] != "rejeitado"]
    if not active:
        if proposals:
            return "nao_localizado", "todas as propostas foram rejeitadas na revisão"
        return "nao_localizado", None
    decisions = {p["state"] for p in active}
    if "validado" in decisions:
        return "confirmado", None
    if "ambiguo" in decisions:
        return "ambiguo", next(p["ambiguity_reason"] for p in active
                               if p["state"] == "ambiguo")
    for field in {p["field_name"] for p in active}:
        values = {json.dumps(p["value"], sort_keys=True, ensure_ascii=False)
                  for p in active if p["field_name"] == field}
        if len(values) > 1:
            return "em_conflito", f"valores divergentes para {field}"
    return "proposto", None


def _dimension_state(snapshot, facts, dimension):
    """Estado de uma dimensão para um concurso, com denominador aplicado depois."""
    key = dimension["key"]
    if key == "edital_oficial":
        if facts["editais"]:
            return "confirmado", None
        if facts["documentos"]:
            return "nao_localizado", "apenas documentos não classificados como edital"
        return "nao_pesquisado", None
    if key == "retificacao":
        if facts["retificacoes"]:
            return "confirmado", None
        if not facts["editais"]:
            return "nao_pesquisado", None
        return "nao_localizado", None
    if key == "cargos":
        # Identidade de cargo criada a partir do rótulo NÃO é confirmação: só a decisão
        # humana de reconciliação (`reconciliacoes_cargo`) confirma o cargo.
        if facts["reconciliacoes"]:
            return "confirmado", None
        if facts["cargos"]:
            return "proposto", ("identidade criada a partir do rótulo do documento, "
                                "sem decisão humana de reconciliação")
        if facts["rotulos_cargo"]:
            return "ambiguo", "rótulo de cargo evidenciado, sem identidade canônica"
        if not facts["editais"]:
            return "nao_pesquisado", None
        if not facts["tem_edital_analisado"]:
            return "nao_pesquisado", None
        return "nao_localizado", None
    if not facts["editais"]:
        return "nao_pesquisado", None
    if facts["versoes_falhas"] and not facts["versoes_analisadas"]:
        return "falha_extracao", None
    if not facts["versoes_analisadas"]:
        return "nao_pesquisado", None
    props = snapshot.proposals.get(facts["contest_id"], [])
    selected = [p for p in props if p["field_name"] in dimension["fields"]]
    return _field_state(selected)


def audit(db_path, *, now=None) -> dict:
    """Auditoria completa: funil, dimensões, causas e recortes. Somente leitura."""
    now_dt = datetime.fromisoformat(now) if isinstance(now, str) else (now or _now())
    snapshot = _Snapshot(db_path)
    contests = snapshot.contests
    facts = {cid: snapshot.facts(cid) for cid in contests}

    # --- funil --------------------------------------------------------------
    com_documento = [c for c in contests if facts[c]["documentos"]]
    com_edital = [c for c in contests if facts[c]["editais"]]
    com_edital_analisado = [c for c in contests if facts[c]["tem_edital_analisado"]]
    com_propostas = [c for c in contests if facts[c]["propostas"]]
    funil = [
        {"etapa": "concursos", "quantidade": len(contests), "de": len(contests)},
        {"etapa": "com_documento", "quantidade": len(com_documento), "de": len(contests)},
        {"etapa": "com_edital_oficial", "quantidade": len(com_edital), "de": len(contests)},
        {"etapa": "com_edital_analisado", "quantidade": len(com_edital_analisado),
         "de": len(contests)},
        {"etapa": "com_propostas", "quantidade": len(com_propostas), "de": len(contests)},
        {"etapa": "com_campo_confirmado", "quantidade": sum(
            1 for c in contests if any(p["state"] == "validado"
                                       for p in snapshot.proposals.get(c, []))),
         "de": len(contests)},
    ]

    # --- dimensões ----------------------------------------------------------
    dimensions = []
    for dimension in _DOC_DIMENSIONS:
        dimensions.append(_aggregate_dimension(snapshot, facts, dimension, contests,
                                               universo=len(contests),
                                               escopo="todos os concursos"))
    for dimension in _FIELD_DIMENSIONS:
        dimensions.append(_aggregate_dimension(snapshot, facts, dimension,
                                               contests=com_edital,
                                               universo=len(contests),
                                               escopo="concursos com edital oficial"))
    for dimension in _UNMAPPED_DIMENSIONS:
        dimensions.append({
            "key": dimension["key"], "label": dimension["label"],
            "group": dimension["group"], "required": False, "escopo": "não medido",
            "universo": len(contests), "denominador": 0,
            "fora_do_denominador": len(contests),
            "estados": {"nao_mapeado": len(contests)},
            "pct_confirmado": None, "pct_com_dado": None,
            "observacao": dimension["motivo"],
        })

    # --- causas -------------------------------------------------------------
    # Dimensões obrigatórias pendentes por concurso: impede declarar "confirmado" quando
    # um único campo foi validado mas o resto continua faltando.
    mandatory = [d for d in (_DOC_DIMENSIONS + _FIELD_DIMENSIONS) if d["required"]]
    pendencias = {}
    for contest_id in contests:
        pendencias[contest_id] = [
            dimension["key"] for dimension in mandatory
            if _dimension_state(snapshot, facts[contest_id], dimension)[0] != "confirmado"]

    causes = {}
    per_contest = []
    for contest_id in contests:
        cause, evidence = classify_cause(facts[contest_id],
                                         snapshot.proposals.get(contest_id, []),
                                         pendencias=pendencias[contest_id])
        causes[cause] = causes.get(cause, 0) + 1
        per_contest.append({"contest_id": contest_id, "causa": cause,
                            "causa_label": CAUSE_LABELS[cause],
                            "acao": CAUSE_ACTIONS[cause],
                            "evidencias": evidence})

    # --- recortes -----------------------------------------------------------
    by_queue = {}
    for contest_id in contests:
        state = facts[contest_id]["fila"] or "sem_registro"
        by_queue[state] = by_queue.get(state, 0) + 1

    sources = {}
    for row in snapshot.sources:
        entry = sources.setdefault(row["source_url"], {
            "source_url": row["source_url"], "ciclos": 0, "documentos_encontrados": 0,
            "documentos_novos": 0, "falhas": 0, "ultimo_estado": None,
            "ultima_verificacao": None})
        entry["ciclos"] += 1
        entry["documentos_encontrados"] += int(row["documents_found"] or 0)
        entry["documentos_novos"] += int(row["documents_new"] or 0)
        if row["state"] in ("falhou", "erro", "falha") or (
                row["http_status"] and int(row["http_status"]) >= 400):
            entry["falhas"] += 1
        entry["ultimo_estado"] = row["state"]
        entry["ultima_verificacao"] = row["checked_at"]

    limitations = [
        "Percentuais de campo usam como denominador apenas concursos com edital analisado; "
        "os demais aparecem como 'nao_pesquisado' e não entram na conta.",
        "Notícia de agregador não é tratada como prova oficial de vaga, requisito ou prazo.",
        "Prazo de pagamento não existe no modelo: aparece como 'nao_mapeado', não como ausente.",
        "Ausência de retificação não é defeito: retificação é opcional por natureza.",
        "A causa é a melhor explicação com os dados atuais; sem prova suficiente fica "
        "'inconclusivo'.",
    ]

    return {
        "version": AUDIT_VERSION,
        "generated_at": now_dt.isoformat(),
        "escopo": {
            "concursos": len(contests),
            "com_documento": len(com_documento),
            "com_edital_oficial": len(com_edital),
            "com_edital_analisado": len(com_edital_analisado),
            "com_propostas": len(com_propostas),
            "propostas": sum(f["propostas"] for f in facts.values()),
            "cargos_identidade": sum(f["cargos"] for f in facts.values()),
            "reconciliacoes_cargo": sum(f["reconciliacoes"] for f in facts.values()),
            "auditorias_humanas": len(snapshot.audits),
        },
        "funil": funil,
        "dimensoes": dimensions,
        "causas": {"distribuicao": causes, "por_concurso": per_contest},
        "recortes": {
            "por_estado_fila": by_queue,
            "por_fonte": sorted(sources.values(), key=lambda s: (-s["documentos_novos"],
                                                                s["source_url"])),
        },
        "limitacoes": limitations,
    }


def _aggregate_dimension(snapshot, facts, dimension, contests, *, universo, escopo):
    counts = {state: 0 for state in STATES}
    for contest_id in contests:
        state, _ = _dimension_state(snapshot, facts[contest_id], dimension)
        counts[state] += 1
    # Denominador = concursos efetivamente avaliados para esta dimensão. Quem ainda não foi
    # pesquisado fica de fora e é reportado à parte — nunca conta como zero.
    denominador = sum(counts[s] for s in STATES if s != "nao_pesquisado")
    confirmado = counts["confirmado"]
    com_dado = denominador - counts["nao_localizado"] - counts["falha_extracao"]
    required = bool(dimension["required"])
    entry = {
        "key": dimension["key"],
        "label": dimension["label"],
        "group": dimension["group"],
        "required": required,
        "escopo": escopo,
        "universo": universo,
        "denominador": denominador,
        "fora_do_denominador": max(0, universo - denominador),
        "estados": {k: v for k, v in counts.items() if v},
        # Dimensão opcional: ausência não é defeito, então não se publica percentual de
        # confirmação (evita transformar "não localizada" em falha).
        "pct_confirmado": _pct(confirmado, denominador) if required else None,
        "pct_com_dado": _pct(max(0, com_dado), denominador),
        "rotulos": {state: STATE_LABELS[state] for state in STATES if counts[state]},
    }
    if not required:
        entry["observacao"] = "dimensão opcional: ausência não é defeito"
    return entry


def classify_cause(facts, proposals, *, pendencias=()):
    """Causa provável da insuficiência, com as evidências que a sustentam.

    ``pendencias`` são as dimensões obrigatórias ainda não confirmadas: um concurso com um
    campo validado mas com dimensão obrigatória em falta **não** está confirmado.
    """
    evidence = []
    ambiguous = [p for p in proposals if p["state"] == "ambiguo"]
    validated = [p for p in proposals if p["state"] == "validado"]
    if validated:
        evidence.append(f"{len(validated)} campo(s) validado(s)")
        if ambiguous or pendencias:
            if ambiguous:
                evidence.append(f"{len(ambiguous)} proposta(s) ainda ambígua(s)")
            if pendencias:
                evidence.append("dimensão(ões) obrigatória(s) pendente(s): "
                                + ", ".join(sorted(pendencias)))
            return ("extraido_ambiguo" if ambiguous else "extraido_parcial"), evidence
        return "confirmado", evidence
    if not facts["documentos"]:
        evidence.append("nenhum documento registrado para o concurso")
        return "sem_documento", evidence
    if not facts["editais"]:
        evidence.append(f"{facts['documentos']} documento(s), nenhum classificado como edital")
        if facts["fila"]:
            evidence.append(f"fila de confirmação: {facts['fila']}")
        if facts["documentos_agregador"] == facts["documentos"]:
            return "apenas_agregador", evidence
        evidence.append(f"{facts['documentos_oficiais_sem_edital']} documento(s) de fonte "
                        "oficial não classificados como edital")
        return "documento_oficial_sem_edital", evidence
    evidence.append(f"{facts['editais']} edital(is)")
    if not facts["versoes_analisadas"]:
        if facts["versoes_falhas"]:
            evidence.append(f"{facts['versoes_falhas']} versão(ões) com falha de extração")
            return "falha_extracao", evidence
        evidence.append("edital sem versão analisada")
        return "edital_sem_processamento", evidence
    if facts["versoes_falhas"] and not facts["propostas"]:
        evidence.append(f"{facts['versoes_falhas']} versão(ões) com falha de extração")
        return "falha_extracao", evidence
    if not facts["propostas"]:
        evidence.append(f"{facts['versoes_analisadas']} versão(ões) analisada(s), 0 proposta")
        return "edital_sem_campos", evidence
    ambiguas = [p for p in proposals if p["state"] == "ambiguo"]
    evidence.append(f"{len(proposals)} proposta(s), {len(ambiguas)} ambígua(s)")
    if ambiguas and len(ambiguas) == len(proposals):
        if facts["rotulos_cargo"]:
            evidence.append(f"{len(facts['rotulos_cargo'])} rótulo(s) de cargo sem identidade")
        return "extraido_ambiguo", evidence
    if not ambiguas:
        return "extraido_parcial", evidence
    return "inconclusivo", evidence


def gaps(db_path, *, limit=50, now=None) -> dict:
    """Fila priorizada de lacunas, com critérios declarados e ação recomendada.

    Determinística: mesma base, mesmo ``now`` → mesma ordem. Não transforma campo ausente em
    prioridade absoluta; cada item explica por que entrou.
    """
    now_dt = datetime.fromisoformat(now) if isinstance(now, str) else (now or _now())
    today = now_dt.date()
    result = audit(db_path, now=now_dt)
    snapshot = _Snapshot(db_path)
    causes = {item["contest_id"]: item for item in result["causas"]["por_concurso"]}

    items = []
    for contest_id in snapshot.contests:
        facts = snapshot.facts(contest_id)
        cause = causes[contest_id]
        score = 0
        reasons = []

        if facts["tem_edital_analisado"]:
            score += 3
            reasons.append("edital analisado disponível (+3)")
        if facts["documentos"] and not facts["editais"]:
            score += 2
            reasons.append("tem documento, falta o edital (+2)")
        if cause["causa"] == "falha_extracao":
            score += 1
            reasons.append("falha de extração registrada (+1)")

        props = snapshot.proposals.get(contest_id, [])
        ambiguous = [p for p in props if p["state"] == "ambiguo"]
        if ambiguous:
            score += 2
            reasons.append(f"{len(ambiguous)} proposta(s) aguardando revisão (+2)")
        if facts["rotulos_cargo"] and not facts["cargos"]:
            score += 1
            reasons.append(f"{len(facts['rotulos_cargo'])} rótulo(s) sem identidade de cargo (+1)")

        deadlines = {}
        for field in ("registration_end", "exemption_end"):
            values = [p["value"] for p in props
                      if p["field_name"] == field and p["state"] != "ambiguo"]
            dates = [d for d in (_parse_date(v) for v in values) if d]
            if dates:
                deadlines[field] = min(dates)
        future = [d for d in deadlines.values() if d >= today]
        if future:
            days = min((d - today).days for d in future)
            if days <= 30:
                score += 2
                reasons.append(f"prazo confirmado em {days} dia(s) (+2)")
        elif facts["propostas"] and not deadlines:
            score += 2
            reasons.append("oportunidade sem prazo confirmado (+2)")

        missing = 0
        if facts["tem_edital_analisado"]:
            # Só faz sentido cobrar campo decisivo onde já houve extração: em concurso nunca
            # pesquisado a ausência é esperada e não é evidência de nada.
            for field in _DECISIVE_FIELDS:
                if not any(p["field_name"] == field for p in props):
                    missing += 1
        if missing:
            pontos = min(3, missing)
            score += pontos
            reasons.append(f"{missing} campo(s) decisivo(s) ausente(s) (+{pontos})")

        if cause["acao"] == "nenhuma":
            continue
        action = cause["acao"]
        if facts["rotulos_cargo"] and not facts["cargos"]:
            action = "reconciliar_cargo" if action == "revisar_proposta" else action

        items.append({
            "contest_id": contest_id,
            "prioridade": score,
            "causa": cause["causa"],
            "causa_label": cause["causa_label"],
            "acao": action,
            "acao_label": ACTION_LABELS[action],
            "tipo_tarefa": _ACTION_KIND[action],
            "motivos": reasons,
            "evidencias": cause["evidencias"],
            "documentos": facts["documentos"],
            "editais": facts["editais"],
            "propostas": facts["propostas"],
            "propostas_ambiguas": len(ambiguous),
            "rotulos_cargo": facts["rotulos_cargo"],
        })

    items.sort(key=lambda i: (-i["prioridade"], i["contest_id"]))
    return {"version": AUDIT_VERSION, "generated_at": now_dt.isoformat(),
            "total": len(items), "itens": items[:max(0, int(limit))]}


def summary(db_path, *, now=None) -> dict:
    """Versão compacta para a interface: números do topo + dimensões obrigatórias."""
    result = audit(db_path, now=now)
    required = [d for d in result["dimensoes"] if d["required"]]
    return {
        "version": result["version"],
        "generated_at": result["generated_at"],
        "escopo": result["escopo"],
        "funil": result["funil"],
        "causas": result["causas"]["distribuicao"],
        "dimensoes_obrigatorias": [
            {"key": d["key"], "label": d["label"], "denominador": d["denominador"],
             "pct_confirmado": d["pct_confirmado"], "pct_com_dado": d["pct_com_dado"],
             "estados": d["estados"]}
            for d in required
        ],
        "limitacoes": result["limitacoes"],
    }
