import sqlite3
import tempfile
import unittest
from pathlib import Path

from radar.document_store import migrate_document_schema
from radar.practice_store import get_question, list_questions
from radar.real_exam_questions import seed_real_questions


class TestRealExamQuestions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        migrate_document_schema(self.db_path)

    def tearDown(self):
        Path(self.db_path).unlink(missing_ok=True)

    def test_seed_and_idempotency(self):
        res1 = seed_real_questions(self.db_path)
        self.assertTrue(res1["total_inseridas"] >= 10)

        # Listing questions (with and without answer keys)
        questions = list_questions(self.db_path)
        self.assertTrue(len(questions) >= 10)
        self.assertIsNone(questions[0].get("gabarito"))
        self.assertIsNone(questions[0].get("comentario"))

        # Check bancas represented in tags
        all_tags = {tag for q in questions for tag in (q.get("tags") or [])}
        self.assertIn("banca:fgv", all_tags)
        self.assertIn("banca:cebraspe", all_tags)
        self.assertIn("banca:quadrix", all_tags)
        self.assertIn("banca:ibfc", all_tags)

        # Check types
        types = {q.get("tipo") for q in questions}
        self.assertIn("escolha_unica", types)
        self.assertIn("verdadeiro_falso", types)

        # Check comments via get_question / include_answer_key=True
        full_questions = list_questions(self.db_path, include_answer_key=True)
        for q in full_questions:
            self.assertTrue(len(q.get("comentario") or "") > 20)
            self.assertTrue(len(q.get("gabarito") or "") > 0)

        # Idempotency: second run shouldn't duplicate
        res2 = seed_real_questions(self.db_path)
        self.assertEqual(res2["total_inseridas"], 0)
        self.assertEqual(len(list_questions(self.db_path)), len(questions))


if __name__ == "__main__":
    unittest.main()
