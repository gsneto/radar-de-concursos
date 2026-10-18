"""Aquisição controlada de editais oficiais (Fase 33).

Não é um coletor novo: usa o **conector já cadastrado** (Fase 29), a **política de
persistência** e o **orçamento** existentes. O objetivo é fechar lacunas documentais
identificadas pelo diagnóstico de cobertura, em lotes pequenos, com simulação, limite,
checkpoint e retomada.

Regras:

- só fonte ``habilitada`` e com persistência autorizada para ``documento``;
- só documentos do tipo edital/retificação (o que muda regra do certame), nunca listas de
  resultado com dados pessoais;
- a identidade já existe (observação do concurso); o documento é registrado nessa observação,
  sem associação por semelhança de título;
- download e extração têm limite por concurso e por execução, com consumo registrado;
- repetir a execução não duplica: URL já registrada é ignorada e versão já baixada não é
  baixada de novo.
"""

from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from radar import budget, source_policy
from radar import source_catalog as catalog
from radar.coverage_states import _host, _source_for, _source_map
from radar.document_store import connect_documents, is_readable_schema

ACQUISITION_VERSION = "acquisition_v1"

# Tipos que alteram regra do certame. Resultado/homologação/gabarito ficam de fora.
ACQUISITION_TYPES = ("edital_abertura", "edital_retificado", "retificacao")
TYPE_PRIORITY = {"edital_retificado": 0, "edital_abertura": 0, "retificacao": 1}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_observations(db_path):
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = conn.execute("""
            SELECT o.id, o.contest_id, o.source_url, o.competition_id, ci.estado_identidade
            FROM observacoes_concurso o JOIN concursos_identidade ci ON ci.id=o.contest_id
            ORDER BY o.observed_at""").fetchall()
        registered = {row[0] for row in conn.execute("SELECT official_url FROM documentos")}
    return [{"observation_id": row[0], "contest_id": row[1], "source_url": row[2],
             "competition_id": row[3], "estado_identidade": row[4]}
            for row in rows], registered


def _registered_urls(db_path):
    with closing(connect_documents(db_path)) as conn:
        return {row[0] for row in conn.execute("SELECT official_url FROM documentos")}


def _documented_contests(db_path):
    with closing(connect_documents(db_path)) as conn:
        return {row[0] for row in conn.execute(
            "SELECT DISTINCT contest_id FROM documentos WHERE contest_id IS NOT NULL")}


def targets(db_path, *, source_id=None, limit=50) -> dict:
    """Certames com fonte oficial conhecida e nenhum documento importado.

    A prioridade é **explicável e conservadora**: sem documento não há evidência de vagas
    indígenas, requisito de SI ou prazo. Por isso a ordem usa apenas (1) existência de fonte
    oficial habilitada com capacidade de edital, (2) recência da observação e (3) ausência
    total de documento. Nenhuma relevância temática é presumida.
    """
    pairs = _source_map()
    observations, _ = _load_observations(db_path)
    documented = _documented_contests(db_path)
    by_contest = {}
    for observation in observations:
        if observation["estado_identidade"] != "certame":
            continue
        if observation["contest_id"] in documented:
            continue
        source = _source_for(_host(observation["source_url"]), pairs)
        if source is None or source.get("nature") not in ("oficial", "institucional"):
            continue
        if source_id and source["id"] != source_id:
            continue
        entry = by_contest.setdefault(observation["contest_id"], {
            "contest_id": observation["contest_id"],
            "observation_id": observation["observation_id"],
            "competition_id": observation["competition_id"],
            "source_url": observation["source_url"],
            "source_id": source["id"], "source_status": source["status"],
            "source_nature": source["nature"],
            "documentos": 0})
        entry["documentos"] = 0
    items = []
    for entry in by_contest.values():
        source = catalog.get_source(entry["source_id"])
        can_fetch = source["status"] == "habilitada"
        capabilities = {"fgv-conhecimento": ("edital", "documento", "retificacao"),
                        "quadrix": ("edital", "documento", "retificacao"),
                        "ibfc": ("edital", "documento", "retificacao"),
                        "dou-secao-3": ("edital", "documento", "retificacao"),
                        "guajara": ("edital", "documento")}.get(entry["source_id"], ())
        reasons = []
        score = 0
        if can_fetch and "edital" in capabilities:
            score += 3
            reasons.append(f"fonte oficial habilitada com páginas de edital: {entry['source_id']}")
        elif source["nature"] in ("oficial", "institucional"):
            score += 1
            reasons.append(f"fonte oficial sem conector de edital: {entry['source_id']}")
        else:
            reasons.append(f"fonte não oficial: {entry['source_id']}")
        if entry["competition_id"]:
            score += 1
            reasons.append("identificador de certame na fonte disponível")
        reasons.append("nenhum documento localizado para o concurso")
        items.append(dict(entry, prioridade=score, motivos=reasons,
                          pode_adquirir=bool(can_fetch and "edital" in capabilities)))
    items.sort(key=lambda item: (-item["prioridade"], item["contest_id"]))
    return {"version": ACQUISITION_VERSION, "total": len(items),
            "adquiriveis": sum(1 for item in items if item["pode_adquirir"]),
            "itens": items[:max(0, int(limit))],
            "limitacao": ("Sem documento não há evidência temática (vagas indígenas, SI, "
                          "prazos); a prioridade não presume relevância.")}


def _fgv_plan(observation, *, limit):
    """Plano FGV: página de detalhe do concurso → documentos de edital/retificação."""
    from radar import fgv_source

    slug = observation["competition_id"] or ""
    if not slug or not all(ch.isalnum() or ch in "._-" for ch in slug):
        raise ValueError("identificador de concurso FGV inválido")
    html = fgv_source.fetch_detail(slug)
    detail = fgv_source.parse_detail(html)
    entry = {"slug": slug, "url": observation["source_url"],
             "title": detail.get("title") or slug}
    documents = []
    from radar.document_types import is_nominal_title

    skipped_nominal = []
    for document in detail.get("documents") or []:
        doc_type = document.get("document_type") or fgv_source.document_type(
            document.get("title") or "")
        if doc_type not in ACQUISITION_TYPES:
            continue
        if is_nominal_title(document.get("title")):
            # Lista nominal (nomes/notas de candidatos) não é regra do certame: não se
            # adquire, mesmo quando a banca a rotula como "Retificação".
            skipped_nominal.append({"title": document.get("title"),
                                    "document_type": doc_type})
            continue
        candidate = fgv_source.to_candidate(document, entry, observation["observation_id"],
                                            _now())
        candidate["kind"] = "edital" if doc_type != "retificacao" else "retificacao"
        documents.append({"candidate": candidate, "document_type": doc_type,
                          "title": document.get("title"),
                          "published_at": document.get("date"),
                          "url": candidate["official_url"]})
    documents.sort(key=lambda item: (TYPE_PRIORITY.get(item["document_type"], 2),
                                     item["published_at"] or ""))
    return {"title": detail.get("title"), "status": detail.get("status"),
            "documents": documents[:max(1, int(limit))],
            "documents_available": len(documents),
            "nominais_ignorados": skipped_nominal}


ADAPTERS = {"fgv-conhecimento": _fgv_plan}

# Tetos operacionais: nenhuma execução abre milhares de requisições.
MAX_CONTESTS_CAP = 50
MAX_DOCUMENTS_CAP = 20


def _limits(max_contests, max_documents_per_contest) -> tuple[int, int]:
    """Valida limites explícitos: inteiro >= 1 e abaixo do teto operacional."""
    checked = []
    for name, value, cap in (("max_contests", max_contests, MAX_CONTESTS_CAP),
                             ("max_documents_per_contest", max_documents_per_contest,
                              MAX_DOCUMENTS_CAP)):
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError(f"{name} precisa ser inteiro >= 1")
        if value > cap:
            raise ValueError(f"{name} acima do teto operacional ({cap})")
        checked.append(int(value))
    return checked[0], checked[1]


def _checkpoint_path(path_value):
    if not path_value:
        return None
    path = Path(path_value)
    return path if path.exists() else None


def _load_checkpoint(path_value, *, source_id, contest_ids):
    """Checkpoint só é aceito para a mesma fonte e a mesma seleção de concursos."""
    path = _checkpoint_path(path_value)
    if path is None:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if payload.get("source_id") != source_id:
        raise ValueError("checkpoint pertence a outra fonte")
    selection = sorted(contest_ids) if contest_ids else None
    if payload.get("contest_ids") != selection:
        raise ValueError("checkpoint pertence a outra seleção de concursos")
    return payload


def _resolve_observations(db_path, contest_ids):
    observations, _ = _load_observations(db_path)
    if contest_ids:
        wanted = set(contest_ids)
        observations = [item for item in observations if item["contest_id"] in wanted]
    return observations


def plan_acquisition(db_path, *, source_id="fgv-conhecimento", contest_ids=None,
                     max_contests=3, max_documents_per_contest=3,
                     budget_run=None, skip_contest_ids=None) -> dict:
    """Simula a aquisição: o que seria registrado/baixado, sem gravar nada.

    A simulação **consulta a página de detalhe** da fonte (é o único jeito de saber quais
    documentos existem), então faz rede. Quando ``budget_run`` é informado, cada consulta é
    contabilizada no orçamento da execução; sem ele, a chamada é avulsa e fica registrada
    como tal no relatório.
    """
    if source_id not in ADAPTERS:
        raise ValueError(f"fonte sem adaptador de aquisição: {source_id}")
    max_contests, max_documents_per_contest = _limits(max_contests, max_documents_per_contest)
    source = catalog.get_source(source_id)
    if source["status"] != "habilitada":
        raise ValueError(f"fonte não habilitada: {source['status']}")
    policy = source_policy.decision(source_id, "documento")
    if not policy["allowed"]:
        raise ValueError(f"persistência não autorizada: {policy['reason']}")
    from radar.document_discovery import allowed_document_url

    pairs = _source_map()
    observations = _resolve_observations(db_path, contest_ids)
    observations = [item for item in observations
                    if (_source_for(_host(item["source_url"]), pairs) or {}).get("id")
                    == source_id]
    if contest_ids is None:
        # Sem seleção explícita, usa os alvos priorizados e só os adquiríveis.
        target_ids = [item["contest_id"] for item in targets(
            db_path, source_id=source_id, limit=max_contests)["itens"]
            if item["pode_adquirir"]]
        observations = [item for item in observations if item["contest_id"] in target_ids]
    if skip_contest_ids:
        # Retomada: concursos já planejados no checkpoint não são reconsultados.
        skip = set(skip_contest_ids)
        observations = [item for item in observations if item["contest_id"] not in skip]
    observations = observations[:max_contests]
    registered = _registered_urls(db_path)
    planned, failures = [], []
    for observation in observations:
        if budget_run:
            budget.check_call(db_path, budget_run, estimated_items=1)
        try:
            plan = ADAPTERS[source_id](observation,
                                       limit=max_documents_per_contest)
        except Exception as error:  # falha de rede/parse não interrompe o plano
            if budget_run:
                budget.record_call(db_path, budget_run, items=0, success=False)
            failures.append({"contest_id": observation["contest_id"],
                             "code": getattr(error, "code", type(error).__name__),
                             "message": str(error)[:200]})
            continue
        if budget_run:
            budget.record_call(db_path, budget_run, items=1, success=True)
        new_documents = []
        for document in plan["documents"]:
            if document["url"] in registered:
                continue
            if not allowed_document_url(document["url"]):
                # URL fora da allowlist de documentos: não se planeja o que não se pode buscar.
                failures.append({"contest_id": observation["contest_id"],
                                 "code": "host_nao_autorizado",
                                 "message": document["url"][:200]})
                continue
            new_documents.append(document)
        planned.append({"contest_id": observation["contest_id"],
                        "observation_id": observation["observation_id"],
                        "title": plan.get("title"),
                        "source_status": plan.get("status"),
                        "documentos_encontrados": plan["documents_available"],
                        "documentos_novos": len(new_documents),
                        "documentos": new_documents,
                        "nominais_ignorados": plan.get("nominais_ignorados", [])})
    return {"version": ACQUISITION_VERSION, "dry_run": True, "source_id": source_id,
            "concursos": len(planned),
            "documentos_planejados": sum(item["documentos_novos"] for item in planned),
            "chamadas_previstas": len(planned) + sum(
                item["documentos_novos"] for item in planned),
            "custo_estimado": 0.0, "moeda": "BRL",
            "itens": planned, "falhas": failures,
            "limitacao": ("Simulação: nenhuma gravação, nenhum download de documento. A "
                          "consulta da página de detalhe é feita para descobrir os documentos "
                          "reais e é contabilizada no orçamento quando há execução aberta.")}


def _write_checkpoint(path_value, payload):
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def execute_acquisition(db_path, *, source_id="fgv-conhecimento", contest_ids=None,
                        max_contests=3, max_documents_per_contest=3, analyze=True,
                        checkpoint=None, apply=False, now=None) -> dict:
    """Executa (ou simula) a aquisição limitada, com orçamento e checkpoint.

    ``now`` existe para execução determinística (teste/retomada); em uso normal é omitido e
    vale o relógio real, que também aplica o intervalo mínimo entre execuções da fonte.
    """
    max_contests, max_documents_per_contest = _limits(max_contests,
                                                      max_documents_per_contest)
    if not apply:
        return plan_acquisition(db_path, source_id=source_id, contest_ids=contest_ids,
                                max_contests=max_contests,
                                max_documents_per_contest=max_documents_per_contest)
    resume = _load_checkpoint(checkpoint, source_id=source_id, contest_ids=contest_ids)
    start_index = int((resume or {}).get("next_index") or 0)
    from radar import pipeline
    from radar.document_download import DownloadError, download_document
    from radar.document_store import register_document

    # A execução abre **antes** do plano: a consulta de detalhe também é uma chamada.
    run = budget.open_run(db_path, source_id,
                          overrides={"max_calls": max(4, max_contests * 3 + 4)},
                          now=now)
    run_id = run["run_id"]
    registered, downloaded, analyzed, failures = [], [], [], []
    plan = {"itens": [], "falhas": []}
    status = "falhou"
    try:
        # Retomada: reaproveita o plano já gravado para os concursos concluídos.
        resumed_items = list((resume or {}).get("itens") or [])[:start_index]
        resumed_ids = [item["contest_id"] for item in resumed_items]
        rest = plan_acquisition(db_path, source_id=source_id, contest_ids=contest_ids,
                                max_contests=max_contests,
                                max_documents_per_contest=max_documents_per_contest,
                                budget_run=run_id, skip_contest_ids=resumed_ids)
        plan = {"itens": resumed_items + rest["itens"], "falhas": rest["falhas"]}
        for index, item in enumerate(plan["itens"]):
            if index < start_index:
                continue
            if item["documentos_novos"] == 0:
                continue
            contest_versions = []
            for document in item["documentos"]:
                try:
                    budget.check_call(db_path, run_id, estimated_items=1)
                    document_id = register_document(db_path, document["candidate"])
                    budget.record_call(db_path, run_id, items=0, success=True)
                    registered.append({"contest_id": item["contest_id"],
                                       "document_id": document_id,
                                       "title": document["title"],
                                       "document_type": document["document_type"]})
                except budget.BudgetError:
                    raise
                except Exception as error:
                    failures.append({"contest_id": item["contest_id"],
                                     "stage": "registro", "title": document["title"],
                                     "code": getattr(error, "code", type(error).__name__),
                                     "message": str(error)[:200]})
                    continue
                with closing(connect_documents(db_path)) as conn:
                    has_version = conn.execute(
                        "SELECT COUNT(*) FROM versoes_documento WHERE document_id=?",
                        (document_id,)).fetchone()[0]
                if has_version:
                    continue
                try:
                    budget.check_call(db_path, run_id, estimated_items=1)
                    version_id = download_document(db_path, document_id, attempts=1)
                    budget.record_call(db_path, run_id, items=1, success=True)
                    downloaded.append({"contest_id": item["contest_id"],
                                       "document_id": document_id,
                                       "version_id": version_id,
                                       "title": document["title"]})
                    contest_versions.append(version_id)
                except budget.BudgetError:
                    raise
                except DownloadError as error:
                    budget.record_call(db_path, run_id, items=0, success=False)
                    failures.append({"contest_id": item["contest_id"],
                                     "stage": "download", "title": document["title"],
                                     "code": error.code,
                                     "message": str(error)[:200]})
                except Exception as error:
                    budget.record_call(db_path, run_id, items=0, success=False)
                    failures.append({"contest_id": item["contest_id"],
                                     "stage": "download", "title": document["title"],
                                     "code": type(error).__name__,
                                     "message": str(error)[:200]})
            if analyze and contest_versions:
                result = pipeline.analyze_versions(db_path, contest_versions, dry_run=False)
                analyzed.append({"contest_id": item["contest_id"],
                                 "extraidas": result.get("extraidas", 0),
                                 "falhas": result.get("falhas", [])})
            _save_progress(db_path, run_id, checkpoint, source_id, contest_ids,
                           index + 1, len(registered), len(downloaded), plan["itens"])
        status = "concluida" if not failures else "parcial"
    except budget.BudgetError as error:
        status = "interrompida"
        _save_progress(db_path, run_id, checkpoint, source_id, contest_ids,
                       start_index, len(registered), len(downloaded),
                       plan.get("itens") or [])
        raise
    finally:
        # Nunca deixa execução presa em "em_andamento", mesmo com exceção inesperada.
        try:
            budget.finish_run(db_path, run_id, status=status,
                              notes=f"{len(registered)} registrados, "
                                    f"{len(downloaded)} baixados")
        except budget.BudgetError:
            pass
    if not plan["itens"]:
        return dict(plan, dry_run=False, executado=False,
                    documentos_registrados=0, documentos_baixados=0,
                    versoes_analisadas=0, registrados=[], baixados=[], analises=[],
                    consumo=budget.usage(db_path, run_id), motivo="nada a adquirir")
    return {"version": ACQUISITION_VERSION, "dry_run": False, "executado": True,
            "source_id": source_id, "run_id": run_id,
            "concursos": len(plan["itens"]),
            "documentos_registrados": len(registered),
            "documentos_baixados": len(downloaded),
            "versoes_analisadas": sum(item["extraidas"] for item in analyzed),
            "registrados": registered, "baixados": downloaded,
            "analises": analyzed, "falhas": failures,
            "retomado_de": start_index if start_index else None,
            "consumo": budget.usage(db_path, run_id)}


def _save_progress(db_path, run_id, checkpoint, source_id, contest_ids, next_index,
                   registered, downloaded, itens=None) -> None:
    """Grava progresso no banco e, se pedido, no arquivo de checkpoint (com a seleção)."""
    budget.save_checkpoint(db_path, run_id, {"next_index": next_index,
                                             "registered": registered,
                                             "downloaded": downloaded,
                                             "updated_at": _now()})
    if not checkpoint:
        return
    _write_checkpoint(checkpoint, {
        "source_id": source_id,
        "contest_ids": sorted(contest_ids) if contest_ids else None,
        "next_index": next_index,
        "registered": registered,
        "downloaded": downloaded,
        "itens": itens or [],
        "updated_at": _now()})
