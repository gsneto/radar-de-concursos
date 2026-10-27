"""Piloto de revisão, reconciliação assistida e decisões independentes (Fase 43).

Testes de leitura usam a base real em modo somente leitura. Testes de decisão usam uma
**cópia isolada** do SQLite — nenhuma decisão humana é gravada na base real.
"""

import json
import os
import shutil
import subprocess
import sqlite3
import tempfile
import unittest
from contextlib import closing

from radar import identity_suggestions, pilot, review, review_groups
from tests.test_portfolio_f36 import make_db

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_DB = os.path.join(ROOT, "data", "radar.sqlite3")
# data/ fica fora do Git: em clone limpo (CI) os testes sobre a base real são pulados,
# não reprovados. Os testes puros deste arquivo rodam sempre.
requires_real_db = unittest.skipUnless(
    os.path.exists(REAL_DB), "base real ausente (data/ fica fora do Git)")
SEDUC = "f4235e23-a5b4-45c2-a949-e758c277eca4"
LABEL_PREFIX = "cargo do documento não reconciliado: "


def _copy_db():
    """Cópia isolada do banco real, com os PDFs originais ligados em somente leitura.

    O piloto precisa do artefato para reconstruir o contexto da linha; a cópia do
    SQLite recebe um junction para o diretório de documentos, então nenhuma decisão
    de teste toca a base real.
    """
    tmp = tempfile.TemporaryDirectory()
    target = os.path.join(tmp.name, "radar.sqlite3")
    shutil.copy2(REAL_DB, target)
    source = REAL_DB + ".documents"
    if os.path.isdir(source):
        destination = target + ".documents"
        subprocess.run(["cmd", "/c", "mklink", "/J", destination, source],
                       check=False, capture_output=True)
    return tmp, target


def _line_proposals(db, *, contest=SEDUC, field_count=4):
    """Primeira linha do quadro com todos os campos, com os ids das propostas."""
    with closing(sqlite3.connect(db)) as conn:
        rows = conn.execute(
            "SELECT p.id, p.field_name, p.value_json, e.version_id, e.block_id, "
            "e.page_number, e.start_offset, e.end_offset, p.ambiguity_reason "
            "FROM propostas_campo p JOIN evidencias e ON e.id=p.evidence_id "
            "WHERE p.contest_id=? AND p.extraction_method='quadro-colunas-pdf' "
            "ORDER BY e.page_number, e.start_offset", (contest,)).fetchall()
    groups = {}
    for row in rows:
        key = (row[3], row[4], row[5], row[6], row[7])
        groups.setdefault(key, []).append({
            "proposal_id": row[0], "field_name": row[1],
            "value": json.loads(row[2]), "label": row[8]})
    for key, items in groups.items():
        if len(items) == field_count:
            return key, items
    raise AssertionError("nenhuma linha com todos os campos")


def _state(db, proposal_id):
    with closing(sqlite3.connect(db)) as conn:
        row = conn.execute(
            "SELECT decision FROM revisoes_campo WHERE proposal_id=? "
            "ORDER BY reviewed_at DESC, rowid DESC LIMIT 1", (proposal_id,)).fetchone()
    return row[0] if row else None


def _count(db, table):
    with closing(sqlite3.connect(db)) as conn:
        return conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]


@requires_real_db
class PilotSelectionTest(unittest.TestCase):
    """Seleção determinística e diversa sobre a base real (somente leitura)."""

    @classmethod
    def setUpClass(cls):
        cls.report = pilot.report(REAL_DB, contest_id=SEDUC)
        cls.again = pilot.report(REAL_DB, contest_id=SEDUC)

    def test_tamanho_e_determinismo(self):
        self.assertGreaterEqual(self.report["linhas_selecionadas"], 10)
        self.assertLessEqual(self.report["linhas_selecionadas"], 20)
        first = [ficha["linha_id"] for ficha in self.report["fichas"]]
        second = [ficha["linha_id"] for ficha in self.again["fichas"]]
        self.assertEqual(first, second)

    def test_diversidade_de_casos(self):
        casos = {motivo["caso"] for ficha in self.report["fichas"]
                 for motivo in ficha["porque"]}
        for esperado in ("pi_exclusivo", "ppiq", "pi_pq", "reserva_zero",
                         "multipagina", "cargo_continuado"):
            self.assertIn(esperado, casos)
        self.assertGreaterEqual(len(self.report["distribuicao"]["regionais"]), 5)
        self.assertGreaterEqual(len(self.report["distribuicao"]["cargos"]), 3)
        por_regional = {}
        for ficha in self.report["fichas"]:
            regional = ficha["linha"]["regional"]
            por_regional[regional] = por_regional.get(regional, 0) + 1
        # Teto de duas linhas por regional, salvo compromisso registrado.
        if not self.report["compromissos"]:
            self.assertLessEqual(max(por_regional.values()), 2)
        self.assertEqual(self.report["compromissos"], [])

    def test_ficha_tem_contexto_e_efeitos(self):
        for ficha in self.report["fichas"]:
            self.assertTrue(ficha["porque"])
            self.assertTrue(ficha["documento"]["sha256"])
            self.assertTrue(ficha["linha"]["cabecalho"])
            self.assertTrue(ficha["linha"]["trecho"])
            self.assertIsNotNone(ficha["linha"]["total_publicado"])
            self.assertTrue(ficha["campos_com_evidencia"])
            self.assertIsNotNone(ficha["identidade"]["sugestao"])
            for acao in ficha["acoes_humanas"]:
                self.assertIn("validado", acao["efeito"])
                self.assertIn("rejeitado", acao["efeito"])

    def test_abrir_o_piloto_nao_cria_decisao(self):
        self.assertEqual(_count(REAL_DB, "revisoes_campo"), 0)
        self.assertEqual(_count(REAL_DB, "valores_atuais"), 0)
        self.assertFalse(self.report["revisao"]["piloto_revisado"])

    def test_disponiveis(self):
        available = pilot.available(REAL_DB)
        contest_ids = {item["contest_id"] for item in available["itens"]}
        self.assertIn(SEDUC, contest_ids)
        self.assertGreaterEqual(available["itens"][0]["linhas"], 10)


@requires_real_db
class PilotContextTypesTest(unittest.TestCase):
    """Notação e texto não publicam coluna PI nem zero explícito."""

    def test_notacao_nao_quebra_nem_vira_zero(self):
        report = pilot.report(REAL_DB, contest_id="4b5579c4-2389-457f-806f-43cd9f95a0ff")
        self.assertGreaterEqual(report["linhas_selecionadas"], 1)
        casos = {motivo["caso"] for ficha in report["fichas"]
                 for motivo in ficha["porque"]}
        self.assertIn("reserva_sem_quantidade", casos)
        self.assertNotIn("reserva_zero", casos)
        self.assertNotIn("pi_exclusivo", casos)

    def test_texto_nao_vira_zero(self):
        report = pilot.report(REAL_DB, contest_id="7c54d7df-a2b2-43ed-a0cd-f0c65ca686c4")
        self.assertGreaterEqual(report["linhas_selecionadas"], 1)
        casos = {motivo["caso"] for ficha in report["fichas"]
                 for motivo in ficha["porque"]}
        self.assertNotIn("reserva_zero", casos)

    def test_todo_concurso_disponivel_produz_relatorio(self):
        for item in pilot.available(REAL_DB)["itens"]:
            report = pilot.report(REAL_DB, contest_id=item["contest_id"], size=10)
            self.assertGreaterEqual(report["linhas_selecionadas"], 1,
                                    item["contest_id"])


@requires_real_db
class IdentitySuggestionTest(unittest.TestCase):
    """Granularidade: cargo+formação é identidade; regional é dimensão da oportunidade."""

    @classmethod
    def setUpClass(cls):
        cls.report = identity_suggestions.report(REAL_DB, contest_id=SEDUC)

    def test_nao_sao_381_cargos(self):
        self.assertEqual(self.report["linhas"], 381)
        self.assertEqual(self.report["identidades_candidatas"], 26)
        self.assertEqual(self.report["regionais"], 24)
        self.assertEqual(sum(item["linhas"] for item in self.report["itens"]), 381)

    def test_regional_nao_faz_parte_da_identidade(self):
        for item in self.report["itens"]:
            self.assertNotIn("DRE", item["cargo"])
            self.assertNotIn("DRE", item["especialidade"] or "")
            self.assertGreaterEqual(len(item["regionais"]), 1)
            self.assertTrue(item["evidencia"])
            self.assertTrue(item["evidencia"][0]["quote"])

    def test_sugestao_nao_e_reconciliacao(self):
        for item in self.report["itens"]:
            self.assertIn(item["acao_sugerida"],
                          ("criar_identidade", "reconciliar_com_identidade_existente"))
            self.assertEqual(item["linhas_confirmadas"], 0)
        self.assertIn("não reconciliação", self.report["limitacao"])


class IdentityNormalizationTest(unittest.TestCase):
    """Normalização de rótulo: funções puras, sem base real."""

    def test_recomposicao_so_com_prova_no_documento(self):
        # "Especialista em" + "Educação" não vira "Especialistaem Educação".
        joined, changed = identity_suggestions.join_cut_words(
            "Especialista em Educação", {"especialista", "em", "educação"})
        self.assertEqual(joined, "Especialista em Educação")
        self.assertFalse(changed)
        # "Governament al" vira "Governamental" quando o documento publica a forma.
        joined, changed = identity_suggestions.join_cut_words(
            "Gestão Governament al", {"gestão", "governamental"})
        self.assertEqual(joined, "Gestão Governamental")
        self.assertTrue(changed)

    def test_formacao_repetida_nao_vira_especialidade(self):
        result = identity_suggestions.normalize_identity(
            "Assistente de Gestão Governamental e Educacional",
            "Assistente de Gestão Governamental e Educacional")
        self.assertIsNone(result["especialidade"])
        self.assertIn("especialidade_repetida",
                      [aviso["codigo"] for aviso in result["avisos"]])

    def test_cargo_continuado_na_formacao(self):
        result = identity_suggestions.normalize_identity(
            "Analista de Gestão Governamental e", "Administraçã o",
            {"administração", "analista", "de", "gestão", "governamental"})
        self.assertEqual(result["cargo"], "Analista de Gestão Governamental e Administração")
        self.assertIsNone(result["especialidade"])
        self.assertIn("cargo_continuado_na_formacao",
                      [aviso["codigo"] for aviso in result["avisos"]])


@requires_real_db
class IndependentDecisionTest(unittest.TestCase):
    """Cada decisão afeta somente o campo escolhido, numa cópia isolada da base."""

    def setUp(self):
        self.tmp, self.db = _copy_db()
        self.addCleanup(self.tmp.cleanup)
        self.key, self.items = _line_proposals(self.db)
        self.by_field = {item["field_name"]: item for item in self.items}

    def decide(self, field, decision, **kwargs):
        return review.decide_proposal(
            self.db, self.by_field[field]["proposal_id"], decision,
            reviewer="teste", reason="conferido no documento", origin="cli", **kwargs)

    def test_confirmar_total_nao_confirma_indigena(self):
        self.decide("immediate_vacancies", "validado")
        self.assertEqual(_state(self.db, self.by_field["immediate_vacancies"]["proposal_id"]),
                         "validado")
        for field in ("indigenous_vacancies", "unified_ppiq_vacancies",
                      "unified_pi_pq_vacancies"):
            self.assertIsNone(_state(self.db, self.by_field[field]["proposal_id"]))
        self.assertEqual(_count(self.db, "valores_atuais"), 0)

    def test_confirmar_uma_modalidade_nao_confirma_as_demais(self):
        self.decide("indigenous_vacancies", "validado")
        self.assertIsNone(_state(self.db, self.by_field["unified_ppiq_vacancies"][
            "proposal_id"]))
        self.assertIsNone(_state(self.db, self.by_field["unified_pi_pq_vacancies"][
            "proposal_id"]))

    def test_rejeitar_preserva_evidencia_e_proposta(self):
        proposal = self.by_field["indigenous_vacancies"]["proposal_id"]
        self.decide("indigenous_vacancies", "rejeitado")
        self.assertEqual(_state(self.db, proposal), "rejeitado")
        with closing(sqlite3.connect(self.db)) as conn:
            row = conn.execute(
                "SELECT e.quote, e.page_number FROM propostas_campo p "
                "JOIN evidencias e ON e.id=p.evidence_id WHERE p.id=?",
                (proposal,)).fetchone()
        self.assertTrue(row[0])
        self.assertIsNotNone(row[1])

    def test_correcao_preserva_original_e_proveniencia(self):
        proposal = self.by_field["indigenous_vacancies"]["proposal_id"]
        original = self.by_field["indigenous_vacancies"]["value"]
        result = self.decide("indigenous_vacancies", "corrigido", value=original + 1)
        self.assertTrue(result["derived_proposal_id"])
        with closing(sqlite3.connect(self.db)) as conn:
            original_row = conn.execute(
                "SELECT value_json, extraction_method FROM propostas_campo WHERE id=?",
                (proposal,)).fetchone()
            derived = conn.execute(
                "SELECT value_json, extraction_method FROM propostas_campo WHERE id=?",
                (result["derived_proposal_id"],)).fetchone()
        self.assertEqual(json.loads(original_row[0]), original)
        self.assertEqual(original_row[1], "quadro-colunas-pdf")
        self.assertEqual(json.loads(derived[0]), original + 1)
        self.assertEqual(derived[1], "correcao_humana")

    def test_reabrir_preserva_historico(self):
        proposal = self.by_field["immediate_vacancies"]["proposal_id"]
        self.decide("immediate_vacancies", "validado")
        self.decide("immediate_vacancies", "reaberto")
        with closing(sqlite3.connect(self.db)) as conn:
            decisions = [row[0] for row in conn.execute(
                "SELECT decision FROM revisoes_campo WHERE proposal_id=? "
                "ORDER BY reviewed_at, rowid", (proposal,))]
        self.assertEqual(decisions, ["validado", "reaberto"])
        self.assertEqual(_state(self.db, proposal), "reaberto")

    def test_valor_vigente_exige_validacao(self):
        proposal = self.by_field["indigenous_vacancies"]["proposal_id"]
        with self.assertRaises(ValueError):
            review.select_current_value(self.db, proposal, "teste", "tentar antes")
        self.decide("indigenous_vacancies", "validado")
        result = review.select_current_value(self.db, proposal, "teste", "confirmado")
        self.assertFalse(result["duplicada"])
        self.assertEqual(_count(self.db, "valores_atuais"), 1)

    def test_ambiguo_nao_altera_outros_campos(self):
        self.decide("unified_ppiq_vacancies", "ambiguo")
        self.assertEqual(_state(self.db, self.by_field["unified_ppiq_vacancies"][
            "proposal_id"]), "ambiguo")
        for field in ("immediate_vacancies", "indigenous_vacancies",
                      "unified_pi_pq_vacancies"):
            self.assertIsNone(_state(self.db, self.by_field[field]["proposal_id"]))

    def test_decidir_campos_nao_confirma_identidade_do_cargo(self):
        for field in self.by_field:
            self.decide(field, "validado")
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM reconciliacoes_cargo").fetchone()[0], 0)
        # A identidade só muda por decisão própria na Mesa de identidades.
        self.assertEqual(_count(self.db, "valores_atuais"), 0)

    def test_decisao_nao_afeta_outra_linha(self):
        other_key, other_items = _line_proposals(self.db, field_count=4)
        # usa a segunda linha distinta encontrada
        with closing(sqlite3.connect(self.db)) as conn:
            rows = conn.execute(
                "SELECT p.id, e.version_id, e.block_id, e.page_number, e.start_offset, "
                "e.end_offset FROM propostas_campo p JOIN evidencias e ON e.id=p.evidence_id "
                "WHERE p.contest_id=? AND p.extraction_method='quadro-colunas-pdf' "
                "ORDER BY e.page_number, e.start_offset", (SEDUC,)).fetchall()
        groups = {}
        for row in rows:
            groups.setdefault(tuple(row[1:]), []).append(row[0])
        second = next(ids for key, ids in groups.items()
                      if key != self.key and len(ids) == 4)
        self.decide("immediate_vacancies", "validado")
        for proposal in second:
            self.assertIsNone(_state(self.db, proposal))


@requires_real_db
class StaleEvidenceTest(unittest.TestCase):
    """Evidência obsoleta não é aceita silenciosamente."""

    def setUp(self):
        self.tmp, self.db = _copy_db()
        self.addCleanup(self.tmp.cleanup)
        self.key, self.items = _line_proposals(self.db)
        self.by_field = {item["field_name"]: item for item in self.items}

    def _fingerprint(self, proposal_id):
        with closing(sqlite3.connect(self.db)) as conn:
            row = conn.execute(
                "SELECT p.value_json, e.quote, e.version_id, e.start_offset, e.end_offset "
                "FROM propostas_campo p JOIN evidencias e ON e.id=p.evidence_id "
                "WHERE p.id=?", (proposal_id,)).fetchone()
        return review._evidence_hash(row[0], row[1], row[2], row[3], row[4])

    def test_hash_errado_bloqueia(self):
        proposal = self.by_field["immediate_vacancies"]["proposal_id"]
        with self.assertRaises(ValueError):
            review.decide_proposal(self.db, proposal, "validado", reviewer="teste",
                                   reason="conferido", origin="cli",
                                   expected_evidence_sha256="0" * 64)
        self.assertIsNone(_state(self.db, proposal))

    def test_evidencia_alterada_bloqueia_hash_antigo(self):
        proposal = self.by_field["immediate_vacancies"]["proposal_id"]
        old = self._fingerprint(proposal)
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("UPDATE propostas_campo SET value_json=? WHERE id=?",
                         (json.dumps(999), proposal))
        with self.assertRaises(ValueError):
            review.decide_proposal(self.db, proposal, "validado", reviewer="teste",
                                   reason="conferido", origin="cli",
                                   expected_evidence_sha256=old)
        self.assertIsNone(_state(self.db, proposal))

    def test_lote_bloqueia_proposta_alterada(self):
        lote = review.open_batch(
            self.db, created_by="teste",
            filters={"contest_id": SEDUC, "field_name": "immediate_vacancies",
                     "state": "pendente"}, size=5)
        item = lote["itens"][0]
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("UPDATE propostas_campo SET value_json=? WHERE id=?",
                         (json.dumps(1234), item["proposal_id"]))
        with self.assertRaises(ValueError):
            review.decide_proposal(self.db, item["proposal_id"], "validado",
                                   reviewer="teste", reason="conferido", origin="cli",
                                   lote_id=lote["lote_id"])
        self.assertIsNone(_state(self.db, item["proposal_id"]))

    def test_lote_bloqueia_quando_surge_nova_proposta(self):
        lote = review.open_batch(
            self.db, created_by="teste",
            filters={"contest_id": SEDUC, "field_name": "immediate_vacancies",
                     "state": "pendente"}, size=5)
        item = lote["itens"][0]
        with closing(sqlite3.connect(self.db)) as conn, conn:
            # Nova proposta no mesmo escopo/campo: o conjunto que o operador viu mudou.
            evidence = conn.execute(
                "SELECT evidence_id, role_id FROM propostas_campo WHERE id=?",
                (item["proposal_id"],)).fetchone()
            conn.execute(
                "INSERT INTO propostas_campo (id,contest_id,role_id,field_name,value_json,"
                "value_type,evidence_id,extraction_method,ambiguity_reason,extracted_at) "
                "SELECT 'nova-proposta-teste', contest_id, role_id, field_name, value_json, "
                "value_type, evidence_id, 'quadro-colunas-pdf', ambiguity_reason, "
                "'2026-10-19T00:00:00+00:00' FROM propostas_campo WHERE id=?",
                (item["proposal_id"],))
        with self.assertRaises(ValueError):
            review.decide_proposal(self.db, item["proposal_id"], "validado",
                                   reviewer="teste", reason="conferido", origin="cli",
                                   lote_id=lote["lote_id"])

    def test_sessao_retomavel_mantem_progresso(self):
        lote = review.open_batch(
            self.db, created_by="teste",
            filters={"contest_id": SEDUC, "field_name": "immediate_vacancies",
                     "state": "pendente"}, size=5)
        item = lote["itens"][0]
        review.decide_proposal(self.db, item["proposal_id"], "validado",
                               reviewer="teste", reason="conferido", origin="cli",
                               lote_id=lote["lote_id"])
        reopened = review.batch_status(self.db, lote["lote_id"])
        self.assertEqual(reopened["progresso"]["decididos"], 1)
        self.assertFalse(reopened["progresso"]["alterados"])


@requires_real_db
class ScopeSnapshotTest(unittest.TestCase):
    """Nova proposta no mesmo campo/escopo bloqueia decisão por linha."""

    def setUp(self):
        self.tmp, self.db = _copy_db()
        self.addCleanup(self.tmp.cleanup)

    def test_snapshot_de_escopo_bloqueia_nova_proposta(self):
        group = review_groups.groups(self.db, contest_id=SEDUC, state="todos",
                                     limit=1)
        item = group["itens"][0]
        proposal = item["propostas"][0]
        snapshot = proposal["scope_snapshot"]
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(
                "INSERT INTO propostas_campo (id,contest_id,role_id,field_name,value_json,"
                "value_type,evidence_id,extraction_method,ambiguity_reason,extracted_at) "
                "SELECT 'competidora-teste', contest_id, role_id, field_name, value_json, "
                "value_type, evidence_id, 'quadro-colunas-pdf', ambiguity_reason, "
                "'2026-10-19T00:00:00+00:00' FROM propostas_campo WHERE id=?",
                (proposal["proposal_id"],))
        with self.assertRaises(ValueError):
            review.decide_proposal(
                self.db, proposal["proposal_id"], "validado", reviewer="teste",
                reason="conferido", origin="cli",
                expected_evidence_sha256=proposal["evidence_sha256"],
                expected_scope_snapshot=snapshot)
        self.assertIsNone(_state(self.db, proposal["proposal_id"]))

    def test_snapshot_correto_permite_decisao(self):
        group = review_groups.groups(self.db, contest_id=SEDUC, state="todos",
                                     limit=1)
        proposal = group["itens"][0]["propostas"][0]
        result = review.decide_proposal(
            self.db, proposal["proposal_id"], "validado", reviewer="teste",
            reason="conferido", origin="cli",
            expected_evidence_sha256=proposal["evidence_sha256"],
            expected_scope_snapshot=proposal["scope_snapshot"])
        self.assertEqual(result["decision"], "validado")


@requires_real_db
class CorrectionDedupeTest(unittest.TestCase):
    """Correção não duplica o campo na ficha do piloto."""

    def setUp(self):
        self.tmp, self.db = _copy_db()
        self.addCleanup(self.tmp.cleanup)

    def test_campo_corrigido_aparece_uma_vez(self):
        page = review_groups.groups(self.db, contest_id=SEDUC, state="todos",
                                    limit=50)
        item = next(i for i in page["itens"]
                    if any(p["field_name"] == "indigenous_vacancies"
                           for p in i["propostas"]))
        proposal = next(p for p in item["propostas"]
                        if p["field_name"] == "indigenous_vacancies")
        review.decide_proposal(self.db, proposal["proposal_id"], "corrigido",
                               reviewer="teste", reason="coluna lida errado",
                               origin="cli", value=proposal["value"] + 1)
        refreshed = review_groups.groups(
            self.db, contest_id=SEDUC, state="todos",
            linha=item["linha_id"])["itens"][0]
        complete, uncertain = pilot._fields(refreshed)
        entries = [entry for entry in complete + uncertain
                   if entry["field_name"] == "indigenous_vacancies"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["value"], proposal["value"] + 1)


class CacheConcurrencyTest(unittest.TestCase):
    """Cache em processo não quebra com requisições simultâneas."""

    @requires_real_db
    def test_grupos_simultaneos(self):
        import threading
        results, errors = [], []

        def run():
            try:
                page = review_groups.groups(REAL_DB, contest_id=SEDUC,
                                            contexto=True, limit=5)
                results.append(page["total"])
            except Exception as error:  # pragma: no cover - diagnóstico
                errors.append(error)

        threads = [threading.Thread(target=run) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 4)
        self.assertEqual(len(set(results)), 1)


@requires_real_db
class ProgressTest(unittest.TestCase):
    """Progresso conta propostas reais decididas, inclusive valor vigente."""

    def setUp(self):
        self.tmp, self.db = _copy_db()
        self.addCleanup(self.tmp.cleanup)

    def test_denominador_ignora_notas_sem_proposta(self):
        report = pilot.report(self.db, contest_id=SEDUC)
        revisao = report["revisao"]
        self.assertEqual(revisao["campos_totais"], 64)
        self.assertEqual(revisao["notas_sem_proposta"], 18)
        self.assertEqual(revisao["campos_decididos"], 0)
        self.assertEqual(revisao["campos_pendentes"], 64)

    def test_valor_vigente_conta_como_decidido(self):
        page = review_groups.groups(self.db, contest_id=SEDUC, state="todos",
                                    limit=50)
        item = next(i for i in page["itens"] if len(i["propostas"]) >= 4)
        antes = pilot.report(self.db, contest_id=SEDUC)["revisao"]
        for proposal in item["propostas"]:
            review.decide_proposal(self.db, proposal["proposal_id"], "validado",
                                   reviewer="teste", reason="conferido",
                                   origin="cli")
        review.select_current_value(self.db, item["propostas"][0]["proposal_id"],
                                    "teste", "vigente")
        depois = pilot.report(self.db, contest_id=SEDUC)["revisao"]
        decididas = len(item["propostas"])
        self.assertEqual(depois["campos_decididos"],
                         antes["campos_decididos"] + decididas)
        self.assertEqual(depois["campos_pendentes"],
                         antes["campos_pendentes"] - decididas)
        self.assertEqual(depois["linhas_decididas"], antes["linhas_decididas"] + 1)


@requires_real_db
class ApiTest(unittest.TestCase):
    """Rotas aditivas e somente leitura do piloto."""

    @classmethod
    def setUpClass(cls):
        import threading
        from radar.server import create_server
        cls.tmp = None
        cls.db = REAL_DB
        cls.server = create_server(cls.db, host="127.0.0.1", port=0)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def get(self, path):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        conn.request("GET", path)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, data

    def test_pilotos(self):
        status, body = self.get("/api/revisao/pilotos")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertIn(SEDUC, {item["contest_id"] for item in payload["itens"]})

    def test_piloto(self):
        status, body = self.get("/api/revisao/piloto?contest_id=" + SEDUC + "&size=12")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["version"], "pilot_v1")
        self.assertEqual(payload["linhas_selecionadas"], 12)
        self.assertEqual(payload["revisao"]["decisoes_registradas"], 0)

    def test_identidades(self):
        status, body = self.get("/api/revisao/identidades?contest_id=" + SEDUC)
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["identidades_candidatas"], 26)

    def test_parametros_invalidos(self):
        for path in ("/api/revisao/piloto", "/api/revisao/identidades",
                     "/api/revisao/piloto?contest_id=" + SEDUC + "&x=1",
                     "/api/revisao/pilotos?x=1"):
            status, _ = self.get(path)
            self.assertEqual(status, 400, path)

    def test_rotas_nao_criam_decisao(self):
        self.get("/api/revisao/piloto?contest_id=" + SEDUC)
        self.get("/api/revisao/identidades?contest_id=" + SEDUC)
        self.assertEqual(_count(self.db, "revisoes_campo"), 0)
        self.assertEqual(_count(self.db, "valores_atuais"), 0)


@requires_real_db
class PrewarmTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = _copy_db()
        self.addCleanup(self.tmp.cleanup)

    def test_prewarm_nao_grava(self):
        before = (_count(self.db, "propostas_campo"), _count(self.db, "revisoes_campo"),
                  _count(self.db, "documentos"))
        result = pilot.prewarm(self.db, contest_id=SEDUC)
        after = (_count(self.db, "propostas_campo"), _count(self.db, "revisoes_campo"),
                 _count(self.db, "documentos"))
        self.assertEqual(before, after)
        self.assertEqual(result["gravacoes"], 0)


class UiStaticTest(unittest.TestCase):
    """A UI oferece decisão por campo e não tem confirmação da linha inteira."""

    def setUp(self):
        self.html = open(os.path.join(ROOT, "web", "index.html"), encoding="utf-8").read()
        self.js = open(os.path.join(ROOT, "web", "app.js"), encoding="utf-8").read()

    def test_painel_do_piloto(self):
        for marker in ('id="piloto-panel"', 'id="piloto-select"',
                       'id="piloto-linha"', 'id="piloto-status"'):
            self.assertIn(marker, self.html)
        self.assertIn("'progress'", self.js)
        self.assertIn("Próxima linha pendente", self.js)

    def test_sem_confirmacao_da_linha_inteira(self):
        for proibido in ("confirmarLinha", "aprovarLinha", "validarLinha",
                         "decidirLinha", "confirmarTudo", "aprovarTodos"):
            self.assertNotIn(proibido, self.js)
        # Cada decisão envia um único proposal_id.
        self.assertIn("'/api/revisao/proposta/' + encodeURIComponent(proposalId)", self.js)

    def test_avisos_e_consequencias(self):
        self.assertIn("vaga unificada", self.js)
        self.assertIn("nunca substitui o total", self.js)
        self.assertIn("consequencia", self.js)
        self.assertIn("Histórico", self.js)


if __name__ == "__main__":
    unittest.main()
