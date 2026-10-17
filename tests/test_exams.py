"""Simulados: seleção sem duplicação, cronômetro, expiração e correção."""

import unittest
from datetime import datetime, timedelta, timezone

from radar import exams


def _q(qid, **kwargs):
    base = {"id": qid, "estado": "ativo", "disciplina": "Mat", "topico": "Arit",
            "dificuldade": "media", "tags": ["x"]}
    base.update(kwargs)
    return base


class SelectTest(unittest.TestCase):
    def test_sem_duplicacao(self):
        pool = [_q("a"), _q("a"), _q("b")]
        out = exams.select_questions(pool, limit=10, seed=1)
        self.assertEqual([q["id"] for q in out], ["a", "b"])

    def test_limite_respeitado(self):
        pool = [_q(str(i)) for i in range(10)]
        self.assertEqual(len(exams.select_questions(pool, limit=3, seed=1)), 3)

    def test_exclui_respondidas(self):
        pool = [_q("a"), _q("b")]
        out = exams.select_questions(pool, limit=10, seed=1, exclude_answered=["a"])
        self.assertEqual([q["id"] for q in out], ["b"])

    def test_apenas_ativas(self):
        pool = [_q("a", estado="arquivado"), _q("b")]
        self.assertEqual([q["id"] for q in exams.select_questions(pool, limit=10, seed=1)], ["b"])

    def test_filtro_por_disciplina(self):
        pool = [_q("a", disciplina="Mat"), _q("b", disciplina="Port")]
        out = exams.select_questions(pool, limit=10, seed=1, disciplina="Port")
        self.assertEqual([q["id"] for q in out], ["b"])

    def test_mesmo_seed_mesma_ordem(self):
        pool = [_q(str(i)) for i in range(8)]
        a = [q["id"] for q in exams.select_questions(pool, limit=8, seed=42)]
        b = [q["id"] for q in exams.select_questions(pool, limit=8, seed=42)]
        self.assertEqual(a, b)


class TimerTest(unittest.TestCase):
    def _start(self, seconds_ago):
        return (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()

    def test_restante_calculado_no_servidor(self):
        remaining = exams.remaining_seconds(self._start(100), 3600)
        self.assertTrue(3490 <= remaining <= 3500)

    def test_sem_limite_devolve_none(self):
        self.assertIsNone(exams.remaining_seconds(self._start(10), None))

    def test_expirado(self):
        self.assertTrue(exams.is_expired(self._start(7200), 3600))
        self.assertFalse(exams.is_expired(self._start(10), 3600))

    def test_restante_nunca_negativo(self):
        self.assertEqual(exams.remaining_seconds(self._start(99999), 60), 0)


class ResultTest(unittest.TestCase):
    def _item(self, resposta, gabarito="B", disciplina="Mat", topico="Arit"):
        return {"questao_id": "q", "questao_versao": 1, "resposta": resposta, "gabarito": gabarito,
                "respondida": bool(resposta), "disciplina": disciplina, "topico": topico}

    def test_acertos_e_brancos(self):
        items = [self._item("B"), self._item("A"), self._item(None)]
        out = exams.result(items, duration_seconds=3600,
                           started_at="2026-01-01T10:00:00+00:00",
                           finished_at="2026-01-01T10:10:00+00:00")
        self.assertEqual((out["total"], out["acertos"], out["erros"], out["brancos"]), (3, 1, 1, 1))
        self.assertEqual(out["pct"], 33)  # branco no denominador
        self.assertEqual(out["tempo_usado_segundos"], 600)

    def test_erradas_listadas(self):
        out = exams.result([self._item("A"), self._item("B")])
        self.assertEqual(len(out["erradas"]), 1)

    def test_por_disciplina_e_topico(self):
        items = [self._item("B", disciplina="Mat"), self._item("A", disciplina="Port")]
        out = exams.result(items)
        self.assertEqual({g["grupo"] for g in out["por_disciplina"]}, {"Mat", "Port"})
        self.assertEqual(next(g for g in out["por_disciplina"] if g["grupo"] == "Mat")["pct"], 100)

    def test_sem_questoes_nao_calculavel(self):
        out = exams.result([])
        self.assertIsNone(out["pct"])
        self.assertIn("não calculável", out["basis"])


if __name__ == "__main__":
    unittest.main()
