"""Exportação, importação, backup e restauração dos dados pessoais de estudo."""

import json
import tempfile
import unittest
from pathlib import Path

from radar import knowledge_store, study_backup, study_store
from radar.document_store import connect_documents, migrate_document_schema


class BackupBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "src.sqlite3")
        migrate_document_schema(self.db)

    def _seed(self, db):
        disc = study_store.create_disciplina(db, "TI")
        top = study_store.create_topico(db, disc["id"], "Redes")
        study_store.set_progress(db, top["id"], "concluido")
        session = study_store.start_session(db, disciplina_id=disc["id"], modo="pomodoro")
        study_store.finish_session(db)
        knowledge_store.set_profile(db, disciplina="TI", rotulo="Redes", nivel="basico")
        return disc, top


class ExportTest(BackupBase):
    def test_export_versionado_com_contagens(self):
        self._seed(self.db)
        payload = study_backup.export_study_data(self.db)
        self.assertEqual(payload["format"], "radar-estudos")
        self.assertEqual(payload["format_version"], study_backup.FORMAT_VERSION)
        self.assertEqual(payload["counts"]["disciplinas"], 1)
        self.assertEqual(payload["counts"]["sessoes"], 1)
        self.assertEqual(payload["counts"]["perfil"], 1)
        self.assertEqual(study_backup.validate_export(payload), [])

    def test_export_nao_inclui_acervo_documental(self):
        payload = study_backup.export_study_data(self.db)
        for forbidden in ("documentos", "propostas_campo", "evidencias", "alertas"):
            self.assertNotIn(forbidden, payload["data"])


class ImportTest(BackupBase):
    def test_validacao_rejeita_arquivo_invalido(self):
        self.assertTrue(study_backup.validate_export({"format": "outro"}))
        self.assertTrue(study_backup.validate_export({"format": "radar-estudos"}))
        report = study_backup.import_study_data(self.db, {"format": "outro"})
        self.assertFalse(report["ok"])
        self.assertTrue(report["errors"])

    def test_validacao_rejeita_item_sem_campo_obrigatorio(self):
        # Regressão: payload que passa na validação não pode estourar KeyError na importação.
        payload = {"format": "radar-estudos", "format_version": 1, "data": {
            "disciplinas": [], "topicos": [], "progresso": [], "sessoes": [], "revisoes": [],
            "perfil": [{"conceito_key": "k", "nivel": "basico"}]}}  # falta id e rotulo
        errors = study_backup.validate_export(payload)
        self.assertTrue(errors)
        report = study_backup.import_study_data(self.db, payload)
        self.assertFalse(report["ok"])  # recusa sem exceção

    def test_topico_com_pai_ausente_importa_na_raiz(self):
        # Regressão: parent_id ausente não pode abortar a importação inteira.
        payload = {"format": "radar-estudos", "format_version": 1, "data": {
            "disciplinas": [{"id": "d1", "nome": "TI"}],
            "topicos": [{"id": "t1", "disciplina_id": "d1", "parent_id": "ausente", "nome": "Redes"}],
            "progresso": [], "sessoes": [], "revisoes": [], "perfil": []}}
        report = study_backup.import_study_data(self.db, payload)
        self.assertTrue(report["ok"])
        self.assertTrue(any(c["entity"] == "topicos" for c in report["conflicts"]))
        self.assertEqual(len(study_store.list_topicos(self.db)), 1)

    def test_dry_run_nao_grava(self):
        self._seed(self.db)
        payload = study_backup.export_study_data(self.db)
        target = str(Path(self.tmp.name) / "target.sqlite3")
        migrate_document_schema(target)
        report = study_backup.import_study_data(target, payload, dry_run=True)
        self.assertTrue(report["ok"])
        self.assertGreater(report["created"], 0)
        self.assertEqual(study_store.list_disciplinas(target), [])  # nada gravado

    def test_importacao_roundtrip(self):
        self._seed(self.db)
        payload = study_backup.export_study_data(self.db)
        target = str(Path(self.tmp.name) / "target.sqlite3")
        migrate_document_schema(target)
        report = study_backup.import_study_data(target, payload)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(len(study_store.list_disciplinas(target)), 1)
        self.assertEqual(len(study_store.list_sessions(target)), 1)
        self.assertEqual(len(knowledge_store.list_profile(target)), 1)

    def test_reimportar_nao_duplica(self):
        self._seed(self.db)
        payload = study_backup.export_study_data(self.db)
        target = str(Path(self.tmp.name) / "target.sqlite3")
        migrate_document_schema(target)
        study_backup.import_study_data(target, payload)
        second = study_backup.import_study_data(target, payload)
        self.assertEqual(second["created"], 0)
        self.assertGreater(second["skipped"], 0)
        self.assertEqual(len(study_store.list_disciplinas(target)), 1)

    def test_preserva_dados_existentes_por_padrao(self):
        self._seed(self.db)
        payload = study_backup.export_study_data(self.db)
        target = str(Path(self.tmp.name) / "target.sqlite3")
        migrate_document_schema(target)
        existing = study_store.create_disciplina(target, "Local")
        study_backup.import_study_data(target, payload)
        names = {d["nome"] for d in study_store.list_disciplinas(target)}
        self.assertIn("Local", names)  # dado local preservado
        self.assertIn("TI", names)

    def test_conflito_de_topico_ausente(self):
        # Tópico cuja disciplina de origem não existe no destino -> conflito, não erro fatal.
        payload = {"format": "radar-estudos", "format_version": 1, "data": {
            "disciplinas": [], "topicos": [{"id": "t1", "disciplina_id": "ausente", "nome": "X"}],
            "progresso": [], "sessoes": [], "revisoes": [], "perfil": []}}
        report = study_backup.import_study_data(self.db, payload)
        self.assertTrue(report["ok"])
        self.assertTrue(any(c["entity"] == "topicos" for c in report["conflicts"]))

    def test_sessao_aberta_finalizada_na_importacao(self):
        disc = study_store.create_disciplina(self.db, "TI")
        study_store.start_session(self.db, disciplina_id=disc["id"])  # fica aberta
        payload = study_backup.export_study_data(self.db)
        target = str(Path(self.tmp.name) / "target.sqlite3")
        migrate_document_schema(target)
        report = study_backup.import_study_data(target, payload)
        self.assertTrue(report["ok"])
        self.assertIsNone(study_store.current_session(target))  # nenhuma sessão aberta
        concluded = study_store.list_sessions(target, concluidas_only=True)
        self.assertEqual(len(concluded), 1)
        self.assertIsNotNone(concluded[0]["fim"])  # finalizada com fim materializado

    def test_backup_recusa_destino_igual_a_origem(self):
        with self.assertRaises(ValueError):
            study_backup.backup_database(self.db, self.db)


class BackupRestoreTest(BackupBase):
    def test_backup_consistente_com_integridade(self):
        self._seed(self.db)
        dest = str(Path(self.tmp.name) / "backup.sqlite3")
        out = study_backup.backup_database(self.db, dest)
        self.assertEqual(out["integrity"], "ok")
        self.assertEqual(out["counts"]["disciplinas"], 1)
        self.assertTrue(Path(dest).exists())

    def test_restore_em_banco_isolado(self):
        self._seed(self.db)
        dest = str(Path(self.tmp.name) / "backup.sqlite3")
        study_backup.backup_database(self.db, dest)
        restored = str(Path(self.tmp.name) / "restored.sqlite3")
        out = study_backup.restore_database(dest, restored)
        self.assertEqual(out["integrity"], "ok")
        self.assertEqual(out["counts"]["sessoes"], 1)
        # Integridade e dados conferem no destino.
        conn = connect_documents(restored)
        try:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("SELECT count(*) FROM estudo_disciplinas").fetchone()[0], 1)
        finally:
            conn.close()

    def test_backup_nao_altera_origem(self):
        self._seed(self.db)
        dest = str(Path(self.tmp.name) / "backup.sqlite3")
        study_backup.backup_database(self.db, dest)
        self.assertEqual(len(study_store.list_disciplinas(self.db)), 1)  # origem intacta


class PracticeBackupTest(BackupBase):
    """Formato v2: prática incluída; v1 continua importável."""

    def _seed_practice(self, db):
        from radar import practice_store
        card = practice_store.create_flashcard(db, frente="F?", verso="V")
        practice_store.review_flashcard(db, card["id"], 4)
        q = practice_store.create_question(db, enunciado="Pergunta número 1?",
                                          alternativas=["a", "b"], gabarito="A")
        practice_store.answer_question(db, q["id"], "A")
        for i in range(2):
            practice_store.create_question(db, enunciado=f"Outra {i}?", alternativas=["a", "b"],
                                           gabarito="A")
        exam = practice_store.create_exam(db, nome="S", limit=2, seed=1, exclude_answered=False)
        practice_store.save_exam_answer(db, exam["id"], 0, "A")
        practice_store.finish_exam(db, exam["id"])

    def test_export_inclui_pratica(self):
        self._seed_practice(self.db)
        payload = study_backup.export_study_data(self.db)
        self.assertEqual(payload["format_version"], 2)
        self.assertEqual(payload["counts"]["flashcards"], 1)
        self.assertEqual(payload["counts"]["questoes"], 3)
        self.assertEqual(payload["counts"]["simulados"], 1)
        self.assertEqual(study_backup.validate_export(payload), [])

    def test_roundtrip_da_pratica(self):
        self._seed_practice(self.db)
        payload = study_backup.export_study_data(self.db)
        target = str(Path(self.tmp.name) / "tgt.sqlite3")
        migrate_document_schema(target)
        report = study_backup.import_study_data(target, payload)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["created"], 14)
        second = study_backup.import_study_data(target, payload)
        self.assertEqual(second["created"], 0)  # idempotente
        self.assertEqual(second["skipped"], 14)

    def test_arquivo_v1_continua_importavel(self):
        # Compatibilidade: um arquivo v1 (sem prática) não pode quebrar a importação.
        v1 = {"format": "radar-estudos", "format_version": 1,
              "data": {k: [] for k in ("disciplinas", "topicos", "progresso", "sessoes",
                                       "revisoes", "perfil")}}
        self.assertEqual(study_backup.validate_export(v1), [])
        report = study_backup.import_study_data(self.db, v1)
        self.assertTrue(report["ok"])

    def test_ordem_zero_nao_e_campo_ausente(self):
        # Regressão: `ordem=0` é válido (não pode ser tratado como ausente).
        payload = {"format": "radar-estudos", "format_version": 2, "data": {
            "disciplinas": [], "topicos": [], "progresso": [], "sessoes": [], "revisoes": [],
            "perfil": [], "flashcards": [], "flashcard_revisoes": [],
            "questoes": [{"id": "q1", "enunciado": "Pergunta?", "gabarito": "A"}],
            "questao_versoes": [], "tentativas": [],
            "simulados": [{"id": "s1", "nome": "S", "estado": "finalizado"}],
            "simulado_questoes": [{"simulado_id": "s1", "ordem": 0, "questao_id": "q1",
                                   "questao_versao": 1}]}}
        self.assertEqual(study_backup.validate_export(payload), [])

    def test_versao_divergente_nao_corrompe_a_cadeia(self):
        # Regressão C2: importar uma versão superior não pode travar a edição futura.
        from radar import practice_store
        q = practice_store.create_question(self.db, enunciado="Pergunta original?",
                                           alternativas=["a", "b"], gabarito="A")
        # Arquivo de outra máquina com a MESMA questão na versão 2.
        payload = {"format": "radar-estudos", "format_version": 2, "data": {
            "disciplinas": [], "topicos": [], "progresso": [], "sessoes": [], "revisoes": [],
            "perfil": [], "flashcards": [], "flashcard_revisoes": [], "tentativas": [],
            "simulados": [], "simulado_questoes": [],
            "questoes": [{"id": q["id"], "versao": 2, "enunciado": "Pergunta original?",
                          "gabarito": "A"}],
            "questao_versoes": [{"id": "other-line", "questao_id": q["id"], "versao": 2,
                                 "enunciado": "Pergunta editada?", "gabarito": "A"}]}}
        report = study_backup.import_study_data(self.db, payload)
        self.assertTrue(report["ok"], report["errors"])
        # A questão local continua editável (não colide em UNIQUE(questao_id, versao)).
        updated = practice_store.update_question(self.db, q["id"], enunciado="Nova edição?")
        self.assertGreater(updated["versao"], 2)

    def test_enum_invalido_rejeitado_na_validacao(self):
        # Regressão I2: domínio inválido deve ser erro de arquivo (400), não IntegrityError.
        payload = {"format": "radar-estudos", "format_version": 2, "data": {
            "disciplinas": [], "topicos": [], "progresso": [], "sessoes": [], "revisoes": [],
            "perfil": [], "flashcards": [{"id": "f1", "frente": "F", "verso": "V",
                                          "estado": "deleted"}],
            "flashcard_revisoes": [], "questoes": [], "questao_versoes": [], "tentativas": [],
            "simulados": [], "simulado_questoes": []}}
        errors = study_backup.validate_export(payload)
        self.assertTrue(any("estado inválido" in e for e in errors))
        report = study_backup.import_study_data(self.db, payload)
        self.assertFalse(report["ok"])


if __name__ == "__main__":
    unittest.main()
