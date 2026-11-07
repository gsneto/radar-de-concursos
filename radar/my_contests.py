"""Módulo de persistência e gestão dos 'Meus Concursos' (Painel Pessoal de Foco).

Permite que o concurseiro favorite e selecione certames descobertos pelo Radar
para manter no seu painel principal, acompanhar prazos e direcionar o plano de estudos.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_my_contests(conn: sqlite3.Connection) -> None:
    """Cria a tabela de concursos selecionados pelo usuário se não existir."""
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS meus_concursos (
            id TEXT PRIMARY KEY,
            contest_id TEXT NOT NULL UNIQUE,
            role_id TEXT,
            selected_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ativo',
            notes TEXT,
            FOREIGN KEY (contest_id) REFERENCES concursos_identidade(id) ON DELETE CASCADE
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_meus_concursos_contest ON meus_concursos(contest_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_meus_concursos_status ON meus_concursos(status)"
    )
    conn.commit()


def add_my_contest(
    db_path: str,
    contest_id: str,
    role_id: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Adiciona ou atualiza um concurso na lista pessoal do usuário."""
    import uuid

    conn = sqlite3.connect(db_path)
    init_my_contests(conn)
    cur = conn.cursor()

    existing = cur.execute(
        "SELECT id, role_id, notes, status FROM meus_concursos WHERE contest_id = ?",
        (contest_id,),
    ).fetchone()

    now_str = _now()
    if existing:
        record_id = existing[0]
        new_role = role_id if role_id is not None else existing[1]
        new_notes = notes if notes is not None else existing[2]
        cur.execute(
            """
            UPDATE meus_concursos
            SET role_id = ?, notes = ?, status = 'ativo', selected_at = ?
            WHERE contest_id = ?
            """,
            (new_role, new_notes, now_str, contest_id),
        )
    else:
        record_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO meus_concursos (id, contest_id, role_id, selected_at, status, notes)
            VALUES (?, ?, ?, ?, 'ativo', ?)
            """,
            (record_id, contest_id, role_id, now_str, notes),
        )

    conn.commit()
    conn.close()

    return {
        "ok": True,
        "id": record_id,
        "contest_id": contest_id,
        "role_id": role_id,
        "selected_at": now_str,
        "notes": notes,
    }


def remove_my_contest(db_path: str, contest_id: str) -> bool:
    """Remove um concurso da lista pessoal do usuário."""
    conn = sqlite3.connect(db_path)
    init_my_contests(conn)
    cur = conn.cursor()
    cur.execute("DELETE FROM meus_concursos WHERE contest_id = ?", (contest_id,))
    rows = cur.rowcount
    conn.commit()
    conn.close()
    return rows > 0


def list_my_contests(db_path: str, *, status: str = "ativo") -> list[dict[str, Any]]:
    """Lista todos os concursos no painel pessoal, enriquecidos com dados de cargo, banca e instituição."""
    import re

    conn = sqlite3.connect(db_path)
    init_my_contests(conn)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    query = """
        SELECT 
            m.id,
            m.contest_id,
            m.role_id,
            m.selected_at,
            m.status,
            m.notes,
            c.name as role_name,
            c.specialty as role_specialty,
            oc.competition_id,
            oc.source_url
        FROM meus_concursos m
        LEFT JOIN cargos_identidade c ON c.id = m.role_id
        LEFT JOIN observacoes_concurso oc ON oc.contest_id = m.contest_id
        WHERE m.status = ?
        ORDER BY m.selected_at DESC
    """
    items = []
    try:
        rows = cur.execute(query, (status,)).fetchall()
        for r in rows:
            cid = r["contest_id"]

            # 1. Buscar banca organizadora
            banca_row = cur.execute(
                """
                SELECT issuer FROM documentos
                WHERE contest_id = ? AND issuer IS NOT NULL AND length(trim(issuer)) > 1
                ORDER BY CASE 
                    WHEN tipo_documental = 'pagina_concurso' THEN 0 
                    WHEN tipo_documental = 'edital_abertura' THEN 1 
                    ELSE 2 
                END, length(issuer) DESC LIMIT 1
                """,
                (cid,),
            ).fetchone()
            banca = banca_row["issuer"].strip() if banca_row and banca_row["issuer"] else None
            if not banca:
                src = r["source_url"] or ""
                if "fgv.br" in src:
                    banca = "FGV Conhecimento"
                elif "cebraspe.org.br" in src:
                    banca = "Cebraspe"
                elif "quadrix.org.br" in src:
                    banca = "Instituto Quadrix"
                elif "ibfc.org.br" in src:
                    banca = "IBFC"
                else:
                    banca = "Banca Oficial do Certame"

            # 2. Buscar título oficial do concurso e órgão/instituição
            doc_row = cur.execute(
                """
                SELECT title, official_url, published_at, tipo_documental
                FROM documentos
                WHERE contest_id = ? AND title IS NOT NULL
                ORDER BY CASE 
                    WHEN tipo_documental = 'pagina_concurso' THEN 0
                    WHEN tipo_documental = 'edital_abertura' THEN 1
                    WHEN kind = 'edital' THEN 2
                    ELSE 3
                END, length(title) DESC LIMIT 1
                """,
                (cid,),
            ).fetchone()

            raw_title = doc_row["title"] if doc_row and doc_row["title"] else (r["competition_id"] or "Concurso Oficial")

            # Extrair órgão de padrões como "Concurso Público para o/a [Órgão]"
            orgao = raw_title
            m = re.search(r'(?:para\s+(?:o|a|os|as)?\s*)(.+)', raw_title, re.IGNORECASE)
            if m:
                orgao = m.group(1).strip()

            contest_label = raw_title

            # 3. Cargo, especialidade e requisitos
            role_name = r["role_name"]
            role_specialty = r["role_specialty"]
            cargos_destaque = []

            if not role_name:
                first_role = cur.execute(
                    "SELECT name, specialty FROM cargos_identidade WHERE contest_id = ? LIMIT 1",
                    (cid,),
                ).fetchone()
                if first_role:
                    role_name = first_role["name"]
                    role_specialty = role_specialty or first_role["specialty"]

            # Buscar propostas de formação/área para enriquecer
            edu_rows = cur.execute(
                """
                SELECT p.value_json, p.ambiguity_reason
                FROM propostas_campo p
                WHERE p.contest_id = ? AND p.field_name IN ('education', 'accepted_courses') AND p.value_json IS NOT NULL
                LIMIT 5
                """,
                (cid,),
            ).fetchall()

            has_ti = False
            for er in edu_rows:
                v = str(er["value_json"]).strip('"')
                if any(k in v for k in ("Ciência da Computação", "Sistemas de Informação", "Ciência de Dados", "Software")):
                    has_ti = True
                    cargos_destaque.append("Tecnologia da Informação & Dados")
                    break

            if not role_name:
                if has_ti:
                    role_name = "Analista de Tecnologia da Informação (TI / SI)"
                else:
                    role_name = "Cargos de Nível Superior & Técnico"

            # 4. Compatibilidade com Sistemas de Informação
            si_row = cur.execute(
                """
                SELECT p.value_json 
                FROM propostas_campo p
                WHERE p.contest_id = ? AND p.field_name = 'si_compatibility'
                ORDER BY CASE 
                    WHEN p.value_json LIKE '%aceito_expressamente%' THEN 0
                    WHEN p.value_json LIKE '%abrangido%' THEN 1
                    WHEN p.value_json LIKE '%nivel_minimo%' THEN 2
                    ELSE 3
                END
                LIMIT 1
                """,
                (cid,),
            ).fetchone()
            si_compativel = bool(si_row and any(k in str(si_row["value_json"]).lower() for k in ("aceito", "abrangido", "nivel_minimo")))

            # 5. Localidade / Prova
            loc_row = cur.execute(
                """
                SELECT p.value_json
                FROM propostas_campo p
                WHERE p.contest_id = ? AND p.field_name IN ('exam_location', 'work_location')
                LIMIT 1
                """,
                (cid,),
            ).fetchone()
            localidade = str(loc_row["value_json"]).strip('"') if loc_row else None

            # 6. Remuneração e Vagas consolidadas
            val_rows = cur.execute(
                """
                SELECT v.field_name, p.value_json
                FROM valores_atuais v
                JOIN propostas_campo p ON p.id = v.proposal_id
                WHERE v.contest_id = ?
                """,
                (cid,),
            ).fetchall()

            remuneracao = None
            vagas = None
            for vr in val_rows:
                fname = vr["field_name"]
                fval = vr["value_json"]
                if fname in ("remuneracao", "salary") and fval:
                    remuneracao = fval
                elif fname in ("vagas_total", "immediate_vacancies", "vagas") and fval:
                    try:
                        vagas = int(fval)
                    except (ValueError, TypeError):
                        pass

            # 7. Buscar próximo prazo ativo com rótulo
            prazo_row = cur.execute(
                """
                SELECT p.field_name, p.value_json
                FROM propostas_campo p
                WHERE p.contest_id = ? AND p.field_name IN ('registration_end', 'exam_date', 'inscricao_fim', 'prova_data', 'registration_start')
                ORDER BY CASE 
                    WHEN p.field_name = 'registration_end' THEN 0 
                    WHEN p.field_name = 'exam_date' THEN 1 
                    ELSE 2 
                END, p.value_json ASC LIMIT 1
                """,
                (cid,),
            ).fetchone()

            proximo_prazo = None
            if prazo_row:
                fname = prazo_row["field_name"]
                prazo_label = (
                    "Fim das Inscrições" if "registration_end" in fname or "inscricao_fim" in fname
                    else "Data da Prova" if "exam_date" in fname or "prova_data" in fname
                    else "Início das Inscrições"
                )
                proximo_prazo = {
                    "campo": fname,
                    "label": prazo_label,
                    "data": str(prazo_row["value_json"]).strip('"'),
                }

            items.append(
                {
                    "id": r["id"],
                    "contest_id": cid,
                    "role_id": r["role_id"],
                    "contest_label": contest_label,
                    "orgao": orgao,
                    "banca": banca,
                    "competition_id": r["competition_id"],
                    "role_name": role_name,
                    "role_specialty": role_specialty,
                    "si_compativel": si_compativel,
                    "localidade": localidade,
                    "remuneracao": remuneracao,
                    "vagas": vagas,
                    "proximo_prazo": proximo_prazo,
                    "selected_at": r["selected_at"],
                    "status": r["status"],
                    "notes": r["notes"],
                }
            )
    finally:
        conn.close()

    return items
