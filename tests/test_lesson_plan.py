import unittest

from radar.lesson_plan import get_banca_profiles, get_lesson, list_lessons


class TestLessonPlan(unittest.TestCase):
    def test_banca_profiles(self):
        profiles = get_banca_profiles()
        self.assertIn("fgv", profiles)
        self.assertIn("cebraspe", profiles)
        self.assertIn("quadrix", profiles)
        self.assertIn("ibfc", profiles)

        fgv = profiles["fgv"]
        self.assertEqual(fgv["nome"], "Fundação Getulio Vargas (FGV)")
        self.assertTrue(len(fgv["caracteristicas"]) > 0)
        self.assertTrue(len(fgv["dicas_ti"]) > 0)

        cebraspe = profiles["cebraspe"]
        self.assertIn("Certo/Errado", cebraspe["estilo_predominante"])
        self.assertIn("penalidade", cebraspe["regras_pontuacao"].lower())

    def test_list_lessons(self):
        lessons = list_lessons()
        self.assertTrue(len(lessons) >= 6)
        
        # Check disciplines
        disciplines = {l["disciplina"] for l in lessons}
        self.assertIn("Banco de Dados", disciplines)
        self.assertIn("Engenharia de Software", disciplines)
        self.assertIn("Língua Portuguesa", disciplines)

        # Filter by discipline
        bd_lessons = list_lessons(disciplina="Banco de Dados")
        self.assertTrue(len(bd_lessons) >= 2)
        for l in bd_lessons:
            self.assertEqual(l["disciplina"], "Banco de Dados")

    def test_get_lesson_detail(self):
        lesson = get_lesson("bd-01")
        self.assertIsNotNone(lesson)
        self.assertEqual(lesson["id"], "bd-01")
        self.assertIn("Modelagem", lesson["titulo"])
        self.assertTrue(len(lesson["teoria_resumida"]) > 50)
        self.assertIn("fgv", lesson["radiografia_bancas"])
        self.assertIn("cebraspe", lesson["radiografia_bancas"])
        self.assertTrue(len(lesson["pontos_criticos"]) > 0)

        # Non-existent
        none_lesson = get_lesson("non-existent")
        self.assertIsNone(none_lesson)


if __name__ == "__main__":
    unittest.main()
