"""Cobertura oficial, conflitos de versão e campos decisivos (Fase 33)."""

import hashlib
import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

from radar import coverage_states, decisive_fields, version_conflicts
from radar.document_store import migrate_document_schema
from radar.server import create_server

NOW = "2026-10-17T12:00:00+00:00"
LATER = "2026-10-20T12:00:00+00:00"


def make_db():
    tmp = tempfile.TemporaryDirectory()
    db = str(Path(tmp.name) / "radar.sqlite3")
    migrate_document_schema(db)
    with closing(sqlite3.connect(db)) as conn, conn:
        for contest_id, estado in (("c1", "certame"), ("c2", "certame"),
                                   ("c3", "certame"), ("c4", "certame"),
                                   ("c5", "certame"), ("c6", "certame"),
                                   ("c7", "certame"), ("cont", "container_fonte")):
            conn.execute("INSERT INTO concursos_identidade (id,created_at,estado_identidade) "
                         "VALUES (?,?,?)", (contest_id, NOW, estado))
    return tmp, db


def add_observation(db, contest_id, url, competition_id=None, observation_id=None):
    observation_id = observation_id or f"obs-{contest_id}"
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("INSERT INTO observacoes_concurso "
                     "(id,contest_id,source_url,competition_id,observed_at) "
                     "VALUES (?,?,?,?,?)",
                     (observation_id, contest_id, url, competition_id or contest_id, NOW))
    return observation_id


def add_document(db, contest_id, *, tipo="edital_abertura", url=None,
                 published_at="2026-09-01", title=None, text=None, observation_id=None,
                 proposals=(), version_state="parcial"):
    observation_id = observation_id or f"obs-{contest_id}"
    document_id = "doc-" + hashlib.md5(
        f"{contest_id}|{tipo}|{url}|{title or ''}|{published_at}".encode("utf-8")
    ).hexdigest()[:12]
    version_id = f"ver-{document_id}"
    url = url or f"https://conhecimento.fgv.br/sites/default/files/concursos/{document_id}.pdf"
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("""INSERT INTO documentos
            (id,contest_id,observation_id,kind,official_url,title,discovered_at,
             discovery_url,discovery_method,issuer,published_at,tipo_documental)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (document_id, contest_id, observation_id,
             "edital" if tipo != "retificacao" else "retificacao", url,
             title or f"Documento {tipo}", NOW,
             f"https://conhecimento.fgv.br/concursos/{contest_id}", "automatico",
             "Fundação Getulio Vargas (FGV Conhecimento)", published_at, tipo))
        if text is None:
            return document_id, None
        conn.execute("""INSERT INTO versoes_documento
            (id,document_id,sha256,fetched_at,fetched_url,content_type,byte_size,
             local_path,extraction_state)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (version_id, document_id, "0" * 64, NOW, url, "application/pdf", len(text),
             f"documents/{version_id}", version_state))
        block_id = f"blk-{version_id}"
        conn.execute("""INSERT INTO blocos_documento
            (id,version_id,page_number,locator,start_offset,end_offset,text)
            VALUES (?,?,?,?,?,?,?)""",
            (block_id, version_id, 1, "página 1", 0, len(text), text))
        for index, proposal in enumerate(proposals):
            quote = proposal.get("quote") or text[:60]
            start = text.find(quote)
            if start < 0:
                start = 0
            evidence_id = f"ev-{version_id}-{index}"
            conn.execute("""INSERT INTO evidencias
                (id,version_id,block_id,quote,page_number,locator,start_offset,
                 end_offset,captured_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                (evidence_id, version_id, block_id, quote, 1, "página 1", start,
                 start + len(quote), NOW))
            conn.execute("""INSERT INTO propostas_campo
                (id,contest_id,role_id,field_name,value_json,value_type,evidence_id,
                 extraction_method,ambiguity_reason,extracted_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (f"prop-{version_id}-{index}", contest_id, proposal.get("role_id"),
                 proposal["field"], json.dumps(proposal["value"]),
                 proposal.get("value_type", "string"), evidence_id,
                 proposal.get("method", "teste"), proposal.get("reason"), NOW))
    return document_id, version_id


class CoverageStatesTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)
        # c1: só agregador
        add_observation(self.db, "c1", "https://www.pciconcursos.com.br/noticias/x")
        add_document(self.db, "c1", tipo="pagina_agregador",
                     url="https://www.pciconcursos.com.br/noticias/x", text="notícia")
        # c2: edital oficial com proposta decisiva
        add_observation(self.db, "c2", "https://conhecimento.fgv.br/concursos/c2", "c2")
        add_document(self.db, "c2", text="Edital. 2 vagas para indígenas.",
                     proposals=[{"field": "indigenous_vacancies", "value": 2,
                                 "quote": "2 vagas para indígenas"}])
        # c3: documento oficial sem edital
        add_observation(self.db, "c3", "https://conhecimento.fgv.br/concursos/c3", "c3")
        add_document(self.db, "c3", tipo="resultado", text="Resultado preliminar")
        # c4: sem documento, fonte oficial habilitada
        add_observation(self.db, "c4", "https://conhecimento.fgv.br/concursos/c4", "c4")
        # c5: sem documento, fonte não autorizada
        add_observation(self.db, "c5", "https://www.qconcursos.com/questoes/x")
        # c6: campo confirmado por revisão humana
        add_observation(self.db, "c6", "https://conhecimento.fgv.br/concursos/c6", "c6")
        add_document(self.db, "c6", text="Edital. 3 vagas imediatas.",
                     proposals=[{"field": "immediate_vacancies", "value": 3,
                                 "quote": "3 vagas imediatas"}])
        with closing(sqlite3.connect(self.db)) as conn, conn:
            proposal_id = conn.execute(
                "SELECT id FROM propostas_campo WHERE contest_id='c6'").fetchone()[0]
            conn.execute("INSERT INTO revisoes_campo "
                         "(id,proposal_id,decision,reviewed_at,reviewer,reason) "
                         "VALUES ('r1',?,'validado',?, 'anton','conferido no edital')",
                         (proposal_id, NOW))
        # c7: retificação posterior altera prazo
        add_observation(self.db, "c7", "https://conhecimento.fgv.br/concursos/c7", "c7")
        add_document(self.db, "c7", text="Inscrições até 10/10/2026.",
                     published_at="2026-09-01",
                     proposals=[{"field": "registration_end", "value": "2026-10-10",
                                 "quote": "Inscrições até 10/10/2026."}])
        add_document(self.db, "c7", tipo="retificacao",
                     text="Inscrições até 20/10/2026.", published_at="2026-10-01",
                     proposals=[{"field": "registration_end", "value": "2026-10-20",
                                 "quote": "Inscrições até 20/10/2026."}])

    def test_estados_exclusivos_e_denominador_de_certames(self):
        report = coverage_states.coverage_report(self.db, limit=0)
        self.assertEqual(report["universo"]["certames"], 7)
        self.assertEqual(report["universo"]["containers"], 1)
        states = {item["estado"]: item["quantidade"] for item in report["estados"]}
        self.assertEqual(states["apenas_agregador"], 1)
        self.assertEqual(states["campos_candidatos"], 1)
        self.assertEqual(states["oficial_sem_edital"], 1)
        self.assertEqual(states["oficial_nao_importado"], 1)
        self.assertEqual(states["obtencao_nao_autorizada"], 1)
        self.assertEqual(states["campos_confirmados"], 1)
        self.assertEqual(states["conflito"], 1)
        self.assertEqual(sum(states.values()), 7)

    def test_agregador_nao_conta_como_documento_oficial(self):
        report = coverage_states.coverage_report(self.db, limit=0)
        funnel = {item["etapa"]: item["quantidade"] for item in report["funil"]}
        self.assertEqual(funnel["com_documento_qualquer"], 5)  # c1, c2, c3, c6, c7
        self.assertEqual(funnel["com_documento_oficial"], 4)   # c2, c3, c6, c7
        self.assertEqual(funnel["com_edital_oficial"], 3)      # c2, c6, c7

    def test_container_nao_entra_nos_estados(self):
        report = coverage_states.coverage_report(self.db, limit=0)
        ids = {item["contest_id"] for item in report["itens"]}
        self.assertNotIn("cont", ids)

    def test_lista_nominal_e_contada_e_listada(self):
        add_document(self.db, "c6", tipo="retificacao",
                     title="Retificação - Relação de inscritos provisórios",
                     text="123 NOME DE CANDIDATO")
        report = coverage_states.coverage_report(self.db, limit=0)
        self.assertGreaterEqual(report["documentos_nominais"], 1)
        listed = coverage_states.nominal_documents(self.db)
        self.assertTrue(any("inscritos" in item["title"].lower()
                            for item in listed["itens"]))

    def test_host_fora_do_catalogo_nao_conta_como_oficial(self):
        add_document(self.db, "c5", tipo="edital_abertura",
                     url="https://noticias.example.com/materia", text="texto qualquer")
        report = coverage_states.coverage_report(self.db, limit=100)
        item = next(item for item in report["itens"] if item["contest_id"] == "c5")
        self.assertEqual(item["estado"], "fonte_nao_catalogada")
        self.assertEqual(item["documentos_oficiais"], 0)
        self.assertEqual(item["documentos_nao_catalogados"], 1)
        funnel = {step["etapa"]: step["quantidade"] for step in report["funil"]}
        self.assertEqual(funnel["com_documento_oficial"], 4)  # c2, c3, c6, c7

    def test_cdn_compartilhado_e_desempatado_pelo_emissor(self):
        add_document(self.db, "c3", tipo="edital_abertura",
                     url="https://anexos-r2.selecao.net.br/uploads/861/concursos/1/a.pdf",
                     title="Edital IBFC", text="edital")
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("UPDATE documentos SET issuer='IBFC' WHERE contest_id='c3' "
                         "AND official_url LIKE '%selecao.net.br%'")
        report = coverage_states.coverage_report(self.db, limit=100)
        item = next(item for item in report["itens"] if item["contest_id"] == "c3")
        self.assertIn("ibfc", item["fontes"])
        self.assertNotIn("quadrix", item["fontes"])

    def test_fonte_habilitada_sem_politica_de_documento_nao_e_obtencao(self):
        # ibge-localidades é habilitada e oficial, mas não declara persistência de documento.
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("DELETE FROM observacoes_concurso WHERE contest_id='c4'")
            conn.execute("INSERT INTO observacoes_concurso "
                         "(id,contest_id,source_url,competition_id,observed_at) "
                         "VALUES ('obs-ibge','c4',"
                         "'https://servicodados.ibge.gov.br/api/v1/localidades','ibge',?)",
                         (NOW,))
        report = coverage_states.coverage_report(self.db, limit=100)
        item = next(item for item in report["itens"] if item["contest_id"] == "c4")
        self.assertEqual(item["estado"], "obtencao_nao_autorizada")

    def test_fonte_restrita_aparece_no_relatorio(self):
        report = coverage_states.coverage_report(self.db, limit=0)
        statuses = {item["source_id"]: item["status"] for item in report["fontes_restritas"]}
        self.assertIn("qconcursos", statuses)

    def test_proxima_acao_por_estado(self):
        report = coverage_states.coverage_report(self.db, limit=0)
        for item in report["estados"]:
            self.assertTrue(item["proxima_acao"])


class VersionConflictsTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)
        add_observation(self.db, "c7", "https://conhecimento.fgv.br/concursos/c7", "c7")

    def test_retificacao_posterior_tem_vigente_e_substituido(self):
        add_document(self.db, "c7", text="Inscrições até 10/10/2026.",
                     published_at="2026-09-01",
                     proposals=[{"field": "registration_end", "value": "2026-10-10",
                                 "quote": "Inscrições até 10/10/2026."}])
        add_document(self.db, "c7", tipo="retificacao", text="Inscrições até 20/10/2026.",
                     published_at="2026-10-01",
                     proposals=[{"field": "registration_end", "value": "2026-10-20",
                                 "quote": "Inscrições até 20/10/2026."}])
        report = version_conflicts.conflicts(self.db)
        item = report["itens"][0]
        self.assertEqual(item["tipo"], "retificacao_posterior")
        self.assertEqual(item["vigente"]["value"], "2026-10-20")
        self.assertEqual(item["substituidos"][0]["value"], "2026-10-10")

    def test_mesmo_documento_com_dois_valores_nao_escolhe(self):
        add_document(self.db, "c7", text="Inscrições até 10/10/2026 ou 20/10/2026.",
                     published_at="2026-09-01",
                     proposals=[{"field": "registration_end", "value": "2026-10-10",
                                 "quote": "Inscrições até 10/10/2026"},
                                {"field": "registration_end", "value": "2026-10-20",
                                 "quote": "20/10/2026."}])
        item = version_conflicts.conflicts(self.db)["itens"][0]
        self.assertEqual(item["tipo"], "divergencia_mesmo_documento")
        self.assertIsNone(item.get("vigente"))

    def test_local_equivalente_nao_e_conflito(self):
        add_document(self.db, "c7", text="Provas em Salvador.",
                     published_at="2026-09-01",
                     proposals=[{"field": "exam_location", "value": "Salvador",
                                 "quote": "Provas em Salvador."}])
        add_document(self.db, "c7", tipo="retificacao", text="Provas em Salvador/BA.",
                     published_at="2026-10-01",
                     proposals=[{"field": "exam_location", "value": "Salvador/BA",
                                 "quote": "Provas em Salvador/BA."}])
        self.assertEqual(version_conflicts.conflicts(self.db)["total"], 0)

    def test_a_divulgar_nao_e_conflito_de_valor(self):
        add_document(self.db, "c7", text="Provas em Salvador.",
                     published_at="2026-09-01",
                     proposals=[{"field": "exam_location", "value": "Salvador/BA",
                                 "quote": "Provas em Salvador."}])
        add_document(self.db, "c7", tipo="retificacao", text="Locais serão divulgados.",
                     published_at="2026-10-01",
                     proposals=[{"field": "exam_location", "value": "a_divulgar",
                                 "quote": "Locais serão divulgados."}])
        report = version_conflicts.conflicts(self.db)
        self.assertEqual(report["por_tipo"].get("escopo_diferente"), 1)

    def test_prazo_de_documento_de_resultado_nao_compete(self):
        add_document(self.db, "c7", text="Inscrições até 10/10/2026.",
                     published_at="2026-09-01",
                     proposals=[{"field": "registration_end", "value": "2026-10-10",
                                 "quote": "Inscrições até 10/10/2026."}])
        add_document(self.db, "c7", tipo="resultado", text="Inscrições até 30/11/2026.",
                     published_at="2026-10-01",
                     proposals=[{"field": "registration_end", "value": "2026-11-30",
                                 "quote": "Inscrições até 30/11/2026."}])
        self.assertEqual(version_conflicts.conflicts(self.db)["total"], 0)


class DecisiveFieldsTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def report_for(self, contest_id):
        return decisive_fields.decisive_report(self.db, contest_ids=[contest_id], limit=10)

    def test_vaga_indigena_explicita(self):
        add_observation(self.db, "c1", "https://conhecimento.fgv.br/concursos/c1", "c1")
        add_document(self.db, "c1", text="2 vagas para pessoas indígenas.",
                     proposals=[{"field": "indigenous_vacancies", "value": 2,
                                 "quote": "2 vagas para pessoas indígenas."}])
        item = self.report_for("c1")["itens"][0]
        self.assertEqual(item["indigenas"]["estado"], "explicito_imediato")
        self.assertFalse(item["indigenas"]["derivado_de_agregado"])

    def test_total_agregado_nunca_vira_vaga_indigena(self):
        add_observation(self.db, "c1", "https://conhecimento.fgv.br/concursos/c1", "c1")
        add_document(self.db, "c1", text="Total de vagas: 100.",
                     proposals=[{"field": "vagas_total_publicado", "value": 100,
                                 "quote": "Total de vagas: 100."}])
        item = self.report_for("c1")["itens"][0]
        self.assertEqual(item["indigenas"]["estado"], "agregado_sem_modalidade")
        self.assertEqual(item["indigenas"]["imediata"], [])
        self.assertFalse(item["indigenas"]["derivado_de_agregado"])

    def test_ausencia_de_modalidade_nao_e_zero(self):
        add_observation(self.db, "c1", "https://conhecimento.fgv.br/concursos/c1", "c1")
        add_document(self.db, "c1", text="Edital sem qualquer reserva.",
                     proposals=[{"field": "immediate_vacancies", "value": 5,
                                 "quote": "Edital sem qualquer reserva."}])
        item = self.report_for("c1")["itens"][0]
        self.assertEqual(item["indigenas"]["estado"], "nao_mencionado")

    def test_mencao_sem_quantidade(self):
        add_observation(self.db, "c1", "https://conhecimento.fgv.br/concursos/c1", "c1")
        add_document(self.db, "c1", text="Haverá reserva para pessoas indígenas.")
        item = self.report_for("c1")["itens"][0]
        self.assertEqual(item["indigenas"]["estado"], "mencao_sem_quantidade")

    def test_reserva_sem_vaga_imediata(self):
        add_observation(self.db, "c1", "https://conhecimento.fgv.br/concursos/c1", "c1")
        add_document(self.db, "c1", text="Reserva indígena de 1 vaga.",
                     proposals=[{"field": "indigenous_vacancies", "value": 0,
                                 "quote": "Reserva indígena de 1 vaga."},
                                {"field": "indigenous_reserve_vacancies", "value": 1,
                                 "quote": "Reserva indígena de 1 vaga."}])
        item = self.report_for("c1")["itens"][0]
        self.assertEqual(item["indigenas"]["estado"], "apenas_reserva")

    def test_si_por_cargo_nao_contamina_outro_cargo(self):
        add_observation(self.db, "c1", "https://conhecimento.fgv.br/concursos/c1", "c1")
        add_document(self.db, "c1", text="Cargo TI exige SI. Cargo Direito exige Direito.",
                     proposals=[
                         {"field": "si_compatibility", "value": "aceito_expressamente",
                          "quote": "Cargo TI exige SI.",
                          "reason": "cargo do documento não reconciliado: 400 ANALISTA — x"},
                         {"field": "si_compatibility",
                          "value": "incompativel_com_requisito_explicito",
                          "quote": "Cargo Direito exige Direito.",
                          "reason": "cargo do documento não reconciliado: 401 ADVOGADO — x"}])
        si = self.report_for("c1")["itens"][0]["sistemas_de_informacao"]
        self.assertEqual(si["estado"], "explicito")
        self.assertEqual(len(si["cargos"]), 2)
        states = {role["estado"] for role in si["cargos"]}
        self.assertEqual(states, {"explicito", "outras_formacoes"})

    def test_si_sem_edital_e_extracao_incompleta(self):
        add_observation(self.db, "c1", "https://conhecimento.fgv.br/concursos/c1", "c1")
        item = self.report_for("c1")["itens"][0]
        self.assertEqual(item["sistemas_de_informacao"]["estado"], "extracao_incompleta")
        self.assertEqual(item["indigenas"]["estado"], "nao_pesquisado")

    def test_prazo_com_retificacao_guarda_anterior(self):
        add_observation(self.db, "c1", "https://conhecimento.fgv.br/concursos/c1", "c1")
        add_document(self.db, "c1", text="Inscrições até 10/10/2026.",
                     published_at="2026-09-01",
                     proposals=[{"field": "registration_end", "value": "2026-10-10",
                                 "quote": "Inscrições até 10/10/2026."}])
        add_document(self.db, "c1", tipo="retificacao", text="Inscrições até 20/10/2026.",
                     published_at="2026-10-01",
                     proposals=[{"field": "registration_end", "value": "2026-10-20",
                                 "quote": "Inscrições até 20/10/2026."}])
        fim = self.report_for("c1")["itens"][0]["prazos"]["inscricao_fim"]
        self.assertEqual(fim["estado"], "candidato")
        self.assertEqual(fim["vigente"]["value"], "2026-10-20")
        self.assertEqual(fim["anteriores"][0]["value"], "2026-10-10")

    def test_local_de_prova_nao_e_lotacao(self):
        add_observation(self.db, "c1", "https://conhecimento.fgv.br/concursos/c1", "c1")
        add_document(self.db, "c1", text="Provas em Salvador/BA. Lotação no Rio de Janeiro/RJ.",
                     proposals=[
                         {"field": "exam_location", "value": "Salvador/BA",
                          "quote": "Provas em Salvador/BA."},
                         {"field": "work_location", "value": "Rio de Janeiro/RJ",
                          "quote": "Lotação no Rio de Janeiro/RJ."}])
        local = self.report_for("c1")["itens"][0]["local"]
        self.assertEqual(local["prova"]["municipios"], ["Salvador"])
        self.assertEqual(local["lotacao"]["municipios"], ["Rio de Janeiro"])
        self.assertEqual(local["prova"]["uf"], "BA")

    def test_a_divulgar_com_local_concreto_e_ambiguo(self):
        add_observation(self.db, "c1", "https://conhecimento.fgv.br/concursos/c1", "c1")
        add_document(self.db, "c1", text="Provas em Salvador. Locais serão divulgados.",
                     proposals=[
                         {"field": "exam_location", "value": "Salvador/BA",
                          "quote": "Provas em Salvador."},
                         {"field": "exam_location", "value": "a_divulgar",
                          "quote": "Locais serão divulgados."}])
        prova = self.report_for("c1")["itens"][0]["local"]["prova"]
        self.assertEqual(prova["state"], "ambiguo")
        self.assertEqual(prova["municipios"], ["Salvador"])

    def test_valor_sem_uf_recupera_uf_do_trecho(self):
        add_observation(self.db, "c1", "https://conhecimento.fgv.br/concursos/c1", "c1")
        add_document(self.db, "c1",
                     text="Todas as provas serão realizadas na cidade de Porto Alegre – RS.",
                     proposals=[{"field": "exam_location", "value": "Porto Alegre –",
                                 "quote": "cidade de Porto Alegre – RS"}])
        prova = self.report_for("c1")["itens"][0]["local"]["prova"]
        self.assertEqual(prova["municipios"], ["Porto Alegre"])
        self.assertEqual(prova["uf"], "RS")


class CoverageApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)
        add_observation(self.db, "c1", "https://conhecimento.fgv.br/concursos/c1", "c1")
        add_document(self.db, "c1", text="Edital. 2 vagas para indígenas.",
                     proposals=[{"field": "indigenous_vacancies", "value": 2,
                                 "quote": "2 vagas para indígenas."}])
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

    def test_rotas_novas_respondem(self):
        for path, key in (("/api/cobertura/estados", "estados"),
                          ("/api/campos-decisivos", "resumo"),
                          ("/api/conflitos", "itens"),
                          ("/api/editais-faltantes", "itens")):
            status, body = self.get(path)
            self.assertEqual(status, 200, path)
            self.assertIn(key, json.loads(body))

    def test_limit_invalido_responde_400(self):
        for path in ("/api/cobertura/estados?limit=x",
                     "/api/campos-decisivos?limit=-1",
                     "/api/conflitos?limit=x",
                     "/api/editais-faltantes?limit=0"):
            status, _ = self.get(path)
            self.assertEqual(status, 400, path)

    def test_parametro_desconhecido_responde_400(self):
        status, _ = self.get("/api/cobertura/estados?foo=1")
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
