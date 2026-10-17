"""Perfil de conhecimentos, cobertura e perspectivas de preparação (funções puras + store)."""

import tempfile
import unittest
from pathlib import Path

from radar import knowledge_store, preparation
from radar.document_store import migrate_document_schema


class NormalizeTest(unittest.TestCase):
    def test_normalizacao_remove_acento_e_caixa(self):
        self.assertEqual(preparation.normalize_text("Segurança da Informação"),
                         "seguranca da informacao")

    def test_chave_de_conceito_estavel(self):
        a = preparation.conceito_key("Informática", "Redes de computadores")
        b = preparation.conceito_key("INFORMÁTICA", "redes de computadores")
        self.assertEqual(a, b)

    def test_disciplina_diferencia_conceitos_iguais(self):
        # "Segurança" em redes vs. legislação NÃO são o mesmo conceito (disciplinas distintas).
        redes = preparation.conceito_key("Redes", "Segurança")
        direito = preparation.conceito_key("Legislação", "Segurança")
        self.assertNotEqual(redes, direito)

    def test_stopwords_ignoradas(self):
        a = preparation.conceito_key("TI", "Banco de dados")
        b = preparation.conceito_key("TI", "banco dados")
        self.assertEqual(a, b)


class CoverageTest(unittest.TestCase):
    def _topic(self, key, estado="extraido_nao_revisado", disciplina="TI", rotulo="X"):
        return {"conceito_key": key, "disciplina": disciplina, "rotulo": rotulo, "estado": estado}

    def test_cobertura_sobre_identificados(self):
        topics = [self._topic("a"), self._topic("b"), self._topic("c", estado="ambiguo")]
        profile = {"a": {"nivel": "avancado"}, "b": {"nivel": "nao_conheco"}}
        out = preparation.coverage(topics, profile)
        self.assertEqual(out["denominator"], 2)  # ambíguo fora
        self.assertEqual(out["known"], 1)
        self.assertEqual(out["pct"], 50)

    def test_nao_extraido_fora_do_denominador(self):
        topics = [self._topic("a"), self._topic("b", estado="nao_extraido"),
                  self._topic("c", estado="rejeitado")]
        out = preparation.coverage(topics, {})
        self.assertEqual(out["denominator"], 1)
        self.assertIn("identificado", out["basis"])

    def test_desconhecido_nao_vira_lacuna_pessoal_automatica(self):
        # Tópico sem perfil conta como "sem_perfil", não como "não conhecido".
        out = preparation.coverage([self._topic("a")], {})
        self.assertEqual(out["counts"]["sem_perfil"], 1)
        self.assertEqual(out["counts"]["nao_conhecidos"], 0)

    def test_sem_topicos_cobertura_nao_calculavel(self):
        out = preparation.coverage([], {})
        self.assertIsNone(out["pct"])
        self.assertIn("não calculável", out["basis"])

    def test_revisar_contabilizado(self):
        topics = [self._topic("a")]
        out = preparation.coverage(topics, {"a": {"nivel": "basico", "revisar": True}})
        self.assertEqual(out["counts"]["revisar"], 1)


class PerspectiveTest(unittest.TestCase):
    def test_incompativel(self):
        self.assertEqual(preparation.perspective(formal_compatible=True, formal_ambiguous=False,
                         formal_incompatible=True, coverage_pct=80, gaps=[], exceptional=False),
                         "compatibilidade_desfavoravel")

    def test_ambiguo_exige_confirmacao(self):
        self.assertEqual(preparation.perspective(formal_compatible=True, formal_ambiguous=True,
                         formal_incompatible=False, coverage_pct=80, gaps=[], exceptional=False),
                         "exige_confirmacao")

    def test_boa_aderencia(self):
        self.assertEqual(preparation.perspective(formal_compatible=True, formal_ambiguous=False,
                         formal_incompatible=False, coverage_pct=80, gaps=[], exceptional=False),
                         "boa_aderencia")

    def test_oportunidade_para_preparar(self):
        self.assertEqual(preparation.perspective(formal_compatible=True, formal_ambiguous=False,
                         formal_incompatible=False, coverage_pct=40, gaps=["x"], exceptional=False),
                         "oportunidade_para_preparar")

    def test_excepcional_com_lacunas(self):
        self.assertEqual(preparation.perspective(formal_compatible=True, formal_ambiguous=False,
                         formal_incompatible=False, coverage_pct=40, gaps=["x"], exceptional=True),
                         "excepcional_com_lacunas")


class ProfileStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "t.sqlite3")
        migrate_document_schema(self.db)

    def test_criar_e_editar_perfil(self):
        knowledge_store.set_profile(self.db, disciplina="TI", rotulo="Redes", nivel="basico")
        knowledge_store.set_profile(self.db, disciplina="TI", rotulo="Redes", nivel="avancado")
        profile = knowledge_store.list_profile(self.db)
        self.assertEqual(len(profile), 1)  # upsert por conceito_key
        self.assertEqual(profile[0]["nivel"], "avancado")

    def test_nivel_invalido_rejeitado(self):
        with self.assertRaises(ValueError):
            knowledge_store.set_profile(self.db, disciplina="TI", rotulo="Redes", nivel="expert")

    def test_origem_separa_declarado_de_resultado(self):
        knowledge_store.set_profile(self.db, disciplina="TI", rotulo="Redes", nivel="basico",
                                    origem="usuario")
        knowledge_store.set_profile(self.db, disciplina="TI", rotulo="SQL", nivel="intermediario",
                                    origem="resultado")
        by_key = {p["rotulo"]: p["origem"] for p in knowledge_store.list_profile(self.db)}
        self.assertEqual(by_key["Redes"], "usuario")
        self.assertEqual(by_key["SQL"], "resultado")

    def test_revisar_e_dimensao_separada(self):
        knowledge_store.set_profile(self.db, disciplina="TI", rotulo="Redes", nivel="avancado",
                                    revisar=True)
        entry = knowledge_store.list_profile(self.db)[0]
        self.assertEqual(entry["nivel"], "avancado")  # familiaridade preservada
        self.assertEqual(entry["revisar"], 1)  # necessidade de revisão separada

    def test_familiaridade_nao_e_progresso(self):
        # Definir familiaridade NÃO cria progresso de estudo.
        knowledge_store.set_profile(self.db, disciplina="TI", rotulo="Redes", nivel="avancado")
        from radar import study_store
        self.assertEqual(study_store.list_progresso(self.db), [])
        self.assertEqual(study_store.list_sessions(self.db), [])

    def test_sem_inferencia_por_formacao(self):
        # O perfil começa vazio; nada é inferido de formação/cargo/disciplina.
        self.assertEqual(knowledge_store.list_profile(self.db), [])

    def test_deletar_perfil(self):
        knowledge_store.set_profile(self.db, disciplina="TI", rotulo="Redes", nivel="basico")
        key = knowledge_store.list_profile(self.db)[0]["conceito_key"]
        self.assertTrue(knowledge_store.delete_profile(self.db, key))
        self.assertEqual(knowledge_store.list_profile(self.db), [])


if __name__ == "__main__":
    unittest.main()
