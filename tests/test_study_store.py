"""Persistência e API da gestão de estudos (schema v10, dados pessoais)."""

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from radar import study_store
from radar.document_store import connect_documents, migrate_document_schema
from radar.server import create_server


class StudyStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "study.sqlite3")
        migrate_document_schema(self.db)

    def test_migracao_v10_cria_tabelas_e_e_idempotente(self):
        conn = connect_documents(self.db)
        try:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 13)
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            conn.close()
        for table in ("estudo_disciplinas", "estudo_topicos", "estudo_progresso",
                      "estudo_sessoes", "estudo_revisoes"):
            self.assertIn(table, tables)
        migrate_document_schema(self.db)  # idempotente

    def test_disciplina_e_topico_persistem(self):
        disc = study_store.create_disciplina(self.db, "Português")
        top = study_store.create_topico(self.db, disc["id"], "Crase")
        self.assertEqual([d["nome"] for d in study_store.list_disciplinas(self.db)], ["Português"])
        self.assertEqual([t["nome"] for t in study_store.list_topicos(self.db, disc["id"])], ["Crase"])
        self.assertEqual(top["disciplina_id"], disc["id"])

    def test_topico_em_disciplina_inexistente_rejeitado(self):
        with self.assertRaises(ValueError):
            study_store.create_topico(self.db, "nao-existe", "X")

    def test_progresso_e_isolado_por_concurso(self):
        disc = study_store.create_disciplina(self.db, "TI")
        top = study_store.create_topico(self.db, disc["id"], "Redes")
        study_store.set_progress(self.db, top["id"], "concluido", contest_id="")
        study_store.set_progress(self.db, top["id"], "estudando", contest_id="concurso-a")
        self.assertEqual(study_store.progresso_por_topico(self.db, ""), {top["id"]: "concluido"})
        self.assertEqual(study_store.progresso_por_topico(self.db, "concurso-a"), {top["id"]: "estudando"})

    def test_concluir_agenda_revisoes(self):
        disc = study_store.create_disciplina(self.db, "Matemática")
        top = study_store.create_topico(self.db, disc["id"], "Logaritmos")
        study_store.set_progress(self.db, top["id"], "concluido")
        conn = connect_documents(self.db)
        try:
            n = conn.execute("SELECT count(*) FROM estudo_revisoes").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(n, 4)  # [1,7,30,90]

    def test_marcar_revisao_avanca_a_agenda(self):
        # Regressão (crítico): a agenda persistida precisa avançar quando uma revisão é feita.
        disc = study_store.create_disciplina(self.db, "TI")
        top = study_store.create_topico(self.db, disc["id"], "Redes")
        prog = study_store.set_progress(self.db, top["id"], "concluido")
        # Antecipa a agenda para o passado, para haver revisão vencida.
        conn = connect_documents(self.db)
        try:
            conn.execute("UPDATE estudo_revisoes SET agendada_para='2020-01-02'")
            conn.execute("UPDATE estudo_revisoes SET agendada_para='2020-01-08' WHERE id IN "
                         "(SELECT id FROM estudo_revisoes ORDER BY agendada_para DESC LIMIT 1)")
            conn.commit()
        finally:
            conn.close()
        self.assertGreaterEqual(len(study_store.pending_revisions(self.db)), 1)
        study_store.mark_revision_done(self.db, prog["id"], resultado="ok")
        # Uma revisão a menos pendente; a agenda avançou (feita_em gravado).
        conn = connect_documents(self.db)
        try:
            feitas = conn.execute("SELECT count(*) FROM estudo_revisoes WHERE feita_em IS NOT NULL").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(feitas, 1)

    def test_marcar_revisao_sem_pendencia_falha(self):
        disc = study_store.create_disciplina(self.db, "TI")
        top = study_store.create_topico(self.db, disc["id"], "Redes")
        prog = study_store.set_progress(self.db, top["id"], "estudando")  # sem agenda
        with self.assertRaises(ValueError):
            study_store.mark_revision_done(self.db, prog["id"])

    def test_duracao_truncada_no_teto(self):
        # Regressão: sessão que atravessa um fechamento longo é truncada no teto plausível.
        from radar import study
        from datetime import datetime, timedelta, timezone
        disc = study_store.create_disciplina(self.db, "TI")
        study_store.start_session(self.db, disciplina_id=disc["id"])
        inicio = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        conn = connect_documents(self.db)
        try:
            conn.execute("UPDATE estudo_sessoes SET inicio=?", (inicio,))
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(study_store.current_session(self.db)["elapsed_seconds"],
                         study.MAX_SESSION_SECONDS)
        fin = study_store.finish_session(self.db)
        self.assertEqual(fin["duracao_segundos"], study.MAX_SESSION_SECONDS)

    def test_contest_id_longo_rejeitado(self):
        disc = study_store.create_disciplina(self.db, "TI")
        top = study_store.create_topico(self.db, disc["id"], "Redes")
        with self.assertRaises(ValueError):
            study_store.set_progress(self.db, top["id"], "estudando", contest_id="x" * 200)

    def test_estado_de_progresso_invalido_rejeitado(self):
        disc = study_store.create_disciplina(self.db, "X")
        top = study_store.create_topico(self.db, disc["id"], "Y")
        with self.assertRaises(ValueError):
            study_store.set_progress(self.db, top["id"], "inventado")

    def test_sessao_fluxo_completo(self):
        disc = study_store.create_disciplina(self.db, "Direito")
        s = study_store.start_session(self.db, disciplina_id=disc["id"], modo="pomodoro")
        self.assertEqual(s["estado"], "em_andamento")
        self.assertEqual(s["modo"], "pomodoro")
        self.assertIsNotNone(study_store.current_session(self.db))
        self.assertEqual(study_store.pause_session(self.db)["estado"], "pausada")
        self.assertEqual(study_store.resume_session(self.db)["estado"], "em_andamento")
        fin = study_store.finish_session(self.db)
        self.assertEqual(fin["estado"], "concluida")
        self.assertIsNone(study_store.current_session(self.db))

    def test_sessao_duplicada_recusada(self):
        study_store.start_session(self.db, modo="livre")
        with self.assertRaises(ValueError):
            study_store.start_session(self.db, modo="livre")

    def test_recupera_sessao_aberta_apos_reinicio(self):
        # Simula "reinício": a sessão permanece aberta no banco e é recuperada.
        disc = study_store.create_disciplina(self.db, "Física")
        started = study_store.start_session(self.db, disciplina_id=disc["id"])
        recovered = study_store.current_session(self.db)
        self.assertEqual(recovered["id"], started["id"])
        self.assertEqual(recovered["estado"], "em_andamento")
        self.assertIn("elapsed_seconds", recovered)

    def test_finish_sem_sessao_aberta_falha(self):
        with self.assertRaises(ValueError):
            study_store.finish_session(self.db)

    def test_discard_nao_conta_como_estudo(self):
        study_store.start_session(self.db, modo="livre")
        study_store.discard_session(self.db)
        dash = study_store.study_dashboard(self.db)
        self.assertEqual(dash["total_segundos"], 0)
        self.assertEqual(dash["sessoes_concluidas"], 0)

    def test_painel_deriva_de_dados_persistidos(self):
        disc = study_store.create_disciplina(self.db, "TI")
        top = study_store.create_topico(self.db, disc["id"], "Banco de dados")
        study_store.set_progress(self.db, top["id"], "concluido")
        s = study_store.start_session(self.db, disciplina_id=disc["id"])
        study_store.finish_session(self.db)
        dash = study_store.study_dashboard(self.db)
        self.assertEqual(dash["conteudo"]["overall"], {"done": 1, "total": 1, "pct": 100})
        self.assertEqual(dash["sessoes_concluidas"], 1)
        # Concluído hoje: a 1ª revisão vence amanhã, então não há pendência hoje (honesto).
        self.assertEqual(dash["revisoes_pendentes"], 0)

    def test_revisao_pendente_quando_agenda_no_passado(self):
        disc = study_store.create_disciplina(self.db, "TI")
        top = study_store.create_topico(self.db, disc["id"], "Redes")
        study_store.set_progress(self.db, top["id"], "concluido")
        # Antecipa a agenda persistida para o passado (simula dias depois).
        conn = connect_documents(self.db)
        try:
            conn.execute("UPDATE estudo_revisoes SET agendada_para='2020-01-01'")
            conn.commit()
        finally:
            conn.close()
        dash = study_store.study_dashboard(self.db)
        self.assertGreaterEqual(dash["revisoes_pendentes"], 1)

    def test_deletar_topico_remove_progresso(self):
        disc = study_store.create_disciplina(self.db, "TI")
        top = study_store.create_topico(self.db, disc["id"], "Redes")
        study_store.set_progress(self.db, top["id"], "concluido")
        self.assertTrue(study_store.delete_topico(self.db, top["id"]))
        self.assertEqual(study_store.list_progresso(self.db), [])


class StudyApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "api.sqlite3")
        migrate_document_schema(self.db)
        self.server = create_server(self.db, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, path, method="GET", body=None):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        try:
            headers = {"Content-Type": "application/json"} if body is not None else {}
            client.request(method, path, body=body, headers=headers)
            response = client.getresponse()
            return response.status, response.read()
        finally:
            client.close()

    def test_fluxo_de_estudo_pela_api(self):
        v1_before = self.request("/api/concursos")[1]
        status, body = self.request("/api/estudos/disciplinas", "POST", json.dumps({"nome": "TI"}))
        self.assertEqual(status, 200)
        disc = json.loads(body)["id"]
        _, body = self.request("/api/estudos/topicos", "POST",
                               json.dumps({"disciplina_id": disc, "nome": "Redes"}))
        top = json.loads(body)["id"]
        self.assertEqual(self.request("/api/estudos/progresso", "POST",
                                      json.dumps({"topico_id": top, "state": "estudando"}))[0], 200)
        self.assertEqual(self.request("/api/estudos/sessoes", "POST",
                                      json.dumps({"action": "start", "disciplina_id": disc}))[0], 200)
        self.assertEqual(json.loads(self.request("/api/estudos/sessao-atual")[1])["estado"], "em_andamento")
        self.assertEqual(self.request("/api/estudos/sessoes", "POST", json.dumps({"action": "finish"}))[0], 200)
        painel = json.loads(self.request("/api/estudos/painel")[1])
        self.assertEqual(painel["disciplinas"], 1)
        self.assertEqual(self.request("/api/concursos")[1], v1_before)  # v1 intacta

    def test_entradas_invalidas(self):
        self.assertEqual(self.request("/api/estudos/disciplinas", "POST", json.dumps({}))[0], 400)
        self.assertEqual(self.request("/api/estudos/sessoes", "POST", json.dumps({"action": "x"}))[0], 400)
        self.assertEqual(self.request("/api/estudos/sessoes", "POST", "nao-json")[0], 400)
        self.assertEqual(self.request("/api/estudos/progresso", "POST",
                                      json.dumps({"topico_id": "x", "state": "y"}))[0], 400)

    def test_sessao_duplicada_pela_api(self):
        self.request("/api/estudos/sessoes", "POST", json.dumps({"action": "start"}))
        self.assertEqual(self.request("/api/estudos/sessoes", "POST",
                                      json.dumps({"action": "start"}))[0], 400)

    def test_metodos_e_consultas_invalidas(self):
        self.assertEqual(self.request("/api/estudos/disciplinas", "PUT")[0], 405)
        self.assertEqual(self.request("/api/estudos/sessoes?limit=0")[0], 400)
        self.assertEqual(self.request("/api/estudos/painel?x=1")[0], 400)
        self.assertEqual(self.request("/api/estudos/inexistente")[0], 404)

    def test_listar_e_criar_disciplinas(self):
        self.request("/api/estudos/disciplinas", "POST", json.dumps({"nome": "A"}))
        self.request("/api/estudos/disciplinas", "POST", json.dumps({"nome": "B"}))
        payload = json.loads(self.request("/api/estudos/disciplinas")[1])
        self.assertEqual([d["nome"] for d in payload], ["A", "B"])

    def test_revisoes_pela_api(self):
        _, body = self.request("/api/estudos/disciplinas", "POST", json.dumps({"nome": "TI"}))
        disc = json.loads(body)["id"]
        _, body = self.request("/api/estudos/topicos", "POST",
                               json.dumps({"disciplina_id": disc, "nome": "Redes"}))
        top = json.loads(body)["id"]
        _, body = self.request("/api/estudos/progresso", "POST",
                               json.dumps({"topico_id": top, "state": "concluido"}))
        prog = json.loads(body)["id"]
        # Agenda no passado -> pendente; marcar como feita via API.
        conn = connect_documents(self.db)
        try:
            conn.execute("UPDATE estudo_revisoes SET agendada_para='2020-01-01'")
            conn.commit()
        finally:
            conn.close()
        self.assertGreaterEqual(len(json.loads(self.request("/api/estudos/revisoes")[1])), 1)
        status, body = self.request("/api/estudos/revisoes", "POST",
                                    json.dumps({"progresso_id": prog, "resultado": "ok"}))
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["feita"])

    def test_erro_json_com_corpo(self):
        # Regressão: 400 deve ter corpo JSON legível (o frontend faz res.json()).
        status, body = self.request("/api/estudos/progresso", "POST", json.dumps({"topico_id": "x"}))
        self.assertEqual(status, 400)
        self.assertIn("error", json.loads(body))


if __name__ == "__main__":
    unittest.main()
