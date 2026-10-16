"""CLI do Radar de Concursos (``python -m radar``).

Subcomandos:
- ``collect --db PATH``: baixa a fonte oficial, faz o parse completo e só então
  persiste via ``upsert_records``. ``verified_at`` em ISO UTC com offset.
  Falha de fetch/collect propaga (saída não-zero) e nada é gravado.
- ``serve --db PATH [--host 127.0.0.1] [--port 8000]``: cria o servidor
  loopback e chama ``serve_forever()``.

Nenhuma coleta automática em background e nenhuma dependência externa.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from radar import confirmation
from radar.collector import collect, fetch_official
from radar.document_store import migrate_document_schema, sync_v1_identifiers
from radar.document_store import connect_documents, record_analysis, link_amendment, ensure_role
from radar.document_discovery import register_manual_url
from radar.document_download import download_document
from radar.document_extract import extract_blocks
from radar.document_fields import extract_field_proposals, invalid_registration_period
from radar.document_review import review_proposal, select_current_value, record_coverage, reconcile_role_label
from radar.monitoring import run_cycle
from radar.server import create_server
from radar.storage import list_records, upsert_records


def _cmd_collect(args: argparse.Namespace) -> None:
    html = fetch_official()
    verified_at = datetime.now(timezone.utc).isoformat()
    records = collect(html, verified_at)
    current = list_records(args.db)
    for record in records:
        old_roles = {
            old["role"] for old in current
            if old["source_url"] == record["source_url"]
            and old["competition_id"] == record["competition_id"]
        }
        new_roles = {
            new["role"] for new in records
            if new["source_url"] == record["source_url"]
            and new["competition_id"] == record["competition_id"]
        }
        if old_roles and old_roles != new_roles:
            raise ValueError("cargos da fonte alterados; revisão manual necessária")
    upsert_records(args.db, records)


def _cmd_serve(args: argparse.Namespace) -> None:
    server = create_server(args.db, host=args.host, port=args.port)
    server.serve_forever()


def _cmd_analyze(args: argparse.Namespace) -> None:
    with closing(connect_documents(args.db)) as conn:
        row = conn.execute('''SELECT v.sha256,v.local_path,v.content_type,d.contest_id,d.role_id
            FROM versoes_documento v JOIN documentos d ON d.id=v.document_id WHERE v.id=?''',
            (args.version_id,)).fetchone()
    if not row:
        raise ValueError('versão inexistente')
    digest, relative_path, content_type, contest_id, role_id = row
    root = Path(args.db).resolve().parent / (Path(args.db).name + '.documents')
    artifact = (Path(args.db).resolve().parent / relative_path).resolve()
    if artifact.parent != root.resolve() or artifact.name != digest:
        raise ValueError('caminho de artefato inválido')
    content = artifact.read_bytes()
    if hashlib.sha256(content).hexdigest() != digest:
        raise ValueError('hash de artefato divergente')
    try:
        blocks = extract_blocks(content, content_type)
    except ValueError as error:
        with closing(connect_documents(args.db)) as conn, conn:
            conn.execute("UPDATE versoes_documento SET extraction_state='falhou',error_code=? WHERE id=?",
                         (type(error).__name__, args.version_id))
            conn.execute("""INSERT INTO eventos_documentais
                (id,document_id,version_id,event_type,occurred_at,note)
                SELECT ?,document_id,id,'falha',?,? FROM versoes_documento WHERE id=?""",
                (str(uuid4()), datetime.now(timezone.utc).isoformat(), type(error).__name__, args.version_id))
        raise
    proposals = extract_field_proposals(blocks, args.version_id, contest_id, role_id)
    record_analysis(args.db, args.version_id, blocks, proposals)
    if invalid_registration_period(blocks):
        with closing(connect_documents(args.db)) as conn, conn:
            conn.execute("UPDATE versoes_documento SET error_code='invalid_registration_period' WHERE id=?", (args.version_id,))
            conn.execute("""INSERT INTO eventos_documentais
                (id,document_id,version_id,event_type,occurred_at,note)
                SELECT ?,document_id,id,'falha',?,'invalid_registration_period'
                FROM versoes_documento WHERE id=?""",
                (str(uuid4()), datetime.now(timezone.utc).isoformat(), args.version_id))


def _cmd_monitor(args: argparse.Namespace) -> None:
    summary = run_cycle(args.db, analyze=args.analyze)
    print(json.dumps(summary, ensure_ascii=False))


def _cmd_quadrix_cargos(args: argparse.Namespace) -> None:
    """Importa cargos do HTML oficial e vincula as propostas existentes por código."""
    from contextlib import closing
    from radar import quadrix_source
    from radar.role_reconciliation import link_contest_proposals
    from radar.document_store import ensure_observation, connect_documents
    html = quadrix_source.fetch_detail(args.quadrix_id)
    table = quadrix_source.parse_cargo_table(html)
    observation_id = ensure_observation(args.db, quadrix_source.detail_url(args.quadrix_id),
                                        f"quadrix-{args.quadrix_id}")
    with closing(connect_documents(args.db)) as conn:
        contest_id = conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                  (observation_id,)).fetchone()[0]
    result = link_contest_proposals(args.db, contest_id, observation_id, table)
    print(json.dumps({"quadrix_id": args.quadrix_id, "contest_id": contest_id,
                      "roles_in_html": len(table), **result}, ensure_ascii=False))


def _cmd_confirmacao_lote(args: argparse.Namespace) -> None:
    if args.enqueue:
        confirmation.enqueue_pending(args.db, source_id=args.source_id)
    if args.dry_run:
        batch = confirmation.select_batch(args.db, limit=args.limit)
        print(json.dumps({"dry_run": True, "eligible": len(batch),
                          "items": [b["competition_id"] for b in batch]}, ensure_ascii=False))
        return
    print(json.dumps(confirmation.process_batch(args.db, limit=args.limit), ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m radar")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser(
        "collect", help="coleta a fonte oficial e persiste no banco SQLite"
    )
    collect_parser.add_argument("--db", required=True, help="caminho do arquivo SQLite")
    collect_parser.set_defaults(func=_cmd_collect)

    serve_parser = subparsers.add_parser(
        "serve", help="inicia o servidor HTTP loopback local"
    )
    serve_parser.add_argument("--db", required=True, help="caminho do arquivo SQLite")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.set_defaults(func=_cmd_serve)

    migrate_parser = subparsers.add_parser('documents-migrate', help='migra explicitamente o banco documental')
    migrate_parser.add_argument('--db', required=True)
    migrate_parser.set_defaults(func=lambda args: migrate_document_schema(args.db))

    sync_parser = subparsers.add_parser('documents-sync', help='sincroniza identidades documentais v1')
    sync_parser.add_argument('--db', required=True)
    sync_parser.set_defaults(func=lambda args: sync_v1_identifiers(args.db))

    register_parser = subparsers.add_parser('documents-register', help='registra URL oficial manualmente')
    register_parser.add_argument('--db', required=True)
    register_parser.add_argument('--observation-id', required=True)
    register_parser.add_argument('--kind', choices=('edital', 'retificacao', 'outro'), required=True)
    register_parser.add_argument('--url', required=True)
    register_parser.add_argument('--title', required=True)
    register_parser.set_defaults(func=lambda args: print(register_manual_url(
        args.db, args.observation_id, args.kind, args.url, args.title)))

    fetch_parser = subparsers.add_parser('documents-fetch', help='baixa documento registrado')
    fetch_parser.add_argument('--db', required=True)
    fetch_parser.add_argument('--document-id', required=True)
    fetch_parser.set_defaults(func=lambda args: print(download_document(args.db, args.document_id)))

    analyze_parser = subparsers.add_parser('documents-analyze', help='extrai propostas sem validar automaticamente')
    analyze_parser.add_argument('--db', required=True)
    analyze_parser.add_argument('--version-id', required=True)
    analyze_parser.set_defaults(func=_cmd_analyze)

    review_parser = subparsers.add_parser('documents-review', help='revisão humana de proposta')
    review_parser.add_argument('--db', required=True)
    review_parser.add_argument('--proposal-id', required=True)
    review_parser.add_argument('--decision', choices=('validado', 'rejeitado'), required=True)
    review_parser.add_argument('--reviewer', required=True)
    review_parser.add_argument('--reason', required=True)
    review_parser.set_defaults(func=lambda args: print(review_proposal(
        args.db, args.proposal_id, args.decision, args.reviewer, args.reason)))

    select_parser = subparsers.add_parser('documents-select', help='seleção humana do valor corrente')
    select_parser.add_argument('--db', required=True)
    select_parser.add_argument('--proposal-id', required=True)
    select_parser.add_argument('--reviewer', required=True)
    select_parser.add_argument('--reason', required=True)
    select_parser.set_defaults(func=lambda args: print(select_current_value(
        args.db, args.proposal_id, args.reviewer, args.reason)))

    coverage_parser = subparsers.add_parser('documents-coverage', help='registra escopo da conferência')
    coverage_parser.add_argument('--db', required=True)
    coverage_parser.add_argument('--contest-id', required=True)
    coverage_parser.add_argument('--state', choices=('parcial', 'auditada_ate'), required=True)
    coverage_parser.add_argument('--checked-url', action='append', default=[])
    coverage_parser.add_argument('--reviewer', required=True)
    coverage_parser.add_argument('--checked-at', required=True)
    coverage_parser.add_argument('--note', required=True)
    coverage_parser.set_defaults(func=lambda args: print(record_coverage(
        args.db, args.contest_id, args.state, args.checked_url, args.reviewer,
        args.checked_at, args.note)))

    reconcile_parser = subparsers.add_parser('documents-reconcile',
        help='vincula rótulo de cargo do documento a uma identidade canônica')
    reconcile_parser.add_argument('--db', required=True)
    reconcile_parser.add_argument('--contest-id', required=True)
    reconcile_parser.add_argument('--label', required=True)
    reconcile_parser.add_argument('--role-id', required=True)
    reconcile_parser.add_argument('--reviewer', required=True)
    reconcile_parser.add_argument('--reason', required=True)
    reconcile_parser.set_defaults(func=lambda args: print(reconcile_role_label(
        args.db, args.contest_id, args.label, args.role_id, args.reviewer, args.reason)))

    link_parser = subparsers.add_parser('documents-link-amendment',
        help='vincula uma retificação ao documento original')
    link_parser.add_argument('--db', required=True)
    link_parser.add_argument('--amendment-id', required=True)
    link_parser.add_argument('--original-id', required=True)
    link_parser.add_argument('--reviewer', required=True)
    link_parser.add_argument('--reason', required=True)
    link_parser.set_defaults(func=lambda args: print(link_amendment(
        args.db, args.amendment_id, args.original_id, args.reviewer, args.reason)))

    monitor_parser = subparsers.add_parser('monitor',
        help='executa um ciclo de monitoramento das fontes autorizadas')
    monitor_parser.add_argument('--db', required=True)
    monitor_parser.add_argument('--analyze', action='store_true',
        help='extrai blocos e propostas das versões novas (nunca valida)')
    monitor_parser.set_defaults(func=_cmd_monitor)

    role_parser = subparsers.add_parser('documents-role',
        help='registra identidade de cargo de um concurso a partir do rótulo do documento')
    role_parser.add_argument('--db', required=True)
    role_parser.add_argument('--contest-id', required=True)
    role_parser.add_argument('--observation-id', required=True)
    role_parser.add_argument('--name', required=True)
    role_parser.add_argument('--specialty', default=None)
    role_parser.set_defaults(func=lambda args: print(ensure_role(
        args.db, args.contest_id, args.observation_id, args.name, args.specialty)))

    conf_status = subparsers.add_parser('confirmacao-status',
        help='resumo da fila de confirmação documental')
    conf_status.add_argument('--db', required=True)
    conf_status.set_defaults(func=lambda args: print(json.dumps(
        confirmation.queue_status(args.db), ensure_ascii=False)))

    conf_reconcile = subparsers.add_parser('confirmacao-reconciliar',
        help='reconcilia candidatos com documentos de outras fontes')
    conf_reconcile.add_argument('--db', required=True)
    conf_reconcile.set_defaults(func=lambda args: print(json.dumps(
        confirmation.reconcile(args.db), ensure_ascii=False)))

    conf_lote = subparsers.add_parser('confirmacao-lote',
        help='processa um lote limitado da fila de confirmação')
    conf_lote.add_argument('--db', required=True)
    conf_lote.add_argument('--limit', type=int, default=confirmation.DEFAULT_BATCH_LIMIT)
    conf_lote.add_argument('--enqueue', action='store_true',
        help='enfileira observações da fonte ainda ausentes na fila antes do lote')
    conf_lote.add_argument('--source-id', default='pci')
    conf_lote.add_argument('--dry-run', action='store_true',
        help='seleciona o lote sem processar (não persiste)')
    conf_lote.set_defaults(func=_cmd_confirmacao_lote)

    conf_item = subparsers.add_parser('confirmacao-item',
        help='mostra o estado de um candidato da fila')
    conf_item.add_argument('--db', required=True)
    conf_item.add_argument('--observation-id', required=True)
    conf_item.set_defaults(func=lambda args: print(json.dumps(
        confirmation.get_item(args.db, args.observation_id), ensure_ascii=False)))

    conf_metrics = subparsers.add_parser('confirmacao-metricas',
        help='métricas de efetividade da confirmação documental')
    conf_metrics.add_argument('--db', required=True)
    conf_metrics.set_defaults(func=lambda args: print(json.dumps(
        confirmation.metrics(args.db), ensure_ascii=False)))

    conf_priority = subparsers.add_parser('confirmacao-prioridades',
        help='itens da fila por prioridade, com os sinais que a explicam')
    conf_priority.add_argument('--db', required=True)
    conf_priority.add_argument('--limit', type=int, default=20)
    conf_priority.set_defaults(func=lambda args: print(json.dumps(
        confirmation.priority_report(args.db, limit=args.limit), ensure_ascii=False)))

    conf_opps = subparsers.add_parser('confirmacao-oportunidades',
        help='oportunidades por cargo (vagas indígenas × formação), explicáveis')
    conf_opps.add_argument('--db', required=True)
    conf_opps.add_argument('--contest-id', required=True)
    conf_opps.set_defaults(func=lambda args: print(json.dumps(
        confirmation.role_opportunities(args.db, args.contest_id), ensure_ascii=False)))

    qx_cargos = subparsers.add_parser('quadrix-cargos',
        help='importa cargos do HTML oficial da Quadrix e vincula propostas por código')
    qx_cargos.add_argument('--db', required=True)
    qx_cargos.add_argument('--quadrix-id', required=True)
    qx_cargos.set_defaults(func=_cmd_quadrix_cargos)

    return parser


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
