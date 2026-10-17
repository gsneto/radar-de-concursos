"""Extração do conteúdo programático: seções, hierarquia, evidência e preservação."""

import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from radar import program_content
from radar.document_store import (connect_documents, ensure_observation, migrate_document_schema,
                                  record_analysis, record_version, register_document)
from radar import knowledge_store


def _now():
    return datetime.now(timezone.utc).isoformat()


class ClassifyTest(unittest.TestCase):
    def test_titulos_de_secao(self):
        for line in ("CONTEÚDO PROGRAMÁTICO", "CONTEUDOS PROGRAMATICOS", "PROGRAMA DAS PROVAS",
                     "CONHECIMENTOS BÁSICOS", "CONHECIMENTOS ESPECÍFICOS",
                     "ANEXO II - CONTEÚDO PROGRAMÁTICO"):
            self.assertTrue(program_content.is_content_heading(line), line)

    def test_nao_e_secao_de_conteudo(self):
        self.assertFalse(program_content.is_content_heading("DAS INSCRIÇÕES"))
        self.assertFalse(program_content.is_content_heading("CRONOGRAMA"))
        self.assertFalse(program_content.is_content_heading("texto qualquer"))

    def test_classificacao_de_linhas(self):
        self.assertEqual(program_content.classify_line("LÍNGUA PORTUGUESA"),
                         ("conteudo_disciplina", "LÍNGUA PORTUGUESA"))
        self.assertEqual(program_content.classify_line("1 Redes de computadores"),
                         ("conteudo_topico", "Redes de computadores"))
        self.assertEqual(program_content.classify_line("1.1 Protocolos"),
                         ("conteudo_subtopico", "Protocolos"))
        self.assertEqual(program_content.classify_line("a) Ortografia"),
                         ("conteudo_topico", "Ortografia"))
        self.assertEqual(program_content.classify_line("- Compreensão de texto"),
                         ("conteudo_topico", "Compreensão de texto"))

    def test_texto_corrido_nao_vira_item(self):
        # Linha explicativa longa em minúsculas não é tópico nem disciplina.
        self.assertIsNone(program_content.classify_line(
            "o candidato deverá demonstrar domínio das regras gramaticais vigentes."))

    def test_disciplina_numerada_maiuscula(self):
        self.assertEqual(program_content.classify_line("3 MATEMÁTICA"),
                         ("conteudo_disciplina", "MATEMÁTICA"))

    def test_titulo_de_parada(self):
        for line in ("CRONOGRAMA", "DAS INSCRIÇÕES", "DOS REQUISITOS", "BIBLIOGRAFIA"):
            self.assertTrue(program_content.is_stop_heading(line), line)

    def test_secoes_com_sufixo_reconhecidas(self):
        # Regressão: variações comuns de título não podem ser perdidas.
        for line in ("CONHECIMENTOS BÁSICOS E ESPECÍFICOS", "CONHECIMENTOS GERAIS E ESPECÍFICOS",
                     "ANEXO I - CONTEÚDO PROGRAMÁTICO DAS PROVAS",
                     "CONTEÚDO PROGRAMÁTICO POR CARGO",
                     "CONTEÚDO PROGRAMÁTICO DAS PROVAS OBJETIVAS"):
            self.assertTrue(program_content.is_content_heading(line), line)

    def test_recursos_como_disciplina_nao_encerra_secao(self):
        # Regressão: "RECURSOS" (disciplina de Direito) não pode encerrar a seção.
        self.assertFalse(program_content.is_stop_heading("RECURSOS"))
        self.assertTrue(program_content.is_stop_heading("DOS RECURSOS"))

    def test_disciplina_numerada_com_ponto(self):
        # Regressão: "1. LÍNGUA PORTUGUESA" é disciplina (não tópico).
        self.assertEqual(program_content.classify_line("1. LÍNGUA PORTUGUESA"),
                         ("conteudo_disciplina", "LÍNGUA PORTUGUESA"))
        self.assertEqual(program_content.classify_line("2. MATEMÁTICA"),
                         ("conteudo_disciplina", "MATEMÁTICA"))

    def test_rotulo_de_tabela_nao_e_disciplina(self):
        # Regressão: rótulos genéricos não viram matéria.
        self.assertIsNone(program_content.classify_line("TOTAL"))
        self.assertIsNone(program_content.classify_line("CARGO: ANALISTA"))

    def test_resto_apos_dois_pontos_vira_topico(self):
        self.assertEqual(program_content.discipline_tail("DIREITO CONSTITUCIONAL: Noções de Estado"),
                         "Noções de Estado")


class ExtractionTest(unittest.TestCase):
    def _blocks(self, pages):
        return [{"page_number": i + 1, "locator": f"p{i+1}", "start_offset": 0,
                 "end_offset": len(t), "text": t} for i, t in enumerate(pages)]

    def test_extrai_dentro_da_secao(self):
        text = ("CONHECIMENTOS ESPECÍFICOS\nINFORMÁTICA\n1 Redes de computadores\n"
                "1.1 Protocolos de comunicação\n2 Banco de dados")
        proposals = program_content.extract_program_content(self._blocks([text]), "c1", label_prefix="x: ")
        fields = [p["field_name"] for p in proposals]
        self.assertIn("conteudo_secao", fields)
        self.assertIn("conteudo_disciplina", fields)
        self.assertEqual(fields.count("conteudo_topico"), 2)
        self.assertEqual(fields.count("conteudo_subtopico"), 1)

    def test_ignora_fora_da_secao(self):
        # Antes da seção, "DAS INSCRIÇÕES" e itens não são conteúdo.
        text = ("DAS INSCRIÇÕES\n1 Período de inscrição\nCONTEÚDO PROGRAMÁTICO\nPORTUGUÊS\n"
                "1 Ortografia")
        proposals = program_content.extract_program_content(self._blocks([text]), "c1", label_prefix="x: ")
        values = [p["evidence"]["quote"] for p in proposals]
        self.assertNotIn("1 Período de inscrição", values)
        self.assertIn("1 Ortografia", values)

    def test_conteudo_entre_paginas(self):
        page1 = "ANEXO II - CONTEÚDO PROGRAMÁTICO\nMATEMÁTICA"
        page2 = "1 Aritmética\n2 Álgebra"
        proposals = program_content.extract_program_content(self._blocks([page1, page2]), "c1", label_prefix="x: ")
        topics = [p for p in proposals if p["field_name"] == "conteudo_topico"]
        self.assertEqual([p["evidence"]["page_number"] for p in topics], [2, 2])
        # A disciplina da página 1 permanece disponível para os tópicos da página 2.
        self.assertEqual([p["evidence"]["quote"] for p in topics], ["1 Aritmética", "2 Álgebra"])

    def test_secao_encerra_em_titulo_de_parada(self):
        text = "CONTEÚDO PROGRAMÁTICO\nPORTUGUÊS\n1 Ortografia\nCRONOGRAMA\n1 Inscrições abertas"
        proposals = program_content.extract_program_content(self._blocks([text]), "c1", label_prefix="x: ")
        values = [p["evidence"]["quote"] for p in proposals]
        self.assertNotIn("1 Inscrições abertas", values)

    def test_sem_secao_de_conteudo(self):
        proposals = program_content.extract_program_content(self._blocks(["EDITAL\nDAS VAGAS\n1 Vaga"]),
                                                            "c1", label_prefix="x: ")
        self.assertEqual(proposals, [])

    def test_evidencia_aponta_pagina(self):
        text = "CONTEÚDO PROGRAMÁTICO\nDIREITO\n1 Constitucional"
        proposals = program_content.extract_program_content(self._blocks([text]), "c1", label_prefix="x: ")
        topic = next(p for p in proposals if p["field_name"] == "conteudo_topico")
        self.assertEqual(topic["evidence"]["page_number"], 1)
        self.assertEqual(topic["evidence"]["quote"], "1 Constitucional")

    def test_candidato_marcado_para_revisao(self):
        text = "CONTEÚDO PROGRAMÁTICO\nDIREITO\n1 Constitucional"
        proposals = program_content.extract_program_content(self._blocks([text]), "c1", label_prefix="x: ")
        for p in proposals:
            self.assertIn("revisar", p["ambiguity_reason"].lower())


class ProgramStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "t.sqlite3")
        migrate_document_schema(self.db)
        self.obs = ensure_observation(self.db, "https://exemplo.test/c1", "c1")
        with closing(connect_documents(self.db)) as conn:
            self.contest = conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                        (self.obs,)).fetchone()[0]

    def _add_version(self, text, key="e.pdf", kind="outro"):
        did = register_document(self.db, dict(
            observation_id=self.obs, kind=kind, official_url=f"https://exemplo.test/c1/{key}",
            title="Edital", discovery_url=f"https://exemplo.test/c1",
            discovery_method="automatico", discovered_at=_now()))
        blocks = [{"page_number": 1, "locator": "p", "start_offset": 0,
                   "end_offset": len(text), "text": text}]
        proposals = program_content.extract_program_content(blocks, self.contest, label_prefix="x: ")
        version = record_version(self.db, did, b"%PDF-1.4 " + text.encode(), dict(
            fetched_at=_now(), fetched_url=f"https://exemplo.test/c1/{key}",
            content_type="application/pdf"))
        record_analysis(self.db, version, blocks, proposals)
        return version

    def test_resolve_program_estrutura(self):
        self._add_version("CONHECIMENTOS ESPECÍFICOS\nINFORMÁTICA\n1 Redes\n1.1 Protocolos")
        prog = knowledge_store.resolve_program(self.db, self.contest)
        self.assertEqual(prog["counts"].get("extraido_nao_revisado"), 2)
        topic = next(t for t in prog["topicos"] if t["value"] == "Redes")
        self.assertEqual(topic["disciplina"], "INFORMÁTICA")
        self.assertEqual(topic["estado"], "extraido_nao_revisado")

    def test_revisao_confirma_item(self):
        self._add_version("CONTEÚDO PROGRAMÁTICO\nDIREITO\n1 Constitucional")
        prog = knowledge_store.resolve_program(self.db, self.contest)
        pid = next(t for t in prog["topicos"] if t["value"] == "Constitucional")["id"]
        from radar.document_review import review_proposal
        review_proposal(self.db, pid, "validado", "revisor", "conferido no edital")
        prog2 = knowledge_store.resolve_program(self.db, self.contest)
        self.assertEqual(prog2["counts"].get("confirmado"), 1)

    def test_rejeicao_preserva_evidencia(self):
        self._add_version("CONTEÚDO PROGRAMÁTICO\nDIREITO\n1 Constitucional")
        prog = knowledge_store.resolve_program(self.db, self.contest)
        pid = next(t for t in prog["topicos"] if t["value"] == "Constitucional")["id"]
        from radar.document_review import review_proposal
        review_proposal(self.db, pid, "rejeitado", "revisor", "não é conteúdo")
        prog2 = knowledge_store.resolve_program(self.db, self.contest)
        rejected = next(t for t in prog2["topicos"] if t["id"] == pid)
        self.assertEqual(rejected["estado"], "rejeitado")
        self.assertTrue(rejected["quote"])  # evidência preservada

    def test_retificacao_preserva_historico(self):
        self._add_version("CONTEÚDO PROGRAMÁTICO\nDIREITO\n1 Constitucional")
        self._add_version("CONTEÚDO PROGRAMÁTICO\nDIREITO\n1 Constitucional\n2 Administrativo",
                          key="ret.pdf", kind="retificacao")
        prog = knowledge_store.resolve_program(self.db, self.contest)
        values = {t["value"] for t in prog["topicos"]}
        self.assertIn("Constitucional", values)
        self.assertIn("Administrativo", values)

    def test_falha_de_extracao_nao_remove_antigos(self):
        self._add_version("CONTEÚDO PROGRAMÁTICO\nDIREITO\n1 Constitucional")
        # Uma versão que não contém conteúdo programático não pode "remover" o antigo.
        self._add_version("DOCUMENTO SEM PROGRAMA", key="outro.pdf")
        prog = knowledge_store.resolve_program(self.db, self.contest)
        self.assertIn("Constitucional", {t["value"] for t in prog["topicos"]})

    def test_conflito_entre_redacoes_vira_ambiguo(self):
        # Mesma chave de conceito com redações divergentes (variação de caixa) sem revisão.
        self._add_version("CONTEÚDO PROGRAMÁTICO\nDIREITO\n1 Direito Constitucional")
        self._add_version("CONTEÚDO PROGRAMÁTICO\nDIREITO\n1 Direito constitucional",
                          key="ret2.pdf", kind="retificacao")
        prog = knowledge_store.resolve_program(self.db, self.contest)
        self.assertIn("ambiguo", {t["estado"] for t in prog["topicos"]})

    def test_topico_sem_disciplina_vira_ambiguo(self):
        # Tópico antes de qualquer disciplina: não é possível situar na hierarquia.
        self._add_version("CONTEÚDO PROGRAMÁTICO\n1 Sem disciplina definida")
        prog = knowledge_store.resolve_program(self.db, self.contest)
        self.assertEqual({t["estado"] for t in prog["topicos"]}, {"ambiguo"})

    def test_conteudo_nao_gera_conflito_escalar(self):
        # Regressão: conteúdo programático multi-item não é "conflito" de campo em /detalhes.
        from radar.document_store import get_competition_details
        self._add_version("CONHECIMENTOS ESPECÍFICOS\nINFORMÁTICA\n1 Redes\n2 Banco de dados\n3 Segurança")
        details = get_competition_details(self.db, self.contest)
        self.assertFalse([c for c in details["conflicts"] if c["field_name"].startswith("conteudo_")])

    def test_evidencia_tem_hash_da_versao(self):
        self._add_version("CONTEÚDO PROGRAMÁTICO\nDIREITO\n1 Constitucional")
        prog = knowledge_store.resolve_program(self.db, self.contest)
        topic = next(t for t in prog["topicos"] if t["value"] == "Constitucional")
        self.assertTrue(topic["version_sha256"])


if __name__ == "__main__":
    unittest.main()
