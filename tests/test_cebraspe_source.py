"""Testes da fonte oficial Cebraspe (Centro Brasileiro de Pesquisa em Avaliação e Seleção)."""

import unittest
from radar import cebraspe_source as cebraspe


def make_catalog_html(entries):
    links = "".join(
        f'<div class="card-concurso">'
        f'<h3><a href="https://www.cebraspe.org.br/concursos/{slug}/">{title}</a></h3>'
        f'</div>'
        for slug, title in entries
    )
    return f"<html><body><div class='lista-concursos'>{links}</div></body></html>"


def make_detail_html(title, status, docs):
    items = "".join(
        f'<div class="documento-item">'
        f'<span class="data-pub">{date}</span>'
        f'<a href="{url}" class="link-download">{label}</a>'
        f'</div>'
        for date, label, url in docs
    )
    return (
        f"<html><head><title>{title} - Cebraspe</title></head><body>"
        f'<h1 class="titulo-concurso">{title}</h1>'
        f'<span class="status-concurso">{status}</span>'
        f'<div class="arquivos-publicados">{items}</div>'
        f'</body></html>'
    )


class CebraspeCatalogTest(unittest.TestCase):
    def test_parses_catalog_entries(self):
        html = make_catalog_html([
            ("tcu_24_auditor", "TCU - Tribunal de Contas da União 2024"),
            ("tse_24_unificado", "TSE Unificado 2024"),
        ])
        entries = cebraspe.parse_catalog(html)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["slug"], "tcu_24_auditor")
        self.assertEqual(entries[0]["url"], "https://www.cebraspe.org.br/concursos/tcu_24_auditor")
        self.assertEqual(entries[0]["title"], "TCU - Tribunal de Contas da União 2024")
        self.assertEqual(entries[1]["slug"], "tse_24_unificado")

    def test_deduplicates_and_ignores_empty(self):
        html = make_catalog_html([
            ("tcu_24", "TCU"),
            ("tcu_24", "TCU Repetido"),
        ]) + '<a href="/concursos/">Todos os Concursos</a>'
        entries = cebraspe.parse_catalog(html)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["slug"], "tcu_24")

    def test_empty_catalog_raises(self):
        with self.assertRaises(ValueError):
            cebraspe.parse_catalog("")

    def test_detail_url_validation(self):
        self.assertEqual(
            cebraspe.detail_url("tcu_24"),
            "https://www.cebraspe.org.br/concursos/tcu_24"
        )
        with self.assertRaises(ValueError):
            cebraspe.detail_url("http://invalid.url/hack")


class CebraspeDetailTest(unittest.TestCase):
    def test_parses_detail_page(self):
        html = make_detail_html(
            "Concurso Público TCU 2024",
            "Inscrições Abertas",
            [
                ("15/10/2026", "Edital nº 1 - Abertura", "https://www.cebraspe.org.br/concursos/tcu_24/edital_1.pdf"),
                ("20/10/2026", "Edital nº 2 - Retificação", "https://www.cebraspe.org.br/concursos/tcu_24/ret_1.pdf"),
                ("01/11/2026", "Comunicado sobre Isenção", "/concursos/tcu_24/comunicado.pdf"),
            ]
        )
        detail = cebraspe.parse_detail(html)
        self.assertEqual(detail["title"], "Concurso Público TCU 2024")
        self.assertEqual(detail["status"], "Inscrições Abertas")
        self.assertEqual(len(detail["documents"]), 3)
        self.assertEqual(detail["documents"][0]["title"], "Edital nº 1 - Abertura")
        self.assertEqual(detail["documents"][0]["date"], "2026-10-15")
        self.assertTrue(detail["documents"][2]["url"].startswith("https://www.cebraspe.org.br/"))

    def test_classify_document(self):
        self.assertEqual(cebraspe.classify_document("Edital nº 1 - Abertura"), "edital")
        self.assertEqual(cebraspe.classify_document("Edital nº 2 - Retificação"), "retificacao")
        self.assertEqual(cebraspe.classify_document("Edital Consolidado (retificado)"), "edital")
        self.assertEqual(cebraspe.classify_document("Comunicado de Horário"), "outro")
