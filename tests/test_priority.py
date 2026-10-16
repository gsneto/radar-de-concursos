"""Priorização integrada: localização real, distância, vagas e compatibilidade."""

import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from radar import preferences, priority
from radar.document_store import (connect_documents, ensure_observation, migrate_document_schema,
                                  record_analysis, record_version, register_document)


def _now():
    return datetime.now(timezone.utc).isoformat()


class PriorityBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "radar.sqlite3")
        migrate_document_schema(self.db)
        self.prefs = preferences.load({})

    def _contest(self, key, proposals, *, validate=(), doc_kind="outro", ambiguous=()):
        """Cria um concurso com um documento analisado e as propostas informadas.

        ``proposals``: lista de ``(field_name, valor_python)``. ``validate``: campos cujo
        valor é marcado como revisado (``validado``). ``ambiguous``: campos marcados como
        ambíguos (``ambiguity_reason``).
        """
        obs = ensure_observation(self.db, f"https://exemplo.test/{key}", key)
        with closing(connect_documents(self.db)) as conn:
            contest_id = conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                      (obs,)).fetchone()[0]
        did = register_document(self.db, dict(
            observation_id=obs, kind=doc_kind, official_url=f"https://exemplo.test/{key}/e.pdf",
            title=f"Edital {key}", discovery_url=f"https://exemplo.test/{key}",
            discovery_method="automatico", discovered_at=_now()))
        blocks = [{"page_number": 1, "locator": "p1", "start_offset": 0, "end_offset": 1, "text": "x"}]
        props = []
        import json
        for field, value in proposals:
            quote = "x"
            props.append(dict(contest_id=contest_id, role_id=None, field_name=field,
                              value_json=json.dumps(value), value_type="string" if isinstance(value, str) else "integer",
                              extraction_method="t",
                              ambiguity_reason=("tabela ilegivel" if field in ambiguous else None),
                              evidence=dict(block_index=0, quote=quote, start_offset=0, end_offset=1)))
        version = record_version(self.db, did, b"%PDF-1.4 x", dict(
            fetched_at=_now(), fetched_url=f"https://exemplo.test/{key}/e.pdf",
            content_type="application/pdf"))
        record_analysis(self.db, version, blocks, props)
        for field in validate:
            with closing(connect_documents(self.db)) as conn, conn:
                pid = conn.execute("SELECT id FROM propostas_campo WHERE contest_id=? AND field_name=?",
                                   (contest_id, field)).fetchone()[0]
                conn.execute("INSERT INTO revisoes_campo VALUES(?,?,?,?,?,?)",
                             (f"rev-{pid}", pid, "validado", _now(), "revisor", "ok"))
                conn.commit()
        return contest_id

    def _items(self, prefs=None, **kwargs):
        return priority.prioritize(self.db, prefs or self.prefs, **kwargs)

    def _add_document(self, contest_id, key, proposals, *, kind="retificacao"):
        """Adiciona um novo documento/versão ao mesmo concurso (ex.: retificação)."""
        import json
        with closing(connect_documents(self.db)) as conn:
            obs = conn.execute("SELECT id FROM observacoes_concurso WHERE contest_id=? LIMIT 1",
                               (contest_id,)).fetchone()[0]
        did = register_document(self.db, dict(
            observation_id=obs, kind=kind, official_url=f"https://exemplo.test/{key}/e.pdf",
            title=f"Doc {key}", discovery_url=f"https://exemplo.test/{key}",
            discovery_method="automatico", discovered_at=_now()))
        blocks = [{"page_number": 2, "locator": "p2", "start_offset": 0, "end_offset": 1, "text": "y"}]
        props = [dict(contest_id=contest_id, role_id=None, field_name=f,
                      value_json=json.dumps(v),
                      value_type="string" if isinstance(v, str) else "integer",
                      extraction_method="t", ambiguity_reason=None,
                      evidence=dict(block_index=0, quote="y", start_offset=0, end_offset=1))
                 for f, v in proposals]
        version = record_version(self.db, did, b"%PDF-1.4 y", dict(
            fetched_at=_now(), fetched_url=f"https://exemplo.test/{key}/e.pdf",
            content_type="application/pdf"))
        record_analysis(self.db, version, blocks, props)
        return version


class RankingIntegrationTest(PriorityBase):
    def test_boa_aderencia_com_prova_proxima(self):
        contest = self._contest("a", [
            ("indigenous_vacancies", 3), ("si_compatibility", "aceito_expressamente"),
            ("exam_location", "Salvador/BA"), ("work_location", "Paulo Afonso/BA")],
            validate=("indigenous_vacancies", "si_compatibility", "exam_location"))
        prefs = preferences.validate({"reference_municipio": "Salvador", "reference_uf": "BA"})
        item = next(i for i in self._items(prefs)["items"] if i["contest_id"] == contest)
        self.assertEqual(item["label"], "boa_aderencia")
        self.assertEqual(item["location"]["prova"]["uf"], "BA")
        self.assertEqual(item["location"]["lotacao"]["municipios"], ["Paulo Afonso"])
        self.assertTrue(item["distance"]["known"])
        self.assertEqual(item["distance"]["kind"], "geografica_linha_reta")

    def test_distante_excepcional_continua_visivel(self):
        contest = self._contest("b", [
            ("indigenous_vacancies", 12), ("si_compatibility", "aceito_expressamente"),
            ("exam_location", "Manaus/AM")],
            validate=("indigenous_vacancies", "si_compatibility", "exam_location"))
        prefs = preferences.validate({"reference_municipio": "Salvador", "reference_uf": "BA"})
        item = next(i for i in self._items(prefs)["items"] if i["contest_id"] == contest)
        self.assertTrue(item["exceptional"])
        self.assertGreaterEqual(item["score"], 10)
        self.assertEqual(item["label"], "oportunidade_importante_distante")

    def test_sem_localizacao_nao_vira_distante(self):
        contest = self._contest("c", [
            ("indigenous_vacancies", 2), ("si_compatibility", "aceito_expressamente")],
            validate=("indigenous_vacancies", "si_compatibility"))
        item = next(i for i in self._items()["items"] if i["contest_id"] == contest)
        self.assertEqual(item["location"]["prova"]["state"], "nao_informado")
        self.assertFalse(item["distance"]["known"])
        self.assertIsNone(item["distance"]["distance_km"])

    def test_lotacao_conhecida_prova_desconhecida(self):
        contest = self._contest("d", [("work_location", "Recife/PE")])
        item = next(i for i in self._items()["items"] if i["contest_id"] == contest)
        self.assertEqual(item["location"]["lotacao"]["uf"], "PE")
        self.assertEqual(item["location"]["prova"]["state"], "nao_informado")
        # A distância de decisão (prova) é desconhecida, apesar da lotação conhecida.
        self.assertFalse(item["distance"]["known"])

    def test_so_cadastro_reserva_nao_e_boa_aderencia(self):
        contest = self._contest("e", [
            ("indigenous_reserve_vacancies", 8), ("si_compatibility", "aceito_expressamente"),
            ("exam_location", "Salvador/BA")],
            validate=("indigenous_reserve_vacancies", "si_compatibility", "exam_location"))
        prefs = preferences.validate({"reference_municipio": "Salvador", "reference_uf": "BA"})
        item = next(i for i in self._items(prefs)["items"] if i["contest_id"] == contest)
        self.assertNotEqual(item["label"], "boa_aderencia")
        self.assertIsNone(item["indigenous_immediate"])

    def test_incompatibilidade_formal(self):
        contest = self._contest("f", [
            ("indigenous_vacancies", 5), ("si_compatibility", "incompativel_com_requisito_explicito"),
            ("exam_location", "Salvador/BA")],
            validate=("indigenous_vacancies", "si_compatibility", "exam_location"))
        item = next(i for i in self._items()["items"] if i["contest_id"] == contest)
        self.assertEqual(item["label"], "compatibilidade_desfavoravel")

    def test_preferencias_alteram_distancia(self):
        contest = self._contest("g", [("exam_location", "Recife/PE")])
        perto = preferences.validate({"reference_municipio": "Recife", "reference_uf": "PE"})
        longe = preferences.validate({"reference_municipio": "Manaus", "reference_uf": "AM"})
        a = next(i for i in self._items(perto)["items"] if i["contest_id"] == contest)
        b = next(i for i in self._items(longe)["items"] if i["contest_id"] == contest)
        self.assertLess(a["distance"]["distance_km"], b["distance"]["distance_km"])

    def test_ordenacao_por_pontuacao_e_deterministica(self):
        self._contest("h", [("indigenous_vacancies", 10), ("si_compatibility", "aceito_expressamente"),
                            ("exam_location", "Salvador/BA")],
                      validate=("indigenous_vacancies", "si_compatibility", "exam_location"))
        self._contest("i", [("indigenous_vacancies", 0), ("si_compatibility", "aceito_expressamente"),
                            ("exam_location", "Salvador/BA")],
                      validate=("indigenous_vacancies", "si_compatibility", "exam_location"))
        first = [i["contest_id"] for i in self._items()["items"]]
        second = [i["contest_id"] for i in self._items()["items"]]
        self.assertEqual(first, second)
        self.assertGreaterEqual(len(first), 2)

    def test_urgencia_exibida_separada_da_pontuacao(self):
        contest = self._contest("j", [
            ("indigenous_vacancies", 4), ("si_compatibility", "aceito_expressamente"),
            ("exam_location", "Salvador/BA"), ("exemption_end", "2020-01-01")],
            validate=("indigenous_vacancies", "si_compatibility", "exam_location"))
        item = next(i for i in self._items()["items"] if i["contest_id"] == contest)
        self.assertIsNotNone(item["urgency"])
        self.assertEqual(item["urgency"]["state"], "expirado")
        # A urgência não entra em factors (dimensão independente).
        self.assertNotIn("urgencia", {f["key"] for f in item["factors"]})


class AmendmentTest(PriorityBase):
    def test_retificacao_altera_local_sem_apagar_historico(self):
        contest = self._contest("r1", [("exam_location", "Salvador/BA")])
        self._add_document(contest, "r1-ret", [("exam_location", "Recife/PE")])
        # Conflito detectado e histórico preservado (ambas as versões presentes).
        with closing(connect_documents(self.db)) as conn:
            count = conn.execute("SELECT count(*) FROM propostas_campo WHERE contest_id=? AND field_name='exam_location'",
                                 (contest,)).fetchone()[0]
        self.assertEqual(count, 2)
        item = next(i for i in self._items()["items"] if i["contest_id"] == contest)
        self.assertEqual(item["location"]["prova"]["state"], "em_conflito")

    def test_valor_validado_vence_conflito_nao_revisado(self):
        # Revisão humana respeitada: um valor validado prevalece sobre proposta não revisada.
        contest = self._contest("r3", [("exam_location", "Salvador/BA")], validate=("exam_location",))
        self._add_document(contest, "r3-ret", [("exam_location", "Recife/PE")])
        item = next(i for i in self._items()["items"] if i["contest_id"] == contest)
        self.assertEqual(item["location"]["prova"]["state"], "confirmado_documentalmente")
        self.assertEqual(item["location"]["prova"]["uf"], "BA")

    def test_lotacao_e_prova_alteradas_em_campos_distintos(self):
        contest = self._contest("r2", [("exam_location", "Salvador/BA"), ("work_location", "Paulo Afonso/BA")])
        self._add_document(contest, "r2-ret", [("work_location", "Recife/PE")])
        item = next(i for i in self._items()["items"] if i["contest_id"] == contest)
        # Prova permanece BA (não alterada); lotação entra em conflito.
        self.assertEqual(item["location"]["prova"]["uf"], "BA")
        self.assertEqual(item["location"]["lotacao"]["state"], "em_conflito")

    def test_si_divergente_sem_revisao_vira_ambiguo(self):
        # Regressão C1: retificação incompatível não pode virar "boa_aderencia".
        contest = self._contest("c1", [("si_compatibility", "aceito_expressamente"),
                                       ("indigenous_vacancies", 5), ("exam_location", "Salvador/BA")],
                                validate=("indigenous_vacancies", "exam_location"))
        self._add_document(contest, "c1-ret", [("si_compatibility", "incompativel_com_requisito_explicito")])
        item = next(i for i in self._items()["items"] if i["contest_id"] == contest)
        self.assertEqual(item["si_compatibility"]["state"], "ambiguo")
        self.assertTrue(item["si_compatibility"]["conflict"])
        self.assertNotEqual(item["label"], "boa_aderencia")

    def test_si_validado_vence_divergencia(self):
        contest = self._contest("c2", [("si_compatibility", "aceito_expressamente"),
                                       ("indigenous_vacancies", 5), ("exam_location", "Salvador/BA")],
                                validate=("si_compatibility", "indigenous_vacancies", "exam_location"))
        self._add_document(contest, "c2-ret", [("si_compatibility", "incompativel_com_requisito_explicito")])
        item = next(i for i in self._items()["items"] if i["contest_id"] == contest)
        self.assertEqual(item["si_compatibility"]["state"], "aceito_expressamente")
        self.assertFalse(item["si_compatibility"]["conflict"])

    def test_prazo_usa_mais_recente_nao_o_mais_antigo(self):
        # Regressão C2: uma retificação que prorroga o prazo não pode deixá-lo "expirado".
        contest = self._contest("d1", [("registration_end", "2020-01-01")])
        self._add_document(contest, "d1-ret", [("registration_end", "2030-01-01")])
        item = next(i for i in self._items()["items"] if i["contest_id"] == contest)
        self.assertTrue(item["urgency"] is None or item["urgency"]["state"] != "expirado")

    def test_vaga_ambigua_nao_conta_como_confirmada(self):
        # Regressão I8: extração ambígua não é confirmada (nem vira zero).
        contest = self._contest("d2", [("indigenous_vacancies", 7), ("si_compatibility", "aceito_expressamente"),
                                       ("exam_location", "Salvador/BA")],
                                ambiguous=("indigenous_vacancies",),
                                validate=("si_compatibility", "exam_location"))
        item = next(i for i in self._items()["items"] if i["contest_id"] == contest)
        self.assertIsNone(item["indigenous_immediate"])
        self.assertEqual(item["indigenous_immediate_state"], "ambiguo")


class CoexistenceTest(PriorityBase):
    def test_alertas_e_triagem_seguem_funcionais(self):
        from radar import ops
        self._contest("z1", [("indigenous_vacancies", 2), ("si_compatibility", "aceito_expressamente"),
                             ("exam_location", "Salvador/BA"), ("exemption_end", "2020-01-01")],
                      validate=("indigenous_vacancies", "si_compatibility", "exam_location"))
        # Priorização não interfere nos alertas/triagem da Fase 19.
        alerts = ops.generate_alerts(self.db, now=_now())
        self.assertIsInstance(alerts, dict)
        triage = ops.triage(self.db)
        self.assertIn("groups", triage)
        self._items()  # priorização roda depois e continua funcionando
        self.assertIn("groups", ops.triage(self.db))


if __name__ == "__main__":
    unittest.main()
