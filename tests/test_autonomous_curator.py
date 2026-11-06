"""Testes unitários do motor de Curadoria Autônoma (radar.autonomous_curator)."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from radar import autonomous_curator, portfolio, review, role_identity
from radar.document_store import migrate_document_schema

NOW = "2026-10-17T12:00:00+00:00"
TODAY = "2026-10-18"
_SEQ = [0]


def make_test_db():
    tmp = tempfile.TemporaryDirectory()
    db = str(Path(tmp.name) / "radar.sqlite3")
    migrate_document_schema(db)
    with closing(sqlite3.connect(db)) as conn, conn:
        for cid in ("c1", "c2"):
            conn.execute("INSERT INTO concursos_identidade (id,created_at,estado_identidade) "
                         "VALUES (?,?,'certame')", (cid, NOW))
            conn.execute("INSERT INTO observacoes_concurso "
                         "(id,contest_id,source_url,competition_id,observed_at) "
                         "VALUES (?,?,?,?,?)",
                         (f"o-{cid}", cid, f"https://conhecimento.fgv.br/concursos/{cid}", cid, NOW))
    return tmp, db


def add_doc(db, contest_id, *, tipo="edital_abertura", title=None,
            published_at="2026-09-01", text=None, url=None):
    document_id = f"doc-{contest_id}-{tipo}-{abs(hash(title or tipo)) % 1000}"
    version_id = f"ver-{document_id}"
    url = url or f"https://conhecimento.fgv.br/sites/default/files/{document_id}.pdf"
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("""INSERT INTO documentos
            (id,contest_id,observation_id,kind,official_url,title,discovered_at,
             discovery_url,discovery_method,issuer,published_at,tipo_documental)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (document_id, contest_id, f"o-{contest_id}",
             "edital" if tipo != "retificacao" else "retificacao", url,
             title or f"Documento {tipo}", NOW,
             f"https://conhecimento.fgv.br/concursos/{contest_id}", "automatico",
             "Fundação Getulio Vargas (FGV Conhecimento)", published_at, tipo))
        if text is not None:
            conn.execute("""INSERT INTO versoes_documento
                (id,document_id,sha256,fetched_at,fetched_url,content_type,byte_size,
                 local_path,extraction_state)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (version_id, document_id, "0" * 64, NOW, url, "application/pdf",
                 len(text), f"documents/{version_id}", "parcial"))
            conn.execute("""INSERT INTO blocos_documento
                (id,version_id,page_number,locator,start_offset,end_offset,text)
                VALUES (?,?,?,?,?,?,?)""",
                (f"blk-{version_id}", version_id, 3, "página 3", 0, len(text), text))
    return document_id, version_id


def add_prop(db, contest_id, *, version_id, field, value, quote, role_id=None,
             reason=None, page=3, method="regex", block_id=None):
    bid = block_id or f"blk-{version_id}"
    with closing(sqlite3.connect(db)) as conn, conn:
        text_row = conn.execute("SELECT text FROM blocos_documento WHERE id=?", (bid,)).fetchone()
        text = text_row[0] if text_row else quote
        start = text.find(quote) if text else 0
        if start < 0:
            start = 0
        _SEQ[0] += 1
        pid = f"p-{contest_id}-{field}-{_SEQ[0]}"
        eid = f"e-{pid}"
        conn.execute("""INSERT INTO evidencias
            (id,version_id,block_id,quote,page_number,locator,start_offset,end_offset,
             captured_at) VALUES (?,?,?,?,?,?,?,?,?)""",
            (eid, version_id, bid, quote, page, "página 3", start,
             start + len(quote), NOW))
        conn.execute("""INSERT INTO propostas_campo
            (id,contest_id,role_id,field_name,value_json,value_type,evidence_id,
             extraction_method,ambiguity_reason,extracted_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (pid, contest_id, role_id, field, json.dumps(value),
             "integer" if isinstance(value, int) else "string", eid, method,
             reason, NOW))
    return pid


class TestAutonomousCurator(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_test_db()
        self.addCleanup(self.tmp.cleanup)

    def test_curate_non_roles(self):
        text = "Anexo II - Conteúdo Programático para o cargo de Analista."
        _, vid = add_doc(self.db, "c1", tipo="edital_abertura", text=text)
        add_prop(self.db, "c1", version_id=vid, field="conteudo_secao",
                 value="Língua Portuguesa", quote="Conteúdo Programático",
                 reason="cargo do documento não reconciliado: conteúdo programático candidato (conteudo_secao)")
        add_prop(self.db, "c1", version_id=vid, field="exam_location",
                 value="Salvador", quote="Salvador",
                 reason="cargo do documento não reconciliado: local de prova candidato")

        res = autonomous_curator.curate_non_roles(self.db)
        self.assertGreaterEqual(res["rejeitados"], 2)

        with closing(sqlite3.connect(self.db)) as conn:
            rows = conn.execute("SELECT label, state, nature, reviewer FROM reconciliacoes_cargo").fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0][1], "rejeitada")
            self.assertEqual(rows[0][3], "agente_autonomo")

    def test_reconcile_canonical_roles(self):
        text = "Cargo: Analista de TI. Requisitos: nível superior."
        _, vid = add_doc(self.db, "c1", tipo="edital_abertura", text=text)

        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO cargos_identidade (id,contest_id,name,created_at) "
                         "VALUES ('role-1','c1','Analista de TI',?)", (NOW,))

        add_prop(self.db, "c1", version_id=vid, field="education",
                 value="nível superior", quote="nível superior",
                 reason="cargo do documento não reconciliado: Analista de TI")

        res = autonomous_curator.reconcile_canonical_roles(self.db)
        self.assertEqual(res["reconciliados"], 1)

        with closing(sqlite3.connect(self.db)) as conn:
            rec = conn.execute("SELECT label, state, role_id, reviewer FROM reconciliacoes_cargo WHERE label='Analista de TI'").fetchone()
            self.assertIsNotNone(rec)
            self.assertEqual(rec[1], "confirmada")
            self.assertEqual(rec[2], "role-1")
            self.assertEqual(rec[3], "agente_autonomo")

    def test_curate_deadlines_chronology(self):
        text1 = "Inscrições até 10/10/2026."
        _, vid1 = add_doc(self.db, "c1", tipo="edital_abertura", published_at="2026-08-01", text=text1)
        p1 = add_prop(self.db, "c1", version_id=vid1, field="registration_end",
                      value="2026-10-10", quote="10/10/2026")

        text2 = "Retificação 01: Inscrições prorrogadas até 20/10/2026."
        _, vid2 = add_doc(self.db, "c1", tipo="retificacao", published_at="2026-08-20", text=text2)
        p2 = add_prop(self.db, "c1", version_id=vid2, field="registration_end",
                      value="2026-10-20", quote="20/10/2026")

        res = autonomous_curator.curate_deadlines_chronology(self.db)
        self.assertGreaterEqual(res["validados"], 1)
        self.assertGreaterEqual(res["rejeitados"], 1)

        with closing(sqlite3.connect(self.db)) as conn:
            val_review = conn.execute("SELECT decision, reviewer FROM revisoes_campo WHERE proposal_id=?", (p2,)).fetchone()
            self.assertEqual(val_review[0], "validado")
            self.assertEqual(val_review[1], "agente_autonomo")

            rej_review = conn.execute("SELECT decision, reviewer FROM revisoes_campo WHERE proposal_id=?", (p1,)).fetchone()
            self.assertEqual(rej_review[0], "rejeitado")

            current = conn.execute("SELECT proposal_id, selected_by FROM valores_atuais WHERE contest_id='c1' AND field_name='registration_end'").fetchone()
            self.assertEqual(current[0], p2)
            self.assertEqual(current[1], "agente_autonomo")

    def test_curate_vacancies_and_deduplication(self):
        text = "Vagas imediatas: 5 vagas para o cargo."
        _, vid = add_doc(self.db, "c1", tipo="edital_abertura", text=text)
        p1 = add_prop(self.db, "c1", version_id=vid, field="immediate_vacancies",
                      value=5, quote="5 vagas", role_id="role-1")
        # Duplicata textual idêntica
        p2 = add_prop(self.db, "c1", version_id=vid, field="immediate_vacancies",
                      value=5, quote="5 vagas", role_id="role-1")

        res = autonomous_curator.curate_vacancies_arithmetic(self.db)
        self.assertGreaterEqual(res["validados"], 1)
        self.assertGreaterEqual(res["duplicatas_rejeitadas"], 1)

        with closing(sqlite3.connect(self.db)) as conn:
            r1 = conn.execute("SELECT decision FROM revisoes_campo WHERE proposal_id=?", (p1,)).fetchone()
            r2 = conn.execute("SELECT decision FROM revisoes_campo WHERE proposal_id=?", (p2,)).fetchone()
            self.assertEqual(r1[0], "validado")
            self.assertEqual(r2[0], "rejeitado")

    def test_curate_formation_si(self):
        text = "Exigência: Diploma em Sistemas de Informação ou Ciência da Computação."
        _, vid = add_doc(self.db, "c1", tipo="edital_abertura", text=text)
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO cargos_identidade (id,contest_id,name,created_at) "
                         "VALUES ('role-1','c1','Analista',?)", (NOW,))
        p = add_prop(self.db, "c1", version_id=vid, field="education",
                     value="Sistemas de Informação ou Ciência da Computação",
                     quote="Sistemas de Informação ou Ciência da Computação",
                     role_id="role-1")

        res = autonomous_curator.curate_formation_si(self.db)
        self.assertEqual(res["validados"], 1)

        with closing(sqlite3.connect(self.db)) as conn:
            curr = conn.execute("SELECT proposal_id, selected_by FROM valores_atuais WHERE contest_id='c1' AND field_name='education'").fetchone()
            self.assertIsNotNone(curr)
            self.assertEqual(curr[0], p)
            self.assertEqual(curr[1], "agente_autonomo")

    def test_run_curation_cycle_idempotence(self):
        text = "Inscrições até 25/10/2026. 10 vagas imediatas. Requisito: Bacharelado em Sistemas de Informação."
        _, vid = add_doc(self.db, "c1", tipo="edital_abertura", published_at="2026-09-01", text=text)
        add_prop(self.db, "c1", version_id=vid, field="registration_end",
                 value="2026-10-25", quote="25/10/2026")
        add_prop(self.db, "c1", version_id=vid, field="immediate_vacancies",
                 value=10, quote="10 vagas imediatas")
        add_prop(self.db, "c1", version_id=vid, field="education",
                 value="Bacharelado em Sistemas de Informação",
                 quote="Bacharelado em Sistemas de Informação")

        res1 = autonomous_curator.run_curation_cycle(self.db)
        self.assertGreater(res1["total_decisoes"], 0)

        # Segunda execução idempotente: sem erros, sem duplicações espúrias
        res2 = autonomous_curator.run_curation_cycle(self.db)
        self.assertEqual(res2["novas_revisoes"], 0)
        self.assertEqual(res2["novas_reconciliacoes"], 0)

    def test_portfolio_transition_to_confirmed(self):
        text = "Edital de Abertura. Inscrições até 2026-12-01. Vagas: 5 imediatas, 0 reserva. Requisito: Bacharelado em Sistemas de Informação."
        _, vid = add_doc(self.db, "c1", tipo="edital_abertura", published_at="2026-09-01", text=text)
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT INTO cargos_identidade (id,contest_id,name,created_at) "
                         "VALUES ('role-ti','c1','Analista de TI',?)", (NOW,))
        add_prop(self.db, "c1", version_id=vid, field="registration_end",
                 value="2026-12-01", quote="2026-12-01", role_id="role-ti")
        add_prop(self.db, "c1", version_id=vid, field="immediate_vacancies",
                 value=5, quote="5 imediatas", role_id="role-ti")
        add_prop(self.db, "c1", version_id=vid, field="reserve_vacancies",
                 value=0, quote="0 reserva", role_id="role-ti")
        add_prop(self.db, "c1", version_id=vid, field="education",
                 value="Bacharelado em Sistemas de Informação",
                 quote="Bacharelado em Sistemas de Informação", role_id="role-ti")
        add_prop(self.db, "c1", version_id=vid, field="si_compatibility",
                 value=True, quote="Sistemas de Informação", role_id="role-ti")

        # Antes da curadoria: item não está confirmado
        p_before = portfolio.portfolio(self.db, contest_id="c1", now=NOW)
        self.assertGreater(p_before["total"], 0)
        st_before = p_before["itens"][0]["prontidao"]["estado"]
        self.assertNotEqual(st_before, "informacao_confirmada")

        # Roda ciclo autônomo
        res = autonomous_curator.run_curation_cycle(self.db)
        self.assertGreater(res["novas_revisoes"], 0)

        # Depois da curadoria: transiciona para informacao_confirmada
        p_after = portfolio.portfolio(self.db, contest_id="c1", now=NOW)
        self.assertGreater(p_after["total"], 0)
        st_after = p_after["itens"][0]["prontidao"]["estado"]
        self.assertEqual(st_after, "informacao_confirmada")


if __name__ == "__main__":
    unittest.main()
