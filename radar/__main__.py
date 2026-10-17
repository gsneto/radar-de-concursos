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


def _cmd_ops_ciclo(args: argparse.Namespace) -> None:
    from radar import ops
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    if args.limit is not None:
        cfg["batch_limit"] = args.limit
    logger = ops.setup_logging(cfg["logs_dir"])
    summary = ops.run_cycle(cfg, logger=logger)
    print(json.dumps(summary, ensure_ascii=False, default=str))


def _cmd_ops_saude(args: argparse.Namespace) -> None:
    from radar import ops
    from radar.ops_config import load_config
    print(json.dumps(ops.health(load_config(args.config), check_server=not args.no_server_check),
                     ensure_ascii=False, default=str))


def _cmd_ops_alertas(args: argparse.Namespace) -> None:
    from radar import ops
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    print(json.dumps(ops.list_alerts(cfg["db_path"], unseen_only=args.unseen, limit=args.limit),
                     ensure_ascii=False, default=str))


def _cmd_ops_alerta_marcar(args: argparse.Namespace) -> None:
    from radar import ops
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    seen = True if args.seen else None
    dismissed = True if args.dismissed else None
    ok = ops.mark_alert(cfg["db_path"], args.id, seen=seen, dismissed=dismissed)
    print(json.dumps({"id": args.id, "updated": ok}, ensure_ascii=False))


def _cmd_ops_config(args: argparse.Namespace) -> None:
    from radar.ops_config import load_config, save_default_config, validate_config
    if args.write:
        path = save_default_config(args.config)
        print(json.dumps({"written": str(path)}, ensure_ascii=False))
        return
    cfg = load_config(args.config)
    print(json.dumps({"config": cfg, "errors": validate_config(cfg)}, ensure_ascii=False, default=str))


def _cmd_ops_triagem(args: argparse.Namespace) -> None:
    from radar import ops
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    print(json.dumps(ops.triage(cfg["db_path"], include_seen=args.include_seen, limit=args.limit,
                                horizon_days=int(cfg.get("triage_horizon_days", 7))),
                     ensure_ascii=False, default=str))


def _cmd_ops_notificar(args: argparse.Namespace) -> None:
    from radar import notifications
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    print(json.dumps(notifications.dispatch(cfg["db_path"], cfg, limit=args.limit),
                     ensure_ascii=False, default=str))


def _cmd_ops_identidade(args: argparse.Namespace) -> None:
    from radar import notifications
    print(json.dumps(notifications.ensure_app_identity(), ensure_ascii=False, default=str))


def _cmd_ops_prioridades(args: argparse.Namespace) -> None:
    from radar import preferences, priority
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    prefs = preferences.load(cfg)
    if args.reference_uf:
        prefs["reference_uf"] = args.reference_uf
    if args.reference_municipio:
        prefs["reference_municipio"] = args.reference_municipio
    print(json.dumps(priority.prioritize(cfg["db_path"], prefs, limit=args.limit),
                     ensure_ascii=False, default=str))


def _cmd_ops_preferencias(args: argparse.Namespace) -> None:
    from radar import preferences
    from radar.ops_config import load_config, update_preferences
    cfg = load_config(args.config)
    current = preferences.load(cfg)
    changed = False
    if args.reference_uf is not None:
        current["reference_uf"] = args.reference_uf or None
        changed = True
    if args.reference_municipio is not None:
        current["reference_municipio"] = args.reference_municipio or None
        changed = True
    if args.practical_distance_km is not None:
        current["practical_distance_km"] = args.practical_distance_km
        changed = True
    if args.priority is not None:
        current["priority"] = args.priority
        changed = True
    if args.interest_states is not None:
        current["interest_states"] = [s.strip() for s in args.interest_states.split(",") if s.strip()]
        changed = True
    if changed:
        saved = preferences.validate(current)
        update_preferences(saved)
        current = saved
    print(json.dumps(current, ensure_ascii=False))


def _cmd_estudos_painel(args: argparse.Namespace) -> None:
    from radar import study_store
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    print(json.dumps(study_store.study_dashboard(cfg["db_path"]), ensure_ascii=False, default=str))


def _cmd_estudos_disciplina(args: argparse.Namespace) -> None:
    from radar import study_store
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    if args.nome:
        print(json.dumps(study_store.create_disciplina(cfg["db_path"], args.nome), ensure_ascii=False))
    else:
        print(json.dumps(study_store.list_disciplinas(cfg["db_path"]), ensure_ascii=False))


def _cmd_estudos_topico(args: argparse.Namespace) -> None:
    from radar import study_store
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    if args.nome:
        print(json.dumps(study_store.create_topico(cfg["db_path"], args.disciplina, args.nome),
                         ensure_ascii=False))
    else:
        print(json.dumps(study_store.list_topicos(cfg["db_path"], args.disciplina), ensure_ascii=False))


def _cmd_estudos_sessao(args: argparse.Namespace) -> None:
    from radar import study_store
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    action = args.sessao_action
    if action == "start":
        out = study_store.start_session(cfg["db_path"], disciplina_id=args.disciplina,
                                        topico_id=args.topico, modo=args.modo or "livre")
    elif action == "pause":
        out = study_store.pause_session(cfg["db_path"])
    elif action == "resume":
        out = study_store.resume_session(cfg["db_path"])
    elif action == "finish":
        out = study_store.finish_session(cfg["db_path"])
    elif action == "discard":
        out = study_store.discard_session(cfg["db_path"])
    else:
        out = study_store.current_session(cfg["db_path"])
    print(json.dumps(out, ensure_ascii=False, default=str))


def _cmd_estudos_revisao(args: argparse.Namespace) -> None:
    from radar import study_store
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    if args.progresso:
        print(json.dumps(study_store.mark_revision_done(cfg["db_path"], args.progresso,
                                                        resultado=args.resultado), ensure_ascii=False))
    else:
        print(json.dumps(study_store.pending_revisions(cfg["db_path"]), ensure_ascii=False))


def _cmd_estudos_conteudo(args: argparse.Namespace) -> None:
    from radar import knowledge_store
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    print(json.dumps(knowledge_store.resolve_program(cfg["db_path"], args.concurso),
                     ensure_ascii=False, default=str))


def _cmd_estudos_perfil(args: argparse.Namespace) -> None:
    from radar import knowledge_store
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    if args.rotulo:
        print(json.dumps(knowledge_store.set_profile(
            cfg["db_path"], disciplina=args.disciplina, rotulo=args.rotulo, nivel=args.nivel,
            revisar=args.revisar, confianca=args.confianca, observacoes=args.observacoes),
            ensure_ascii=False, default=str))
    else:
        print(json.dumps(knowledge_store.list_profile(cfg["db_path"]), ensure_ascii=False, default=str))


def _cmd_estudos_cobertura(args: argparse.Namespace) -> None:
    from radar import knowledge_store
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    print(json.dumps(knowledge_store.preparation_report(cfg["db_path"], args.concurso),
                     ensure_ascii=False, default=str))


def _cmd_estudos_exportar(args: argparse.Namespace) -> None:
    from radar import study_backup
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    payload = study_backup.export_study_data(cfg["db_path"])
    if args.out:
        Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"exported_to": args.out, "counts": payload["counts"]}, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False, default=str))


def _cmd_estudos_importar(args: argparse.Namespace) -> None:
    from radar import study_backup
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
    report = study_backup.import_study_data(cfg["db_path"], payload, dry_run=args.dry_run)
    print(json.dumps(report, ensure_ascii=False, default=str))


def _cmd_estudos_backup(args: argparse.Namespace) -> None:
    from radar import study_backup
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    print(json.dumps(study_backup.backup_database(cfg["db_path"], args.dest),
                     ensure_ascii=False, default=str))


def _cmd_pratica_flashcard(args: argparse.Namespace) -> None:
    from radar import practice_store
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    action = args.fc_action
    if action == "create":
        out = practice_store.create_flashcard(cfg["db_path"], frente=args.frente,
                                              verso=args.verso, disciplina_id=args.disciplina,
                                              topico_id=args.topico)
    elif action == "review":
        out = practice_store.review_flashcard(cfg["db_path"], args.id, args.qualidade)
    elif action == "archive":
        out = practice_store.update_flashcard(cfg["db_path"], args.id, estado="arquivado")
    elif action == "fila":
        out = practice_store.study_queue(cfg["db_path"], limit=args.limit)
    elif action == "stats":
        out = practice_store.flashcard_stats(cfg["db_path"])
    else:
        out = practice_store.list_flashcards(cfg["db_path"])
    print(json.dumps(out, ensure_ascii=False, default=str))


def _cmd_pratica_questao(args: argparse.Namespace) -> None:
    from radar import practice_store
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    if args.q_action == "create":
        out = practice_store.create_question(
            cfg["db_path"], enunciado=args.enunciado, alternativas=args.alternativa,
            gabarito=args.gabarito, disciplina=args.disciplina, topico=args.topico,
            comentario=args.comentario)
    elif args.q_action == "answer":
        out = practice_store.answer_question(cfg["db_path"], args.id, args.resposta)
    elif args.q_action == "archive":
        out = practice_store.archive_question(cfg["db_path"], args.id)
    else:
        out = practice_store.list_questions(cfg["db_path"])
    print(json.dumps(out, ensure_ascii=False, default=str))


def _cmd_pratica_simulado(args: argparse.Namespace) -> None:
    from radar import practice_store
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    action = args.sim_action
    if action == "create":
        out = practice_store.create_exam(cfg["db_path"], nome=args.nome, limit=args.limit,
                                         duracao_segundos=args.duracao, seed=args.seed)
    elif action == "answer":
        out = practice_store.save_exam_answer(cfg["db_path"], args.id, args.ordem, args.resposta)
    elif action == "finish":
        out = practice_store.finish_exam(cfg["db_path"], args.id)
    elif action == "result":
        out = practice_store.exam_result(cfg["db_path"], args.id)
    else:
        out = practice_store.list_exams(cfg["db_path"])
    print(json.dumps(out, ensure_ascii=False, default=str))


def _cmd_pratica_desempenho(args: argparse.Namespace) -> None:
    from radar import practice_store
    from radar.ops_config import load_config
    cfg = load_config(args.config)
    print(json.dumps(practice_store.performance_report(cfg["db_path"]),
                     ensure_ascii=False, default=str))


def build_parser() -> argparse.ArgumentParser:
    from radar.preferences import PRIORITIES
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

    ops_ciclo = subparsers.add_parser('ops-ciclo',
        help='executa um ciclo operacional completo (coleta, fila, alertas)')
    ops_ciclo.add_argument('--config', default=None)
    ops_ciclo.add_argument('--limit', type=int, default=None,
        help='sobrepõe o limite de itens da fila por execução')
    ops_ciclo.set_defaults(func=_cmd_ops_ciclo)

    ops_saude = subparsers.add_parser('ops-saude',
        help='verificação de saúde operacional (config, banco, ciclos, fila, alertas)')
    ops_saude.add_argument('--config', default=None)
    ops_saude.add_argument('--no-server-check', action='store_true')
    ops_saude.set_defaults(func=_cmd_ops_saude)

    ops_alertas = subparsers.add_parser('ops-alertas', help='lista os alertas persistentes')
    ops_alertas.add_argument('--config', default=None)
    ops_alertas.add_argument('--unseen', action='store_true')
    ops_alertas.add_argument('--limit', type=int, default=50)
    ops_alertas.set_defaults(func=_cmd_ops_alertas)

    ops_marcar = subparsers.add_parser('ops-alerta-marcar', help='marca um alerta como visto/descartado')
    ops_marcar.add_argument('--config', default=None)
    ops_marcar.add_argument('--id', required=True)
    ops_marcar.add_argument('--seen', dest='seen', action='store_true')
    ops_marcar.add_argument('--dismissed', dest='dismissed', action='store_true')
    ops_marcar.set_defaults(func=_cmd_ops_alerta_marcar)

    ops_conf = subparsers.add_parser('ops-config', help='mostra (ou grava) a configuração operacional')
    ops_conf.add_argument('--config', default=None)
    ops_conf.add_argument('--write', action='store_true', help='grava um radar_ops.json com os defaults')
    ops_conf.set_defaults(func=_cmd_ops_config)

    ops_tri = subparsers.add_parser('ops-triagem', help='central de triagem: alertas agrupados por concurso')
    ops_tri.add_argument('--config', default=None)
    ops_tri.add_argument('--include-seen', action='store_true')
    ops_tri.add_argument('--limit', type=int, default=200)
    ops_tri.set_defaults(func=_cmd_ops_triagem)

    ops_notif = subparsers.add_parser('ops-notificar', help='despacha notificações nativas dos alertas elegíveis')
    ops_notif.add_argument('--config', default=None)
    ops_notif.add_argument('--limit', type=int, default=None)
    ops_notif.set_defaults(func=_cmd_ops_notificar)

    ops_ident = subparsers.add_parser('ops-identidade', help='registra a identidade do app para toasts')
    ops_ident.add_argument('--config', default=None)
    ops_ident.set_defaults(func=_cmd_ops_identidade)

    ops_prio = subparsers.add_parser('ops-prioridades', help='ranking explicável de oportunidades')
    ops_prio.add_argument('--config', default=None)
    ops_prio.add_argument('--limit', type=int, default=200)
    ops_prio.add_argument('--reference-uf', default=None)
    ops_prio.add_argument('--reference-municipio', default=None)
    ops_prio.set_defaults(func=_cmd_ops_prioridades)

    ops_pref = subparsers.add_parser('ops-preferencias', help='mostra/atualiza preferências geográficas')
    ops_pref.add_argument('--config', default=None)
    ops_pref.add_argument('--reference-uf', default=None)
    ops_pref.add_argument('--reference-municipio', default=None)
    ops_pref.add_argument('--practical-distance-km', type=int, default=None)
    ops_pref.add_argument('--priority', default=None, choices=PRIORITIES)
    ops_pref.add_argument('--interest-states', default=None, help='UFs separadas por vírgula, ex.: BA,PE')
    ops_pref.set_defaults(func=_cmd_ops_preferencias)

    est_painel = subparsers.add_parser('estudos-painel', help='painel de estudos (progresso, tempo, revisões)')
    est_painel.add_argument('--config', default=None)
    est_painel.set_defaults(func=_cmd_estudos_painel)

    est_disc = subparsers.add_parser('estudos-disciplina', help='lista/cria disciplinas de estudo')
    est_disc.add_argument('--config', default=None)
    est_disc.add_argument('--nome', default=None)
    est_disc.set_defaults(func=_cmd_estudos_disciplina)

    est_top = subparsers.add_parser('estudos-topico', help='lista/cria tópicos de uma disciplina')
    est_top.add_argument('--config', default=None)
    est_top.add_argument('--disciplina', required=True)
    est_top.add_argument('--nome', default=None)
    est_top.set_defaults(func=_cmd_estudos_topico)

    est_sess = subparsers.add_parser('estudos-sessao', help='cronômetro de estudo (start/pause/resume/finish/discard/status)')
    est_sess.add_argument('--config', default=None)
    est_sess.add_argument('sessao_action', nargs='?', default='status',
                          choices=['start', 'pause', 'resume', 'finish', 'discard', 'status'])
    est_sess.add_argument('--disciplina', default=None)
    est_sess.add_argument('--topico', default=None)
    est_sess.add_argument('--modo', default=None, choices=['livre', 'pomodoro'])
    est_sess.set_defaults(func=_cmd_estudos_sessao)

    est_rev = subparsers.add_parser('estudos-revisao', help='lista revisões pendentes ou marca uma como feita')
    est_rev.add_argument('--config', default=None)
    est_rev.add_argument('--progresso', default=None, help='id do progresso a marcar como revisado')
    est_rev.add_argument('--resultado', default=None)
    est_rev.set_defaults(func=_cmd_estudos_revisao)

    est_cont = subparsers.add_parser('estudos-conteudo', help='conteúdo programático extraído de um concurso')
    est_cont.add_argument('--config', default=None)
    est_cont.add_argument('--concurso', required=True)
    est_cont.set_defaults(func=_cmd_estudos_conteudo)

    est_perf = subparsers.add_parser('estudos-perfil', help='lista/atualiza o perfil de conhecimentos')
    est_perf.add_argument('--config', default=None)
    est_perf.add_argument('--disciplina', default=None)
    est_perf.add_argument('--rotulo', default=None)
    est_perf.add_argument('--nivel', default='nao_avaliado')
    est_perf.add_argument('--revisar', action='store_true')
    est_perf.add_argument('--confianca', default=None)
    est_perf.add_argument('--observacoes', default=None)
    est_perf.set_defaults(func=_cmd_estudos_perfil)

    est_cob = subparsers.add_parser('estudos-cobertura', help='cobertura de preparação de um concurso')
    est_cob.add_argument('--config', default=None)
    est_cob.add_argument('--concurso', required=True)
    est_cob.set_defaults(func=_cmd_estudos_cobertura)

    est_exp = subparsers.add_parser('estudos-exportar', help='exporta os dados pessoais de estudo')
    est_exp.add_argument('--config', default=None)
    est_exp.add_argument('--out', default=None)
    est_exp.set_defaults(func=_cmd_estudos_exportar)

    est_imp = subparsers.add_parser('estudos-importar', help='importa dados pessoais de estudo (com prévia)')
    est_imp.add_argument('--config', default=None)
    est_imp.add_argument('--file', required=True)
    est_imp.add_argument('--dry-run', action='store_true')
    est_imp.set_defaults(func=_cmd_estudos_importar)

    est_bak = subparsers.add_parser('estudos-backup', help='backup consistente do banco (com integridade)')
    est_bak.add_argument('--config', default=None)
    est_bak.add_argument('--dest', required=True)
    est_bak.set_defaults(func=_cmd_estudos_backup)

    fc = subparsers.add_parser('estudos-flashcard', help='flashcards: criar, revisar, arquivar, fila, estatísticas')
    fc.add_argument('--config', default=None)
    fc.add_argument('fc_action', nargs='?', default='list',
                    choices=['list', 'create', 'review', 'archive', 'fila', 'stats'])
    fc.add_argument('--frente', default=None)
    fc.add_argument('--verso', default=None)
    fc.add_argument('--disciplina', default=None)
    fc.add_argument('--topico', default=None)
    fc.add_argument('--id', default=None)
    fc.add_argument('--qualidade', type=int, default=None)
    fc.add_argument('--limit', type=int, default=20)
    fc.set_defaults(func=_cmd_pratica_flashcard)

    q = subparsers.add_parser('estudos-questao', help='questões: criar, responder, arquivar, listar')
    q.add_argument('--config', default=None)
    q.add_argument('q_action', nargs='?', default='list', choices=['list', 'create', 'answer', 'archive'])
    q.add_argument('--enunciado', default=None)
    q.add_argument('--alternativa', action='append', default=None, help='repita para cada alternativa')
    q.add_argument('--gabarito', default=None)
    q.add_argument('--disciplina', default=None)
    q.add_argument('--topico', default=None)
    q.add_argument('--comentario', default=None)
    q.add_argument('--id', default=None)
    q.add_argument('--resposta', default=None)
    q.set_defaults(func=_cmd_pratica_questao)

    sim = subparsers.add_parser('estudos-simulado', help='simulados: criar, responder, finalizar, resultado')
    sim.add_argument('--config', default=None)
    sim.add_argument('sim_action', nargs='?', default='list',
                     choices=['list', 'create', 'answer', 'finish', 'result'])
    sim.add_argument('--nome', default=None)
    sim.add_argument('--limit', type=int, default=10)
    sim.add_argument('--duracao', type=int, default=None, help='duração máxima em segundos')
    sim.add_argument('--seed', default=None)
    sim.add_argument('--id', default=None)
    sim.add_argument('--ordem', type=int, default=None)
    sim.add_argument('--resposta', default=None)
    sim.set_defaults(func=_cmd_pratica_simulado)

    perf = subparsers.add_parser('estudos-desempenho', help='desempenho agregado (tentativas e simulados)')
    perf.add_argument('--config', default=None)
    perf.set_defaults(func=_cmd_pratica_desempenho)

    return parser


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
