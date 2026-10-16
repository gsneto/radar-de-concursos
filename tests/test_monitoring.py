"""Monitoramento: migração v4, ciclos, classificação de mudanças e resumo."""

import sqlite3
import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from radar.collector import SOURCE_URL, collect
from radar.document_store import (
    SCHEMA_VERSION,
    connect_documents,
    migrate_document_schema,
    sync_v1_identifiers,
)
from radar.monitoring import run_cycle
from radar.storage import list_records, upsert_records

_FIXTURE = Path(__file__).parent / "fixtures" / "guajara-oficial.html"
_TS = "2026-10-15T12:00:00+00:00"


class SchemaV4Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "db.sqlite3")

    def _tables(self):
        with closing(sqlite3.connect(self.db)) as conn:
            return {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}

    def _columns(self, table):
        with closing(sqlite3.connect(self.db)) as conn:
            return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}

    def _user_version(self):
        with closing(sqlite3.connect(self.db)) as conn:
            return conn.execute("PRAGMA user_version").fetchone()[0]

    def test_new_database_migrates_to_v4_with_monitoring_tables(self):
        migrate_document_schema(self.db)
        self.assertEqual(self._user_version(), SCHEMA_VERSION)
        tables = self._tables()
        self.assertIn("ciclos_monitoramento", tables)
        self.assertIn("ciclos_fontes", tables)
        self.assertTrue({
            "id", "started_at", "finished_at", "state", "documents_found",
            "documents_new", "versions_new", "changes_pending", "last_success_at",
        }.issubset(self._columns("ciclos_monitoramento")))
        self.assertTrue({
            "id", "cycle_id", "source_url", "state", "checked_at", "last_success_at",
            "http_status", "error_code", "documents_found", "documents_new",
            "versions_new", "changes_pending", "coverage_state", "summary_json",
        }.issubset(self._columns("ciclos_fontes")))

    def test_migration_is_idempotent_and_integrity_holds(self):
        migrate_document_schema(self.db)
        migrate_document_schema(self.db)
        self.assertEqual(self._user_version(), SCHEMA_VERSION)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_v3_database_upgrades_additively(self):
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("DROP TABLE ciclos_fontes")
            conn.execute("DROP TABLE ciclos_monitoramento")
            conn.execute("PRAGMA user_version=3")
            conn.commit()
        migrate_document_schema(self.db)
        self.assertEqual(self._user_version(), SCHEMA_VERSION)
        self.assertIn("ciclos_fontes", self._tables())

    def test_future_version_is_rejected_without_touching_database(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("PRAGMA user_version=99")
            conn.commit()
        with self.assertRaises(ValueError):
            migrate_document_schema(self.db)
        self.assertEqual(self._user_version(), 99)

    def test_monitoring_status_reads_unmigrated_as_pending(self):
        from radar.document_store import monitoring_status
        with self.assertRaises(ValueError):
            monitoring_status(self.db)

    def test_monitoring_status_on_existing_v3_is_pending(self):
        from radar.document_store import monitoring_status
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("DROP TABLE ciclos_fontes")
            conn.execute("DROP TABLE ciclos_monitoramento")
            conn.execute("PRAGMA user_version=3")
            conn.commit()
        with self.assertRaises(ValueError):
            monitoring_status(self.db)


def _pdf_transport(body=b"%PDF-1.4\nvalid"):
    def transport(url, timeout, limit):
        return dict(status=200, final_url=url, content_type="application/pdf", peer_ip="8.8.8.8", body=body)
    return transport


def _html_transport(body):
    def transport(url, timeout, limit):
        return dict(status=200, final_url=url, content_type="text/html", peer_ip="8.8.8.8", body=body)
    return transport


def _source(fetch, links, source_url=SOURCE_URL):
    def discover(html, observation_id):
        return [dict(observation_id=observation_id, kind=kind, official_url=url, title=title,
                     discovery_url=source_url, discovery_method="automatico", discovered_at=_TS)
                for url, kind, title in links]
    return {"source_url": source_url, "fetch": fetch, "discover": discover}


class CycleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "db.sqlite3")
        upsert_records(self.db, collect(_FIXTURE.read_text(encoding="utf-8"), _TS))
        migrate_document_schema(self.db)

    def _version_count(self):
        with closing(connect_documents(self.db)) as conn:
            return conn.execute("SELECT count(*) FROM versoes_documento").fetchone()[0]

    def test_no_new_document_completes_cleanly(self):
        result = run_cycle(self.db, sources=[_source(lambda: "x", [])])
        self.assertEqual(result["state"], "concluido")
        self.assertEqual(result["documents_new"], 0)
        self.assertEqual(result["versions_new"], 0)

    def test_one_new_document_then_repeat_creates_no_duplicate(self):
        url = "https://guajaramirim.ro.gov.br/e.pdf"
        source = _source(lambda: "x", [(url, "edital", "Edital")])
        first = run_cycle(self.db, sources=[source], transport=_pdf_transport())
        self.assertEqual(first["documents_new"], 1)
        self.assertEqual(first["versions_new"], 1)
        second = run_cycle(self.db, sources=[source], transport=_pdf_transport())
        self.assertEqual(second["documents_new"], 0)
        self.assertEqual(second["versions_new"], 0)

    def test_volatile_telemetry_does_not_create_a_version(self):
        url = "https://guajaramirim.ro.gov.br/edital.html"
        source = _source(lambda: "x", [(url, "edital", "Edital")])
        run_cycle(self.db, sources=[source],
                  transport=_html_transport(b'<p>Edital</p><script>var a="bam.nr-data.net";</script>'))
        result = run_cycle(self.db, sources=[source], transport=_html_transport(
            b'<p>Edital</p><script>var a="bam.nr-data.net";var t=2;</script>'))
        self.assertEqual(result["versions_new"], 0)
        self.assertEqual(self._version_count(), 1)

    def test_substantive_change_creates_a_new_version_pending_analysis(self):
        url = "https://guajaramirim.ro.gov.br/edital.html"
        source = _source(lambda: "x", [(url, "edital", "Edital")])
        run_cycle(self.db, sources=[source], transport=_html_transport(b"<p>10 vagas</p>"))
        result = run_cycle(self.db, sources=[source], transport=_html_transport(b"<p>12 vagas</p>"))
        self.assertEqual(result["versions_new"], 1)
        self.assertEqual(result["sources"][0]["changes"], 1)
        self.assertGreaterEqual(result["changes_pending"], 1)

    def test_non_canonical_url_does_not_create_duplicate_new_document(self):
        # Fragmento na URL é aceito pela descoberta e normalizado por register_document;
        # a repetição não pode contar o mesmo documento como novo (falso alerta).
        url = "https://guajaramirim.ro.gov.br/e.pdf#secao"
        source = _source(lambda: "x", [(url, "edital", "Edital")])
        first = run_cycle(self.db, sources=[source], transport=_pdf_transport())
        second = run_cycle(self.db, sources=[source], transport=_pdf_transport())
        self.assertEqual(first["documents_new"], 1)
        self.assertEqual(second["documents_new"], 0)
        self.assertEqual(second["versions_new"], 0)

    def test_missing_link_does_not_mark_document_removed(self):
        url = "https://guajaramirim.ro.gov.br/e.pdf"
        present = _source(lambda: "x", [(url, "edital", "Edital")])
        run_cycle(self.db, sources=[present], transport=_pdf_transport())
        # A consulta seguinte não encontra mais o link: não é prova de remoção.
        gone = _source(lambda: "x", [])
        result = run_cycle(self.db, sources=[gone], transport=_pdf_transport())
        with closing(connect_documents(self.db)) as conn:
            documents = conn.execute("SELECT count(*) FROM documentos").fetchone()[0]
            versions = conn.execute("SELECT count(*) FROM versoes_documento").fetchone()[0]
        self.assertEqual(documents, 1)
        self.assertEqual(versions, 1)
        self.assertEqual(result["documents_new"], 0)

    def test_new_amendment_is_registered_as_separate_document(self):
        links = [("https://guajaramirim.ro.gov.br/edital.pdf", "edital", "Edital"),
                 ("https://guajaramirim.ro.gov.br/retificacao.pdf", "retificacao", "Retificação")]
        result = run_cycle(self.db, sources=[_source(lambda: "x", links)], transport=_pdf_transport())
        self.assertEqual(result["documents_new"], 2)
        with closing(connect_documents(self.db)) as conn:
            kinds = {row[0] for row in conn.execute("SELECT kind FROM documentos")}
            related = conn.execute("SELECT count(*) FROM eventos_documentais WHERE related_document_id IS NOT NULL").fetchone()[0]
        self.assertEqual(kinds, {"edital", "retificacao"})
        self.assertEqual(related, 0)

    def test_inaccessible_document_preserves_previous_version(self):
        url = "https://guajaramirim.ro.gov.br/e.pdf"
        source = _source(lambda: "x", [(url, "edital", "Edital")])
        run_cycle(self.db, sources=[source], transport=_pdf_transport())
        before = self._version_count()

        def failing(url, timeout, limit):
            raise TimeoutError("sem resposta")

        result = run_cycle(self.db, sources=[source], transport=failing)
        self.assertEqual(result["state"], "parcial")
        self.assertEqual(self._version_count(), before)
        self.assertTrue(result["sources"][0]["errors"])

    def test_source_timeout_records_failure(self):
        def boom():
            raise TimeoutError("fonte fora do ar")

        result = run_cycle(self.db, sources=[_source(boom, [])])
        self.assertEqual(result["state"], "falhou")
        self.assertEqual(result["sources"][0]["state"], "falhou")
        self.assertEqual(result["sources"][0]["error_code"], "TimeoutError")

    def test_interrupted_cycle_is_recovered(self):
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute("INSERT INTO ciclos_monitoramento (id,started_at,state) VALUES ('old',?,'em_andamento')", (_TS,))
        run_cycle(self.db, sources=[_source(lambda: "x", [])])
        with closing(connect_documents(self.db)) as conn:
            state = conn.execute("SELECT state FROM ciclos_monitoramento WHERE id='old'").fetchone()[0]
        self.assertEqual(state, "interrompido")

    def test_failure_preserves_last_success(self):
        from radar.document_store import monitoring_status
        run_cycle(self.db, sources=[_source(lambda: "x", [])])

        def boom():
            raise TimeoutError("caiu")

        run_cycle(self.db, sources=[_source(boom, [])])
        with closing(connect_documents(self.db)) as conn:
            successes = [row[0] for row in conn.execute(
                "SELECT last_success_at FROM ciclos_fontes ORDER BY checked_at")]
        self.assertIsNotNone(successes[0])
        self.assertEqual(successes[-1], successes[0], "falha preserva o último sucesso da fonte")
        status = monitoring_status(self.db)
        self.assertEqual(status["last_cycle"]["state"], "falhou")
        self.assertIsNotNone(status["sources"][0]["last_success_at"])

    def test_one_source_failure_does_not_block_others(self):
        other = "https://guajaramirim.ro.gov.br/outra/"
        upsert_records(self.db, [{"source_url": other, "competition_id": "X/2026",
                                 "role": "Cargo", "verified_at": _TS}])

        def boom():
            raise TimeoutError("caiu")

        result = run_cycle(self.db, sources=[_source(boom, []), _source(lambda: "y", [], source_url=other)])
        states = {s["source_url"]: s["state"] for s in result["sources"]}
        self.assertEqual(result["state"], "parcial")
        self.assertEqual(states[SOURCE_URL], "falhou")
        self.assertEqual(states[other], "concluido")

    def test_unknown_candidate_is_skipped_without_failing_cycle(self):
        url = "https://guajaramirim.ro.gov.br/x.pdf"
        result = run_cycle(self.db, sources=[_source(lambda: "x", [(url, "invalido", "??")])])
        self.assertEqual(result["documents_new"], 0)
        self.assertEqual(result["state"], "concluido")

    def test_missing_database_raises(self):
        with self.assertRaises(ValueError):
            run_cycle(str(Path(self.tmp.name) / "ausente.sqlite3"))

    def test_analyze_failure_marks_version_without_losing_it(self):
        url = "https://guajaramirim.ro.gov.br/e.pdf"
        source = _source(lambda: "x", [(url, "edital", "Edital")])
        run_cycle(self.db, sources=[source], transport=_pdf_transport(b"%PDF-1.4\nnao e pdf"), analyze=True)
        with closing(connect_documents(self.db)) as conn:
            rows = conn.execute("SELECT extraction_state,error_code FROM versoes_documento").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "falhou")

    def test_analyze_creates_proposals_without_validating(self):
        annex = (Path(__file__).parent / "fixtures" / "documents" / "edital-guajara-anexo-i.html").read_bytes()
        url = "https://guajaramirim.ro.gov.br/edital.html"
        source = _source(lambda: "x", [(url, "edital", "Edital")])
        run_cycle(self.db, sources=[source], transport=_html_transport(annex), analyze=True)
        with closing(connect_documents(self.db)) as conn:
            states = [row[0] for row in conn.execute("SELECT extraction_state FROM versoes_documento")]
            proposals = conn.execute("SELECT count(*) FROM propostas_campo").fetchone()[0]
            validations = conn.execute("SELECT count(*) FROM revisoes_campo").fetchone()[0]
        self.assertEqual(states, ["parcial"])
        self.assertGreater(proposals, 0)
        self.assertEqual(validations, 0)


class DouSourceIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "db.sqlite3")
        migrate_document_schema(self.db)

    def _edition_html(self):
        item = {"pubName": "DO3", "urlTitle": "edital-concurso-1-999", "title": "EDITAL DE CONCURSO PÚBLICO Nº 1/2026",
                "artType": "Edital", "pubDate": "01/10/2026", "content":
                "O concurso público oferece 5 vagas para pessoas indígenas. Inscrições de 1 a 20/10/2026.",
                "hierarchyStr": "Ministério da Educação/UF X", "hierarchyList": ["Ministério da Educação", "UF X"]}
        payload = json.dumps({"dateUrl": "01-10-2026", "section": "DO3", "jsonArray": [item]}, ensure_ascii=False)
        return '<script>var x = ' + payload + ';</script>'

    def _dou_source(self):
        from radar.dou_source import DOU_COMPETITION_ID, DOU_SOURCE_URL, discover
        html = self._edition_html()
        return {"source_url": DOU_SOURCE_URL, "competition_id": DOU_COMPETITION_ID, "inline": True,
                "fetch": lambda: html, "discover": lambda h, observation_id: discover(h, observation_id)}

    def _edition_source(self, slug):
        from radar.dou_source import DOU_COMPETITION_ID, DOU_SOURCE_URL, discover
        item = {"pubName": "DO3", "urlTitle": slug, "title": "EDITAL DE CONCURSO PÚBLICO",
                "artType": "Edital", "pubDate": "01/10/2026", "content": "concurso público",
                "hierarchyStr": "Órgão X", "hierarchyList": ["Órgão X"]}
        payload = json.dumps({"dateUrl": "01-10-2026", "section": "DO3", "jsonArray": [item]}, ensure_ascii=False)
        html = '<script>var x = ' + payload + ';</script>'
        return {"source_url": DOU_SOURCE_URL, "competition_id": DOU_COMPETITION_ID, "inline": True,
                "fetch": lambda: html, "discover": lambda h, observation_id: discover(h, observation_id)}

    def test_dou_cycle_registers_documents_versions_and_is_idempotent(self):
        first = run_cycle(self.db, sources=[self._dou_source()], analyze=True)
        self.assertEqual(first["state"], "concluido")
        self.assertEqual(first["documents_new"], 1)
        self.assertEqual(first["versions_new"], 1)
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM observacoes_concurso").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM documentos").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM versoes_documento").fetchone()[0], 1)
            validations = conn.execute("SELECT count(*) FROM revisoes_campo").fetchone()[0]
        self.assertEqual(validations, 0)
        # Reexecução sem mudanças não cria documento nem versão novos.
        second = run_cycle(self.db, sources=[self._dou_source()], analyze=True)
        self.assertEqual(second["documents_new"], 0)
        self.assertEqual(second["versions_new"], 0)

    def test_dou_does_not_write_v1_concursos(self):
        run_cycle(self.db, sources=[self._dou_source()], analyze=True)
        self.assertEqual(list_records(self.db), [])

    def test_previous_edition_document_is_not_reversioned(self):
        # Regressão: uma edição nova não pode rebaixar (nem contar como mudança)
        # documentos DOU de edições anteriores — e não deve tentar baixá-los.
        run_cycle(self.db, sources=[self._edition_source("edital-a-111")])
        calls = []

        def transport(url, timeout, limit):
            calls.append(url)
            raise TimeoutError("não deveria baixar páginas de artigos DOU")

        result = run_cycle(self.db, sources=[self._edition_source("edital-b-222")], transport=transport)
        self.assertEqual(result["documents_new"], 1)
        self.assertEqual(result["versions_new"], 1)
        self.assertEqual(result["sources"][0]["changes"], 0)
        self.assertEqual(calls, [], "documentos inline não são baixados da página")
        with closing(connect_documents(self.db)) as conn:
            doc_a = conn.execute("SELECT id FROM documentos WHERE official_url LIKE '%edital-a-111'").fetchone()[0]
            versions_a = conn.execute("SELECT count(*) FROM versoes_documento WHERE document_id=?", (doc_a,)).fetchone()[0]
            total_versions = conn.execute("SELECT count(*) FROM versoes_documento").fetchone()[0]
        self.assertEqual(versions_a, 1)
        self.assertEqual(total_versions, 2)

    def test_dou_failure_does_not_block_guajara(self):
        upsert_records(self.db, collect(_FIXTURE.read_text(encoding="utf-8"), _TS))
        migrate_document_schema(self.db)

        def boom():
            raise TimeoutError("dou fora do ar")

        dou = self._dou_source()
        dou["fetch"] = boom
        guajara = _source(lambda: "x", [])
        result = run_cycle(self.db, sources=[guajara, dou])
        states = {s["source_url"]: s["state"] for s in result["sources"]}
        self.assertEqual(states[SOURCE_URL], "concluido")
        self.assertEqual(states[dou["source_url"]], "falhou")
        self.assertEqual(result["state"], "parcial")


class MonitorCliTest(unittest.TestCase):
    def test_monitor_requires_migrated_schema(self):
        from radar.__main__ import main
        with tempfile.TemporaryDirectory() as temp:
            db = str(Path(temp) / "r.sqlite3")
            with self.assertRaises(ValueError):
                main(["monitor", "--db", db])

    def test_parser_wires_monitor_command(self):
        from radar.__main__ import build_parser
        args = build_parser().parse_args(["monitor", "--db", "x", "--analyze"])
        self.assertTrue(args.analyze)
        self.assertTrue(callable(args.func))

    def test_parser_wires_role_command(self):
        from radar.__main__ import build_parser
        args = build_parser().parse_args(["documents-role", "--db", "x", "--contest-id", "c",
                                          "--observation-id", "o", "--name", "Cargo"])
        self.assertTrue(callable(args.func))


if __name__ == "__main__":
    unittest.main()
