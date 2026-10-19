"""Revisão agrupada por linha documental, validação e reparo de rótulo (Fase 42)."""

import json
import sqlite3
import unittest
from contextlib import closing

from radar import label_repair, review, review_groups, vacancy_columns
from tests.test_portfolio_f36 import NOON, add_document, add_proposal, make_db

LABEL = "cargo do documento não reconciliado: "


def _prop(db, contest, *, version, field, value, quote, label="CARGO A", page=3):
    return add_proposal(db, contest, version_id=version, field=field, value=value,
                        quote=quote, reason=LABEL + label, page=page)


def _wide_pdf(rows, *, continuation=None, pitch=32):
    """PDF mínimo com o arranjo de colunas do Anexo II (duas páginas)."""
    import pymupdf

    document = pymupdf.open()
    xs = [150, 240, 296, 357, 386, 414, 443, 471, 499, 527, 552]
    header = ("AC", "PcD", "PP", "PI", "PQ", "PPIQ", "PI/PQ", "Total")

    def page(rows_page, top=110):
        sheet = document.new_page(width=612, height=792)
        for x, text in zip(xs[:3], ["Cargo", "Formação", "Escolaridade"]):
            sheet.insert_text((x, 80), text, fontsize=7)
        for x, text in zip(xs[3:], header):
            sheet.insert_text((x, 80), text, fontsize=7)
        y = top
        for row in rows_page:
            sheet.insert_text((150, y), row["cargo"], fontsize=7)
            sheet.insert_text((240, y), row["formacao"], fontsize=7)
            sheet.insert_text((296, y), row["escolaridade"], fontsize=7)
            for x, value in zip(xs[3:], row["values"]):
                sheet.insert_text((x, y), value, fontsize=7)
            y += pitch
        return y

    page(rows)
    if continuation:
        sheet = document.new_page(width=612, height=792)
        for x, text in zip(xs[:3], ["Cargo", "Formação", "Escolaridade"]):
            sheet.insert_text((x, 80), text, fontsize=7)
        for x, text in zip(xs[3:], header):
            sheet.insert_text((x, 80), text, fontsize=7)
        sheet.insert_text((296, 96), continuation["escolaridade"], fontsize=7)
        sheet.insert_text((150, 150), continuation["cargo"], fontsize=7)
        sheet.insert_text((240, 150), continuation["formacao"], fontsize=7)
        sheet.insert_text((296, 150), "Nível Médio", fontsize=7)
        for x, value in zip(xs[3:], continuation["values"]):
            sheet.insert_text((x, 150), value, fontsize=7)
    return document.tobytes()


def _store_version(db, pdf, *, contest="c1", version="v1", document="doc1"):
    """Grava documento, versão, blocos e o artefato do PDF no banco de teste."""
    import hashlib
    from pathlib import Path
    from radar.document_extract import extract_document
    from radar.document_store import migrate_document_schema

    migrate_document_schema(db)
    digest = hashlib.sha256(pdf).hexdigest()
    relative = f"radar.sqlite3.documents/{digest}"
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute(
            "INSERT INTO documentos (id,contest_id,observation_id,kind,official_url,title,"
            "discovered_at,discovery_url,discovery_method,issuer,published_at,"
            "tipo_documental) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (document, contest, f"o-{contest}", "edital", "https://x/edital.pdf", "Edital",
             "2026-09-01", "https://x", "automatico", "FGV", "2026-09-01",
             "edital_abertura"))
        conn.execute(
            "INSERT INTO versoes_documento (id,document_id,sha256,fetched_at,fetched_url,"
            "content_type,byte_size,local_path,extraction_state) VALUES (?,?,?,?,?,?,?,?,?)",
            (version, document, digest, "2026-09-01", "https://x/edital.pdf",
             "application/pdf", len(pdf), relative, "parcial"))
        blocks = extract_document(pdf, "application/pdf")["blocks"]
        for index, block in enumerate(blocks):
            conn.execute(
                "INSERT INTO blocos_documento (id,version_id,page_number,locator,"
                "start_offset,end_offset,text) VALUES (?,?,?,?,?,?,?)",
                (f"blk-{version}-{index}", version, block["page_number"],
                 block["locator"], block["start_offset"], block["end_offset"],
                 block["text"]))
    artifact = Path(db).resolve().parent / relative
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(pdf)
    return digest


def _insert_proposal(db, *, contest, version, field, value, quote, label, page,
                     method="quadro-colunas-pdf", block="blk-v1-0", start=0):
    with closing(sqlite3.connect(db)) as conn, conn:
        text = conn.execute("SELECT text FROM blocos_documento WHERE id=?",
                            (block,)).fetchone()[0]
        offset = text.find(quote)
        if offset < 0:
            offset = start
        evidence = f"ev-{field}-{abs(hash(label)) % 10000}"
        conn.execute(
            "INSERT INTO evidencias (id,version_id,block_id,quote,page_number,locator,"
            "start_offset,end_offset,captured_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (evidence, version, block, quote, page, "página", offset,
             offset + len(quote), "2026-09-01T00:00:00+00:00"))
        proposal = f"p-{field}-{evidence}"
        conn.execute(
            "INSERT INTO propostas_campo (id,contest_id,role_id,field_name,value_json,"
            "value_type,evidence_id,extraction_method,ambiguity_reason,extracted_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (proposal, contest, None, field, json.dumps(value), "integer", evidence,
             method, label, "2026-09-01T00:00:00+00:00"))
    return proposal


class GroupingTest(unittest.TestCase):
    """Agrupa pela identidade documental da linha, nunca por valor igual."""

    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def test_mesma_evidencia_agrupa_campos_distintos(self):
        _, version = add_document(self.db, "c1", text="CARGO A 8 1 3 1 1 0 0 14")
        for field, value in (("immediate_vacancies", 14), ("indigenous_vacancies", 1),
                             ("unified_ppiq_vacancies", 0),
                             ("unified_pi_pq_vacancies", 0)):
            _prop(self.db, "c1", version=version, field=field, value=value,
                  quote="CARGO A 8 1 3 1 1 0 0 14")
        report = review_groups.groups(self.db, now=NOON)
        self.assertEqual(report["total"], 1)
        item = report["itens"][0]
        self.assertEqual(len(item["propostas"]), 4)
        self.assertEqual(item["pendentes"], 4)
        self.assertEqual(item["estado"], "pendente")

    def test_mesmo_valor_em_trechos_diferentes_nao_agrupa(self):
        _, version = add_document(
            self.db, "c1", text="CARGO A 1 0 0 0 0 0 0 1 CARGO B 1 0 0 0 0 0 0 1")
        _prop(self.db, "c1", version=version, field="immediate_vacancies", value=1,
              quote="CARGO A 1 0 0 0 0 0 0 1", label="CARGO A")
        _prop(self.db, "c1", version=version, field="immediate_vacancies", value=1,
              quote="CARGO B 1 0 0 0 0 0 0 1", label="CARGO B")
        report = review_groups.groups(self.db, now=NOON)
        self.assertEqual(report["total"], 2)
        scopes = {item["scope"] for item in report["itens"]}
        self.assertEqual(len(scopes), 2)

    def test_estado_do_grupo_reflete_cada_proposta(self):
        _, version = add_document(self.db, "c1", text="CARGO A 1 0 0 0 0 0 0 1")
        first = _prop(self.db, "c1", version=version, field="immediate_vacancies",
                      value=1, quote="CARGO A 1 0 0 0 0 0 0 1")
        _prop(self.db, "c1", version=version, field="indigenous_vacancies", value=0,
              quote="CARGO A 1 0 0 0 0 0 0 1")
        review.decide_proposal(self.db, first, "validado", reviewer="teste",
                               reason="total publicado confere", origin="cli")
        report = review_groups.groups(self.db, now=NOON)
        item = report["itens"][0]
        self.assertEqual(item["estado"], "parcial")
        self.assertEqual(item["pendentes"], 1)
        states = {proposal["field_name"]: proposal["state"]
                  for proposal in item["propostas"]}
        self.assertEqual(states["immediate_vacancies"], "validado")
        self.assertEqual(states["indigenous_vacancies"], "pendente")

    def test_filtro_de_campo_e_estado(self):
        _, version = add_document(self.db, "c1", text="CARGO A 1 0 0 0 0 0 0 1")
        _prop(self.db, "c1", version=version, field="immediate_vacancies", value=1,
              quote="CARGO A 1 0 0 0 0 0 0 1")
        _prop(self.db, "c1", version=version, field="indigenous_vacancies", value=0,
              quote="CARGO A 1 0 0 0 0 0 0 1")
        report = review_groups.groups(self.db, field_name="indigenous_vacancies",
                                      now=NOON)
        self.assertEqual(report["total"], 1)
        self.assertEqual([proposal["field_name"]
                          for proposal in report["itens"][0]["propostas"]],
                         ["indigenous_vacancies"])

    def test_limite_e_paginacao(self):
        for index in range(3):
            _, version = add_document(self.db, "c1", text=f"CARGO {index} 1 0 0 0 0 0 0 1",
                                      published_at=f"2026-09-0{index + 1}")
            _prop(self.db, "c1", version=version, field="immediate_vacancies", value=1,
                  quote=f"CARGO {index} 1 0 0 0 0 0 0 1", label=f"CARGO {index}")
        first = review_groups.groups(self.db, limit=2, now=NOON)
        self.assertEqual(first["total"], 3)
        self.assertTrue(first["has_more"])
        second = review_groups.groups(self.db, limit=2, offset=2, now=NOON)
        self.assertFalse(second["has_more"])
        self.assertEqual(len(second["itens"]), 1)

    def test_resumo_separa_linhas_propostas_decisoes_e_vigentes(self):
        _, version = add_document(self.db, "c1", text="CARGO A 1 0 0 0 0 0 0 1")
        proposal = _prop(self.db, "c1", version=version, field="immediate_vacancies",
                         value=1, quote="CARGO A 1 0 0 0 0 0 0 1")
        review.decide_proposal(self.db, proposal, "validado", reviewer="teste",
                               reason="conferido", origin="cli")
        resumo = review_groups.groups(self.db, state="todos", now=NOON)["resumo"]
        self.assertEqual(resumo["linhas"], 1)
        self.assertEqual(resumo["propostas"], 1)
        self.assertEqual(resumo["decisoes_registradas"], 1)
        self.assertEqual(resumo["valores_vigentes"], 0)


class ValidationTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def test_soma_divergente_nao_substitui_o_total(self):
        _, version = add_document(self.db, "c1", text="CARGO A 4 1 2 0 0 0 0 9")
        for field, value in (("immediate_vacancies", 9), ("indigenous_vacancies", 0),
                             ("unified_ppiq_vacancies", 0),
                             ("unified_pi_pq_vacancies", 0)):
            _prop(self.db, "c1", version=version, field=field, value=value,
                  quote="CARGO A 4 1 2 0 0 0 0 9")
        # O grupo sem contexto de quadro não inventa validação.
        report = review_groups.groups(self.db, now=NOON)
        self.assertIsNone(report["itens"][0]["validacao"])

    def test_validacao_usa_colunas_publicadas(self):
        blocks = [{"block_id": "b1", "page_number": 3, "locator": "página 3",
                   "start_offset": 0, "end_offset": 30,
                   "text": "CARGO A 4 1 2 0 0 0 0 9"}]
        context = {"tipo": "colunas",
                   "valores": {"AC": 4, "PcD": 1, "PP": 2, "PI": 0, "PQ": 0,
                               "PPIQ": 0, "PI/PQ": 0, "Total": 9}}
        validacao = review_groups._validacao(context)
        self.assertEqual(validacao["publicado"], 9)
        self.assertEqual(validacao["soma"], 7)
        self.assertEqual(validacao["diferenca"], 2)
        self.assertEqual(validacao["estado"], "divergente")
        self.assertIn("unificadas", validacao["regra"])

    def test_total_agregado_nao_vira_vaga(self):
        context = {"tipo": "texto", "total": 30,
                   "valores": {"AC": 19, "PCD": 1, "PP": 8, "PI": 1, "PQ": 1}}
        validacao = review_groups._validacao(context)
        self.assertEqual(validacao["publicado"], 30)
        self.assertEqual(validacao["soma"], 30)
        self.assertEqual(validacao["estado"], "consistente")


class CrossPageAuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def build_pdf(self):
        import pymupdf

        document = pymupdf.open()
        xs = [150, 240, 296, 357, 386, 414, 443, 471, 499, 527, 552]
        header = ("AC", "PcD", "PP", "PI", "PQ", "PPIQ", "PI/PQ", "Total")
        first = document.new_page(width=612, height=792)
        first.insert_text((20, 40), "ANEXO II - QUADRO DE VAGAS", fontsize=8)
        for x, text in zip(xs[:3], ["Cargo", "Formação", "Escolaridade"]):
            first.insert_text((x, 80), text, fontsize=7)
        for x, text in zip(xs[3:], header):
            first.insert_text((x, 80), text, fontsize=7)
        first.insert_text((150, 110), "Professor", fontsize=7)
        first.insert_text((240, 110), "Física", fontsize=7)
        first.insert_text((296, 110), "Nível", fontsize=7)
        for x, value in zip(xs[3:], ["2", "0", "0", "0", "0", "1", "0", "3"]):
            first.insert_text((x, 110), value, fontsize=7)
        # Linha cortada: escolaridade continua na página seguinte.
        first.insert_text((150, 140), "Professor", fontsize=7)
        first.insert_text((240, 140), "Química", fontsize=7)
        first.insert_text((296, 140), "Nível", fontsize=7)
        for x, value in zip(xs[3:], ["1", "0", "0", "0", "0", "1", "0", "2"]):
            first.insert_text((x, 140), value, fontsize=7)

        second = document.new_page(width=612, height=792)
        for x, text in zip(xs[:3], ["Cargo", "Formação", "Escolaridade"]):
            second.insert_text((x, 80), text, fontsize=7)
        for x, text in zip(xs[3:], header):
            second.insert_text((x, 80), text, fontsize=7)
        # Continuação da linha anterior (mesma coluna, topo da página).
        second.insert_text((296, 96), "Superior", fontsize=7)
        # Primeira linha da página, com rótulo multilinha acima dos números.
        second.insert_text((150, 140), "Assistente de", fontsize=7)
        second.insert_text((150, 151), "Gestão", fontsize=7)
        second.insert_text((240, 140), "Assistente de", fontsize=7)
        second.insert_text((240, 151), "Gestão", fontsize=7)
        second.insert_text((296, 151), "Nível", fontsize=7)
        second.insert_text((296, 162), "Médio", fontsize=7)
        for x, value in zip(xs[3:], ["1", "0", "0", "0", "0", "0", "0", "1"]):
            second.insert_text((x, 151), value, fontsize=7)
        return document.tobytes()

    def test_continuacao_nao_contamina_linha_anterior(self):
        pdf = self.build_pdf()
        from radar.document_extract import extract_document
        from radar import modality_legend
        blocks = extract_document(pdf, "application/pdf")["blocks"]
        report = vacancy_columns.parse_wide_table(
            blocks, "c1", label_prefix=LABEL, pdf_path=pdf,
            definitions=modality_legend.parse_definitions(""))
        stitched = [row for row in report["rows"] if row["rotulo_completado"]]
        self.assertEqual(len(stitched), 1)
        self.assertEqual(stitched[0]["formacao"], "Química")
        self.assertEqual(stitched[0]["escolaridade"], "Nível Superior")
        # A primeira linha da página seguinte não entrou na costura.
        self.assertNotIn("Assistente", stitched[0]["cargo"])
        following = [row for row in report["rows"] if row["page"] == 2][0]
        self.assertEqual(following["cargo"], "Assistente de Gestão")

    def test_auditoria_compara_antes_e_depois(self):
        pdf = self.build_pdf()
        from radar.document_extract import extract_document
        from radar.document_store import migrate_document_schema
        # Grava a versão com artefato local para a auditoria poder reler o PDF.
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(
                "INSERT INTO documentos (id,contest_id,observation_id,kind,official_url,"
                "title,discovered_at,discovery_url,discovery_method,issuer,published_at,"
                "tipo_documental) VALUES ('doc1','c1','o-c1','edital','https://x/edital.pdf',"
                "'Edital','2026-09-01','https://x','automatico','FGV','2026-09-01',"
                "'edital_abertura')")
            import hashlib
            digest = hashlib.sha256(pdf).hexdigest()
            relative = f"radar.sqlite3.documents/{digest}"
            conn.execute(
                "INSERT INTO versoes_documento (id,document_id,sha256,fetched_at,fetched_url,"
                "content_type,byte_size,local_path,extraction_state) VALUES "
                "('v1','doc1',?,'2026-09-01','https://x/edital.pdf','application/pdf',?,?,"
                "'parcial')", (digest, len(pdf), relative))
            for block in extract_document(pdf, "application/pdf")["blocks"]:
                conn.execute(
                    "INSERT INTO blocos_documento (id,version_id,page_number,locator,"
                    "start_offset,end_offset,text) VALUES (?,?,?,?,?,?,?)",
                    (f"b{block['page_number']}", 'v1', block['page_number'],
                     block['locator'], block['start_offset'], block['end_offset'],
                     block['text']))
        from pathlib import Path
        artifact = Path(self.db).resolve().parent / relative
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(pdf)
        audit = vacancy_columns.audit_schooling(self.db, contest_id="c1")
        self.assertEqual(audit["linhas"], 1)
        item = audit["itens"][0]
        self.assertEqual(item["antes"]["escolaridade"], "Nível")
        self.assertEqual(item["depois"]["escolaridade"], "Nível Superior")
        self.assertTrue(item["continuacao_comprovada"])
        self.assertEqual(item["pages"], [1, 2])


class SchoolingRegressionTest(unittest.TestCase):
    def test_escolaridade_nao_canonica_nao_derruba_a_linha(self):
        pdf = _wide_pdf([{"cargo": "Professor", "formacao": "Química",
                          "escolaridade": "Ensino Superior",
                          "values": ["1", "0", "0", "0", "0", "1", "0", "2"]}])
        from radar.document_extract import extract_document
        from radar import modality_legend
        blocks = extract_document(pdf, "application/pdf")["blocks"]
        report = vacancy_columns.parse_wide_table(
            blocks, "c1", label_prefix=LABEL, pdf_path=pdf,
            definitions=modality_legend.parse_definitions(
                "I – AC: Ampla Concorrência; IV – PI: Pessoas Indígenas; "
                "VI – PPIQ: vaga unificada destinada às Pessoas Indígenas; "
                "VII – PI/PQ: vaga unificada destinada às Pessoas Indígenas."))
        # Redação diferente e completa não é truncamento: a linha continua extraída.
        self.assertEqual(len(report["rows"]), 1)
        self.assertEqual(len(report["proposals"]), 4)
        self.assertIn("escolaridade_incompleta",
                      [item["causa"] for item in report["pendencias"]])

    def test_linhas_apertadas_nao_fundem_cargos(self):
        pdf = _wide_pdf([
            {"cargo": "Professor", "formacao": "Física",
             "escolaridade": "Nível Superior",
             "values": ["2", "0", "0", "0", "0", "1", "0", "3"]},
            {"cargo": "Professor", "formacao": "Química",
             "escolaridade": "Nível Superior",
             "values": ["1", "0", "0", "0", "0", "1", "0", "2"]},
        ], pitch=14)
        from radar.document_extract import extract_document
        from radar import modality_legend
        blocks = extract_document(pdf, "application/pdf")["blocks"]
        report = vacancy_columns.parse_wide_table(
            blocks, "c1", label_prefix=LABEL, pdf_path=pdf,
            definitions=modality_legend.parse_definitions(""))
        labels = {(row["cargo"], row["formacao"]) for row in report["rows"]}
        self.assertIn(("Professor", "Física"), labels)
        self.assertIn(("Professor", "Química"), labels)
        self.assertNotIn(("Professor Professor", "Física Química"), labels)


class LabelRepairTest(unittest.TestCase):
    """Reparo real sobre uma versão de quadro largo gravada no banco de teste."""

    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)
        self.pdf = _wide_pdf(
            [{"cargo": "Professor", "formacao": "Química",
              "escolaridade": "Nível", "values": ["1", "0", "0", "0", "0",
                                                       "1", "0", "2"]}],
            continuation={"cargo": "Assistente de Gestão", "formacao": "Gestão",
                          "escolaridade": "Superior",
                          "values": ["1", "0", "0", "0", "0", "0", "0", "1"]})
        _store_version(self.db, self.pdf)
        self.truncated = _insert_proposal(
            self.db, contest="c1", version="v1", field="indigenous_vacancies", value=0,
            quote="Professor Química Nível 1 0 0 0 0 1 0 2",
            label=LABEL + "Professor / Química / DRE BELÉM"
                         " [rotulo completado na pagina seguinte]", page=1)

    def test_repara_uma_vez_com_evento(self):
        first = label_repair.repair_labels(self.db, contest_id="c1", dry_run=False)
        self.assertEqual(first["reparaveis"], 1)
        self.assertEqual(first["reparadas"], 1)
        second = label_repair.repair_labels(self.db, contest_id="c1", dry_run=False)
        self.assertEqual(second["reparaveis"], 0)
        with closing(sqlite3.connect(self.db)) as conn:
            stored = conn.execute(
                "SELECT ambiguity_reason FROM propostas_campo WHERE id=?",
                (self.truncated,)).fetchone()[0]
            self.assertEqual(stored, LABEL + "Professor / Química")
            notes = conn.execute(
                "SELECT note FROM eventos_documentais WHERE event_type='analise'").fetchall()
            self.assertEqual(len(notes), 1)
            payload = json.loads(notes[0][0])
            self.assertEqual(payload["reparo"], "label_repair_v1")
            self.assertIn("rotulo completado", payload["de"])
            self.assertEqual(payload["para"], "Professor / Química")

    def test_nao_repara_proposta_com_decisao(self):
        review.decide_proposal(self.db, self.truncated, "validado", reviewer="teste",
                               reason="conferido", origin="cli")
        report = label_repair.repair_labels(self.db, contest_id="c1", dry_run=False)
        self.assertEqual(report["reparaveis"], 0)
        self.assertEqual(report["reparadas"], 0)
        self.assertIn("proposta_com_decisao_ou_lote",
                      [item["motivo"] for item in report["ignorados"]])
        with closing(sqlite3.connect(self.db)) as conn:
            stored = conn.execute(
                "SELECT ambiguity_reason FROM propostas_campo WHERE id=?",
                (self.truncated,)).fetchone()[0]
            self.assertIn("rotulo completado", stored)

    def test_nao_repara_rotulo_nao_comprovado(self):
        other = _insert_proposal(
            self.db, contest="c1", version="v1", field="immediate_vacancies", value=2,
            quote="Professor Química Nível 1 0 0 0 0 1 0 2",
            label=LABEL + "OUTRO CARGO", page=1, block="blk-v1-0")
        report = label_repair.repair_labels(self.db, contest_id="c1", dry_run=False)
        # Só a proposta com marca legada é reparável; a inventada não.
        self.assertEqual(report["reparaveis"], 1)
        with closing(sqlite3.connect(self.db)) as conn:
            stored = conn.execute(
                "SELECT ambiguity_reason FROM propostas_campo WHERE id=?",
                (other,)).fetchone()[0]
            self.assertEqual(stored, LABEL + "OUTRO CARGO")


class ApiTest(unittest.TestCase):
    def setUp(self):
        import threading
        from radar.server import create_server
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)
        _, version = add_document(self.db, "c1", text="CARGO A 1 0 0 0 0 0 0 1")
        _prop(self.db, "c1", version=version, field="immediate_vacancies", value=1,
              quote="CARGO A 1 0 0 0 0 0 0 1")
        self.server = create_server(self.db, host="127.0.0.1", port=0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_address[1]

    def get(self, path):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", path)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, data

    def test_grupos(self):
        status, body = self.get("/api/revisao/grupos?limit=5")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["version"], "review_groups_v1")
        self.assertEqual(payload["total"], 1)
        self.assertIn("resumo", payload)
        self.assertIn("denominador", payload)

    def test_parametro_desconhecido(self):
        status, _ = self.get("/api/revisao/grupos?x=1")
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
