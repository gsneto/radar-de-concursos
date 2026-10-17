"""Pacotes portáveis de questões e flashcards (Fase 24)."""

import io
import json
import struct
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path

from radar import packages, practice_store
from radar.document_store import migrate_document_schema


def png_bytes(width=20, height=10):
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunk = b"IHDR" + ihdr
    return (b"\x89PNG\r\n\x1a\n" + struct.pack(">I", len(ihdr)) + chunk
            + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF))


def make_zip(members, *, compress=zipfile.ZIP_DEFLATED):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compress) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def manifest(**overrides):
    data = {"formato": "radar-pacote", "versao_formato": 1, "tipo": "misto",
            "nome": "Pacote de teste", "licenca": "propria", "procedencia": "teste"}
    data.update(overrides)
    return data


class PackageBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = str(self.root / "origem.sqlite3")
        self.dest = str(self.root / "destino.sqlite3")
        migrate_document_schema(self.db)
        migrate_document_schema(self.dest)

    def _seed(self):
        q = practice_store.create_question(
            self.db, enunciado="Questão exportável número 1?", alternativas=["A1", "A2"],
            gabarito="A", disciplina="Português", topico="Gramática")
        card = practice_store.create_flashcard(self.db, frente="Frente?", verso="Verso")
        return q, card


class ExportTest(PackageBase):
    def test_exporta_estrutura_do_pacote(self):
        self._seed()
        blob = packages.export_package(self.db, nome="Meu pacote", licenca="propria")
        parsed = packages.read_package(blob)
        self.assertEqual(parsed["manifest"]["formato"], "radar-pacote")
        self.assertEqual(parsed["manifest"]["nome"], "Meu pacote")
        self.assertEqual(len(parsed["registros"]["questoes"]), 1)
        self.assertEqual(len(parsed["registros"]["flashcards"]), 1)
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            names = archive.namelist()
        self.assertIn("manifest.json", names)
        self.assertIn("registros.json", names)

    def test_licenca_invalida_recusada(self):
        with self.assertRaises(packages.PackageError):
            packages.export_package(self.db, licenca="gratis")

    def test_tipo_invalido_recusado(self):
        with self.assertRaises(packages.PackageError):
            packages.export_package(self.db, tipo="garbage")

    def test_exporta_midia_do_flashcard(self):
        card = practice_store.create_flashcard(self.db, frente="Com imagem", verso="V")
        practice_store.attach_flashcard_image(self.db, card["id"], png_bytes())
        blob = packages.export_package(self.db)
        parsed = packages.read_package(blob)
        self.assertEqual(len(parsed["midias"]), 1)
        self.assertEqual(parsed["manifest"]["contagens"]["midias"], 1)


class ReadTest(PackageBase):
    def test_zip_slip_recusado(self):
        blob = make_zip({"../evil.txt": b"x", "manifest.json": b"{}",
                         "registros.json": b"{}"})
        with self.assertRaises(packages.PackageError):
            packages.read_package(blob)

    def test_caminho_absoluto_recusado(self):
        blob = make_zip({"/etc/passwd": b"x", "manifest.json": b"{}",
                         "registros.json": b"{}"})
        with self.assertRaises(packages.PackageError):
            packages.read_package(blob)

    def test_sem_manifesto_recusado(self):
        blob = make_zip({"registros.json": b"{}"})
        with self.assertRaises(packages.PackageError):
            packages.read_package(blob)

    def test_zip_bomb_recusado(self):
        bomb = b"\x00" * (2 * 1024 * 1024)
        blob = make_zip({"manifest.json": b"{}", "registros.json": b"{}", "midia/big.png": bomb})
        with self.assertRaises(packages.PackageError):
            packages.read_package(blob)

    def test_midia_invalida_recusada(self):
        blob = make_zip({"manifest.json": json.dumps(manifest()).encode(),
                         "registros.json": b"{}",
                         "midia/x.png": b"<svg xmlns='http://www.w3.org/2000/svg'/>"})
        with self.assertRaises(packages.PackageError):
            packages.read_package(blob)

    def test_manifesto_com_formato_errado(self):
        with self.assertRaises(packages.PackageError):
            packages.validate_manifest({"formato": "outro", "versao_formato": 1, "tipo": "misto"})

    def test_versao_futura_recusada(self):
        with self.assertRaises(packages.PackageError):
            packages.validate_manifest(manifest(versao_formato=99))

    def test_licenca_desconhecida_nao_e_verificada(self):
        info = packages.validate_manifest(manifest(licenca="desconhecida"))
        self.assertFalse(info["licenca_verificada"])
        self.assertIn("não deve ser redistribuído", info["aviso"])


class MalformedTest(PackageBase):
    def _pkg(self, registros):
        return make_zip({"manifest.json": json.dumps(manifest()).encode(),
                         "registros.json": json.dumps(registros).encode()})

    def test_questao_sem_id(self):
        with self.assertRaises(packages.PackageError):
            packages.preview_package(self.dest, self._pkg({"questoes": [{"enunciado": "x"}]}))

    def test_registro_que_nao_e_objeto(self):
        with self.assertRaises(packages.PackageError):
            packages.preview_package(self.dest, self._pkg({"questoes": ["x"]}))

    def test_versao_nao_numerica(self):
        blob = self._pkg({"questoes": [{"id": "q1", "enunciado": "Pergunta valida?",
                                        "gabarito": "A", "versao": "x"}]})
        with self.assertRaises(packages.PackageError):
            packages.preview_package(self.dest, blob)

    def test_licenca_com_tipo_errado_nao_quebra(self):
        info = packages.validate_manifest(manifest(licenca=123))
        self.assertEqual(info["licenca"], "desconhecida")
        self.assertFalse(info["licenca_verificada"])

    def test_import_tambem_valida(self):
        with self.assertRaises(packages.PackageError):
            packages.import_package(self.dest, self._pkg({"questoes": [{}]}))

    def test_limite_de_membros(self):
        members = {"manifest.json": json.dumps(manifest()).encode(),
                   "registros.json": b"{}"}
        for i in range(6):
            members[f"x{i}.txt"] = b"x"
        with self.assertRaises(packages.PackageError):
            packages.read_package(make_zip(members), max_members=5)

    def test_limite_por_membro(self):
        blob = make_zip({"manifest.json": json.dumps(manifest()).encode(),
                         "registros.json": b"{}", "midia/a.png": b"\x89PNG" + b"0" * 100})
        with self.assertRaises(packages.PackageError):
            packages.read_package(blob, max_member_bytes=20)


class ImportTest(PackageBase):
    def test_previa_nao_grava_e_aponta_conflito(self):
        self._seed()
        blob = packages.export_package(self.db)
        preview = packages.preview_package(self.dest, blob)
        self.assertTrue(preview["pode_importar"])
        self.assertEqual(preview["contagens"]["questoes"], 1)
        self.assertEqual(preview["conflitos"], [])
        self.assertEqual(practice_store.list_questions(self.dest), [])

    def test_previa_aponta_item_ja_existente(self):
        self._seed()
        blob = packages.export_package(self.db)
        packages.import_package(self.dest, blob)
        preview = packages.preview_package(self.dest, blob)
        self.assertEqual(len(preview["conflitos"]), 2)

    def test_importacao_roundtrip(self):
        q, card = self._seed()
        blob = packages.export_package(self.db)
        report = packages.import_package(self.dest, blob)
        self.assertTrue(report["ok"])
        self.assertEqual(report["criados"], {"questoes": 1, "flashcards": 1, "midias": 0})
        imported = practice_store.list_questions(self.dest)
        self.assertEqual(imported[0]["enunciado"], q["enunciado"])
        self.assertEqual(practice_store.list_flashcards(self.dest)[0]["frente"], card["frente"])

    def test_reimportar_nao_duplica(self):
        self._seed()
        blob = packages.export_package(self.db)
        packages.import_package(self.dest, blob)
        again = packages.import_package(self.dest, blob)
        self.assertEqual(again["criados"]["questoes"], 0)
        self.assertEqual(again["criados"]["flashcards"], 0)
        self.assertEqual(again["ignorados"], 2)
        self.assertEqual(len(practice_store.list_questions(self.dest)), 1)

    def test_dry_run_com_midia_nao_reporta_conflito_falso(self):
        card = practice_store.create_flashcard(self.db, frente="Com imagem", verso="V")
        practice_store.attach_flashcard_image(self.db, card["id"], png_bytes())
        blob = packages.export_package(self.db)
        report = packages.import_package(self.dest, blob, dry_run=True)
        self.assertEqual(report["criados"]["midias"], 1)
        self.assertEqual([c for c in report["conflitos"] if c["tipo"] == "midia"], [])
        self.assertEqual(practice_store.list_flashcards(self.dest), [])
        self.assertEqual(packages.list_packages(self.dest), [])
        import sqlite3
        conn = sqlite3.connect(self.dest)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM pratica_midias").fetchone()[0], 0)
        finally:
            conn.close()

    def test_flashcard_com_disciplina_e_portavel(self):
        import sqlite3
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO estudo_disciplinas(id,nome,created_at) VALUES('d1','Português',"
                     "'2026-10-17T00:00:00+00:00')")
        conn.execute("INSERT INTO estudo_topicos(id,disciplina_id,parent_id,nome,created_at) "
                     "VALUES('t1','d1',NULL,'Gramática','2026-10-17T00:00:00+00:00')")
        conn.commit()
        conn.close()
        practice_store.create_flashcard(self.db, frente="Vinculado?", verso="V",
                                        disciplina_id="d1", topico_id="t1")
        blob = packages.export_package(self.db)
        report = packages.import_package(self.dest, blob)
        self.assertEqual(report["criados"]["flashcards"], 1)
        card = practice_store.list_flashcards(self.dest)[0]
        self.assertEqual(card["disciplina_id"], "d1")

    def test_dry_run_nao_grava(self):
        self._seed()
        blob = packages.export_package(self.db)
        report = packages.import_package(self.dest, blob, dry_run=True)
        self.assertTrue(report["dry_run"])
        self.assertEqual(report["criados"]["questoes"], 1)
        self.assertEqual(practice_store.list_questions(self.dest), [])

    def test_importa_midia_e_vincula(self):
        card = practice_store.create_flashcard(self.db, frente="Com imagem", verso="V")
        practice_store.attach_flashcard_image(self.db, card["id"], png_bytes())
        blob = packages.export_package(self.db)
        report = packages.import_package(self.dest, blob)
        self.assertEqual(report["criados"]["midias"], 1)
        imported = practice_store.list_flashcards(self.dest)[0]
        imagem = practice_store.flashcard_image(self.dest, imported["id"])
        self.assertIsNotNone(imagem)
        self.assertEqual(imagem["mime"], "image/png")

    def test_historico_registra_procedencia(self):
        self._seed()
        blob = packages.export_package(self.db, nome="Histórico", procedencia="banco próprio")
        packages.import_package(self.dest, blob)
        history = packages.list_packages(self.dest)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["questoes"], 1)
        self.assertEqual(history[0]["flashcards"], 1)
        self.assertEqual(history[0]["tipo"], "misto")
        self.assertEqual(history[0]["nome"], "Histórico")
        self.assertEqual(history[0]["procedencia"], "banco próprio")
        self.assertEqual(history[0]["counts"]["questoes"], 1)

    def test_conteudo_local_prevalece(self):
        self._seed()
        blob = packages.export_package(self.db)
        packages.import_package(self.dest, blob)
        local = practice_store.list_questions(self.dest)[0]
        practice_store.update_question(self.dest, local["id"],
                                       enunciado="Texto local ajustado?")
        packages.import_package(self.dest, blob)
        current = practice_store.list_questions(self.dest)[0]
        self.assertEqual(current["enunciado"], "Texto local ajustado?")

if __name__ == "__main__":
    unittest.main()
