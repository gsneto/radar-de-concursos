"""Carteira operacional, calendário de prazos e revalidação (Fase 36)."""

import hashlib
import http.client
import json
import sqlite3
import threading
import unittest
import urllib.error
from contextlib import closing
from unittest import mock

from radar import deadline_calendar, deadline_revalidation, document_store, portfolio
from radar.document_store import SCHEMA_VERSION, migrate_document_schema
from radar.server import create_server
from tests.test_role_identity_f35 import NOW, TODAY, add_document, add_proposal, make_db

PAYLOAD = b"%PDF-1.4 documento oficial de teste"
PAYLOAD_SHA = hashlib.sha256(PAYLOAD).hexdigest()
LABEL = "cargo do documento não reconciliado: CARGO TESTE"
NOON = TODAY + "T12:00:00+00:00"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def document(self, contest_id="c1", **kwargs):
        return add_document(self.db, contest_id, **kwargs)

    def proposal(self, contest_id="c1", *, version_id, field, value, quote,
                 reason=LABEL):
        return add_proposal(self.db, contest_id, version_id=version_id, field=field,
                            value=value, quote=quote, reason=reason)

    def set_version_sha(self, version_id, payload=PAYLOAD):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("UPDATE versoes_documento SET sha256=? WHERE id=?",
                         (hashlib.sha256(payload).hexdigest(), version_id))

    def version_sha(self, version_id):
        with closing(sqlite3.connect(self.db)) as conn:
            return conn.execute("SELECT sha256 FROM versoes_documento WHERE id=?",
                                (version_id,)).fetchone()[0]

    def add_revalidation(self, *, contest_id="c1", grupo="inscricao_fim", escopo=None,
                         valor="2026-12-01", document_id=None, version_id=None,
                         result="fonte_inalterada", checked_at=NOW, sha=None):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(
                """INSERT INTO revalidacoes_prazo
                   (id,contest_id,grupo,escopo,valor,document_id,version_id,checked_at,
                    official_url,http_status,stored_sha256,observed_sha256,result,note,
                    checked_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (f"r-{contest_id}-{grupo}-{checked_at}-{result}", contest_id, grupo,
                 escopo, valor, document_id, version_id, checked_at,
                 "https://conhecimento.fgv.br/site.pdf", 200, sha, sha, result, None,
                 "teste"))

    def counts(self):
        with closing(sqlite3.connect(self.db)) as conn:
            return conn.execute(
                "SELECT (SELECT COUNT(*) FROM revalidacoes_prazo),"
                "(SELECT COUNT(*) FROM revisoes_campo),"
                "(SELECT COUNT(*) FROM valores_atuais),"
                "(SELECT COUNT(*) FROM reconciliacoes_cargo)").fetchone()

    def calendar_item(self, grupo="inscricao_fim", now=None):
        report = deadline_calendar.calendar(self.db, now=now or NOON)
        return [item for item in report["itens"] if item["grupo"] == grupo][0]


class CalendarTest(Base):
    def test_futuro_sem_revalidacao_e_candidato(self):
        _, version = self.document(text="Inscrições até 01/12/2026.")
        self.proposal(version_id=version, field="registration_end",
                      value="2026-12-01", quote="Inscrições até 01/12/2026.")
        item = self.calendar_item()
        self.assertEqual(item["estado_operacional"], "candidato_nao_revalidado")
        self.assertTrue(item["precisa_revalidacao"])
        self.assertEqual(item["valor"], "2026-12-01")
        self.assertEqual(item["dias_restantes"], 44)
        self.assertEqual(item["urgencia"], "futuro")

    def test_futuro_revalidado_nao_vira_confirmado(self):
        document_id, version = self.document(text="Inscrições até 01/12/2026.")
        self.proposal(version_id=version, field="registration_end",
                      value="2026-12-01", quote="Inscrições até 01/12/2026.")
        self.set_version_sha(version)
        self.add_revalidation(document_id=document_id, version_id=version,
                              escopo="label:CARGO TESTE",
                              sha=self.version_sha(version))
        item = self.calendar_item()
        self.assertEqual(item["estado_operacional"], "revalidado_na_fonte")
        self.assertFalse(item["precisa_revalidacao"])
        self.assertIn("não confirmado", item["estado_operacional_label"])
        self.assertEqual(item["revalidacao"]["result"], "fonte_inalterada")

    def test_revalidacao_de_outra_versao_nao_vale(self):
        document_id, version = self.document(text="Inscrições até 01/12/2026.")
        self.proposal(version_id=version, field="registration_end",
                      value="2026-12-01", quote="Inscrições até 01/12/2026.")
        self.add_revalidation(document_id=document_id, version_id=version,
                              escopo="label:CARGO TESTE", sha="f" * 64)
        item = self.calendar_item()
        self.assertEqual(item["estado_operacional"], "candidato_nao_revalidado")

    def test_passado_preservado(self):
        _, version = self.document(text="Inscrições até 01/01/2026.")
        self.proposal(version_id=version, field="registration_end",
                      value="2026-01-01", quote="Inscrições até 01/01/2026.")
        item = self.calendar_item()
        self.assertEqual(item["estado_operacional"], "passado_com_evidencia")
        self.assertEqual(item["valor"], "2026-01-01")
        self.assertEqual(item["urgencia"], "vencido")
        self.assertFalse(item["precisa_revalidacao"])

    def test_retificacao_que_altera(self):
        _, opening = self.document(text="Inscrições até 01/12/2026.")
        self.proposal(version_id=opening, field="registration_end",
                      value="2026-12-01", quote="Inscrições até 01/12/2026.")
        _, retif = self.document(tipo="retificacao", title="1ª Retificação",
                                 published_at="2026-10-10",
                                 text="Inscrições até 15/12/2026.")
        self.proposal(version_id=retif, field="registration_end",
                      value="2026-12-15", quote="Inscrições até 15/12/2026.")
        item = self.calendar_item()
        self.assertEqual(item["estado_operacional"], "alterado_por_retificacao")
        self.assertTrue(item["retificacao"]["altera_o_prazo"])
        self.assertTrue(item["precisa_revisao_humana"])

    def test_retificacao_que_repete_valor_nao_altera(self):
        _, opening = self.document(text="Inscrições até 01/12/2026.")
        self.proposal(version_id=opening, field="registration_end",
                      value="2026-12-01", quote="Inscrições até 01/12/2026.")
        _, retif = self.document(tipo="retificacao", title="1ª Retificação",
                                 published_at="2026-10-10",
                                 text="Inscrições até 01/12/2026.")
        self.proposal(version_id=retif, field="registration_end",
                      value="2026-12-01", quote="Inscrições até 01/12/2026.")
        item = self.calendar_item()
        self.assertNotEqual(item["estado_operacional"], "alterado_por_retificacao")
        self.assertEqual(item["valor"], "2026-12-01")

    def test_conflito_nao_escolhe_valor(self):
        _, version = self.document(text="Inscrições até 01/12/2026. Inscrições até 10/12/2026.")
        self.proposal(version_id=version, field="registration_end",
                      value="2026-12-01", quote="Inscrições até 01/12/2026.")
        self.proposal(version_id=version, field="registration_end",
                      value="2026-12-10", quote="Inscrições até 10/12/2026.")
        item = self.calendar_item()
        self.assertEqual(item["estado_operacional"], "conflito_documental")
        self.assertIsNone(item["valor"])
        self.assertEqual(item["conflito"]["valores"], 2)
        self.assertEqual(len(item["candidatos"]), 2)
        self.assertEqual({candidate["valor"] for candidate in item["candidatos"]},
                         {"2026-12-01", "2026-12-10"})
        self.assertFalse(item["precisa_revalidacao"])
        self.assertTrue(item["precisa_revisao_humana"])

    def test_retificacao_com_terceiro_valor_e_conflito(self):
        _, opening = self.document(text="Inscrições até 01/12/2026.")
        self.proposal(version_id=opening, field="registration_end",
                      value="2026-12-01", quote="Inscrições até 01/12/2026.")
        _, retif = self.document(tipo="retificacao", title="1ª Retificação",
                                 published_at="2026-10-10",
                                 text="Inscrições até 15/12/2026.")
        self.proposal(version_id=retif, field="registration_end",
                      value="2026-12-15", quote="Inscrições até 15/12/2026.")
        _, cronograma = self.document(tipo="cronograma", title="Cronograma",
                                      published_at="2026-10-12",
                                      text="Inscrições até 20/12/2026.")
        self.proposal(version_id=cronograma, field="registration_end",
                      value="2026-12-20", quote="Inscrições até 20/12/2026.")
        item = self.calendar_item()
        self.assertEqual(item["estado_operacional"], "conflito_documental")
        self.assertIsNone(item["valor"])
        self.assertIsNone(item["valor_candidato"])
        self.assertEqual(len(item["candidatos"]), 3)

    def test_sem_documento_autoritativo(self):
        _, version = self.document(tipo="resultado", text="Resultado publicado.")
        self.proposal(version_id=version, field="registration_end",
                      value="2026-12-01", quote="Resultado publicado.")
        item = self.calendar_item()
        self.assertEqual(item["estado_operacional"], "nao_localizado")
        self.assertIsNone(item["valor"])

    def test_data_ilegivel(self):
        _, version = self.document(text="Inscrições em data a definir.")
        self.proposal(version_id=version, field="registration_end",
                      value="a definir", quote="Inscrições em data a definir.")
        item = self.calendar_item()
        self.assertEqual(item["estado_operacional"], "data_ilegivel")

    def test_urgencia_usa_fuso_de_recife(self):
        _, version = self.document(text="Inscrições até 18/10/2026.")
        self.proposal(version_id=version, field="registration_end",
                      value="2026-10-18", quote="Inscrições até 18/10/2026.")
        # 18/10 23:30 em Recife ainda é dia 18; em UTC já é 19.
        item = self.calendar_item(now="2026-10-19T02:30:00+00:00")
        self.assertEqual(item["dias_restantes"], 0)
        self.assertEqual(item["urgencia"], "hoje")

    def test_alvos_excluem_conflito_e_passado(self):
        _, version = self.document(text="Inscrições até 01/12/2026. Até 10/12/2026.")
        self.proposal(version_id=version, field="registration_end",
                      value="2026-12-01", quote="Inscrições até 01/12/2026.")
        self.proposal(version_id=version, field="registration_end",
                      value="2026-12-10", quote="Até 10/12/2026.")
        _, past = self.document(tipo="edital_abertura", title="Outro edital",
                                published_at="2026-08-01",
                                text="Inscrições até 01/01/2026.")
        self.proposal(contest_id="c2", version_id=past, field="registration_end",
                      value="2026-01-01", quote="Inscrições até 01/01/2026.")
        targets = deadline_calendar.revalidation_targets(self.db, limit=10, now=NOW)
        self.assertEqual(targets["total"], 0)


class RevalidationTest(Base):
    def prepare(self):
        document_id, version = self.document(text="Inscrições até 01/12/2026.")
        self.proposal(version_id=version, field="registration_end",
                      value="2026-12-01", quote="Inscrições até 01/12/2026.")
        self.set_version_sha(version)
        return document_id, version

    def test_simulacao_nao_consulta_nem_grava(self):
        self.prepare()

        def forbidden(url, timeout=20):
            raise AssertionError("simulação não pode consultar a rede")

        result = deadline_revalidation.execute(self.db, limit=5, apply=False,
                                               fetcher=forbidden, now=NOW)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["total"], 1)
        self.assertIsNone(result["itens"][0]["result"])
        self.assertEqual(self.counts()[0], 0)

    def test_apply_grava_fonte_inalterada(self):
        document_id, version = self.prepare()
        result = deadline_revalidation.execute(
            self.db, limit=5, apply=True, now=NOW,
            fetcher=lambda url, timeout=20: (200, PAYLOAD))
        self.assertFalse(result["dry_run"])
        self.assertEqual(result["por_resultado"], {"fonte_inalterada": 1})
        self.assertEqual(self.counts()[0], 1)
        history = deadline_revalidation.history(self.db)
        self.assertEqual(history["total"], 1)
        self.assertEqual(history["itens"][0]["observed_sha256"], PAYLOAD_SHA)
        self.assertEqual(history["itens"][0]["escopo"], "label:CARGO TESTE")

    def test_apply_detecta_fonte_alterada(self):
        self.prepare()
        result = deadline_revalidation.execute(
            self.db, limit=5, apply=True, now=NOW,
            fetcher=lambda url, timeout=20: (200, b"conteudo novo"))
        self.assertEqual(result["por_resultado"], {"fonte_alterada": 1})
        self.assertEqual(self.counts()[0], 1)

    def test_fonte_indisponivel(self):
        self.prepare()

        def fail(url, timeout=20):
            raise urllib.error.URLError("sem rede")

        result = deadline_revalidation.execute(self.db, limit=5, apply=True, now=NOW,
                                               fetcher=fail)
        self.assertEqual(result["por_resultado"], {"fonte_indisponivel": 1})

    def test_sem_permissao_nao_consulta(self):
        self.prepare()
        target = deadline_revalidation.plan(self.db, limit=5, now=NOW)["itens"][0]
        target = dict(target, politica=dict(target["politica"], allowed=False,
                                            reason="política de teste bloqueia"))

        def forbidden(url, timeout=20):
            raise AssertionError("política bloqueada não pode consultar")

        with mock.patch.object(deadline_revalidation, "plan",
                               return_value={"total": 1, "itens": [target],
                                             "limit": 5, "has_more": False}):
            result = deadline_revalidation.execute(self.db, limit=5, apply=True,
                                                   now=NOW, fetcher=forbidden)
        self.assertEqual(result["por_resultado"], {"sem_permissao": 1})

    def test_alvo_especifico_nao_troca_prazo(self):
        _, first = self.document(text="Inscrições até 01/12/2026.")
        self.proposal(version_id=first, field="registration_end",
                      value="2026-12-01", quote="Inscrições até 01/12/2026.")
        self.set_version_sha(first)
        _, second = self.document(tipo="edital_abertura", title="Outro edital",
                                  published_at="2026-08-01",
                                  text="Inscrições até 10/12/2026.")
        self.proposal(contest_id="c2", version_id=second, field="registration_end",
                      value="2026-12-10", quote="Inscrições até 10/12/2026.")
        self.set_version_sha(second)
        result = deadline_revalidation.execute(
            self.db, limit=1, apply=True, now=NOW,
            fetcher=lambda url, timeout=20: (200, PAYLOAD),
            only={"contest_id": "c1", "grupo": "inscricao_fim"})
        self.assertEqual(result["total"], 1)
        history = deadline_revalidation.history(self.db)
        self.assertEqual(history["total"], 1)
        self.assertEqual(history["itens"][0]["contest_id"], "c1")

    def test_alvo_inexistente_e_recusado(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, "alvos de revalidação"):
            deadline_revalidation.execute(
                self.db, limit=1, apply=True, now=NOW,
                only={"contest_id": "c2", "grupo": "inscricao_fim"},
                fetcher=lambda url, timeout=20: (200, PAYLOAD))

    def test_historico_nao_apaga(self):
        document_id, version = self.prepare()
        self.add_revalidation(document_id=document_id, version_id=version,
                              escopo="label:CARGO TESTE", checked_at=NOW,
                              sha=self.version_sha(version))
        self.add_revalidation(document_id=document_id, version_id=version,
                              escopo="label:CARGO TESTE",
                              checked_at="2026-10-17T13:00:00+00:00",
                              result="fonte_alterada", sha="e" * 64)
        history = deadline_revalidation.history(self.db)
        self.assertEqual(history["total"], 2)
        self.assertEqual({item["result"] for item in history["itens"]},
                         {"fonte_inalterada", "fonte_alterada"})


class PortfolioTest(Base):
    def opportunity(self, contest_id="c1", *, reason=LABEL, fields=None,
                    document_kwargs=None):
        document_kwargs = document_kwargs or {}
        _, version = self.document(contest_id, text="Texto do edital.",
                                   **document_kwargs)
        for field, value, quote in (fields or []):
            self.proposal(contest_id, version_id=version, field=field, value=value,
                          quote=quote, reason=reason)
        return version

    def find(self, **filters):
        report = portfolio.portfolio(self.db, limit=200, now=NOON, **filters)
        return report

    def test_identidade_pendente(self):
        self.opportunity(fields=[("education", "Superior", "Texto do edital.")])
        item = self.find()["itens"][0]
        self.assertEqual(item["prontidao"]["estado"], "identidade_cargo_pendente")
        self.assertIn("cargo não reconciliado", item["lacunas"])
        self.assertEqual(item["proxima_acao"], "confirmar a identidade do cargo")

    def test_conflito_documental_pendente(self):
        _, version = self.document(text="Curso de Direito. Curso de Medicina.")
        self.proposal(version_id=version, field="education",
                      value="Curso de Direito", quote="Curso de Direito.")
        self.proposal(version_id=version, field="education",
                      value="Curso de Medicina", quote="Curso de Medicina.")
        item = self.find()["itens"][0]
        self.assertEqual(item["prontidao"]["estado"], "conflito_documental_pendente")
        self.assertEqual(item["proxima_acao"], "resolver conflito entre versões antes de usar o valor")

    def test_prazo_pendente_antes_de_campos(self):
        _, version = self.document(text="Inscrições até 01/12/2026.")
        self.proposal(version_id=version, field="registration_end",
                      value="2026-12-01", quote="Inscrições até 01/12/2026.")
        item = self.find()["itens"][0]
        self.assertEqual(item["prontidao"]["estado"], "prazo_precisa_revalidacao")
        self.assertEqual(item["proxima_acao"], "confirmar prazo na fonte oficial")

    def test_historica_quando_todos_os_prazos_passaram(self):
        _, version = self.document(text="Inscrições até 01/01/2026.")
        self.proposal(version_id=version, field="registration_end",
                      value="2026-01-01", quote="Inscrições até 01/01/2026.")
        item = self.find()["itens"][0]
        self.assertEqual(item["prontidao"]["estado"], "oportunidade_historica")
        self.assertEqual(item["proxima_acao"], "manter como histórica; acompanhar nova publicação")

    def test_si_aceito_expressamente(self):
        self.opportunity(fields=[("si_compatibility", "aceito_expressamente",
                                  "Texto do edital.")])
        item = self.find()["itens"][0]
        self.assertEqual(item["si"]["estado"], "explicito")
        self.assertIn("expressamente aceito", item["si"]["estado_label"])

    def test_si_ambiguo_exige_interpretacao(self):
        self.opportunity(fields=[("si_compatibility", "ambiguo", "Texto do edital.")])
        item = self.find()["itens"][0]
        self.assertEqual(item["si"]["estado"], "area_correlata_interpretacao")
        self.assertIn("SI:", " ".join(item["lacunas"]))

    def test_si_nao_herda_estado_de_outro_cargo(self):
        _, version = self.document(text="Requisito de TI. Requisito de Química.")
        self.proposal(version_id=version, field="si_compatibility",
                      value="aceito_expressamente", quote="Requisito de TI.",
                      reason="cargo do documento não reconciliado: "
                             "404 ANALISTA DE INFORMATICA — edital cita o curso")
        self.proposal(version_id=version, field="si_compatibility",
                      value="incompativel_com_requisito_explicito",
                      quote="Requisito de Química.",
                      reason="cargo do documento não reconciliado: "
                             "400 AGENTE FISCAL — requisito de área alheia")
        items = portfolio.portfolio(self.db, limit=50, now=NOON)["itens"]
        by_role = {item["role_name"]: item for item in items}
        self.assertEqual(by_role["404 ANALISTA DE INFORMATICA"]["si"]["estado"],
                         "explicito")
        self.assertEqual(by_role["400 AGENTE FISCAL"]["si"]["estado"],
                         "outras_formacoes")
        self.assertFalse(by_role["400 AGENTE FISCAL"]["si"]["agregado"])

    def test_si_do_concurso_e_agregado_qualificado(self):
        _, version = self.document(text="Requisito de TI.")
        self.proposal(version_id=version, field="si_compatibility",
                      value="aceito_expressamente", quote="Requisito de TI.",
                      reason=None)
        item = portfolio.portfolio(self.db, limit=50, now=NOON)["itens"][0]
        self.assertTrue(item["si"]["agregado"])
        self.assertIn("Melhor estado entre cargos", item["si"]["estado_label"])

    def test_dossie_nao_herda_si_de_outro_cargo(self):
        _, version = self.document(text="Requisito de TI. Requisito de Química.")
        self.proposal(version_id=version, field="si_compatibility",
                      value="aceito_expressamente", quote="Requisito de TI.",
                      reason="cargo do documento não reconciliado: "
                             "404 ANALISTA DE INFORMATICA — edital cita o curso")
        self.proposal(version_id=version, field="si_compatibility",
                      value="incompativel_com_requisito_explicito",
                      quote="Requisito de Química.",
                      reason="cargo do documento não reconciliado: "
                             "400 AGENTE FISCAL — requisito de área alheia")
        dossier = portfolio.portfolio_dossier(
            self.db, "c1", scope="label:400 AGENTE FISCAL", now=NOON)
        self.assertEqual(dossier["formacao"]["si_por_cargo"]["estado"],
                         "outras_formacoes")
        self.assertFalse(dossier["formacao"]["si_por_cargo"]["agregado"])

    def test_indigena_e_do_concurso_e_nao_do_cargo(self):
        self.opportunity(fields=[
            ("indigenous_reserve_vacancies", 5, "Texto do edital."),
        ])
        item = self.find()["itens"][0]
        self.assertEqual(item["indigenas"]["ambito"], "concurso")
        self.assertIn("nota_cargo", item["indigenas"])
        self.assertFalse([motivo for motivo in item["prioridade"]["motivos"]
                          if "reserva" in motivo.lower()])

    def test_redirect_para_outro_host_e_recusado(self):
        import urllib.request
        request = urllib.request.Request("https://conhecimento.fgv.br/edital.pdf")
        with self.assertRaises(urllib.error.HTTPError):
            deadline_revalidation._SameHostRedirect().redirect_request(
                request, None, 302, "Found", {},
                "https://outro.example/edital.pdf")
        with self.assertRaises(urllib.error.HTTPError):
            deadline_revalidation._SameHostRedirect().redirect_request(
                request, None, 302, "Found", {},
                "http://conhecimento.fgv.br/edital.pdf")

    def test_reserva_indigena_sem_derivar_agregado(self):
        self.opportunity(fields=[
            ("vagas_total_publicado", 100, "Texto do edital."),
            ("indigenous_reserve_vacancies", 5, "Texto do edital."),
        ])
        item = self.find()["itens"][0]
        self.assertEqual(item["indigenas"]["estado"], "apenas_reserva")
        self.assertFalse(item["indigenas"]["derivado_de_agregado"])
        self.assertEqual(item["indigenas"]["total_agregado"][0]["value"], 100)
        self.assertFalse([entry for entry in item["indigenas"]["imediata"]
                          if entry["value"]])

    def test_local_de_prova_nao_usa_lotacao(self):
        self.opportunity(fields=[
            ("exam_location", "Salvador/BA", "Texto do edital."),
            ("work_location", "Feira de Santana/BA", "Texto do edital."),
        ])
        dossier = portfolio.portfolio_dossier(
            self.db, "c1", scope="label:CARGO TESTE", now=NOON)
        prova = dossier["localizacao"]["prova"]
        lotacao = dossier["localizacao"]["lotacao"]
        self.assertIn("Salvador", prova["text"])
        self.assertNotEqual(prova["text"], lotacao["text"])

    def test_dossie_traz_evidencias_de_duas_versoes(self):
        _, opening = self.document(text="Requisito: Superior.")
        self.proposal(version_id=opening, field="education",
                      value="Superior", quote="Requisito: Superior.")
        _, retif = self.document(tipo="retificacao", title="1ª Retificação",
                                 published_at="2026-10-10",
                                 text="Requisito: Superior em Tecnologia.")
        self.proposal(version_id=retif, field="education",
                      value="Superior em Tecnologia",
                      quote="Requisito: Superior em Tecnologia.")
        dossier = portfolio.portfolio_dossier(
            self.db, "c1", scope="label:CARGO TESTE", now=NOON)
        requisito = dossier["formacao"]["requisito"]
        self.assertGreaterEqual(len(requisito["evidencias"]), 2)
        self.assertEqual({entry["value"] for entry in requisito["evidencias"]},
                         {"Superior", "Superior em Tecnologia"})

    def test_dossie_inclui_pagamento_nao_extraido(self):
        self.opportunity(fields=[("education", "Superior", "Texto do edital.")])
        dossier = portfolio.portfolio_dossier(
            self.db, "c1", scope="label:CARGO TESTE", now=NOON)
        pagamento = [entry for entry in dossier["prazos"]
                     if entry["grupo"] == "pagamento"][0]
        self.assertEqual(pagamento["estado_operacional"], "nao_localizado")
        self.assertIn("não extrai", pagamento["estado_operacional_label"])

    def test_paginacao_e_filtros(self):
        for contest in ("c1", "c2"):
            _, version = self.document(contest, text="Inscrições até 01/12/2026.")
            self.proposal(contest, version_id=version, field="registration_end",
                          value="2026-12-01", quote="Inscrições até 01/12/2026.")
        first = portfolio.portfolio(self.db, limit=1, offset=0, now=NOON)
        second = portfolio.portfolio(self.db, limit=1, offset=1, now=NOON)
        self.assertEqual(first["total"], 2)
        self.assertTrue(first["has_more"])
        self.assertEqual(len(first["itens"]), 1)
        self.assertFalse(second["has_more"])
        filtered = portfolio.portfolio(self.db, prontidao="prazo_precisa_revalidacao",
                                       now=NOON)
        self.assertEqual(filtered["total"], 2)
        empty = portfolio.portfolio(self.db, prontidao="informacao_confirmada", now=NOON)
        self.assertEqual(empty["total"], 0)

    def test_filtro_uf_e_conflito(self):
        _, version = self.document(text="Prova em Salvador/BA.")
        self.proposal(version_id=version, field="exam_location",
                      value="Salvador/BA", quote="Prova em Salvador/BA.")
        self.assertEqual(portfolio.portfolio(self.db, uf="BA", now=NOON)["total"], 1)
        self.assertEqual(portfolio.portfolio(self.db, uf="PE", now=NOON)["total"], 0)
        self.assertEqual(portfolio.portfolio(self.db, conflito=False, now=NOON)["total"], 1)

    def test_destaques_limita_dois_por_concurso(self):
        for index in range(3):
            _, version = self.document(
                "c1", tipo="edital_abertura", title=f"Edital {index}",
                published_at=f"2026-0{index + 1}-01",
                text="Inscrições até 01/12/2026.")
            self.proposal("c1", version_id=version, field="registration_end",
                          value="2026-12-01", quote="Inscrições até 01/12/2026.",
                          reason=f"cargo do documento não reconciliado: CARGO {index}")
        highlights = portfolio.portfolio_highlights(self.db, limit=10, now=NOON)
        self.assertLessEqual(len([item for item in highlights["itens"]
                                  if item["contest_id"] == "c1"]), 2)

    def test_destaques_exclui_rotulo_que_nao_e_cargo(self):
        _, version = self.document(text="Local de prova em Salvador/BA.")
        self.proposal(version_id=version, field="exam_location",
                      value="Salvador/BA", quote="Local de prova em Salvador/BA.",
                      reason="cargo do documento não reconciliado: local de prova candidato")
        highlights = portfolio.portfolio_highlights(self.db, limit=10, now=NOON)
        self.assertEqual(highlights["total"], 0)

    def test_ciclo_nao_atribui_sem_evidencia(self):
        _, version = self.document(text="Inscrições até 01/12/2026.")
        self.proposal(version_id=version, field="registration_end",
                      value="2026-12-01", quote="Inscrições até 01/12/2026.")
        first = portfolio.portfolio(self.db, now=NOON)
        _, second_version = self.document(
            "c1", tipo="edital_abertura", title="Novo edital",
            published_at="2026-10-18", text="Outro requisito.")
        self.proposal("c1", version_id=second_version, field="education",
                      value="Superior", quote="Outro requisito.",
                      reason="cargo do documento não reconciliado: OUTRO CARGO")
        second = portfolio.portfolio(self.db, now=NOON)
        self.assertGreater(second["total"], first["total"])
        self.assertEqual(second["referencia"]["hoje_local"], "2026-10-18")
        self.assertEqual(self.counts()[1:], (0, 0, 0))


class ApiTest(Base):
    def setUp(self):
        super().setUp()
        _, version = self.document(text="Inscrições até 01/12/2026.")
        self.proposal(version_id=version, field="registration_end",
                      value="2026-12-01", quote="Inscrições até 01/12/2026.")
        self.set_version_sha(version)
        self.server = create_server(self.db, host="127.0.0.1", port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_address[1]

    def request(self, path, method="GET", body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"} if payload else {}
        conn.request(method, path, body=payload, headers=headers)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, data

    def test_rotas_novas(self):
        for path, key in (("/api/carteira", "por_prontidao"),
                          ("/api/carteira/destaques", "criterio"),
                          ("/api/prazos/calendario", "por_estado"),
                          ("/api/prazos/revalidacao", "itens"),
                          ("/api/prazos/revalidacao/historico", "itens")):
            status, body = self.request(path)
            self.assertEqual(status, 200, path)
            self.assertIn(key, json.loads(body))

    def test_dossie_exige_concurso(self):
        status, _ = self.request("/api/carteira/dossie")
        self.assertEqual(status, 400)
        status, body = self.request("/api/carteira/dossie?contest_id=c1&scope=label:CARGO%20TESTE")
        self.assertEqual(status, 200)
        self.assertIn("identificacao", json.loads(body))

    def test_filtros_invalidos(self):
        for path in ("/api/carteira?prontidao=xyz", "/api/carteira?prazo=xyz",
                     "/api/prazos/calendario?state=xyz",
                     "/api/prazos/calendario?urgency=xyz",
                     "/api/carteira?desconhecido=1"):
            status, _ = self.request(path)
            self.assertEqual(status, 400, path)

    def test_post_simulacao_nao_grava(self):
        status, body = self.request("/api/prazos/revalidacao", "POST", {"limit": 1})
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload["dry_run"])
        self.assertEqual(self.counts()[0], 0)

    def test_post_apply_grava(self):
        with mock.patch.object(deadline_revalidation, "_default_fetcher",
                               return_value=(200, PAYLOAD)):
            status, body = self.request("/api/prazos/revalidacao", "POST",
                                        {"limit": 1, "dry_run": False})
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["dry_run"])
        self.assertEqual(self.counts()[0], 1)

    def test_verbos_nao_permitidos(self):
        status, _ = self.request("/api/prazos/revalidacao", "PUT")
        self.assertEqual(status, 405)


class SchemaTest(Base):
    def test_v21_cria_tabela_e_e_idempotente(self):
        self.assertEqual(SCHEMA_VERSION, 21)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 21)
            self.assertTrue(conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='revalidacoes_prazo'").fetchone())
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 21)

    def test_v20_migra_sem_perder_dados(self):
        _, version = self.document(text="Inscrições até 01/12/2026.")
        self.proposal(version_id=version, field="registration_end",
                      value="2026-12-01", quote="Inscrições até 01/12/2026.")
        with closing(sqlite3.connect(self.db)) as conn, conn:
            before = conn.execute("SELECT COUNT(*) FROM propostas_campo").fetchone()[0]
            conn.execute("DROP TABLE revalidacoes_prazo")
            conn.execute("PRAGMA user_version=20")
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 21)
            self.assertTrue(conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='revalidacoes_prazo'").fetchone())
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM propostas_campo").fetchone()[0],
                             before)

    def test_v20_legivel_mas_v21_tambem(self):
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertIn(20, document_store._READABLE_VERSIONS)
            self.assertIn(21, document_store._READABLE_VERSIONS)


if __name__ == "__main__":
    unittest.main()
