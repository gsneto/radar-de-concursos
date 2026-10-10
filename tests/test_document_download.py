import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from radar.document_download import download_document
from radar.document_store import get_competition_details, migrate_document_schema, register_document


class DownloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / 'db.sqlite3')
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("INSERT INTO concursos_identidade VALUES ('contest','2026-10-10T00:00:00+00:00')")
            conn.execute("INSERT INTO observacoes_concurso VALUES ('obs','contest','https://guajaramirim.ro.gov.br/a/','1/2026','2026-10-10T00:00:00+00:00')")
            conn.commit()
        self.url = 'https://guajaramirim.ro.gov.br/e.pdf'
        self.doc = register_document(self.db, dict(observation_id='obs', kind='edital', official_url=self.url,
                  title='Edital', discovery_url='https://guajaramirim.ro.gov.br/a/',
                  discovery_method='manual', discovered_at='2026-10-10T00:00:00+00:00'))

    def test_download_records_integrity_and_preserves_success_after_rejected_private_peer(self):
        def good(url, timeout, limit):
            return dict(status=200, final_url=url, content_type='application/pdf', peer_ip='8.8.8.8',
                        body=b'%PDF-valid-example')
        version = download_document(self.db, self.doc, transport=good)
        def private(url, timeout, limit):
            return dict(status=200, final_url=url, content_type='application/pdf', peer_ip='127.0.0.1', body=b'evil')
        with self.assertRaises(ValueError):
            download_document(self.db, self.doc, transport=private)
        details = get_competition_details(self.db, 'contest')['documents'][0]
        self.assertEqual(details['versions'][0]['id'], version)
        self.assertEqual(len(details['versions']), 1)
        self.assertEqual([a['state'] for a in details['download_attempts']], ['concluido', 'falhou'])

    def test_rejects_payload_disguised_as_pdf_without_storing_version(self):
        def disguised(url, timeout, limit):
            return dict(status=200, final_url=url, content_type='application/pdf', peer_ip='8.8.8.8',
                        body=b'<html>not a PDF</html>')
        with self.assertRaises(ValueError):
            download_document(self.db, self.doc, transport=disguised)
        details = get_competition_details(self.db, 'contest')['documents'][0]
        self.assertEqual(details['versions'], [])
        self.assertEqual(details['download_attempts'][0]['state'], 'falhou')

    def test_rejects_html_response_to_pdf_document(self):
        def unexpected(url, timeout, limit):
            return dict(status=200, final_url=url, content_type='text/html', peer_ip='8.8.8.8',
                        body=b'<html><p>Access denied</p></html>')
        with self.assertRaisesRegex(ValueError, 'HTML inesperado'):
            download_document(self.db, self.doc, transport=unexpected)
        detail = get_competition_details(self.db, 'contest')['documents'][0]
        self.assertEqual(detail['versions'], [])
        self.assertEqual(detail['download_attempts'][0]['state'], 'falhou')

    def test_rejects_redirect_of_pdf_to_unrelated_html_page(self):
        def login(url, timeout, limit):
            return dict(status=200, final_url='https://guajaramirim.ro.gov.br/login.html',
                        content_type='text/html', peer_ip='8.8.8.8', body=b'<p>10 vagas imediatas</p>')
        with self.assertRaises(ValueError):
            download_document(self.db, self.doc, transport=login)
        self.assertEqual(get_competition_details(self.db, 'contest')['documents'][0]['versions'], [])

    def test_identical_content_is_idempotent_and_changed_content_links_previous(self):
        html_doc = register_document(self.db, dict(
            observation_id='obs', kind='edital',
            official_url='https://guajaramirim.ro.gov.br/edital.html', title='Edital HTML',
            discovery_url='https://guajaramirim.ro.gov.br/a/', discovery_method='manual',
            discovered_at='2026-10-10T00:00:00+00:00'))
        def fixed(body):
            def transport(url, timeout, limit):
                return dict(status=200, final_url=url, content_type='text/html',
                            peer_ip='8.8.8.8', body=body)
            return transport
        first = download_document(self.db, html_doc, transport=fixed(b'<p>mesmo</p>'))
        self.assertEqual(download_document(self.db, html_doc, transport=fixed(b'<p>mesmo</p>')), first)
        second = download_document(self.db, html_doc, transport=fixed(b'<p>mudou</p>'))
        self.assertNotEqual(second, first)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM versoes_documento').fetchone()[0], 2)
            self.assertEqual(conn.execute(
                'SELECT previous_version_id FROM versoes_documento WHERE id=?', (second,)).fetchone()[0], first)

    def test_default_transport_is_present_and_rejects_private_dns_before_connect(self):
        from unittest.mock import patch
        import socket
        from radar.document_download import fetch_document

        with patch('radar.document_download.socket.getaddrinfo', return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))
        ]), patch('radar.document_download.socket.create_connection') as connect:
            with self.assertRaises(ValueError):
                fetch_document(self.url, timeout=15, limit=1024)
            connect.assert_not_called()

    def test_approved_redirect_is_recorded_without_replacing_primary_url(self):
        redirected = 'https://guajaramirim.ro.gov.br/edital-publicado.pdf'
        def moved(url, timeout, limit):
            return dict(status=200, final_url=redirected, content_type='application/pdf', peer_ip='8.8.8.8',
                        body=b'%PDF-1.4\nvalid')
        download_document(self.db, self.doc, transport=moved)
        details = get_competition_details(self.db, 'contest')['documents'][0]
        self.assertEqual(details['official_url'], self.url)
        self.assertEqual(details['final_url'], redirected)
        self.assertEqual(details['versions'][0]['fetched_url'], redirected)

    def test_external_redirect_is_rejected_without_version(self):
        def moved(url, timeout, limit):
            return dict(status=200, final_url='https://example.com/edital.pdf', content_type='application/pdf',
                        peer_ip='8.8.8.8', body=b'%PDF-1.4\nvalid')
        with self.assertRaises(ValueError):
            download_document(self.db, self.doc, transport=moved)
        self.assertEqual(get_competition_details(self.db, 'contest')['documents'][0]['versions'], [])

    def test_default_transport_does_not_connect_to_external_redirect(self):
        from unittest.mock import patch
        import socket
        from radar.document_download import fetch_document

        class Redirect:
            status = 302
            def getheader(self, key, default=None):
                return 'https://evil.example/private.pdf' if key == 'Location' else default

        class Connection:
            sock = type('Peer', (), {'getpeername': lambda self: ('8.8.8.8', 443)})()
            def __init__(self, *args):
                connections.append(args)
            def request(self, *args, **kwargs):
                pass
            def getresponse(self):
                return Redirect()
            def close(self):
                pass

        connections = []
        with patch('radar.document_download.socket.getaddrinfo', return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 443))
        ]), patch('radar.document_download._PinnedHTTPSConnection', Connection):
            with self.assertRaises(ValueError):
                fetch_document(self.url, timeout=15, limit=1024)
        self.assertEqual(len(connections), 1)
