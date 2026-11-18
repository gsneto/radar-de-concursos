"""Módulo de persistência e gestão dos 'Meus Concursos' (Painel Pessoal de Foco).

Permite que o concurseiro favorite e selecione certames descobertos pelo Radar
para manter no seu painel principal, acompanhar prazos e direcionar o plano de estudos,
com isolamento multiusuário por ``user_id`` e consultas em lote (sem N+1).
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCHEMA_LOCK = threading.Lock()
_SCHEMA_READY: dict[str, int] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(db_path: str | Path) -> sqlite3.Connection:
    return sqlite3.connect(str(db_path), timeout=15)


def init_my_contests(conn: sqlite3.Connection) -> None:
    """Cria/atualiza a tabela de concursos selecionados com suporte multiusuário (user_id)."""
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS meus_concursos (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT '',
            contest_id TEXT NOT NULL,
            role_id TEXT,
            selected_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ativo',
            notes TEXT,
            UNIQUE(user_id, contest_id),
            FOREIGN KEY (contest_id) REFERENCES concursos_identidade(id) ON DELETE CASCADE
        )
        """
    )
    cols = {row[1] for row in cur.execute("PRAGMA table_info(meus_concursos)").fetchall()}
    if "user_id" not in cols:
        cur.execute("PRAGMA foreign_keys=OFF")
        try:
            cur.execute(
                """
                CREATE TABLE meus_concursos_v2 (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT '',
                    contest_id TEXT NOT NULL,
                    role_id TEXT,
                    selected_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'ativo',
                    notes TEXT,
                    UNIQUE(user_id, contest_id),
                    FOREIGN KEY (contest_id) REFERENCES concursos_identidade(id) ON DELETE CASCADE
                )
                """
            )
            cur.execute(
                """
                INSERT INTO meus_concursos_v2 (id, user_id, contest_id, role_id, selected_at, status, notes)
                SELECT id, '', contest_id, role_id, selected_at, status, notes FROM meus_concursos
                """
            )
            cur.execute("DROP TABLE meus_concursos")
            cur.execute("ALTER TABLE meus_concursos_v2 RENAME TO meus_concursos")
        finally:
            cur.execute("PRAGMA foreign_keys=ON")

    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_meus_concursos_contest ON meus_concursos(contest_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_meus_concursos_user ON meus_concursos(user_id, status)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_meus_concursos_status ON meus_concursos(status)"
    )
    conn.commit()


def ensure_my_contests_schema(db_path: str | Path) -> None:
    """Inicializa o esquema de meus_concursos apenas uma vez por arquivo SQLite."""
    cache_key: str | None = None
    ctime_ns = 0
    try:
        resolved = Path(db_path).resolve()
        if resolved.exists():
            cache_key = str(resolved)
            ctime_ns = resolved.stat().st_ctime_ns
            if _SCHEMA_READY.get(cache_key) == ctime_ns:
                return
    except OSError:
        cache_key = None

    with _SCHEMA_LOCK:
        if cache_key and _SCHEMA_READY.get(cache_key) == ctime_ns:
            return
        with closing(_connect(db_path)) as conn:
            init_my_contests(conn)
        if cache_key is None:
            try:
                resolved = Path(db_path).resolve()
                if resolved.exists():
                    cache_key = str(resolved)
                    ctime_ns = resolved.stat().st_ctime_ns
            except OSError:
                cache_key = None
        if cache_key:
            _SCHEMA_READY[cache_key] = ctime_ns


def _decode_json_scalar(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (int, float, bool)):
        return raw
    text = str(raw)
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text.strip('"')


def add_my_contest(
    db_path: str,
    contest_id: str,
    role_id: str | None = None,
    notes: str | None = None,
    *,
    status: str = "ativo",
    user_id: str = "",
) -> dict[str, Any]:
    """Adiciona ou atualiza um concurso na lista pessoal do usuário."""
    if status not in ("ativo", "arquivado"):
        raise ValueError("status inválido")
    ensure_my_contests_schema(db_path)
    uid = str(user_id or "")
    now_str = _now()

    with closing(_connect(db_path)) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT id, role_id, notes FROM meus_concursos WHERE user_id = ? AND contest_id = ?",
                (uid, contest_id),
            ).fetchone()

            if existing:
                record_id = existing[0]
                final_role = role_id if role_id is not None else existing[1]
                final_notes = notes if notes is not None else existing[2]
                conn.execute(
                    """
                    UPDATE meus_concursos
                    SET role_id = ?, notes = ?, status = ?, selected_at = ?
                    WHERE user_id = ? AND contest_id = ?
                    """,
                    (final_role, final_notes, status, now_str, uid, contest_id),
                )
            else:
                record_id = str(uuid.uuid4())
                final_role = role_id
                final_notes = notes
                conn.execute(
                    """
                    INSERT INTO meus_concursos (id, user_id, contest_id, role_id, selected_at, status, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (record_id, uid, contest_id, final_role, now_str, status, final_notes),
                )
            conn.commit()
        except BaseException:
            conn.rollback()
            raise

    return {
        "ok": True,
        "id": record_id,
        "contest_id": contest_id,
        "role_id": final_role,
        "status": status,
        "selected_at": now_str,
        "notes": final_notes,
    }


def remove_my_contest(db_path: str, contest_id: str, *, user_id: str = "") -> bool:
    """Remove um concurso da lista pessoal do usuário."""
    ensure_my_contests_schema(db_path)
    uid = str(user_id or "")
    with closing(_connect(db_path)) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                "DELETE FROM meus_concursos WHERE user_id = ? AND contest_id = ?",
                (uid, contest_id),
            )
            rows = cur.rowcount
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    return rows > 0


def count_my_contests(db_path: str, *, status: str = "ativo", user_id: str = "") -> int:
    """Conta o total de concursos selecionados pelo usuário (para paginação honesta)."""
    ensure_my_contests_schema(db_path)
    uid = str(user_id or "")
    with closing(_connect(db_path)) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM meus_concursos WHERE user_id = ? AND status = ?",
            (uid, status),
        ).fetchone()
        return int(row[0] if row else 0)


def list_my_contests(
    db_path: str,
    *,
    status: str = "ativo",
    user_id: str = "",
    limit: int | None = None,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Lista os concursos no painel pessoal sem fan-out de observações e com enriquecimento em lote."""
    ensure_my_contests_schema(db_path)
    uid = str(user_id or "")

    with closing(_connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        base_sql = """
            SELECT
                m.id,
                m.contest_id,
                m.role_id,
                m.selected_at,
                m.status,
                m.notes,
                c.name AS role_name,
                c.specialty AS role_specialty,
                (
                    SELECT oc.competition_id
                    FROM observacoes_concurso oc
                    WHERE oc.contest_id = m.contest_id
                    ORDER BY oc.observed_at DESC, oc.rowid DESC
                    LIMIT 1
                ) AS competition_id,
                (
                    SELECT oc.source_url
                    FROM observacoes_concurso oc
                    WHERE oc.contest_id = m.contest_id
                    ORDER BY oc.observed_at DESC, oc.rowid DESC
                    LIMIT 1
                ) AS source_url
            FROM meus_concursos m
            LEFT JOIN cargos_identidade c ON c.id = m.role_id
            WHERE m.user_id = ? AND m.status = ?
            ORDER BY m.selected_at DESC, m.id DESC
        """
        params: list[Any] = [uid, status]
        if limit is not None:
            base_sql += " LIMIT ? OFFSET ?"
            params.extend([max(0, int(limit)), max(0, int(offset))])

        rows = cur.execute(base_sql, params).fetchall()
        if not rows:
            return []

        contest_ids = list({r["contest_id"] for r in rows})
        placeholders = ",".join("?" for _ in contest_ids)

        # 1. Batch fetch documentos (título e banca)
        docs_by_contest: dict[str, list[sqlite3.Row]] = {}
        for d_row in cur.execute(
            f"""
            SELECT contest_id, title, issuer, official_url, published_at, tipo_documental, kind
            FROM documentos
            WHERE contest_id IN ({placeholders})
            """,
            contest_ids,
        ).fetchall():
            docs_by_contest.setdefault(d_row["contest_id"], []).append(d_row)

        # 2. Batch fetch primeiro cargo como fallback
        first_role_by_contest: dict[str, tuple[str, str | None]] = {}
        for c_row in cur.execute(
            f"""
            SELECT contest_id, name, specialty
            FROM cargos_identidade
            WHERE contest_id IN ({placeholders})
            ORDER BY created_at ASC, id ASC
            """,
            contest_ids,
        ).fetchall():
            first_role_by_contest.setdefault(
                c_row["contest_id"], (c_row["name"], c_row["specialty"])
            )

        # 3. Batch fetch propostas relevantes
        props_by_contest: dict[str, list[sqlite3.Row]] = {}
        for p_row in cur.execute(
            f"""
            SELECT contest_id, role_id, field_name, value_json, ambiguity_reason
            FROM propostas_campo
            WHERE contest_id IN ({placeholders})
              AND value_json IS NOT NULL
              AND field_name IN (
                  'education', 'accepted_courses', 'si_compatibility',
                  'exam_location', 'work_location',
                  'registration_end', 'exam_date', 'inscricao_fim', 'prova_data', 'registration_start'
              )
            """,
            contest_ids,
        ).fetchall():
            props_by_contest.setdefault(p_row["contest_id"], []).append(p_row)

        # 4. Batch fetch valores atuais selecionados
        vals_by_contest: dict[str, list[sqlite3.Row]] = {}
        for v_row in cur.execute(
            f"""
            SELECT v.contest_id, v.role_id, v.field_name, p.value_json
            FROM valores_atuais v
            JOIN propostas_campo p ON p.id = v.proposal_id
            WHERE v.contest_id IN ({placeholders})
            ORDER BY v.selected_at ASC, v.rowid ASC
            """,
            contest_ids,
        ).fetchall():
            vals_by_contest.setdefault(v_row["contest_id"], []).append(v_row)

        items: list[dict[str, Any]] = []
        for r in rows:
            cid = r["contest_id"]
            rid = r["role_id"]
            c_docs = docs_by_contest.get(cid, [])
            c_props = props_by_contest.get(cid, [])
            c_vals = vals_by_contest.get(cid, [])

            # Banca
            issuer_docs = [
                d for d in c_docs if d["issuer"] and len(d["issuer"].strip()) > 1
            ]
            issuer_docs.sort(
                key=lambda d: (
                    0 if d["tipo_documental"] == "pagina_concurso"
                    else 1 if d["tipo_documental"] == "edital_abertura"
                    else 2,
                    -len(d["issuer"] or ""),
                )
            )
            banca = issuer_docs[0]["issuer"].strip() if issuer_docs else None
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

            # Título e Órgão
            titled_docs = [d for d in c_docs if d["title"]]
            titled_docs.sort(
                key=lambda d: (
                    0 if d["tipo_documental"] == "pagina_concurso"
                    else 1 if d["tipo_documental"] == "edital_abertura"
                    else 2 if d["kind"] == "edital"
                    else 3,
                    -len(d["title"] or ""),
                )
            )
            raw_title = (
                titled_docs[0]["title"]
                if titled_docs
                else (r["competition_id"] or "Concurso Oficial")
            )
            m = re.search(r"(?:para\s+(?:o|a|os|as)?\s*)(.+)", raw_title, re.IGNORECASE)
            orgao = m.group(1).strip() if m else raw_title
            contest_label = raw_title

            # Cargo e formação
            role_name = r["role_name"]
            role_specialty = r["role_specialty"]
            if not role_name and cid in first_role_by_contest:
                role_name, fallback_spec = first_role_by_contest[cid]
                role_specialty = role_specialty or fallback_spec

            has_ti = any(
                any(
                    k in str(p["value_json"])
                    for k in ("Ciência da Computação", "Sistemas de Informação", "Ciência de Dados", "Software")
                )
                for p in c_props
                if p["field_name"] in ("education", "accepted_courses")
            )
            if not role_name:
                role_name = (
                    "Analista de Tecnologia da Informação (TI / SI)"
                    if has_ti
                    else "Cargos de Nível Superior & Técnico"
                )

            # Compatibilidade SI
            si_props = [p for p in c_props if p["field_name"] == "si_compatibility"]
            si_compativel = any(
                any(k in str(p["value_json"]).lower() for k in ("aceito", "abrangido", "nivel_minimo"))
                for p in si_props
            )

            # Localidade
            loc_prop = next(
                (p for p in c_props if p["field_name"] in ("exam_location", "work_location")),
                None,
            )
            localidade = str(_decode_json_scalar(loc_prop["value_json"])) if loc_prop else None

            # Remuneração e Vagas (filtradas pelo cargo selecionado ou escopo global do edital)
            remuneracao = None
            vagas = None
            for vr in c_vals:
                if rid and vr["role_id"] is not None and vr["role_id"] != rid:
                    continue
                fname = vr["field_name"]
                decoded = _decode_json_scalar(vr["value_json"])
                if fname in ("remuneracao", "salary") and decoded is not None:
                    remuneracao = str(decoded)
                elif fname in ("vagas_total", "immediate_vacancies", "vagas") and decoded is not None:
                    try:
                        vagas = int(decoded)
                    except (ValueError, TypeError):
                        pass

            # Próximo prazo
            prazo_props = [
                p
                for p in c_props
                if p["field_name"]
                in ("registration_end", "exam_date", "inscricao_fim", "prova_data", "registration_start")
            ]
            prazo_props.sort(
                key=lambda p: (
                    0 if p["field_name"] == "registration_end"
                    else 1 if p["field_name"] == "exam_date"
                    else 2,
                    str(p["value_json"]),
                )
            )
            proximo_prazo = None
            if prazo_props:
                best_p = prazo_props[0]
                fname = best_p["field_name"]
                prazo_label = (
                    "Fim das Inscrições"
                    if "registration_end" in fname or "inscricao_fim" in fname
                    else "Data da Prova"
                    if "exam_date" in fname or "prova_data" in fname
                    else "Início das Inscrições"
                )
                proximo_prazo = {
                    "campo": fname,
                    "label": prazo_label,
                    "data": str(_decode_json_scalar(best_p["value_json"])),
                }

            items.append(
                {
                    "id": r["id"],
                    "contest_id": cid,
                    "role_id": rid,
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

        return items
