"""Pipeline documental end-to-end: estados, extração controlada, cobertura (Fase 30)."""

import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter
from radar import pipeline
from radar.document_store import (connect_documents, migrate_document_schema, record_analysis,
                                  record_version, register_document)
from radar.server import create_server

NOW = "2026-10-17T12:00:00+00:00"


def text_pdf(lines: list[str]) -> bytes:
    """PDF textual mínimo (uma página) para exercitar o extrator real."""
    content = "BT /F1 12 Tf 40 700 Td " + " ".join(
        f"({line}) Tj 0 -16 Td" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


def multipage_text_pdf(pages: int, line: str = "10 vagas imediatas") -> bytes:
    """PDF textual com N páginas, cada uma com a mesma linha de texto."""
    content = "BT /F1 12 Tf 40 700 Td " + f"({line}) Tj ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [%s] /Count %d >>" % (
            " ".join(f"{4 + 2 * i} 0 R" for i in range(pages)), pages),
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    kids = []
    for _ in range(pages):
        page_obj = len(objects) + 1
        content_obj = page_obj + 1
        kids.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                    f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_obj} 0 R >>")
        objects.append(kids[-1])
        objects.append(f"<< /Length {len(content)} >>\nstream\n{content}\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


def blank_pdf(pages: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class PipelineBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "radar.sqlite3")
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("INSERT INTO concursos_identidade (id,created_at) "
                         "VALUES ('c','2026-10-01T00:00:00+00:00')")
            conn.execute("INSERT INTO observacoes_concurso (id,contest_id,source_url,"
                         "competition_id,observed_at) VALUES ('o','c',"
                         "'https://anexos-r2.selecao.net.br/uploads/1/','ibfc-1',?)", (NOW,))
            conn.commit()

    def document(self, url, title, *, kind="edital", tipo="edital_abertura",
                 published="2026-10-01", issuer="IBFC", identifier=None):
        return register_document(self.db, dict(
            observation_id="o", kind=kind, official_url=url, title=title,
            discovery_url="https://anexos-r2.selecao.net.br/uploads/1/",
            discovery_method="automatico", discovered_at=NOW, published_at=published,
            tipo_documental=tipo, issuer=issuer,
            source_identifier=identifier or f"ibfc-1:{url.rsplit('/', 1)[-1]}"))

    def version(self, document_id, body, *, content_type="application/pdf"):
        return record_version(self.db, document_id, body, dict(
            fetched_at=NOW, fetched_url=f"https://x/{document_id}.pdf",
            content_type=content_type))


class DocumentStageTest(PipelineBase):
    def test_documento_sem_versao_fica_em_sem_versao(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/a.pdf", "Edital")
        audit = pipeline.audit_documents(self.db, document_id=doc)
        item = audit["itens"][0]
        self.assertEqual(item["blocked_at"], "sem_versao")
        self.assertFalse(item["review_ready"])
        self.assertEqual(item["stages"], ["descoberto"])

    def test_baixado_nao_e_extraido(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/b.pdf", "Edital")
        self.version(doc, blank_pdf())
        item = pipeline.audit_documents(self.db, document_id=doc)["itens"][0]
        self.assertIn("baixado", item["stages"])
        self.assertNotIn("extraido", item["stages"])
        self.assertEqual(item["blocked_at"], "nao_iniciada")

    def test_extraido_com_propostas_fica_pronto_para_revisao(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/c.pdf", "Edital")
        version = self.version(doc, text_pdf([
            "10 vagas imediatas",
            "Inscricoes de 01/10/2026 a 20/10/2026",
        ]))
        report = pipeline.analyze_versions(self.db, [version], dry_run=False)
        self.assertEqual(report["extraidas"], 1)
        item = pipeline.audit_documents(self.db, document_id=doc)["itens"][0]
        self.assertTrue(item["proposals"] > 0)
        self.assertTrue(item["review_ready"])
        self.assertIsNone(item["blocked_at"])

    def test_bloqueio_sem_texto_e_distinto_de_nao_iniciada(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/w.pdf", "Sem texto")
        version = self.version(doc, blank_pdf(1))
        pipeline.analyze_versions(self.db, [version], dry_run=False)
        item = pipeline.audit_documents(self.db, document_id=doc)["itens"][0]
        self.assertEqual(item["blocked_at"], "sem_texto")
        self.assertIn("OCR", item["blocked_reason"])
        self.assertEqual(item["last_extraction_error"], "pdf_sem_texto")
        summary = pipeline.pipeline_summary(self.db)
        self.assertEqual(summary["documentos_por_bloqueio"].get("sem_texto"), 1)
        self.assertNotIn("nao_iniciada", summary["documentos_por_bloqueio"])

    def test_truncamento_nao_conta_como_falha(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/x.pdf", "Lista")
        version = self.version(doc, multipage_text_pdf(3))
        from radar import document_extract, monitoring
        original_prefix = monitoring.PREFIX_PAGES
        original_pages = document_extract._MAX_PAGES
        monitoring.PREFIX_PAGES = 1
        document_extract._MAX_PAGES = 2
        try:
            pipeline.analyze_versions(self.db, [version], dry_run=False)
        finally:
            monitoring.PREFIX_PAGES = original_prefix
            document_extract._MAX_PAGES = original_pages
        coverage = pipeline.contest_coverage(self.db)
        item = next(i for i in coverage["itens"] if i["contest_id"] == "c")
        self.assertEqual(item["falhas_extracao"], 0)
        self.assertEqual(item["paginas_excedidas"], 1)

    def test_falha_permanente_nao_entra_na_fila_de_pendentes(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/d.pdf", "Sem texto")
        version = self.version(doc, blank_pdf(1))
        report = pipeline.analyze_versions(self.db, [version], dry_run=False)
        self.assertEqual(report["falhas"][0]["code"], "pdf_sem_texto")
        self.assertEqual(pipeline.pending_versions(self.db), [])
        blocked = pipeline.pending_versions(self.db, include_blocked=True)
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0]["error_code"], "pdf_sem_texto")


class ExtractionTest(PipelineBase):
    def test_dry_run_nao_grava_nada(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/e.pdf", "Edital")
        version = self.version(doc, text_pdf(["10 vagas imediatas"]))
        preview = pipeline.analyze_versions(self.db, [version], dry_run=True)
        self.assertGreater(preview["previa"][0]["would_blocks"], 0)
        self.assertEqual(preview["previa"][0]["citacoes_invalidas"], 0)
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM blocos_documento")
                             .fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM propostas_campo")
                             .fetchone()[0], 0)

    def test_reprocessar_nao_duplica(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/f.pdf", "Edital")
        version = self.version(doc, text_pdf(["10 vagas imediatas"]))
        pipeline.analyze_versions(self.db, [version], dry_run=False)
        with closing(connect_documents(self.db)) as conn:
            first = (conn.execute("SELECT COUNT(*) FROM blocos_documento").fetchone()[0],
                     conn.execute("SELECT COUNT(*) FROM propostas_campo").fetchone()[0],
                     conn.execute("SELECT COUNT(*) FROM evidencias").fetchone()[0])
        second = pipeline.analyze_versions(self.db, [version], dry_run=False)
        self.assertEqual(second["ja_analisadas"], 1)
        self.assertEqual(second["extraidas"], 0)
        with closing(connect_documents(self.db)) as conn:
            after = (conn.execute("SELECT COUNT(*) FROM blocos_documento").fetchone()[0],
                     conn.execute("SELECT COUNT(*) FROM propostas_campo").fetchone()[0],
                     conn.execute("SELECT COUNT(*) FROM evidencias").fetchone()[0])
        self.assertEqual(first, after)

    def test_pdf_longo_usa_prefixo_e_registra_limitacao(self):
        from radar.document_extract import extract_document
        # 3 páginas, limite 2, prefixo 1: truncamento real, não simulado.
        extracted = extract_document(multipage_text_pdf(3), "application/pdf",
                                     max_pages=2, prefix_pages=1)
        self.assertTrue(extracted["truncated"])
        self.assertEqual(extracted["total_pages"], 3)
        self.assertEqual(len(extracted["blocks"]), 1)
        self.assertEqual(extracted["blocks"][0]["page_number"], 1)
        self.assertIn("1 primeiras de 3 páginas", extracted["limitation"])

    def test_pdf_longo_sem_prefixo_e_recusado_com_codigo(self):
        from radar.document_extract import ExtractionError, extract_document
        with self.assertRaises(ExtractionError) as ctx:
            extract_document(multipage_text_pdf(3), "application/pdf", max_pages=2)
        self.assertEqual(ctx.exception.code, "pdf_paginas_excedidas")

    def test_analise_limpa_erro_anterior(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/t.pdf", "Edital")
        version = self.version(doc, text_pdf(["10 vagas imediatas"]))
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute("UPDATE versoes_documento SET extraction_state='falhou', "
                         "error_code='pdf_sem_texto' WHERE id=?", (version,))
        pipeline.analyze_versions(self.db, [version], dry_run=False)
        with closing(connect_documents(self.db)) as conn:
            row = conn.execute("SELECT extraction_state, error_code FROM versoes_documento "
                               "WHERE id=?", (version,)).fetchone()
        self.assertEqual(row, ("parcial", None))

    def test_dry_run_isola_versao_invalida(self):
        report = pipeline.analyze_versions(self.db, ["nao-existe"], dry_run=True)
        self.assertEqual(report["falhas"][0]["code"], "ValueError")
        self.assertEqual(report["previa"], [])

    def test_versao_nova_preserva_versao_anterior(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/h.pdf", "Edital")
        first = self.version(doc, text_pdf(["10 vagas imediatas"]))
        pipeline.analyze_versions(self.db, [first], dry_run=False)
        with closing(connect_documents(self.db)) as conn:
            old_blocks = conn.execute(
                "SELECT COUNT(*) FROM blocos_documento WHERE version_id=?",
                (first,)).fetchone()[0]
        second = record_version(self.db, doc, text_pdf(["12 vagas imediatas"]), dict(
            fetched_at="2026-10-18T00:00:00+00:00",
            fetched_url="https://x/h.pdf", content_type="application/pdf"))
        pipeline.analyze_versions(self.db, [second], dry_run=False)
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM blocos_documento WHERE version_id=?",
                (first,)).fetchone()[0], old_blocks)
            self.assertGreater(conn.execute(
                "SELECT COUNT(*) FROM blocos_documento WHERE version_id=?",
                (second,)).fetchone()[0], 0)

    def test_decisao_humana_nao_e_alterada_por_reextracao(self):
        from radar import review
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/i.pdf", "Edital")
        version = self.version(doc, text_pdf(["10 vagas imediatas"]))
        pipeline.analyze_versions(self.db, [version], dry_run=False)
        proposal = review.review_queue(self.db, limit=5, now=NOW)["items"][0]["proposal_id"]
        review.decide_proposal(self.db, proposal, "validado", reviewer="Ana",
                               reason="conferido", now=NOW)
        pipeline.analyze_versions(self.db, [version], dry_run=False)
        self.assertEqual(review.proposal_detail(self.db, proposal)["proposal"]["state"],
                         "validado")
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM revisoes_campo")
                             .fetchone()[0], 1)


class CoverageTest(PipelineBase):
    def test_categorias_sao_exclusivas_e_explicitas(self):
        # concurso sem documento
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO concursos_identidade (id,created_at) "
                         "VALUES ('vazio','2026-10-01T00:00:00+00:00')")
        # concurso com documento sem texto
        blank = self.document("https://anexos-r2.selecao.net.br/uploads/1/j.pdf", "Digitalizado")
        self.version(blank, blank_pdf())
        # concurso com texto e propostas (o mesmo concurso 'c')
        rich = self.document("https://anexos-r2.selecao.net.br/uploads/1/k.pdf", "Edital")
        version = self.version(rich, text_pdf(["10 vagas imediatas"]))
        pipeline.analyze_versions(self.db, [version], dry_run=False)
        coverage = pipeline.contest_coverage(self.db)
        self.assertEqual(coverage["concursos"], 2)
        self.assertEqual(coverage["por_categoria"]["sem_documento"], 1)
        self.assertEqual(coverage["por_categoria"]["campo_candidato"], 1)

    def test_resumo_tem_denominadores(self):
        summary = pipeline.pipeline_summary(self.db)
        self.assertEqual(summary["concursos"], 1)
        self.assertEqual(summary["documentos"], 0)
        self.assertIsNone(summary["cobertura"]["documentos_com_texto_pct"])
        self.assertEqual(summary["campos_confirmados"], 0)
        self.assertEqual(summary["revisoes_humanas"], 0)

    def test_proposta_nao_vira_confirmado(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/l.pdf", "Edital")
        version = self.version(doc, text_pdf(["10 vagas imediatas"]))
        pipeline.analyze_versions(self.db, [version], dry_run=False)
        summary = pipeline.pipeline_summary(self.db)
        self.assertGreater(summary["propostas"], 0)
        self.assertEqual(summary["campos_confirmados"], 0)


class DuplicateTest(PipelineBase):
    def test_analise_nao_duplica_proposta_identica(self):
        from radar.document_fields import extract_field_proposals
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/n.pdf", "Edital")
        version = self.version(doc, text_pdf(["10 vagas imediatas"]))
        texto = "10 vagas imediatas"
        blocks = [dict(text=texto, start_offset=0, end_offset=len(texto),
                       page_number=1, locator="página 1")]
        proposal = dict(contest_id="c", role_id=None, field_name="immediate_vacancies",
                        value_json="10", value_type="integer", extraction_method="regex",
                        evidence=dict(block_index=0, quote=texto,
                                      start_offset=0, end_offset=len(texto)))
        record_analysis(self.db, version, blocks, [proposal, dict(proposal)])
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM propostas_campo").fetchone()[0], 1)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM evidencias").fetchone()[0], 1)

    def test_relatorio_de_duplicidades_e_somente_leitura(self):
        from radar import review
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/o.pdf", "Edital")
        version = self.version(doc, text_pdf(["10 vagas imediatas"]))
        pipeline.analyze_versions(self.db, [version], dry_run=False)
        with closing(connect_documents(self.db)) as conn:
            before = conn.execute("SELECT COUNT(*) FROM propostas_campo").fetchone()[0]
        report = pipeline.duplicate_report(self.db)
        self.assertEqual(report["grupos"], 0)
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM propostas_campo")
                             .fetchone()[0], before)
        self.assertEqual(report["documentos_url_repetida"], 0)


class OCRTest(PipelineBase):
    def test_pdf_em_branco_precisa_de_ocr(self):
        from radar import ocr
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/p.pdf", "Digitalizado")
        version = self.version(doc, blank_pdf(2))
        need = ocr.detect_need(self.db, version)
        self.assertTrue(need["needs_ocr"])
        self.assertEqual(need["reason"], "sem_texto_sem_imagem")
        self.assertEqual(need["pages"], 2)
        self.assertEqual(need["text_chars"], 0)

    def test_pdf_textual_nao_precisa_de_ocr(self):
        from radar import ocr
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/q.pdf", "Edital")
        version = self.version(doc, text_pdf([
            "Edital de abertura numero 1 de 2026",
            "Abertura de inscricoes para o cargo de Analista Judiciario",
            "com 10 vagas imediatas e cadastro de reserva",
        ]))
        need = ocr.detect_need(self.db, version)
        self.assertFalse(need["needs_ocr"])
        self.assertEqual(need["reason"], "texto_suficiente")

    def test_relatorio_declara_motor_indisponivel_sem_executar(self):
        from radar import ocr
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/r.pdf", "Digitalizado")
        self.version(doc, blank_pdf(1))
        report = ocr.ocr_report(self.db)
        self.assertEqual(report["precisam_ocr"], 1)
        self.assertIn("motor", report)
        self.assertFalse(report["motor"]["motor_disponivel"])
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM blocos_documento")
                             .fetchone()[0], 0)

    def test_sem_inspetor_nao_afirma_que_nao_precisa(self):
        from unittest.mock import patch
        from radar import ocr
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/u.pdf", "Digitalizado")
        version = self.version(doc, blank_pdf(2))
        with patch.dict("sys.modules", {"pymupdf": None}):
            need = ocr.detect_need(self.db, version)
        self.assertIsNone(need["needs_ocr"])
        self.assertIn(need["reason"], ("inspecao_indisponivel", "texto_suficiente"))

    def test_relatorio_nao_esconde_sem_texto_confirmado(self):
        from unittest.mock import patch
        from radar import ocr
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/v.pdf", "Digitalizado")
        version = self.version(doc, blank_pdf(1))
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute("UPDATE versoes_documento SET extraction_state='falhou', "
                         "error_code='pdf_sem_texto' WHERE id=?", (version,))
        with patch.dict("sys.modules", {"pymupdf": None}):
            report = ocr.ocr_report(self.db)
        self.assertEqual(report["precisam_ocr"], 1)
        self.assertEqual(report["itens"][0]["reason"], "sem_texto_confirmado_na_extracao")

    def test_ocr_recusa_sem_motor(self):
        from radar import ocr
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/s.pdf", "Digitalizado")
        version = self.version(doc, blank_pdf(1))
        if ocr.availability()["motor_disponivel"]:  # pragma: no cover - máquina com OCR
            self.skipTest("motor de OCR instalado nesta máquina")
        with self.assertRaisesRegex(ValueError, "ocr_indisponivel"):
            ocr.ocr_version(self.db, version)


class PipelineApiTest(PipelineBase):
    def setUp(self):
        super().setUp()
        self.server = create_server(self.db, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, path):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1],
                                            timeout=5)
        try:
            client.request("GET", path)
            response = client.getresponse()
            return response.status, response.read()
        finally:
            client.close()

    def test_resumo(self):
        status, body = self.request("/api/pipeline")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["concursos"], 1)
        self.assertIn("cobertura", payload)

    def test_cobertura(self):
        status, body = self.request("/api/pipeline/cobertura?limit=10")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["concursos"], 1)

    def test_documentos(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/m.pdf", "Edital")
        status, body = self.request("/api/pipeline/documentos?contest_id=c")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["itens"][0]["document_id"], doc)

    def test_ocr_route(self):
        status, body = self.request("/api/pipeline/ocr?limit=5")
        self.assertEqual(status, 200)
        self.assertIn("motor", json.loads(body))

    def test_duplicidades_route(self):
        status, body = self.request("/api/pipeline/duplicidades")
        self.assertEqual(status, 200)
        self.assertIn("grupos", json.loads(body))

    def test_parametros_invalidos(self):
        self.assertEqual(self.request("/api/pipeline?x=1")[0], 400)
        self.assertEqual(self.request("/api/pipeline/cobertura?x=1")[0], 400)
        self.assertEqual(self.request("/api/pipeline/documentos?x=1")[0], 400)

    def test_contrato_v1_intacto(self):
        from radar.storage import CONTRACT_FIELDS
        self.assertEqual(len(CONTRACT_FIELDS), 18)
        self.assertEqual(json.loads(self.request("/api/concursos")[1]), [])


if __name__ == "__main__":
    unittest.main()
