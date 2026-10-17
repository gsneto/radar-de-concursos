"""Decisões humanas append-only sobre propostas e cobertura documental."""

from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from radar.document_discovery import allowed_document_url
from radar.document_fields import label_from_ambiguity
from radar.document_store import connect_documents


def _now():
    return datetime.now(timezone.utc).isoformat()


def _reviewer(reviewer, reason):
    if not reviewer or not reviewer.strip() or not reason or not reason.strip():
        raise ValueError('revisor e justificativa são obrigatórios')


def review_proposal(db_path, proposal_id: str, decision: str, reviewer: str, reason: str) -> str:
    """Revisão de proposta (CLI legado). Delega à central de revisão: uma só semântica."""
    from radar.review import decide_proposal
    _reviewer(reviewer, reason)
    if decision not in ('validado', 'rejeitado'):
        raise ValueError('decisão inválida')
    result = decide_proposal(db_path, proposal_id, decision, reviewer=reviewer.strip(),
                             reason=reason.strip(), origin='cli')
    return result['review_id']


def select_current_value(db_path, proposal_id: str, reviewer: str, reason: str) -> str:
    """Seleção do valor vigente (CLI legado). Delega à central de revisão (idempotente)."""
    from radar.review import select_current_value as _select
    _reviewer(reviewer, reason)
    result = _select(db_path, proposal_id, reviewer.strip(), reason.strip(), origin='cli')
    return result['selection_id']


def reconcile_role_label(db_path, contest_id: str, label: str, role_id: str,
                         reviewer: str, reason: str) -> str:
    """Vincula um rótulo de cargo do documento a uma identidade canônica, por decisão humana.

    Nunca casa por similaridade: exige rótulo evidenciado em proposta do concurso e
    recusa mapear o mesmo rótulo para cargos diferentes (correspondência ambígua).
    """
    _reviewer(reviewer, reason)
    if not isinstance(label, str) or not label.strip():
        raise ValueError('rótulo de cargo obrigatório')
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute('SELECT 1 FROM concursos_identidade WHERE id=?', (contest_id,)).fetchone():
            raise ValueError('concurso inexistente')
        if not conn.execute('SELECT 1 FROM cargos_identidade WHERE id=? AND contest_id=?',
                            (role_id, contest_id)).fetchone():
            raise ValueError('cargo de outro concurso')
        labels = {label_from_ambiguity(row[0]) for row in conn.execute(
            'SELECT ambiguity_reason FROM propostas_campo WHERE contest_id=?', (contest_id,))}
        labels.discard(None)
        if label not in labels:
            raise ValueError('rótulo sem evidência documental neste concurso')
        existing = conn.execute('''SELECT id,role_id FROM reconciliacoes_cargo
            WHERE contest_id=? AND label=? ORDER BY reconciled_at DESC,id DESC''',
            (contest_id, label)).fetchone()
        if existing:
            if existing[1] != role_id:
                raise ValueError('rótulo já reconciliado com outro cargo')
            return existing[0]
        reconciliation_id = str(uuid4())
        conn.execute('INSERT INTO reconciliacoes_cargo VALUES (?,?,?,?,?,?,?)',
                     (reconciliation_id, contest_id, label, role_id, _now(),
                      reviewer.strip(), reason.strip()))
        return reconciliation_id


def record_coverage(db_path, contest_id: str, state: str, checked_urls: list[str],
                    reviewer: str, checked_at: str, note: str) -> str:
    _reviewer(reviewer, note)
    if state not in ('parcial', 'auditada_ate') or not isinstance(checked_urls, list):
        raise ValueError('estado de cobertura inválido')
    if state == 'auditada_ate' and not checked_urls:
        raise ValueError('auditoria exige URLs conferidas')
    if any(not isinstance(url, str) or not allowed_document_url(url) for url in checked_urls):
        raise ValueError('URLs de cobertura inválidas')
    try:
        when = datetime.fromisoformat(checked_at)
        if when.tzinfo is None:
            raise ValueError('fuso horário ausente')
    except (TypeError, ValueError) as error:
        raise ValueError('data de cobertura inválida') from error
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute('SELECT 1 FROM concursos_identidade WHERE id=?', (contest_id,)).fetchone():
            raise ValueError('concurso inexistente')
        if state == 'auditada_ate':
            registered = {row[0] for row in conn.execute(
                'SELECT official_url FROM documentos WHERE contest_id=?', (contest_id,))}
            if not registered or not registered.issubset(set(checked_urls)) or any(
                url not in registered for url in checked_urls
            ):
                raise ValueError('cobertura não corresponde aos documentos registrados')
        coverage_id = str(uuid4())
        conn.execute('INSERT INTO auditorias_cobertura VALUES (?,?,?,?,?,?,?)',
                     (coverage_id, contest_id, state, checked_at, json.dumps(checked_urls),
                      reviewer.strip(), note.strip()))
        return coverage_id
