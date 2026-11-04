"""Testes da Fase 47: campos de quadro/Quadrix em record_analysis e menor distância entre municípios de prova."""

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from radar import geography, preferences, priority
from radar.document_store import (
    connect_documents,
    ensure_observation,
    migrate_document_schema,
    record_analysis,
    record_version,
    register_document,
)


def _now():
    return datetime.now(timezone.utc).isoformat()


class RecordAnalysisQuadrixAndWideFieldsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "radar.sqlite3")
        migrate_document_schema(self.db)

    def test_record_analysis_aceita_vaga_municipio_e_colunas_unificadas(self):
        obs = ensure_observation(self.db, "https://www.quadrix.org.br/todos-os-concursos", "quadrix-3055")
        conn = connect_documents(self.db)
        try:
            contest_id = conn.execute(
                "SELECT contest_id FROM observacoes_concurso WHERE id=?", (obs,)
            ).fetchone()[0]
        finally:
            conn.close()

        did = register_document(
            self.db,
            dict(
                observation_id=obs,
                kind="edital",
                official_url="https://anexos-r2.selecao.net.br/uploads/3055/edital.pdf",
                title="Edital 1",
                discovery_url="https://www.quadrix.org.br/todos-os-concursos",
                discovery_method="automatico",
                discovered_at=_now(),
            ),
        )
        text = "200 Fiscal Belo Horizonte/MG 5 1 2 0+CR"
        blocks = [{"page_number": 1, "locator": "p1", "start_offset": 0, "end_offset": len(text), "text": text}]
        vid = record_version(
            self.db,
            did,
            b"%PDF-1.4 test",
            dict(
                fetched_at=_now(),
                fetched_url="https://anexos-r2.selecao.net.br/uploads/3055/edital.pdf",
                content_type="application/pdf",
            ),
        )
        proposals = [
            dict(
                contest_id=contest_id,
                role_id=None,
                field_name="vaga_municipio",
                value_json=json.dumps("Belo Horizonte/MG"),
                value_type="string",
                extraction_method="quadrix-quadro",
                ambiguity_reason="escopo de cargo: 200 Fiscal",
                evidence=dict(block_index=0, quote="Belo Horizonte/MG", start_offset=11, end_offset=28),
            ),
            dict(
                contest_id=contest_id,
                role_id=None,
                field_name="unified_ppiq_vacancies",
                value_json=json.dumps(1),
                value_type="integer",
                extraction_method="quadro-colunas-pdf",
                ambiguity_reason="escopo de cargo: 200 Fiscal",
                evidence=dict(block_index=0, quote=text, start_offset=0, end_offset=len(text)),
            ),
            dict(
                contest_id=contest_id,
                role_id=None,
                field_name="unified_pi_pq_vacancies",
                value_json=json.dumps(2),
                value_type="integer",
                extraction_method="quadro-colunas-pdf",
                ambiguity_reason="escopo de cargo: 200 Fiscal",
                evidence=dict(block_index=0, quote=text, start_offset=0, end_offset=len(text)),
            ),
            dict(
                contest_id=contest_id,
                role_id=None,
                field_name="indigenous_reserve_notation",
                value_json=json.dumps("0+CR"),
                value_type="string",
                extraction_method="quadro-colunas-pdf",
                ambiguity_reason="escopo de cargo: 200 Fiscal",
                evidence=dict(block_index=0, quote="0+CR", start_offset=35, end_offset=39),
            ),
        ]
        record_analysis(self.db, vid, blocks, proposals, partial=False)

        conn = connect_documents(self.db)
        try:
            saved = dict(
                conn.execute(
                    "SELECT field_name, value_json FROM propostas_campo WHERE contest_id=?",
                    (contest_id,),
                ).fetchall()
            )
        finally:
            conn.close()

        self.assertEqual(json.loads(saved["vaga_municipio"]), "Belo Horizonte/MG")
        self.assertEqual(json.loads(saved["unified_ppiq_vacancies"]), 1)
        self.assertEqual(json.loads(saved["unified_pi_pq_vacancies"]), 2)
        self.assertEqual(json.loads(saved["indigenous_reserve_notation"]), "0+CR")


class ClosestExamMunicipioDistanceTest(unittest.TestCase):
    def test_escolhe_municipio_com_coordenada_e_menor_distancia(self):
        ref = {"municipio": "Paulo Afonso", "uf": "BA"}
        # Colatina e Guarapari não têm coordenada no seed; Vitória tem.
        out = geography.closest_distance_from_reference(
            ["Colatina", "Guarapari", "Vitória"], "ES", reference=ref
        )
        self.assertTrue(out["known"])
        self.assertIsNotNone(out["distance_km"])
        self.assertEqual(out.get("municipio"), "Vitória")


if __name__ == "__main__":
    unittest.main()
