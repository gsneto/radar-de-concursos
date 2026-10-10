"""Testes do conector HTML da fonte oficial de Guajará-Mirim (Task 1)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError

from radar import collector

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "guajara-oficial.html"
VERIFIED_AT = "2026-10-09T12:00:00-04:00"

REQUIRED_KEYS = {
    "competition_id",
    "competition",
    "agency",
    "role",
    "education",
    "immediate_vacancies",
    "reserve_vacancies",
    "indigenous_vacancies",
    "registration_start",
    "registration_end",
    "registration_status",
    "exam_date",
    "exam_location",
    "work_location",
    "source_name",
    "source_url",
    "evidence_url",
    "verified_at",
}

EXPECTED_ROLES = [
    ("Professor de Educação Infantil", 69),
    ("Professor dos Anos Iniciais do Ensino Fundamental", 32),
    ("Professor Intérprete de Libras", 3),
    ("Professor de Braille", 3),
]

# Variante sintética: declara zero explícito (vagas imediatas e reserva),
# informa local de prova e de exercício distintos e usa período numérico.
# Não corresponde à fonte real.
SYNTHETIC_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Prefeitura de Guajará-Mirim abre inscrições para concurso público da educação com 5 vagas</title>
</head>
<body>
<article>
  <h1>Prefeitura de Guajará-Mirim abre inscrições para concurso público da educação com 5 vagas</h1>
  <p>A Prefeitura Municipal de Guajará-Mirim publicou o concurso público nº 002/2026 para cargos da educação.</p>
  <p>As inscrições foram realizadas de 10 a 30/07/2026.</p>
  <h2>Cargos e vagas</h2>
  <ul>
    <li><strong>5</strong> para Professor de Educação Infantil;</li>
    <li><strong>0</strong> para Professor de Braille.</li>
  </ul>
  <p>Não haverá cadastro de reserva: 0 vagas.</p>
  <p>Local de prova: Porto Velho/RO.</p>
  <p>Local de exercício: Guajará-Mirim/RO.</p>
</article>
</body>
</html>
"""


class _FakeHeaders:
    def __init__(self, charset):
        self._charset = charset

    def get_content_charset(self):
        return self._charset


class _FakeResponse:
    """Resposta HTTP mínima que imita o objeto retornado por urlopen."""

    def __init__(self, body, charset=None, url=None):
        self._body = body
        self.headers = _FakeHeaders(charset)
        self._url = url or collector.SOURCE_URL

    def geturl(self):
        return self._url

    def read(self, size=-1):
        if size is None or size < 0:
            return self._body
        return self._body[:size]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class CollectOfficialFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = FIXTURE_PATH.read_text(encoding="utf-8")

    def setUp(self):
        self.records = collector.collect(self.html, VERIFIED_AT)

    def test_returns_four_records(self):
        self.assertEqual(len(self.records), 4)

    def test_roles_and_immediate_vacancies_match_source(self):
        observed = [(r["role"], r["immediate_vacancies"]) for r in self.records]
        self.assertEqual(observed, EXPECTED_ROLES)

    def test_every_record_has_exact_contract_keys(self):
        for record in self.records:
            self.assertEqual(set(record.keys()), REQUIRED_KEYS)

    def test_unknown_fields_remain_none(self):
        for record in self.records:
            self.assertIsNone(record["reserve_vacancies"])
            self.assertIsNone(record["indigenous_vacancies"])
            self.assertIsNone(record["education"])
            self.assertIsNone(record["exam_date"])
            self.assertIsNone(record["exam_location"])
            self.assertIsNone(record["work_location"])

    def test_shared_fields_match_confirmed_facts(self):
        for record in self.records:
            self.assertEqual(record["competition_id"], "001/2026")
            self.assertEqual(record["competition"], "Concurso público da educação")
            self.assertEqual(
                record["agency"], "Prefeitura Municipal de Guajará-Mirim/RO (SEMED)"
            )
            self.assertEqual(record["registration_start"], "2026-07-10")
            self.assertEqual(record["registration_end"], "2026-07-30")
            self.assertEqual(
                record["registration_status"], "encerradas conforme período divulgado"
            )
            self.assertEqual(
                record["source_name"], "Prefeitura Municipal de Guajará-Mirim/RO"
            )
            self.assertEqual(record["verified_at"], VERIFIED_AT)

    def test_source_url_is_the_official_article(self):
        expected = (
            "https://guajaramirim.ro.gov.br/"
            "prefeitura-de-guajara-mirim-abre-inscricoes-para-concurso-publico-"
            "da-educacao-com-107-vagas-e-cadastro-de-reserva/"
        )
        self.assertEqual(collector.SOURCE_URL, expected)
        for record in self.records:
            self.assertEqual(record["source_url"], expected)
            self.assertEqual(record["evidence_url"], expected)

    def test_registration_dates_are_iso_from_textual_period(self):
        for record in self.records:
            self.assertEqual(record["registration_start"], "2026-07-10")
            self.assertEqual(record["registration_end"], "2026-07-30")

    def test_roles_and_vacancies_follow_source_order(self):
        observed = [(r["role"], r["immediate_vacancies"]) for r in self.records]
        self.assertEqual(observed, EXPECTED_ROLES)

    def test_fixture_does_not_use_invented_role_or_numeric_period_format(self):
        self.assertNotIn(": 69 vagas", self.html)
        self.assertNotIn("10 a 30/07/2026", self.html)
        self.assertIn("entre 10 e 30 de julho de 2026", self.html)
        self.assertIn("<strong>69</strong>", self.html)

    def test_fixture_uses_official_para_role_format(self):
        # O HTML vivo lista os cargos como ``número + "para" + cargo``.
        # A fixture precisa ser fiel a esse conector, não a uma variante.
        for count, role in (
            ("69", "Professor de Educação Infantil"),
            ("32", "Professor dos Anos Iniciais do Ensino Fundamental"),
            ("3", "Professor Intérprete de Libras"),
            ("3", "Professor de Braille"),
        ):
            self.assertIn(f"<strong>{count}</strong> para {role}", self.html)


class CollectRegistrationContextTest(unittest.TestCase):
    """O período só vale quando aparece no texto de inscrições."""

    @classmethod
    def setUpClass(cls):
        cls.html = FIXTURE_PATH.read_text(encoding="utf-8")

    def test_period_outside_article_registration_text_raises(self):
        without_period = self.html.replace(
            "As inscrições foram realizadas exclusivamente pela internet, "
            "de forma gratuita, entre 10 e 30 de julho de 2026.",
            "Consulte o edital publicado para mais informações.",
        )
        broken = without_period.replace(
            "</body>",
            "<footer>As inscrições foram realizadas entre 10 e 30 de julho de 2026.</footer></body>",
        )
        self.assertNotEqual(broken, self.html)
        with self.assertRaisesRegex(
            ValueError, "período de inscrições não encontrado"
        ):
            collector.collect(broken, VERIFIED_AT)

    def test_registration_period_present_in_registration_text_is_accepted(self):
        records = collector.collect(self.html, VERIFIED_AT)
        self.assertEqual(records[0]["registration_start"], "2026-07-10")
        self.assertEqual(records[0]["registration_end"], "2026-07-30")

    def test_impossible_registration_date_is_rejected(self):
        invalid = self.html.replace(
            "10 e 30 de julho de 2026", "31 e 32 de fevereiro de 2026"
        )
        self.assertNotEqual(invalid, self.html)
        with self.assertRaises(ValueError):
            collector.collect(invalid, VERIFIED_AT)

    def test_reversed_registration_period_is_rejected(self):
        reversed_period = self.html.replace(
            "10 e 30 de julho de 2026", "30 e 10 de julho de 2026"
        )
        self.assertNotEqual(reversed_period, self.html)
        with self.assertRaises(ValueError):
            collector.collect(reversed_period, VERIFIED_AT)

    def test_negated_registration_realization_does_not_mark_closed(self):
        negated = self.html.replace(
            "As inscrições foram realizadas exclusivamente pela internet, ",
            "As inscrições não foram realizadas exclusivamente pela internet, ",
        )
        self.assertNotEqual(negated, self.html)
        records = collector.collect(negated, "2026-10-09T12:00:00-04:00")
        for record in records:
            self.assertIsNone(record["registration_status"])

    def test_registration_status_is_not_closed_on_final_day(self):
        records = collector.collect(self.html, "2026-07-30T12:00:00-04:00")
        for record in records:
            self.assertIsNone(record["registration_status"])

    def test_registration_period_requires_spaces_around_connector(self):
        malformed = self.html.replace(
            "entre 10 e 30 de julho de 2026",
            "entre 10e30 de julho de 2026",
        )
        self.assertNotEqual(malformed, self.html)
        with self.assertRaisesRegex(ValueError, "período de inscrições não encontrado"):
            collector.collect(malformed, VERIFIED_AT)


class CollectSyntheticVariantTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = collector.collect(SYNTHETIC_HTML, VERIFIED_AT)

    def test_explicit_zero_immediate_vacancies_is_zero_not_none(self):
        braille = next(r for r in self.records if r["role"] == "Professor de Braille")
        self.assertIsNotNone(braille["immediate_vacancies"])
        self.assertEqual(braille["immediate_vacancies"], 0)

    def test_explicit_zero_reserve_is_zero_while_absent_is_none(self):
        for record in self.records:
            self.assertIsNotNone(record["reserve_vacancies"])
            self.assertEqual(record["reserve_vacancies"], 0)
        official = collector.collect(
            FIXTURE_PATH.read_text(encoding="utf-8"), VERIFIED_AT
        )
        for record in official:
            self.assertIsNone(record["reserve_vacancies"])

    def test_exam_location_is_kept_separate_from_work_location(self):
        for record in self.records:
            self.assertEqual(record["exam_location"], "Porto Velho/RO")
            self.assertEqual(record["work_location"], "Guajará-Mirim/RO")
            self.assertNotEqual(record["exam_location"], record["work_location"])

    def test_global_indigenous_count_is_not_repeated_for_each_role(self):
        html = SYNTHETIC_HTML.replace(
            "<p>Local de prova:",
            "<p>Indígenas: 2 vagas em todo o concurso, distribuição por cargo não informada.</p>\n"
            "  <p>Local de prova:",
        )
        records = collector.collect(html, VERIFIED_AT)
        self.assertEqual(len(records), 2)
        self.assertTrue(all(row["indigenous_vacancies"] is None for row in records))

    def test_global_reserve_count_is_not_repeated_for_each_role(self):
        html = SYNTHETIC_HTML.replace(
            "Não haverá cadastro de reserva: 0 vagas.",
            "Cadastro de reserva: 5 vagas em todo o concurso, distribuição por cargo não informada.",
        )
        records = collector.collect(html, VERIFIED_AT)
        self.assertEqual(len(records), 2)
        self.assertTrue(all(row["reserve_vacancies"] is None for row in records))


class CollectRejectsIncompleteDocumentsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = FIXTURE_PATH.read_text(encoding="utf-8")

    def test_empty_html_raises(self):
        with self.assertRaises(ValueError):
            collector.collect("", VERIFIED_AT)

    def test_missing_title_raises(self):
        broken = re.sub(r"<title>.*?</title>", "", self.html, flags=re.DOTALL)
        broken = re.sub(r"<h1>.*?</h1>", "", broken, flags=re.DOTALL)
        with self.assertRaises(ValueError):
            collector.collect(broken, VERIFIED_AT)

    def test_missing_competition_id_raises(self):
        broken = self.html.replace("nº 001/2026", "concurso público")
        with self.assertRaises(ValueError):
            collector.collect(broken, VERIFIED_AT)

    def test_missing_role_list_raises(self):
        broken = re.sub(r"<ul>.*?</ul>", "", self.html, flags=re.DOTALL)
        with self.assertRaises(ValueError):
            collector.collect(broken, VERIFIED_AT)

    def test_altered_role_list_raises_without_partial_records(self):
        broken = self.html.replace(
            "<li><strong>3</strong> para Professor de Braille.</li>", ""
        )
        self.assertNotEqual(broken, self.html)
        with self.assertRaises(ValueError):
            collector.collect(broken, VERIFIED_AT)

    def test_duplicate_role_raises(self):
        item = "<li><strong>3</strong> para Professor de Braille.</li>"
        broken = self.html.replace(item, item + item)
        self.assertNotEqual(broken, self.html)
        with self.assertRaises(ValueError):
            collector.collect(broken, VERIFIED_AT)

    def test_role_items_require_official_para_connector(self):
        # O formato vivo é ``número + "para" + cargo``. Remover o conector
        # altera a estrutura da lista e deve falhar fechado, em vez de casar
        # por permissividade e devolver os quatro registros.
        altered = self.html.replace(" para Professor", " Professor")
        self.assertNotEqual(altered, self.html)
        with self.assertRaisesRegex(
            ValueError, "item de lista numerado fora do padrão"
        ):
            collector.collect(altered, VERIFIED_AT)

    def test_numeric_list_item_outside_role_pattern_fails_closed(self):
        # Uma edição composta poderia preservar a soma do título; ainda assim,
        # lista numerada fora do padrão oficial deve ser revisão manual.
        altered = self.html.replace(
            "<li><strong>69</strong> para Professor de Educação Infantil;</li>",
            "<li><strong>69</strong> Professor de Educação Infantil;</li>",
        )
        altered = altered.replace(
            "<li><strong>3</strong> para Professor de Braille.</li>",
            "<li><strong>72</strong> para Professor de Braille.</li>",
        )
        self.assertNotEqual(altered, self.html)
        with self.assertRaisesRegex(ValueError, "item de lista numerado fora do padrão"):
            collector.collect(altered, VERIFIED_AT)


class FetchOfficialTest(unittest.TestCase):
    def test_rejects_redirect_to_non_official_host(self):
        response = _FakeResponse(b"<html>not official</html>", url="https://example.com/clone")
        with mock.patch.object(collector, "urlopen", return_value=response):
            with self.assertRaisesRegex(ValueError, "redirecionamento"):
                collector.fetch_official()

    def test_rejects_redirect_to_another_article_on_official_host(self):
        response = _FakeResponse(
            b"<html>another article</html>",
            url="https://guajaramirim.ro.gov.br/outra-noticia/",
        )
        with mock.patch.object(collector, "urlopen", return_value=response):
            with self.assertRaisesRegex(ValueError, "redirecionamento"):
                collector.fetch_official()

    def test_decodes_response_body_and_enforces_timeout(self):
        body = "<html><title>ok</title></html>".encode("utf-8")
        response = _FakeResponse(body, charset="utf-8")
        with mock.patch.object(collector, "urlopen", return_value=response) as fake:
            result = collector.fetch_official()
        self.assertEqual(result, "<html><title>ok</title></html>")
        fake.assert_called_once()
        timeout = fake.call_args.kwargs.get("timeout")
        self.assertIsNotNone(timeout)
        self.assertGreater(timeout, 0)

    def test_raises_on_network_error_instead_of_faking_success(self):
        with mock.patch.object(collector, "urlopen", side_effect=URLError("offline")):
            with self.assertRaises(URLError):
                collector.fetch_official()

    def test_raises_on_http_error(self):
        error = HTTPError(collector.SOURCE_URL, 503, "Service Unavailable", {}, None)
        with mock.patch.object(collector, "urlopen", side_effect=error):
            with self.assertRaises(HTTPError):
                collector.fetch_official()

    def test_rejects_oversized_response(self):
        response = _FakeResponse(b"x" * 3_000_000, charset="utf-8")
        with mock.patch.object(collector, "urlopen", return_value=response):
            with self.assertRaises(ValueError):
                collector.fetch_official()

    def test_rejects_non_https_source_url(self):
        with mock.patch.object(
            collector, "SOURCE_URL", "http://guajaramirim.ro.gov.br/artigo/"
        ):
            with mock.patch.object(collector, "urlopen") as fake:
                with self.assertRaises(ValueError):
                    collector.fetch_official()
                fake.assert_not_called()

    def test_rejects_unexpected_host(self):
        with mock.patch.object(
            collector, "SOURCE_URL", "https://example.com/artigo/"
        ):
            with mock.patch.object(collector, "urlopen") as fake:
                with self.assertRaises(ValueError):
                    collector.fetch_official()
                fake.assert_not_called()


if __name__ == "__main__":
    unittest.main()
