"""Testes da persistência SQLite do Radar de Concursos (Task 2 — storage).

Cobrem, com sqlite3 stdlib e banco temporário:
- criação do banco/tabela e persistência dos registros do contrato v1;
- ``list_records`` retorna ``list[dict]`` JSON-compatível, com todos os campos
  na ordem do contrato, preservando ``None`` (desconhecido) e ``0`` (zero
  afirmado pela fonte);
- idempotência (mesma chave natural não duplica);
- atualização por upsert (mesma chave atualiza campos e ``verified_at``);
- rollback: lote inválido não grava parcial nem altera dados anteriores;
- validação: campos obrigatórios ausentes e tipos inválidos são rejeitados.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from radar import storage

# Campos exatos do contrato v1, na ordem da spec.
CONTRACT_FIELDS = [
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
]


def make_record(role="Professor de Educação Infantil", **overrides):
    """Constrói um registro válido do contrato v1, permitindo sobrescrita."""
    record = {
        "competition_id": "001/2026",
        "competition": "Concurso público da educação",
        "agency": "Prefeitura Municipal de Guajará-Mirim/RO (SEMED)",
        "role": role,
        "education": None,
        "immediate_vacancies": 69,
        "reserve_vacancies": None,
        "indigenous_vacancies": None,
        "registration_start": "2026-07-10",
        "registration_end": "2026-07-30",
        "registration_status": "encerradas conforme período divulgado",
        "exam_date": None,
        "exam_location": None,
        "work_location": None,
        "source_name": "Prefeitura Municipal de Guajará-Mirim/RO",
        "source_url": "https://guajaramirim.ro.gov.br/artigo/",
        "evidence_url": "https://guajaramirim.ro.gov.br/artigo/",
        "verified_at": "2026-10-09T12:00:00-04:00",
    }
    record.update(overrides)
    return record


class StorageTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "radar.db")

    def tearDown(self):
        self._tmp.cleanup()


class UpsertAndListTest(StorageTestCase):
    def test_upsert_creates_database_and_persists_contract_record(self):
        storage.upsert_records(self.db_path, [make_record()])
        rows = storage.list_records(self.db_path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(list(rows[0].keys()), CONTRACT_FIELDS)
        self.assertEqual(rows[0]["role"], "Professor de Educação Infantil")
        self.assertEqual(rows[0]["immediate_vacancies"], 69)
        self.assertIsNone(rows[0]["reserve_vacancies"])
        self.assertIsNone(rows[0]["education"])

    def test_list_records_returns_json_compatible_list(self):
        storage.upsert_records(self.db_path, [make_record()])
        rows = storage.list_records(self.db_path)
        # Deve ser serializável em JSON sem erro.
        json.dumps(rows)

    def test_list_records_empty_when_database_does_not_exist(self):
        missing = str(Path(self._tmp.name) / "nope.db")
        self.assertEqual(storage.list_records(missing), [])

    def test_preserves_explicit_zero_and_unknown_none(self):
        records = [
            make_record(role="Cargo Zero", immediate_vacancies=0, reserve_vacancies=None),
            make_record(role="Cargo Cheio", immediate_vacancies=69, reserve_vacancies=0),
        ]
        storage.upsert_records(self.db_path, records)
        rows = {r["role"]: r for r in storage.list_records(self.db_path)}
        self.assertEqual(rows["Cargo Zero"]["immediate_vacancies"], 0)
        self.assertIsNone(rows["Cargo Zero"]["reserve_vacancies"])
        self.assertEqual(rows["Cargo Cheio"]["immediate_vacancies"], 69)
        self.assertEqual(rows["Cargo Cheio"]["reserve_vacancies"], 0)

    def test_list_is_deterministically_ordered(self):
        records = [
            make_record(role="Professor de Braille"),
            make_record(role="Professor de Educação Infantil"),
            make_record(role="Professor Intérprete de Libras"),
        ]
        storage.upsert_records(self.db_path, records)
        roles = [r["role"] for r in storage.list_records(self.db_path)]
        self.assertEqual(
            roles,
            [
                "Professor de Braille",
                "Professor de Educação Infantil",
                "Professor Intérprete de Libras",
            ],
        )


class IdempotencyTest(StorageTestCase):
    def test_same_natural_key_does_not_duplicate(self):
        storage.upsert_records(self.db_path, [make_record()])
        storage.upsert_records(self.db_path, [make_record()])
        self.assertEqual(len(storage.list_records(self.db_path)), 1)

    def test_same_key_updates_fields_and_verified_at(self):
        storage.upsert_records(self.db_path, [make_record()])
        storage.upsert_records(
            self.db_path,
            [
                make_record(
                    immediate_vacancies=70,
                    verified_at="2026-10-10T09:00:00+00:00",
                )
            ],
        )
        rows = storage.list_records(self.db_path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["immediate_vacancies"], 70)
        self.assertEqual(rows[0]["verified_at"], "2026-10-10T09:00:00+00:00")


class RollbackTest(StorageTestCase):
    def test_invalid_batch_writes_nothing_and_preserves_previous_data(self):
        baseline = make_record(role="Original", immediate_vacancies=42)
        storage.upsert_records(self.db_path, [baseline])

        bad = [make_record(role="Novo"), make_record(role=None)]
        with self.assertRaises(ValueError):
            storage.upsert_records(self.db_path, bad)

        rows = storage.list_records(self.db_path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["role"], "Original")
        self.assertEqual(rows[0]["immediate_vacancies"], 42)


class ValidationTest(StorageTestCase):
    def test_rejects_missing_required_key_field(self):
        record = make_record()
        del record["role"]
        with self.assertRaises(ValueError):
            storage.upsert_records(self.db_path, [record])
        self.assertEqual(storage.list_records(self.db_path), [])

    def test_rejects_empty_required_key_field(self):
        with self.assertRaises(ValueError):
            storage.upsert_records(self.db_path, [make_record(role="   ")])
        self.assertEqual(storage.list_records(self.db_path), [])

    def test_rejects_non_int_vacancy_count(self):
        with self.assertRaises(ValueError):
            storage.upsert_records(
                self.db_path, [make_record(immediate_vacancies="69")]
            )
        self.assertEqual(storage.list_records(self.db_path), [])

    def test_rejects_non_text_contract_field(self):
        with self.assertRaises(ValueError):
            storage.upsert_records(self.db_path, [make_record(exam_location=123)])
        self.assertEqual(storage.list_records(self.db_path), [])

    def test_rejects_unknown_contract_field(self):
        record = make_record()
        record["extra_field"] = "nope"
        with self.assertRaises(ValueError):
            storage.upsert_records(self.db_path, [record])
        self.assertEqual(storage.list_records(self.db_path), [])

    def test_rejects_non_dict_record(self):
        with self.assertRaises(ValueError):
            storage.upsert_records(self.db_path, ["not-a-dict"])
        self.assertEqual(storage.list_records(self.db_path), [])

    def test_rejects_non_list_input(self):
        with self.assertRaises(ValueError):
            storage.upsert_records(self.db_path, make_record())

    def test_missing_optional_field_is_stored_as_none(self):
        record = make_record()
        del record["education"]
        storage.upsert_records(self.db_path, [record])
        rows = storage.list_records(self.db_path)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["education"])


if __name__ == "__main__":
    unittest.main()
