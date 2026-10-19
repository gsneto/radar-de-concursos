"""Fechamento do backend (Fase 44): contrato, prontidão, segurança e estados."""

import io
import json
import os
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import closing
from datetime import datetime, timedelta, timezone

from radar import api_contract, budget, ops, readiness, study_store
from radar.document_extract import extract_document
from radar.document_store import record_analysis
from radar.server import create_server
from tests.test_role_identity_f35 import NOW, add_document, make_db

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ContractTest(unittest.TestCase):
    def test_contrato_cobre_todas_as_rotas_do_servidor(self):
        result = api_contract.verify(os.path.join(ROOT, "radar", "server.py"))
        self.assertTrue(result["ok"], result)
        self.assertGreaterEqual(result["rotas_no_servidor"], 110)

    def test_documento_estruturado(self):
        document = api_contract.document()
        self.assertEqual(document["version"], "api_contract_v1")
        self.assertEqual(document["total"], len(api_contract.ROUTES))
        self.assertGreaterEqual(document["paths"], 105)
        self.assertIn("revisao", document["domains"])
        self.assertIn("estudos", document["domains"])

    def test_markdown_lista_todos_os_caminhos(self):
        markdown = api_contract.markdown().replace("{", "").replace("}", "")
        for route in api_contract.ROUTES:
            self.assertIn(route["path"].replace("{", "").replace("}", ""), markdown)
        self.assertIn("## Convenções", markdown)
        self.assertIn("GET /api/concursos", markdown.replace("`", ""))

    def test_rotas_de_escrita_declaram_idempotencia(self):
        for route in api_contract.ROUTES:
            if route["writes"]:
                self.assertIn(route["idempotent"], ("sim", "condicional", "nao"), route)


class ReadinessTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def test_relatorio_aprovado_em_base_integra(self):
        report = readiness.report(self.db)
        self.assertTrue(report["ready"])
        self.assertEqual(report["status"], "pronto_com_pendencias")
        checks = {item["id"]: item for item in report["checks"]}
        self.assertEqual(checks["integridade"]["status"], "aprovado")
        self.assertEqual(checks["chaves_estrangeiras"]["status"], "aprovado")
        self.assertEqual(checks["proveniencia"]["status"], "aprovado")
        self.assertEqual(checks["contrato_api"]["status"], "aprovado")
        self.assertTrue(report["api"]["ok"])

    def test_banco_inexistente_bloqueia(self):
        report = readiness.report(os.path.join(self.tmp.name, "nao-existe.sqlite3"))
        self.assertFalse(report["ready"])
        self.assertEqual(report["status"], "bloqueado")
        self.assertEqual(report["checks"][0]["status"], "reprovado")

    def test_violacao_de_chave_estrangeira_bloqueia(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO versoes_documento "
                         "(id,document_id,sha256,fetched_at,fetched_url,content_type,"
                         "byte_size,local_path,extraction_state) VALUES "
                         "('v-orfa','doc-inexistente',?,'2026-10-19','https://x/a','application/pdf',"
                         "1,'x','nao_iniciada')", ("a" * 64,))
        report = readiness.report(self.db)
        checks = {item["id"]: item for item in report["checks"]}
        self.assertEqual(checks["chaves_estrangeiras"]["status"], "reprovado")
        self.assertFalse(report["ready"])
        self.assertEqual(report["status"], "bloqueado")

    def test_proposta_sem_evidencia_bloqueia(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO propostas_campo "
                         "(id,contest_id,role_id,field_name,value_json,value_type,evidence_id,"
                         "extraction_method,ambiguity_reason,extracted_at) VALUES "
                         "('p-orfa','c1',NULL,'immediate_vacancies','1','integer','e-inexistente',"
                         "'regex',NULL,?)", (NOW,))
        report = readiness.report(self.db)
        checks = {item["id"]: item for item in report["checks"]}
        self.assertEqual(checks["proveniencia"]["status"], "reprovado")
        self.assertEqual(report["status"], "bloqueado")

    def test_proxima_execucao_calculada(self):
        started = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO ciclos_monitoramento (id,started_at,state) "
                         "VALUES ('c1',?,'concluido')", (started,))
        from radar.ops_config import load_config
        config = load_config()
        config["db_path"] = self.db
        health = ops.health(config, check_server=False)
        self.assertIsNotNone(health["next_run_at"])
        expected = (datetime.fromisoformat(started) + timedelta(hours=6)).isoformat()
        self.assertEqual(health["next_run_at"], expected)


class ExtractionStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def _version(self, document_id):
        version_id = "v-" + document_id
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(
                "INSERT INTO versoes_documento (id,document_id,sha256,fetched_at,fetched_url,"
                "content_type,byte_size,local_path,extraction_state) VALUES "
                "(?,?,?,?,'https://x/a','text/html',1,'x','nao_iniciada')",
                (version_id, document_id, "b" * 64, NOW))
        return version_id

    def _document(self):
        document_id, _ = add_document(self.db, "c1")
        return document_id

    def test_documento_pequeno_fica_concluido(self):
        document_id = self._document()
        version_id = self._version(document_id)
        extracted = extract_document(b"<p>Edital com 10 vagas imediatas.</p>", "text/html")
        self.assertFalse(extracted["truncated"])
        record_analysis(self.db, version_id, extracted["blocks"], [],
                        partial=bool(extracted["truncated"]))
        with closing(sqlite3.connect(self.db)) as conn:
            state = conn.execute("SELECT extraction_state FROM versoes_documento WHERE id=?",
                                 (version_id,)).fetchone()[0]
        self.assertEqual(state, "concluida")

    def test_prefixo_declarado_fica_parcial(self):
        import pymupdf

        document_id = self._document()
        version_id = self._version(document_id)
        pdf = pymupdf.open()
        for page in range(3):
            sheet = pdf.new_page()
            sheet.insert_text((72, 72), f"Pagina {page + 1} do edital")
        extracted = extract_document(pdf.tobytes(), "application/pdf", max_pages=1, prefix_pages=1)
        self.assertTrue(extracted["truncated"])
        record_analysis(self.db, version_id, extracted["blocks"], [],
                        partial=bool(extracted["truncated"]))
        with closing(sqlite3.connect(self.db)) as conn:
            state = conn.execute("SELECT extraction_state FROM versoes_documento WHERE id=?",
                                 (version_id,)).fetchone()[0]
        self.assertEqual(state, "parcial")

    def test_note_de_ocr_tambem_marca_parcial(self):
        document_id = self._document()
        version_id = self._version(document_id)
        extracted = extract_document(b"<p>Texto reconhecido.</p>", "text/html")
        note = json.dumps({"pages": [1], "derived_layer": True})
        record_analysis(self.db, version_id, extracted["blocks"], [], note=note)
        with closing(sqlite3.connect(self.db)) as conn:
            state = conn.execute("SELECT extraction_state FROM versoes_documento WHERE id=?",
                                 (version_id,)).fetchone()[0]
        self.assertEqual(state, "parcial")


class SourcesConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def test_configuracao_define_habilitacao(self):
        report = budget.state_report(self.db, config={"sources": {"fgv": {"enabled": True}}})
        items = {item["id"]: item for item in report["items"]}
        self.assertTrue(items["fgv-conhecimento"]["enabled"])
        self.assertTrue(items["fgv-conhecimento"]["configured"])
        self.assertFalse(items["quadrix"]["enabled"])

    def test_sem_configuracao_mantem_estado_persistido(self):
        report = budget.state_report(self.db)
        items = {item["id"]: item for item in report["items"]}
        self.assertFalse(items["fgv-conhecimento"]["enabled"])
        self.assertFalse(items["fgv-conhecimento"]["configured"])


class WriteGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)
        self.server = create_server(self.db, port=0)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, body=None, headers=None):
        data = None
        outgoing = dict(headers or {})
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            outgoing.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=data, headers=outgoing,
            method=method)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, response.read(), dict(response.headers)
        except urllib.error.HTTPError as error:
            return error.code, error.read(), dict(error.headers)

    def test_origem_estranha_recusada(self):
        status, body, _ = self.request(
            "POST", "/api/estudos/disciplinas", {"nome": "X"},
            {"Origin": "https://evil.example"})
        self.assertEqual(status, 403)
        self.assertIn(b"origem", body)

    def test_corpo_texto_simples_recusado(self):
        status, body, _ = self.request(
            "POST", "/api/estudos/disciplinas", {"nome": "X"},
            {"Content-Type": "text/plain"})
        self.assertEqual(status, 415)
        self.assertIn(b"application/json", body)

    def test_origem_loopback_aceita(self):
        status, _, _ = self.request(
            "POST", "/api/estudos/disciplinas", {"nome": "Local"},
            {"Origin": f"http://127.0.0.1:{self.port}"})
        self.assertEqual(status, 200)

    def test_host_estranho_recusado(self):
        status, body, _ = self.request("GET", "/api/estudos/painel",
                                       headers={"Host": "evil.example"})
        self.assertEqual(status, 403)
        self.assertIn(b"host", body)

    def test_cabecalhos_de_seguranca(self):
        status, _, headers = self.request("GET", "/api/estudos/painel")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(headers.get("Cache-Control"), "no-store")

    def test_delete_sem_origem_local_nao_exige_corpo(self):
        status, _, _ = self.request("DELETE", "/api/estudos/perfil?conceito_key=x")
        self.assertIn(status, (200, 404))


class StudySessionIdempotencyTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def test_concluir_duas_vezes_devolve_a_mesma_sessao(self):
        session = study_store.start_session(self.db)
        first = study_store.finish_session(self.db, session["id"])
        second = study_store.finish_session(self.db, session["id"])
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["estado"], "concluida")
        self.assertEqual(len(study_store.list_sessions(self.db)), 1)

class ContractMethodTest(unittest.TestCase):
    def test_metodo_errado_e_detectado(self):
        import shutil
        source = os.path.join(ROOT, "radar", "server.py")
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "server.py")
            shutil.copy2(source, target)
            text = io.open(target, encoding="utf-8").read()
            text = text.replace('elif path == "/api/saude":', 'elif path == "/api/saude-ausente":', 1)
            io.open(target, "w", encoding="utf-8").write(text)
            result = api_contract.verify(target)
        self.assertFalse(result["ok"])
        self.assertIn("GET /api/saude", result["sobrando_no_contrato"])


class ReadinessReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def test_configuracao_de_fontes_aparece_no_relatorio(self):
        report = readiness.report(self.db, config={"sources": {"fgv": {"enabled": True}}})
        self.assertEqual(report["sources"]["habilitadas"], 1)

    def test_banco_vazio_bloqueia_sem_traceback(self):
        path = os.path.join(self.tmp.name, "vazio.sqlite3")
        open(path, "wb").close()
        report = readiness.report(path)
        self.assertEqual(report["status"], "bloqueado")
        self.assertFalse(report["ready"])

    def test_ciclo_parcial_fica_pendente(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO ciclos_monitoramento (id,started_at,state) "
                         "VALUES ('c1',?,'parcial')", (NOW,))
        report = readiness.report(self.db)
        checks = {item["id"]: item for item in report["checks"]}
        self.assertEqual(checks["monitoramento"]["status"], "pendente")
        self.assertIn("ultimo_ciclo_parcial", [item["codigo"] for item in report["pendencias"]])

    def test_servico_de_estudos_ausente_bloqueia(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("DROP TABLE estudo_sessoes")
        report = readiness.report(self.db)
        checks = {item["id"]: item for item in report["checks"]}
        self.assertEqual(checks["estudos"]["status"], "reprovado")
        self.assertEqual(report["status"], "bloqueado")


class PortfolioCacheTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def test_data_local_invalida_cache(self):
        from radar import portfolio
        first = portfolio.portfolio(self.db, limit=1, now="2026-10-18T00:30:00+00:00")
        second = portfolio.portfolio(self.db, limit=1, now="2026-10-18T03:30:00+00:00")
        self.assertEqual(first["referencia"]["hoje_local"], "2026-10-17")
        self.assertEqual(second["referencia"]["hoje_local"], "2026-10-18")


class BatchCompletionTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def test_ultimo_lote_marca_concluida(self):
        from radar.document_store import append_page_analysis
        document_id, _ = add_document(self.db, "c1")
        version_id = "v-lote"
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO versoes_documento (id,document_id,sha256,fetched_at,"
                         "fetched_url,content_type,byte_size,local_path,extraction_state) "
                         "VALUES (?,?,?,?,'https://x/a','text/html',1,'x','parcial')",
                         (version_id, document_id, "c" * 64, NOW))
        blocks = [{"page_number": 2, "locator": "pagina 2", "start_offset": 0,
                   "end_offset": 4, "text": "text"}]
        append_page_analysis(self.db, version_id, blocks, [], partial=False)
        with closing(sqlite3.connect(self.db)) as conn:
            state = conn.execute("SELECT extraction_state FROM versoes_documento WHERE id=?",
                                 (version_id,)).fetchone()[0]
        self.assertEqual(state, "concluida")

    def test_note_json_nao_objeto_nao_quebra(self):
        from radar.document_store import _note_is_partial
        for note in ('"x"', "null", "[]", "123"):
            self.assertFalse(_note_is_partial(note))
