"""Aquisição controlada de editais oficiais (Fase 33) — offline, com fetcher injetado."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from radar import acquisition
from radar.document_store import migrate_document_schema

NOW = "2026-10-17T12:00:00+00:00"

DETAIL_HTML = """<html><head><title>Concurso Teste | FGV</title></head><body>
<h1>Concurso Publico de Teste</h1>
<div class="field--name-field-concurso-status"><small>Em Andamento</small></div>
<div class="paragraph paragraph--type--texto-data"><a href="https://conhecimento.fgv.br/sites/default/files/concursos/edital.pdf">Edital</a><time datetime="2026-09-01">01/09/2026</time></div>
<div class="paragraph paragraph--type--texto-data"><a href="https://conhecimento.fgv.br/sites/default/files/concursos/1-retificacao.pdf">1a Retificacao</a><time datetime="2026-09-10">10/09/2026</time></div>
<div class="paragraph paragraph--type--texto-data"><a href="https://conhecimento.fgv.br/sites/default/files/concursos/resultado.pdf">Resultado preliminar</a><time datetime="2026-10-01">01/10/2026</time></div>
<div class="paragraph paragraph--type--texto-data"><a href="https://conhecimento.fgv.br/sites/default/files/concursos/inscritos.pdf">Retificacao - Relacao de inscritos provisorios</a><time datetime="2026-10-02">02/10/2026</time></div>
</body></html>"""


def make_db():
    tmp = tempfile.TemporaryDirectory()
    db = str(Path(tmp.name) / "radar.sqlite3")
    migrate_document_schema(db)
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("INSERT INTO concursos_identidade (id,created_at,estado_identidade) "
                     "VALUES ('c1',?,'certame')", (NOW,))
        conn.execute("INSERT INTO concursos_identidade (id,created_at,estado_identidade) "
                     "VALUES ('c2',?,'certame')", (NOW,))
        conn.execute("INSERT INTO observacoes_concurso "
                     "(id,contest_id,source_url,competition_id,observed_at) "
                     "VALUES ('o1','c1','https://conhecimento.fgv.br/concursos/teste','teste',?)",
                     (NOW,))
        conn.execute("INSERT INTO observacoes_concurso "
                     "(id,contest_id,source_url,competition_id,observed_at) "
                     "VALUES ('o2','c2','https://www.pciconcursos.com.br/noticias/x',"
                     "'pciconcursos',?)", (NOW,))
    return tmp, db


class AcquisitionTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def test_alvos_so_de_fonte_oficial_habilitada(self):
        report = acquisition.targets(self.db)
        self.assertEqual(report["total"], 1)
        item = report["itens"][0]
        self.assertEqual(item["contest_id"], "c1")
        self.assertEqual(item["source_id"], "fgv-conhecimento")
        self.assertTrue(item["pode_adquirir"])
        self.assertIn("nenhum documento localizado", " ".join(item["motivos"]))

    def test_plano_filtra_resultado_e_nao_grava(self):
        with mock.patch("radar.fgv_source.fetch_detail", return_value=DETAIL_HTML):
            plan = acquisition.plan_acquisition(self.db, max_contests=1,
                                                max_documents_per_contest=5)
        self.assertEqual(plan["concursos"], 1)
        self.assertEqual(plan["documentos_planejados"], 2)
        types = [doc["document_type"] for doc in plan["itens"][0]["documentos"]]
        self.assertEqual(types, ["edital_abertura", "retificacao"])
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM documentos").fetchone()[0], 0)

    def test_lista_nominal_e_ignorada_mesmo_rotulada_retificacao(self):
        with mock.patch("radar.fgv_source.fetch_detail", return_value=DETAIL_HTML):
            plan = acquisition.plan_acquisition(self.db, max_contests=1,
                                                max_documents_per_contest=5)
        item = plan["itens"][0]
        titles = [doc["title"] for doc in item["documentos"]]
        self.assertEqual(len(titles), 2)
        self.assertNotIn("Retificacao - Relacao de inscritos provisorios", titles)
        self.assertEqual(len(item["nominais_ignorados"]), 1)

    def test_execucao_registra_baixa_e_grava_checkpoint(self):
        checkpoint = Path(self.tmp.name) / "checkpoint.json"
        with mock.patch("radar.fgv_source.fetch_detail", return_value=DETAIL_HTML), \
             mock.patch("radar.document_download.download_document",
                        return_value="ver-fake"):
            result = acquisition.execute_acquisition(
                self.db, max_contests=1, max_documents_per_contest=5, analyze=False,
                checkpoint=str(checkpoint), apply=True)
        self.assertTrue(result["executado"])
        self.assertEqual(result["documentos_registrados"], 2)
        self.assertEqual(result["documentos_baixados"], 2)
        self.assertEqual(result["consumo"]["status"], "concluida")
        with closing(sqlite3.connect(self.db)) as conn:
            urls = {row[0] for row in conn.execute("SELECT official_url FROM documentos")}
        self.assertIn("https://conhecimento.fgv.br/sites/default/files/concursos/edital.pdf", urls)
        self.assertFalse(any("resultado.pdf" in url for url in urls))
        saved = json.loads(checkpoint.read_text(encoding="utf-8"))
        self.assertEqual(saved["source_id"], "fgv-conhecimento")
        self.assertEqual(saved["next_index"], 1)

    def test_execucao_e_idempotente(self):
        with mock.patch("radar.fgv_source.fetch_detail", return_value=DETAIL_HTML), \
             mock.patch("radar.document_download.download_document",
                        return_value="ver-fake"):
            acquisition.execute_acquisition(self.db, max_contests=1,
                                            max_documents_per_contest=5, analyze=False,
                                            apply=True, now=NOW)
            second = acquisition.execute_acquisition(self.db, max_contests=1,
                                                     max_documents_per_contest=5,
                                                     analyze=False, apply=True,
                                                     now="2026-10-18T12:00:00+00:00")
        self.assertEqual(second["documentos_registrados"], 0)
        self.assertEqual(second["documentos_baixados"], 0)

    def test_intervalo_minimo_entre_execucoes_e_respeitado(self):
        from radar.budget import BudgetError
        with mock.patch("radar.fgv_source.fetch_detail", return_value=DETAIL_HTML), \
             mock.patch("radar.document_download.download_document",
                        return_value="ver-fake"):
            acquisition.execute_acquisition(self.db, max_contests=1,
                                            max_documents_per_contest=5, analyze=False,
                                            apply=True, now=NOW)
            with self.assertRaises(BudgetError):
                acquisition.execute_acquisition(self.db, max_contests=1,
                                                max_documents_per_contest=5,
                                                analyze=False, apply=True,
                                                now="2026-10-17T13:00:00+00:00")

    def test_limites_invalidos_sao_recusados(self):
        for kwargs in ({"max_contests": 0}, {"max_contests": -1},
                       {"max_documents_per_contest": 0},
                       {"max_contests": 51}, {"max_documents_per_contest": 21}):
            with self.assertRaises(ValueError):
                acquisition.plan_acquisition(self.db, **kwargs)

    def test_fonte_sem_adaptador_ou_nao_habilitada_e_recusada(self):
        with self.assertRaises(ValueError):
            acquisition.plan_acquisition(self.db, source_id="pci")

    def test_dry_run_padrao_nao_executa(self):
        with mock.patch("radar.fgv_source.fetch_detail", return_value=DETAIL_HTML):
            result = acquisition.execute_acquisition(self.db, max_contests=1)
        self.assertTrue(result["dry_run"])
        self.assertNotIn("executado", result)

    def test_titulos_de_lista_nominal_variantes(self):
        from radar.document_types import is_nominal_title
        for title in ("Retificação - Lista de classificados",
                      "Retificação - Relação de aprovados",
                      "Retificação da Nota Final dos Candidatos",
                      "Resultado preliminar",
                      "Relação de inscrições homologadas"):
            self.assertTrue(is_nominal_title(title), title)
        for title in ("1ª Retificação", "2ª Retificação do Edital",
                      "Retificação do cronograma", "Edital de Abertura",
                      "Edital (retificado em 29/01/2026)"):
            self.assertFalse(is_nominal_title(title), title)

    def test_checkpoint_retoma_e_nao_reconsulta(self):
        # Dois certames sem documento: o primeiro já foi concluído no checkpoint.
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO concursos_identidade (id,created_at,estado_identidade) "
                         "VALUES ('c9',?,'certame')", (NOW,))
            conn.execute("INSERT INTO observacoes_concurso "
                         "(id,contest_id,source_url,competition_id,observed_at) "
                         "VALUES ('o9','c9','https://conhecimento.fgv.br/concursos/outro',"
                         "'outro',?)", (NOW,))
        checkpoint = Path(self.tmp.name) / "resume.json"
        checkpoint.write_text(json.dumps({
            "source_id": "fgv-conhecimento", "contest_ids": None, "next_index": 1,
            "registered": 2, "downloaded": 2,
            "itens": [{"contest_id": "c1", "observation_id": "o1", "title": "Teste",
                       "source_status": "Em Andamento", "documentos_encontrados": 2,
                       "documentos_novos": 0, "documentos": [], "nominais_ignorados": []}]}),
            encoding="utf-8")
        calls = []

        def fake_detail(slug):
            calls.append(slug)
            return DETAIL_HTML

        with mock.patch("radar.fgv_source.fetch_detail", side_effect=fake_detail), \
             mock.patch("radar.document_download.download_document",
                        return_value="ver-fake"):
            result = acquisition.execute_acquisition(
                self.db, max_contests=2, max_documents_per_contest=5, analyze=False,
                checkpoint=str(checkpoint), apply=True, now=NOW)
        self.assertEqual(result["retomado_de"], 1)
        self.assertEqual(len(calls), 1)  # o primeiro concurso não foi reconsultado

    def test_checkpoint_de_outra_selecao_e_recusado(self):
        checkpoint = Path(self.tmp.name) / "outro.json"
        checkpoint.write_text(json.dumps({"source_id": "fgv-conhecimento",
                                          "contest_ids": ["x"], "next_index": 1}),
                              encoding="utf-8")
        with self.assertRaises(ValueError):
            acquisition.execute_acquisition(self.db, max_contests=1,
                                            checkpoint=str(checkpoint), apply=True,
                                            now=NOW)

    def test_falha_de_rede_nao_interrompe_plano(self):
        with mock.patch("radar.fgv_source.fetch_detail", side_effect=OSError("sem rede")):
            plan = acquisition.plan_acquisition(self.db, max_contests=1)
        self.assertEqual(plan["concursos"], 0)
        self.assertEqual(plan["falhas"][0]["code"], "OSError")


if __name__ == "__main__":
    unittest.main()
