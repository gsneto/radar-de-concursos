"""Pontuação adaptativa determinística e explicável (Fase 24)."""

import unittest
from datetime import datetime, timedelta, timezone

from radar import adaptive

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


def attempt(topico, correta, days_ago=0, respondida=True):
    return {
        "topico": topico,
        "correta": correta,
        "respondida": respondida,
        "created_at": (NOW - timedelta(days=days_ago)).isoformat(),
    }


def question(qid, topico, **kwargs):
    data = {"id": qid, "topico": topico, "enunciado": "Pergunta " + qid, "estado": "ativo"}
    data.update(kwargs)
    return data


class HistoryTest(unittest.TestCase):
    def test_branco_nao_conta_como_erro(self):
        history = adaptive.topic_history(
            [attempt("Redes", True), attempt("Redes", None, respondida=False)], now=NOW)
        self.assertEqual(history["Redes"]["tentativas"], 1)
        self.assertEqual(history["Redes"]["acertos"], 1)
        self.assertEqual(history["Redes"]["erros"], 0)

    def test_sem_topico_agrupa_em_rotulo_proprio(self):
        history = adaptive.topic_history([attempt("", True)], now=NOW)
        self.assertIn("(sem tópico)", history)

    def test_janela_recente_limitada(self):
        attempts = [attempt("Redes", i % 2 == 0) for i in range(20)]
        history = adaptive.topic_history(attempts, now=NOW)
        self.assertEqual(len(history["Redes"]["recentes"]), adaptive.RECENT_WINDOW)

    def test_janela_recente_usa_as_tentativas_mais_novas(self):
        # list_attempts devolve DESC; o histórico deve ordenar antes de cortar a janela.
        attempts = [attempt("Redes", False, days_ago=20 - i) for i in range(10)]
        attempts += [attempt("Redes", True, days_ago=i) for i in range(5)]
        history = adaptive.topic_history(attempts, now=NOW)
        self.assertEqual(history["Redes"]["recentes"][-5:], [True] * 5)
        result = adaptive.score_question(
            question("q1", "Redes"), history=history, profile={}, now=NOW)
        erro = next(f for f in result["factors"] if f["fator"] == "erro_recente")
        self.assertEqual(erro["pontos"], 2)  # 5 erros antigos, 5 acertos recentes

    def test_ultima_pratica_e_a_mais_recente(self):
        history = adaptive.topic_history(
            [attempt("Redes", True, days_ago=5), attempt("Redes", False, days_ago=1)], now=NOW)
        self.assertIn("2026-10-16", history["Redes"]["ultima_pratica"])


class ScoreTest(unittest.TestCase):
    def test_sem_evidencia_tem_confianca_baixa(self):
        result = adaptive.score_question(
            question("q1", "Redes"), history={}, profile={}, now=NOW)
        self.assertEqual(result["confidence"], "baixa")
        self.assertLess(result["score"], adaptive.MAX_SCORE)

    def test_cada_fator_tem_motivo_e_limite(self):
        result = adaptive.score_question(
            question("q1", "Redes"), history={}, profile={}, now=NOW)
        self.assertEqual(len(result["factors"]), len(adaptive.WEIGHTS))
        for factor in result["factors"]:
            self.assertIn(factor["fator"], adaptive.WEIGHTS)
            self.assertLessEqual(factor["pontos"], factor["max"])
            self.assertTrue(factor["motivo"])

    def test_poucas_tentativas_nao_geram_peso_maximo_de_erro(self):
        history = adaptive.topic_history([attempt("Redes", False)], now=NOW)
        result = adaptive.score_question(
            question("q1", "Redes"), history=history, profile={}, now=NOW)
        erro = next(f for f in result["factors"] if f["fator"] == "erro_recente")
        self.assertEqual(erro["pontos"], 1)
        self.assertIn("insuficiente", erro["motivo"])

    def test_muitos_erros_geram_peso_maximo(self):
        history = adaptive.topic_history(
            [attempt("Redes", False, days_ago=i) for i in range(4)], now=NOW)
        result = adaptive.score_question(
            question("q1", "Redes"), history=history, profile={}, now=NOW)
        erro = next(f for f in result["factors"] if f["fator"] == "erro_recente")
        self.assertEqual(erro["pontos"], 3)

    def test_revisao_atrasada(self):
        history = adaptive.topic_history(
            [attempt("Redes", True, days_ago=30)], now=NOW)
        result = adaptive.score_question(
            question("q1", "Redes"), history=history, profile={}, now=NOW)
        atraso = next(f for f in result["factors"] if f["fator"] == "revisao_atrasada")
        self.assertEqual(atraso["pontos"], 2)

    def test_lacuna_declarada_no_perfil(self):
        result = adaptive.score_question(
            question("q1", "Redes", conceito_key="redes"),
            history={}, profile={"redes": {"nivel": "nao_conheco", "revisar": False}}, now=NOW)
        lacuna = next(f for f in result["factors"] if f["fator"] == "lacuna_perfil")
        self.assertEqual(lacuna["pontos"], 2)

    def test_dificuldade_alta_com_bom_desempenho(self):
        result = adaptive.score_question(
            question("q1", "Redes", dificuldade="dificil"),
            history={}, profile={}, now=NOW, global_accuracy=0.9)
        dificuldade = next(f for f in result["factors"] if f["fator"] == "dificuldade")
        self.assertGreaterEqual(dificuldade["pontos"], 1)

    def test_score_nunca_excede_maximo(self):
        history = adaptive.topic_history(
            [attempt("Redes", False, days_ago=40) for _ in range(5)], now=NOW)
        result = adaptive.score_question(
            question("q1", "Redes", conceito_key="redes", dificuldade="dificil"),
            history=history, profile={"redes": {"nivel": "nao_conheco", "revisar": True}},
            now=NOW, global_accuracy=0.95)
        self.assertLessEqual(result["score"], adaptive.MAX_SCORE)
        self.assertEqual(result["max_score"], adaptive.MAX_SCORE)


class RankingTest(unittest.TestCase):
    def test_deterministico_com_mesma_seed(self):
        questions = [question(f"q{i}", "Topico A") for i in range(5)]
        first = adaptive.rank_questions(questions, history={}, profile={}, now=NOW, seed=7)
        second = adaptive.rank_questions(questions, history={}, profile={}, now=NOW, seed=7)
        self.assertEqual([r["questao_id"] for r in first], [r["questao_id"] for r in second])

    def test_topicos_com_erro_vem_antes_de_intocados(self):
        history = adaptive.topic_history(
            [attempt("Redes", False, days_ago=i) for i in range(4)], now=NOW)
        questions = [question("q-novo", "Banco de Dados"), question("q-erro", "Redes")]
        ranked = adaptive.rank_questions(questions, history=history, profile={}, now=NOW)
        self.assertEqual(ranked[0]["questao_id"], "q-erro")

    def test_plano_respeita_limite(self):
        questions = [question(f"q{i}", f"Topico {i}") for i in range(10)]
        plan = adaptive.session_plan(questions, history={}, profile={}, limit=3, now=NOW)
        self.assertEqual(len(plan), 3)

    def test_plano_vazio_com_limite_zero(self):
        self.assertEqual(adaptive.session_plan([question("q", "A")], history={}, profile={},
                                               limit=0, now=NOW), [])

    def test_next_exclui_ja_usadas(self):
        questions = [question("q1", "A"), question("q2", "B")]
        result = adaptive.next_question(questions, history={}, profile={}, now=NOW,
                                        exclude=("q1",))
        self.assertEqual(result["questao_id"], "q2")

    def test_revisao_erros_so_erradas(self):
        attempts = [
            {"questao_id": "q1", "correta": False, "respondida": True, "topico": "A"},
            {"questao_id": "q2", "correta": True, "respondida": True, "topico": "A"},
        ]
        questions = [question("q1", "A"), question("q2", "A")]
        review = adaptive.review_questions(attempts, questions)
        self.assertEqual([item["id"] for item in review], ["q1"])

    def test_modos_declarados(self):
        self.assertEqual(set(adaptive.MODES),
                         {"tradicional", "adaptativa", "revisao_erros", "personalizada"})
        for mode in adaptive.MODES:
            self.assertIn(mode, adaptive.MODE_LABELS)

    def test_aviso_sobre_comparabilidade(self):
        self.assertIn("NÃO é comparável", adaptive.ADAPTIVE_CAVEAT)


if __name__ == "__main__":
    unittest.main()
