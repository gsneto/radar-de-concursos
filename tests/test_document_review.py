import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from radar.document_review import review_proposal, select_current_value, record_coverage
from radar.document_store import get_competition_details, migrate_document_schema, register_document, record_version, record_analysis


class ReviewTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = str(Path(tmp.name) / 'db.sqlite3')
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("INSERT INTO concursos_identidade (id,created_at) VALUES ('c','2026-10-10T00:00:00+00:00')")
            conn.execute("INSERT INTO observacoes_concurso (id,contest_id,source_url,competition_id,observed_at) VALUES ('o','c','https://guajaramirim.ro.gov.br/a/','1/2026','2026-10-10T00:00:00+00:00')")
            conn.commit()
        self.url = 'https://guajaramirim.ro.gov.br/e.pdf'
        self.doc = register_document(self.db, dict(observation_id='o', kind='edital', official_url=self.url,
                  title='Edital', discovery_url='https://guajaramirim.ro.gov.br/a/', discovery_method='manual',
                  discovered_at='2026-10-10T00:00:00+00:00'))
        self.version = record_version(self.db, self.doc, b'pdf', dict(fetched_at='2026-10-10T00:00:00+00:00',
                              fetched_url=self.url, content_type='application/pdf'))
        record_analysis(self.db, self.version,
                        [dict(text='10 vagas imediatas', start_offset=0, end_offset=18, page_number=1, locator='p.1')],
                        [dict(contest_id='c', role_id=None, field_name='immediate_vacancies', value_json='10',
                              value_type='integer', extraction_method='regex',
                              evidence=dict(block_index=0, quote='10 vagas imediatas', start_offset=0, end_offset=18))])
        self.proposal = get_competition_details(self.db, 'c')['proposals'][0]['id']

    def test_selection_requires_human_review_and_preserves_history(self):
        with self.assertRaises(ValueError):
            select_current_value(self.db, self.proposal, 'Ana', 'conferido')
        review_proposal(self.db, self.proposal, 'validado', 'Ana', 'conferido no PDF')
        first = select_current_value(self.db, self.proposal, 'Ana', 'decisão documentada')
        review_proposal(self.db, self.proposal, 'rejeitado', 'Beto', 'retificação contradiz')
        with self.assertRaises(ValueError):
            select_current_value(self.db, self.proposal, 'Ana', 'repetir')
        details = get_competition_details(self.db, 'c')
        self.assertEqual(details['current_values'][0]['id'], first)
        self.assertEqual(details['proposals'][0]['state'], 'rejeitado')
        self.assertEqual(len(details['proposals'][0]['reviews']), 2)

    def test_coverage_drops_to_partial_when_new_document_is_discovered(self):
        with self.assertRaises(ValueError):
            record_coverage(self.db, 'c', 'auditada_ate', [], 'Ana', '2026-10-10T01:00:00+00:00', 'conferido')
        record_coverage(self.db, 'c', 'auditada_ate', [self.url], 'Ana', '2026-10-10T01:00:00+00:00', 'conferido')
        self.assertEqual(get_competition_details(self.db, 'c')['coverage']['state'], 'auditada_ate')
        register_document(self.db, dict(observation_id='o', kind='retificacao',
             official_url='https://guajaramirim.ro.gov.br/r.pdf', title='Retificação',
             discovery_url='https://guajaramirim.ro.gov.br/a/', discovery_method='manual',
             discovered_at='2026-10-10T02:00:00+00:00'))
        self.assertEqual(get_competition_details(self.db, 'c')['coverage']['state'], 'parcial')

    def test_invalid_or_unobserved_coverage_cannot_claim_audit(self):
        with self.assertRaises(ValueError):
            record_coverage(self.db, 'c', 'auditada_ate', ['https://guajaramirim.ro.gov.br/not-seen.pdf'],
                            'Ana', '2026-10-10T01:00:00+00:00', 'supostamente')

    def test_second_validated_proposal_supersedes_only_same_scope_and_field(self):
        review_proposal(self.db, self.proposal, 'validado', 'Ana', 'conferido')
        first = select_current_value(self.db, self.proposal, 'Ana', 'primeira escolha')
        new_version = record_version(self.db, self.doc, b'pdf-retificado',
            dict(fetched_at='2026-10-10T02:00:00+00:00', fetched_url=self.url, content_type='application/pdf'))
        record_analysis(self.db, new_version,
            [dict(text='12 vagas imediatas', start_offset=0, end_offset=18, page_number=1, locator='p.1')],
            [dict(contest_id='c', role_id=None, field_name='immediate_vacancies', value_json='12',
                  value_type='integer', extraction_method='regex', evidence=dict(
                  block_index=0, quote='12 vagas imediatas', start_offset=0, end_offset=18))])
        details = get_competition_details(self.db, 'c')
        self.assertEqual(len(details['current_values']), 1)
        new_proposal = next(p['id'] for p in details['proposals'] if p['id'] != self.proposal)
        review_proposal(self.db, new_proposal, 'validado', 'Ana', 'retificação conferida')
        second = select_current_value(self.db, new_proposal, 'Ana', 'retificação prevalece')
        values = get_competition_details(self.db, 'c')['current_values']
        self.assertEqual(len(values), 2)
        self.assertEqual(next(v for v in values if v['id'] == second)['supersedes_id'], first)

    def test_rejected_selected_proposal_is_not_displayed_as_active(self):
        review_proposal(self.db, self.proposal, 'validado', 'Ana', 'conferido')
        selected = select_current_value(self.db, self.proposal, 'Ana', 'escolha')
        review_proposal(self.db, self.proposal, 'rejeitado', 'Beto', 'erro detectado')
        history = get_competition_details(self.db, 'c')['current_values']
        self.assertEqual(history[0]['id'], selected)
        self.assertFalse(history[0]['active'])

    def test_rejection_of_newer_selection_exposes_previous_valid_selection(self):
        review_proposal(self.db, self.proposal, 'validado', 'Ana', 'edital conferido')
        first = select_current_value(self.db, self.proposal, 'Ana', 'edital vigente')
        version = record_version(self.db, self.doc, b'outro-pdf', dict(
            fetched_at='2026-10-10T02:00:00+00:00', fetched_url=self.url, content_type='application/pdf'))
        record_analysis(self.db, version,
            [dict(text='12 vagas imediatas', start_offset=0, end_offset=18, page_number=1)],
            [dict(contest_id='c', role_id=None, field_name='immediate_vacancies', value_json='12',
                  value_type='integer', extraction_method='manual', evidence=dict(block_index=0,
                  quote='12 vagas imediatas', start_offset=0, end_offset=18))])
        newer = next(p['id'] for p in get_competition_details(self.db, 'c')['proposals'] if p['id'] != self.proposal)
        review_proposal(self.db, newer, 'validado', 'Ana', 'retificação conferida')
        second = select_current_value(self.db, newer, 'Ana', 'retificação prevalece')
        review_proposal(self.db, newer, 'rejeitado', 'Beto', 'retificação incorreta')
        history = {item['id']: item for item in get_competition_details(self.db, 'c')['current_values']}
        self.assertTrue(history[first]['active'])
        self.assertFalse(history[second]['active'])

    def test_invalid_calendar_proposal_is_not_recorded(self):
        version = record_version(self.db, self.doc, b'novo-pdf', dict(
            fetched_at='2026-10-10T02:00:00+00:00', fetched_url=self.url, content_type='application/pdf'))
        with self.assertRaisesRegex(ValueError, 'data'):
            record_analysis(self.db, version,
                [dict(text='Inscrições 30/02/2026', start_offset=0, end_offset=21, page_number=1)],
                [dict(contest_id='c', role_id=None, field_name='registration_start',
                      value_json='"2026-02-30"', value_type='string', extraction_method='manual',
                      evidence=dict(block_index=0, quote='30/02/2026', start_offset=11, end_offset=21))])
        self.assertEqual(len(get_competition_details(self.db, 'c')['proposals']), 1)
