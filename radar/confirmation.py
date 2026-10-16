"""Fila persistente de confirmação documental e reconciliação multifonte.

Transforma candidatos descobertos (ex.: PCI) em oportunidades rastreáveis: uma
fila retomável e incremental que procura referências oficiais, registra documentos
com proveniência e mantém a descoberta separada da confirmação. Nada é promovido a
valor validado sem revisão humana.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from radar.document_store import connect_documents, register_document

# Vocabulário de estados da confirmação (ver spec da Fase 11).
QUEUE_STATES = (
    "pendente", "em_processamento", "fonte_oficial_localizada", "documento_localizado",
    "documento_registrado", "documento_processado", "revisao_pendente",
    "confirmacao_parcial", "nao_localizado", "inconclusivo", "falhou", "concluido",
)
# Estados finais que podem ser reprocessados após o intervalo de retentativa.
RETRYABLE_STATES = ("falhou", "nao_localizado", "inconclusivo", "documento_localizado",
                    "fonte_oficial_localizada")
DEFAULT_BATCH_LIMIT = 10
DEFAULT_STALE_MINUTES = 60
RETRY_BACKOFF_MINUTES = 60

_TI_TOKENS = ("analista de sistemas", "tecnico em informatica", "tecnologia da informacao",
              "sistemas de informacao", "desenvolvimento de sistemas", "ciencia da computacao")
_INDIGENA_TOKENS = ("indigena", "indigenas")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None


def normalize(text) -> str:
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", ascii_text.lower()).split())


def classify_official(title: str) -> str:
    norm = normalize(title)
    if re.match(r"^\s*\d*\s*[ao]?\s*retifica", norm) or ("retifica" in norm and "edital" not in norm):
        return "retificacao"
    if "edital" in norm:
        return "edital"
    return "outro"


def compute_priority(candidate: dict) -> tuple[int, str]:
    """Ordenação transparente (maior = antes). Não exclui; apenas prioriza."""
    score = 0
    reasons = []
    cargos = normalize(candidate.get("cargos_resumo") or "")
    title = normalize(candidate.get("title") or "")
    text = f"{cargos} {title}"
    if any(token in text for token in _TI_TOKENS):
        score += 50
        reasons.append("cargo_ti")
    if any(token in text for token in _INDIGENA_TOKENS):
        score += 20
        reasons.append("mencao_indigena")
    if candidate.get("aberto") is True:
        score += 10
        reasons.append("inscricoes_abertas_pci")
    dias = candidate.get("dias_restantes")
    if isinstance(dias, int) and dias <= 15:
        score += 10
        reasons.append("prazo_proximo_pci")
    if candidate.get("url"):
        score += 5
        reasons.append("referencia_pronta")
    return score, ",".join(reasons) if reasons else "neutro"


def _insert_queue_row(conn, observation_id, source_id, competition_id, candidate, now):
    score, reason = compute_priority(candidate or {})
    conn.execute(
        """INSERT OR IGNORE INTO fila_confirmacao
        (observation_id, source_id, competition_id, state, attempts, priority_score,
         priority_reason, result_json, history_json, updated_at)
        VALUES (?,?,?,?,0,?,?,?,?,?)""",
        (observation_id, source_id, competition_id, "pendente", score, reason,
         json.dumps({"candidate": candidate}, ensure_ascii=False), json.dumps([]), now))


def _candidate_meta(candidate: dict) -> dict:
    """Metadados do candidato para prioridade/resolução (aceita documento ou meta)."""
    meta = dict(candidate.get("pci_meta") or {})
    for key in ("competition_id", "title", "url", "uf", "regiao", "cargos_resumo",
                "vagas_salario", "formacao", "data_inicio", "data_fim", "aberto",
                "dias_restantes", "query"):
        if meta.get(key) is None and candidate.get(key) is not None:
            meta[key] = candidate[key]
    meta.setdefault("title", candidate.get("title"))
    meta.setdefault("url", candidate.get("official_url"))
    if not meta.get("competition_id"):
        meta["competition_id"] = candidate.get("source_identifier")
    return meta


def enqueue_from_candidates(db_path, candidates, *, source_id: str = "pci", now=None) -> int:
    """Enfileira candidatos (com metadados) ainda não presentes na fila."""
    now = now or _now()
    created = 0
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        for candidate in candidates:
            observation_id = candidate.get("observation_id")
            meta = _candidate_meta(candidate)
            competition_id = meta.get("competition_id")
            if not observation_id or not competition_id:
                continue
            if not conn.execute("SELECT 1 FROM observacoes_concurso WHERE id=?",
                                (observation_id,)).fetchone():
                continue
            before = conn.total_changes
            _insert_queue_row(conn, observation_id, source_id, competition_id, meta, now)
            if conn.total_changes > before:
                created += 1
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return created


def enqueue_pending(db_path, *, source_id: str = "pci", now=None) -> int:
    """Enfileira observações da fonte que ainda não têm linha na fila.

    Reconstroi metadados mínimos a partir da observação e do documento de descoberta
    (título e URL), para retomada quando a fila estiver vazia.
    """
    now = now or _now()
    created = 0
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            """SELECT o.id, o.competition_id, d.title, d.discovery_url
            FROM observacoes_concurso o
            LEFT JOIN documentos d ON d.observation_id = o.id AND d.issuer LIKE 'PCI%'
            WHERE o.id NOT IN (SELECT observation_id FROM fila_confirmacao)
            ORDER BY o.competition_id""").fetchall()
        for observation_id, competition_id, title, url in rows:
            if not str(competition_id).startswith(f"{source_id}-"):
                continue
            candidate = {"competition_id": competition_id, "title": title, "url": url}
            before = conn.total_changes
            _insert_queue_row(conn, observation_id, source_id, competition_id, candidate, now)
            if conn.total_changes > before:
                created += 1
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return created


def recover_stale(db_path, *, stale_minutes: int = DEFAULT_STALE_MINUTES, now=None) -> int:
    """Itens presos em `em_processamento` voltam a `pendente` (retomada após interrupção)."""
    now_dt = _parse(now or _now())
    cutoff = (now_dt - timedelta(minutes=stale_minutes)).isoformat()
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            """UPDATE fila_confirmacao SET state='pendente', updated_at=?
            WHERE state='em_processamento' AND (last_attempt_at IS NULL OR last_attempt_at < ?)""",
            ((now or _now()), cutoff))
        conn.commit()
        return cur.rowcount
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def select_batch(db_path, *, limit: int = DEFAULT_BATCH_LIMIT, now=None) -> list[dict]:
    """Seleciona até `limit` itens elegíveis, por prioridade (maior primeiro)."""
    now = now or _now()
    limit = max(0, int(limit))
    conn = connect_documents(db_path)
    try:
        placeholders = ",".join("?" for _ in RETRYABLE_STATES)
        rows = conn.execute(
            f"""SELECT observation_id, source_id, competition_id, state, attempts, priority_score,
            priority_reason, result_json, official_url
            FROM fila_confirmacao
            WHERE state='pendente'
               OR (state IN ({placeholders}) AND (next_attempt_at IS NULL OR next_attempt_at <= ?))
            ORDER BY priority_score DESC, competition_id ASC
            LIMIT ?""", (*RETRYABLE_STATES, now, limit)).fetchall()
        return [
            {"observation_id": r[0], "source_id": r[1], "competition_id": r[2], "state": r[3],
             "attempts": r[4], "priority_score": r[5], "priority_reason": r[6],
             "candidate": (json.loads(r[7]) or {}).get("candidate", {}) if r[7] else {},
             "official_url": r[8]}
            for r in rows
        ]
    finally:
        conn.close()


def _append_history(conn, observation_id, entry):
    row = conn.execute("SELECT history_json FROM fila_confirmacao WHERE observation_id=?",
                       (observation_id,)).fetchone()
    history = json.loads(row[0]) if row and row[0] else []
    history.append(entry)
    return json.dumps(history, ensure_ascii=False)


def _update(conn, observation_id, *, state, now, next_attempt_at=None, official_url=None,
            official_source=None, document_id=None, reason=None, ambiguity=None,
            result=None, success=False):
    history = _append_history(conn, observation_id, {"at": now, "state": state, "reason": reason})
    conn.execute(
        """UPDATE fila_confirmacao SET state=?, attempts=attempts+1, last_attempt_at=?,
        next_attempt_at=?, last_success_at=COALESCE(?, last_success_at),
        official_url=COALESCE(?, official_url), official_source=COALESCE(?, official_source),
        document_id=COALESCE(?, document_id), reason=?, ambiguity=?,
        result_json=COALESCE(?, result_json), history_json=?, updated_at=?
        WHERE observation_id=?""",
        (state, now, next_attempt_at, now if success else None, official_url, official_source,
         document_id, reason, ambiguity, json.dumps(result, ensure_ascii=False) if result else None,
         history, now, observation_id))


def _analyze(db_path, version_id):
    from radar.monitoring import _analyze_version
    _analyze_version(db_path, version_id)


def _resolve(resolvers, candidate):
    """Executa a cadeia de resolvers; devolve (resolution|None, all_failed).

    ``all_failed`` é True apenas quando **todos** os resolvers levantaram exceção
    (falha técnica), o que distingue "nenhuma referência encontrada" de "fontes
    oficiais indisponíveis".
    """
    errored = 0
    total = 0
    fallback = None
    for resolver in resolvers:
        total += 1
        fn = resolver if callable(resolver) else getattr(resolver, "resolve", None)
        if fn is None:
            errored += 1
            continue
        try:
            resolution = fn(candidate)
        except Exception:
            errored += 1
            continue
        if resolution:
            if not resolution.get("ambiguity"):
                return resolution, False  # casamento não ambíguo: para aqui
            if fallback is None:
                fallback = resolution  # guarda o ambíguo como reserva
    if fallback is not None:
        return fallback, False
    return None, bool(total) and errored == total


def process_batch(db_path, *, resolvers=None, limit: int = DEFAULT_BATCH_LIMIT, now=None,
                  transport=None, analyze: bool = True, stale_minutes: int = DEFAULT_STALE_MINUTES) -> dict:
    """Processa um lote da fila. Cada item é isolado; uma falha não derruba o lote."""
    if resolvers is None:
        from radar.official_resolvers import default_resolvers
        resolvers = default_resolvers()
    now = now or _now()

    recovered = recover_stale(db_path, stale_minutes=stale_minutes, now=now)
    batch = select_batch(db_path, limit=limit, now=now)

    summary = {"eligible": len(batch), "processed": 0, "states": {}, "recovered_stale": recovered,
               "errors": []}

    def _bump(state):
        summary["states"][state] = summary["states"].get(state, 0) + 1

    for item in batch:
        observation_id = item["observation_id"]
        candidate = item.get("candidate") or {}
        candidate.setdefault("url", item.get("official_url"))
        summary["processed"] += 1
        try:
            _mark_processing(db_path, observation_id, now)
            resolution, all_failed = _resolve(resolvers, candidate)

            if not resolution or not resolution.get("official_url"):
                if all_failed:
                    _finish(db_path, observation_id, state="falhou", now=now,
                            reason="fontes oficiais indisponíveis", next_attempt_at=_backoff(now))
                    _bump("falhou")
                else:
                    _finish(db_path, observation_id, state="nao_localizado", now=now,
                            reason="sem referência oficial localizada", next_attempt_at=_backoff(now))
                    _bump("nao_localizado")
                continue
            if resolution.get("ambiguity"):
                _finish(db_path, observation_id, state="inconclusivo", now=now,
                        reason=resolution.get("reason") or "associação ambígua",
                        official_url=resolution["official_url"], official_source=resolution.get("source"),
                        ambiguity=resolution["ambiguity"], next_attempt_at=_backoff(now))
                _bump("inconclusivo")
                continue
            if resolution.get("no_download"):
                # Página oficial localizada, sem arquivo recuperável: registra a referência
                # sem baixar (não confunde página com edital processado).
                _finish(db_path, observation_id, state="fonte_oficial_localizada", now=now,
                        reason=resolution.get("reason") or "página oficial localizada",
                        official_url=resolution["official_url"], official_source=resolution.get("source"),
                        next_attempt_at=_backoff(now))
                _bump("fonte_oficial_localizada")
                continue

            state, document_id = _register_official(db_path, observation_id, candidate, resolution,
                                                    transport=transport, analyze=analyze)
            _bump(state)
        except Exception as error:
            # Isolamento por item: erro inesperado não derruba o lote inteiro.
            summary["errors"].append({"observation_id": observation_id, "error_code": type(error).__name__})
            try:
                _finish(db_path, observation_id, state="falhou", now=now,
                        reason=f"erro inesperado: {type(error).__name__}", next_attempt_at=_backoff(now))
                _bump("falhou")
            except Exception:
                pass
    return summary


def _mark_processing(db_path, observation_id, now):
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """UPDATE fila_confirmacao SET state='em_processamento', last_attempt_at=?, updated_at=?
            WHERE observation_id=?""", (now, now, observation_id))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _backoff(now: str, minutes: int = RETRY_BACKOFF_MINUTES) -> str:
    dt = _parse(now) or datetime.now(timezone.utc)
    return (dt + timedelta(minutes=minutes)).isoformat()


def _register_official(db_path, observation_id, candidate, resolution, *, transport, analyze):
    """Registra o documento oficial; devolve (state, document_id|None)."""
    now = _now()
    title = resolution.get("title") or candidate.get("title") or "Documento oficial"
    try:
        from radar import document_types
        document_id = register_document(db_path, {
            "observation_id": observation_id,
            "kind": classify_official(title),
            "document_type": resolution.get("document_type") or document_types.classify(title),
            "official_url": resolution["official_url"],
            "title": title,
            "discovery_url": resolution["official_url"],
            "discovery_method": "automatico",
            "discovered_at": now,
            "issuer": resolution.get("source"),
        })
    except Exception as error:
        _finish(db_path, observation_id, state="falhou", now=now,
                reason=f"registro: {type(error).__name__}", next_attempt_at=_backoff(now))
        return "falhou", None

    from radar.document_download import download_document
    try:
        version_id = download_document(db_path, document_id, transport=transport)
    except Exception as error:
        _finish(db_path, observation_id, state="documento_localizado", now=now,
                reason=f"download: {type(error).__name__}", official_url=resolution["official_url"],
                official_source=resolution.get("source"), document_id=document_id,
                next_attempt_at=_backoff(now))
        return "documento_localizado", document_id

    if analyze:
        try:
            _analyze(db_path, version_id)
        except Exception:
            pass
    conn = connect_documents(db_path)
    try:
        proposals = conn.execute(
            """SELECT count(*) FROM propostas_campo p JOIN evidencias e ON e.id=p.evidence_id
            WHERE e.version_id=?""", (version_id,)).fetchone()[0]
    finally:
        conn.close()
    if proposals > 0:
        state = "revisao_pendente"
        reason = "documento oficial registrado; propostas pendentes de revisão"
    else:
        state = "documento_processado"
        reason = "documento oficial registrado e processado; sem campos propostos"
    _finish(db_path, observation_id, state=state, now=now, reason=reason,
            official_url=resolution["official_url"], official_source=resolution.get("source"),
            document_id=document_id, result={"confidence": resolution.get("confidence"),
                                             "proposals": proposals}, success=True)
    return state, document_id


def _finish(db_path, observation_id, *, state, now, reason=None, next_attempt_at=None,
            official_url=None, official_source=None, document_id=None, ambiguity=None,
            result=None, success=False):
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        _update(conn, observation_id, state=state, now=now, next_attempt_at=next_attempt_at,
                official_url=official_url, official_source=official_source, document_id=document_id,
                reason=reason, ambiguity=ambiguity, result=result, success=success)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def queue_status(db_path, *, now=None) -> dict:
    """Contadores por estado, última execução e próximos itens."""
    now = now or _now()
    conn = connect_documents(db_path)
    try:
        counts = {state: 0 for state in QUEUE_STATES}
        for state, total in conn.execute(
                "SELECT state, count(*) FROM fila_confirmacao GROUP BY state"):
            counts[state] = total
        last = conn.execute("SELECT max(updated_at) FROM fila_confirmacao").fetchone()[0]
        pending = conn.execute(
            "SELECT count(*) FROM fila_confirmacao WHERE state='pendente'").fetchone()[0]
        upcoming = [
            {"observation_id": r[0], "competition_id": r[1], "state": r[2], "priority_score": r[3]}
            for r in conn.execute(
                """SELECT observation_id, competition_id, state, priority_score FROM fila_confirmacao
                WHERE state IN ('pendente','falhou','nao_localizado','inconclusivo','documento_localizado')
                ORDER BY priority_score DESC, competition_id ASC LIMIT 10""")
        ]
        return {"counts": counts, "total": sum(counts.values()), "pending": pending,
                "last_update_at": last, "upcoming": upcoming}
    finally:
        conn.close()


def get_item(db_path, observation_id: str) -> dict | None:
    conn = connect_documents(db_path)
    try:
        row = conn.execute(
            """SELECT observation_id, source_id, competition_id, state, attempts, last_attempt_at,
            next_attempt_at, last_success_at, official_url, official_source, document_id,
            priority_score, priority_reason, reason, ambiguity, result_json, history_json, updated_at
            FROM fila_confirmacao WHERE observation_id=?""", (observation_id,)).fetchone()
        if not row:
            return None
        keys = ("observation_id", "source_id", "competition_id", "state", "attempts",
                "last_attempt_at", "next_attempt_at", "last_success_at", "official_url",
                "official_source", "document_id", "priority_score", "priority_reason", "reason",
                "ambiguity", "result_json", "history_json", "updated_at")
        item = dict(zip(keys, row))
        item["result"] = json.loads(item.pop("result_json")) if item.get("result_json") else {}
        item["history"] = json.loads(item.pop("history_json")) if item.get("history_json") else []
        return item
    finally:
        conn.close()


def reconcile(db_path, *, now=None) -> dict:
    """Compara candidatos com documentos de outras fontes (título/órgão normalizados).

    Preserva proveniências; não funde identidades automaticamente.
    """
    conn = connect_documents(db_path)
    try:
        other = conn.execute(
            "SELECT title, issuer FROM documentos WHERE issuer IS NULL OR issuer NOT LIKE 'PCI%'").fetchall()
        other_map: dict[str, list] = {}
        for t, issuer in other:
            if t:
                other_map.setdefault(normalize(t), []).append((t, issuer))
        rows = conn.execute(
            """SELECT f.observation_id, f.competition_id, d.title
            FROM fila_confirmacao f
            LEFT JOIN documentos d ON d.observation_id = f.observation_id AND d.issuer LIKE 'PCI%'""").fetchall()
        result = {"coincidente": 0, "novo": 0, "ambiguo": 0, "sem_dados": 0, "details": []}
        for observation_id, competition_id, title in rows:
            norm = normalize(title or "")
            if not norm:
                result["sem_dados"] += 1
                result["details"].append({"competition_id": competition_id, "match": "sem_dados"})
                continue
            matches = other_map.get(norm) or []
            if not matches:
                result["novo"] += 1
                result["details"].append({"competition_id": competition_id, "match": "novo"})
            elif len({issuer for _, issuer in matches}) > 1:
                result["ambiguo"] += 1
                result["details"].append({"competition_id": competition_id, "match": "ambiguo",
                                          "other_titles": sorted({t for t, _ in matches})})
            else:
                result["coincidente"] += 1
                result["details"].append({"competition_id": competition_id, "match": "coincidente",
                                          "other_title": matches[0][0]})
        return result
    finally:
        conn.close()


def metrics(db_path) -> dict:
    """Métricas de efetividade da confirmação (contagens distintas, sem inflar).

    Uma página e um PDF **não** são duas oportunidades; propostas **não** são valores
    validados. Separa selecionados, páginas localizadas, documentos encontrados/recuperados,
    editais, anexos, retificações, propostas, pendências, falhas e ambiguidades.
    """
    conn = connect_documents(db_path)
    try:
        states = {state: 0 for state in QUEUE_STATES}
        for state, total in conn.execute("SELECT state, count(*) FROM fila_confirmacao GROUP BY state"):
            states[state] = total
        selected = sum(states.values())
        pages = conn.execute(
            "SELECT count(*) FROM documentos WHERE tipo_documental='pagina_concurso'").fetchone()[0]
        by_type = {row[0]: row[1] for row in conn.execute(
            "SELECT coalesce(tipo_documental,'desconhecido'), count(*) FROM documentos GROUP BY 1")}
        documents_found = sum(by_type.values())
        recovered = conn.execute(
            "SELECT count(DISTINCT document_id) FROM versoes_documento").fetchone()[0]
        processed = conn.execute(
            "SELECT count(DISTINCT document_id) FROM versoes_documento "
            "WHERE extraction_state IN ('concluida','parcial')").fetchone()[0]
        editais = by_type.get("edital_abertura", 0) + by_type.get("edital_retificado", 0)
        return {
            "selected": selected,
            "pages_found": pages,
            "documents_found": documents_found,
            "documents_recovered": recovered,
            "documents_processed": processed,
            "editais": editais,
            "anexos": by_type.get("anexo", 0),
            "retificacoes": by_type.get("retificacao", 0),
            "proposals": conn.execute("SELECT count(*) FROM propostas_campo").fetchone()[0],
            "reviews": conn.execute("SELECT count(*) FROM revisoes_campo").fetchone()[0],
            "pending": states.get("pendente", 0),
            "review_pending": states.get("revisao_pendente", 0),
            "not_found": states.get("nao_localizado", 0),
            "inconclusive": states.get("inconclusivo", 0),
            "failed": states.get("falhou", 0),
            "by_state": states,
            "by_type": by_type,
            "by_source": source_metrics(conn),
        }
    finally:
        conn.close()


def source_metrics(conn) -> dict:
    """Métricas por origem (issuer): documentos, recuperados, processados, propostas.

    Diferencia a contribuição de cada fonte (PCI, DOU, FGV, Quadrix) sem contar página
    e PDF como duas oportunidades: ``documents`` conta registros; ``recovered`` e
    ``processed`` contam documentos distintos com versão.
    """
    docs = dict(conn.execute(
        "SELECT coalesce(issuer,'(sem fonte)'), count(*) FROM documentos GROUP BY 1"))
    recovered = dict(conn.execute(
        """SELECT coalesce(d.issuer,'(sem fonte)'), count(DISTINCT v.document_id)
        FROM documentos d JOIN versoes_documento v ON v.document_id=d.id GROUP BY 1"""))
    processed = dict(conn.execute(
        """SELECT coalesce(d.issuer,'(sem fonte)'), count(DISTINCT v.document_id)
        FROM documentos d JOIN versoes_documento v ON v.document_id=d.id
        WHERE v.extraction_state IN ('concluida','parcial') GROUP BY 1"""))
    proposals = dict(conn.execute(
        """SELECT coalesce(d.issuer,'(sem fonte)'), count(*)
        FROM propostas_campo p JOIN evidencias e ON e.id=p.evidence_id
        JOIN versoes_documento v ON v.id=e.version_id JOIN documentos d ON d.id=v.document_id
        GROUP BY 1"""))
    sources = sorted(set(docs) | set(recovered) | set(processed) | set(proposals))
    return {s: {"documents": docs.get(s, 0), "recovered": recovered.get(s, 0),
                "processed": processed.get(s, 0), "proposals": proposals.get(s, 0)}
            for s in sources}


def priority_report(db_path, *, limit: int = 20) -> list[dict]:
    """Itens da fila ordenados por prioridade, com os sinais que a explicam.

    Cada linha mostra o motivo textual (``priority_reason``) e evidências documentais já
    extraídas (propostas de vagas imediatas/indígenas do concurso). Não é uma pontuação
    opaca: sinais e contagens são expostos para conferência.
    """
    limit = max(0, int(limit))
    conn = connect_documents(db_path)
    try:
        rows = conn.execute(
            """SELECT f.observation_id, f.competition_id, f.state, f.priority_score,
            f.priority_reason, f.official_source
            FROM fila_confirmacao f
            ORDER BY f.priority_score DESC, f.competition_id ASC LIMIT ?""", (limit,)).fetchall()
        report = []
        for observation_id, competition_id, state, score, reason, source in rows:
            row = conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                               (observation_id,)).fetchone()
            contest_id = row[0] if row else None
            indigenous = immediate = 0
            if contest_id:
                indigenous = conn.execute(
                    "SELECT count(*) FROM propostas_campo WHERE contest_id=? AND field_name='indigenous_vacancies'",
                    (contest_id,)).fetchone()[0]
                immediate = conn.execute(
                    "SELECT count(*) FROM propostas_campo WHERE contest_id=? AND field_name='immediate_vacancies'",
                    (contest_id,)).fetchone()[0]
            signals = [s for s in (reason or "").split(",") if s and s != "neutro"]
            if immediate:
                signals.append("propostas_vagas_imediatas")
            if indigenous:
                signals.append("propostas_vagas_indigenas")
            report.append({"observation_id": observation_id, "competition_id": competition_id,
                           "state": state, "priority_score": score, "signals": signals,
                           "official_source": source, "immediate_proposals": immediate,
                           "indigenous_proposals": indigenous})
        return report
    finally:
        conn.close()
