"""Fila de confirmação documental: enqueue, lotes, estados, retomada e reconciliação."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from radar import confirmation
from radar.document_store import (
    connect_documents, ensure_observation, migrate_document_schema, register_document,
)
from radar.storage import list_records

_TS = "2026-10-16T12:00:00+00:00"


def _candidate(pid, title, *, uf="SP", cargos="Vários Cargos", aberto=True, dias=24, url=None):
    return {
        "pci_id": pid, "competition_id": f"pci-{pid}", "title": title, "uf": uf,
        "regiao": "SUDESTE", "cargos_resumo": cargos, "vagas_salario": "10 vagas",
        "formacao": "Superior", "data_inicio": "2026-09-21", "data_fim": "2026-11-09",
        "aberto": aberto, "dias_restantes": dias,
        "url": url or f"https://www.pciconcursos.com.br/noticias/{pid}",
    }


class QueueTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "db.sqlite3")
        migrate_document_schema(self.db)

    def _seed_candidate(self, candidate):
        observation_id = ensure_observation(self.db, candidate["url"], candidate["competition_id"])
        register_document(self.db, {
            "observation_id": observation_id, "kind": "outro", "official_url": candidate["url"],
            "title": candidate["title"], "discovery_url": candidate["url"],
            "discovery_method": "automatico", "discovered_at": _TS,
            "issuer": "PCI Concursos (agregador)",
            "inline_content": b"<p>descoberta</p>", "inline_content_type": "text/html"})
        candidate = dict(candidate, observation_id=observation_id)
        return candidate


class SchemaV5Test(QueueTestBase):
    def test_migrates_to_v5_with_queue_table(self):
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 9)
            self.assertIsNotNone(conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='fila_confirmacao'").fetchone())
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_v4_database_upgrades_additively(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("DROP TABLE fila_confirmacao")
            conn.execute("PRAGMA user_version=4")
            conn.commit()
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 9)

    def test_v6_adds_document_type_column(self):
        with closing(sqlite3.connect(self.db)) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(documentos)")}
        self.assertIn("tipo_documental", cols)

    def test_v5_database_upgrades_to_current(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("ALTER TABLE documentos DROP COLUMN tipo_documental")
            conn.execute("PRAGMA user_version=5")
            conn.commit()
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 9)
            cols = {row[1] for row in conn.execute("PRAGMA table_info(documentos)")}
        self.assertIn("tipo_documental", cols)


class EnqueueTest(QueueTestBase):
    def test_enqueue_from_candidates_creates_pending_rows(self):
        candidates = [self._seed_candidate(_candidate(1, "A")), self._seed_candidate(_candidate(2, "B"))]
        created = confirmation.enqueue_from_candidates(self.db, candidates)
        self.assertEqual(created, 2)
        status = confirmation.queue_status(self.db)
        self.assertEqual(status["counts"]["pendente"], 2)

    def test_enqueue_is_idempotent(self):
        candidates = [self._seed_candidate(_candidate(1, "A"))]
        confirmation.enqueue_from_candidates(self.db, candidates)
        self.assertEqual(confirmation.enqueue_from_candidates(self.db, candidates), 0)

    def test_enqueue_pending_from_existing_observations(self):
        self._seed_candidate(_candidate(1, "A"))
        self._seed_candidate(_candidate(2, "B"))
        created = confirmation.enqueue_pending(self.db)
        self.assertEqual(created, 2)
        self.assertEqual(confirmation.enqueue_pending(self.db), 0)

    def test_enqueue_pending_counts_once_per_observation(self):
        candidate = self._seed_candidate(_candidate(1, "A"))
        # Segundo documento PCI para a MESMA observação não pode supercontar.
        register_document(self.db, {
            "observation_id": candidate["observation_id"], "kind": "outro",
            "official_url": candidate["url"] + "-extra", "title": candidate["title"],
            "discovery_url": candidate["url"] + "-extra", "discovery_method": "automatico",
            "discovered_at": _TS, "issuer": "PCI Concursos (agregador)"})
        self.assertEqual(confirmation.enqueue_pending(self.db), 1)

    def test_enqueue_skips_candidates_without_observation(self):
        good = self._seed_candidate(_candidate(1, "A"))
        bad = dict(_candidate(2, "B"), observation_id="inexistente")
        self.assertEqual(confirmation.enqueue_from_candidates(self.db, [bad, good]), 1)


class PriorityTest(unittest.TestCase):
    def test_ti_and_indigenous_raise_priority(self):
        ti, reason = confirmation.compute_priority(_candidate(1, "Prefeitura", cargos="Analista de Sistemas"))
        plain, _ = confirmation.compute_priority(_candidate(2, "Prefeitura", cargos="Merendeira"))
        self.assertGreater(ti, plain)
        self.assertIn("cargo_ti", reason)

    def test_indigenous_mention(self):
        score, reason = confirmation.compute_priority(_candidate(1, "X", cargos="vagas para pessoas indígenas"))
        self.assertIn("mencao_indigena", reason)


class BatchTest(QueueTestBase):
    def _resolver(self, result):
        return lambda candidate: result

    def test_page_only_resolution_marks_fonte_oficial_localizada(self):
        candidate = self._seed_candidate(_candidate(1, "C"))
        confirmation.enqueue_from_candidates(self.db, [candidate])
        resolver = lambda c: {"official_url": "https://www.quadrix.org.br/informacoes/1/",
                              "source": "Instituto Quadrix", "title": "Página do concurso",
                              "no_download": True}
        summary = confirmation.process_batch(self.db, resolvers=[resolver], limit=5)
        self.assertEqual(summary["states"].get("fonte_oficial_localizada"), 1)
        item = confirmation.get_item(self.db, candidate["observation_id"])
        self.assertEqual(item["state"], "fonte_oficial_localizada")
        self.assertIsNone(item["document_id"])

    def test_register_official_sets_document_type(self):
        candidate = self._seed_candidate(_candidate(1, "C"))
        confirmation.enqueue_from_candidates(self.db, [candidate])
        resolver = lambda c: {"official_url": "https://www.in.gov.br/web/dou/-/edital-x-1",
                              "source": "DOU", "title": "Edital de Abertura nº 1"}
        confirmation.process_batch(self.db, resolvers=[resolver], limit=5,
                                   transport=_html_transport(b"<p>10 vagas imediatas.</p>"))
        with closing(connect_documents(self.db)) as conn:
            tipos = {r[0] for r in conn.execute("SELECT tipo_documental FROM documentos")}
        self.assertIn("edital_abertura", tipos)

    def test_select_batch_orders_by_priority_and_limits(self):
        candidates = [
            self._seed_candidate(_candidate(1, "Comum", cargos="Merendeira")),
            self._seed_candidate(_candidate(2, "TI", cargos="Analista de Sistemas")),
            self._seed_candidate(_candidate(3, "Outro", cargos="Professor")),
        ]
        confirmation.enqueue_from_candidates(self.db, candidates)
        batch = confirmation.select_batch(self.db, limit=2)
        self.assertEqual(len(batch), 2)
        self.assertEqual(batch[0]["competition_id"], "pci-2")  # prioridade TI

    def test_official_resolution_registers_and_marks_review(self):
        candidate = self._seed_candidate(_candidate(1, "Concurso X"))
        confirmation.enqueue_from_candidates(self.db, [candidate])
        resolver = self._resolver({"official_url": "https://www.in.gov.br/web/dou/-/edital-x-1",
                                   "source": "DOU", "title": "Edital X", "confidence": "alta"})
        summary = confirmation.process_batch(self.db, resolvers=[resolver], limit=5,
                                             transport=_html_transport(b"<p>10 vagas imediatas.</p>"))
        self.assertEqual(summary["states"].get("revisao_pendente"), 1)
        item = confirmation.get_item(self.db, candidate["observation_id"])
        self.assertEqual(item["state"], "revisao_pendente")
        self.assertIsNotNone(item["document_id"])
        with closing(connect_documents(self.db)) as conn:
            n_prop = conn.execute("SELECT count(*) FROM propostas_campo").fetchone()[0]
            n_rev = conn.execute("SELECT count(*) FROM revisoes_campo").fetchone()[0]
        self.assertGreater(n_prop, 0)
        self.assertEqual(n_rev, 0)  # nada auto-validado

    def test_no_reference_marks_nao_localizado(self):
        candidate = self._seed_candidate(_candidate(1, "Sem Referência"))
        confirmation.enqueue_from_candidates(self.db, [candidate])
        summary = confirmation.process_batch(self.db, resolvers=[self._resolver(None)], limit=5)
        self.assertEqual(summary["states"].get("nao_localizado"), 1)
        item = confirmation.get_item(self.db, candidate["observation_id"])
        self.assertIsNotNone(item["next_attempt_at"])  # agendado para retentativa

    def test_ambiguous_marks_inconclusivo(self):
        candidate = self._seed_candidate(_candidate(1, "Ambíguo"))
        confirmation.enqueue_from_candidates(self.db, [candidate])
        resolver = self._resolver({"official_url": "https://www.in.gov.br/web/dou/-/x-1",
                                   "source": "DOU", "ambiguity": "título parcial", "reason": "fraco"})
        summary = confirmation.process_batch(self.db, resolvers=[resolver], limit=5)
        self.assertEqual(summary["states"].get("inconclusivo"), 1)
        self.assertEqual(confirmation.get_item(self.db, candidate["observation_id"])["ambiguity"],
                         "título parcial")

    def test_download_failure_keeps_reference_as_documento_localizado(self):
        candidate = self._seed_candidate(_candidate(1, "Doc inacessível"))
        confirmation.enqueue_from_candidates(self.db, [candidate])
        resolver = self._resolver({"official_url": "https://www.in.gov.br/web/dou/-/x-1",
                                   "source": "DOU", "title": "Edital"})

        def failing_transport(url, timeout, limit):
            raise TimeoutError("caiu")

        summary = confirmation.process_batch(self.db, resolvers=[resolver], limit=5,
                                             transport=failing_transport)
        self.assertEqual(summary["states"].get("documento_localizado"), 1)
        item = confirmation.get_item(self.db, candidate["observation_id"])
        self.assertEqual(item["state"], "documento_localizado")
        self.assertTrue(item["official_url"])

    def test_one_failure_does_not_stop_the_batch(self):
        candidates = [self._seed_candidate(_candidate(i, f"C{i}")) for i in range(1, 4)]
        confirmation.enqueue_from_candidates(self.db, candidates)

        calls = {"n": 0}

        def resolver(candidate):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("resolver falhou")
            return None

        summary = confirmation.process_batch(self.db, resolvers=[resolver], limit=5)
        self.assertEqual(summary["processed"], 3)
        self.assertEqual(summary["states"].get("falhou"), 1)       # falha técnica isolada
        self.assertEqual(summary["states"].get("nao_localizado"), 2)  # demais seguem

    def test_limit_bounds_processing(self):
        candidates = [self._seed_candidate(_candidate(i, f"C{i}")) for i in range(1, 6)]
        confirmation.enqueue_from_candidates(self.db, candidates)
        summary = confirmation.process_batch(self.db, resolvers=[self._resolver(None)], limit=2)
        self.assertEqual(summary["processed"], 2)
        self.assertEqual(confirmation.queue_status(self.db)["counts"]["pendente"], 3)

    def test_idempotent_second_run_skips_completed(self):
        candidate = self._seed_candidate(_candidate(1, "C"))
        confirmation.enqueue_from_candidates(self.db, [candidate])
        resolver = self._resolver({"official_url": "https://www.in.gov.br/web/dou/-/x-1",
                                   "source": "DOU", "title": "Edital"})
        confirmation.process_batch(self.db, resolvers=[resolver], limit=5,
                                   transport=_html_transport(b"<p>5 vagas imediatas.</p>"))
        second = confirmation.process_batch(self.db, resolvers=[resolver], limit=5,
                                            transport=_html_transport(b"<p>5 vagas imediatas.</p>"))
        self.assertEqual(second["processed"], 0)  # revisao_pendente não é reprocessado

    def test_dry_run_selects_without_processing(self):
        self._seed_candidate(_candidate(1, "C"))
        confirmation.enqueue_pending(self.db)
        batch = confirmation.select_batch(self.db, limit=5)
        self.assertEqual(len(batch), 1)
        self.assertEqual(confirmation.queue_status(self.db)["counts"]["pendente"], 1)

    def test_v1_contract_untouched(self):
        self._seed_candidate(_candidate(1, "C"))
        confirmation.enqueue_pending(self.db)
        confirmation.process_batch(self.db, resolvers=[self._resolver(None)], limit=5)
        self.assertEqual(list_records(self.db), [])

    def test_accepts_resolver_objects_with_resolve_method(self):
        candidate = self._seed_candidate(_candidate(1, "C"))
        confirmation.enqueue_from_candidates(self.db, [candidate])

        class Resolver:
            name = "fake"

            def resolve(self, candidate):
                return {"official_url": "https://www.in.gov.br/web/dou/-/x-1", "source": "DOU",
                        "title": "Edital"}

        summary = confirmation.process_batch(self.db, resolvers=[Resolver()], limit=5,
                                             transport=_html_transport(b"<p>3 vagas imediatas.</p>"))
        self.assertEqual(summary["states"].get("revisao_pendente"), 1)

    def test_document_without_proposals_is_processado(self):
        candidate = self._seed_candidate(_candidate(1, "C"))
        confirmation.enqueue_from_candidates(self.db, [candidate])
        resolver = self._resolver({"official_url": "https://www.in.gov.br/web/dou/-/x-1",
                                   "source": "DOU", "title": "Página do concurso"})
        summary = confirmation.process_batch(self.db, resolvers=[resolver], limit=5,
                                             transport=_html_transport(b"<p>texto sem campos extraiveis</p>"))
        self.assertEqual(summary["states"].get("documento_processado"), 1)
        item = confirmation.get_item(self.db, candidate["observation_id"])
        self.assertEqual(item["state"], "documento_processado")
        self.assertIsNotNone(item["document_id"])


class RecoverStaleTest(QueueTestBase):
    def test_stale_processing_returns_to_pending(self):
        candidate = self._seed_candidate(_candidate(1, "C"))
        confirmation.enqueue_from_candidates(self.db, [candidate])
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute("UPDATE fila_confirmacao SET state='em_processamento', last_attempt_at=?",
                         ("2020-01-01T00:00:00+00:00",))
        recovered = confirmation.recover_stale(self.db, stale_minutes=60)
        self.assertEqual(recovered, 1)
        self.assertEqual(confirmation.get_item(self.db, candidate["observation_id"])["state"], "pendente")

    def test_fresh_processing_is_not_recovered(self):
        candidate = self._seed_candidate(_candidate(1, "C"))
        confirmation.enqueue_from_candidates(self.db, [candidate])
        confirmation._mark_processing(self.db, candidate["observation_id"], _TS)
        item = confirmation.get_item(self.db, candidate["observation_id"])
        self.assertEqual(item["last_attempt_at"], _TS)  # marcação registra a tentativa
        self.assertEqual(confirmation.recover_stale(self.db, stale_minutes=99999, now=_TS), 0)


class RetryTest(QueueTestBase):
    def test_due_retryable_state_is_reselected(self):
        candidate = self._seed_candidate(_candidate(1, "C"))
        confirmation.enqueue_from_candidates(self.db, [candidate])
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute(
                "UPDATE fila_confirmacao SET state='inconclusivo', next_attempt_at=? WHERE observation_id=?",
                ("2020-01-01T00:00:00+00:00", candidate["observation_id"]))
        self.assertEqual(len(confirmation.select_batch(self.db, limit=5, now=_TS)), 1)

    def test_future_retryable_state_is_skipped(self):
        candidate = self._seed_candidate(_candidate(1, "C"))
        confirmation.enqueue_from_candidates(self.db, [candidate])
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute(
                "UPDATE fila_confirmacao SET state='documento_localizado', next_attempt_at=? WHERE observation_id=?",
                ("2999-01-01T00:00:00+00:00", candidate["observation_id"]))
        self.assertEqual(confirmation.select_batch(self.db, limit=5, now=_TS), [])


class IsolationTest(QueueTestBase):
    def test_unexpected_error_in_marking_does_not_stop_batch(self):
        candidates = [self._seed_candidate(_candidate(i, f"C{i}")) for i in range(1, 4)]
        confirmation.enqueue_from_candidates(self.db, candidates)
        original = confirmation._mark_processing
        calls = {"n": 0}

        def flaky(db_path, observation_id, now):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            return original(db_path, observation_id, now)

        with mock.patch.object(confirmation, "_mark_processing", flaky):
            summary = confirmation.process_batch(self.db, resolvers=[lambda c: None], limit=5)
        self.assertEqual(summary["processed"], 3)
        self.assertEqual(summary["states"].get("falhou"), 1)
        self.assertEqual(summary["states"].get("nao_localizado"), 2)
        self.assertEqual(len(summary["errors"]), 1)


class ReconcileTest(QueueTestBase):
    def test_reconcile_classifies_new_and_coincident(self):
        # Candidato PCI
        pci = self._seed_candidate(_candidate(1, "Câmara de Boituva"))
        confirmation.enqueue_from_candidates(self.db, [pci])
        # Documento de outra fonte com o mesmo título
        other = ensure_observation(self.db, "https://conhecimento.fgv.br/concursos/x", "x")
        register_document(self.db, {"observation_id": other, "kind": "edital",
            "official_url": "https://conhecimento.fgv.br/concursos/x", "title": "Câmara de Boituva",
            "discovery_url": "https://conhecimento.fgv.br/concursos/x", "discovery_method": "automatico",
            "discovered_at": _TS, "issuer": "FGV Conhecimento"})
        report = confirmation.reconcile(self.db)
        self.assertEqual(report["coincidente"], 1)
        self.assertEqual(report["novo"], 0)

    def test_reconcile_flags_conflicting_issuers_as_ambiguous(self):
        pci = self._seed_candidate(_candidate(1, "Câmara de Boituva"))
        confirmation.enqueue_from_candidates(self.db, [pci])
        for slug, issuer in (("a", "FGV Conhecimento"), ("b", "DOU")):
            oid = ensure_observation(self.db, f"https://x/{slug}", slug)
            register_document(self.db, {"observation_id": oid, "kind": "edital",
                "official_url": f"https://x/{slug}", "title": "Câmara de Boituva",
                "discovery_url": f"https://x/{slug}", "discovery_method": "automatico",
                "discovered_at": _TS, "issuer": issuer})
        report = confirmation.reconcile(self.db)
        self.assertEqual(report["ambiguo"], 1)
        self.assertEqual(report["coincidente"], 0)

    def test_official_match_preserves_pci_provenance(self):
        # A fonte que confirma não apaga a descoberta original (PCI).
        candidate = self._seed_candidate(_candidate(1, "C"))
        confirmation.enqueue_from_candidates(self.db, [candidate])
        resolver = lambda c: {"official_url": "https://www.in.gov.br/web/dou/-/x-1",
                              "source": "DOU", "title": "Edital"}
        confirmation.process_batch(self.db, resolvers=[resolver], limit=5,
                                   transport=_html_transport(b"<p>10 vagas imediatas.</p>"))
        with closing(connect_documents(self.db)) as conn:
            issuers = {r[0] for r in conn.execute("SELECT issuer FROM documentos")}
        self.assertIn("PCI Concursos (agregador)", issuers)  # proveniência preservada
        self.assertIn("DOU", issuers)


class MetricsTest(QueueTestBase):
    def test_metrics_count_distinct_documents(self):
        candidate = self._seed_candidate(_candidate(1, "C"))
        confirmation.enqueue_from_candidates(self.db, [candidate])
        resolver = lambda c: {"official_url": "https://www.in.gov.br/web/dou/-/x-1",
                              "source": "DOU", "title": "Edital"}
        confirmation.process_batch(self.db, resolvers=[resolver], limit=5,
                                   transport=_html_transport(b"<p>10 vagas imediatas.</p>"))
        m = confirmation.metrics(self.db)
        self.assertEqual(m["selected"], 1)
        self.assertGreaterEqual(m["documents_found"], 1)
        self.assertEqual(m["documents_recovered"], 1)
        self.assertGreaterEqual(m["proposals"], 1)
        self.assertEqual(m["reviews"], 0)  # nada auto-validado
        self.assertIn("by_source", m)

    def test_source_metrics_break_down_by_issuer(self):
        candidate = self._seed_candidate(_candidate(1, "C"))
        confirmation.enqueue_from_candidates(self.db, [candidate])
        resolver = lambda c: {"official_url": "https://www.in.gov.br/web/dou/-/x-1",
                              "source": "DOU", "title": "Edital"}
        confirmation.process_batch(self.db, resolvers=[resolver], limit=5,
                                   transport=_html_transport(b"<p>10 vagas imediatas.</p>"))
        by_source = confirmation.metrics(self.db)["by_source"]
        self.assertIn("DOU", by_source)
        self.assertEqual(by_source["DOU"]["recovered"], 1)
        self.assertGreaterEqual(by_source["DOU"]["proposals"], 1)

    def test_priority_report_is_explainable(self):
        candidates = [
            self._seed_candidate(_candidate(1, "Concurso TI", cargos="Analista de Sistemas")),
            self._seed_candidate(_candidate(2, "Concurso Comum", cargos="Merendeira")),
        ]
        confirmation.enqueue_from_candidates(self.db, candidates)
        report = confirmation.priority_report(self.db)
        self.assertEqual(len(report), 2)
        self.assertEqual(report[0]["competition_id"], "pci-1")  # TI primeiro
        self.assertIn("cargo_ti", report[0]["signals"])
        self.assertIn("priority_score", report[0])


def _html_transport(body):
    def transport(url, timeout, limit):
        return dict(status=200, final_url=url, content_type="text/html", peer_ip="8.8.8.8", body=body)
    return transport


class OpportunityTest(unittest.TestCase):
    def test_immediate_indigenous_with_si_is_top_tier(self):
        c = confirmation.classify_opportunity(
            {"indigenous_vacancies": 2, "indigenous_reserve_vacancies": 0,
             "si_compatibility": "aceito_expressamente"})
        self.assertEqual(c["vacancy"], "vaga_indigena_imediata")
        self.assertEqual(c["tier"], 1)
        self.assertIn("si_aceito_expressamente", c["signals"])

    def test_reserve_indigenous_is_not_immediate(self):
        c = confirmation.classify_opportunity(
            {"indigenous_vacancies": 0, "indigenous_reserve_vacancies": 3,
             "si_compatibility": "abrangido_por_categoria"})
        self.assertEqual(c["vacancy"], "vaga_indigena_reserva")
        self.assertNotEqual(c["vacancy"], "vaga_indigena_imediata")
        self.assertEqual(c["tier"], 2)

    def test_unknown_indigenous_is_not_zero(self):
        c = confirmation.classify_opportunity({"si_compatibility": "ambiguo"})
        self.assertEqual(c["vacancy"], "vaga_indigena_desconhecida")
        self.assertIn("vaga_indigena_nao_extraida", c["signals"])

    def test_partial_indigenous_data_is_unknown_not_absence(self):
        # Regressão: imediato=0 conhecido, reserva não extraída → desconhecido (não "sem vaga").
        c = confirmation.classify_opportunity({"indigenous_vacancies": 0})
        self.assertEqual(c["vacancy"], "vaga_indigena_desconhecida")

    def test_both_known_zero_is_confirmed_absence(self):
        c = confirmation.classify_opportunity(
            {"indigenous_vacancies": 0, "indigenous_reserve_vacancies": 0})
        self.assertEqual(c["vacancy"], "sem_vaga_indigena")

    def test_si_incompatible_is_lower(self):
        c = confirmation.classify_opportunity(
            {"indigenous_vacancies": 1, "si_compatibility": "incompativel_com_requisito_explicito"})
        self.assertEqual(c["si"], "si_incompativel")
        self.assertEqual(c["tier"], 3)  # vaga imediata, mas formação incompatível

    def test_role_opportunities_orders_by_tier(self):
        import tempfile
        from pathlib import Path
        from radar.document_store import (connect_documents, migrate_document_schema,
                                          ensure_observation, register_document, record_version,
                                          record_analysis, ensure_role)
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        db = str(Path(tmp.name) / "db.sqlite3"); migrate_document_schema(db)
        obs = ensure_observation(db, "https://www.quadrix.org.br/informacoes/1/", "quadrix-1")
        with closing(connect_documents(db)) as conn:
            contest = conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                   (obs,)).fetchone()[0]
        doc = register_document(db, dict(observation_id=obs, kind="outro",
            official_url="https://anexos-r2.selecao.net.br/uploads/x/e.pdf", title="Edital",
            discovery_url="https://www.quadrix.org.br/", discovery_method="automatico",
            discovered_at=_TS))
        block = dict(page_number=2, locator="p", start_offset=0, end_offset=1, text="x")
        role = ensure_role(db, contest, obs, "Analista de Informática", code="404")
        proposals = []
        for field, val in (("indigenous_vacancies", 0), ("indigenous_reserve_vacancies", 2),
                           ("si_compatibility", "aceito_expressamente")):
            proposals.append(dict(contest_id=contest, role_id=role, field_name=field,
                value_json=json.dumps(val), value_type="string" if field == "si_compatibility" else "integer",
                extraction_method="t", ambiguity_reason="associado",
                evidence=dict(block_index=0, quote="x", start_offset=0, end_offset=1)))
        version = record_version(db, doc, b"%PDF-1.4 x", dict(fetched_at=_TS,
            fetched_url="https://anexos-r2.selecao.net.br/uploads/x/e.pdf", content_type="application/pdf"))
        record_analysis(db, version, [block], proposals)
        opps = confirmation.role_opportunities(db, contest)
        self.assertEqual(len(opps), 1)
        self.assertEqual(opps[0]["code"], "404")
        self.assertEqual(opps[0]["indigenous_reserve_vacancies"], 2)
        self.assertEqual(opps[0]["classification"]["tier"], 2)


if __name__ == "__main__":
    unittest.main()
