"""Auditoria de prazos, contagens por dimensão e verificação de documento (Fase 37)."""

import hashlib
import http.client
import json
import sqlite3
import threading
import unittest
from contextlib import closing
from unittest import mock

from radar import (deadline_audit, deadline_calendar, deadline_revalidation,
                   document_fields, review)
from radar.document_store import SCHEMA_VERSION
from radar.server import create_server
from tests.test_portfolio_f36 import NOON, TODAY, add_document, add_proposal, make_db

PAYLOAD = b"%PDF-1.4 edital de teste"
LABEL = "cargo do documento não reconciliado: CARGO TESTE"

# Texto com três eventos distintos no mesmo bloco — o caso que gerou o conflito 4f495c42.
THREE_EVENTS = (
    "9.1.2 As inscrições para o Concurso Público estarão abertas no período das 16h do "
    "dia 19 de outubro de 2026 até às 16h do dia 26 de novembro de 2026. "
    "10.2 A isenção mencionada no subitem 10.1 poderá ser solicitada no período das 16h do "
    "dia 19 de outubro de 2026 às 16h do dia 21 de outubro de 2026, por meio de inscrição "
    "no sítio eletrônico. "
    "15.1.1.1 As provas serão aplicadas nas datas prováveis de 18 de abril de 2027 e 19 de "
    "abril de 2027, sendo: a) no dia 18 de abril de 2027, no período da manhã, das 8h às "
    "12h, prova discursiva; b) no dia 18 de abril de 2027, prova prática."
)
REG_QUOTE = "dia 19 de outubro de 2026 até às 16h do dia 26 de novembro de 2026"
EXEMPTION_QUOTE = "dia 19 de outubro de 2026 às 16h do dia 21 de outubro de 2026"
EXAM_QUOTE = ("dia 18 de abril de 2027, no período da manhã, das 8h às 12h, "
              "prova discursiva; b) no dia 18 de abril de 2027")


class EventContextTest(unittest.TestCase):
    def test_evento_por_marcador_proximo(self):
        text = THREE_EVENTS
        registration = text.index(REG_QUOTE)
        exemption = text.index(EXEMPTION_QUOTE)
        exam = text.index(EXAM_QUOTE)
        self.assertEqual(document_fields.event_marker(text, registration)[0], "inscricao")
        self.assertEqual(document_fields.event_marker(text, exemption)[0], "isencao")
        self.assertEqual(document_fields.event_marker(text, exam)[0], "prova")

    def test_extrator_nao_usa_isencao_nem_prova_como_inscricao(self):
        produced = document_fields._registration_dates(THREE_EVENTS)
        self.assertEqual({(field, value) for field, value, *_ in produced},
                         {("registration_start", "2026-10-19"),
                          ("registration_end", "2026-11-26")})

    def test_frase_longa_de_inscricao_continua_reconhecida(self):
        text = ("As inscrições para o Concurso Público de ingresso na carreira do órgão, "
                "regulamentado por edital próprio e pelas normas aplicáveis ao certame, "
                "estarão abertas no período das 16h do dia 27 de fevereiro de 2023 até as "
                "16h do dia 10 de abril de 2023.")
        produced = {(field, value) for field, value, *_ in
                    document_fields._registration_dates(text)}
        self.assertIn(("registration_end", "2023-04-10"), produced)

    def test_frase_ambigua_nao_e_atribuida(self):
        text = ("A isenção e as inscrições ocorrem no período das 16h do dia 01 de "
                "outubro de 2026 às 16h do dia 05 de outubro de 2026.")
        self.assertEqual(document_fields.event_marker(text, text.index("dia 01"))[0],
                         "outro")


class MarkerRegressionTest(unittest.TestCase):
    def test_taxa_de_inscricao_nao_e_evento(self):
        text = ("A isenção do pagamento da taxa de inscrição poderá ser solicitada no "
                "período das 16h do dia 19 de outubro de 2026 às 16h do dia 21 de "
                "outubro de 2026.")
        self.assertEqual(document_fields.event_marker(text, text.index("dia 19"))[0],
                         "isencao")
        self.assertEqual(document_fields._registration_dates(text), [])

    def test_inscritos_nao_e_evento(self):
        text = ("Os candidatos inscritos deverão comparecer no período das 16h do dia 01 "
                "de outubro de 2026 às 16h do dia 05 de outubro de 2026.")
        self.assertEqual(document_fields.event_marker(text, text.index("dia 01"))[0],
                         "outro")

    def test_frase_muito_longa_continua_reconhecida(self):
        filler = ("considerando a necessidade de disciplinar o ingresso na carreira, "
                  "observadas as disposições constitucionais e legais aplicáveis, bem como "
                  "as normas internas do órgão e as orientações da comissão organizadora "
                  "do certame, ") * 3
        text = ("As inscrições " + filler + "estarão abertas no período das 16h do dia 27 "
                "de fevereiro de 2023 até as 16h do dia 10 de abril de 2023.")
        self.assertGreater(text.index("dia 27"), 400)
        produced = {(field, value) for field, value, *_ in
                    document_fields._registration_dates(text)}
        self.assertIn(("registration_end", "2023-04-10"), produced)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def three_events(self):
        document_id, version = add_document(self.db, "c1", text=THREE_EVENTS)
        self.registration = add_proposal(
            self.db, "c1", version_id=version, field="registration_end",
            value="2026-11-26", quote=REG_QUOTE)
        self.exemption = add_proposal(
            self.db, "c1", version_id=version, field="registration_end",
            value="2026-10-21", quote=EXEMPTION_QUOTE)
        self.exam = add_proposal(
            self.db, "c1", version_id=version, field="registration_end",
            value="2027-04-18", quote=EXAM_QUOTE)
        return document_id, version

    def counts(self):
        with closing(sqlite3.connect(self.db)) as conn:
            return conn.execute(
                "SELECT (SELECT COUNT(*) FROM revisoes_campo),"
                "(SELECT COUNT(*) FROM valores_atuais),"
                "(SELECT COUNT(*) FROM reconciliacoes_cargo),"
                "(SELECT COUNT(*) FROM revalidacoes_prazo)").fetchone()


class CaseFileTest(Base):
    def test_caso_4f495c42_explica_evento_diferente(self):
        self.three_events()
        case = deadline_audit.case_file(self.db, contest_id="c1", group="inscricao_fim",
                                        now=NOON)
        self.assertEqual(case["causa"], "evento_diferente")
        self.assertEqual(case["valores_sustentados"], ["2026-11-26"])
        self.assertEqual(case["abertas"], 3)
        events = {item["value"]: item["event"] for item in case["candidatos"]}
        self.assertEqual(events, {"2026-11-26": "inscricao",
                                  "2026-10-21": "isencao",
                                  "2027-04-18": "prova"})
        repro = {item["value"]: item["reproducibility"] for item in case["candidatos"]}
        self.assertEqual(repro["2026-11-26"], "reproduzido")
        self.assertEqual(repro["2026-10-21"], "nao_reproduzido")
        self.assertEqual(repro["2027-04-18"], "nao_reproduzido")
        # Proposta de correção existe, mas nada foi executado.
        proposal = case["proposta_correcao"]
        self.assertTrue(proposal["requer_decisao_humana"])
        self.assertTrue(proposal["nao_executado"])
        self.assertEqual(set(proposal["propostas_para_rejeitar"]),
                         {self.exemption, self.exam})
        self.assertEqual(self.counts(), (0, 0, 0, 0))

    def test_candidatos_trazem_evidencia_completa(self):
        _, version = self.three_events()
        case = deadline_audit.case_file(self.db, contest_id="c1", group="inscricao_fim",
                                        now=NOON)
        candidate = [item for item in case["candidatos"]
                     if item["value"] == "2026-11-26"][0]
        for key in ("quote", "page_number", "start_offset", "end_offset", "block_id",
                    "version_id", "sha256", "official_url", "document_title",
                    "context_before", "context_after"):
            self.assertIn(key, candidate)
        self.assertEqual(candidate["version_id"], version)
        self.assertIn("inscri", (candidate["context_before"] or "").lower())

    def test_divergencia_real_nao_escolhe(self):
        _, opening = add_document(self.db, "c1", text="Inscrições até 01/12/2026.")
        add_proposal(self.db, "c1", version_id=opening, field="registration_end",
                     value="2026-12-01", quote="Inscrições até 01/12/2026.")
        _, cronograma = add_document(self.db, "c1", tipo="cronograma",
                                     title="Cronograma", published_at="2026-10-10",
                                     text="Inscrições até 10/12/2026.")
        add_proposal(self.db, "c1", version_id=cronograma, field="registration_end",
                     value="2026-12-10", quote="Inscrições até 10/12/2026.")
        case = deadline_audit.case_file(self.db, contest_id="c1", group="inscricao_fim",
                                        now=NOON)
        self.assertEqual(case["causa"], "divergencia_real")
        self.assertEqual(sorted(case["valores_sustentados"]),
                         ["2026-12-01", "2026-12-10"])

    def test_retificacao_que_altera_nao_e_escolhida(self):
        _, opening = add_document(self.db, "c1", text="Inscrições até 01/12/2026.")
        add_proposal(self.db, "c1", version_id=opening, field="registration_end",
                     value="2026-12-01", quote="Inscrições até 01/12/2026.")
        _, retif = add_document(self.db, "c1", tipo="retificacao", title="1ª Retificação",
                                published_at="2026-10-10",
                                text="Inscrições até 15/12/2026.")
        add_proposal(self.db, "c1", version_id=retif, field="registration_end",
                     value="2026-12-15", quote="Inscrições até 15/12/2026.")
        case = deadline_audit.case_file(self.db, contest_id="c1", group="inscricao_fim",
                                        now=NOON)
        # A auditoria mostra as duas leituras e não promove a mais recente.
        self.assertEqual(sorted(case["valores_sustentados"]),
                         ["2026-12-01", "2026-12-15"])
        self.assertIn(case["causa"], ("divergencia_real",))

    def test_rejeitada_aparece_mas_nao_sustenta(self):
        self.three_events()
        review.decide_proposal(self.db, self.exemption, "rejeitado", reviewer="Ana",
                               reason="é isenção, não inscrição", origin="interface")
        case = deadline_audit.case_file(self.db, contest_id="c1", group="inscricao_fim",
                                        now=NOON)
        rejected = [item for item in case["candidatos"]
                    if item["proposal_id"] == self.exemption][0]
        self.assertFalse(rejected["is_open"])
        self.assertEqual(case["rejeitadas"], 1)
        self.assertEqual(case["valores_sustentados"], ["2026-11-26"])
        self.assertEqual(self.counts()[0], 1)

    def test_auditoria_nao_grava(self):
        self.three_events()
        deadline_audit.audit_conflicts(self.db, limit=10, now=NOON)
        deadline_audit.case_file(self.db, contest_id="c1", group="inscricao_fim", now=NOON)
        self.assertEqual(self.counts(), (0, 0, 0, 0))

    def test_grupo_invalido_e_concurso_inexistente(self):
        with self.assertRaises(ValueError):
            deadline_audit.case_file(self.db, contest_id="c1", group="nao_existe")
        with self.assertRaises(ValueError):
            deadline_audit.case_file(self.db, contest_id="c99", group="inscricao_fim")


class ReconciliationScopeTest(Base):
    def test_ficha_nao_fica_vazia_com_rotulo_reconciliado(self):
        document_id, version = add_document(self.db, "c1", text=THREE_EVENTS)
        add_proposal(self.db, "c1", version_id=version, field="registration_end",
                     value="2026-11-26", quote=REG_QUOTE,
                     reason="cargo do documento não reconciliado: CARGO TESTE")
        add_proposal(self.db, "c1", version_id=version, field="registration_end",
                     value="2026-10-21", quote=EXEMPTION_QUOTE,
                     reason="cargo do documento não reconciliado: CARGO TESTE")
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO cargos_identidade (id,contest_id,name,created_at) "
                         "VALUES ('role-1','c1','CARGO TESTE',?)", (NOON,))
            conn.execute(
                "INSERT INTO reconciliacoes_cargo (id,contest_id,label,role_id,"
                "reconciled_at,reviewer,reason,state) VALUES (?,?,?,?,?,?,?,'confirmada')",
                ("rec-1", "c1", "CARGO TESTE", "role-1", NOON, "Ana", "confere"))
        case = deadline_audit.case_file(self.db, contest_id="c1", group="inscricao_fim",
                                        escopo="role-1", now=NOON)
        self.assertEqual(len(case["candidatos"]), 2)
        self.assertEqual(case["valores_sustentados"], ["2026-11-26"])
        self.assertEqual(case["causa"], "evento_diferente")

    def test_prazo_sem_divergencia_e_coerente(self):
        _, version = add_document(self.db, "c1", text="Inscrições até 01/12/2026.")
        add_proposal(self.db, "c1", version_id=version, field="registration_end",
                     value="2026-12-01", quote="Inscrições até 01/12/2026.")
        case = deadline_audit.case_file(self.db, contest_id="c1", group="inscricao_fim",
                                        now=NOON)
        self.assertEqual(case["causa"], "coerente")
        self.assertEqual(case["proposta_correcao"]["propostas_para_rejeitar"], [])

    def test_dois_valores_nao_classificados_nao_sao_coerentes(self):
        _, version = add_document(self.db, "c1", text="A. B.")
        add_proposal(self.db, "c1", version_id=version, field="registration_end",
                     value="2026-12-01", quote="A.")
        add_proposal(self.db, "c1", version_id=version, field="registration_end",
                     value="2026-12-10", quote="B.")
        case = deadline_audit.case_file(self.db, contest_id="c1", group="inscricao_fim",
                                        now=NOON)
        self.assertNotEqual(case["causa"], "coerente")
        self.assertEqual(sorted(case["valores_nao_classificados"]),
                         ["2026-12-01", "2026-12-10"])


class DimensionTest(Base):
    def test_dimensoes_somam_o_total(self):
        self.three_events()
        _, past = add_document(self.db, "c1", tipo="edital_abertura", title="Outro",
                               published_at="2026-08-01",
                               text="Inscrições até 01/01/2026.")
        add_proposal(self.db, "c1", version_id=past, field="registration_end",
                     value="2026-01-01", quote="Inscrições até 01/01/2026.",
                     reason="cargo do documento não reconciliado: OUTRO CARGO")
        report = deadline_calendar.calendar(self.db, now=NOON)
        total = report["total"]
        for key in ("por_temporal", "por_revalidacao", "por_conflito", "por_revisao",
                    "por_situacao", "por_urgencia", "por_grupo"):
            self.assertEqual(sum(report[key].values()), total, key)
        for item in report["itens"]:
            self.assertEqual(set(item["dimensoes"]),
                             {"temporal", "revalidacao", "conflito", "revisao"})
        self.assertTrue(set(report["por_temporal"]) <= {"futuro", "hoje", "expirado",
                                                        "data_invalida", "sem_data"})
        self.assertIn("denominador", report)
        self.assertEqual(report["denominador"]["filtros"]["group"], None)

    def test_revalidacao_e_dimensao_independente(self):
        document_id, version = add_document(self.db, "c1", text="Inscrições até 01/12/2026.")
        add_proposal(self.db, "c1", version_id=version, field="registration_end",
                     value="2026-12-01", quote="Inscrições até 01/12/2026.")
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("UPDATE versoes_documento SET sha256=? WHERE id=?",
                         (hashlib.sha256(PAYLOAD).hexdigest(), version))
            conn.execute(
                """INSERT INTO revalidacoes_prazo
                   (id,contest_id,grupo,escopo,valor,document_id,version_id,checked_at,
                    official_url,http_status,stored_sha256,observed_sha256,result,note,
                    checked_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                ("r1", "c1", "inscricao_fim", None, "2026-12-01", document_id, version,
                 NOON, "https://conhecimento.fgv.br/x.pdf", 200,
                 hashlib.sha256(PAYLOAD).hexdigest(), hashlib.sha256(PAYLOAD).hexdigest(),
                 "fonte_inalterada", None, "teste"))
        report = deadline_calendar.calendar(self.db, now=NOON)
        self.assertEqual(report["por_temporal"], {"futuro": 1})
        self.assertEqual(report["por_revalidacao"], {"fonte_inalterada": 1})
        self.assertEqual(report["por_situacao"], {"revalidado_na_fonte": 1})
        # `fonte_inalterada` não vira "confirmado".
        self.assertNotIn("confirmado", report["por_situacao"])


class GroupsFilterTest(Base):
    """Recorte por vários grupos: o resumo conta só o que foi pedido."""

    def four_groups(self):
        _, version = add_document(self.db, "c1", text=THREE_EVENTS)
        for field, value, quote in (
                ("registration_end", "2026-11-26", REG_QUOTE),
                ("exemption_end", "2026-10-21", EXEMPTION_QUOTE),
                ("exam_date", "2027-04-18", EXAM_QUOTE),
                ("exemption_result_final", "2026-10-30",
                 "Resultado final da isenção em 30 de outubro de 2026")):
            add_proposal(self.db, "c1", version_id=version, field=field,
                         value=value, quote=quote)

    def test_groups_traz_apenas_os_grupos_pedidos(self):
        self.four_groups()
        report = deadline_calendar.calendar(
            self.db, groups=["inscricao_fim", "isencao_fim", "data_prova"], now=NOON)
        self.assertEqual(set(report["por_grupo"]),
                         {"inscricao_fim", "isencao_fim", "data_prova"})
        self.assertEqual(report["total"], 3)
        self.assertEqual(sum(report["por_urgencia"].values()), report["total"])
        self.assertEqual(report["denominador"]["filtros"]["groups"],
                         ["data_prova", "inscricao_fim", "isencao_fim"])

    def test_resultado_de_isencao_fica_fora_do_recorte(self):
        self.four_groups()
        operacionais = deadline_calendar.calendar(
            self.db, groups=["inscricao_fim", "isencao_fim", "data_prova"], now=NOON)
        self.assertNotIn("resultado_isencao_final", operacionais["por_grupo"])
        completo = deadline_calendar.calendar(self.db, now=NOON)
        self.assertIn("resultado_isencao_final", completo["por_grupo"])
        self.assertGreater(completo["total"], operacionais["total"])

    def test_groups_vazio_ou_ausente_nao_filtra(self):
        self.four_groups()
        sem_filtro = deadline_calendar.calendar(self.db, now=NOON)
        vazio = deadline_calendar.calendar(self.db, groups=[], now=NOON)
        self.assertEqual(sem_filtro["total"], vazio["total"])
        self.assertEqual(sem_filtro["por_grupo"], vazio["por_grupo"])

    def test_group_especifico_manda_sobre_groups(self):
        self.four_groups()
        report = deadline_calendar.calendar(
            self.db, group="inscricao_fim", groups=["inscricao_fim", "data_prova"],
            now=NOON)
        self.assertEqual(set(report["por_grupo"]), {"inscricao_fim"})

    def test_grupo_invalido_em_groups_falha(self):
        with self.assertRaises(ValueError):
            deadline_calendar.calendar(self.db, groups=["inscricao_fim", "xyz"],
                                       now=NOON)


class VerifyVersionTest(Base):
    def prepare(self):
        document_id, version = add_document(self.db, "c1", text="Inscrições até 01/12/2026.")
        add_proposal(self.db, "c1", version_id=version, field="registration_end",
                     value="2026-12-01", quote="Inscrições até 01/12/2026.")
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("UPDATE versoes_documento SET sha256=? WHERE id=?",
                         (hashlib.sha256(PAYLOAD).hexdigest(), version))
        return document_id, version

    def test_simulacao_nao_consulta(self):
        _, version = self.prepare()

        def forbidden(url, timeout=20):
            raise AssertionError("simulação não pode consultar a rede")

        result = deadline_revalidation.verify_version(
            self.db, version, contest_id="c1", grupo="inscricao_fim", apply=False,
            fetcher=forbidden)
        self.assertTrue(result["dry_run"])
        self.assertIsNone(result["result"])
        self.assertEqual(self.counts()[3], 0)

    def test_apply_grava_metadados(self):
        _, version = self.prepare()
        result = deadline_revalidation.verify_version(
            self.db, version, contest_id="c1", grupo="inscricao_fim", apply=True,
            fetcher=lambda url, timeout=20: (200, PAYLOAD))
        self.assertEqual(result["result"], "fonte_inalterada")
        self.assertEqual(self.counts()[3], 1)
        with closing(sqlite3.connect(self.db)) as conn:
            row = conn.execute("SELECT result,observed_sha256,note FROM revalidacoes_prazo"
                               ).fetchone()
        self.assertEqual(row[0], "fonte_inalterada")
        self.assertEqual(row[1], hashlib.sha256(PAYLOAD).hexdigest())
        self.assertIn("não confirma", row[2])

    def test_documento_alterado(self):
        _, version = self.prepare()
        result = deadline_revalidation.verify_version(
            self.db, version, contest_id="c1", apply=True,
            fetcher=lambda url, timeout=20: (200, b"outro conteudo"))
        self.assertEqual(result["result"], "fonte_alterada")

    def test_politica_bloqueada_nao_consulta(self):
        _, version = self.prepare()

        def forbidden(url, timeout=20):
            raise AssertionError("política bloqueada não pode consultar")

        with mock.patch.object(deadline_calendar, "_source_info",
                               return_value={"id": "x", "label": "x",
                                             "policy": {"allowed": False,
                                                        "permission": "acesso_bloqueado",
                                                        "reason": "bloqueado"}}):
            result = deadline_revalidation.verify_version(
                self.db, version, contest_id="c1", apply=True, fetcher=forbidden)
        self.assertEqual(result["result"], "sem_permissao")
        self.assertEqual(self.counts()[3], 1)

    def test_grupo_derivado_da_versao(self):
        _, version = self.prepare()
        result = deadline_revalidation.verify_version(
            self.db, version, contest_id="c1", apply=True,
            fetcher=lambda url, timeout=20: (200, PAYLOAD))
        self.assertEqual(result["result"], "fonte_inalterada")
        with closing(sqlite3.connect(self.db)) as conn:
            grupo = conn.execute("SELECT grupo FROM revalidacoes_prazo").fetchone()[0]
        self.assertEqual(grupo, "inscricao_fim")
        case = deadline_audit.case_file(self.db, contest_id="c1", group="inscricao_fim",
                                        now=NOON)
        self.assertTrue(case["verificacoes"])

    def test_concurso_de_outra_versao_e_recusado(self):
        _, version = self.prepare()
        with self.assertRaisesRegex(ValueError, "não corresponde"):
            deadline_revalidation.verify_version(
                self.db, version, contest_id="c2", apply=False)

    def test_versao_inexistente(self):
        with self.assertRaises(ValueError):
            deadline_revalidation.verify_version(self.db, "nao-existe", apply=False)


class ApiTest(Base):
    def setUp(self):
        super().setUp()
        self.three_events()
        self.server = create_server(self.db, host="127.0.0.1", port=0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_address[1]

    def request(self, path, method="GET", body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"} if payload else {}
        conn.request(method, path, body=payload, headers=headers)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, data

    def test_rotas_de_auditoria(self):
        status, body = self.request("/api/prazos/auditoria?limit=5")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["por_causa"], {"evento_diferente": 1})
        status, body = self.request(
            "/api/prazos/caso?contest_id=c1&group=inscricao_fim")
        self.assertEqual(status, 200)
        case = json.loads(body)
        self.assertEqual(case["causa"], "evento_diferente")
        self.assertEqual(case["valores_sustentados"], ["2026-11-26"])

    def test_parametros_invalidos(self):
        for path in ("/api/prazos/caso", "/api/prazos/caso?contest_id=c1",
                     "/api/prazos/auditoria?cause=xyz",
                     "/api/prazos/auditoria?group=xyz",
                     "/api/prazos/auditoria?desconhecido=1"):
            status, _ = self.request(path)
            self.assertEqual(status, 400, path)

    def test_verificar_documento_simulacao(self):
        with closing(sqlite3.connect(self.db)) as conn:
            version = conn.execute("SELECT id FROM versoes_documento").fetchone()[0]
        status, body = self.request("/api/prazos/verificar-documento", "POST",
                                    {"version_id": version, "contest_id": "c1"})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["dry_run"])
        self.assertEqual(self.counts()[3], 0)

    def test_calendario_com_groups(self):
        # O fixture só tem `inscricao_fim`; `data_prova` é pedido válido e fica vazio.
        status, body = self.request(
            "/api/prazos/calendario?groups=inscricao_fim,data_prova")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(set(payload["por_grupo"]), {"inscricao_fim"})
        self.assertEqual(payload["denominador"]["filtros"]["groups"],
                         ["data_prova", "inscricao_fim"])
        status, _ = self.request("/api/prazos/calendario?groups=inscricao_fim,xyz")
        self.assertEqual(status, 400)

    def test_verificar_documento_sem_versao(self):
        status, _ = self.request("/api/prazos/verificar-documento", "POST", {})
        self.assertEqual(status, 400)


class SchemaTest(Base):
    def test_schema_v21(self):
        self.assertEqual(SCHEMA_VERSION, 21)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 21)
            self.assertTrue(conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='idx_revalidacoes_prazo'").fetchone())


if __name__ == "__main__":
    unittest.main()
