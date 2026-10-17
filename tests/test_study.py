"""Lógica pura de estudos: revisões espaçadas, progresso, tempo e validação de sessão."""

import unittest
from datetime import datetime, timedelta, timezone

from radar import study


class RevisionTest(unittest.TestCase):
    def test_datas_de_revisao_padrao(self):
        self.assertEqual(study.revision_dates("2026-01-01", []),
                         ["2026-01-02", "2026-01-08", "2026-01-31", "2026-04-01"])

    def test_revisoes_feitas_consomem_a_proxima_frequencia(self):
        self.assertEqual(study.revision_dates("2026-01-01", ["2026-01-02"]),
                         ["2026-01-08", "2026-01-31", "2026-04-01"])

    def test_adiamento_desloca_a_agenda(self):
        self.assertEqual(study.revision_dates("2026-01-01", [], 5)[0], "2026-01-07")

    def test_data_invalida_devolve_vazio(self):
        self.assertEqual(study.revision_dates(None, []), [])
        self.assertEqual(study.revision_dates("nao-e-data", []), [])

    def test_todas_as_revisoes_feitas_devolve_vazio(self):
        self.assertEqual(study.revision_dates("2026-01-01", ["a", "b", "c", "d"]), [])

    def test_pendentes_apenas_vencidas(self):
        hoje = "2026-01-10"
        progressos = [
            {"id": "p1", "state": "concluido", "data_conclusao": "2026-01-01", "revisoes": []},
            {"id": "p2", "state": "estudando", "data_conclusao": None, "revisoes": []},
            {"id": "p3", "state": "concluido", "data_conclusao": "2026-12-01", "revisoes": []},
        ]
        pend = study.pending_revisions(progressos, today=hoje)
        self.assertEqual([p["progresso_id"] for p in pend], ["p1"])
        self.assertEqual(pend[0]["data"], "2026-01-02")


class ProgressTest(unittest.TestCase):
    def test_progresso_por_topico(self):
        disciplinas = [
            {"topicos": [{"state": "concluido"}, {"state": "estudando"}, {"state": "nao_iniciado"}]},
            {"topicos": [{"state": "concluido"}]},
        ]
        out = study.content_progress(disciplinas)
        self.assertEqual(out["topics"], {"done": 2, "total": 4, "pct": 50})

    def test_sem_topicos_nao_divide_por_zero(self):
        self.assertEqual(study.content_progress([{"topicos": []}])["overall"]["pct"], 0)
        self.assertEqual(study.content_progress([])["overall"]["pct"], 0)


class ElapsedTest(unittest.TestCase):
    def test_pausada_usa_acumulado(self):
        session = {"estado": "pausada", "duracao_segundos": 120, "inicio": None}
        self.assertEqual(study.elapsed_seconds(session), 120)

    def test_andamento_soma_segmento(self):
        inicio = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        session = {"estado": "em_andamento", "duracao_segundos": 60, "inicio": inicio}
        self.assertGreaterEqual(study.elapsed_seconds(session), 89)

    def test_nunca_negativo(self):
        session = {"estado": "pausada", "duracao_segundos": -50, "inicio": None}
        self.assertEqual(study.elapsed_seconds(session), 0)

    def test_capped_elapsed_trunca_sessao_longa(self):
        # Regressão: fechar o app por dias não pode virar horas de estudo.
        inicio = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        session = {"estado": "em_andamento", "duracao_segundos": 0, "inicio": inicio}
        self.assertEqual(study.capped_elapsed(session), study.MAX_SESSION_SECONDS)

    def test_capped_elapsed_preserva_sessao_curta(self):
        session = {"estado": "pausada", "duracao_segundos": 120, "inicio": None}
        self.assertEqual(study.capped_elapsed(session), 120)

    def test_local_today_retorna_data(self):
        from datetime import date as _date
        self.assertIsInstance(study.local_today(), _date)


class AggregateTest(unittest.TestCase):
    def _sessions(self):
        return [
            {"estado": "concluida", "duracao_segundos": 600, "disciplina_id": "d1", "fim": "2026-01-10T12:00:00+00:00"},
            {"estado": "concluida", "duracao_segundos": 300, "disciplina_id": "d1", "fim": "2026-01-09T12:00:00+00:00"},
            {"estado": "concluida", "duracao_segundos": 900, "disciplina_id": "d2", "fim": "2026-01-01T12:00:00+00:00"},
            {"estado": "descartada", "duracao_segundos": 5000, "disciplina_id": "d1", "fim": "2026-01-10T12:00:00+00:00"},
        ]

    def test_total_ignora_descartadas(self):
        self.assertEqual(study.total_study_seconds(self._sessions()), 1800)

    def test_total_por_janela(self):
        self.assertEqual(study.total_study_seconds(self._sessions(), days=2, today="2026-01-10"), 900)

    def test_minutos_por_disciplina(self):
        self.assertEqual(study.minutes_by_discipline(self._sessions()), {"d1": 15, "d2": 15})


class ValidateSessionTest(unittest.TestCase):
    def test_duracao_valida(self):
        self.assertEqual(study.validate_session("2026-01-01T10:00:00+00:00",
                                                "2026-01-01T11:00:00+00:00"), 3600)

    def test_fim_antes_do_inicio_rejeitado(self):
        with self.assertRaises(ValueError):
            study.validate_session("2026-01-01T11:00:00+00:00", "2026-01-01T10:00:00+00:00")

    def test_duracao_absurda_rejeitada(self):
        with self.assertRaises(ValueError):
            study.validate_session("2026-01-01T00:00:00+00:00", "2026-01-03T00:00:00+00:00")

    def test_datas_invalidas_rejeitadas(self):
        with self.assertRaises(ValueError):
            study.validate_session(None, "2026-01-01T10:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
