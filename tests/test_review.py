"""Fila de revisão humana, decisões auditáveis, lotes e importação (Fase 28)."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from radar import review
from radar.document_store import (get_competition_details, migrate_document_schema,
                                  record_analysis, record_version, register_document)

NOW = "2026-10-17T12:00:00+00:00"


class ReviewBase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = str(Path(tmp.name) / "r.sqlite3")
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("INSERT INTO concursos_identidade (id,created_at) "
                         "VALUES ('c','2026-10-01T00:00:00+00:00')")
            conn.execute("INSERT INTO observacoes_concurso (id,contest_id,source_url,"
                         "competition_id,observed_at) VALUES ('o','c',"
                         "'https://anexos-r2.selecao.net.br/uploads/1/','1/2026',"
                         "'2026-10-01T00:00:00+00:00')")
            conn.commit()
        self.doc1 = self._document("https://anexos-r2.selecao.net.br/uploads/1/edital.pdf",
                                   "Edital de abertura", "edital_abertura", "2026-10-01")
        self.version1 = record_version(
            self.db, self.doc1, b"pdf-1",
            dict(fetched_at="2026-10-01T00:00:00+00:00",
                 fetched_url="https://anexos-r2.selecao.net.br/uploads/1/edital.pdf",
                 content_type="application/pdf"))
        texto1 = "10 vagas imediatas. Inscrições até 01/11/2026."
        record_analysis(
            self.db, self.version1,
            [dict(text=texto1, start_offset=0, end_offset=len(texto1),
                  page_number=1, locator="p.1")],
            [dict(contest_id="c", role_id=None, field_name="immediate_vacancies",
                  value_json="10", value_type="integer", extraction_method="regex",
                  evidence=self._evidence(0, texto1, "10 vagas imediatas")),
             dict(contest_id="c", role_id=None, field_name="registration_end",
                  value_json='"2026-11-01"', value_type="string", extraction_method="cronograma",
                  evidence=self._evidence(0, texto1, "Inscrições até 01/11/2026"))])
        self.doc2 = self._document("https://anexos-r2.selecao.net.br/uploads/1/ret.pdf",
                                   "Retificação", "retificacao", "2026-10-10")
        self.version2 = record_version(
            self.db, self.doc2, b"pdf-2",
            dict(fetched_at="2026-10-10T00:00:00+00:00",
                 fetched_url="https://anexos-r2.selecao.net.br/uploads/1/ret.pdf",
                 content_type="application/pdf"))
        texto2 = "12 vagas imediatas."
        record_analysis(
            self.db, self.version2,
            [dict(text=texto2, start_offset=0, end_offset=len(texto2),
                  page_number=2, locator="p.2")],
            [dict(contest_id="c", role_id=None, field_name="immediate_vacancies",
                  value_json="12", value_type="integer", extraction_method="regex",
                  evidence=self._evidence(0, texto2, "12 vagas imediatas"))])
        details = get_competition_details(self.db, "c")
        self.proposals = details["proposals"]
        self.by_value = {}
        for proposal in self.proposals:
            self.by_value.setdefault(proposal["field_name"], []).append(proposal)

    @staticmethod
    def _evidence(block_index, text, quote):
        start = text.index(quote)
        return dict(block_index=block_index, quote=quote,
                    start_offset=start, end_offset=start + len(quote))

    def _document(self, url, title, tipo, published):
        return register_document(self.db, dict(
            observation_id="o", kind="edital", official_url=url, title=title,
            discovery_url="https://anexos-r2.selecao.net.br/uploads/1/",
            discovery_method="manual", discovered_at=f"{published}T00:00:00+00:00",
            published_at=published, tipo_documental=tipo))

    def proposal_id(self, field, value):
        for proposal in self.proposals:
            if proposal["field_name"] == field and proposal["value"] == value:
                return proposal["id"]
        raise AssertionError(f"proposta não encontrada: {field}={value}")


class QueueTest(ReviewBase):
    def test_fila_ordena_de_forma_deterministica(self):
        first = review.review_queue(self.db, limit=10, now=NOW)
        second = review.review_queue(self.db, limit=10, now=NOW)
        self.assertEqual([i["proposal_id"] for i in first["items"]],
                         [i["proposal_id"] for i in second["items"]])
        self.assertEqual(first["total"], 3)

    def test_paginacao_nao_repete_nem_perde_itens(self):
        page1 = review.review_queue(self.db, limit=2, offset=0, now=NOW)
        page2 = review.review_queue(self.db, limit=2, offset=2, now=NOW)
        ids = [i["proposal_id"] for i in page1["items"] + page2["items"]]
        self.assertEqual(len(ids), 3)
        self.assertEqual(len(set(ids)), 3)
        self.assertTrue(page1["has_more"])
        self.assertFalse(page2["has_more"])

    def test_conflito_eleva_prioridade_e_aparece_na_evidencia(self):
        queue = review.review_queue(self.db, limit=10, now=NOW)
        item = next(i for i in queue["items"]
                    if i["field_name"] == "immediate_vacancies"
                    and i["value"] == 12)
        factors = {factor["fator"] for factor in item["factors"]}
        self.assertIn("conflito", factors)
        self.assertIn("documento_mais_recente", factors)
        self.assertTrue(item["conflicts"])
        self.assertEqual(item["conflicts"][0]["value"], 10)

    def test_filtros_por_campo_e_conflito(self):
        by_field = review.review_queue(self.db, field_name="registration_end", now=NOW)
        self.assertEqual(by_field["total"], 1)
        conflicts = review.review_queue(self.db, conflict=True, now=NOW)
        self.assertEqual(conflicts["total"], 2)
        self.assertTrue(all(i["field_name"] == "immediate_vacancies"
                            for i in conflicts["items"]))

    def test_filtro_por_ultima_tentativa_de_revisao(self):
        proposal = self.proposal_id("immediate_vacancies", 10)
        review.decide_proposal(self.db, proposal, "adiado", reviewer="Ana",
                               reason="aguardando", now=NOW)
        after = review.review_queue(self.db, state="adiado", reviewed_since=NOW, now=NOW)
        self.assertEqual(after["total"], 1)
        before = review.review_queue(self.db, state="adiado",
                                     reviewed_until="2026-10-16T00:00:00+00:00", now=NOW)
        self.assertEqual(before["total"], 0)

    def test_evidencia_ausente_declara_limitacao(self):
        # Evidência sem trecho literal: o item não pode inventar citação.
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("INSERT INTO evidencias (id,version_id,block_id,quote,page_number,"
                         "locator,start_offset,end_offset,captured_at) VALUES "
                         "('ev-vazia',?,'b','',NULL,NULL,0,1,'2026-10-01T00:00:00+00:00')",
                         (self.version1,))
            conn.execute("INSERT INTO propostas_campo VALUES ('p-vazia','c',NULL,"
                         "'exam_location','\"a_divulgar\"','string','ev-vazia','manual',"
                         "'sem trecho', '2026-10-01T00:00:00+00:00')")
            conn.commit()
        item = review.review_queue(self.db, field_name="exam_location", now=NOW)["items"][0]
        self.assertEqual(item["evidence"]["quote"], "")
        self.assertEqual(item["evidence"]["limitation"], "sem trecho literal registrado")

    def test_container_de_fonte_nao_entra_na_fila(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("INSERT INTO concursos_identidade (id,created_at,estado_identidade) "
                         "VALUES ('ct','2026-10-01T00:00:00+00:00','container_fonte')")
            conn.execute("INSERT INTO observacoes_concurso (id,contest_id,source_url,"
                         "competition_id,observed_at,tipo_identidade) VALUES ('oc','ct',"
                         "'https://www.in.gov.br/leiturajornal?secao=do3','DOU-S3',"
                         "'2026-10-01T00:00:00+00:00','secao_publicacao')")
            conn.execute("INSERT INTO documentos (id,contest_id,observation_id,kind,official_url,"
                         "title,discovered_at,discovery_url,discovery_method,tipo_documental) "
                         "VALUES ('dc','ct','oc','outro','https://www.in.gov.br/web/dou/-/a',"
                         "'Ato','2026-10-01T00:00:00+00:00','https://www.in.gov.br/',"
                         "'automatico','comunicado')")
            conn.commit()
        version = record_version(
            self.db, "dc", b"<p>ato</p>",
            dict(fetched_at="2026-10-01T00:00:00+00:00",
                 fetched_url="https://www.in.gov.br/web/dou/-/a",
                 content_type="text/html"))
        record_analysis(
            self.db, version,
            [dict(text="ato", start_offset=0, end_offset=3, page_number=1, locator="p.1")],
            [dict(contest_id="ct", role_id=None, field_name="registration_end",
                  value_json='"2026-11-01"', value_type="string", extraction_method="manual",
                  evidence=dict(block_index=0, quote="ato", start_offset=0, end_offset=3))])
        with closing(sqlite3.connect(self.db)) as conn:
            container_proposal = conn.execute(
                "SELECT id FROM propostas_campo WHERE contest_id='ct'").fetchone()[0]
        queue = review.review_queue(self.db, state="todos", limit=50, now=NOW)
        self.assertNotIn(container_proposal,
                         [item["proposal_id"] for item in queue["items"]])
        self.assertEqual(len(queue["items"]), 3)


class DecisionTest(ReviewBase):
    def test_aprovacao_registra_estado_anterior_e_canal(self):
        proposal = self.proposal_id("immediate_vacancies", 10)
        result = review.decide_proposal(self.db, proposal, "validado", reviewer="Ana",
                                        reason="conferido no edital", origin="interface",
                                        now=NOW)
        self.assertFalse(result["duplicada"])
        detail = review.proposal_detail(self.db, proposal)
        self.assertEqual(detail["proposal"]["state"], "validado")
        self.assertEqual(detail["reviews"][0]["origin"], "interface")
        self.assertIsNone(detail["reviews"][0]["previous_decision"])
        self.assertTrue(detail["reviews"][0]["evidence_sha256"])

    def test_repetir_a_mesma_decisao_nao_duplica(self):
        proposal = self.proposal_id("immediate_vacancies", 10)
        first = review.decide_proposal(self.db, proposal, "validado", reviewer="Ana",
                                       reason="conferido", now=NOW)
        second = review.decide_proposal(self.db, proposal, "validado", reviewer="Ana",
                                        reason="conferido", now=NOW)
        self.assertFalse(first["duplicada"])
        self.assertTrue(second["duplicada"])
        self.assertEqual(len(review.proposal_detail(self.db, proposal)["reviews"]), 1)

    def test_adiar_nao_conta_como_decidido(self):
        proposal = self.proposal_id("registration_end", "2026-11-01")
        review.decide_proposal(self.db, proposal, "adiado", reviewer="Ana",
                               reason="aguardando retificação", now=NOW)
        self.assertEqual(review.proposal_detail(self.db, proposal)["proposal"]["state"], "adiado")
        self.assertEqual(review.review_queue(self.db, state="pendente", now=NOW)["total"], 2)
        self.assertEqual(review.review_queue(self.db, state="aberto", now=NOW)["total"], 3)

    def test_reabrir_volta_a_pendente_sem_apagar_historico(self):
        proposal = self.proposal_id("immediate_vacancies", 10)
        review.decide_proposal(self.db, proposal, "rejeitado", reviewer="Ana",
                               reason="não confere", now=NOW)
        review.decide_proposal(self.db, proposal, "reaberto", reviewer="Beto",
                               reason="nova versão do documento", now=NOW)
        detail = review.proposal_detail(self.db, proposal)
        self.assertEqual(detail["proposal"]["state"], "pendente")
        self.assertEqual([r["decision"] for r in detail["reviews"]],
                         ["rejeitado", "reaberto"])
        self.assertEqual(detail["reviews"][1]["previous_decision"], "rejeitado")

    def test_correcao_cria_proposta_derivada_com_evidencia_original(self):
        proposal = self.proposal_id("immediate_vacancies", 10)
        result = review.decide_proposal(self.db, proposal, "corrigido", reviewer="Ana",
                                        reason="edital diz 11, não 10", value=11, now=NOW)
        self.assertIsNotNone(result["derived_proposal_id"])
        original = review.proposal_detail(self.db, proposal)
        derived = review.proposal_detail(self.db, result["derived_proposal_id"])
        self.assertEqual(original["proposal"]["state"], "corrigido")
        self.assertEqual(original["proposal"]["value"], 10)
        self.assertEqual(derived["proposal"]["value"], 11)
        self.assertEqual(derived["proposal"]["extraction_method"], "correcao_humana")
        self.assertEqual(derived["evidence"]["version_id"], original["evidence"]["version_id"])
        self.assertEqual(derived["evidence"]["quote"], original["evidence"]["quote"])

    def test_correcao_repetida_nao_cria_outra_proposta(self):
        proposal = self.proposal_id("immediate_vacancies", 10)
        first = review.decide_proposal(self.db, proposal, "corrigido", reviewer="Ana",
                                       reason="edital diz 11", value=11, now=NOW)
        second = review.decide_proposal(self.db, proposal, "corrigido", reviewer="Ana",
                                        reason="edital diz 11", value=11, now=NOW)
        self.assertTrue(second["duplicada"])
        self.assertEqual(second["derived_proposal_id"], first["derived_proposal_id"])
        self.assertEqual(len(review.review_queue(self.db, state="todos", now=NOW)["items"]), 4)

    def test_selecao_exige_validacao_e_e_idempotente(self):
        proposal = self.proposal_id("immediate_vacancies", 10)
        with self.assertRaisesRegex(ValueError, "validada"):
            review.select_current_value(self.db, proposal, "Ana", "cedo demais")
        review.decide_proposal(self.db, proposal, "validado", reviewer="Ana",
                               reason="conferido", now=NOW)
        first = review.select_current_value(self.db, proposal, "Ana", "vigente", now=NOW)
        second = review.select_current_value(self.db, proposal, "Ana", "vigente", now=NOW)
        self.assertFalse(first["duplicada"])
        self.assertTrue(second["duplicada"])
        self.assertEqual(first["selection_id"], second["selection_id"])
        detail = review.proposal_detail(self.db, proposal)
        self.assertEqual(detail["current_value"]["proposal_id"], proposal)

    def test_rejeicao_preserva_documento_e_evidencia(self):
        proposal = self.proposal_id("immediate_vacancies", 12)
        review.decide_proposal(self.db, proposal, "rejeitado", reviewer="Ana",
                               reason="retificação anterior", now=NOW)
        details = get_competition_details(self.db, "c")
        self.assertEqual(len(details["documents"]), 2)
        self.assertTrue(any(p["id"] == proposal for p in details["proposals"]))


class DecisionSemanticsTest(ReviewBase):
    """Regressões da revisão independente (Fase 28)."""

    def test_rejeitar_depois_de_selecionar_nao_e_valor_vigente(self):
        proposal = self.proposal_id("immediate_vacancies", 10)
        review.decide_proposal(self.db, proposal, "validado", reviewer="Ana",
                               reason="conferido", now=NOW)
        review.select_current_value(self.db, proposal, "Ana", "vigente", now=NOW)
        review.decide_proposal(self.db, proposal, "rejeitado", reviewer="Beto",
                               reason="retificação contradiz",
                               now="2026-10-17T13:00:00+00:00")
        self.assertEqual(review.review_queue(self.db, state="selecionado", now=NOW)["total"], 0)
        self.assertEqual(review.proposal_detail(self.db, proposal)["proposal"]["state"],
                         "rejeitado")

    def test_apenas_a_selecao_mais_recente_e_vigente(self):
        first = self.proposal_id("immediate_vacancies", 10)
        second = self.proposal_id("immediate_vacancies", 12)
        for proposal in (first, second):
            review.decide_proposal(self.db, proposal, "validado", reviewer="Ana",
                                   reason="conferido", now=NOW)
        review.select_current_value(self.db, first, "Ana", "primeira",
                                    now="2026-10-17T12:00:00+00:00")
        review.select_current_value(self.db, second, "Ana", "segunda",
                                    now="2026-10-17T13:00:00+00:00")
        selected = review.review_queue(self.db, state="selecionado", now=NOW)
        self.assertEqual([i["proposal_id"] for i in selected["items"]], [second])

    def test_desempate_de_revisao_usa_ordem_de_insercao(self):
        proposal = self.proposal_id("immediate_vacancies", 10)
        review.decide_proposal(self.db, proposal, "validado", reviewer="Ana",
                               reason="conferido", now=NOW)
        review.decide_proposal(self.db, proposal, "rejeitado", reviewer="Beto",
                               reason="contradiz", now=NOW)
        with self.assertRaisesRegex(ValueError, "validada"):
            review.select_current_value(self.db, proposal, "Ana", "não pode", now=NOW)

    def test_conflito_ignora_proposta_rejeitada(self):
        first = self.proposal_id("immediate_vacancies", 10)
        second = self.proposal_id("immediate_vacancies", 12)
        review.decide_proposal(self.db, second, "rejeitado", reviewer="Ana",
                               reason="valor errado", now=NOW)
        queue = review.review_queue(self.db, conflict=True, now=NOW)
        self.assertNotIn(first, [i["proposal_id"] for i in queue["items"]])
        item = next(i for i in review.review_queue(self.db, now=NOW)["items"]
                    if i["proposal_id"] == first)
        self.assertEqual(item["conflicts"], [])
        self.assertNotIn("conflito", {f["fator"] for f in item["factors"]})

    def test_correcao_com_outra_justificativa_reusa_derivada(self):
        proposal = self.proposal_id("immediate_vacancies", 10)
        first = review.decide_proposal(self.db, proposal, "corrigido", reviewer="Ana",
                                       reason="edital diz 11", value=11, now=NOW)
        second = review.decide_proposal(self.db, proposal, "corrigido", reviewer="Ana",
                                        reason="confirmado na página 3", value=11,
                                        now="2026-10-17T13:00:00+00:00")
        self.assertFalse(second["duplicada"])
        self.assertEqual(second["derived_proposal_id"], first["derived_proposal_id"])
        derived = [p for p in review.review_queue(self.db, state="todos", limit=50,
                                                  now=NOW)["items"]
                   if p["value"] == 11]
        self.assertEqual(len(derived), 1)

    def test_lote_recusa_filtro_desconhecido(self):
        with self.assertRaisesRegex(ValueError, "filtro"):
            review.open_batch(self.db, created_by="Ana", size=2,
                              filters={"limit": 5}, now=NOW)


class BatchTest(ReviewBase):
    def test_lote_persiste_e_navega_sem_perder_progresso(self):
        lote = review.open_batch(self.db, created_by="Ana", size=2, origin="cli", now=NOW)
        self.assertEqual(lote["progresso"]["total"], 2)
        self.assertEqual(lote["cursor"], 1)
        self.assertEqual(lote["state"], "aberto")
        self.assertEqual(lote["item_atual"]["position"], 1)

        current = lote["itens"][0]["proposal_id"]
        review.decide_proposal(self.db, current, "validado", reviewer="Ana",
                               reason="conferido", lote_id=lote["lote_id"], now=NOW)
        paused = review.batch_step(self.db, lote["lote_id"], "pausar", now=NOW)
        self.assertEqual(paused["state"], "pausado")
        self.assertEqual(paused["progresso"]["decididos"], 1)

        resumed = review.batch_step(self.db, lote["lote_id"], "retomar", now=NOW)
        self.assertEqual(resumed["state"], "aberto")
        advanced = review.batch_step(self.db, lote["lote_id"], "proximo", now=NOW)
        self.assertEqual(advanced["cursor"], 2)
        back = review.batch_step(self.db, lote["lote_id"], "anterior", now=NOW)
        self.assertEqual(back["cursor"], 1)
        self.assertEqual(back["item_atual"]["proposal_id"], current)

    def test_lote_sem_pendencias_falha_alto(self):
        with self.assertRaisesRegex(ValueError, "nenhuma proposta"):
            review.open_batch(self.db, created_by="Ana", size=5,
                              filters={"field_name": "exam_location"}, now=NOW)

    def test_lote_nao_aprova_em_massa(self):
        lote = review.open_batch(self.db, created_by="Ana", size=3, now=NOW)
        queue = review.review_queue(self.db, state="pendente", now=NOW)
        self.assertEqual(queue["total"], 3)
        self.assertEqual(lote["progresso"]["decididos"], 0)


class ExportImportTest(ReviewBase):
    def test_exportacao_traz_impressao_estavel_da_evidencia(self):
        lote = review.open_batch(self.db, created_by="Ana", size=3, now=NOW)
        export = review.export_batch(self.db, lote["lote_id"], now=NOW)
        self.assertEqual(len(export["itens"]), 3)
        self.assertTrue(all(item["evidence_sha256"] for item in export["itens"]))

    def test_importacao_aplica_decisao_em_evidencia_inalterada(self):
        lote = review.open_batch(self.db, created_by="Ana", size=3, now=NOW)
        export = review.export_batch(self.db, lote["lote_id"], now=NOW)
        export["itens"][0]["decision"] = "validado"
        export["itens"][0]["reason"] = "revisado fora da interface"
        preview = review.import_decisions(self.db, export, reviewer="Ana",
                                          reason="lote importado", dry_run=True, now=NOW)
        self.assertEqual(preview["aplicados"], 1)
        self.assertEqual(review.review_queue(self.db, state="pendente", now=NOW)["total"], 3)
        applied = review.import_decisions(self.db, export, reviewer="Ana",
                                          reason="lote importado", dry_run=False, now=NOW)
        self.assertEqual(applied["aplicados"], 1)
        self.assertEqual(review.review_queue(self.db, state="pendente", now=NOW)["total"], 2)

    def test_importacao_rejeita_evidencia_desatualizada(self):
        lote = review.open_batch(self.db, created_by="Ana", size=3, now=NOW)
        export = review.export_batch(self.db, lote["lote_id"], now=NOW)
        export["itens"][0]["decision"] = "validado"
        export["itens"][0]["evidence_sha256"] = "0" * 64
        result = review.import_decisions(self.db, export, reviewer="Ana",
                                         reason="lote importado", dry_run=False, now=NOW)
        self.assertEqual(result["aplicados"], 0)
        self.assertEqual(result["rejeitados"][0]["motivo"], "evidência desatualizada")

    def test_importacao_rejeita_item_ja_decidido(self):
        lote = review.open_batch(self.db, created_by="Ana", size=3, now=NOW)
        export = review.export_batch(self.db, lote["lote_id"], now=NOW)
        proposal = export["itens"][0]["proposal_id"]
        review.decide_proposal(self.db, proposal, "rejeitado", reviewer="Beto",
                               reason="decidido antes", now=NOW)
        export["itens"][0]["decision"] = "validado"
        result = review.import_decisions(self.db, export, reviewer="Ana",
                                         reason="lote importado", dry_run=False, now=NOW)
        self.assertEqual(result["aplicados"], 0)
        self.assertEqual(result["rejeitados"][0]["motivo"], "já decidido")

    def test_importacao_rejeita_proposta_repetida_no_arquivo(self):
        lote = review.open_batch(self.db, created_by="Ana", size=3, now=NOW)
        export = review.export_batch(self.db, lote["lote_id"], now=NOW)
        duplicated = dict(export["itens"][0])
        duplicated["decision"] = "validado"
        export["itens"] = [duplicated, dict(duplicated)]
        result = review.import_decisions(self.db, export, reviewer="Ana",
                                         reason="lote importado", dry_run=False, now=NOW)
        self.assertEqual(result["aplicados"], 1)
        self.assertIn("proposta repetida no arquivo",
                      [item["motivo"] for item in result["rejeitados"]])
        self.assertEqual(len(review.proposal_detail(
            self.db, duplicated["proposal_id"])["reviews"]), 1)

    def test_importacao_com_erro_desfaz_tudo(self):
        from unittest.mock import patch
        lote = review.open_batch(self.db, created_by="Ana", size=3, now=NOW)
        export = review.export_batch(self.db, lote["lote_id"], now=NOW)
        for item in export["itens"]:
            item["decision"] = "validado"
        original = review._decide_on
        calls = {"count": 0}

        def failing(conn, *args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 2:
                raise RuntimeError("falha simulada")
            return original(conn, *args, **kwargs)

        with patch.object(review, "_decide_on", side_effect=failing):
            result = review.import_decisions(self.db, export, reviewer="Ana",
                                             reason="lote importado", dry_run=False, now=NOW)
        self.assertEqual(result["aplicados"], 0)
        self.assertEqual(result["erro"], "RuntimeError")
        self.assertEqual(review.review_queue(self.db, state="pendente", now=NOW)["total"], 3)

    def test_importacao_aceita_item_adiado(self):
        lote = review.open_batch(self.db, created_by="Ana", size=1, now=NOW)
        export = review.export_batch(self.db, lote["lote_id"], now=NOW)
        proposal = export["itens"][0]["proposal_id"]
        review.decide_proposal(self.db, proposal, "adiado", reviewer="Ana",
                               reason="depois", now=NOW)
        export = review.export_batch(self.db, lote["lote_id"], now=NOW)
        export["itens"][0]["decision"] = "validado"
        result = review.import_decisions(self.db, export, reviewer="Ana",
                                         reason="lote importado", dry_run=False, now=NOW)
        self.assertEqual(result["aplicados"], 1)
        self.assertEqual(result["rejeitados"], [])

    def test_importacao_recusa_arquivo_invalido(self):
        with self.assertRaisesRegex(ValueError, "inválido"):
            review.import_decisions(self.db, {"version": "outra"}, reviewer="Ana",
                                    reason="x", dry_run=True)


class CliTest(ReviewBase):
    def _run(self, argv):
        import contextlib
        import io as _io
        from radar.__main__ import main
        buffer = _io.StringIO()
        with contextlib.redirect_stdout(buffer):
            main(argv)
        return json.loads(buffer.getvalue())

    def test_cli_fila_e_decisao(self):
        payload = self._run(["revisao-fila", "--db", self.db, "--field",
                             "immediate_vacancies", "--limit", "5"])
        self.assertEqual(payload["total"], 2)
        proposal = payload["items"][0]["proposal_id"]
        result = self._run(["revisao-decidir", "--db", self.db, "--proposal-id", proposal,
                            "--decision", "validado", "--reviewer", "Ana",
                            "--reason", "conferido"])
        self.assertFalse(result["duplicada"])
        self.assertEqual(result["decision"], "validado")

    def test_cli_documentos_bloqueados(self):
        from radar import document_ingest
        blocked = register_document(self.db, dict(
            observation_id="o", kind="edital",
            official_url="https://anexos.cdn.selecao.net.br/uploads/1/bloqueado.pdf",
            title="Bloqueado", discovery_url="https://anexos-r2.selecao.net.br/uploads/1/",
            discovery_method="automatico", discovered_at=NOW,
            tipo_documental="edital_abertura"))
        document_ingest.record_blocked_document(
            self.db, blocked, "robots_disallow_anexos_cdn", detected_at=NOW)
        payload = self._run(["documentos-bloqueados", "--db", self.db])
        self.assertEqual(payload["por_estado"].get("bloqueado"), 1)


if __name__ == "__main__":
    unittest.main()
