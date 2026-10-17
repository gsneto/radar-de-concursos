import json
from io import BytesIO
import unittest

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from radar.document_extract import extract_blocks
from radar.document_fields import extract_field_proposals


class DocumentExtractTest(unittest.TestCase):
    def test_html_has_no_script_text_and_proposals_quote_exact_spans(self):
        html = b'''<html><body><h2>Vagas</h2><p>Haver\xc3\xa1 10 vagas imediatas.</p>
            <script>20 vagas imediatas</script><p>N\xc3\xa3o haver\xc3\xa1 cadastro de reserva: 0 vagas.</p>
            <p>Reservadas 2 vagas para pessoas ind\xc3\xadgenas.</p></body></html>'''
        blocks = extract_blocks(html, 'text/html; charset=utf-8')
        self.assertNotIn('20 vagas', ' '.join(b['text'] for b in blocks))
        proposals = extract_field_proposals(blocks, 'version', 'contest')
        self.assertEqual({p['field_name']: json.loads(p['value_json']) for p in proposals},
                         {'immediate_vacancies': 10, 'reserve_vacancies': 0, 'indigenous_vacancies': 2})
        for proposal in proposals:
            evidence = proposal['evidence']
            self.assertEqual(blocks[evidence['block_index']]['text'][evidence['start_offset']:evidence['end_offset']], evidence['quote'])
            self.assertIsNone(proposal['role_id'])

    def test_generic_quota_and_unknown_reserve_create_no_proposal(self):
        blocks = extract_blocks('''<article><p>Cadastro de reserva e vagas reservadas para cotas raciais.</p></article>'''.encode(), 'text/html')
        self.assertEqual(extract_field_proposals(blocks, 'v', 'c'), [])

    def test_invalid_pdf_has_no_invented_text(self):
        with self.assertRaises(ValueError):
            extract_blocks(b'%PDF-not-a-valid-document', 'application/pdf')

    def test_textual_pdf_preserves_page_one_quote(self):
        writer = PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
            NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
            DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(b'BT /F1 12 Tf 72 720 Td (10 vagas imediatas) Tj ET')
        page[NameObject('/Contents')] = writer._add_object(stream)
        output = BytesIO()
        writer.write(output)
        blocks = extract_blocks(output.getvalue(), 'application/pdf')
        self.assertEqual(blocks[0]['page_number'], 1)
        self.assertEqual(blocks[0]['text'], '10 vagas imediatas')
        evidence = extract_field_proposals(blocks, 'v', 'c')[0]['evidence']
        self.assertEqual(evidence['quote'], '10 vagas imediatas')

    def test_registration_interval_is_validated_before_proposing_dates(self):
        valid = extract_blocks(b'<p>Inscricoes de 10 a 30/07/2026.</p>', 'text/html')
        proposals = extract_field_proposals(valid, 'v', 'c')
        self.assertEqual({p['field_name']: json.loads(p['value_json']) for p in proposals},
                         {'registration_start': '2026-07-10', 'registration_end': '2026-07-30'})
        for interval in (b'Inscricoes de 31 a 32/02/2026.', b'Inscricoes de 30 a 10/07/2026.'):
            invalid = extract_blocks(b'<p>' + interval + b'</p>', 'text/html')
            self.assertEqual(extract_field_proposals(invalid, 'v', 'c'), [])

    def test_page_limit_is_configurable(self):
        writer = PdfWriter()
        for _ in range(2):
            writer.add_blank_page(width=200, height=200)
        output = BytesIO()
        writer.write(output)
        pdf = output.getvalue()
        with self.assertRaisesRegex(ValueError, 'excede o limite'):
            extract_blocks(pdf, 'application/pdf', max_pages=1)
        with self.assertRaisesRegex(ValueError, 'sem texto'):
            extract_blocks(pdf, 'application/pdf', max_pages=2)

    def test_prefixo_declarado_para_pdf_longo(self):
        from radar.document_extract import ExtractionError, extract_document
        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=200, height=200)
        output = BytesIO()
        writer.write(output)
        pdf = output.getvalue()
        with self.assertRaises(ExtractionError) as ctx:
            extract_document(pdf, "application/pdf", max_pages=1)
        self.assertEqual(ctx.exception.code, "pdf_paginas_excedidas")
        # Prefixo não inventa texto: páginas em branco continuam sem texto extraível.
        with self.assertRaises(ExtractionError) as ctx2:
            extract_document(pdf, "application/pdf", max_pages=1, prefix_pages=1)
        self.assertEqual(ctx2.exception.code, "pdf_sem_texto")

    def test_codigos_de_falha_sao_estaveis(self):
        from radar.document_extract import ExtractionError, extract_document
        with self.assertRaises(ExtractionError) as ctx:
            extract_document(b"<html>sem corpo</html>", "text/html")
        self.assertEqual(ctx.exception.code, "html_sem_texto")
        with self.assertRaises(ExtractionError) as ctx2:
            extract_document(b"MZ executavel", "application/pdf")
        self.assertEqual(ctx2.exception.code, "tipo_invalido")

    def test_simple_vagas_table_produces_per_role_immediate(self):
        # Documento cujo único quadro é CARGO | VAGAS: nova capacidade da Fase 8.
        html = ('<table><tr><td>CARGO</td><td>VAGAS</td></tr>'
                '<tr><td>Professor de Matemática</td><td>12</td></tr>'
                '<tr><td>Professor de Física</td><td>8</td></tr></table>')
        proposals = extract_field_proposals(extract_blocks(html.encode(), 'text/html'), 'v', 'c')
        values = sorted(json.loads(p['value_json']) for p in proposals
                        if p['field_name'] == 'immediate_vacancies')
        self.assertEqual(values, [8, 12])
        labels = sorted(p['ambiguity_reason'] for p in proposals)
        self.assertEqual(len(labels), 2)
