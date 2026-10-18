"""Catálogo de fontes, política de persistência, orçamento e IBGE (Fase 29)."""

import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

from radar import budget, connectors, ibge_source, source_catalog, source_policy
from radar.document_store import (SCHEMA_VERSION, connect_documents,
                                  migrate_document_schema)
from radar.server import create_server

NOW = "2026-10-17T12:00:00+00:00"

MUNICIPIOS = json.dumps([
    {"id": 3550308, "nome": "São Paulo",
     "microrregiao": {"mesorregiao": {"UF": {"sigla": "SP"}}}},
    {"id": 2930766, "nome": "Salvador",
     "microrregiao": {"mesorregiao": {"UF": {"sigla": "BA"}}}},
    {"id": 4113700, "nome": "Londrina",
     "microrregiao": {"mesorregiao": {"UF": {"sigla": "PR"}}}},
]).encode("utf-8")


class CatalogTest(unittest.TestCase):
    def test_catalogo_valido(self):
        self.assertEqual(source_catalog.validate_catalog(), [])

    def test_ids_unicos_e_campos_obrigatorios(self):
        ids = source_catalog.source_ids()
        self.assertEqual(len(ids), len(set(ids)))
        for source in source_catalog.catalog():
            for field in source_catalog.REQUIRED_FIELDS:
                self.assertIn(field, source, f"{source['id']} sem {field}")

    def test_persistencia_exige_evidencia(self):
        for source in source_catalog.catalog():
            for content_type, entry in source["content"].items():
                if entry["permission"] == source_catalog.PERSISTENCIA_PERMITIDA:
                    self.assertTrue(entry["evidence_url"], f"{source['id']}/{content_type}")
                    self.assertTrue(entry["verified_at"], f"{source['id']}/{content_type}")

    def test_agregador_nao_persiste_conteudo_editorial(self):
        self.assertFalse(source_policy.can_persist("pci", "noticia"))
        self.assertTrue(source_policy.can_persist("pci", "metadados"))

    def test_api_sem_licenca_bloqueada(self):
        decision = source_policy.decision("api-concursos-kaua", "metadados")
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["permission"], source_catalog.ACESSO_BLOQUEADO)

    def test_quest_api_exige_credencial(self):
        source = source_catalog.get_source("quest-api")
        self.assertEqual(source["credential_env"], "RADAR_QUEST_API_KEY")
        self.assertFalse(source_policy.can_persist("quest-api", "questao"))

    def test_credencial_nao_contem_valor(self):
        for source in source_catalog.catalog():
            value = source.get("credential_env")
            if value:
                self.assertNotIn("=", value)
                self.assertNotIn(" ", value)

    def test_revisao_vencida(self):
        due = source_catalog.review_due_sources("2027-12-31")
        self.assertIn("pci", due)
        self.assertNotIn("pci", source_catalog.review_due_sources("2026-10-17"))


class PolicyTest(unittest.TestCase):
    def test_fonte_desconhecida_falha(self):
        with self.assertRaises(source_policy.PolicyError) as ctx:
            source_policy.require_persist("inexistente", "metadados")
        self.assertEqual(ctx.exception.code, "fonte_desconhecida")

    def test_tipo_nao_declarado_e_bloqueado(self):
        decision = source_policy.decision("guajara", "questao")
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["permission"], source_catalog.ACESSO_BLOQUEADO)

    def test_transitorio_nao_pode_persistir_e_e_redigido(self):
        decision = source_policy.decision("jcconcursos", "noticia")
        self.assertEqual(decision["permission"], source_catalog.SOMENTE_USO_TRANSITORIO)
        self.assertFalse(decision["allowed"])
        self.assertTrue(source_policy.transient_only("jcconcursos", "noticia"))
        redacted = source_policy.redact_for_log("corpo jornalístico", source_id="jcconcursos",
                                                content_type="noticia")
        self.assertTrue(redacted["redacted"])
        self.assertNotIn("corpo jornalístico", json.dumps(redacted))

    def test_catalogo_nao_e_mutavel_por_chamador(self):
        copy_source = source_catalog.get_source("pci")
        copy_source["content"]["noticia"]["permission"] = source_catalog.PERSISTENCIA_PERMITIDA
        self.assertFalse(source_policy.can_persist("pci", "noticia"))

    def test_require_persist_autoriza_metadados(self):
        decision = source_policy.require_persist("ibge-localidades", "dado_aberto")
        self.assertTrue(decision["allowed"])

    def test_estado_da_fonte_bloqueia_mesmo_com_permissao(self):
        # dados.gov.br tem metadados marcados como bloqueados por falta de credencial.
        decision = source_policy.decision("dados-gov-br", "metadados")
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["source_status"], "aguardando_credencial")

    def test_status_desativada_bloqueia_persistencia(self):
        import copy
        original = copy.deepcopy(source_catalog._SOURCES)
        try:
            for source in source_catalog._SOURCES:
                if source["id"] == "ibge-localidades":
                    source["status"] = "desativada"
            decision = source_policy.decision("ibge-localidades", "dado_aberto")
            self.assertFalse(decision["allowed"])
            self.assertEqual(decision["source_status"], "desativada")
        finally:
            source_catalog._SOURCES[:] = original


class BudgetTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = str(Path(tmp.name) / "b.sqlite3")
        migrate_document_schema(self.db)
        budget.ensure_state(self.db, "ibge-localidades", enabled=True)

    def test_execucao_registra_chamadas_e_itens(self):
        run = budget.open_run(self.db, "ibge-localidades", now=NOW)
        budget.record_call(self.db, run["run_id"], items=3)
        budget.save_checkpoint(self.db, run["run_id"], {"pagina": 2})
        usage = budget.finish_run(self.db, run["run_id"], status="concluida", now=NOW)
        self.assertEqual(usage["calls"], 1)
        self.assertEqual(usage["items"], 3)
        self.assertEqual(usage["checkpoint"], {"pagina": 2})
        self.assertEqual(usage["status"], "concluida")

    def test_limite_de_chamadas(self):
        run = budget.open_run(self.db, "ibge-localidades",
                              overrides={"max_calls": 1}, now=NOW)
        budget.check_call(self.db, run["run_id"])
        budget.record_call(self.db, run["run_id"], items=1)
        with self.assertRaises(budget.BudgetError) as ctx:
            budget.check_call(self.db, run["run_id"])
        self.assertEqual(ctx.exception.code, "limite_de_chamadas")

    def test_limite_de_itens(self):
        run = budget.open_run(self.db, "ibge-localidades",
                              overrides={"max_items": 2}, now=NOW)
        with self.assertRaises(budget.BudgetError) as ctx:
            budget.check_call(self.db, run["run_id"], estimated_items=3)
        self.assertEqual(ctx.exception.code, "limite_de_itens")

    def test_custo_nao_verificado_recusa_pago(self):
        with self.assertRaises(budget.BudgetError) as ctx:
            budget.require_paid_allowed("quest-api", 10.0)
        self.assertEqual(ctx.exception.code, "custo_nao_verificado")

    def test_limite_monetario(self):
        run = budget.open_run(self.db, "ibge-localidades",
                              overrides={"max_cost": 0}, now=NOW)
        with self.assertRaises(budget.BudgetError) as ctx:
            budget.check_call(self.db, run["run_id"], estimated_cost=1.0)
        self.assertEqual(ctx.exception.code, "limite_de_custo")

    def test_record_call_nao_excede_limites(self):
        run = budget.open_run(self.db, "ibge-localidades",
                              overrides={"max_calls": 1, "max_items": 2,
                                         "max_cost": 0}, now=NOW)
        budget.record_call(self.db, run["run_id"], items=2)
        with self.assertRaises(budget.BudgetError) as ctx:
            budget.record_call(self.db, run["run_id"], items=1)
        self.assertEqual(ctx.exception.code, "limite_excedido")
        self.assertEqual(budget.usage(self.db, run["run_id"])["calls"], 1)
        self.assertEqual(budget.usage(self.db, run["run_id"])["items"], 2)

    def test_falha_nao_cobra_creditos_nem_valor(self):
        run = budget.open_run(self.db, "ibge-localidades", now=NOW)
        budget.record_call(self.db, run["run_id"], items=1, credits=5, cost=0, success=False)
        usage = budget.usage(self.db, run["run_id"])
        self.assertEqual(usage["credits"], 0)
        self.assertEqual(usage["cost"], 0)

    def test_estado_e_preenchido_pela_execucao(self):
        run = budget.open_run(self.db, "ibge-localidades", now=NOW)
        budget.record_call(self.db, run["run_id"], items=1)
        budget.finish_run(self.db, run["run_id"], status="concluida", now=NOW)
        report = budget.state_report(self.db)
        item = next(i for i in report["items"] if i["id"] == "ibge-localidades")
        self.assertEqual(item["calls_total"], 1)
        self.assertEqual(item["last_run_status"], "concluida")
        self.assertEqual(item["last_run_at"], NOW)

    def test_intervalo_minimo_entre_execucoes(self):
        budget.open_run(self.db, "ibge-localidades", now=NOW)
        with self.assertRaises(budget.BudgetError) as ctx:
            budget.open_run(self.db, "ibge-localidades", now=NOW)
        self.assertEqual(ctx.exception.code, "intervalo_minimo")

    def test_execucao_encerrada_nao_aceita_chamada(self):
        run = budget.open_run(self.db, "ibge-localidades", now=NOW)
        budget.finish_run(self.db, run["run_id"], now=NOW)
        with self.assertRaises(budget.BudgetError) as ctx:
            budget.check_call(self.db, run["run_id"])
        self.assertEqual(ctx.exception.code, "execucao_encerrada")

    def test_consumo_por_fonte(self):
        run = budget.open_run(self.db, "ibge-localidades", now=NOW)
        budget.record_call(self.db, run["run_id"], items=2)
        budget.finish_run(self.db, run["run_id"], now=NOW)
        report = budget.consumption_report(self.db, source_id="ibge-localidades")
        self.assertEqual(report["total"], 1)
        self.assertEqual(report["itens"][0]["items"], 2)

    def test_estado_operacional_nao_expoe_segredo(self):
        report = budget.state_report(self.db)
        text = json.dumps(report)
        self.assertNotIn("sk-", text)
        self.assertNotIn("Bearer ", text)
        self.assertNotIn("api_key=", text)
        quest = next(item for item in report["items"] if item["id"] == "quest-api")
        self.assertEqual(quest["credential_env"], "RADAR_QUEST_API_KEY")
        self.assertEqual(quest["runtime_status"], "nao_testada")


class ConnectorTest(unittest.TestCase):
    def test_registro_inclui_fontes_existentes_e_ibge(self):
        ids = [connector.id for connector in connectors.connectors()]
        for expected in ("guajara", "dou-secao-3", "fgv-conhecimento", "quadrix", "ibfc",
                         "pci", "ibge-localidades"):
            self.assertIn(expected, ids)

    def test_descricao_traz_politica_por_tipo(self):
        described = connectors.get_connector("pci").describe()
        self.assertEqual(described["storage_policy"]["metadados"]["permission"],
                         source_catalog.PERSISTENCIA_PERMITIDA)
        self.assertEqual(described["storage_policy"]["noticia"]["permission"],
                         source_catalog.PERSISTENCIA_NAO_VERIFICADA)

    def test_normalizacao_preserva_procedencia(self):
        result = connectors.normalize(
            {"original_id": "ibfc-485", "title": "Edital", "url": "https://x/edital.pdf",
             "published_at": "2026-10-01"},
            source_id="ibfc", content_type="metadados", official=True, collected_at=NOW,
            uncertainty="candidato")
        self.assertEqual(result["original_id"], "ibfc-485")
        self.assertEqual(result["url"], "https://x/edital.pdf")
        self.assertEqual(result["source_id"], "ibfc")
        self.assertTrue(result["official"])
        self.assertEqual(result["uncertainty"], "candidato")
        self.assertEqual(result["collected_at"], NOW)
        self.assertIsNone(result["raw"])

    def test_normalizacao_exige_url(self):
        with self.assertRaises(connectors.ConnectorError):
            connectors.normalize({"title": "x"}, source_id="ibfc", content_type="metadados",
                                 official=True)

    def test_guard_filtra_conteudo_nao_persistivel(self):
        results = [
            connectors.normalize({"url": "https://x/a", "title": "A"}, source_id="pci",
                                 content_type="metadados", official=False),
            connectors.normalize({"url": "https://x/b", "title": "B"}, source_id="pci",
                                 content_type="noticia", official=False),
        ]
        allowed, blocked = connectors.guard_persistence(results)
        self.assertEqual(len(allowed), 1)
        self.assertEqual(allowed[0]["content_type"], "metadados")
        self.assertEqual(blocked[0]["content_type"], "noticia")

    def test_discover_exige_parametros_e_nao_quebra(self):
        connector = connectors.get_connector("guajara")
        with self.assertRaises(connectors.ConnectorError):
            connector.discover()
        multi = connectors.get_connector("pci")
        with self.assertRaises(connectors.ConnectorError):
            multi.discover()

    def test_conector_inexistente(self):
        with self.assertRaises(connectors.ConnectorError):
            connectors.get_connector("nao-existe")


class IBGETest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = str(Path(tmp.name) / "i.sqlite3")
        migrate_document_schema(self.db)

    def test_parse_municipios(self):
        municipios = ibge_source.parse_municipios(MUNICIPIOS)
        self.assertEqual(len(municipios), 3)
        self.assertEqual(municipios[0]["uf"], "SP")

    def test_parse_invalido(self):
        with self.assertRaises(ibge_source.IBGEError):
            ibge_source.parse_municipios(b"<html>")

    def test_sync_e_idempotente_no_ttl(self):
        first = ibge_source.sync_snapshot(self.db, transport=lambda: MUNICIPIOS, now=NOW)
        self.assertTrue(first["atualizado"])
        second = ibge_source.sync_snapshot(self.db, transport=lambda: MUNICIPIOS,
                                           now="2026-10-20T00:00:00+00:00")
        self.assertFalse(second["atualizado"])
        forced = ibge_source.sync_snapshot(self.db, transport=lambda: MUNICIPIOS,
                                           force=True, now="2026-10-20T00:00:00+00:00")
        self.assertTrue(forced["atualizado"])

    def test_validate_location_status(self):
        ibge_source.sync_snapshot(self.db, transport=lambda: MUNICIPIOS, now=NOW)
        self.assertEqual(ibge_source.validate_location(self.db, "São Paulo", "SP")["status"],
                         "confere_ibge")
        self.assertEqual(ibge_source.validate_location(self.db, "Londrina", "SP")["status"],
                         "uf_divergente")
        self.assertEqual(ibge_source.validate_location(self.db, "Cidade Falsa", "SP")["status"],
                         "nao_encontrado")
        self.assertEqual(ibge_source.validate_location(self.db, "SAO PAULO", "sp")["status"],
                         "confere_ibge")

    def test_gzip_bomb_e_recusado(self):
        import gzip as _gzip
        payload = _gzip.compress(b"0" * (ibge_source.MAX_BYTES + 1024))

        class Response:
            status = 200
            headers = {"Content-Encoding": "gzip"}
            def geturl(self):
                return ibge_source.MUNICIPIOS_URL
            def read(self, size=-1):
                return payload
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        class Opener:
            def open(self, request, timeout=None):
                return Response()

        original = ibge_source.urllib.request.build_opener
        ibge_source.urllib.request.build_opener = lambda *a, **k: Opener()
        try:
            with self.assertRaises(ibge_source.IBGEError) as ctx:
                ibge_source._fetch()
            self.assertEqual(ctx.exception.code, "resposta_grande")
        finally:
            ibge_source.urllib.request.build_opener = original

    def test_redirect_para_outro_host_e_recusado(self):
        handler = ibge_source._SameHostRedirects()
        with self.assertRaises(ibge_source.IBGEError):
            handler.redirect_request(None, None, 302, "", {}, "https://evil.example/x")
        with self.assertRaises(ibge_source.IBGEError):
            ibge_source._fetch("https://evil.example/municipios")

    def test_sem_snapshot(self):
        self.assertEqual(ibge_source.validate_location(self.db, "Salvador", "BA")["status"],
                         "sem_snapshot")

    def test_validate_proposals_nao_altera_nada(self):
        ibge_source.sync_snapshot(self.db, transport=lambda: MUNICIPIOS, now=NOW)
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute("INSERT INTO concursos_identidade (id,created_at) "
                         "VALUES ('c','2026-10-01T00:00:00+00:00')")
            conn.execute("INSERT INTO observacoes_concurso (id,contest_id,source_url,"
                         "competition_id,observed_at) VALUES ('o','c','https://x/','1/2026',?)",
                         (NOW,))
            conn.execute("INSERT INTO documentos (id,contest_id,observation_id,kind,"
                         "official_url,title,discovered_at,discovery_url,discovery_method) "
                         "VALUES ('d','c','o','edital','https://x/e.pdf','E',?,'https://x/',"
                         "'manual')", (NOW,))
            conn.execute("INSERT INTO versoes_documento (id,document_id,sha256,fetched_at,"
                         "fetched_url,content_type,byte_size,local_path) VALUES "
                         "('v','d','h',?,'https://x/e.pdf','application/pdf',1,'x')", (NOW,))
            conn.execute("INSERT INTO blocos_documento (id,version_id,page_number,locator,"
                         "start_offset,end_offset,text) VALUES ('b','v',1,'p.1',0,10,'x')")
            conn.execute("INSERT INTO evidencias (id,version_id,block_id,quote,page_number,"
                         "locator,start_offset,end_offset,captured_at) VALUES "
                         "('e','v','b','x',1,'p.1',0,10,?)", (NOW,))
            conn.execute("INSERT INTO propostas_campo VALUES ('p','c',NULL,'exam_location',"
                         "'\"Londrina/PR\"','string','e','local-prova',NULL,?)", (NOW,))
            conn.commit()
        report = ibge_source.validate_proposals(self.db)
        self.assertEqual(report["total"], 1)
        self.assertEqual(report["itens"][0]["ibge"]["status"], "confere_ibge")
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute(
                "SELECT value_json FROM propostas_campo WHERE id='p'").fetchone()[0],
                '"Londrina/PR"')
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM revisoes_campo").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM valores_atuais").fetchone()[0], 0)


class PolicyReviewTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = str(Path(tmp.name) / "r.sqlite3")
        migrate_document_schema(self.db)

    def test_revisao_append_only(self):
        first = source_policy.record_review(self.db, "pci", reviewer="Ana",
                                            review_decision="restringir",
                                            note="termos não verificados", now=NOW)
        second = source_policy.record_review(self.db, "pci", reviewer="Ana",
                                             review_decision="manter",
                                             note="termos revisados", now=NOW)
        history = source_policy.review_history(self.db, "pci")
        self.assertEqual(history["total"], 2)
        self.assertNotEqual(first["review_id"], second["review_id"])

    def test_revisao_exige_justificativa(self):
        with self.assertRaises(source_policy.PolicyError):
            source_policy.record_review(self.db, "pci", reviewer="Ana",
                                        review_decision="manter", note="  ")


class SourcesApiTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = str(Path(tmp.name) / "api.sqlite3")
        migrate_document_schema(self.db)
        self.server = create_server(self.db, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, path):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1],
                                            timeout=5)
        try:
            client.request("GET", path)
            response = client.getresponse()
            return response.status, response.read()
        finally:
            client.close()

    def test_lista_de_fontes(self):
        status, body = self.request("/api/fontes")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertGreaterEqual(payload["total"], 15)
        self.assertIn("catalogo", payload)
        ids = {item["id"] for item in payload["items"]}
        self.assertIn("ibge-localidades", ids)
        self.assertNotIn("RADAR_QUEST_API_KEY=", body.decode())
        self.assertNotIn("Bearer ", body.decode())

    def test_detalhe_de_fonte(self):
        status, body = self.request("/api/fontes/pci")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["connector"]["id"], "pci")
        self.assertEqual(payload["policy"][0]["source_id"], "pci")
        self.assertEqual(payload["reviews"], [])

    def test_consumo(self):
        status, body = self.request("/api/fontes-consumo?limit=5")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["total"], 0)

    def test_fonte_inexistente(self):
        self.assertEqual(self.request("/api/fontes/nao-existe")[0], 400)

    def test_parametros_invalidos(self):
        self.assertEqual(self.request("/api/fontes?x=1")[0], 400)
        self.assertEqual(self.request("/api/fontes-consumo?x=1")[0], 400)

    def test_contrato_v1_intacto(self):
        from radar.storage import CONTRACT_FIELDS
        self.assertEqual(len(CONTRACT_FIELDS), 18)
        self.assertEqual(json.loads(self.request("/api/concursos")[1]), [])


class SchemaTest(unittest.TestCase):
    def test_v18_tabelas_e_idempotencia(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = str(Path(tmp.name) / "s.sqlite3")
        migrate_document_schema(db)
        migrate_document_schema(db)
        with closing(sqlite3.connect(db)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0],
                         SCHEMA_VERSION)
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            for table in ("fontes_estado", "fontes_consumo", "fontes_revisoes",
                          "localidades_ibge"):
                self.assertIn(table, tables)


if __name__ == "__main__":
    unittest.main()
