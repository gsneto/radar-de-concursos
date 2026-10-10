import unittest

from radar.collector import SOURCE_URL
from radar.document_discovery import allowed_document_url, discover_documents


class AuthorizedSourceTest(unittest.TestCase):
    def test_diario_oficial_source_is_authorized_for_document_paths(self):
        self.assertTrue(allowed_document_url("https://www.diariomunicipal.com.br/arom/materia/3E102D15"))
        self.assertTrue(allowed_document_url("https://www.diariomunicipal.com.br/arom/download/materia/3E102D15"))

    def test_other_paths_and_hosts_remain_blocked(self):
        self.assertFalse(allowed_document_url("https://www.diariomunicipal.com.br/qualquer-coisa"))
        self.assertFalse(allowed_document_url("http://www.diariomunicipal.com.br/arom/materia/3E102D15"))
        self.assertFalse(allowed_document_url("https://evil.example/arom/materia/3E102D15"))


class DiscoveryTest(unittest.TestCase):
    def test_official_links_keep_provenance_and_ignore_external_links(self):
        html = '''<article><a href="/edital-concurso-001-2026.pdf">Edital do concurso</a>
        <a href="/retificacao-001-2026.pdf">Retificação do edital</a>
        <a href="/edital-concurso-001-2026.pdf">Edital do concurso</a>
        <a href="https://example.com/retificacao.pdf">Retificação</a>
        <a href="#">Edital</a><a href="/noticia/">Notícia</a></article>'''
        candidates = discover_documents(html, SOURCE_URL, "obs")
        self.assertEqual({c["kind"] for c in candidates}, {"edital", "retificacao"})
        self.assertEqual(len(candidates), 2)
        self.assertTrue(all(c["observation_id"] == "obs" and c["discovery_url"] == SOURCE_URL for c in candidates))

    def test_no_document_links_returns_empty(self):
        self.assertEqual(discover_documents('<article><p>Sem links</p></article>', SOURCE_URL, 'obs'), [])
