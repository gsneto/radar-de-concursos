"""Flashcards: agendamento SM-2-lite (adaptado, MIT), fila e estatísticas."""

import unittest
from datetime import date

from radar import flashcards


class ScheduleTest(unittest.TestCase):
    def test_lapso_reseta_sem_mexer_no_ease(self):
        # Mesma semântica do projeto de origem (MIT): lapso não ajusta o ease.
        out = flashcards.schedule_review(ease=2.5, interval=10, repetitions=3, quality=2,
                                         today=date(2024, 1, 1))
        self.assertEqual(out["repeticoes"], 0)
        self.assertEqual(out["intervalo"], 1)
        self.assertEqual(out["ease"], 2.5)
        self.assertEqual(out["proxima_revisao"], "2024-01-02")

    def test_primeiro_acerto_um_dia(self):
        out = flashcards.schedule_review(ease=2.5, interval=0, repetitions=0, quality=4,
                                         today=date(2024, 1, 1))
        self.assertEqual((out["repeticoes"], out["intervalo"]), (1, 1))
        self.assertEqual(out["proxima_revisao"], "2024-01-02")

    def test_segundo_acerto_seis_dias(self):
        out = flashcards.schedule_review(ease=2.5, interval=1, repetitions=1, quality=4,
                                         today=date(2024, 1, 1))
        self.assertEqual((out["repeticoes"], out["intervalo"]), (2, 6))

    def test_terceiro_acerto_multiplica_pelo_ease_anterior(self):
        out = flashcards.schedule_review(ease=2.5, interval=6, repetitions=2, quality=4,
                                         today=date(2024, 1, 1))
        self.assertEqual(out["intervalo"], round(6 * 2.5))

    def test_qualidade_4_nao_muda_ease(self):
        out = flashcards.schedule_review(ease=2.5, interval=6, repetitions=2, quality=4)
        self.assertEqual(out["ease"], 2.5)

    def test_qualidade_5_aumenta_ease(self):
        out = flashcards.schedule_review(ease=2.5, interval=6, repetitions=2, quality=5)
        self.assertGreater(out["ease"], 2.5)

    def test_ease_nunca_abaixo_do_piso(self):
        out = flashcards.schedule_review(ease=1.3, interval=6, repetitions=2, quality=3)
        self.assertEqual(out["ease"], flashcards.MIN_EASE)

    def test_qualidade_fora_da_faixa_rejeitada(self):
        for quality in (-1, 6, 99):
            with self.assertRaises(ValueError):
                flashcards.schedule_review(ease=2.5, interval=1, repetitions=0, quality=quality)
        with self.assertRaises(ValueError):
            flashcards.schedule_review(ease=2.5, interval=1, repetitions=0, quality=True)

    def test_deterministico(self):
        a = flashcards.schedule_review(ease=2.4, interval=6, repetitions=2, quality=4,
                                       today=date(2024, 5, 1))
        b = flashcards.schedule_review(ease=2.4, interval=6, repetitions=2, quality=4,
                                       today=date(2024, 5, 1))
        self.assertEqual(a, b)


class QueueTest(unittest.TestCase):
    def _card(self, cid, proxima=None, revisoes=0, estado="ativo"):
        return {"id": cid, "estado": estado, "proxima_revisao": proxima, "revisoes": revisoes}

    def test_novos_antes_dos_vencidos(self):
        cards = [self._card("v", "2020-01-01", 1), self._card("n", None, 0)]
        out = flashcards.queue(cards, today="2026-01-01")
        self.assertEqual([c["id"] for c in out["fila"]], ["n", "v"])

    def test_arquivado_fora_da_fila(self):
        cards = [self._card("a", estado="arquivado"), self._card("b", None, 0)]
        out = flashcards.queue(cards, today="2026-01-01")
        self.assertEqual([c["id"] for c in out["fila"]], ["b"])

    def test_futuro_nao_entra_na_fila(self):
        cards = [self._card("f", "2030-01-01", 1)]
        out = flashcards.queue(cards, today="2026-01-01")
        self.assertEqual(out["fila"], [])
        self.assertEqual(len(out["futuros"]), 1)

    def test_limit_corta_sem_descartar(self):
        cards = [self._card(f"c{i}", None, 0) for i in range(10)]
        out = flashcards.queue(cards, today="2026-01-01", limit=3)
        self.assertEqual(len(out["fila"]), 3)
        self.assertEqual(out["total_pendente"], 10)  # nada é descartado


class StatsTest(unittest.TestCase):
    def test_percentual_sobre_revisoes_registradas(self):
        cards = [{"estado": "ativo", "revisoes": 1, "proxima_revisao": "2020-01-01"}]
        reviews = [{"qualidade": 4}, {"qualidade": 5}, {"qualidade": 1}]
        out = flashcards.stats(cards, reviews, today="2026-01-01")
        self.assertEqual(out["revisoes"], 3)
        self.assertEqual(out["acertos"], 2)
        self.assertEqual(out["pct_acerto"], 67)

    def test_sem_revisoes_nao_calculavel(self):
        out = flashcards.stats([{"estado": "ativo", "revisoes": 0}], [], today="2026-01-01")
        self.assertIsNone(out["pct_acerto"])
        self.assertIn("não calculável", out["basis"])

    def test_arquivados_contados_separadamente(self):
        cards = [{"estado": "ativo", "revisoes": 0}, {"estado": "arquivado", "revisoes": 2}]
        out = flashcards.stats(cards, [], today="2026-01-01")
        self.assertEqual((out["ativos"], out["arquivados"]), (1, 1))


if __name__ == "__main__":
    unittest.main()
