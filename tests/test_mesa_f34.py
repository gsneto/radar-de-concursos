"""Mesa de revisão: oportunidades, dossiê, evidência, sessão, nominais e linha do tempo."""

import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

from radar import (nominal_triage, opportunities, review, timeline)
from radar.document_store import migrate_document_schema
from radar.server import create_server

NOW = "2026-10-17T12:00:00+00:00"
LATER = "2026-10-18T12:00:00+00:00"
_SEQ = [0]


def make_db():
    tmp = tempfile.TemporaryDirectory()
    db = str(Path(tmp.name) / "radar.sqlite3")
    migrate_document_schema(db)
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("INSERT INTO concursos_identidade (id,created_at,estado_identidade) "
                     "VALUES ('c1',?,'certame')", (NOW,))
        conn.execute("INSERT INTO concursos_identidade (id,created_at,estado_identidade) "
                     "VALUES ('c2',?,'certame')", (NOW,))
        conn.execute("INSERT INTO concursos_identidade (id,created_at,estado_identidade) "
                     "VALUES ('cont',?,'container_fonte')", (NOW,))
        conn.execute("INSERT INTO observacoes_concurso "
                     "(id,contest_id,source_url,competition_id,observed_at) "
                     "VALUES ('o1','c1','https://conhecimento.fgv.br/concursos/c1','c1',?)",
                     (NOW,))
        conn.execute("INSERT INTO observacoes_concurso "
                     "(id,contest_id,source_url,competition_id,observed_at) "
                     "VALUES ('o2','c2','https://www.pciconcursos.com.br/noticias/x','c2',?)",
                     (NOW,))
        conn.execute("INSERT INTO cargos_identidade (id,contest_id,name,specialty,created_at,"
                     "code) VALUES ('r1','c1','Analista de TI','Tecnologia',?,'400')", (NOW,))
    return tmp, db


def add_document(db, contest_id, *, tipo="edital_abertura", url=None, title=None,
                 issuer="Fundação Getulio Vargas (FGV Conhecimento)",
                 published_at="2026-09-01", observation_id=None, text="texto"):
    observation_id = observation_id or f"obs-{contest_id}"
    document_id = f"doc-{contest_id}-{tipo}-{len(title or tipo)}-{published_at}"
    version_id = f"ver-{document_id}"
    url = url or (f"https://conhecimento.fgv.br/sites/default/files/concursos/"
                  f"{document_id}.pdf")
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("INSERT OR IGNORE INTO observacoes_concurso "
                     "(id,contest_id,source_url,competition_id,observed_at) "
                     "VALUES (?,?,?,?,?)",
                     (observation_id, contest_id,
                      f"https://conhecimento.fgv.br/concursos/{contest_id}",
                      contest_id, NOW))
        conn.execute("""INSERT INTO documentos
            (id,contest_id,observation_id,kind,official_url,title,discovered_at,
             discovery_url,discovery_method,issuer,published_at,tipo_documental)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (document_id, contest_id, observation_id,
             "edital" if tipo != "retificacao" else "retificacao", url,
             title or f"Documento {tipo}", NOW,
             f"https://conhecimento.fgv.br/concursos/{contest_id}", "automatico",
             issuer, published_at, tipo))
        if text is None:
            return document_id, None
        conn.execute("""INSERT INTO versoes_documento
            (id,document_id,sha256,fetched_at,fetched_url,content_type,byte_size,
             local_path,extraction_state)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (version_id, document_id, "0" * 64, NOW, url, "application/pdf",
             len(text), f"documents/{version_id}", "parcial"))
        block_id = f"blk-{version_id}"
        conn.execute("""INSERT INTO blocos_documento
            (id,version_id,page_number,locator,start_offset,end_offset,text)
            VALUES (?,?,?,?,?,?,?)""",
            (block_id, version_id, 2, "página 2", 0, len(text), text))
    return document_id, version_id


def add_proposal(db, contest_id, *, version_id, field, value, quote,
                 role_id=None, page=2, reason=None, method="regex",
                 extracted_at=NOW, value_type="string"):
    block_id = f"blk-{version_id}"
    with closing(sqlite3.connect(db)) as conn, conn:
        text = conn.execute("SELECT text FROM blocos_documento WHERE id=?",
                            (block_id,)).fetchone()[0]
        start = text.find(quote)
        if start < 0:
            start = 0
        _SEQ[0] += 1
        proposal_id = (f"p-{contest_id}-{field}-{version_id}-{len(quote)}-"
                       f"{extracted_at[-6:]}-{method}-{_SEQ[0]}")
        evidence_id = f"e-{proposal_id}"
        conn.execute("""INSERT INTO evidencias
            (id,version_id,block_id,quote,page_number,locator,start_offset,end_offset,
             captured_at) VALUES (?,?,?,?,?,?,?,?,?)""",
            (evidence_id, version_id, block_id, quote, page, "página 2", start,
             start + len(quote), NOW))
        conn.execute("""INSERT INTO propostas_campo
            (id,contest_id,role_id,field_name,value_json,value_type,evidence_id,
             extraction_method,ambiguity_reason,extracted_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (proposal_id, contest_id, role_id, field, json.dumps(value), value_type,
             evidence_id, method, reason, extracted_at))
    return proposal_id


class MesaBase(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)
        self.doc, self.version = add_document(
            self.db, "c1", text="Requisito: bacharelado em Sistemas de Informação. "
                                "2 vagas imediatas para indígenas. "
                                "Inscrições até 20/10/2026.")
        self.indigenous = add_proposal(
            self.db, "c1", version_id=self.version, field="indigenous_vacancies",
            value=2, quote="2 vagas imediatas para indígenas",
            role_id="r1", method="tabela")
        self.education = add_proposal(
            self.db, "c1", version_id=self.version, field="education",
            value="Bacharelado em Sistemas de Informação",
            quote="bacharelado em Sistemas de Informação", role_id="r1")
        self.deadline = add_proposal(
            self.db, "c1", version_id=self.version, field="registration_end",
            value="2026-10-20", quote="Inscrições até 20/10/2026")

    def count_reviews(self):
        with closing(sqlite3.connect(self.db)) as conn:
            return conn.execute("SELECT COUNT(*) FROM revisoes_campo").fetchone()[0]


class GroupingTest(MesaBase):
    def test_agrupa_por_concurso_e_cargo(self):
        report = opportunities.opportunity_list(self.db, limit=50)
        self.assertEqual(report["total"], 2)  # (c1, r1) e (c1, sem cargo)
        roles = {(item["role_id"], item["role_name"]) for item in report["itens"]}
        self.assertIn(("r1", "Analista de TI"), roles)

    def test_agrupa_por_rotulo_quando_nao_ha_identidade(self):
        _, version = add_document(self.db, "c2", tipo="edital_abertura",
                                  text="Cargo 200 Fiscal.")
        add_proposal(self.db, "c2", version_id=version, field="immediate_vacancies",
                     value=3, quote="Cargo 200 Fiscal",
                     reason="cargo do documento não reconciliado: 200 FISCAL — linha 1")
        report = opportunities.opportunity_list(self.db, contest_id="c2", limit=10)
        item = report["itens"][0]
        self.assertEqual(item["role_name"], "200 FISCAL")
        self.assertFalse(item["role_reconciliado"])
        self.assertIsNone(item["role_id"])

    def test_container_nao_aparece(self):
        report = opportunities.opportunity_list(self.db, limit=100)
        self.assertNotIn("cont", {item["contest_id"] for item in report["itens"]})

    def test_ordem_deterministica(self):
        first = opportunities.opportunity_list(self.db, limit=100)
        second = opportunities.opportunity_list(self.db, limit=100)
        self.assertEqual([item["contest_id"] for item in first["itens"]],
                         [item["contest_id"] for item in second["itens"]])
        self.assertEqual([item["role_id"] for item in first["itens"]],
                         [item["role_id"] for item in second["itens"]])

    def test_prioridade_tem_motivos_explicados(self):
        report = opportunities.opportunity_list(self.db, limit=50)
        item = next(item for item in report["itens"] if item["role_id"] == "r1")
        factors = {factor["fator"] for factor in item["motivos"]}
        self.assertIn("vaga_indigena", factors)
        self.assertIn("edital_oficial", factors)
        self.assertTrue(all("motivo" in factor for factor in item["motivos"]))


class FilterTest(MesaBase):
    def test_filtra_por_campo(self):
        report = opportunities.opportunity_list(self.db, field="education", limit=50)
        self.assertEqual(report["total"], 1)
        self.assertEqual(report["itens"][0]["role_id"], "r1")

    def test_filtra_por_pagina(self):
        report = opportunities.opportunity_list(self.db, has_page=True, limit=50)
        self.assertEqual(report["total"], 2)
        report = opportunities.opportunity_list(self.db, has_page=False, limit=50)
        self.assertEqual(report["total"], 0)

    def test_filtra_por_busca(self):
        report = opportunities.opportunity_list(self.db, search="analista", limit=50)
        self.assertEqual(report["total"], 1)

    def test_filtra_por_estado_documental(self):
        report = opportunities.opportunity_list(self.db, document_state="campos_candidatos",
                                                limit=50)
        self.assertGreaterEqual(report["total"], 1)
        report = opportunities.opportunity_list(self.db, document_state="sem_documento",
                                                limit=50)
        self.assertEqual(report["total"], 0)

    def test_campo_desconhecido_e_recusado(self):
        with self.assertRaises(ValueError):
            opportunities.opportunity_list(self.db, field="campo_inventado")

    def test_limite_fora_da_faixa(self):
        with self.assertRaises(ValueError):
            opportunities.opportunity_list(self.db, limit=0)
        with self.assertRaises(ValueError):
            opportunities.opportunity_list(self.db, limit=500)


class FieldStateTest(MesaBase):
    def test_valores_de_cargos_distintos_nao_sao_conflito(self):
        _, version = add_document(self.db, "c2", tipo="edital_abertura",
                                  text="Requisitos variados.")
        add_proposal(self.db, "c2", version_id=version, field="education",
                     value="Ensino médio", quote="Requisitos variados",
                     reason="cargo do documento não reconciliado: 100 AUXILIAR — x")
        add_proposal(self.db, "c2", version_id=version, field="education",
                     value="Superior em Direito", quote="Requisitos variados",
                     reason="cargo do documento não reconciliado: 200 ADVOGADO — x")
        dossier = opportunities.opportunity_dossier(self.db, "c2")
        field = next(item for item in dossier["campos"] if item["campo"] == "education")
        self.assertEqual(field["estado"], "multiplo_por_cargo")

    def test_conflito_entre_cargos_distintos_nao_conta_como_conflito(self):
        add_document(self.db, "c2", tipo="edital_abertura", text="Requisitos variados.")
        _, version = add_document(self.db, "c2", tipo="retificacao",
                                  url="https://conhecimento.fgv.br/sites/default/files/concursos/r9.pdf",
                                  title="1ª Retificação", published_at="2026-10-01",
                                  text="Requisitos variados.")
        add_proposal(self.db, "c2", version_id=version, field="education",
                     value="Ensino médio", quote="Requisitos variados",
                     reason="cargo do documento não reconciliado: 100 AUXILIAR — x")
        add_proposal(self.db, "c2", version_id=version, field="education",
                     value="Superior em Direito", quote="Requisitos variados",
                     reason="cargo do documento não reconciliado: 200 ADVOGADO — x")
        report = opportunities.opportunity_list(self.db, contest_id="c2", limit=50)
        for item in report["itens"]:
            self.assertEqual(item["conflitos"], 0, item["role_name"])
        queue = review.review_queue(self.db, contest_id="c2", state="todos", limit=50)
        self.assertEqual(queue["resumo"]["com_conflito"], 0)

    def test_mesmo_cargo_com_valores_distintos_e_conflito(self):
        _, version = add_document(
            self.db, "c1", tipo="retificacao",
            url="https://conhecimento.fgv.br/sites/default/files/concursos/r.pdf",
            title="1ª Retificação", published_at="2026-10-01",
            text="Requisito: ensino médio.")
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Ensino médio", quote="Requisito: ensino médio", role_id="r1")
        dossier = opportunities.opportunity_dossier(self.db, "c1", role_id="r1")
        field = next(item for item in dossier["campos"] if item["campo"] == "education")
        self.assertEqual(field["estado"], "em_conflito")
        self.assertEqual(len(field["evidencias"]), 2)


class ScopeReconciliationTest(MesaBase):
    def test_rotulo_reconciliado_mescla_escopo_e_revela_conflito(self):
        # Rótulo e identidade do mesmo cargo: sem consultar a reconciliação, viravam dois
        # escopos e o conflito real (2 × 3) ficava invisível.
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO reconciliacoes_cargo "
                         "(id,contest_id,label,role_id,reconciled_at,reviewer,reason) "
                         "VALUES ('rc1','c1','200 FISCAL','r1',?, 'Ana','rótulo conferido')",
                         (NOW,))
        _, version = add_document(
            self.db, "c1", tipo="retificacao",
            url="https://conhecimento.fgv.br/sites/default/files/concursos/rr.pdf",
            title="1ª Retificação", published_at="2026-10-01",
            text="3 vagas imediatas para indígenas")
        add_proposal(self.db, "c1", version_id=version, field="indigenous_vacancies",
                     value=3, quote="3 vagas imediatas para indígenas",
                     reason="cargo do documento não reconciliado: 200 FISCAL — linha 1")
        report = opportunities.opportunity_list(self.db, contest_id="c1", limit=50)
        self.assertNotIn("label:200 FISCAL", {item["scope"] for item in report["itens"]})
        item = next(item for item in report["itens"] if item["scope"] == "r1")
        self.assertEqual(item["campos"]["indigenous_vacancies"]["estado"], "em_conflito")
        self.assertEqual(item["conflitos"], 1)

    def test_filtro_de_conflito_respeita_escopo_de_rotulo(self):
        _, version = add_document(self.db, "c2", tipo="edital_abertura", text="Requisitos.")
        for value in ("Ensino médio", "Superior"):
            add_proposal(self.db, "c2", version_id=version, field="education",
                         value=value, quote="Requisitos",
                         reason="cargo do documento não reconciliado: 200 FISCAL — x")
        only = opportunities.opportunity_list(self.db, contest_id="c2", conflict=True,
                                             limit=50)
        self.assertEqual(only["total"], 1)
        without = opportunities.opportunity_list(self.db, contest_id="c2", conflict=False,
                                                limit=50)
        self.assertEqual(without["total"], 0)

    def test_snapshot_de_escopo_nao_bloqueia_cargo_diferente(self):
        _, version = add_document(self.db, "c2", tipo="edital_abertura", text="Cargos.")
        fiscal = add_proposal(self.db, "c2", version_id=version, field="education",
                              value="Ensino médio", quote="Cargos",
                              reason="cargo do documento não reconciliado: 200 FISCAL — x")
        add_proposal(self.db, "c2", version_id=version, field="education",
                     value="Direito", quote="Cargos",
                     reason="cargo do documento não reconciliado: 300 ADVOGADO — x")
        lote = review.open_batch(self.db, created_by="Ana", size=50, now=NOW)
        self.assertEqual(lote["progresso"]["alterados"], 0)
        _, new_version = add_document(
            self.db, "c2", tipo="retificacao",
            url="https://conhecimento.fgv.br/sites/default/files/concursos/r6.pdf",
            title="2ª Retificação", published_at="2026-10-02", text="Cargos.")
        add_proposal(self.db, "c2", version_id=new_version, field="education",
                     value="Qualquer", quote="Cargos",
                     reason="cargo do documento não reconciliado: 300 ADVOGADO — x")
        after = review.batch_status(self.db, lote["lote_id"])
        alterados = [item for item in after["itens"] if item["alterado"]]
        # O item alterado é a proposta ANTIGA do cargo que ganhou publicação nova.
        self.assertEqual(len(alterados), 1)
        self.assertEqual(alterados[0]["field_name"], "education")
        self.assertNotEqual(alterados[0]["proposal_id"], fiscal)
        # O item do cargo 200 continua decidível: o contexto dele não mudou.
        review.decide_proposal(self.db, fiscal, "validado", reviewer="Ana",
                               reason="conferido", lote_id=lote["lote_id"], now=NOW)
        self.assertEqual(self.count_reviews(), 1)

    def test_lote_anterior_a_v19_exige_reabertura(self):
        lote = review.open_batch(self.db, created_by="Ana", size=5, now=NOW)
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("UPDATE lote_revisao_itens SET snapshot_sha256=NULL, "
                         "scope_snapshot=NULL WHERE lote_id=?", (lote["lote_id"],))
        status = review.batch_status(self.db, lote["lote_id"])
        self.assertTrue(all(item["motivo_alteracao"] == "sem_snapshot"
                            for item in status["itens"]))
        with self.assertRaisesRegex(ValueError, "reabra o lote"):
            review.decide_proposal(self.db, status["itens"][0]["proposal_id"], "validado",
                                   reviewer="Ana", reason="conferido",
                                   lote_id=lote["lote_id"], now=NOW)
        self.assertEqual(self.count_reviews(), 0)

    def test_sessao_coage_conflict_e_aceita_busca(self):
        # Um conflito real no escopo do cargo r1.
        _, version = add_document(
            self.db, "c1", tipo="retificacao",
            url="https://conhecimento.fgv.br/sites/default/files/concursos/r5.pdf",
            title="3ª Retificação", published_at="2026-10-03",
            text="Requisito: ensino médio.")
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Ensino médio", quote="Requisito: ensino médio", role_id="r1")
        lote = review.open_batch(self.db, created_by="Ana", size=5, origin="cli",
                                 filters={"conflict": "1"}, now=NOW)
        self.assertTrue(lote["filters"]["conflict"] is True)
        self.assertTrue(all(item["field_name"] == "education" for item in lote["itens"]))
        # Filtro de busca é aceito (não derruba a sessão).
        busca = review.open_batch(self.db, created_by="Ana", size=5, origin="cli",
                                  filters={"search": "sistemas"}, now=NOW)
        self.assertGreaterEqual(busca["progresso"]["total"], 1)


class DossierTest(MesaBase):
    def test_dossie_traz_documentos_campos_e_lacunas(self):
        dossier = opportunities.opportunity_dossier(self.db, "c1", role_id="r1")
        self.assertEqual(dossier["documental"]["editais"], 1)
        self.assertTrue(dossier["documental"]["documentos"])
        names = {item["campo"] for item in dossier["campos"]}
        self.assertIn("education", names)
        self.assertIn("immediate_vacancies", dossier["campos_ausentes"])
        self.assertEqual(dossier["revisao"]["pendentes"], 2)

    def test_evidencia_do_dossie_tem_pagina_e_trecho(self):
        dossier = opportunities.opportunity_dossier(self.db, "c1", role_id="r1")
        field = next(item for item in dossier["campos"] if item["campo"] == "education")
        evidence = field["evidencias"][0]
        self.assertEqual(evidence["page_number"], 2)
        self.assertIn("Sistemas de Informação", evidence["quote"])
        self.assertEqual(evidence["version_id"], self.version)
        self.assertTrue(evidence["sha256"])

    def test_concurso_inexistente_falha_alto(self):
        with self.assertRaises(ValueError):
            opportunities.opportunity_dossier(self.db, "nao-existe")


class DossierScopeTest(MesaBase):
    def test_dossie_de_concurso_nao_inventa_conflito_entre_cargos(self):
        # Dois cargos reconciliados com requisitos diferentes: é escopo distinto, não conflito.
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO cargos_identidade (id,contest_id,name,specialty,"
                         "created_at,code) VALUES ('r2','c1','Advogado','Jurídica',?,'401')",
                         (NOW,))
        _, version = add_document(
            self.db, "c1", tipo="retificacao",
            url="https://conhecimento.fgv.br/sites/default/files/concursos/r4.pdf",
            title="4ª Retificação", published_at="2026-10-04",
            text="Requisito: bacharelado em Direito.")
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Bacharelado em Direito", quote="bacharelado em Direito",
                     role_id="r2")
        dossier = opportunities.opportunity_dossier(self.db, "c1")
        field = next(item for item in dossier["campos"] if item["campo"] == "education")
        self.assertEqual(field["estado"], "multiplo_por_cargo")
        self.assertEqual(len(field["evidencias"]), 2)

    def test_dossie_por_escopo_de_rotulo_filtra_somente_o_cargo(self):
        _, version = add_document(self.db, "c2", tipo="edital_abertura", text="Cargos.")
        add_proposal(self.db, "c2", version_id=version, field="education",
                     value="Ensino médio", quote="Cargos",
                     reason="cargo do documento não reconciliado: 200 FISCAL")
        add_proposal(self.db, "c2", version_id=version, field="education",
                     value="Direito", quote="Cargos",
                     reason="cargo do documento não reconciliado: 300 ADVOGADO")
        dossier = opportunities.opportunity_dossier(self.db, "c2", scope="label:200 FISCAL")
        field = next(item for item in dossier["campos"] if item["campo"] == "education")
        self.assertEqual(field["estado"], "candidato")
        self.assertEqual(len(field["evidencias"]), 1)

    def test_conflitos_do_dossie_reportam_total(self):
        dossier = opportunities.opportunity_dossier(self.db, "c1")
        self.assertEqual(dossier["conflitos_total"], len(dossier["conflitos"]))


class EvidenceTest(MesaBase):
    def test_comparacao_traz_contexto_origem_e_outras_propostas(self):
        detail = opportunities.proposal_evidence(self.db, self.education)
        self.assertIn("Requisito", detail["context"]["before"] or "")
        self.assertIn("2 vagas", detail["context"]["after"] or "")
        self.assertEqual(detail["origin"], "extração direta (regex)")
        self.assertEqual(detail["proposal"]["field_name"], "education")
        self.assertTrue(detail["evidence_sha256"])

    def test_origem_de_tabela_e_declarada(self):
        detail = opportunities.proposal_evidence(self.db, self.indigenous)
        self.assertIn("tabela", detail["origin"])
        self.assertFalse(detail["structural_confidence"]["aplicavel"])
        self.assertIn("motivo", detail["structural_confidence"])

    def test_historico_de_decisoes_aparece(self):
        review.decide_proposal(self.db, self.education, "validado", reviewer="Ana",
                               reason="conferido no edital", now=NOW)
        detail = opportunities.proposal_evidence(self.db, self.education)
        self.assertEqual(detail["reviews"][0]["decision"], "validado")
        self.assertEqual(detail["reviews"][0]["reviewer"], "Ana")


class SessionTest(MesaBase):
    def test_sessao_guarda_snapshot_e_detecta_nova_proposta(self):
        lote = review.open_batch(self.db, created_by="Ana", size=5, now=NOW)
        self.assertTrue(all(item["snapshot_sha256"] for item in lote["itens"]))
        self.assertEqual(lote["progresso"]["alterados"], 0)

        _, version = add_document(
            self.db, "c1", tipo="retificacao",
            url="https://conhecimento.fgv.br/sites/default/files/concursos/r.pdf",
            title="1ª Retificação", published_at="2026-10-01",
            text="Inscrições até 30/10/2026.")
        add_proposal(self.db, "c1", version_id=version, field="registration_end",
                     value="2026-10-30", quote="Inscrições até 30/10/2026")

        after = review.batch_status(self.db, lote["lote_id"])
        self.assertEqual(after["progresso"]["alterados"], 1)
        changed = [item for item in after["itens"] if item["alterado"]]
        self.assertEqual(changed[0]["motivo_alteracao"], "nova_proposta")

    def test_decisao_bloqueada_quando_contexto_mudou(self):
        lote = review.open_batch(self.db, created_by="Ana", size=5, now=NOW)
        target = next(item for item in lote["itens"]
                      if item["field_name"] == "registration_end")
        _, version = add_document(
            self.db, "c1", tipo="retificacao",
            url="https://conhecimento.fgv.br/sites/default/files/concursos/r2.pdf",
            title="2ª Retificação", published_at="2026-10-02",
            text="Inscrições até 31/10/2026.")
        add_proposal(self.db, "c1", version_id=version, field="registration_end",
                     value="2026-10-31", quote="Inscrições até 31/10/2026")
        with self.assertRaisesRegex(ValueError, "reavalie"):
            review.decide_proposal(self.db, target["proposal_id"], "validado",
                                   reviewer="Ana", reason="conferido",
                                   lote_id=lote["lote_id"], now=LATER)
        self.assertEqual(self.count_reviews(), 0)

    def test_decisao_em_sessao_estavel_funciona_e_e_idempotente(self):
        lote = review.open_batch(self.db, created_by="Ana", size=5, now=NOW)
        target = lote["itens"][0]
        first = review.decide_proposal(self.db, target["proposal_id"], "validado",
                                       reviewer="Ana", reason="conferido",
                                       lote_id=lote["lote_id"],
                                       expected_evidence_sha256=target["evidence_sha256"],
                                       now=NOW)
        self.assertFalse(first["duplicada"])
        second = review.decide_proposal(self.db, target["proposal_id"], "validado",
                                        reviewer="Ana", reason="conferido",
                                        lote_id=lote["lote_id"],
                                        expected_evidence_sha256=target["evidence_sha256"],
                                        now=NOW)
        self.assertTrue(second["duplicada"])
        self.assertEqual(self.count_reviews(), 1)

    def test_proposta_fora_do_lote_e_recusada(self):
        lote = review.open_batch(self.db, created_by="Ana", size=1, now=NOW)
        other = next(pid for pid in (self.education, self.deadline)
                     if pid != lote["itens"][0]["proposal_id"])
        with self.assertRaisesRegex(ValueError, "não pertence ao lote"):
            review.decide_proposal(self.db, other, "validado", reviewer="Ana",
                                   reason="x", lote_id=lote["lote_id"], now=NOW)

    def test_abrir_sessao_nao_decide_nada(self):
        review.open_batch(self.db, created_by="Ana", size=5, now=NOW)
        self.assertEqual(self.count_reviews(), 0)


class NominalTriageTest(MesaBase):
    def test_lista_nominal_e_identificada_sem_conteudo(self):
        add_document(self.db, "c2", tipo="resultado",
                     url="https://conhecimento.fgv.br/sites/default/files/concursos/r.pdf",
                     title="Resultado preliminar de isenção", text=None)
        report = nominal_triage.nominal_triage(self.db)
        self.assertEqual(report["total"], 1)
        item = report["itens"][0]
        self.assertEqual(item["estado"], "nominal_sem_conteudo")
        self.assertIn("lista de pessoas", item["motivo"])
        self.assertTrue(item["politica"]["permitido"])
        self.assertNotIn("quote", item)

    def test_ato_de_regra_nao_entra_na_triagem(self):
        report = nominal_triage.nominal_triage(self.db)
        self.assertEqual(report["total"], 0)

    def test_resumo_conta_por_fonte(self):
        add_document(self.db, "c2", tipo="resultado",
                     url="https://conhecimento.fgv.br/sites/default/files/concursos/r.pdf",
                     title="Resultado preliminar", text=None)
        summary = nominal_triage.nominal_summary(self.db)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["por_fonte"].get("fgv-conhecimento"), 1)


class TimelineTest(MesaBase):
    def test_mostra_novos_e_snapshot_anterior(self):
        report = timeline.timeline(self.db, since=NOW)
        self.assertEqual(report["snapshot_anterior"]["documentos"], 0)
        self.assertEqual(report["novos"]["documentos"], 1)
        self.assertEqual(report["referencia"]["desde"], NOW)

    def test_atribui_documento_ao_ciclo_na_janela(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO ciclos_monitoramento "
                         "(id,started_at,finished_at,state,documents_found,documents_new,"
                         "versions_new,changes_pending) "
                         "VALUES ('cy1','2026-10-17T12:30:00+00:00',"
                         "'2026-10-17T12:40:00+00:00','parcial',1,1,1,0)")
            conn.execute("UPDATE documentos SET discovered_at='2026-10-17T12:35:00+00:00'")
        report = timeline.timeline(self.db, since=NOW)
        self.assertEqual(report["ciclos"][0]["cycle_id"], "cy1")
        self.assertEqual(report["documentos_descobertos"][0]["atribuicao"], "ciclo_agendado")
        self.assertEqual(report["documentos_descobertos"][0]["cycle_id"], "cy1")

    def test_documento_fora_de_ciclo_e_manual(self):
        report = timeline.timeline(self.db, since=NOW)
        self.assertEqual(report["documentos_descobertos"][0]["atribuicao"], "fora_de_ciclo")

    def test_since_invalido_e_recusado(self):
        with self.assertRaises(ValueError):
            timeline.timeline(self.db, since="ontem")


class PrivacyAndTimeTest(MesaBase):
    def test_dossie_e_evidencia_nao_reproduzem_trecho_nominal(self):
        _, version = add_document(
            self.db, "c2", tipo="resultado",
            url="https://conhecimento.fgv.br/sites/default/files/concursos/res.pdf",
            title="Resultado preliminar", text="FULANO DE TAL 1234567890")
        add_proposal(self.db, "c2", version_id=version, field="immediate_vacancies",
                     value=1, quote="FULANO DE TAL 1234567890")
        dossier = opportunities.opportunity_dossier(self.db, "c2")
        field = next(item for item in dossier["campos"]
                     if item["campo"] == "immediate_vacancies")
        evidence = field["evidencias"][0]
        self.assertTrue(evidence["nominal"])
        self.assertIsNone(evidence["quote"])
        self.assertIn("nominal", evidence["limitation"])
        detail = opportunities.proposal_evidence(self.db, evidence["proposal_id"])
        self.assertTrue(detail["nominal"])
        self.assertIsNone(detail["evidence"]["quote"])
        self.assertIsNone(detail["context"]["before"])
        self.assertIsNone(detail["context"]["after"])

    def test_triagem_separa_identificacao_natureza_acesso_e_armazenamento(self):
        add_document(self.db, "c2", tipo="resultado",
                     url="https://conhecimento.fgv.br/sites/default/files/concursos/r3.pdf",
                     title="Resultado preliminar", text=None)
        item = nominal_triage.nominal_triage(self.db)["itens"][0]
        self.assertEqual(item["natureza"], "lista_nominal")
        self.assertEqual(item["identificacao"], "certame_identificado")
        self.assertEqual(item["acesso"], "permitido")
        self.assertEqual(item["armazenamento"], "sem_conteudo")
        self.assertEqual(item["estado"], "nominal_sem_conteudo")

    def test_triagem_de_fonte_desconhecida_nao_diz_nao_autorizada(self):
        add_document(self.db, "c2", tipo="resultado",
                     url="https://exemplo.example.com/resultado.pdf",
                     title="Resultado preliminar", text=None)
        item = nominal_triage.nominal_triage(self.db)["itens"][0]
        self.assertEqual(item["acesso"], "fonte_desconhecida")
        self.assertEqual(item["estado"], "fonte_desconhecida")

    def test_linha_do_tempo_normaliza_fuso(self):
        a = timeline.timeline(self.db, since="2026-10-17T09:00:00-03:00")
        b = timeline.timeline(self.db, since="2026-10-17T12:00:00+00:00")
        self.assertEqual(a["novos"], b["novos"])
        self.assertEqual(a["referencia"]["desde"], b["referencia"]["desde"])


class QueuePrivacyTest(MesaBase):
    def test_fila_nao_reproduz_trecho_nominal(self):
        _, version = add_document(
            self.db, "c2", tipo="resultado",
            url="https://conhecimento.fgv.br/sites/default/files/concursos/res2.pdf",
            title="Resultado preliminar", text="FULANO DE TAL 1234567890")
        pid = add_proposal(self.db, "c2", version_id=version,
                           field="immediate_vacancies", value=1,
                           quote="FULANO DE TAL 1234567890")
        queue = review.review_queue(self.db, contest_id="c2", limit=10)
        item = next(item for item in queue["items"] if item["proposal_id"] == pid)
        self.assertIsNone(item["evidence"]["quote"])
        self.assertTrue(item["evidence"]["nominal"])
        detail = review.proposal_detail(self.db, pid)
        self.assertIsNone(detail["evidence"]["quote"])
        self.assertTrue(detail["evidence"]["nominal"])


class MesaApiTest(MesaBase):
    def setUp(self):
        super().setUp()
        self.server = create_server(self.db, host="127.0.0.1", port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_address[1]

    def get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", path)
        response = conn.getresponse()
        body = response.read()
        conn.close()
        return response.status, body

    def test_rotas_da_mesa_respondem(self):
        for path, key in (("/api/oportunidades", "itens"),
                          ("/api/oportunidades/c1", "campos"),
                          ("/api/revisao/evidencia/" + self.education, "proposal"),
                          ("/api/documentos/nominais", "itens"),
                          ("/api/linha-do-tempo", "novos")):
            status, body = self.get(path)
            self.assertEqual(status, 200, path)
            self.assertIn(key, json.loads(body))

    def test_parametros_invalidos_respondem_400(self):
        for path in ("/api/oportunidades?limit=0",
                     "/api/oportunidades?limit=x",
                     "/api/oportunidades?field=inventado",
                     "/api/oportunidades?foo=1",
                     "/api/documentos/nominais?limit=0",
                     "/api/linha-do-tempo?since=ontem",
                     "/api/oportunidades?document_state=campos_confirmado",
                     "/api/revisao/evidencia/" + self.education + "?foo=1"):
            status, _ = self.get(path)
            self.assertEqual(status, 400, path)

    def test_concurso_inexistente_responde_400(self):
        status, _ = self.get("/api/oportunidades/nao-existe")
        self.assertEqual(status, 400)

    def test_leitura_nao_cria_decisao(self):
        self.get("/api/oportunidades")
        self.get("/api/oportunidades/c1")
        self.get("/api/revisao/evidencia/" + self.education)
        self.assertEqual(self.count_reviews(), 0)


if __name__ == "__main__":
    unittest.main()
