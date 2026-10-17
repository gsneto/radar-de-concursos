"""Persistência e API da prática: flashcards, questões, tentativas e simulados."""

import http.client
import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from radar import practice_store
from radar.document_store import connect_documents, migrate_document_schema
from radar.server import create_server


class PracticeBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "p.sqlite3")
        migrate_document_schema(self.db)

    def _question(self, i=0, **kwargs):
        params = {"enunciado": f"Questão número {i}?", "alternativas": ["A1", "A2", "A3"],
                  "gabarito": "B", "disciplina": "Matemática", "topico": "Aritmética"}
        params.update(kwargs)
        return practice_store.create_question(self.db, **params)


class FlashcardStoreTest(PracticeBase):
    def test_migracao_v12_cria_tabelas(self):
        conn = connect_documents(self.db)
        try:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 13)
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            conn.close()
        for table in ("pratica_flashcards", "pratica_flashcard_revisoes", "pratica_questoes",
                      "pratica_questao_versoes", "pratica_tentativas", "pratica_simulados",
                      "pratica_simulado_questoes"):
            self.assertIn(table, tables)
        migrate_document_schema(self.db)  # idempotente

    def test_criar_e_revisar_persiste(self):
        card = practice_store.create_flashcard(self.db, frente="F?", verso="V")
        self.assertEqual(card["revisoes"], 0)
        reviewed = practice_store.review_flashcard(self.db, card["id"], 4)
        self.assertEqual(reviewed["revisoes"], 1)
        self.assertEqual(reviewed["intervalo"], 1)
        self.assertIsNotNone(reviewed["proxima_revisao"])
        self.assertEqual(len(practice_store.flashcard_reviews(self.db, card["id"])), 1)

    def test_editar_preserva_historico(self):
        card = practice_store.create_flashcard(self.db, frente="F?", verso="V")
        practice_store.review_flashcard(self.db, card["id"], 4)
        updated = practice_store.update_flashcard(self.db, card["id"], frente="Nova frente")
        self.assertEqual(updated["frente"], "Nova frente")
        self.assertEqual(updated["revisoes"], 1)  # histórico preservado
        self.assertEqual(len(practice_store.flashcard_reviews(self.db, card["id"])), 1)

    def test_arquivar_sai_da_fila(self):
        card = practice_store.create_flashcard(self.db, frente="F?", verso="V")
        practice_store.update_flashcard(self.db, card["id"], estado="arquivado")
        self.assertEqual(practice_store.study_queue(self.db)["fila"], [])
        with self.assertRaises(ValueError):
            practice_store.review_flashcard(self.db, card["id"], 4)

    def test_fila_recuperada_apos_reinicio(self):
        card = practice_store.create_flashcard(self.db, frente="F?", verso="V")
        # Nova leitura (simula reinício) encontra o cartão novo.
        self.assertIn(card["id"], [c["id"] for c in practice_store.study_queue(self.db)["fila"]])

    def test_qualidade_invalida_rejeitada(self):
        card = practice_store.create_flashcard(self.db, frente="F?", verso="V")
        with self.assertRaises(ValueError):
            practice_store.review_flashcard(self.db, card["id"], 9)

    def test_estatisticas_derivadas(self):
        card = practice_store.create_flashcard(self.db, frente="F?", verso="V")
        practice_store.review_flashcard(self.db, card["id"], 5)
        stats = practice_store.flashcard_stats(self.db)
        self.assertEqual(stats["revisoes"], 1)
        self.assertEqual(stats["pct_acerto"], 100)


class QuestionStoreTest(PracticeBase):
    def test_criar_registra_versao(self):
        q = self._question()
        self.assertEqual(q["versao"], 1)
        self.assertEqual(len(q["alternativas"]), 3)
        self.assertIsNotNone(practice_store.question_version(self.db, q["id"], 1))

    def test_editar_cria_nova_versao(self):
        q = self._question()
        updated = practice_store.update_question(self.db, q["id"], enunciado="Enunciado revisado?")
        self.assertEqual(updated["versao"], 2)
        # Versão 1 permanece intacta no histórico.
        old = practice_store.question_version(self.db, q["id"], 1)
        self.assertEqual(old["enunciado"], "Questão número 0?")

    def test_tentativa_preserva_versao_respondida(self):
        q = self._question()
        attempt = practice_store.answer_question(self.db, q["id"], "B")
        self.assertEqual(attempt["questao_versao"], 1)
        practice_store.update_question(self.db, q["id"], gabarito="C")
        attempts = practice_store.list_attempts(self.db)
        self.assertEqual(attempts[0]["questao_versao"], 1)  # histórico intacto
        self.assertTrue(attempts[0]["correta"])

    def test_branco_registrado_sem_erro(self):
        q = self._question()
        out = practice_store.answer_question(self.db, q["id"], "")
        self.assertFalse(out["respondida"])
        self.assertIsNone(out["correta"])
        self.assertFalse(practice_store.list_attempts(self.db)[0]["respondida"])

    def test_arquivar_preserva_tentativas(self):
        q = self._question()
        practice_store.answer_question(self.db, q["id"], "B")
        practice_store.archive_question(self.db, q["id"])
        self.assertEqual(len(practice_store.list_attempts(self.db)), 1)
        with self.assertRaises(ValueError):
            practice_store.answer_question(self.db, q["id"], "B")

    def test_formato_invalido_rejeitado(self):
        with self.assertRaises(ValueError):
            practice_store.create_question(self.db, enunciado="Pergunta?", alternativas=["a"],
                                           gabarito="A")


class ExamStoreTest(PracticeBase):
    def _questions(self, n=5):
        return [self._question(i) for i in range(n)]

    def test_simulado_sem_duplicacao(self):
        self._questions(5)
        exam = practice_store.create_exam(self.db, nome="S", limit=10, seed=1)
        ids = [i["questao_id"] for i in practice_store.exam_items(self.db, exam["id"])]
        self.assertEqual(len(ids), len(set(ids)))

    def test_resposta_progressiva_e_recuperacao(self):
        self._questions(3)
        exam = practice_store.create_exam(self.db, nome="S", limit=3, seed=1)
        practice_store.save_exam_answer(self.db, exam["id"], 1, "B")
        # Nova leitura (simula recarregar a página) vê a resposta salva.
        items = practice_store.exam_items(self.db, exam["id"])
        self.assertEqual(items[1]["resposta"], "B")
        self.assertTrue(items[1]["respondida"])

    def test_finalizar_persiste_resultado(self):
        self._questions(3)
        exam = practice_store.create_exam(self.db, nome="S", limit=3, seed=1)
        practice_store.save_exam_answer(self.db, exam["id"], 0, "B")
        out = practice_store.finish_exam(self.db, exam["id"])
        self.assertEqual(out["simulado"]["estado"], "finalizado")
        self.assertEqual(out["resultado"]["total"], 3)
        self.assertEqual(out["resultado"]["brancos"], 2)
        self.assertEqual(len(practice_store.list_attempts(self.db, simulado_id=exam["id"])), 3)

    def test_versao_aplicada_preservada(self):
        qs = self._questions(2)
        exam = practice_store.create_exam(self.db, nome="S", limit=2, seed=1)
        practice_store.update_question(self.db, qs[0]["id"], gabarito="C")
        items = practice_store.exam_items(self.db, exam["id"])
        target = next(i for i in items if i["questao_id"] == qs[0]["id"])
        self.assertEqual(target["questao_versao"], 1)
        self.assertEqual(target["gabarito"], "B")  # gabarito original aplicado

    def test_expiracao_decidida_no_servidor(self):
        self._questions(2)
        exam = practice_store.create_exam(self.db, nome="S", limit=2, duracao_segundos=60)
        past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        conn = connect_documents(self.db)
        try:
            conn.execute("UPDATE pratica_simulados SET iniciado_em=? WHERE id=?", (past, exam["id"]))
            conn.commit()
        finally:
            conn.close()
        reloaded = practice_store.get_exam(self.db, exam["id"])
        self.assertEqual(reloaded["estado"], "expirado")
        with self.assertRaises(ValueError):
            practice_store.save_exam_answer(self.db, exam["id"], 0, "B")

    def test_sem_questoes_elegiveis_falha(self):
        with self.assertRaises(ValueError):
            practice_store.create_exam(self.db, nome="S", limit=5)

    def test_desempenho_agrega(self):
        self._questions(2)
        exam = practice_store.create_exam(self.db, nome="S", limit=2, seed=1)
        practice_store.save_exam_answer(self.db, exam["id"], 0, "B")
        practice_store.finish_exam(self.db, exam["id"])
        report = practice_store.performance_report(self.db)
        self.assertGreaterEqual(report["geral"]["total"], 2)
        self.assertTrue(report["por_disciplina"])

    def test_finish_idempotente(self):
        # Regressão C1: finalizar duas vezes não pode duplicar tentativas.
        self._questions(3)
        exam = practice_store.create_exam(self.db, nome="S", limit=3, seed=1)
        practice_store.finish_exam(self.db, exam["id"])
        practice_store.finish_exam(self.db, exam["id"])
        self.assertEqual(len(practice_store.list_attempts(self.db, simulado_id=exam["id"])), 3)

    def test_finish_idempotente_quando_expirado(self):
        # Regressão C1: o caminho "expirado" também precisa ser idempotente.
        self._questions(2)
        exam = practice_store.create_exam(self.db, nome="S", limit=2, duracao_segundos=60)
        past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        conn = connect_documents(self.db)
        try:
            conn.execute("UPDATE pratica_simulados SET iniciado_em=? WHERE id=?", (past, exam["id"]))
            conn.commit()
        finally:
            conn.close()
        practice_store.finish_exam(self.db, exam["id"])
        practice_store.finish_exam(self.db, exam["id"])
        self.assertEqual(len(practice_store.list_attempts(self.db, simulado_id=exam["id"])), 2)

    def test_resultado_nao_vaza_gabarito_em_andamento(self):
        # Regressão C3: prova em andamento não pode revelar o gabarito.
        self._questions(2)
        exam = practice_store.create_exam(self.db, nome="S", limit=2, seed=1)
        with self.assertRaises(ValueError):
            practice_store.exam_result(self.db, exam["id"])
        # O caminho de retomada devolve as questões SEM gabarito.
        questions_payload = practice_store.exam_questions(self.db, exam["id"])
        self.assertEqual(len(questions_payload["questoes"]), 2)
        for item in questions_payload["questoes"]:
            self.assertNotIn("gabarito", item)

    def test_resultado_apos_finalizar_tem_gabarito(self):
        self._questions(2)
        exam = practice_store.create_exam(self.db, nome="S", limit=2, seed=1)
        out = practice_store.finish_exam(self.db, exam["id"])
        self.assertTrue(all("gabarito" in q for q in out["questoes"]))

    def test_snapshot_de_disciplina_na_versao_aplicada(self):
        # Regressão I1: editar a questão não reatribui o escopo da prova antiga.
        qs = self._questions(2)
        exam = practice_store.create_exam(self.db, nome="S", limit=2, seed=1)
        practice_store.update_question(self.db, qs[0]["id"], disciplina="Português")
        items = practice_store.exam_items(self.db, exam["id"])
        target = next(i for i in items if i["questao_id"] == qs[0]["id"])
        self.assertEqual(target["disciplina"], "Matemática")

    def test_responder_sem_ordem_falha_com_erro_de_validacao(self):
        # Regressão I4: `ordem` ausente deve ser 400 (ValueError), não derrubar a conexão.
        self._questions(2)
        exam = practice_store.create_exam(self.db, nome="S", limit=2, seed=1)
        with self.assertRaises(ValueError):
            practice_store.save_exam_answer(self.db, exam["id"], None, "B")


class PracticeApiTest(PracticeBase):
    def setUp(self):
        super().setUp()
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

    def test_fluxo_completo_pela_api(self):
        v1_before = self.request("/api/concursos")[1]
        status, body = self.request("/api/estudos/flashcards", "POST",
                                    json.dumps({"frente": "F?", "verso": "V"}))
        self.assertEqual(status, 200)
        card = json.loads(body)["id"]
        self.assertEqual(self.request("/api/estudos/flashcards", "POST",
                                      json.dumps({"action": "review", "id": card,
                                                  "qualidade": 4}))[0], 200)
        for i in range(3):
            self.request("/api/estudos/questoes", "POST", json.dumps({
                "enunciado": f"Questão {i}?", "alternativas": ["a", "b", "c"], "gabarito": "B",
                "disciplina": "Mat", "topico": "Arit"}))
        qid = json.loads(self.request("/api/estudos/questoes")[1])[0]["id"]
        self.assertEqual(self.request("/api/estudos/tentativas", "POST",
                                      json.dumps({"questao_id": qid, "resposta": "B"}))[0], 200)
        status, body = self.request("/api/estudos/simulados", "POST", json.dumps({
            "nome": "S", "limit": 5, "duracao_segundos": 3600, "seed": 1,
            "exclude_answered": False}))
        self.assertEqual(status, 200)
        exam = json.loads(body)["id"]
        self.assertEqual(self.request(f"/api/estudos/simulados/{exam}/responder", "POST",
                                      json.dumps({"ordem": 0, "resposta": "B"}))[0], 200)
        self.assertEqual(self.request(f"/api/estudos/simulados/{exam}/finalizar", "POST",
                                      json.dumps({}))[0], 200)
        result = json.loads(self.request(f"/api/estudos/simulados/{exam}/resultado")[1])
        self.assertEqual(result["resultado"]["total"], 3)
        self.assertEqual(self.request("/api/concursos")[1], v1_before)  # v1 intacta

    def test_endpoints_de_leitura(self):
        self._question()
        for path in ("/api/estudos/flashcards", "/api/estudos/flashcards/fila",
                     "/api/estudos/flashcards/estatisticas", "/api/estudos/questoes",
                     "/api/estudos/tentativas", "/api/estudos/desempenho",
                     "/api/estudos/simulados"):
            self.assertEqual(self.request(path)[0], 200, path)

    def test_entradas_invalidas(self):
        self.assertEqual(self.request("/api/estudos/flashcards", "POST",
                                      json.dumps({"action": "nope"}))[0], 400)
        self.assertEqual(self.request("/api/estudos/questoes", "POST",
                                      json.dumps({"enunciado": "x"}))[0], 400)
        self.assertEqual(self.request("/api/estudos/simulados", "POST",
                                      json.dumps({"nome": "S", "limit": 1}))[0], 400)
        self.assertEqual(self.request("/api/estudos/flashcards", "POST", "nao-json")[0], 400)

    def test_metodos_invalidos(self):
        self.assertEqual(self.request("/api/estudos/flashcards", "PUT")[0], 405)
        self.assertEqual(self.request("/api/estudos/questoes", "DELETE")[0], 405)
        self.assertEqual(self.request("/api/estudos/flashcards?x=1")[0], 400)


if __name__ == "__main__":
    unittest.main()
