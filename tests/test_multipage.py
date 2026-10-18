"""Reconstrução multipágina, escopo regional e lotes de páginas (Fase 32)."""

import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

from radar import page_batches, regional_scope, table_continuity
from radar.document_store import (connect_documents, migrate_document_schema, record_analysis,
                                  record_version, register_document)
from radar.server import create_server

NOW = "2026-10-17T12:00:00+00:00"


def text_pdf(lines: list[str]) -> bytes:
    """PDF textual mínimo (uma página) — mesmo formato usado nos demais testes."""
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


def multipage_pdf(lines_per_page: list[list[str]]) -> bytes:
    """PDF textual com uma página por lista de linhas (objetos numerados corretamente)."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None,
               "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    page_ids = []
    for index, lines in enumerate(lines_per_page):
        content_id = 4 + index * 2
        page_id = content_id + 1
        stream = "BT /F1 10 Tf 40 780 Td " + " ".join(
            f"({line}) Tj 0 -14 Td" for line in lines) + " ET"
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                       f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>")
        page_ids.append(page_id)
    objects[1] = ("<< /Type /Pages /Kids [" + " ".join(f"{pid} 0 R" for pid in page_ids)
                  + f"] /Count {len(page_ids)} >>")
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


def blocks_from(pages: list[str]) -> list[dict]:
    return [dict(page_number=index, locator=f"página {index}", start_offset=0,
                 end_offset=len(text), text=text)
            for index, text in enumerate(pages, 1)]


TABLE_PAGES = [
    "Edital de Abertura. Função temporária de Técnico de Nível Médio, para a Secretaria "
    "de Educação. TOTAL DE VAGAS (ampla concorrência e reservas) por NTE. "
    "NTE 01 - SEDE: IRECÊ 84 NTE 01 - SEDE: IRECÊ AMERICA DOURADA 3 BARRA DO MENDES 4",
    "NTE 01 - SEDE: IRECÊ IRECÊ 77 NTE 02 - SEDE: BOM JESUS LAPA 94 NTE 02 - SEDE: BOM "
    "JESUS LAPA BARRA 10 BOM JESUS DA LAPA 84 NÚCLEO 06 - VALENÇA 34 NÚCLEO 06 - VALENÇA "
    "ARATUIPE 1 CAIRU 33",
    "TOTAL 212 (*) Total de vagas incluindo as reservadas. Lei Estadual nº 6.677 de "
    "26/09/1994.",
]


class ContinuityTest(unittest.TestCase):
    def test_quadro_atravessa_paginas_e_fecha_com_total(self):
        report = table_continuity.continuity_report(blocks_from(TABLE_PAGES))
        table = report["tabelas"][0]
        self.assertEqual(table["header_page"], 1)
        self.assertEqual(table["total_page"], 3)
        self.assertEqual(table["total"], 212)
        self.assertEqual(table["soma_linhas"], 212)
        self.assertIn(table["certeza"], {"forte", "provavel"})
        self.assertEqual([row["nte"] for row in table["ntes"]], [1, 2, 6])

    def test_subcabecalho_repetido_nao_engole_municipio(self):
        table = table_continuity.analyze_tables(blocks_from(TABLE_PAGES))[0]
        nte6 = next(row for row in table["ntes"] if row["nte"] == 6)
        self.assertEqual(nte6["total"], 34)
        self.assertEqual(nte6["sede"], "VALENÇA")

    def test_total_do_quadro_nao_inclui_numeros_de_lei(self):
        table = table_continuity.analyze_tables(blocks_from(TABLE_PAGES))[0]
        self.assertEqual(table["total"], 212)
        self.assertEqual(table["soma_linhas"], 212)

    def test_relatorio_so_multipagina(self):
        single = blocks_from(["NTE 01 - SEDE: IRECÊ 84 TOTAL 84"])
        self.assertEqual(table_continuity.continuity_report(
            single, only_multi_page=True)["total"], 0)


class RegionalScopeTest(unittest.TestCase):
    def test_cargo_do_escopo_vem_do_texto_do_edital(self):
        candidates = regional_scope.cargo_candidates(blocks_from(TABLE_PAGES))
        self.assertEqual([item["cargo"] for item in candidates], ["Técnico de Nível Médio"])
        self.assertEqual(candidates[0]["page"], 1)
        self.assertIn("função temporária de", candidates[0]["quote"].lower())

    def test_mencao_fraca_nao_disputa_com_cargo_do_escopo(self):
        blocks = blocks_from(["Função de jurado é considerada atividade jurídica. "
                              "Função temporária de Professor de Educação Básica."])
        candidates = regional_scope.cargo_candidates(blocks)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["cargo"], "Professor de Educação Básica")
        self.assertEqual(candidates[0]["forca"], "forte")

    def test_mais_de_um_cargo_torna_escopo_ambiguo(self):
        blocks = blocks_from(["Função temporária de Professor. "
                              "Função temporária de Coordenador Pedagógico."])
        candidates = regional_scope.cargo_candidates(blocks)
        certeza, ambiguidades = regional_scope.scope_certainty(candidates)
        self.assertEqual(certeza, "ambiguo")
        self.assertTrue(ambiguidades)

    def test_distribuicao_regional_soma_ntes(self):
        report = regional_scope.regional_breakdown(blocks_from(TABLE_PAGES))
        self.assertEqual(report["total_ntes"], 3)
        self.assertEqual(report["soma_ntes"], 212)
        # O nome fala de SOMA: aqui os três NTEs fecham com seus municípios.
        self.assertTrue(report["soma_municipios_confere"])
        self.assertIsNone(report["limitacao_municipios"])

    def test_municipio_que_nao_fecha_fica_diagnostico(self):
        quebrado = [TABLE_PAGES[0],
                    "NTE 01 - SEDE: IRECÊ IRECÊ 77 NTE 02 - SEDE: BOM JESUS LAPA 94 "
                    "NTE 02 - SEDE: BOM JESUS LAPA BARRA 10",
                    "TOTAL 171"]
        report = regional_scope.regional_breakdown(blocks_from(quebrado))
        self.assertFalse(report["soma_municipios_confere"])
        self.assertIsNotNone(report["limitacao_municipios"])
        self.assertIn("diagnóstica", report["limitacao_municipios"])

    def test_dois_quadros_com_nte_ficam_ambiguos(self):
        dois = blocks_from([
            "TOTAL DE VAGAS (ampla) NTE 01 - SEDE: IRECÊ 10 TOTAL 10",
            "TOTAL DE VAGAS (ampla) NTE 02 - SEDE: SEABRA 20 TOTAL 20"])
        report = regional_scope.regional_breakdown(dois)
        self.assertIsNone(report["tabela"])
        self.assertIn("2 quadros", report["ambiguidade"])
        self.assertEqual(report["ntes"], [])

    def scoped(self, report):
        return {"contest_id": "c", "tabela": report["tabela"], "ntes": report["ntes"],
                "total_publicado": report["soma_ntes"], "total_ntes": report["total_ntes"],
                "total_block_index": report["total_block_index"],
                "total_start_offset": report["total_start_offset"],
                "cargo_do_escopo": None}

    def test_proposta_padrao_e_so_o_total_do_quadro(self):
        blocks = blocks_from(TABLE_PAGES)
        report = regional_scope.regional_breakdown(blocks)
        proposals = regional_scope.proposals_from_scope(self.scoped(report))
        self.assertEqual(len(proposals), 1)
        proposal = proposals[0]
        self.assertEqual(proposal["value_json"], "212")
        self.assertIsNone(proposal["role_id"])
        self.assertIn("não distribuir por modalidade", proposal["ambiguity_reason"])
        # A evidência precisa apontar para o bloco e o offset reais do trecho citado.
        evidence = proposal["evidence"]
        block = blocks[evidence["block_index"]]
        self.assertEqual(block["text"][evidence["start_offset"]:evidence["end_offset"]],
                         evidence["quote"])
        self.assertEqual(evidence["quote"], "TOTAL 212")

    def test_ntes_so_com_include_ntes_e_sempre_como_recorte(self):
        blocks = blocks_from(TABLE_PAGES)
        report = regional_scope.regional_breakdown(blocks)
        proposals = regional_scope.proposals_from_scope(self.scoped(report),
                                                        include_ntes=True)
        self.assertEqual(len(proposals), 4)  # 3 NTEs + total
        for proposal in proposals:
            self.assertEqual(proposal["field_name"], "vagas_total_publicado")
            self.assertIsNone(proposal["role_id"])
            evidence = proposal["evidence"]
            block = blocks[evidence["block_index"]]
            self.assertEqual(block["text"][evidence["start_offset"]:evidence["end_offset"]],
                             evidence["quote"])
        for proposal in proposals[:-1]:
            self.assertIn("recorte do NTE", proposal["ambiguity_reason"])
            self.assertIn("não é o total do concurso", proposal["ambiguity_reason"])

    def test_quadro_sem_certeza_suficiente_nao_gera_proposta(self):
        report = regional_scope.regional_breakdown(blocks_from(TABLE_PAGES))
        report["tabela"] = dict(report["tabela"], certeza="ambigua")
        self.assertEqual(regional_scope.proposals_from_scope(self.scoped(report)), [])

    def test_nte_nao_e_municipio_nem_lotacao(self):
        report = regional_scope.regional_breakdown(blocks_from(TABLE_PAGES))
        nte = report["ntes"][0]
        self.assertIn("sede", nte)
        self.assertNotIn("lotacao", nte)
        self.assertTrue(all("municipio" in row for row in nte["municipios"]))


class ClassifyTest(unittest.TestCase):
    def index(self, pages, extracted=0):
        return [{"page": page, "extracted": page <= extracted, "chars": len(text),
                 "util": [name for name, pattern in page_batches._USEFUL.items()
                          if pattern.search(text)],
                 "pessoal": [name for name, pattern in page_batches._PERSONAL.items()
                             if pattern.search(text)]}
                for page, text in enumerate(pages, 1)]

    def test_ato_de_resultado_nao_e_processado(self):
        decision = page_batches._classify(
            self.index(["Nome do candidato: FULANO. Nota 80. Resultado: aprovado."]),
            "Resultado Preliminar da Prova Objetiva")
        self.assertFalse(decision["processar"])
        self.assertEqual(decision["classificacao"], "dados_pessoais_lista_resultado")
        self.assertIn("dados pessoais", decision["justificativa"])

    def test_edital_longo_tem_conteudo_util(self):
        decision = page_batches._classify(
            self.index(["Quadro de vagas para o cargo. Requisitos: diploma. "
                        "Inscrições no cronograma."]),
            "Edital de Abertura nº 010/2026")
        self.assertTrue(decision["processar"])
        self.assertEqual(decision["classificacao"], "conteudo_util")

    def test_sem_marcador_nao_e_processado(self):
        decision = page_batches._classify(self.index(["texto qualquer sem marcador"]),
                                          "Anexo")
        self.assertFalse(decision["processar"])
        self.assertEqual(decision["classificacao"], "sem_conteudo_util")


class PageBatchBase(unittest.TestCase):
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

    def version(self, body, title="Edital de Abertura"):
        document_id = register_document(self.db, dict(
            observation_id="o", kind="edital", official_url="https://x/a.pdf", title=title,
            discovery_url="https://anexos-r2.selecao.net.br/uploads/1/",
            discovery_method="automatico", discovered_at=NOW, published_at="2026-10-01",
            tipo_documental="edital_abertura", issuer="IBFC", source_identifier="ibfc-1:a"))
        return document_id, record_version(self.db, document_id, body, dict(
            fetched_at=NOW, fetched_url="https://x/a.pdf", content_type="application/pdf"))


class PageBatchTest(PageBatchBase):
    def test_lote_seco_nao_grava(self):
        document_id, version_id = self.version(
            multipage_pdf([["página um"], ["página dois"], ["página três"]]))
        record_analysis(self.db, version_id, blocks_from(["página um"]), [])
        report = page_batches.append_pages(self.db, version_id, dry_run=True, max_pages=1)
        self.assertEqual(report["paginas_no_lote"], [2])
        self.assertEqual(report["next_page"], 3)
        self.assertEqual(report["added_blocks"], 0)
        with closing(connect_documents(self.db)) as conn:
            pages = [row[0] for row in conn.execute(
                "SELECT DISTINCT page_number FROM blocos_documento WHERE version_id=?",
                (version_id,))]
        self.assertEqual(pages, [1])

    def test_lote_aplicado_acrescenta_pagina_e_e_idempotente(self):
        document_id, version_id = self.version(
            multipage_pdf([["página um"], ["página dois"], ["página três"]]))
        record_analysis(self.db, version_id, blocks_from(["página um"]), [])
        first = page_batches.append_pages(self.db, version_id, dry_run=False, max_pages=2)
        self.assertEqual(first["added_blocks"], 2)
        self.assertIsNone(first["next_page"])
        second = page_batches.append_pages(self.db, version_id, dry_run=False, max_pages=2)
        self.assertEqual(second["added_blocks"], 0)
        with closing(connect_documents(self.db)) as conn:
            pages = [row[0] for row in conn.execute(
                "SELECT DISTINCT page_number FROM blocos_documento WHERE version_id=? "
                "ORDER BY page_number", (version_id,))]
        self.assertEqual(pages, [1, 2, 3])

    def test_versao_completa_nao_abre_lote(self):
        document_id, version_id = self.version(multipage_pdf([["página um"]]))
        record_analysis(self.db, version_id, blocks_from(["página um"]), [])
        report = page_batches.append_pages(self.db, version_id, dry_run=False)
        self.assertEqual(report["paginas_no_lote"], [])
        self.assertIsNone(report["start_page"])
        self.assertIn("todas as páginas", report["motivo"])

    def test_checkpoint_guarda_proxima_pagina(self):
        document_id, version_id = self.version(
            multipage_pdf([["página um"], ["página dois"], ["página três"]]))
        record_analysis(self.db, version_id, blocks_from(["página um"]), [])
        checkpoint = Path(self.tmp.name) / "lote.json"
        page_batches.append_pages(self.db, version_id, dry_run=False, max_pages=1,
                                  checkpoint=str(checkpoint))
        data = json.loads(checkpoint.read_text(encoding="utf-8"))
        self.assertEqual(data["version_id"], version_id)
        self.assertEqual(data["next_page"], 3)

    def test_indice_de_paginas_so_amostra_nao_lidas(self):
        document_id, version_id = self.version(
            multipage_pdf([["página um"], ["Quadro de vagas"], ["Resultado"]]))
        record_analysis(self.db, version_id, blocks_from(["página um"]), [])
        index = page_batches.page_index(self.db, version_id)
        self.assertEqual([item["page"] for item in index["paginas"]], [2, 3])
        self.assertFalse(any(item["extracted"] for item in index["paginas"]))


class AppendEvidenceTest(PageBatchBase):
    def three_pages(self):
        document_id, version_id = self.version(
            multipage_pdf([["página um"], ["página dois"], ["página três TOTAL 10"]]))
        record_analysis(self.db, version_id, blocks_from(["página um"]), [])
        return version_id

    def block(self, page, text):
        return dict(page_number=page, locator=f"página {page}", start_offset=0,
                    end_offset=len(text), text=text)

    def proposal(self, index, quote, value="10"):
        return {"contest_id": "c", "role_id": None, "field_name": "vagas_total_publicado",
                "value_json": value, "value_type": "integer",
                "extraction_method": "teste",
                "evidence": {"block_index": index, "quote": quote, "start_offset": 0,
                             "end_offset": len(quote)}}

    def test_remapeamento_aponta_para_a_pagina_nova(self):
        version_id = self.three_pages()
        from radar.document_store import append_page_analysis
        blocks = [self.block(2, "página dois"), self.block(3, "página três TOTAL 10")]
        report = append_page_analysis(self.db, version_id, blocks,
                                      [self.proposal(1, "página três TOTAL 10")])
        self.assertEqual(report["added_proposals"], 1)
        with closing(connect_documents(self.db)) as conn:
            page = conn.execute(
                "SELECT e.page_number FROM propostas_campo p "
                "JOIN evidencias e ON e.id=p.evidence_id WHERE p.contest_id='c'"
            ).fetchone()[0]
        self.assertEqual(page, 3)

    def test_proposta_de_pagina_pulada_e_contabilizada(self):
        version_id = self.three_pages()
        from radar.document_store import append_page_analysis
        report = append_page_analysis(
            self.db, version_id, [self.block(1, "página um"), self.block(2, "página dois")],
            [self.proposal(0, "página um")])
        self.assertEqual(report["added_blocks"], 1)
        self.assertEqual(report["added_proposals"], 0)
        self.assertEqual(report["dropped_proposals"], 1)
        self.assertFalse(report["idempotent"])

    def test_indice_malformado_e_erro_e_nao_descarte(self):
        version_id = self.three_pages()
        from radar.document_store import append_page_analysis
        for bad in (True, None, "0", 99):
            with self.assertRaises(ValueError):
                append_page_analysis(self.db, version_id, [self.block(2, "página dois")],
                                     [self.proposal(bad, "página dois")])

    def test_citacao_invalida_no_append_nao_grava(self):
        version_id = self.three_pages()
        from radar.document_store import append_page_analysis
        with self.assertRaises(ValueError):
            append_page_analysis(self.db, version_id, [self.block(2, "página dois")],
                                 [self.proposal(0, "trecho que não existe")])
        with closing(connect_documents(self.db)) as conn:
            pages = [row[0] for row in conn.execute(
                "SELECT DISTINCT page_number FROM blocos_documento WHERE version_id=?",
                (version_id,))]
        self.assertEqual(pages, [1])

    def test_reanalise_de_versao_ja_analisada_continua_erro(self):
        version_id = self.three_pages()
        with self.assertRaises(ValueError):
            record_analysis(self.db, version_id, blocks_from(["página um"]), [])

    def test_pdf_criptografado_falha_com_codigo(self):
        from radar.document_extract import ExtractionError
        # Assinatura de PDF criptografado: o leitor precisa recusar, não estourar.
        document_id, version_id = self.version(
            b"%PDF-1.4\ntrailer\n<< /Encrypt 1 0 R /Root 2 0 R >>\n%%EOF\n")
        with self.assertRaises(ExtractionError):
            page_batches.page_index(self.db, version_id)


class ContinuityApiTest(PageBatchBase):
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

    def test_continuidade_e_parciais_respondem(self):
        status, body = self.get("/api/pipeline/continuidade")
        self.assertEqual(status, 200)
        self.assertIn("tabelas", json.loads(body))
        status, body = self.get("/api/pipeline/parciais")
        self.assertEqual(status, 200)
        self.assertIn("parciais", json.loads(body))

    def test_escopo_regional_exige_versao(self):
        status, _ = self.get("/api/pipeline/escopo-regional")
        self.assertEqual(status, 400)
