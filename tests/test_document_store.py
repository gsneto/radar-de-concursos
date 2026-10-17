"""Migração documental e identidades, sempre em bancos temporários."""

import sqlite3
import hashlib
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from radar.collector import collect
from radar.document_store import (
    SCHEMA_VERSION,
    get_competition_details,
    list_competition_identities,
    migrate_document_schema,
    record_analysis,
    record_version,
    register_document,
    sync_v1_identifiers,
)
from radar.storage import list_records, upsert_records


class MigrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "radar.sqlite3")

    def test_migration_preserves_v1_and_is_idempotent(self):
        html = (Path(__file__).parent / "fixtures" / "guajara-oficial.html").read_text(encoding="utf-8")
        upsert_records(self.db, collect(html, "2026-10-10T12:00:00+00:00"))
        before = list_records(self.db)
        migrate_document_schema(self.db)
        migrate_document_schema(self.db)
        self.assertEqual(list_records(self.db), before)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(conn.execute("SELECT count(*) FROM concursos_identidade").fetchone()[0], 0)

    def test_future_schema_is_rejected_unchanged(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("PRAGMA user_version=99")
        with self.assertRaises(ValueError):
            migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 99)
            self.assertEqual(conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [])

    def test_v2_database_is_upgraded_to_current_version(self):
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("DROP TABLE reconciliacoes_cargo")
            conn.execute("PRAGMA user_version=2")
            conn.commit()
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(versoes_documento)")}
            self.assertIn("comparison_sha256", columns)
            self.assertIsNotNone(conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='reconciliacoes_cargo'").fetchone())

    def test_empty_database_is_migrated(self):
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_v5_database_reads_without_tipo_documental_column(self):
        # Leitura de banco não migrado (v5) não pode quebrar por falta da coluna nova.
        from radar.document_store import (
            ensure_observation, register_document, get_competition_details)
        migrate_document_schema(self.db)
        obs = ensure_observation(self.db, "https://www.in.gov.br/web/dou/-/x-1", "x")
        register_document(self.db, {"observation_id": obs, "kind": "outro",
            "official_url": "https://www.in.gov.br/web/dou/-/x-1", "title": "Doc",
            "discovery_url": "https://www.in.gov.br/web/dou/-/x-1", "discovery_method": "automatico",
            "discovered_at": "2026-10-16T12:00:00+00:00"})
        with closing(sqlite3.connect(self.db)) as conn:
            contest_id = conn.execute("SELECT contest_id FROM observacoes_concurso").fetchone()[0]
            conn.execute("ALTER TABLE documentos DROP COLUMN tipo_documental")
            conn.execute("PRAGMA user_version=5")
            conn.commit()
        detail = get_competition_details(self.db, contest_id)  # não deve levantar
        self.assertIsNone(detail["documents"][0]["document_type"])


    def test_migration_refuses_incomplete_v2_without_silently_repairing_it(self):
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('DROP TABLE auditorias_cobertura')
            conn.commit()
        with self.assertRaisesRegex(ValueError, 'incompleto'):
            migrate_document_schema(self.db)

    def test_migration_refuses_v2_missing_required_column(self):
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('ALTER TABLE concursos_identidade RENAME COLUMN created_at TO creation_time')
            conn.commit()
        with self.assertRaisesRegex(ValueError, 'incompleto'):
            migrate_document_schema(self.db)

    def test_migration_refuses_v15_missing_identity_table(self):
        # Caminho rápido (base já em v15) também valida o esquema, não só as versões antigas.
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('DROP TABLE associacoes_documento')
            conn.commit()
        with self.assertRaisesRegex(ValueError, 'incompleto'):
            migrate_document_schema(self.db)

    def test_existing_artifact_must_match_hash_before_recording_version(self):
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("INSERT INTO concursos_identidade (id,created_at) VALUES ('c','2026-10-10T00:00:00+00:00')")
            conn.execute("INSERT INTO observacoes_concurso (id,contest_id,source_url,competition_id,observed_at) VALUES ('o','c','https://guajaramirim.ro.gov.br/a/','1/2026','2026-10-10T00:00:00+00:00')")
            conn.commit()
        url = 'https://guajaramirim.ro.gov.br/e.pdf'
        doc = register_document(self.db, dict(observation_id='o', kind='edital', official_url=url,
            title='Edital', discovery_url=url, discovery_method='manual', discovered_at='2026-10-10T00:00:00+00:00'))
        digest = hashlib.sha256(b'correct').hexdigest()
        folder = Path(self.db + '.documents')
        folder.mkdir()
        (folder / digest).write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'artefato'):
            record_version(self.db, doc, b'correct', dict(fetched_at='2026-10-10T00:01:00+00:00',
                fetched_url=url, content_type='application/pdf'))
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM versoes_documento').fetchone()[0], 0)

    def test_sync_preserves_identities_and_keeps_same_number_from_other_source_separate(self):
        html = (Path(__file__).parent / "fixtures" / "guajara-oficial.html").read_text(encoding="utf-8")
        records = collect(html, "2026-10-10T12:00:00+00:00")
        second = dict(records[0], source_url="https://exemplo.gov.br/artigo/")
        upsert_records(self.db, records + [second])
        before = list_records(self.db)
        migrate_document_schema(self.db)
        self.assertEqual(list_competition_identities(self.db), [])
        sync_v1_identifiers(self.db)
        identities = list_competition_identities(self.db)
        self.assertEqual(len(identities), 2)
        self.assertEqual(len({row["id"] for row in identities}), 2)
        self.assertEqual({row["observations"][0]["competition_id"] for row in identities}, {"001/2026"})
        self.assertEqual(sorted(len(get_competition_details(self.db, row["id"])["roles"]) for row in identities), [1, 4])
        sync_v1_identifiers(self.db)
        self.assertEqual(list_competition_identities(self.db), identities)
        self.assertEqual(list_records(self.db), before)

    def test_document_url_and_content_hash_have_stable_separate_ids(self):
        html = (Path(__file__).parent / "fixtures" / "guajara-oficial.html").read_text(encoding="utf-8")
        upsert_records(self.db, collect(html, "2026-10-10T12:00:00+00:00"))
        migrate_document_schema(self.db)
        sync_v1_identifiers(self.db)
        contest = list_competition_identities(self.db)[0]
        with closing(sqlite3.connect(self.db)) as conn:
            observation_id = conn.execute("SELECT id FROM observacoes_concurso").fetchone()[0]
        candidate = {
            "observation_id": observation_id, "kind": "edital",
            "official_url": "https://guajaramirim.ro.gov.br/edital.pdf", "title": "Edital",
            "discovery_url": contest["observations"][0]["source_url"],
            "discovery_method": "manual", "discovered_at": "2026-10-10T12:00:00+00:00",
        }
        document_id = register_document(self.db, candidate)
        self.assertEqual(register_document(self.db, candidate), document_id)
        another = dict(candidate, official_url="https://guajaramirim.ro.gov.br/outro.pdf")
        self.assertNotEqual(register_document(self.db, another), document_id)
        metadata = {"fetched_at": "2026-10-10T12:01:00+00:00", "fetched_url": candidate["official_url"], "content_type": "application/pdf"}
        first = record_version(self.db, document_id, b"first-pdf", metadata)
        self.assertEqual(record_version(self.db, document_id, b"first-pdf", metadata), first)
        self.assertNotEqual(record_version(self.db, document_id, b"second-pdf", metadata), first)
        details = get_competition_details(self.db, contest["id"])
        self.assertEqual(len(details["documents"]), 2)
        self.assertEqual(len(next(d for d in details["documents"] if d["id"] == document_id)["versions"]), 2)
        self.assertNotIn("local_path", str(details))

    def test_inexact_evidence_rolls_back_analysis(self):
        html = (Path(__file__).parent / "fixtures" / "guajara-oficial.html").read_text(encoding="utf-8")
        upsert_records(self.db, collect(html, "2026-10-10T12:00:00+00:00"))
        migrate_document_schema(self.db)
        sync_v1_identifiers(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            observation_id, contest_id = conn.execute("SELECT id,contest_id FROM observacoes_concurso").fetchone()
        url = "https://guajaramirim.ro.gov.br/edital.pdf"
        doc_id = register_document(self.db, dict(observation_id=observation_id, kind="edital", official_url=url,
                                                  title="Edital", discovery_url=url, discovery_method="manual",
                                                  discovered_at="2026-10-10T12:00:00+00:00"))
        version_id = record_version(self.db, doc_id, b"pdf", dict(fetched_at="2026-10-10T12:01:00+00:00",
                                                                   fetched_url=url, content_type="application/pdf"))
        blocks = [dict(text="10 vagas imediatas", page_number=1, locator="p. 1", start_offset=0, end_offset=18)]
        proposals = [dict(contest_id=contest_id, role_id=None, field_name="immediate_vacancies", value_json="10",
                          value_type="integer", extraction_method="regex", evidence=dict(block_index=0,
                          quote="11 vagas", start_offset=0, end_offset=8))]
        with self.assertRaises(ValueError):
            record_analysis(self.db, version_id, blocks, proposals)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM blocos_documento").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT count(*) FROM propostas_campo").fetchone()[0], 0)

    def test_valid_proposal_is_readable_but_not_current_without_review(self):
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("INSERT INTO concursos_identidade (id,created_at) VALUES (?,?)", ("contest", "2026-10-10T00:00:00+00:00"))
            conn.execute("INSERT INTO observacoes_concurso (id,contest_id,source_url,competition_id,observed_at) VALUES (?,?,?,?,?)", ("obs", "contest", "https://guajaramirim.ro.gov.br/a/", "1/2026", "2026-10-10T00:00:00+00:00"))
            conn.commit()
        candidate = dict(observation_id="obs", kind="edital", official_url="https://guajaramirim.ro.gov.br/e.pdf", title="Edital", discovery_url="https://guajaramirim.ro.gov.br/a/", discovery_method="manual", discovered_at="2026-10-10T00:00:00+00:00")
        doc = register_document(self.db, candidate)
        version = record_version(self.db, doc, b"text", dict(fetched_at="2026-10-10T00:00:00+00:00", fetched_url=candidate["official_url"], content_type="application/pdf"))
        record_analysis(self.db, version, [dict(text="10 vagas", page_number=1, locator="p.1", start_offset=0, end_offset=8)],
                        [dict(contest_id="contest", role_id=None, field_name="immediate_vacancies", value_json="10", value_type="integer", extraction_method="regex", evidence=dict(block_index=0, quote="10 vagas", start_offset=0, end_offset=8))])
        details = get_competition_details(self.db, "contest")
        self.assertEqual(details["proposals"][0]["value"], 10)
        self.assertEqual(details["proposals"][0]["evidence"]["quote"], "10 vagas")
        self.assertEqual(details["current_values"], [])

    def test_role_scope_must_belong_to_documents_observation(self):
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("INSERT INTO concursos_identidade (id,created_at) VALUES ('c','2026-10-10T00:00:00+00:00')")
            for obs in ('a', 'b'):
                conn.execute('INSERT INTO observacoes_concurso (id,contest_id,source_url,competition_id,observed_at) VALUES (?,?,?,?,?)',
                    (obs, 'c', 'https://guajaramirim.ro.gov.br/' + obs,
                     '1/2026', '2026-10-10T00:00:00+00:00'))
            conn.execute("INSERT INTO cargos_identidade (id,contest_id,name,specialty,created_at) VALUES ('r','c','Professor',NULL,'2026-10-10T00:00:00+00:00')")
            conn.execute("INSERT INTO observacoes_cargo VALUES ('or','r','b','Professor','2026-10-10T00:00:00+00:00')")
            conn.commit()
        candidate = dict(observation_id='a', role_id='r', kind='edital',
            official_url='https://guajaramirim.ro.gov.br/e.pdf', title='Edital',
            discovery_url='https://guajaramirim.ro.gov.br/a', discovery_method='manual',
            discovered_at='2026-10-10T00:00:00+00:00')
        with self.assertRaisesRegex(ValueError, 'cargo'):
            register_document(self.db, candidate)
        candidate.pop('role_id')
        doc = register_document(self.db, candidate)
        version = record_version(self.db, doc, b'pdf', dict(
            fetched_at='2026-10-10T00:00:00+00:00', fetched_url=candidate['official_url'],
            content_type='application/pdf'))
        with self.assertRaisesRegex(ValueError, 'cargo'):
            record_analysis(self.db, version, [dict(text='1 vaga imediata',
                start_offset=0, end_offset=15, page_number=1)], [dict(
                contest_id='c', role_id='r', field_name='immediate_vacancies',
                value_json='1', value_type='integer', extraction_method='manual',
                evidence=dict(block_index=0, quote='1 vaga imediata', start_offset=0, end_offset=15))])


class EnsureRoleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "radar.sqlite3")
        migrate_document_schema(self.db)
        from radar.document_store import ensure_observation
        self.obs = ensure_observation(self.db, "https://guajaramirim.ro.gov.br/a/", "DOU-S3")
        with closing(sqlite3.connect(self.db)) as conn:
            self.contest = conn.execute(
                "SELECT contest_id FROM observacoes_concurso WHERE id=?", (self.obs,)).fetchone()[0]

    def test_ensure_role_is_idempotent(self):
        from radar.document_store import ensure_role
        first = ensure_role(self.db, self.contest, self.obs, "Professor de Educação Infantil")
        second = ensure_role(self.db, self.contest, self.obs, "Professor de Educação Infantil")
        self.assertEqual(first, second)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM cargos_identidade").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM observacoes_cargo").fetchone()[0], 1)

    def test_ensure_role_rejects_unknown_contest_and_observation(self):
        from radar.document_store import ensure_role
        with self.assertRaises(ValueError):
            ensure_role(self.db, "no-contest", self.obs, "Cargo")
        with self.assertRaises(ValueError):
            ensure_role(self.db, self.contest, "no-obs", "Cargo")

    def test_ensure_role_requires_name(self):
        from radar.document_store import ensure_role
        with self.assertRaises(ValueError):
            ensure_role(self.db, self.contest, self.obs, "  ")

    def test_ensure_role_by_code_is_idempotent(self):
        from radar.document_store import ensure_role
        first = ensure_role(self.db, self.contest, self.obs, "Analista de Informática", code="404")
        second = ensure_role(self.db, self.contest, self.obs, "Analista de Informática", code="404")
        self.assertEqual(first, second)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT code FROM cargos_identidade WHERE id=?",
                                          (first,)).fetchone()[0], "404")

    def test_ensure_role_code_conflict_raises(self):
        from radar.document_store import ensure_role
        ensure_role(self.db, self.contest, self.obs, "Analista de Informática", code="404")
        with self.assertRaisesRegex(ValueError, "código"):
            ensure_role(self.db, self.contest, self.obs, "Merendeira Escolar", code="404")

    def test_ensure_role_code_tolerates_benign_name_variation(self):
        # Mesmo código com sufixo de localidade (variação benigna) não é conflito.
        from radar.document_store import ensure_role
        first = ensure_role(self.db, self.contest, self.obs, "Analista de Informática", code="404")
        second = ensure_role(self.db, self.contest, self.obs, "Analista de Informática - Curitiba", code="404")
        self.assertEqual(first, second)

    def test_ensure_role_adopts_homonymous_role_without_code(self):
        from radar.document_store import ensure_role
        without = ensure_role(self.db, self.contest, self.obs, "Analista de Informática")
        with_code = ensure_role(self.db, self.contest, self.obs, "Analista de Informática", code="404")
        self.assertEqual(without, with_code)  # adota o registro existente, não duplica
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM cargos_identidade").fetchone()[0], 1)

    def test_ensure_role_code_is_contextual_to_contest(self):
        from radar.document_store import ensure_observation, ensure_role
        other_obs = ensure_observation(self.db, "https://www.quadrix.org.br/informacoes/9/", "quadrix-9")
        with closing(sqlite3.connect(self.db)) as conn:
            other = conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                 (other_obs,)).fetchone()[0]
        a = ensure_role(self.db, self.contest, self.obs, "Cargo", code="404")
        b = ensure_role(self.db, other, other_obs, "Cargo", code="404")
        self.assertNotEqual(a, b)  # mesmo código, concursos diferentes

    def test_v7_adds_role_code_column(self):
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
            cols = {row[1] for row in conn.execute("PRAGMA table_info(cargos_identidade)")}
        self.assertIn("code", cols)


if __name__ == "__main__":
    unittest.main()
