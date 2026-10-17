"""Auditoria de cobertura e qualidade dos dados (Fase 25)."""

import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from radar import data_quality
from radar.document_store import connect_documents, migrate_document_schema

NOW = "2026-10-17T12:00:00+00:00"


def json_value(raw):
    """Valor já serializado para colunas de texto (datas/strings)."""
    return raw


class AuditBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "q.sqlite3")
        migrate_document_schema(self.db)

    # --- semeadura ---------------------------------------------------------

    def _write(self, sql, params):
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute(sql, params)

    def contest(self, cid):
        self._write("INSERT INTO concursos_identidade (id,created_at) VALUES (?,?)", (cid, NOW))
        return cid

    def document(self, contest_id, *, kind="edital", tipo=None, state="parcial",
                 analysis=True, url="https://oficial.test/a.pdf"):
        doc_id, obs_id, version_id = str(uuid4()), str(uuid4()), str(uuid4())
        self._write(
            "INSERT INTO observacoes_concurso (id,contest_id,source_url,competition_id,"
            "observed_at) VALUES (?,?,?,?,?)",
            (obs_id, contest_id, "https://oficial.test/", f"obs-{obs_id[:8]}", NOW))
        self._write(
            "INSERT INTO documentos (id,contest_id,observation_id,kind,official_url,"
            "title,discovered_at,discovery_url,discovery_method,tipo_documental) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (doc_id, contest_id, obs_id, kind, url, "Doc",
             NOW, "https://oficial.test/", "manual", tipo))
        if analysis:
            self._write(
                "INSERT INTO versoes_documento (id,document_id,sha256,fetched_at,fetched_url,"
                "content_type,byte_size,local_path,extraction_state) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (version_id, doc_id, "a" * 64, NOW, "https://oficial.test/a.pdf",
                 "application/pdf", 10, "x", state))
        return doc_id, version_id

    def proposal(self, contest_id, field, value, *, ambiguity=None, version_id=None,
                 decision=None, role_id=None):
        proposal_id = str(uuid4())
        evidence_id = str(uuid4())
        if version_id is None:
            _, version_id = self.document(contest_id)
        block_id = str(uuid4())
        self._write(
            "INSERT INTO blocos_documento (id,version_id,page_number,locator,start_offset,"
            "end_offset,text) VALUES (?,?,?,?,?,?,?)",
            (block_id, version_id, 1, "p1", 0, 6, "trecho"))
        self._write(
            "INSERT INTO evidencias (id,version_id,block_id,quote,page_number,locator,"
            "start_offset,end_offset,captured_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (evidence_id, version_id, block_id, "trecho", 1, "p1", 0, 6, NOW))
        self._write(
            "INSERT INTO propostas_campo (id,contest_id,role_id,field_name,value_json,"
            "value_type,evidence_id,extraction_method,ambiguity_reason,extracted_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (proposal_id, contest_id, role_id, field, value, "integer", evidence_id,
             "regex", ambiguity, NOW))
        if decision:
            self._write(
                "INSERT INTO revisoes_campo (id,proposal_id,decision,reviewed_at,reviewer,"
                "reason) VALUES (?,?,?,?,?,?)",
                (str(uuid4()), proposal_id, decision, NOW, "revisor", "conferido"))
        return proposal_id, version_id


class FunnelTest(AuditBase):
    def test_contagens_do_funil(self):
        self.contest("c1")                       # sem documento
        self.contest("c2")
        self.document("c2", kind="outro")        # só agregador
        self.contest("c3")
        self.document("c3")                      # edital analisado
        result = data_quality.audit(self.db, now=NOW)
        funil = {item["etapa"]: item["quantidade"] for item in result["funil"]}
        self.assertEqual(funil["concursos"], 3)
        self.assertEqual(funil["com_documento"], 2)
        self.assertEqual(funil["com_edital_oficial"], 1)
        self.assertEqual(funil["com_edital_analisado"], 1)
        self.assertEqual(funil["com_propostas"], 0)
        self.assertEqual(funil["com_campo_confirmado"], 0)

    def test_sem_documento_nao_e_edital_ausente(self):
        self.contest("c1")
        result = data_quality.audit(self.db, now=NOW)
        edital = next(d for d in result["dimensoes"] if d["key"] == "edital_oficial")
        self.assertEqual(edital["estados"], {"nao_pesquisado": 1})
        self.assertEqual(edital["denominador"], 0)
        self.assertIsNone(edital["pct_confirmado"])

    def test_agregador_nao_conta_como_edital(self):
        self.contest("c1")
        self.document("c1", kind="outro", tipo="pagina_concurso",
                      url="https://www.pciconcursos.com.br/noticias/x")
        result = data_quality.audit(self.db, now=NOW)
        edital = next(d for d in result["dimensoes"] if d["key"] == "edital_oficial")
        self.assertEqual(edital["estados"], {"nao_localizado": 1})
        self.assertEqual(edital["pct_confirmado"], 0.0)
        causa = result["causas"]["por_concurso"][0]
        self.assertEqual(causa["causa"], "apenas_agregador")

    def test_documento_oficial_sem_edital_nao_e_agregador(self):
        self.contest("c1")
        self.document("c1", kind="outro", tipo="pagina_concurso",
                      url="https://www.quadrix.org.br/informacoes/3056/")
        result = data_quality.audit(self.db, now=NOW)
        causa = result["causas"]["por_concurso"][0]
        self.assertEqual(causa["causa"], "documento_oficial_sem_edital")
        self.assertEqual(causa["acao"], "coletar_documento_oficial")


class DenominatorTest(AuditBase):
    def test_denominador_exclui_nao_pesquisado(self):
        for cid in ("c1", "c2", "c3", "c4"):
            self.contest(cid)
        self.document("c1")
        result = data_quality.audit(self.db, now=NOW)
        vagas = next(d for d in result["dimensoes"] if d["key"] == "vagas_imediatas")
        self.assertEqual(vagas["universo"], 4)
        self.assertEqual(vagas["denominador"], 1)
        # os 3 concursos sem edital não somem: ficam explicitamente fora do denominador
        self.assertEqual(vagas["fora_do_denominador"], 3)
        edital = next(d for d in result["dimensoes"] if d["key"] == "edital_oficial")
        self.assertEqual(edital["universo"], 4)
        self.assertEqual(edital["denominador"], 1)
        self.assertEqual(edital["fora_do_denominador"], 3)

    def test_zero_confirmado_difere_de_ausente(self):
        self.contest("c1")
        self.proposal("c1", "indigenous_vacancies", "0")
        result = data_quality.audit(self.db, now=NOW)
        indigenas = next(d for d in result["dimensoes"] if d["key"] == "vagas_indigenas")
        self.assertEqual(indigenas["estados"], {"proposto": 1})
        self.assertEqual(indigenas["pct_com_dado"], 100.0)
        self.assertEqual(indigenas["pct_confirmado"], 0.0)

    def test_prazo_pagamento_declarado_nao_mapeado(self):
        self.contest("c1")
        result = data_quality.audit(self.db, now=NOW)
        pagamento = next(d for d in result["dimensoes"] if d["key"] == "prazo_pagamento")
        self.assertEqual(pagamento["estados"], {"nao_mapeado": 1})
        self.assertIsNone(pagamento["pct_confirmado"])
        self.assertIn("não existe no modelo",
                      " ".join(result["limitacoes"]))


class StateTest(AuditBase):
    def test_ambiguo_nao_conta_como_confirmado(self):
        self.contest("c1")
        self.proposal("c1", "immediate_vacancies", "10",
                      ambiguity="cargo do documento não reconciliado: X")
        result = data_quality.audit(self.db, now=NOW)
        vagas = next(d for d in result["dimensoes"] if d["key"] == "vagas_imediatas")
        self.assertEqual(vagas["estados"], {"ambiguo": 1})
        self.assertEqual(vagas["pct_com_dado"], 100.0)
        self.assertEqual(vagas["pct_confirmado"], 0.0)

    def test_validado_conta_como_confirmado(self):
        self.contest("c1")
        self.proposal("c1", "immediate_vacancies", "10", decision="validado")
        result = data_quality.audit(self.db, now=NOW)
        vagas = next(d for d in result["dimensoes"] if d["key"] == "vagas_imediatas")
        self.assertEqual(vagas["estados"], {"confirmado": 1})
        self.assertEqual(vagas["pct_confirmado"], 100.0)

    def test_valores_divergentes_viram_conflito(self):
        self.contest("c1")
        _, version = self.document("c1")
        self.proposal("c1", "immediate_vacancies", "10", version_id=version)
        self.proposal("c1", "immediate_vacancies", "12", version_id=version)
        result = data_quality.audit(self.db, now=NOW)
        vagas = next(d for d in result["dimensoes"] if d["key"] == "vagas_imediatas")
        self.assertEqual(vagas["estados"], {"em_conflito": 1})

    def test_falha_de_extracao_e_estado_proprio(self):
        self.contest("c1")
        self.document("c1", state="falhou")
        result = data_quality.audit(self.db, now=NOW)
        vagas = next(d for d in result["dimensoes"] if d["key"] == "vagas_imediatas")
        self.assertEqual(vagas["estados"], {"falha_extracao": 1})
        self.assertEqual(vagas["pct_com_dado"], 0.0)
        causa = result["causas"]["por_concurso"][0]
        self.assertEqual(causa["causa"], "falha_extracao")

    def test_local_prova_nao_confunde_campos_complementares(self):
        self.contest("c1")
        _, version = self.document("c1")
        self.proposal("c1", "exam_municipio", json_value('"Paulo Afonso"'),
                      version_id=version)
        self.proposal("c1", "exam_uf", json_value('"BA"'), version_id=version)
        result = data_quality.audit(self.db, now=NOW)
        local = next(d for d in result["dimensoes"] if d["key"] == "local_prova")
        self.assertEqual(local["estados"], {"proposto": 1})

    def test_prazo_inscricao_inicio_e_fim_nao_conflitam(self):
        self.contest("c1")
        _, version = self.document("c1")
        self.proposal("c1", "registration_start", json_value('"2026-11-01"'),
                      version_id=version)
        self.proposal("c1", "registration_end", json_value('"2026-11-30"'),
                      version_id=version)
        result = data_quality.audit(self.db, now=NOW)
        prazo = next(d for d in result["dimensoes"] if d["key"] == "prazo_inscricao")
        self.assertEqual(prazo["estados"], {"proposto": 1})

    def test_mesmo_campo_com_valores_distintos_e_conflito(self):
        self.contest("c1")
        _, version = self.document("c1")
        self.proposal("c1", "exam_uf", json_value('"BA"'), version_id=version)
        self.proposal("c1", "exam_uf", json_value('"PE"'), version_id=version)
        result = data_quality.audit(self.db, now=NOW)
        local = next(d for d in result["dimensoes"] if d["key"] == "local_prova")
        self.assertEqual(local["estados"], {"em_conflito": 1})

    def test_rejeitado_nao_conta_como_dado(self):
        self.contest("c1")
        self.proposal("c1", "work_location", json_value('"Recife"'), decision="rejeitado")
        result = data_quality.audit(self.db, now=NOW)
        lotacao = next(d for d in result["dimensoes"] if d["key"] == "lotacao")
        self.assertEqual(lotacao["estados"], {"nao_localizado": 1})
        self.assertEqual(lotacao["pct_com_dado"], 0.0)

    def test_um_validado_nao_confirma_o_concurso(self):
        self.contest("c1")
        _, version = self.document("c1")
        self.proposal("c1", "immediate_vacancies", "10", decision="validado",
                      version_id=version)
        self.proposal("c1", "indigenous_vacancies", "1", ambiguity="motivo",
                      version_id=version)
        result = data_quality.audit(self.db, now=NOW)
        causa = result["causas"]["por_concurso"][0]
        self.assertNotEqual(causa["causa"], "confirmado")
        self.assertNotEqual(causa["acao"], "nenhuma")
        self.assertTrue(result["funil"][-1]["quantidade"] == 1)

    def test_retificacao_opcional(self):
        self.contest("c1")
        self.document("c1")
        result = data_quality.audit(self.db, now=NOW)
        retificacao = next(d for d in result["dimensoes"] if d["key"] == "retificacao")
        self.assertFalse(retificacao["required"])
        self.assertEqual(retificacao["estados"], {"nao_localizado": 1})


class CauseTest(AuditBase):
    def test_sem_documento(self):
        self.contest("c1")
        result = data_quality.audit(self.db, now=NOW)
        self.assertEqual(result["causas"]["por_concurso"][0]["causa"], "sem_documento")
        self.assertEqual(result["causas"]["por_concurso"][0]["acao"],
                         "coletar_documento_oficial")

    def test_edital_sem_campos(self):
        self.contest("c1")
        self.document("c1")
        result = data_quality.audit(self.db, now=NOW)
        causa = result["causas"]["por_concurso"][0]
        self.assertEqual(causa["causa"], "edital_sem_campos")
        self.assertEqual(causa["acao"], "investigar_falha")

    def test_extraido_ambiguo(self):
        self.contest("c1")
        self.proposal("c1", "immediate_vacancies", "10", ambiguity="motivo")
        result = data_quality.audit(self.db, now=NOW)
        causa = result["causas"]["por_concurso"][0]
        self.assertEqual(causa["causa"], "extraido_ambiguo")
        self.assertEqual(causa["acao"], "revisar_proposta")

    def test_extraido_sem_ambiguidade(self):
        self.contest("c1")
        self.proposal("c1", "immediate_vacancies", "10")
        result = data_quality.audit(self.db, now=NOW)
        self.assertEqual(result["causas"]["por_concurso"][0]["causa"], "extraido_parcial")

    def test_confirmado_somente_sem_pendencias(self):
        self.contest("c1")
        self.proposal("c1", "immediate_vacancies", "10", decision="validado")
        snapshot = data_quality._Snapshot(self.db)
        facts = snapshot.facts("c1")
        proposals = snapshot.proposals["c1"]
        cause, _ = data_quality.classify_cause(facts, proposals, pendencias=())
        self.assertEqual(cause, "confirmado")
        cause_pending, _ = data_quality.classify_cause(
            facts, proposals, pendencias=["local_prova"])
        self.assertNotEqual(cause_pending, "confirmado")

    def test_edital_nao_processado(self):
        self.contest("c1")
        self.document("c1", analysis=False)
        result = data_quality.audit(self.db, now=NOW)
        self.assertEqual(result["causas"]["por_concurso"][0]["causa"],
                         "edital_sem_processamento")

    def test_distribuicao_soma_o_total(self):
        self.contest("c1")
        self.contest("c2")
        self.document("c2", kind="outro")
        result = data_quality.audit(self.db, now=NOW)
        self.assertEqual(sum(result["causas"]["distribuicao"].values()), 2)


class GapsTest(AuditBase):
    def test_fila_e_deterministica_e_explicavel(self):
        self.contest("c1")
        self.document("c1")
        self.proposal("c1", "immediate_vacancies", "10", ambiguity="motivo")
        self.contest("c2")
        first = data_quality.gaps(self.db, now=NOW)
        second = data_quality.gaps(self.db, now=NOW)
        self.assertEqual([i["contest_id"] for i in first["itens"]],
                         [i["contest_id"] for i in second["itens"]])
        self.assertTrue(first["itens"])
        item = first["itens"][0]
        self.assertEqual(item["contest_id"], "c1")
        self.assertGreater(item["prioridade"], 0)
        self.assertTrue(item["motivos"])
        self.assertIn(item["tipo_tarefa"], ("coleta", "revisao_humana", "tecnica"))

    def test_validado_parcial_continua_na_fila(self):
        self.contest("c1")
        self.proposal("c1", "immediate_vacancies", "10", decision="validado")
        result = data_quality.gaps(self.db, now=NOW)
        self.assertEqual(len(result["itens"]), 1)
        self.assertEqual(result["itens"][0]["contest_id"], "c1")
        self.assertNotEqual(result["itens"][0]["causa"], "confirmado")

    def test_limite_respeitado(self):
        for index in range(5):
            self.contest(f"c{index}")
        self.assertEqual(len(data_quality.gaps(self.db, limit=2, now=NOW)["itens"]), 2)

    def test_sem_edital_recebe_acao_de_coleta(self):
        self.contest("c1")
        item = data_quality.gaps(self.db, now=NOW)["itens"][0]
        self.assertEqual(item["acao"], "coletar_documento_oficial")
        self.assertEqual(item["tipo_tarefa"], "coleta")


class SummaryTest(AuditBase):
    def test_resumo_traz_apenas_dimensoes_obrigatorias(self):
        self.contest("c1")
        result = data_quality.summary(self.db, now=NOW)
        keys = {d["key"] for d in result["dimensoes_obrigatorias"]}
        self.assertIn("edital_oficial", keys)
        self.assertIn("vagas_indigenas", keys)
        self.assertNotIn("retificacao", keys)
        self.assertNotIn("prazo_pagamento", keys)

    def test_schema_ilegivel_falha_alto(self):
        with self.assertRaises(ValueError):
            data_quality.audit(str(Path(self.tmp.name) / "nao_existe.sqlite3"))


if __name__ == "__main__":
    unittest.main()
