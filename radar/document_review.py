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
    _reviewer(reviewer, reason)
    if decision not in ('validado', 'rejeitado'):
        raise ValueError('decisão inválida')
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('''SELECT d.id FROM propostas_campo p
            JOIN evidencias e ON e.id=p.evidence_id JOIN versoes_documento v ON v.id=e.version_id
            JOIN documentos d ON d.id=v.document_id WHERE p.id=? AND d.contest_id=p.contest_id''',
            (proposal_id,)).fetchone()
        if not row:
            raise ValueError('proposta sem evidência válida')
        review_id, at = str(uuid4()), _now()
        conn.execute('INSERT INTO revisoes_campo VALUES (?,?,?,?,?,?)',
                     (review_id, proposal_id, decision, at, reviewer.strip(), reason.strip()))
        conn.execute('''INSERT INTO eventos_documentais
            (id,document_id,version_id,event_type,occurred_at,note)
            SELECT ?,d.id,v.id,'revisao',?,? FROM propostas_campo p
            JOIN evidencias e ON e.id=p.evidence_id JOIN versoes_documento v ON v.id=e.version_id
            JOIN documentos d ON d.id=v.document_id WHERE p.id=?''',
            (str(uuid4()), at, decision, proposal_id))
        return review_id


def select_current_value(db_path, proposal_id: str, reviewer: str, reason: str) -> str:
    _reviewer(reviewer, reason)
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('''SELECT p.contest_id,p.role_id,p.field_name,p.ambiguity_reason FROM propostas_campo p
            JOIN evidencias e ON e.id=p.evidence_id JOIN versoes_documento v ON v.id=e.version_id
            JOIN documentos d ON d.id=v.document_id WHERE p.id=? AND d.contest_id=p.contest_id''',
            (proposal_id,)).fetchone()
        if not row:
            raise ValueError('proposta sem evidência válida')
        last = conn.execute('SELECT decision FROM revisoes_campo WHERE proposal_id=? ORDER BY reviewed_at DESC,id DESC LIMIT 1',
                            (proposal_id,)).fetchone()
        if not last or last[0] != 'validado':
            raise ValueError('proposta exige revisão validada mais recente')
        contest_id, role_id, field_name, ambiguity_reason = row
        if role_id is None:
            label = label_from_ambiguity(ambiguity_reason)
            if label:
                reconciled = conn.execute('''SELECT role_id FROM reconciliacoes_cargo
                    WHERE contest_id=? AND label=? ORDER BY reconciled_at DESC,id DESC LIMIT 1''',
                    (contest_id, label)).fetchone()
                if reconciled:
                    role_id = reconciled[0]
        prior = conn.execute('''SELECT id FROM valores_atuais WHERE contest_id=? AND role_id IS ?
            AND field_name=? ORDER BY selected_at DESC,id DESC LIMIT 1''',
            (contest_id, role_id, field_name)).fetchone()
        selection_id = str(uuid4())
        conn.execute('INSERT INTO valores_atuais VALUES (?,?,?,?,?,?,?,?,?)',
                     (selection_id, contest_id, role_id, field_name, proposal_id, _now(), reviewer.strip(),
                      prior[0] if prior else None, reason.strip()))
        return selection_id


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
