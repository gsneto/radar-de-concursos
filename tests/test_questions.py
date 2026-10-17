"""Questões: validação de formato, correção e estatísticas com denominador explícito."""

import unittest

from radar import questions


class ValidateTest(unittest.TestCase):
    def test_escolha_unica_valida(self):
        out = questions.validate_question(enunciado="Quanto é 2+2?", alternativas=["3", "4", "5"],
                                          gabarito="B")
        self.assertEqual([a["id"] for a in out["alternativas"]], ["A", "B", "C"])
        self.assertEqual(out["gabarito"], "B")

    def test_gabarito_inexistente_rejeitado(self):
        with self.assertRaises(ValueError):
            questions.validate_question(enunciado="Pergunta?", alternativas=["a", "b"], gabarito="Z")

    def test_menos_de_duas_alternativas_rejeitado(self):
        with self.assertRaises(ValueError):
            questions.validate_question(enunciado="Pergunta?", alternativas=["a"], gabarito="A")

    def test_alternativa_vazia_rejeitada(self):
        with self.assertRaises(ValueError):
            questions.validate_question(enunciado="Pergunta?", alternativas=["a", "  "], gabarito="A")

    def test_alternativas_duplicadas_rejeitadas(self):
        with self.assertRaises(ValueError):
            questions.validate_question(
                enunciado="Pergunta?", alternativas=[{"id": "A", "texto": "x"},
                                                     {"id": "A", "texto": "y"}], gabarito="A")

    def test_enunciado_curto_rejeitado(self):
        with self.assertRaises(ValueError):
            questions.validate_question(enunciado="oi", alternativas=["a", "b"], gabarito="A")

    def test_verdadeiro_falso(self):
        out = questions.validate_question(enunciado="A terra é plana?", tipo="verdadeiro_falso",
                                          alternativas=None, gabarito="F")
        self.assertEqual(out["gabarito"], "F")
        self.assertEqual(len(out["alternativas"]), 2)

    def test_verdadeiro_falso_gabarito_invalido(self):
        with self.assertRaises(ValueError):
            questions.validate_question(enunciado="A terra é plana?", tipo="verdadeiro_falso",
                                        alternativas=None, gabarito="X")

    def test_dificuldade_invalida(self):
        with self.assertRaises(ValueError):
            questions.validate_question(enunciado="Pergunta?", alternativas=["a", "b"],
                                        gabarito="A", dificuldade="impossivel")


class GradeTest(unittest.TestCase):
    def test_resposta_correta(self):
        out = questions.grade({"gabarito": "B"}, "b")
        self.assertEqual(out, {"respondida": True, "correta": True})

    def test_resposta_errada(self):
        out = questions.grade({"gabarito": "B"}, "A")
        self.assertEqual(out, {"respondida": True, "correta": False})

    def test_branco_nao_e_erro(self):
        self.assertEqual(questions.grade({"gabarito": "B"}, ""), {"respondida": False, "correta": None})
        self.assertEqual(questions.grade({"gabarito": "B"}, None), {"respondida": False, "correta": None})


class StatsTest(unittest.TestCase):
    def _a(self, correta, respondida=True, disciplina="Mat", topico="Arit"):
        return {"correta": correta, "respondida": respondida, "disciplina": disciplina, "topico": topico}

    def test_brancos_fora_do_denominador_por_padrao(self):
        out = questions.stats([self._a(True), self._a(False), self._a(None, respondida=False)])
        self.assertEqual(out["denominator"], 2)
        self.assertEqual(out["pct"], 50)
        self.assertEqual(out["brancos"], 1)

    def test_brancos_dentro_do_denominador_quando_pedido(self):
        out = questions.stats([self._a(True), self._a(None, respondida=False)], include_blank=True)
        self.assertEqual(out["denominator"], 2)
        self.assertEqual(out["pct"], 50)

    def test_sem_tentativas_nao_calculavel(self):
        out = questions.stats([])
        self.assertIsNone(out["pct"])
        self.assertIn("não calculável", out["basis"])

    def test_agrupamento_por_disciplina(self):
        out = questions.stats_by([self._a(True, disciplina="Mat"), self._a(False, disciplina="Port")],
                                 "disciplina")
        self.assertEqual({g["grupo"] for g in out}, {"Mat", "Port"})
        self.assertEqual(next(g for g in out if g["grupo"] == "Mat")["pct"], 100)


if __name__ == "__main__":
    unittest.main()
