"""Fase 31: OCR opcional, quadro agregado, requisitos inline e duplicidades."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter
from radar import inline_requirements, ocr, review, vacancy_aggregate, vacancy_tables
from radar.document_store import (connect_documents, migrate_document_schema, record_analysis,
                                  record_version, register_document)

NOW = "2026-10-17T12:00:00Z"
LABEL = "cargo do documento não reconciliado: "


def text_pdf(lines: list[str]) -> bytes:
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


def blank_pdf(pages: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


IBFC_QUADRO = (
    "Página 23 de 29 ANEXO I – QUADRO DE VAGAS Função Temporária Núcleo Territorial de "
    "Educação - NTE Total de Vagas (Ampla, Negros e PCD)* Professor Orientador de Estágio "
    "em Saúde - Enfermagem 01 – Sede: Irecê 06 02- Sede: Bom Jesus da Lapa 06 "
    "26 - Sede: Salvador 40 Professor Orientador de Estágio em Saúde - Radiologia "
    "26 - Sede: Salvador 06 TOTAL 228 (*) Total de vagas incluindo as reservadas para "
    "candidatos com deficiência e a reserva de vagas para negros."
)


class Base(unittest.TestCase):
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

    def document(self, url, title="Edital"):
        return register_document(self.db, dict(
            observation_id="o", kind="edital", official_url=url, title=title,
            discovery_url="https://anexos-r2.selecao.net.br/uploads/1/",
            discovery_method="automatico", discovered_at=NOW, published_at="2026-10-01",
            tipo_documental="edital_abertura", issuer="IBFC",
            source_identifier=f"ibfc-1:{url.rsplit('/', 1)[-1]}"))

    def version(self, document_id, body, content_type="application/pdf"):
        return record_version(self.db, document_id, body, dict(
            fetched_at=NOW, fetched_url=f"https://x/{document_id}.pdf",
            content_type=content_type))


class VacancyAggregateTest(unittest.TestCase):
    def blocks(self, text):
        return [dict(page_number=23, locator="página 23", start_offset=0,
                     end_offset=len(text), text=text)]

    def test_total_agregado_nao_vira_vagas_imediatas(self):
        proposals = vacancy_aggregate.parse_aggregate_table(
            self.blocks(IBFC_QUADRO), "c", label_prefix=LABEL)
        fields = {p["field_name"] for p in proposals}
        self.assertEqual(fields, {"vagas_total_publicado"})
        for forbidden in ("immediate_vacancies", "indigenous_vacancies",
                          "indigenous_reserve_vacancies", "reserve_vacancies"):
            self.assertNotIn(forbidden, fields)
        valores = [json.loads(p["value_json"]) for p in proposals]
        self.assertIn(228, valores)  # total do quadro

    def test_cabecalhos_agregados_alternativos_nao_viram_modalidade(self):
        for header in ("VAGAS TOTAIS (AMPLA, NEGROS E PCD)", "VAGAS (AMPLA, NEGROS E PCD)",
                       "QUANTIDADE DE VAGAS (AMPLA, NEGROS, PCD E INDIGENAS)"):
            self.assertIsNone(vacancy_tables._field_for(header), header)

    def test_separador_de_milhar(self):
        text = ("ANEXO I QUADRO DE VAGAS Total de Vagas (Ampla, Negros e PCD) "
                "Professor de Ciencias 01 - Sede: Irece 1.500 TOTAL 1.500")
        proposals = vacancy_aggregate.parse_aggregate_table(
            self.blocks(text), "c", label_prefix=LABEL)
        valores = [json.loads(p["value_json"]) for p in proposals]
        self.assertEqual(valores, [1500, 1500])

    def test_quadro_por_regiao_sem_cargo_nao_inventa_cargo(self):
        # Layout "NTE 01 - SEDE: X 84" seguido de municípios: o cargo não está na tabela.
        text = ("ANEXO I QUADRO DE VAGAS Município Total de Vagas (Ampla, Negros e PCD) "
                "NTE 01 - SEDE: IRECE 84 NTE 01 - SEDE: IRECE AMERICA DOURADA 3 "
                "BARRA DO MENDES 4 BARRO ALTO 2 TOTAL 90")
        proposals = vacancy_aggregate.parse_aggregate_table(
            self.blocks(text), "c", label_prefix=LABEL)
        # Nenhuma linha vira proposta (cargo desconhecido); só o TOTAL do quadro é extraível.
        for proposal in proposals:
            self.assertTrue(proposal["evidence"]["quote"].upper().startswith("TOTAL"))
            self.assertIn("total do quadro", proposal["ambiguity_reason"])

    def test_nao_usa_linha_de_outra_tabela(self):
        text = ("ANEXO I QUADRO DE VAGAS Total de Vagas (Ampla, Negros e PCD) "
                "Professor de Ciencias 01 - Sede: Irece 40 TOTAL 40 "
                "ANEXO II Outra tabela 02 - Sede: Feira 12 TOTAL 12")
        proposals = vacancy_aggregate.parse_aggregate_table(
            self.blocks(text), "c", label_prefix=LABEL)
        valores = [json.loads(p["value_json"]) for p in proposals]
        self.assertEqual(valores, [40, 40])

    def test_nao_distribui_por_percentual(self):
        proposals = vacancy_aggregate.parse_aggregate_table(
            self.blocks(IBFC_QUADRO), "c", label_prefix=LABEL)
        # Fixture com 4 linhas + total; nenhuma quantidade fracionária ou de percentual.
        self.assertEqual(len(proposals), 5)
        self.assertTrue(all(isinstance(json.loads(p["value_json"]), int) for p in proposals))

    def test_motivo_declara_agregado_e_nota(self):
        proposals = vacancy_aggregate.parse_aggregate_table(
            self.blocks(IBFC_QUADRO), "c", label_prefix=LABEL)
        reason = proposals[0]["ambiguity_reason"]
        self.assertIn("total agregado publicado", reason)
        self.assertIn("nota do edital", reason)
        self.assertIn("Enfermagem", reason)

    def test_evidencia_e_trecho_literal(self):
        proposals = vacancy_aggregate.parse_aggregate_table(
            self.blocks(IBFC_QUADRO), "c", label_prefix=LABEL)
        for proposal in proposals:
            evidence = proposal["evidence"]
            self.assertEqual(
                IBFC_QUADRO[evidence["start_offset"]:evidence["end_offset"]],
                evidence["quote"])

    def test_conflito_entre_soma_e_total(self):
        text = IBFC_QUADRO.replace("TOTAL 228", "TOTAL 300")
        proposals = vacancy_aggregate.parse_aggregate_table(
            self.blocks(text), "c", label_prefix=LABEL)
        self.assertTrue(any("conflito" in (p["ambiguity_reason"] or "") for p in proposals))

    def test_cabecalho_com_uma_modalidade_nao_e_agregado(self):
        text = IBFC_QUADRO.replace("(Ampla, Negros e PCD)", "(Ampla)")
        self.assertEqual(vacancy_aggregate.parse_aggregate_table(
            self.blocks(text), "c", label_prefix=LABEL), [])

    def test_tabela_sem_total_nao_inventa_total(self):
        text = IBFC_QUADRO.replace("TOTAL 228", "")
        proposals = vacancy_aggregate.parse_aggregate_table(
            self.blocks(text), "c", label_prefix=LABEL)
        valores = [json.loads(p["value_json"]) for p in proposals]
        self.assertNotIn(228, valores)

    def test_resumo_do_quadro(self):
        summary = vacancy_aggregate.aggregate_summary(self.blocks(IBFC_QUADRO))
        self.assertTrue(summary["agregado"])
        self.assertEqual(summary["total_publicado"], 228)
        # O fixture abrevia as linhas: a soma (58) difere do TOTAL publicado (228), e o
        # parser precisa declarar o conflito em vez de "consertar" o número.
        self.assertEqual(summary["soma"], 58)
        self.assertEqual(summary["linhas"], 4)

    def test_guard_do_extrator_generico(self):
        self.assertIsNone(vacancy_tables._field_for("TOTAL DE VAGAS (AMPLA, NEGROS E PCD)*"))
        self.assertEqual(vacancy_tables._field_for("VAGAS IMEDIATAS"),
                         "immediate_vacancies")
        self.assertEqual(vacancy_tables._field_for("CADASTRO DE RESERVA"),
                         "reserve_vacancies")


class InlineRequirementsTest(unittest.TestCase):
    TEXT = (
        "2.6.2. PROFESSOR ORIENTADOR DE ESTÁGIO EM SAÚDE PARA ATUAÇÃO NO CURSO DE "
        "RADIOLOGIA Requisito: Diploma devidamente registrado, de conclusão de curso de "
        "nível superior em Enfermagem, em instituição reconhecida pelo Ministério da "
        "Educação – MEC. Atribuições: executar atividades."
    )

    def test_extrai_education_e_curso(self):
        proposals = inline_requirements.extract_inline_requirements(
            [dict(page_number=3, text=self.TEXT)], "c", label_prefix=LABEL)
        education = [p for p in proposals if p["field_name"] == "education"]
        courses = [p for p in proposals if p["field_name"] == "accepted_courses"]
        self.assertEqual(len(education), 1)
        self.assertEqual(json.loads(courses[0]["value_json"]), "Enfermagem")
        self.assertIn("RADIOLOGIA", education[0]["ambiguity_reason"])
        self.assertIn("Enfermagem", json.loads(education[0]["value_json"]))

    def test_nao_captura_atribuicoes(self):
        proposals = inline_requirements.extract_inline_requirements(
            [dict(page_number=3, text=self.TEXT)], "c", label_prefix=LABEL)
        value = json.loads(proposals[0]["value_json"])
        self.assertNotIn("Atribui", value)

    def test_si_compatibility_e_candidata(self):
        proposals = inline_requirements.extract_inline_requirements(
            [dict(page_number=3, text=self.TEXT)], "c", label_prefix=LABEL)
        si = [p for p in proposals if p["field_name"] == "si_compatibility"]
        self.assertEqual(len(si), 1)
        self.assertIn(json.loads(si[0]["value_json"]),
                      ("incompativel_com_requisito_explicito", "ambiguo",
                       "compativel_com_area_correlata"))
        self.assertTrue(si[0]["ambiguity_reason"])

    def test_si_explicito_quando_citado(self):
        text = ("PROFESSOR DE INFORMÁTICA Requisito: Diploma de curso superior em "
                "Sistemas de Informação ou áreas correlatas, reconhecido pelo MEC.")
        proposals = inline_requirements.extract_inline_requirements(
            [dict(page_number=4, text=text)], "c", label_prefix=LABEL)
        si = [json.loads(p["value_json"]) for p in proposals
              if p["field_name"] == "si_compatibility"]
        self.assertTrue(si)
        self.assertNotEqual(si[0], "incompativel_com_requisito_explicito")

    def test_cargo_de_outro_bloco_nao_e_associado(self):
        blocks = [dict(page_number=3, text="CARGO TOTALMENTE DIFERENTE AQUI"),
                  dict(page_number=4, text="Requisito: Diploma de nível superior em Direito "
                                           "expedido por instituição reconhecida.")]
        proposals = inline_requirements.extract_inline_requirements(
            blocks, "c", label_prefix=LABEL)
        self.assertIn("sem cargo identificado", proposals[0]["ambiguity_reason"])

    def test_requisito_nao_educacional_nao_vira_education(self):
        for text in ("Requisito: CNH categoria B e veiculo proprio.",
                     "Requisito: Registro ativo no COREN com anuidade em dia.",
                     "Requisito: Experiencia minima de 6 meses na funcao."):
            proposals = inline_requirements.extract_inline_requirements(
                [dict(page_number=1, text="CARGO DE PROFESSOR SUBSTITUTO " + text)],
                "c", label_prefix=LABEL)
            self.assertEqual(proposals, [], text)

    def test_anexo_ii_nao_e_reprocessado_pelo_inline(self):
        text = ("CARGO DE PROFESSOR SUBSTITUTO a) Requisitos: Diploma de curso superior "
                "em qualquer area do conhecimento.")
        self.assertEqual(inline_requirements.extract_inline_requirements(
            [dict(page_number=2, text=text)], "c", label_prefix=LABEL), [])

    def test_sem_requisito_nao_emite(self):
        self.assertEqual(inline_requirements.extract_inline_requirements(
            [dict(page_number=1, text="Texto sem requisito algum.")], "c",
            label_prefix=LABEL), [])


class OcrTest(Base):
    def test_diagnostico_de_texto_vetorial(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/vet.pdf", "Vetorial")
        version = self.version(doc, text_pdf([
            "EDITAL DE ABERTURA NUMERO 1 DE 2026 PARA PROVIMENTO DE CARGOS",
            "Abertura de inscricoes com 10 vagas imediatas e cadastro de reserva",
        ]))
        need = ocr.detect_need(self.db, version)
        self.assertFalse(need["needs_ocr"])  # este fixture tem fonte e texto
        self.assertEqual(need["reason"], "texto_suficiente")
        self.assertGreater(need["fonts"], 0)

    def test_pdf_em_branco_precisa_de_ocr(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/scan.pdf", "Scan")
        version = self.version(doc, blank_pdf(2))
        need = ocr.detect_need(self.db, version)
        self.assertTrue(need["needs_ocr"])
        self.assertEqual(need["reason"], "sem_texto_sem_imagem")
        self.assertEqual(need["fonts"], 0)

    def test_dry_run_nao_grava_nada(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/dry.pdf", "Scan")
        version = self.version(doc, blank_pdf(1))
        plan = ocr.ocr_version(self.db, version, pages=[1], apply=False)
        self.assertFalse(plan["apply"])
        self.assertIn("motor_disponivel", plan)
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM blocos_documento")
                             .fetchone()[0], 0)

    def test_motor_ausente_nao_tem_efeito_colateral(self):
        from unittest.mock import patch
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/nomotor.pdf", "Scan")
        version = self.version(doc, blank_pdf(1))
        with patch.object(ocr, "availability", return_value={
                "version": ocr.OCR_VERSION, "pymupdf": True, "engines": {},
                "motor_escolhido": None, "motor_disponivel": False, "limites": {},
                "limitacao": ""}):
            with self.assertRaises(ocr.OcrError) as ctx:
                ocr.ocr_version(self.db, version, apply=True)
        self.assertEqual(ctx.exception.code, "ocr_indisponivel")
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM blocos_documento")
                             .fetchone()[0], 0)

    def test_modelo_ausente(self):
        from unittest.mock import patch
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/nomodel.pdf", "Scan")
        version = self.version(doc, blank_pdf(1))
        with patch.object(ocr, "availability", return_value={
                "version": ocr.OCR_VERSION, "pymupdf": True,
                "engines": {"windows_ocr": {"disponivel": False, "idiomas": [],
                                            "motivo": "modelo pt-BR ausente"}},
                "motor_escolhido": None, "motor_disponivel": False, "limites": {},
                "limitacao": ""}):
            with self.assertRaises(ocr.OcrError) as ctx:
                ocr.ocr_version(self.db, version, apply=True)
        self.assertEqual(ctx.exception.code, "ocr_indisponivel")

    def test_parametros_invalidos(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/p.pdf", "Scan")
        version = self.version(doc, blank_pdf(1))
        with self.assertRaises(ocr.OcrError):
            ocr.ocr_version(self.db, version, dpi=10, apply=False)
        with self.assertRaises(ocr.OcrError):
            ocr.ocr_version(self.db, version, pages=[9], apply=False)
        with self.assertRaises(ocr.OcrError):
            ocr.ocr_version(self.db, version, pages=list(range(1, 30)), apply=False)

    def test_timeout_e_limite_declarados(self):
        info = ocr.availability()
        self.assertIn("limites", info)
        self.assertGreater(info["limites"]["paginas_por_chamada"], 0)
        self.assertLessEqual(info["limites"]["dpi_maximo"], ocr.MAX_DPI)

    def test_ocr_e_uma_chamada_por_versao(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/once.pdf", "Scan")
        version = self.version(doc, blank_pdf(1))
        from unittest.mock import patch

        def fake_render(document, index, dpi, target):
            target.write_bytes(b"png")
            return 100, 100

        with patch.object(ocr, "_resolve_engine", return_value=(
                "windows_ocr", "pt-BR", {"motor_disponivel": True})):
            with patch.object(ocr, "_render_page", side_effect=fake_render), \
                    patch.object(ocr, "_recognize", return_value=("texto reconhecido", 5)):
                ocr.ocr_version(self.db, version, pages=[1], apply=True)
                with self.assertRaises(ocr.OcrError) as ctx:
                    ocr.ocr_version(self.db, version, pages=[1], apply=True)
        self.assertEqual(ctx.exception.code, "ocr_versao_ja_analisada")

    def test_relatorio_nao_executa(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/rep.pdf", "Scan")
        self.version(doc, blank_pdf(1))
        report = ocr.ocr_report(self.db)
        self.assertEqual(report["precisam_ocr"], 1)
        self.assertIn("motor", report)
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM blocos_documento")
                             .fetchone()[0], 0)


class DuplicateGroupTest(Base):
    def _proposal(self, version, blocks, proposals):
        record_analysis(self.db, version, blocks, proposals)

    def test_duplicidade_no_mesmo_span(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/d1.pdf")
        version = self.version(doc, text_pdf(["10 vagas"]))
        texto = "10 vagas"
        blocks = [dict(page_number=1, locator="página 1", start_offset=0,
                       end_offset=len(texto), text=texto)]
        base = dict(contest_id="c", role_id=None, field_name="immediate_vacancies",
                    value_json="10", value_type="integer", extraction_method="regex",
                    evidence=dict(block_index=0, quote=texto, start_offset=0,
                                  end_offset=len(texto)))
        # record_analysis deduplica na escrita; inserimos direto para simular histórico.
        self._proposal(version, blocks, [base])
        with closing(connect_documents(self.db)) as conn, conn:
            row = conn.execute("SELECT id, evidence_id FROM propostas_campo").fetchone()
            conn.execute("INSERT INTO propostas_campo VALUES ('dup','c',NULL,"
                         "'immediate_vacancies','10','integer',?,'regex',NULL,?)",
                         (row[1], NOW))
        report = review.duplicate_groups(self.db)
        self.assertEqual(report["total"], 1)
        self.assertEqual(report["excedentes"], 1)
        self.assertIn(report["itens"][0]["representante"], (row[0], "dup"))
        self.assertEqual(len(report["itens"][0]["membros"]), 2)

    def test_mesmo_valor_em_spans_diferentes_e_repeticao_legitima(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/d2.pdf")
        version = self.version(doc, text_pdf(["10 vagas", "10 vagas"]))
        texto = "10 vagas 10 vagas"
        blocks = [dict(page_number=1, locator="página 1", start_offset=0,
                       end_offset=len(texto), text=texto)]
        proposals = [
            dict(contest_id="c", role_id=None, field_name="immediate_vacancies",
                 value_json="10", value_type="integer", extraction_method="regex",
                 evidence=dict(block_index=0, quote="10 vagas", start_offset=0,
                               end_offset=8)),
            dict(contest_id="c", role_id=None, field_name="immediate_vacancies",
                 value_json="10", value_type="integer", extraction_method="regex",
                 evidence=dict(block_index=0, quote="10 vagas", start_offset=9,
                               end_offset=17)),
        ]
        record_analysis(self.db, version, blocks, proposals)
        report = review.duplicate_groups(self.db)
        self.assertEqual(report["total"], 0)
        self.assertEqual(report["repeticao_legitima"], 1)

    def test_relatorio_nao_apaga(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/d3.pdf")
        version = self.version(doc, text_pdf(["10 vagas"]))
        texto = "10 vagas"
        blocks = [dict(page_number=1, locator="página 1", start_offset=0,
                       end_offset=len(texto), text=texto)]
        record_analysis(self.db, version, blocks, [dict(
            contest_id="c", role_id=None, field_name="immediate_vacancies",
            value_json="10", value_type="integer", extraction_method="regex",
            evidence=dict(block_index=0, quote=texto, start_offset=0,
                          end_offset=len(texto)))])
        with closing(connect_documents(self.db)) as conn:
            before = conn.execute("SELECT COUNT(*) FROM propostas_campo").fetchone()[0]
        review.duplicate_groups(self.db)
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM propostas_campo")
                             .fetchone()[0], before)


class PriorityTest(Base):
    def test_vaga_indigena_e_formacao_elevam_prioridade(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/pr.pdf")
        version = self.version(doc, text_pdf(["10 vagas"]))
        texto = "10 vagas"
        blocks = [dict(page_number=1, locator="página 1", start_offset=0,
                       end_offset=len(texto), text=texto)]
        record_analysis(self.db, version, blocks, [
            dict(contest_id="c", role_id=None, field_name="indigenous_vacancies",
                 value_json="1", value_type="integer", extraction_method="regex",
                 evidence=dict(block_index=0, quote=texto, start_offset=0, end_offset=8)),
            dict(contest_id="c", role_id=None, field_name="si_compatibility",
                 value_json='"ambiguo"', value_type="string", extraction_method="manual",
                 evidence=dict(block_index=0, quote=texto, start_offset=0, end_offset=8)),
        ])
        queue = review.review_queue(self.db, limit=10, now=NOW)
        factors = {item["field_name"]: {f["fator"] for f in item["factors"]}
                   for item in queue["items"]}
        self.assertIn("vaga_indigena", factors["indigenous_vacancies"])
        self.assertIn("formacao_si", factors["si_compatibility"])

    def test_duplicata_recebe_fator_proprio(self):
        doc = self.document("https://anexos-r2.selecao.net.br/uploads/1/pr2.pdf")
        version = self.version(doc, text_pdf(["10 vagas"]))
        texto = "10 vagas"
        blocks = [dict(page_number=1, locator="página 1", start_offset=0,
                       end_offset=len(texto), text=texto)]
        record_analysis(self.db, version, blocks, [dict(
            contest_id="c", role_id=None, field_name="immediate_vacancies",
            value_json="10", value_type="integer", extraction_method="regex",
            evidence=dict(block_index=0, quote=texto, start_offset=0, end_offset=8))])
        with closing(connect_documents(self.db)) as conn, conn:
            evidence = conn.execute("SELECT evidence_id FROM propostas_campo").fetchone()[0]
            conn.execute("INSERT INTO propostas_campo VALUES ('dup2','c',NULL,"
                         "'immediate_vacancies','10','integer',?,'regex',NULL,?)",
                         (evidence, NOW))
        queue = review.review_queue(self.db, limit=10, now=NOW)
        self.assertTrue(any("duplicata" in {f["fator"] for f in item["factors"]}
                            for item in queue["items"]))


if __name__ == "__main__":
    unittest.main()
