"""Identidade canônica do concurso e associações documentais (Fase 27)."""

import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from radar import identity
from radar.document_store import (
    connect_documents,
    ensure_observation,
    migrate_document_schema,
    register_document,
)

NOW = "2026-10-17T12:00:00+00:00"


class IdentityBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "i.sqlite3")
        migrate_document_schema(self.db)

    def document(self, observation_id, url, *, kind="edital", title="Edital",
                 issuer=None, published_at=None, document_type=None):
        return register_document(self.db, {
            "observation_id": observation_id, "kind": kind, "official_url": url,
            "title": title, "discovery_url": "https://fonte.test/",
            "discovery_method": "automatico", "discovered_at": NOW,
            "issuer": issuer, "published_at": published_at,
            "document_type": document_type})

    def counts(self):
        with closing(connect_documents(self.db)) as conn:
            return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    for t in ("concursos_identidade", "observacoes_concurso", "documentos",
                              "associacoes_documento", "propostas_campo", "valores_atuais")}


class ClassificationTest(unittest.TestCase):
    def test_secao_de_diario_nao_e_certame(self):
        self.assertEqual(identity.classify_external_id("DOU-S3"), "secao_publicacao")
        self.assertEqual(identity.classify_external_id("dou-s1"), "secao_publicacao")
        self.assertEqual(identity.classify_external_id("DO-3"), "secao_publicacao")

    def test_catalogo(self):
        self.assertEqual(identity.classify_external_id("catalogo-2026"), "catalogo")

    def test_identificador_de_certame(self):
        for value in ("quadrix-3056", "ibfc-497", "tjap26", "pci-267456"):
            self.assertEqual(identity.classify_external_id(value), "certame", value)

    def test_vazio_e_desconhecido(self):
        self.assertEqual(identity.classify_external_id(""), "desconhecida")
        self.assertEqual(identity.classify_external_id(None), "desconhecida")


class ObservationTypeTest(IdentityBase):
    def test_fonte_de_secao_cria_container(self):
        observation = ensure_observation(self.db, "https://www.in.gov.br/leiturajornal?secao=do3",
                                         "DOU-S3")
        with closing(connect_documents(self.db)) as conn:
            row = conn.execute(
                "SELECT o.tipo_identidade, c.estado_identidade FROM observacoes_concurso o "
                "JOIN concursos_identidade c ON c.id=o.contest_id WHERE o.id=?",
                (observation,)).fetchone()
        self.assertEqual(row, ("secao_publicacao", "container_fonte"))
        self.assertEqual(len(identity.containers(self.db)), 1)
        self.assertEqual(identity.certame_ids(self.db), [])

    def test_certame_normal_continua_certame(self):
        ensure_observation(self.db, "https://conhecimento.fgv.br/concursos/x", "tjap26")
        self.assertEqual(identity.containers(self.db), [])
        self.assertEqual(len(identity.certame_ids(self.db)), 1)

    def test_idempotente(self):
        first = ensure_observation(self.db, "https://www.in.gov.br/leiturajornal?secao=do3",
                                   "DOU-S3")
        second = ensure_observation(self.db, "https://www.in.gov.br/leiturajornal?secao=do3",
                                    "DOU-S3")
        self.assertEqual(first, second)
        self.assertEqual(self.counts()["concursos_identidade"], 1)


class PendingAssociationTest(IdentityBase):
    def test_documento_em_container_nasce_pendente(self):
        observation = ensure_observation(self.db, "https://www.in.gov.br/leiturajornal?secao=do3",
                                         "DOU-S3")
        document_id = self.document(observation, "https://www.in.gov.br/web/dou/-/a",
                                    issuer="Ministerio da Educacao/UFMA",
                                    published_at="2026-10-15")
        with closing(connect_documents(self.db)) as conn:
            row = conn.execute(
                "SELECT state, contest_id, evidence_json FROM associacoes_documento "
                "WHERE document_id=?", (document_id,)).fetchone()
        self.assertEqual(row[0], "pendente")
        self.assertIsNone(row[1])
        evidence = json.loads(row[2])
        self.assertEqual(evidence["orgao"], "Ministerio da Educacao/UFMA")
        self.assertEqual(evidence["grupo_candidato"], "ministerio da educacao ufma")
        self.assertEqual(evidence["identificador_fonte"], "DOU-S3")

    def test_documento_de_certame_nao_cria_pendencia(self):
        observation = ensure_observation(self.db, "https://conhecimento.fgv.br/concursos/x",
                                         "tjap26")
        self.document(observation, "https://conhecimento.fgv.br/x")
        self.assertEqual(self.counts()["associacoes_documento"], 0)

    def test_repetir_registro_nao_duplica_pendencia(self):
        observation = ensure_observation(self.db, "https://www.in.gov.br/leiturajornal?secao=do3",
                                         "DOU-S3")
        for _ in range(3):
            self.document(observation, "https://www.in.gov.br/web/dou/-/a",
                          issuer="Orgao X")
        self.assertEqual(self.counts()["associacoes_documento"], 1)


class RecordAssociationTest(IdentityBase):
    def setUp(self):
        super().setUp()
        self.container = ensure_observation(
            self.db, "https://www.in.gov.br/leiturajornal?secao=do3", "DOU-S3")
        self.certame = ensure_observation(
            self.db, "https://conhecimento.fgv.br/concursos/x", "tjap26")
        self.document_id = self.document(self.container, "https://www.in.gov.br/web/dou/-/a",
                                         issuer="Orgao X")

    def _contest(self):
        with closing(connect_documents(self.db)) as conn:
            return conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                (self.certame,)).fetchone()[0]

    def test_confirma_associacao_com_historico(self):
        contest = self._contest()
        first = identity.record_association(
            self.db, self.document_id, contest, "confirmada", {"motivo": "edital confere"},
            decided_by="revisor", note="número e órgão conferem", dry_run=False)
        self.assertFalse(first["duplicada"])
        with closing(connect_documents(self.db)) as conn:
            current = identity.current_association(conn, self.document_id)
        self.assertEqual(current["state"], "confirmada")
        self.assertEqual(current["contest_id"], contest)

    def test_decisao_repetida_nao_duplica(self):
        contest = self._contest()
        identity.record_association(self.db, self.document_id, contest, "confirmada",
                                    {"motivo": "x"}, decided_by="revisor", note="ok",
                                    dry_run=False)
        again = identity.record_association(self.db, self.document_id, contest, "confirmada",
                                            {"motivo": "x"}, decided_by="revisor", note="ok",
                                            dry_run=False)
        self.assertTrue(again["duplicada"])
        self.assertEqual(self.counts()["associacoes_documento"], 2)  # pendente + confirmada

    def test_rejeitar_exige_justificativa(self):
        with self.assertRaises(ValueError):
            identity.record_association(self.db, self.document_id, None, "rejeitada",
                                        {"motivo": "x"}, decided_by="revisor", note=" ")

    def test_pendente_nao_pode_apontar_concurso(self):
        with self.assertRaises(ValueError):
            identity.record_association(self.db, self.document_id, self._contest(), "pendente",
                                        {"motivo": "x"}, decided_by="r", note="n")

    def test_dry_run_nao_grava(self):
        before = self.counts()
        identity.record_association(self.db, self.document_id, self._contest(), "confirmada",
                                    {"motivo": "x"}, decided_by="revisor", note="ok")
        self.assertEqual(self.counts(), before)

    def test_concurso_inexistente_rejeitado(self):
        with self.assertRaises(ValueError):
            identity.record_association(self.db, self.document_id, "nao-existe", "confirmada",
                                        {"motivo": "x"}, decided_by="r", note="n",
                                        dry_run=False)


class RepairTest(IdentityBase):
    def setUp(self):
        super().setUp()
        self.container = ensure_observation(
            self.db, "https://www.in.gov.br/leiturajornal?secao=do3", "DOU-S3")
        # Legado: concurso criado como certame antes da correção (estado 'certame').
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute("UPDATE concursos_identidade SET estado_identidade='certame'")
            conn.execute("UPDATE observacoes_concurso SET tipo_identidade='certame'")
        self.docs = [
            self.document(self.container, "https://www.in.gov.br/web/dou/-/a",
                          title="EDITAL Nº 8", issuer="Orgao A", published_at="2026-10-15"),
            self.document(self.container, "https://www.in.gov.br/web/dou/-/b",
                          title="EDITAL Nº 19", issuer="Orgao B", published_at="2026-10-15"),
        ]

    def test_plano_detecta_identidade_de_secao(self):
        plan = identity.repair_plan(self.db)
        self.assertEqual(plan["concursos_afetados"], 1)
        self.assertEqual(plan["documentos_afetados"], 2)
        action = plan["acoes"][0]
        self.assertEqual(action["acao"], "marcar_container")
        self.assertEqual(len(action["grupos_candidatos"]), 2)
        self.assertEqual(action["propostas"], 0)

    def test_plano_nao_altera_nada(self):
        before = self.counts()
        identity.repair_plan(self.db)
        self.assertEqual(self.counts(), before)

    def test_reparacao_marca_container_e_pendencias(self):
        report = identity.apply_repair(self.db, decided_by="revisor",
                                       note="identidade de fonte não é certame",
                                       dry_run=False)
        self.assertEqual(report["concursos_marcados"], 1)
        self.assertEqual(report["observacoes_tipadas"], 1)
        self.assertEqual(report["associacoes_criadas"], 2)
        self.assertEqual(identity.containers(self.db), [self._contest()])
        self.assertEqual(identity.certame_ids(self.db), [])

    def test_reparacao_idempotente(self):
        identity.apply_repair(self.db, decided_by="revisor", note="x", dry_run=False)
        second = identity.apply_repair(self.db, decided_by="revisor", note="x", dry_run=False)
        self.assertEqual(second["concursos_marcados"], 0)
        self.assertEqual(second["associacoes_criadas"], 0)

    def test_reparacao_preserva_documentos(self):
        before = self.counts()
        identity.apply_repair(self.db, decided_by="revisor", note="x", dry_run=False)
        after = self.counts()
        self.assertEqual(after["documentos"], before["documentos"])
        self.assertEqual(after["propostas_campo"], before["propostas_campo"])
        self.assertEqual(after["valores_atuais"], 0)

    def test_reparacao_nao_cria_certame(self):
        identity.apply_repair(self.db, decided_by="revisor", note="x", dry_run=False)
        self.assertEqual(self.counts()["concursos_identidade"], 1)

    def _contest(self):
        with closing(connect_documents(self.db)) as conn:
            return conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                (self.container,)).fetchone()[0]


class QueueTest(IdentityBase):
    def test_fila_lista_pendentes_com_evidencia(self):
        observation = ensure_observation(self.db, "https://www.in.gov.br/leiturajornal?secao=do3",
                                         "DOU-S3")
        self.document(observation, "https://www.in.gov.br/web/dou/-/a", issuer="Orgao A")
        queue = identity.association_queue(self.db)
        self.assertEqual(queue["total"], 1)
        item = queue["itens"][0]
        self.assertEqual(item["estado"], "pendente")
        self.assertEqual(item["evidencia"]["orgao"], "Orgao A")
        self.assertIsNone(item["contest_id"])

    def test_filtro_por_estado(self):
        observation = ensure_observation(self.db, "https://www.in.gov.br/leiturajornal?secao=do3",
                                         "DOU-S3")
        self.document(observation, "https://www.in.gov.br/web/dou/-/a")
        self.assertEqual(identity.association_queue(self.db, state="confirmada")["total"], 0)
        self.assertEqual(identity.association_queue(self.db, state="pendente")["total"], 1)


class AuditTest(IdentityBase):
    def test_auditoria_conta_containers_e_certames(self):
        ensure_observation(self.db, "https://www.in.gov.br/leiturajornal?secao=do3", "DOU-S3")
        ensure_observation(self.db, "https://conhecimento.fgv.br/concursos/x", "tjap26")
        audit = identity.identity_audit(self.db)
        self.assertEqual(audit["concursos"], 2)
        self.assertEqual(audit["certames"], 1)
        self.assertEqual(audit["containers"], 1)
        self.assertEqual(audit["suspeitos"], [])

    def test_auditoria_aponta_legado_sem_marcar(self):
        observation = ensure_observation(
            self.db, "https://www.in.gov.br/leiturajornal?secao=do3", "DOU-S3")
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute("UPDATE concursos_identidade SET estado_identidade='certame'")
            conn.execute("UPDATE observacoes_concurso SET tipo_identidade='certame'")
        audit = identity.identity_audit(self.db)
        self.assertEqual(len(audit["suspeitos"]), 1)
        self.assertEqual(audit["suspeitos"][0]["observation_id"], observation)


class HumanDecisionTest(IdentityBase):
    """Regressão: reparar de novo não pode desfazer decisão humana."""

    def setUp(self):
        super().setUp()
        self.container = ensure_observation(
            self.db, "https://www.in.gov.br/leiturajornal?secao=do3", "DOU-S3")
        self.certame = ensure_observation(
            self.db, "https://conhecimento.fgv.br/concursos/x", "tjap26")
        self.document_id = self.document(self.container,
                                         "https://www.in.gov.br/web/dou/-/a",
                                         issuer="Orgao A")
        identity.apply_repair(self.db, decided_by="anton", note="x", dry_run=False)

    def _certame(self):
        with closing(connect_documents(self.db)) as conn:
            return conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                (self.certame,)).fetchone()[0]

    def test_reparar_de_novo_preserva_confirmacao(self):
        identity.record_association(self.db, self.document_id, self._certame(), "confirmada",
                                    {"motivo": "confere"}, decided_by="revisor", note="ok",
                                    dry_run=False)
        again = identity.apply_repair(self.db, decided_by="anton", note="x", dry_run=False)
        self.assertEqual(again["associacoes_criadas"], 0)
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(identity.current_association(conn, self.document_id)["state"],
                             "confirmada")

    def test_plano_nao_repete_acao_apos_reparo(self):
        identity.record_association(self.db, self.document_id, self._certame(), "confirmada",
                                    {"motivo": "confere"}, decided_by="revisor", note="ok",
                                    dry_run=False)
        self.assertEqual(identity.repair_plan(self.db)["concursos_afetados"], 0)

    def test_container_nao_e_alvo_de_associacao(self):
        with closing(connect_documents(self.db)) as conn:
            container_id = conn.execute(
                "SELECT contest_id FROM observacoes_concurso WHERE id=?",
                (self.container,)).fetchone()[0]
        with self.assertRaises(ValueError):
            identity.record_association(self.db, self.document_id, container_id, "confirmada",
                                        {"motivo": "x"}, decided_by="r", note="n",
                                        dry_run=False)


class ContainerExclusionTest(IdentityBase):
    """Containers não entram em métricas de certame (cobertura, prioridade, saúde)."""

    def setUp(self):
        super().setUp()
        self.container = ensure_observation(
            self.db, "https://www.in.gov.br/leiturajornal?secao=do3", "DOU-S3")
        self.document(self.container, "https://www.in.gov.br/web/dou/-/a", issuer="Orgao A")
        self.certame = ensure_observation(
            self.db, "https://conhecimento.fgv.br/concursos/x", "tjap26")
        self.document(self.certame, "https://conhecimento.fgv.br/x")

    def test_cobertura_exclui_container(self):
        from radar import data_quality
        result = data_quality.audit(self.db, now=NOW)
        self.assertEqual(result["escopo"]["concursos"], 1)
        self.assertEqual(result["escopo"]["containers_fonte"], 1)
        self.assertEqual(result["escopo"]["documentos_em_container"], 1)
        self.assertEqual(result["funil"][0]["quantidade"], 1)

    def test_prioridade_exclui_container(self):
        from radar import preferences, priority
        result = priority.prioritize(self.db, dict(preferences.DEFAULTS), limit=50)
        ids = [item["contest_id"] for item in result["items"]]
        with closing(connect_documents(self.db)) as conn:
            container_id = conn.execute(
                "SELECT contest_id FROM observacoes_concurso WHERE id=?",
                (self.container,)).fetchone()[0]
        self.assertNotIn(container_id, ids)

    def test_saude_conta_apenas_certames(self):
        import sys
        from radar import ops, ops_config
        cfg = ops_config.load_config()
        cfg.update({"project_root": str(Path(self.tmp.name)),
                    "python": sys.executable, "db_path": self.db,
                    "logs_dir": str(Path(self.tmp.name) / "logs")})
        health = ops.health(cfg, check_server=False)
        self.assertEqual(health["database"]["contests"], 1)

    def test_associacao_ignora_container(self):
        from radar import association
        report = association.suspect_associations(self.db)
        self.assertEqual(report["total"], 0)
        self.assertEqual(report["containers_fonte"], 1)


if __name__ == "__main__":
    unittest.main()
