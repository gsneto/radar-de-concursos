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
    """Lista todos os concursos no painel pessoal, enriquecidos com dados de cargo e prazos."""
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
            # Buscar títulos e documentos associados
            doc_row = cur.execute(
                """
                SELECT title, official_url, published_at
                FROM documentos
                WHERE contest_id = ?
                ORDER BY published_at DESC LIMIT 1
                """,
                (cid,),
            ).fetchone()

            contest_label = r["competition_id"] or "Concurso"
            if doc_row and doc_row["title"]:
                contest_label = doc_row["title"]

            # Se role_name ainda for nulo, tenta o primeiro cargo do certame
            role_name = r["role_name"]
            if not role_name:
                first_role = cur.execute(
                    "SELECT name, specialty FROM cargos_identidade WHERE contest_id = ? LIMIT 1",
                    (cid,),
                ).fetchone()
                if first_role:
                    role_name = first_role["name"]

            # Verificar se há valores consolidados de remuneração ou vagas em valores_atuais
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

            # Buscar próximo prazo ativo
            prazo_row = cur.execute(
                """
                SELECT p.field_name, p.value_json, e.quote
                FROM propostas_campo p
                JOIN evidencias e ON e.id = p.evidence_id
                WHERE p.contest_id = ? AND p.field_name IN ('registration_end', 'exam_date', 'inscricao_fim', 'prova_data')
                ORDER BY p.value_json ASC LIMIT 1
                """,
                (cid,),
            ).fetchone()

            proximo_prazo = None
            if prazo_row:
                proximo_prazo = {
                    "campo": prazo_row["field_name"],
                    "data": str(prazo_row["value_json"]).strip('"'),
                }

            items.append(
                {
                    "id": r["id"],
                    "contest_id": cid,
                    "role_id": r["role_id"],
                    "contest_label": contest_label,
                    "competition_id": r["competition_id"],
                    "role_name": role_name,
                    "role_specialty": r["role_specialty"],
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
