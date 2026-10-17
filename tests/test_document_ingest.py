"""Documentos bloqueados, alternativas e ingestão manual controlada (Fase 28)."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from radar import document_ingest
from radar.document_store import (connect_documents, migrate_document_schema,
                                  record_version, register_document)

NOW = "2026-10-17T12:00:00+00:00"
PDF = b"%PDF-1.4\nconteudo"


class IngestBase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = str(Path(tmp.name) / "i.sqlite3")
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("INSERT INTO concursos_identidade (id,created_at) "
                         "VALUES ('c','2026-10-01T00:00:00+00:00')")
            conn.execute("INSERT INTO observacoes_concurso (id,contest_id,source_url,"
                         "competition_id,observed_at) VALUES ('o','c',"
                         "'https://concursos.ibfc.org.br/informacoes/485/','ibfc-485',"
                         "'2026-10-01T00:00:00+00:00')")
            conn.commit()
        self.blocked = self._document(
            "https://anexos.cdn.selecao.net.br/uploads/747/concursos/485/anexos/aaa.pdf",
            "Edital bloqueado")
        self.allowed = self._document(
            "https://anexos-r2.selecao.net.br/uploads/747/concursos/485/anexos/bbb.pdf",
            "Edital acessível")
        record_version(self.db, self.allowed, PDF, dict(
            fetched_at="2026-10-01T00:00:00+00:00",
            fetched_url="https://anexos-r2.selecao.net.br/uploads/747/concursos/485/anexos/bbb.pdf",
            content_type="application/pdf"))

    def _document(self, url, title):
        return register_document(self.db, dict(
            observation_id="o", kind="edital", official_url=url, title=title,
            discovery_url="https://concursos.ibfc.org.br/informacoes/485/",
            discovery_method="automatico", discovered_at="2026-10-01T00:00:00+00:00",
            published_at="2026-10-01", tipo_documental="edital_abertura"))


class BlockedTest(IngestBase):
    def test_bloqueio_registrado_de_forma_idempotente(self):
        first = document_ingest.record_blocked_document(
            self.db, self.blocked, "robots_disallow_anexos_cdn",
            evidence={"robots": "Disallow: /"}, detected_at=NOW)
        second = document_ingest.record_blocked_document(
            self.db, self.blocked, "robots_disallow_anexos_cdn",
            evidence={"robots": "Disallow: /"},
            detected_at="2026-10-18T12:00:00+00:00")
        self.assertFalse(first["duplicado"])
        self.assertTrue(second["duplicado"])
        with closing(connect_documents(self.db)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM eventos_documentais "
                                 "WHERE event_type='download_bloqueado'").fetchone()[0]
        self.assertEqual(count, 1)

    def test_motivo_desconhecido_e_recusado(self):
        with self.assertRaisesRegex(ValueError, "desconhecido"):
            document_ingest.record_blocked_document(self.db, self.blocked, "porque sim")

    def test_relatorio_classifica_estado_e_motivo(self):
        document_ingest.record_blocked_document(
            self.db, self.blocked, "robots_disallow_anexos_cdn",
            evidence={"robots": "Disallow: /"}, detected_at=NOW)
        report = document_ingest.blocked_report(self.db)
        by_id = {item["document_id"]: item for item in report["itens"]}
        self.assertEqual(by_id[self.blocked]["state"], "bloqueado")
        self.assertEqual(by_id[self.blocked]["blocked_reason"], "robots_disallow_anexos_cdn")
        self.assertIn("robots.txt", by_id[self.blocked]["blocked_reason_label"])
        self.assertEqual(by_id[self.allowed]["state"], "obtido")
        self.assertEqual(report["por_estado"]["bloqueado"], 1)
        self.assertEqual(report["por_estado"]["obtido"], 1)

    def test_bloqueado_nao_e_tratado_como_inexistente(self):
        report = document_ingest.blocked_report(self.db)
        item = next(i for i in report["itens"] if i["document_id"] == self.blocked)
        self.assertTrue(item["official_url"].endswith("aaa.pdf"))
        self.assertNotIn(item["state"], ("obtido", "inexistente"))
        self.assertIn("não é 'edital inexistente'", report["limitacao"])

    def test_alternativas_nao_usam_semelhanca_de_titulo(self):
        document_ingest.record_blocked_document(
            self.db, self.blocked, "robots_disallow_anexos_cdn", detected_at=NOW)
        report = document_ingest.blocked_report(self.db)
        item = next(i for i in report["itens"] if i["document_id"] == self.blocked)
        kinds = {alternative["tipo"] for alternative in item["alternatives"]}
        self.assertIn("pagina_de_origem", kinds)
        self.assertIn("importacao_manual", kinds)
        self.assertNotIn("caminho_identico_em_host_autorizado", kinds)
        self.assertNotIn("titulo_semelhante", kinds)
        page = next(a for a in item["alternatives"] if a["tipo"] == "pagina_de_origem")
        self.assertFalse(page["download_autorizado"])
        self.assertIn("/informacoes/485/", page["url"])

    def test_caminho_identico_em_host_autorizado_e_alternativa(self):
        # Mesmo caminho da plataforma em host permitido: igualdade exata, não semelhança.
        mirror = self._document(
            "https://anexos-r2.selecao.net.br/uploads/747/concursos/485/anexos/aaa.pdf",
            "Espelho")
        record_version(self.db, mirror, PDF + b"-mirror", dict(
            fetched_at="2026-10-02T00:00:00+00:00",
            fetched_url="https://anexos-r2.selecao.net.br/uploads/747/concursos/485/anexos/aaa.pdf",
            content_type="application/pdf"))
        document_ingest.record_blocked_document(
            self.db, self.blocked, "robots_disallow_anexos_cdn", detected_at=NOW)
        report = document_ingest.blocked_report(self.db)
        item = next(i for i in report["itens"] if i["document_id"] == self.blocked)
        mirrors = [a for a in item["alternatives"]
                   if a["tipo"] == "caminho_identico_em_host_autorizado"]
        self.assertEqual(mirrors[0]["document_id"], mirror)


    def test_relatorio_filtra_por_estado(self):
        document_ingest.record_blocked_document(
            self.db, self.blocked, "robots_disallow_anexos_cdn", detected_at=NOW)
        report = document_ingest.blocked_report(self.db, states="bloqueado")
        self.assertEqual(report["total"], 1)
        self.assertEqual(report["itens"][0]["document_id"], self.blocked)
        self.assertEqual(report["por_estado"]["obtido"], 1)
        with self.assertRaisesRegex(ValueError, "inválido"):
            document_ingest.blocked_report(self.db, states="inexistente")


    def test_espelho_em_host_nao_autorizado_nao_e_apresentado_como_autorizado(self):
        other = self._document(
            "https://espelho-qualquer.example.com/uploads/747/concursos/485/anexos/aaa.pdf",
            "Espelho não autorizado")
        record_version(self.db, other, PDF + b"-x", dict(
            fetched_at="2026-10-03T00:00:00+00:00",
            fetched_url="https://espelho-qualquer.example.com/uploads/747/concursos/485/anexos/aaa.pdf",
            content_type="application/pdf"))
        document_ingest.record_blocked_document(
            self.db, self.blocked, "robots_disallow_anexos_cdn", detected_at=NOW)
        report = document_ingest.blocked_report(self.db, states="bloqueado")
        item = report["itens"][0]
        kinds = {alternative["tipo"] for alternative in item["alternatives"]}
        self.assertIn("caminho_identico_em_host_nao_autorizado", kinds)
        self.assertNotIn("caminho_identico_em_host_autorizado", kinds)


class ManualIngestTest(IngestBase):
    def test_ingestao_manual_registra_procedencia_e_hash(self):
        result = document_ingest.ingest_manual_document(
            self.db, self.blocked, PDF, declared_origin="download manual do portal do órgão",
            channel="upload_local", declared_by="Anton", original_url="https://tjpe.jus.br/e.pdf",
            note="arquivo conferido", now=NOW)
        self.assertFalse(result["duplicada"])
        self.assertEqual(result["content_type"], "application/pdf")
        with closing(connect_documents(self.db)) as conn:
            row = conn.execute("SELECT declared_origin,channel FROM ingestoes_documentais "
                               "WHERE document_id=?", (self.blocked,)).fetchone()
            self.assertEqual(row[0], "download manual do portal do órgão")
            self.assertEqual(row[1], "upload_local")
            version = conn.execute("SELECT sha256 FROM versoes_documento WHERE document_id=?",
                                   (self.blocked,)).fetchone()
            self.assertEqual(version[0], result["sha256"])
        report = document_ingest.blocked_report(self.db)
        item = next(i for i in report["itens"] if i["document_id"] == self.blocked)
        self.assertEqual(item["state"], "importado_manualmente")
        self.assertEqual(item["manual_import"]["channel"], "upload_local")

    def test_ingestao_manual_nao_confirma_nada(self):
        document_ingest.ingest_manual_document(
            self.db, self.blocked, PDF, declared_origin="origem declarada",
            channel="upload_local", declared_by="Anton", now=NOW)
        with closing(connect_documents(self.db)) as conn:
            proposals = conn.execute("SELECT COUNT(*) FROM propostas_campo").fetchone()[0]
            reviews = conn.execute("SELECT COUNT(*) FROM revisoes_campo").fetchone()[0]
            values = conn.execute("SELECT COUNT(*) FROM valores_atuais").fetchone()[0]
        self.assertEqual((proposals, reviews, values), (0, 0, 0))

    def test_ingestao_manual_recusa_formato_desconhecido(self):
        with self.assertRaisesRegex(ValueError, "formato"):
            document_ingest.ingest_manual_document(
                self.db, self.blocked, b"MZ\x90\x00executavel", declared_origin="x",
                channel="upload_local", declared_by="Anton", now=NOW)

    def test_ingestao_manual_recusa_arquivo_vazio(self):
        with self.assertRaisesRegex(ValueError, "vazio"):
            document_ingest.ingest_manual_document(
                self.db, self.blocked, b"", declared_origin="x", channel="upload_local",
                declared_by="Anton", now=NOW)

    def test_ingestao_manual_recusa_url_invalida(self):
        with self.assertRaisesRegex(ValueError, "URL"):
            document_ingest.ingest_manual_document(
                self.db, self.blocked, PDF, declared_origin="x", channel="upload_local",
                declared_by="Anton", original_url="file:///etc/passwd", now=NOW)

    def test_previa_nao_grava(self):
        result = document_ingest.ingest_manual_document(
            self.db, self.blocked, PDF, declared_origin="x", channel="upload_local",
            declared_by="Anton", dry_run=True, now=NOW)
        self.assertTrue(result["dry_run"])
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM ingestoes_documentais").fetchone()[0], 0)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM versoes_documento WHERE document_id=?",
                (self.blocked,)).fetchone()[0], 0)

    def test_mesmo_arquivo_nao_duplica_versao(self):
        first = document_ingest.ingest_manual_document(
            self.db, self.blocked, PDF, declared_origin="x", channel="upload_local",
            declared_by="Anton", now=NOW)
        second = document_ingest.ingest_manual_document(
            self.db, self.blocked, PDF, declared_origin="x", channel="upload_local",
            declared_by="Anton", now=NOW)
        self.assertTrue(second["duplicada"])
        self.assertEqual(second["version_id"], first["version_id"])


if __name__ == "__main__":
    unittest.main()
