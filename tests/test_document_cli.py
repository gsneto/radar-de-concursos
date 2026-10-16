import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from radar.__main__ import main
from radar.document_store import list_competition_identities, get_competition_details, record_version, register_document, record_analysis, migrate_document_schema
from radar.document_extract import extract_blocks
from radar.document_fields import LABEL_PREFIX, extract_field_proposals

FIXTURE = Path(__file__).parent / "fixtures" / "documents" / "edital-guajara-anexo-i.html"
AMENDMENT = Path(__file__).parent / "fixtures" / "documents" / "retificacao-sintetica.html"


class DocumentCLITest(unittest.TestCase):
    def test_link_amendment_command_relates_documents(self):
        with tempfile.TemporaryDirectory() as temp:
            db = str(Path(temp) / 'radar.sqlite3')
            main(['documents-migrate', '--db', db])
            with closing(sqlite3.connect(db)) as conn:
                conn.execute("INSERT INTO concursos_identidade VALUES ('c','2026-10-10T00:00:00+00:00')")
                conn.execute("INSERT INTO observacoes_concurso VALUES ('o','c','https://guajaramirim.ro.gov.br/a/','1/2026','2026-10-10T00:00:00+00:00')")
                conn.commit()
            original = register_document(db, dict(observation_id='o', kind='edital',
                official_url='https://guajaramirim.ro.gov.br/edital.html', title='Edital',
                discovery_url='https://guajaramirim.ro.gov.br/edital.html', discovery_method='manual',
                discovered_at='2026-10-10T00:00:00+00:00'))
            amendment = register_document(db, dict(observation_id='o', kind='retificacao',
                official_url='https://guajaramirim.ro.gov.br/retificacao.html', title='Retificação',
                discovery_url='https://guajaramirim.ro.gov.br/retificacao.html', discovery_method='manual',
                discovered_at='2026-10-10T00:00:00+00:00'))
            main(['documents-link-amendment', '--db', db, '--amendment-id', amendment,
                  '--original-id', original, '--reviewer', 'Ana', '--reason', 'mesmo certame'])
            docs = {d['id']: d for d in get_competition_details(db, 'c')['documents']}
            self.assertIn(original, docs[amendment]['related_document_ids'])

    def test_reconcile_command_links_label_to_role(self):
        with tempfile.TemporaryDirectory() as temp:
            db = str(Path(temp) / 'radar.sqlite3')
            main(['documents-migrate', '--db', db])
            with closing(sqlite3.connect(db)) as conn:
                conn.execute("INSERT INTO concursos_identidade VALUES ('c','2026-10-10T00:00:00+00:00')")
                conn.execute("INSERT INTO observacoes_concurso VALUES ('o','c','https://guajaramirim.ro.gov.br/a/','1/2026','2026-10-10T00:00:00+00:00')")
                conn.execute("INSERT INTO cargos_identidade (id,contest_id,name,specialty,created_at) VALUES ('r','c','Professor de Educação Infantil',NULL,'2026-10-10T00:00:00+00:00')")
                conn.commit()
            url = 'https://guajaramirim.ro.gov.br/edital.html'
            doc = register_document(db, dict(observation_id='o', kind='edital', official_url=url,
                title='Edital', discovery_url=url, discovery_method='manual',
                discovered_at='2026-10-10T00:00:00+00:00'))
            content = FIXTURE.read_bytes()
            version = record_version(db, doc, content, dict(fetched_at='2026-10-10T01:00:00+00:00',
                fetched_url=url, content_type='text/html'))
            blocks = extract_blocks(content, 'text/html; charset=utf-8')
            record_analysis(db, version, blocks, extract_field_proposals(blocks, version, 'c', None))
            proposal = next(p for p in get_competition_details(db, 'c')['proposals']
                            if p['field_name'] == 'immediate_vacancies' and p['value'] == 69)
            label = proposal['ambiguity_reason'][len(LABEL_PREFIX):]
            main(['documents-reconcile', '--db', db, '--contest-id', 'c', '--label', label,
                  '--role-id', 'r', '--reviewer', 'Ana', '--reason', 'cargo conferido'])
            reconciled = next(p for p in get_competition_details(db, 'c')['proposals']
                              if p['id'] == proposal['id'])
            self.assertEqual(reconciled['reconciled_role_id'], 'r')

    def test_analysis_preserves_document_role_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            db = str(Path(temp) / 'radar.sqlite3')
            main(['documents-migrate', '--db', db])
            with closing(sqlite3.connect(db)) as conn:
                conn.execute("INSERT INTO concursos_identidade VALUES ('c','2026-10-10T00:00:00+00:00')")
                conn.execute("INSERT INTO observacoes_concurso VALUES ('o','c','https://guajaramirim.ro.gov.br/a/','1/2026','2026-10-10T00:00:00+00:00')")
                conn.execute("INSERT INTO cargos_identidade (id,contest_id,name,specialty,created_at) VALUES ('r','c','Professor',NULL,'2026-10-10T00:00:00+00:00')")
                conn.execute("INSERT INTO observacoes_cargo VALUES ('or','r','o','Professor','2026-10-10T00:00:00+00:00')")
                conn.commit()
            url = 'https://guajaramirim.ro.gov.br/edital.html'
            document_id = register_document(db, dict(observation_id='o', role_id='r',
                kind='edital', official_url=url, title='Edital do cargo', discovery_url=url,
                discovery_method='manual', discovered_at='2026-10-10T00:00:00+00:00'))
            version = record_version(db, document_id, b'<p>10 vagas imediatas.</p>', dict(
                fetched_at='2026-10-10T01:00:00+00:00', fetched_url=url, content_type='text/html'))
            main(['documents-analyze', '--db', db, '--version-id', version])
            self.assertEqual(get_competition_details(db, 'c')['proposals'][0]['role_id'], 'r')

    def test_failed_pdf_analysis_is_auditable_without_proposals(self):
        with tempfile.TemporaryDirectory() as temp:
            db = str(Path(temp) / 'radar.sqlite3')
            main(['documents-migrate', '--db', db])
            with closing(sqlite3.connect(db)) as conn:
                conn.execute("INSERT INTO concursos_identidade VALUES ('c','2026-10-10T00:00:00+00:00')")
                conn.execute("INSERT INTO observacoes_concurso VALUES ('o','c','https://guajaramirim.ro.gov.br/a/','1/2026','2026-10-10T00:00:00+00:00')")
                conn.commit()
            url = 'https://guajaramirim.ro.gov.br/e.pdf'
            main(['documents-register','--db',db,'--observation-id','o','--kind','edital','--url',url,'--title','Edital'])
            doc = get_competition_details(db, 'c')['documents'][0]['id']
            version = record_version(db, doc, b'%PDF-invalid', dict(
                fetched_at='2026-10-10T01:00:00+00:00', fetched_url=url, content_type='application/pdf'))
            with self.assertRaises(ValueError):
                main(['documents-analyze','--db',db,'--version-id',version])
            detail = get_competition_details(db, 'c')
            self.assertEqual(detail['documents'][0]['versions'][0]['extraction_state'], 'falhou')
            self.assertEqual(detail['proposals'], [])
            self.assertTrue(any(e['event_type'] == 'falha' for e in detail['documents'][0]['events']))

    def test_invalid_registration_interval_records_diagnostic(self):
        with tempfile.TemporaryDirectory() as temp:
            db = str(Path(temp) / 'radar.sqlite3')
            main(['documents-migrate', '--db', db])
            with closing(sqlite3.connect(db)) as conn:
                conn.execute("INSERT INTO concursos_identidade VALUES ('c','2026-10-10T00:00:00+00:00')")
                conn.execute("INSERT INTO observacoes_concurso VALUES ('o','c','https://guajaramirim.ro.gov.br/a/','1/2026','2026-10-10T00:00:00+00:00')")
                conn.commit()
            url = 'https://guajaramirim.ro.gov.br/edital.html'
            doc = register_document(db, dict(observation_id='o', kind='edital', official_url=url,
                title='Edital', discovery_url=url, discovery_method='manual',
                discovered_at='2026-10-10T00:00:00+00:00'))
            version = record_version(db, doc, b'<p>Inscricoes de 31 a 32/02/2026.</p>', dict(
                fetched_at='2026-10-10T01:00:00+00:00', fetched_url=url, content_type='text/html'))
            main(['documents-analyze', '--db', db, '--version-id', version])
            detail = get_competition_details(db, 'c')
            self.assertEqual(detail['proposals'], [])
            self.assertEqual(detail['documents'][0]['versions'][0]['error_code'], 'invalid_registration_period')
            self.assertTrue(any(e['event_type'] == 'falha' for e in detail['documents'][0]['events']))

    def test_migration_and_sync_are_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            db = str(Path(temp) / 'radar.sqlite3')
            with closing(sqlite3.connect(db)) as conn:
                conn.execute('CREATE TABLE concursos (source_url TEXT, competition_id TEXT, role TEXT)')
                conn.execute("INSERT INTO concursos VALUES ('https://guajaramirim.ro.gov.br/a/','1/2026','Professor')")
                conn.commit()
            with closing(sqlite3.connect(db)) as conn:
                self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 0)
            main(['documents-migrate', '--db', db])
            self.assertEqual(list_competition_identities(db), [])
            main(['documents-sync', '--db', db])
            before = list_competition_identities(db)
            main(['documents-sync', '--db', db])
            self.assertEqual(list_competition_identities(db), before)

    def test_local_commands_analyze_review_and_select_without_changing_v1(self):
        with tempfile.TemporaryDirectory() as temp:
            db = str(Path(temp) / 'radar.sqlite3')
            main(['documents-migrate', '--db', db])
            with closing(sqlite3.connect(db)) as conn:
                conn.execute("INSERT INTO concursos_identidade VALUES ('c','2026-10-10T00:00:00+00:00')")
                conn.execute("INSERT INTO observacoes_concurso VALUES ('o','c','https://guajaramirim.ro.gov.br/a/','1/2026','2026-10-10T00:00:00+00:00')")
                conn.commit()
            url = 'https://guajaramirim.ro.gov.br/edital.html'
            main(['documents-register','--db',db,'--observation-id','o','--kind','edital','--url',url,'--title','Edital'])
            doc = get_competition_details(db, 'c')['documents'][0]['id']
            version = record_version(db, doc, b'<p>10 vagas imediatas.</p>', dict(fetched_at='2026-10-10T00:01:00+00:00',
                fetched_url=url, content_type='text/html'))
            main(['documents-analyze','--db',db,'--version-id',version])
            with self.assertRaises(ValueError):
                main(['documents-analyze','--db',db,'--version-id',version])
            self.assertEqual(len(get_competition_details(db, 'c')['proposals']), 1)
            proposal = get_competition_details(db, 'c')['proposals'][0]['id']
            self.assertEqual(get_competition_details(db, 'c')['current_values'], [])
            main(['documents-review','--db',db,'--proposal-id',proposal,'--decision','validado',
                  '--reviewer','Ana','--reason','Conferido no texto'])
            main(['documents-select','--db',db,'--proposal-id',proposal,
                  '--reviewer','Ana','--reason','Escolha humana'])
            main(['documents-coverage','--db',db,'--contest-id','c','--state','parcial','--checked-url',url,
                  '--reviewer','Ana','--checked-at','2026-10-10T00:02:00+00:00','--note','Somente edital'])
            detail = get_competition_details(db, 'c')
            self.assertEqual(detail['current_values'][0]['evidence']['quote'], '10 vagas imediatas')
            self.assertEqual(detail['coverage']['state'], 'parcial')
