"""Reconciliação de cargos, conflitos, prazos e destino nominal (Fase 35)."""

import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

from radar import (conflict_review, deadline_review, document_review,
                   document_store, nominal_destination, review, role_identity)
from radar.document_store import (SCHEMA_VERSION, migrate_document_schema,
                                  record_analysis, record_version, register_document)
from radar.server import create_server

NOW = "2026-10-17T12:00:00+00:00"
_SEQ = [0]
TODAY = "2026-10-18"


def make_db():
    tmp = tempfile.TemporaryDirectory()
    db = str(Path(tmp.name) / "radar.sqlite3")
    migrate_document_schema(db)
    with closing(sqlite3.connect(db)) as conn, conn:
        for contest_id in ("c1", "c2"):
            conn.execute("INSERT INTO concursos_identidade (id,created_at,estado_identidade) "
                         "VALUES (?,?,'certame')", (contest_id, NOW))
            conn.execute("INSERT INTO observacoes_concurso "
                         "(id,contest_id,source_url,competition_id,observed_at) "
                         "VALUES (?,?,?,?,?)",
                         (f"o-{contest_id}", contest_id,
                          f"https://conhecimento.fgv.br/concursos/{contest_id}",
                          contest_id, NOW))
    return tmp, db


def add_document(db, contest_id, *, tipo="edital_abertura", title=None,
                 published_at="2026-09-01", text=None, url=None):
    document_id = f"doc-{contest_id}-{tipo}-{published_at}-{abs(hash(title or tipo)) % 1000}"
    version_id = f"ver-{document_id}"
    url = url or (f"https://conhecimento.fgv.br/sites/default/files/concursos/"
                  f"{document_id}.pdf")
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("""INSERT INTO documentos
            (id,contest_id,observation_id,kind,official_url,title,discovered_at,
             discovery_url,discovery_method,issuer,published_at,tipo_documental)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (document_id, contest_id, f"o-{contest_id}",
             "edital" if tipo != "retificacao" else "retificacao", url,
             title or f"Documento {tipo}", NOW,
             f"https://conhecimento.fgv.br/concursos/{contest_id}", "automatico",
             "Fundação Getulio Vargas (FGV Conhecimento)", published_at, tipo))
        if text is None:
            return document_id, None
        conn.execute("""INSERT INTO versoes_documento
            (id,document_id,sha256,fetched_at,fetched_url,content_type,byte_size,
             local_path,extraction_state)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (version_id, document_id, "0" * 64, NOW, url, "application/pdf",
             len(text), f"documents/{version_id}", "parcial"))
        conn.execute("""INSERT INTO blocos_documento
            (id,version_id,page_number,locator,start_offset,end_offset,text)
            VALUES (?,?,?,?,?,?,?)""",
            (f"blk-{version_id}", version_id, 3, "página 3", 0, len(text), text))
    return document_id, version_id


def add_proposal(db, contest_id, *, version_id, field, value, quote, role_id=None,
                 reason=None, page=3, method="regex"):
    block_id = f"blk-{version_id}"
    with closing(sqlite3.connect(db)) as conn, conn:
        text = conn.execute("SELECT text FROM blocos_documento WHERE id=?",
                            (block_id,)).fetchone()[0]
        start = text.find(quote)
        if start < 0:
            start = 0
        _SEQ[0] += 1
        proposal_id = f"p-{contest_id}-{field}-{version_id}-{len(quote)}-{_SEQ[0]}"
        evidence_id = f"e-{proposal_id}"
        conn.execute("""INSERT INTO evidencias
            (id,version_id,block_id,quote,page_number,locator,start_offset,end_offset,
             captured_at) VALUES (?,?,?,?,?,?,?,?,?)""",
            (evidence_id, version_id, block_id, quote, page, "página 3", start,
             start + len(quote), NOW))
        conn.execute("""INSERT INTO propostas_campo
            (id,contest_id,role_id,field_name,value_json,value_type,evidence_id,
             extraction_method,ambiguity_reason,extracted_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (proposal_id, contest_id, role_id, field, json.dumps(value),
             "integer" if isinstance(value, int) else "string", evidence_id, method,
             reason, NOW))
    return proposal_id


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def role(self, contest_id, name, *, code=None, specialty=None):
        self._role_seq = getattr(self, "_role_seq", 0) + 1
        role_id = f"role-{contest_id}-{self._role_seq}"
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO cargos_identidade "
                         "(id,contest_id,name,specialty,created_at,code) "
                         "VALUES (?,?,?,?,?,?)",
                         (role_id, contest_id, name, specialty, NOW, code))
        return role_id

    def counts(self):
        with closing(sqlite3.connect(self.db)) as conn:
            return conn.execute(
                "SELECT (SELECT COUNT(*) FROM reconciliacoes_cargo),"
                "(SELECT COUNT(*) FROM propostas_campo),"
                "(SELECT COUNT(*) FROM documentos)").fetchone()


class LabelNatureTest(unittest.TestCase):
    def test_naturezas_por_marcador(self):
        self.assertEqual(role_identity.classify_label("MERENDEIRO ESCOLAR"), "cargo_literal")
        self.assertEqual(role_identity.classify_label("400 Assistente Administrativo"),
                         "cargo_com_codigo")
        self.assertEqual(role_identity.classify_label("400"), "codigo_sem_nome")
        self.assertEqual(role_identity.classify_label("PROFESSOR PII – EDUCAÇÃO FÍSICA"),
                         "abreviacao")
        self.assertEqual(role_identity.classify_label("PROFESSOR IV – MATEMÁTICA"),
                         "abreviacao")
        self.assertEqual(role_identity.classify_label(
            "TÉCNICO DE NÍVEL SUPERIOR – ÁREA DE ATUAÇÃO EM ADMINISTRAÇÃO"), "especialidade")
        self.assertEqual(role_identity.classify_label("local de prova candidato"),
                         "nao_e_cargo")
        self.assertEqual(role_identity.classify_label(
            "conteúdo programático candidato (conteudo_topico)"), "nao_e_cargo")
        self.assertEqual(role_identity.classify_label(
            "escolaridade declarada (Nível Superior - Direito)"), "nao_e_cargo")

    def test_nome_longo_em_maiusculas_nao_e_abreviacao(self):
        # Regressão: "P" + letras maiúsculas classificava qualquer nome como abreviação.
        self.assertEqual(role_identity.classify_label(
            "PROFESSOR ORIENTADOR DE ESTÁGIO EM SAÚDE PARA ATUAÇÃO NO CURSO DE ENFERMAGEM"),
            "cargo_literal")


class InventoryTest(Base):
    def test_rotulo_exato_gera_sugestao_sem_confirmar(self):
        _, version = add_document(self.db, "c1", text="Requisito do cargo.")
        role = self.role("c1", "MERENDEIRO ESCOLAR")
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Fundamental", quote="Requisito do cargo.",
                     reason="cargo do documento não reconciliado: MERENDEIRO ESCOLAR")
        report = role_identity.label_inventory(self.db, limit=100)
        item = report["itens"][0]
        self.assertEqual(item["nature"], "cargo_literal")
        self.assertEqual(item["state"], "exata")
        self.assertEqual(item["suggestions"][0]["role_id"], role)
        self.assertEqual(item["acao_proposta"], "confirmar_correspondencia")
        # Nenhuma decisão foi criada por gerar sugestão.
        self.assertEqual(self.counts()[0], 0)

    def test_nome_igual_em_outro_concurso_nao_e_sugerido(self):
        _, version = add_document(self.db, "c1", text="Requisito do cargo.")
        self.role("c2", "MERENDEIRO ESCOLAR")  # mesmo nome, outro concurso
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Fundamental", quote="Requisito do cargo.",
                     reason="cargo do documento não reconciliado: MERENDEIRO ESCOLAR")
        report = role_identity.label_inventory(self.db, limit=100)
        item = report["itens"][0]
        self.assertEqual(item["suggestions"], [])
        self.assertEqual(item["state"], "evidencia_insuficiente")
        self.assertEqual(item["acao_proposta"], "criar_identidade_a_partir_do_rotulo")

    def test_especialidades_diferentes_nao_se_confundem(self):
        _, version = add_document(self.db, "c1", text="Requisito.")
        role_a = self.role("c1", "TÉCNICO DE NÍVEL SUPERIOR – ÁREA DE ATUAÇÃO EM "
                                 "ENGENHARIA CIVIL")
        role_b = self.role("c1", "TÉCNICO DE NÍVEL SUPERIOR – ÁREA DE ATUAÇÃO EM "
                                 "ENGENHARIA ELÉTRICA")
        add_proposal(self.db, "c1", version_id=version, field="education", value="Engenharia",
                     quote="Requisito.",
                     reason="cargo do documento não reconciliado: TÉCNICO DE NÍVEL SUPERIOR "
                            "– ÁREA DE ATUAÇÃO EM ENGENHARIA CIVIL")
        report = role_identity.label_inventory(self.db, limit=100)
        item = report["itens"][0]
        self.assertEqual(item["suggestions"][0]["role_id"], role_a)
        self.assertNotIn(role_b, [s["role_id"] for s in item["suggestions"][:1]])

    def test_identidade_duplicada_e_sinalizada_sem_escolha(self):
        _, version = add_document(self.db, "c1", text="Requisito.")
        self.role("c1", "CONTADOR", code="406")
        self.role("c1", "Contador", code="406")
        add_proposal(self.db, "c1", version_id=version, field="education", value="Ciências",
                     quote="Requisito.",
                     reason="cargo do documento não reconciliado: 406 CONTADOR")
        report = role_identity.label_inventory(self.db, limit=100)
        item = report["itens"][0]
        self.assertEqual(item["state"], "duplicata_de_identidade")
        self.assertEqual(item["acao_proposta"], "consolidar_identidade_duplicada")
        self.assertEqual(self.counts()[0], 0)

    def test_rotulo_que_nao_e_cargo_nao_recebe_sugestao(self):
        _, version = add_document(self.db, "c1", text="Local.")
        self.role("c1", "ANALISTA")
        add_proposal(self.db, "c1", version_id=version, field="exam_location",
                     value="a_divulgar", quote="Local.",
                     reason="cargo do documento não reconciliado: local de prova candidato")
        report = role_identity.label_inventory(self.db, limit=100)
        item = report["itens"][0]
        self.assertEqual(item["state"], "nao_e_cargo")
        self.assertEqual(item["suggestions"], [])


class DecisionTest(Base):
    def prepare(self):
        _, version = add_document(self.db, "c1", text="Requisito do cargo.")
        role = self.role("c1", "MERENDEIRO ESCOLAR")
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Fundamental", quote="Requisito do cargo.",
                     reason="cargo do documento não reconciliado: MERENDEIRO ESCOLAR")
        return role

    def test_dry_run_nao_grava(self):
        role = self.prepare()
        result = role_identity.decide_reconciliation(
            self.db, contest_id="c1", label="MERENDEIRO ESCOLAR", state="confirmada",
            role_id=role, reviewer="Ana", reason="rótulo confere", dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertEqual(self.counts()[0], 0)

    def test_confirmacao_grava_estado_e_evidencia(self):
        role = self.prepare()
        result = role_identity.decide_reconciliation(
            self.db, contest_id="c1", label="MERENDEIRO ESCOLAR", state="confirmada",
            role_id=role, reviewer="Ana", reason="rótulo confere", dry_run=False,
            evidence={"documento": "edital", "pagina": 3})
        self.assertFalse(result["dry_run"])
        with closing(sqlite3.connect(self.db)) as conn:
            row = conn.execute("SELECT state,role_id,evidence_json,previous_id "
                               "FROM reconciliacoes_cargo WHERE id=?",
                               (result["decision_id"],)).fetchone()
        self.assertEqual(row[0], "confirmada")
        self.assertEqual(row[1], role)
        self.assertIn("pagina", row[2])
        self.assertIsNone(row[3])

    def test_fila_reconhece_estado_confirmada(self):
        # Regressão: depois de confirmar, a fila levantava KeyError em MATCH_LABELS
        # e o endpoint devolvia 400, deixando a UI sem atualizar.
        role = self.prepare()
        role_identity.decide_reconciliation(
            self.db, contest_id="c1", label="MERENDEIRO ESCOLAR", state="confirmada",
            role_id=role, reviewer="Ana", reason="confere", dry_run=False)
        inventory = role_identity.label_inventory(self.db, limit=100)
        self.assertEqual(inventory["por_estado"].get("confirmada"), 1)
        queue = role_identity.reconciliation_queue(self.db, state="confirmada", limit=10)
        self.assertEqual(queue["total"], 1)
        self.assertEqual(queue["itens"][0]["state_label"],
                         "Correspondência confirmada por decisão humana")

    def test_cargo_de_outro_concurso_e_recusado(self):
        self.prepare()
        other = self.role("c2", "MERENDEIRO ESCOLAR")
        with self.assertRaisesRegex(ValueError, "cargo de outro concurso"):
            role_identity.decide_reconciliation(
                self.db, contest_id="c1", label="MERENDEIRO ESCOLAR", state="confirmada",
                role_id=other, reviewer="Ana", reason="x", dry_run=False)

    def test_confirmar_exige_cargo(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, "confirmar exige cargo"):
            role_identity.decide_reconciliation(
                self.db, contest_id="c1", label="MERENDEIRO ESCOLAR", state="confirmada",
                reviewer="Ana", reason="x", dry_run=False)

    def test_rotulo_sem_evidencia_e_recusado(self):
        role = self.role("c1", "MERENDEIRO ESCOLAR")
        with self.assertRaisesRegex(ValueError, "sem evidência"):
            role_identity.decide_reconciliation(
                self.db, contest_id="c1", label="CARGO INVENTADO", state="confirmada",
                role_id=role, reviewer="Ana", reason="x", dry_run=False)

    def test_rejeitar_e_reabrir_preserva_historico(self):
        role = self.prepare()
        first = role_identity.decide_reconciliation(
            self.db, contest_id="c1", label="MERENDEIRO ESCOLAR", state="confirmada",
            role_id=role, reviewer="Ana", reason="confere", dry_run=False)
        second = role_identity.decide_reconciliation(
            self.db, contest_id="c1", label="MERENDEIRO ESCOLAR", state="rejeitada",
            reviewer="Ana", reason="rótulo é de outro cargo", dry_run=False)
        self.assertEqual(second["previous_id"], first["decision_id"])
        history = role_identity.reconciliation_history(
            self.db, contest_id="c1", label="MERENDEIRO ESCOLAR")
        self.assertEqual([item["state"] for item in history["decisoes"]],
                         ["confirmada", "rejeitada"])
        self.assertEqual(history["vigente"]["state"], "rejeitada")
        # Rejeitado deixa de contar como identidade na fila.
        report = role_identity.label_inventory(self.db, limit=100)
        self.assertEqual(report["itens"][0]["state"], "rejeitada")

    def test_mudar_vinculo_exige_reabertura(self):
        role = self.prepare()
        other = self.role("c1", "MERENDEIRO")
        role_identity.decide_reconciliation(
            self.db, contest_id="c1", label="MERENDEIRO ESCOLAR", state="confirmada",
            role_id=role, reviewer="Ana", reason="confere", dry_run=False)
        with self.assertRaisesRegex(ValueError, "reabra"):
            role_identity.decide_reconciliation(
                self.db, contest_id="c1", label="MERENDEIRO ESCOLAR", state="confirmada",
                role_id=other, reviewer="Ana", reason="mudou", dry_run=False)
        role_identity.decide_reconciliation(
            self.db, contest_id="c1", label="MERENDEIRO ESCOLAR", state="reaberta",
            reviewer="Ana", reason="reavaliando", dry_run=False)
        final = role_identity.decide_reconciliation(
            self.db, contest_id="c1", label="MERENDEIRO ESCOLAR", state="confirmada",
            role_id=other, reviewer="Ana", reason="corrigido", dry_run=False)
        self.assertEqual(final["role_id"], other)

    def test_decisao_concorrente_e_recusada(self):
        role = self.prepare()
        first = role_identity.decide_reconciliation(
            self.db, contest_id="c1", label="MERENDEIRO ESCOLAR", state="confirmada",
            role_id=role, reviewer="Ana", reason="confere", dry_run=False)
        with self.assertRaisesRegex(ValueError, "reavalie"):
            role_identity.decide_reconciliation(
                self.db, contest_id="c1", label="MERENDEIRO ESCOLAR", state="rejeitada",
                reviewer="Bia", reason="outra decisão", dry_run=False,
                expected_previous_id="id-antigo")

    def test_criar_identidade_a_partir_do_rotulo(self):
        _, version = add_document(self.db, "c1", text="Requisito.")
        add_proposal(self.db, "c1", version_id=version, field="education", value="Médio",
                     quote="Requisito.",
                     reason="cargo do documento não reconciliado: TÉCNICO ADMINISTRATIVO")
        dry = role_identity.create_role_for_label(
            self.db, contest_id="c1", label="TÉCNICO ADMINISTRATIVO", reviewer="Ana",
            reason="cargo do edital", dry_run=True)
        self.assertTrue(dry["would_create"])
        real = role_identity.create_role_for_label(
            self.db, contest_id="c1", label="TÉCNICO ADMINISTRATIVO", reviewer="Ana",
            reason="cargo do edital", dry_run=False)
        self.assertTrue(real["created"])
        with closing(sqlite3.connect(self.db)) as conn:
            name = conn.execute("SELECT name FROM cargos_identidade WHERE id=?",
                                (real["role_id"],)).fetchone()[0]
        self.assertEqual(name, "TÉCNICO ADMINISTRATIVO")

    def test_criar_identidade_recusa_rotulo_que_nao_e_cargo(self):
        _, version = add_document(self.db, "c1", text="Local.")
        add_proposal(self.db, "c1", version_id=version, field="exam_location",
                     value="a_divulgar", quote="Local.",
                     reason="cargo do documento não reconciliado: local de prova candidato")
        with self.assertRaisesRegex(ValueError, "não é cargo"):
            role_identity.create_role_for_label(
                self.db, contest_id="c1", label="local de prova candidato",
                reviewer="Ana", reason="x", dry_run=False)


class ConflictTest(Base):
    def test_mesmo_documento_com_valores_distintos(self):
        _, version = add_document(self.db, "c1", text="Prova em Aracaju. Prova em Macapá.")
        add_proposal(self.db, "c1", version_id=version, field="exam_location",
                     value="Aracaju/SE", quote="Prova em Aracaju.")
        add_proposal(self.db, "c1", version_id=version, field="exam_location",
                     value="Macapá/AP", quote="Prova em Macapá.")
        report = conflict_review.conflict_groups(self.db)
        item = report["itens"][0]
        self.assertEqual(item["cause"], "mesmo_documento_valores_distintos")
        self.assertEqual(item["prioridade"], 4)

    def test_a_divulgar_nao_e_conflito_de_valor(self):
        _, version = add_document(self.db, "c1", text="Provas em Salvador. Locais a divulgar.")
        add_proposal(self.db, "c1", version_id=version, field="exam_location",
                     value="Salvador/BA", quote="Provas em Salvador.")
        add_proposal(self.db, "c1", version_id=version, field="exam_location",
                     value="a_divulgar", quote="Locais a divulgar.")
        item = conflict_review.conflict_groups(self.db)["itens"][0]
        self.assertEqual(item["cause"], "escopo_diferente")
        self.assertEqual(item["prioridade"], 4)

    def test_variacao_de_extracao_do_mesmo_texto(self):
        _, version = add_document(self.db, "c1", text="Requisito. Outro.")
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Curso superior completo", quote="Requisito.")
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Curso superior completo [...]", quote="Outro.")
        item = conflict_review.conflict_groups(self.db)["itens"][0]
        self.assertEqual(item["cause"], "variacao_de_extracao")

    def test_retificacao_posterior_por_tipo_de_documento(self):
        _, v1 = add_document(self.db, "c1", tipo="edital_abertura",
                             title="Edital de abertura", text="Inscrições até 10/10.")
        add_proposal(self.db, "c1", version_id=v1, field="registration_end",
                     value="2026-10-10", quote="Inscrições até 10/10.")
        _, v2 = add_document(self.db, "c1", tipo="retificacao", title="1ª Retificação",
                             published_at="2026-10-01", text="Inscrições até 20/10.")
        add_proposal(self.db, "c1", version_id=v2, field="registration_end",
                     value="2026-10-20", quote="Inscrições até 20/10.")
        item = conflict_review.conflict_groups(self.db)["itens"][0]
        self.assertEqual(item["cause"], "retificacao_posterior")
        self.assertTrue(item["vigente_candidato"].startswith("p-c1-registration_end-"))
        self.assertIn("retificação", " ".join(item["motivos"]).lower())

    def test_cargos_diferentes_sem_identificacao(self):
        _, version = add_document(self.db, "c1", text="Curso de Direito. Curso de Medicina.")
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Curso de Direito", quote="Curso de Direito.")
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Curso de Medicina", quote="Curso de Medicina.")
        item = conflict_review.conflict_groups(self.db)["itens"][0]
        self.assertEqual(item["cause"], "cargos_diferentes_sem_identificacao")

    def test_conflito_de_campos_diferentes_nao_se_mistura(self):
        _, version = add_document(self.db, "c1", text="A. B.")
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Médio", quote="A.")
        add_proposal(self.db, "c1", version_id=version, field="si_compatibility",
                     value="ambiguo", quote="B.")
        report = conflict_review.conflict_groups(self.db)
        self.assertEqual(report["total"], 0)


class DeadlineTest(Base):
    def test_prazo_futuro_nao_e_confirmado(self):
        _, version = add_document(self.db, "c1", text="Inscrições até 30/11/2026.")
        add_proposal(self.db, "c1", version_id=version, field="registration_end",
                     value="2026-11-30", quote="Inscrições até 30/11/2026.")
        report = deadline_review.deadline_report(self.db, now=TODAY + "T12:00:00+00:00")
        item = report["itens"][0]
        self.assertEqual(item["estado"], "futuro")
        self.assertIn("vigência não comprovada", item["estado_label"])
        self.assertIsNone(item["decisao"])

    def test_prazo_passado_preservado_como_historico(self):
        _, version = add_document(self.db, "c1", text="Inscrições até 10/10/2026.")
        add_proposal(self.db, "c1", version_id=version, field="registration_end",
                     value="2026-10-10", quote="Inscrições até 10/10/2026.")
        report = deadline_review.deadline_report(self.db, now=TODAY + "T12:00:00+00:00")
        item = report["itens"][0]
        self.assertEqual(item["estado"], "expirado")
        self.assertEqual(item["valor"], "2026-10-10")
        self.assertIn("histórico", item["proxima_acao"])

    def test_retificacao_que_altera_o_prazo(self):
        _, v1 = add_document(self.db, "c1", tipo="edital_abertura",
                             published_at="2026-09-01", text="Inscrições até 10/10/2026.")
        add_proposal(self.db, "c1", version_id=v1, field="registration_end",
                     value="2026-10-10", quote="Inscrições até 10/10/2026.")
        _, v2 = add_document(self.db, "c1", tipo="retificacao", title="1ª Retificação",
                             published_at="2026-10-01", text="Inscrições até 20/10/2026.")
        add_proposal(self.db, "c1", version_id=v2, field="registration_end",
                     value="2026-10-20", quote="Inscrições até 20/10/2026.")
        report = deadline_review.deadline_report(self.db, now=TODAY + "T12:00:00+00:00")
        item = report["itens"][0]
        self.assertTrue(item["retificacao"]["altera_o_prazo"])
        self.assertEqual(item["valor"], "2026-10-20")
        self.assertTrue(item["conflito"])

    def test_retificacao_que_nao_menciona_o_prazo(self):
        _, v1 = add_document(self.db, "c1", tipo="edital_abertura",
                             published_at="2026-09-01", text="Inscrições até 10/12/2026.")
        add_proposal(self.db, "c1", version_id=v1, field="registration_end",
                     value="2026-12-10", quote="Inscrições até 10/12/2026.")
        _, v2 = add_document(self.db, "c1", tipo="retificacao", title="1ª Retificação",
                             published_at="2026-10-01",
                             text="Altera o requisito de escolaridade.")
        add_proposal(self.db, "c1", version_id=v2, field="education",
                     value="Superior", quote="Altera o requisito de escolaridade.")
        report = deadline_review.deadline_report(self.db, now=TODAY + "T12:00:00+00:00")
        item = next(item for item in report["itens"] if item["grupo"] == "inscricao_fim")
        self.assertEqual(item["valor"], "2026-12-10")
        self.assertIsNone(item["conflito"])
        self.assertIn("não menciona", item["proxima_acao"])

    def test_filtro_por_concurso_nao_e_sobrescrito(self):
        # Regressão: o laço de documentos reutilizava o nome do parâmetro contest_id e
        # fazia o relatório devolver zero itens.
        for contest in ("c1", "c2"):
            _, version = add_document(self.db, contest, text="Inscrições até 10/12/2026.")
            add_proposal(self.db, contest, version_id=version, field="registration_end",
                         value="2026-12-10", quote="Inscrições até 10/12/2026.")
        report = deadline_review.deadline_report(
            self.db, contest_id="c1", now=TODAY + "T12:00:00+00:00")
        self.assertGreaterEqual(report["total"], 1)
        self.assertTrue(all(item["contest_id"] == "c1" for item in report["itens"]))

    def test_documento_nao_autoritativo_nao_sustenta_prazo(self):
        _, version = add_document(self.db, "c1", tipo="resultado",
                                 text="Inscrições até 10/10/2026.")
        add_proposal(self.db, "c1", version_id=version, field="registration_end",
                     value="2026-10-10", quote="Inscrições até 10/10/2026.")
        report = deadline_review.deadline_report(self.db, now=TODAY + "T12:00:00+00:00")
        self.assertEqual(report["itens"][0]["estado"], "sem_data")


class NominalDestinationTest(Base):
    def test_sem_conteudo_mantem_metadados(self):
        add_document(self.db, "c1", tipo="resultado", title="Resultado preliminar", text=None)
        report = nominal_destination.nominal_destinations(self.db)
        item = report["itens"][0]
        self.assertEqual(item["destino"], "manter_metadados_na_fila")
        self.assertFalse(item["executado"])
        self.assertEqual(report["modo"], "simulacao")

    def test_com_conteudo_sai_da_fila_sem_apagar(self):
        _, version = add_document(self.db, "c1", tipo="resultado",
                                 title="Resultado preliminar",
                                 text="FULANO 123")
        add_proposal(self.db, "c1", version_id=version, field="immediate_vacancies",
                     value=1, quote="FULANO 123")
        report = nominal_destination.nominal_destinations(self.db)
        item = report["itens"][0]
        self.assertEqual(item["destino"], "retirar_da_fila_operacional")
        self.assertIn("nada é apagado", item["consequencia"])
        # Nenhum trecho nominal é devolvido.
        self.assertNotIn("FULANO", json.dumps(report, ensure_ascii=False))

    def test_fonte_desconhecida_exige_revisao_de_politica(self):
        add_document(self.db, "c1", tipo="resultado", title="Resultado preliminar",
                     url="https://exemplo.example.com/r.pdf", text=None)
        item = nominal_destination.nominal_destinations(self.db)["itens"][0]
        self.assertEqual(item["destino"], "revisar_politica_antes_de_agir")


class ApiTest(Base):
    def setUp(self):
        super().setUp()
        _, version = add_document(self.db, "c1", text="Requisito do cargo. Até 10/10/2026.")
        self.role_id = self.role("c1", "MERENDEIRO ESCOLAR")
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Fundamental", quote="Requisito do cargo.",
                     reason="cargo do documento não reconciliado: MERENDEIRO ESCOLAR")
        add_proposal(self.db, "c1", version_id=version, field="registration_end",
                     value="2026-10-10", quote="Até 10/10/2026.")
        self.server = create_server(self.db, host="127.0.0.1", port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_address[1]

    def request(self, path, method="GET", body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"} if payload else {}
        conn.request(method, path, body=payload, headers=headers)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, data

    def test_rotas_novas_respondem(self):
        for path, key in (("/api/reconciliacao", "itens"),
                          ("/api/conflitos-revisao", "por_causa"),
                          ("/api/prazos", "por_estado"),
                          ("/api/documentos/nominais-destino", "por_destino")):
            status, body = self.request(path)
            self.assertEqual(status, 200, path)
            self.assertIn(key, json.loads(body))

    def test_historico_exige_parametros(self):
        status, _ = self.request("/api/reconciliacao/historico")
        self.assertEqual(status, 400)

    def test_post_dry_run_nao_grava(self):
        status, body = self.request("/api/reconciliacao", "POST", {
            "contest_id": "c1", "label": "MERENDEIRO ESCOLAR", "state": "confirmada",
            "role_id": self.role_id, "reviewer": "Ana", "reason": "confere"})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["dry_run"])
        self.assertEqual(self.counts()[0], 0)

    def test_post_dry_run_null_nao_grava(self):
        # Só alse explícito aplica; null/0/"" continuam simulação.
        status, body = self.request("/api/reconciliacao", "POST", {
            "contest_id": "c1", "label": "MERENDEIRO ESCOLAR", "state": "confirmada",
            "role_id": self.role_id, "reviewer": "Ana", "reason": "confere",
            "dry_run": None})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["dry_run"])
        self.assertEqual(self.counts()[0], 0)

    def test_post_com_apply_grava(self):
        status, body = self.request("/api/reconciliacao", "POST", {
            "contest_id": "c1", "label": "MERENDEIRO ESCOLAR", "state": "confirmada",
            "role_id": self.role_id, "reviewer": "Ana", "reason": "confere",
            "dry_run": False})
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["dry_run"])
        self.assertEqual(self.counts()[0], 1)

    def test_fila_reflete_decisao_confirmada(self):
        status, _ = self.request("/api/reconciliacao", "POST", {
            "contest_id": "c1", "label": "MERENDEIRO ESCOLAR", "state": "confirmada",
            "role_id": self.role_id, "reviewer": "Ana", "reason": "confere",
            "dry_run": False})
        self.assertEqual(status, 200)
        status, body = self.request("/api/reconciliacao?state=confirmada")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["itens"][0]["state"], "confirmada")

    def test_parametros_invalidos_respondem_400(self):
        for path in ("/api/reconciliacao?limit=0",
                     "/api/reconciliacao?nature=inventada",
                     "/api/conflitos-revisao?cause=inventada",
                     "/api/prazos?state=inventado",
                     "/api/documentos/nominais-destino?destination=inventado",
                     "/api/reconciliacao?foo=1"):
            status, _ = self.request(path)
            self.assertEqual(status, 400, path)

    def test_leitura_nao_cria_decisao(self):
        self.request("/api/reconciliacao")
        self.request("/api/conflitos-revisao")
        self.request("/api/prazos")
        self.assertEqual(self.counts()[0], 0)


class ReviewInvariantTest(Base):
    """Invariantes da fase: só confirmação vigente vincula; sugestão não é certeza."""

    def confirm(self, role_id, label="MERENDEIRO ESCOLAR", contest_id="c1"):
        return role_identity.decide_reconciliation(
            self.db, contest_id=contest_id, label=label, state="confirmada",
            role_id=role_id, reviewer="Ana", reason="confere", dry_run=False)

    def prepare_role_label(self):
        _, version = add_document(self.db, "c1", text="Requisito do cargo.")
        role = self.role("c1", "MERENDEIRO ESCOLAR")
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Fundamental", quote="Requisito do cargo.",
                     reason="cargo do documento não reconciliado: MERENDEIRO ESCOLAR")
        return role, version

    def test_rejeicao_nao_vincula_no_dossie(self):
        role, _ = self.prepare_role_label()
        self.confirm(role)
        role_identity.decide_reconciliation(
            self.db, contest_id="c1", label="MERENDEIRO ESCOLAR", state="rejeitada",
            reviewer="Ana", reason="não é este cargo", dry_run=False)
        details = document_store.get_competition_details(self.db, "c1")
        proposal = [item for item in details["proposals"]
                    if item["field_name"] == "education"][0]
        self.assertIsNone(proposal["reconciled_role_id"])
        latest = [item for item in details["role_reconciliations"]
                  if item["label"] == "MERENDEIRO ESCOLAR"][-1]
        self.assertEqual(latest["state"], "rejeitada")
        self.assertIsNone(latest["role_id"])
        self.assertFalse([conflict for conflict in details["conflicts"]
                          if conflict["field_name"] == "education"
                          and conflict["scope_type"] == "role"])

    def test_selecao_de_valor_nao_usa_cargo_rejeitado(self):
        role, version = self.prepare_role_label()
        proposal_id = add_proposal(
            self.db, "c1", version_id=version, field="education", value="Fundamental",
            quote="Requisito do cargo.",
            reason="cargo do documento não reconciliado: MERENDEIRO ESCOLAR")
        self.confirm(role)
        role_identity.decide_reconciliation(
            self.db, contest_id="c1", label="MERENDEIRO ESCOLAR", state="rejeitada",
            reviewer="Ana", reason="não é este cargo", dry_run=False)
        review.decide_proposal(self.db, proposal_id, "validado", reviewer="Ana",
                               reason="valor confere", origin="interface")
        selection = review.select_current_value(self.db, proposal_id, "Ana", "vigente")
        self.assertIsNone(selection["role_id"])
        with closing(sqlite3.connect(self.db)) as conn:
            stored = conn.execute("SELECT role_id FROM valores_atuais WHERE id=?",
                                  (selection["selection_id"],)).fetchone()[0]
        self.assertIsNone(stored)

    def test_reconcile_role_label_respeita_estado(self):
        role, _ = self.prepare_role_label()
        self.confirm(role)
        role_identity.decide_reconciliation(
            self.db, contest_id="c1", label="MERENDEIRO ESCOLAR", state="rejeitada",
            reviewer="Ana", reason="não é este cargo", dry_run=False)
        with self.assertRaisesRegex(ValueError, "reabra"):
            document_review.reconcile_role_label(
                self.db, "c1", "MERENDEIRO ESCOLAR", role, "Ana", "confere")
        # Reabrir também não confirma: é preciso decidir de novo.
        role_identity.decide_reconciliation(
            self.db, contest_id="c1", label="MERENDEIRO ESCOLAR", state="reaberta",
            reviewer="Ana", reason="reavaliando", dry_run=False)
        with self.assertRaisesRegex(ValueError, "reabra"):
            document_review.reconcile_role_label(
                self.db, "c1", "MERENDEIRO ESCOLAR", role, "Ana", "confere")

    def test_reconcile_role_label_idempotente_apenas_confirmada(self):
        role, _ = self.prepare_role_label()
        first = self.confirm(role)["decision_id"]
        second = document_review.reconcile_role_label(
            self.db, "c1", "MERENDEIRO ESCOLAR", role, "Ana", "confere")
        self.assertEqual(second, first)

    def test_decisao_avalia_historico_dentro_da_transacao(self):
        role, _ = self.prepare_role_label()
        self.confirm(role)
        original = role_identity._latest_decision
        seen = {}

        def spy(conn, contest_id, label):
            seen["in_transaction"] = conn.in_transaction
            return original(conn, contest_id, label)

        role_identity._latest_decision = spy
        try:
            role_identity.decide_reconciliation(
                self.db, contest_id="c1", label="MERENDEIRO ESCOLAR", state="rejeitada",
                reviewer="Ana", reason="revendo", dry_run=False,
                expected_previous_id="id-antigo")
        except ValueError:
            pass
        finally:
            role_identity._latest_decision = original
        self.assertTrue(seen.get("in_transaction"))

    def test_prazo_por_cargo_nao_mistura_identidades(self):
        _, version = add_document(self.db, "c1", text="Inscrições até 10/12/2026. "
                                                     "Inscrições até 20/12/2026.")
        add_proposal(self.db, "c1", version_id=version, field="registration_end",
                     value="2026-12-10", quote="Inscrições até 10/12/2026.",
                     reason="cargo do documento não reconciliado: CARGO A")
        add_proposal(self.db, "c1", version_id=version, field="registration_end",
                     value="2026-12-20", quote="Inscrições até 20/12/2026.",
                     reason="cargo do documento não reconciliado: CARGO B")
        report = deadline_review.deadline_report(
            self.db, group="inscricao_fim", now=TODAY + "T12:00:00+00:00")
        self.assertEqual(report["total"], 2)
        self.assertEqual({item["escopo_rotulo"] for item in report["itens"]},
                         {"CARGO A", "CARGO B"})
        self.assertEqual({item["valor"] for item in report["itens"]},
                         {"2026-12-10", "2026-12-20"})

    def test_prazo_ignora_proposta_rejeitada(self):
        _, version = add_document(self.db, "c1", text="Inscrições até 10/12/2026.")
        proposal_id = add_proposal(
            self.db, "c1", version_id=version, field="registration_end",
            value="2026-12-10", quote="Inscrições até 10/12/2026.")
        review.decide_proposal(self.db, proposal_id, "rejeitado", reviewer="Ana",
                               reason="data errada", origin="interface")
        report = deadline_review.deadline_report(
            self.db, group="inscricao_fim", now=TODAY + "T12:00:00+00:00")
        self.assertEqual(report["total"], 1)
        self.assertEqual(report["itens"][0]["estado"], "sem_data")

    def test_retificacao_atribuida_ao_documento_que_alterou(self):
        _, opening = add_document(self.db, "c1", text="Inscrições até 10/12/2026.")
        add_proposal(self.db, "c1", version_id=opening, field="registration_end",
                     value="2026-12-10", quote="Inscrições até 10/12/2026.")
        _, first = add_document(self.db, "c1", tipo="retificacao",
                                title="1ª Retificação", published_at="2026-09-10",
                                text="Inscrições até 20/12/2026.")
        add_proposal(self.db, "c1", version_id=first, field="registration_end",
                     value="2026-12-20", quote="Inscrições até 20/12/2026.")
        _, second = add_document(self.db, "c1", tipo="retificacao",
                                 title="2ª Retificação", published_at="2026-09-20",
                                 text="Requisito alterado.")
        add_proposal(self.db, "c1", version_id=second, field="education",
                     value="Médio", quote="Requisito alterado.")
        report = deadline_review.deadline_report(
            self.db, group="inscricao_fim", now=TODAY + "T12:00:00+00:00")
        item = report["itens"][0]
        self.assertTrue(item["retificacao"]["altera_o_prazo"])
        self.assertEqual(item["retificacao"]["documento"], "1ª Retificação")
        self.assertEqual(item["retificacao"]["valor_na_retificacao"], "2026-12-20")

    def test_retificacao_que_repete_valor_nao_e_causa(self):
        _, opening = add_document(self.db, "c1", text="Inscrições até 10/12/2026.")
        add_proposal(self.db, "c1", version_id=opening, field="registration_end",
                     value="2026-12-10", quote="Inscrições até 10/12/2026.")
        _, retif = add_document(self.db, "c1", tipo="retificacao",
                                title="Retificação", published_at="2026-09-10",
                                text="Inscrições até 10/12/2026.")
        add_proposal(self.db, "c1", version_id=retif, field="registration_end",
                     value="2026-12-10", quote="Inscrições até 10/12/2026.")
        _, cronograma = add_document(self.db, "c1", tipo="cronograma",
                                     title="Cronograma", published_at="2026-09-20",
                                     text="Inscrições até 20/12/2026.")
        cronograma_proposal = add_proposal(
            self.db, "c1", version_id=cronograma, field="registration_end",
            value="2026-12-20", quote="Inscrições até 20/12/2026.")
        groups = conflict_review.conflict_groups(self.db, limit=10)
        item = [group for group in groups["itens"]
                if group["field_name"] == "registration_end"][0]
        # A retificação repetiu o valor de abertura: não é ela a causa da divergência.
        self.assertNotEqual(item["cause"], "retificacao_posterior")
        self.assertEqual(item["vigente_candidato"], cronograma_proposal)

    def test_codigo_nao_supera_nome_compativel(self):
        self.role("c1", "ANALISTA", code="400")
        merendeiro = self.role("c1", "MERENDEIRO", code="401")
        _, version = add_document(self.db, "c1", text="Cargo.")
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Médio", quote="Cargo.",
                     reason="cargo do documento não reconciliado: 400 MERENDEIRO")
        report = role_identity.label_inventory(self.db, limit=10)
        item = [entry for entry in report["itens"]
                if entry["label"] == "400 MERENDEIRO"][0]
        self.assertEqual(item["suggestions"][0]["role_id"], merendeiro)
        self.assertNotEqual(item["suggestions"][0]["state"], "exata")

    def test_criar_cargo_exige_evidencia(self):
        self.role("c1", "OUTRO")
        with self.assertRaisesRegex(ValueError, "sem evidência"):
            role_identity.create_role_for_label(
                self.db, contest_id="c1", label="CARGO INVENTADO", reviewer="Ana",
                reason="x", dry_run=False)

    def test_criar_cargo_respeita_especialidade(self):
        existing = self.role("c1", "ANALISTA", specialty="Direito")
        _, version = add_document(self.db, "c1", text="Requisito.")
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Superior", quote="Requisito.",
                     reason="cargo do documento não reconciliado: ANALISTA")
        result = role_identity.create_role_for_label(
            self.db, contest_id="c1", label="ANALISTA", reviewer="Ana", reason="x",
            specialty="Medicina", dry_run=False)
        self.assertTrue(result["created"])
        self.assertNotEqual(result["role_id"], existing)

    def test_v19_nao_e_legivel(self):
        self.assertNotIn(19, document_store._READABLE_VERSIONS)
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("PRAGMA user_version=19")
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertFalse(document_store.is_readable_schema(conn))


class SchemaTest(unittest.TestCase):
    def test_v20_idempotente_e_preserva_reconciliacoes(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = str(Path(tmp.name) / "x.sqlite3")
        migrate_document_schema(db)
        with closing(sqlite3.connect(db)) as conn, conn:
            conn.execute("INSERT INTO concursos_identidade (id,created_at,estado_identidade) "
                         "VALUES ('c1',?,'certame')", (NOW,))
            conn.execute("INSERT INTO cargos_identidade "
                         "(id,contest_id,name,specialty,created_at,code) "
                         "VALUES ('r1','c1','Analista',NULL,?,NULL)", (NOW,))
            conn.execute("INSERT INTO reconciliacoes_cargo "
                         "(id,contest_id,label,role_id,reconciled_at,reviewer,reason) "
                         "VALUES ('rc','c1','Analista','r1',?,'Ana','ok')", (NOW,))
        migrate_document_schema(db)
        migrate_document_schema(db)
        with closing(sqlite3.connect(db)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0],
                             SCHEMA_VERSION)
            row = conn.execute("SELECT state,role_id,previous_id FROM reconciliacoes_cargo "
                               "WHERE id='rc'").fetchone()
            self.assertEqual(row, ("confirmada", "r1", None))
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])


if __name__ == "__main__":
    unittest.main()
