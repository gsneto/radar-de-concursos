"""Persistência SQLite local do Radar de Concursos (contrato v1).

Mantém uma tabela ``concursos`` com as colunas exatas do contrato v1 e chave
natural ``(source_url, competition_id, role)``. ``upsert_records`` é
transacional: valida o lote inteiro antes de gravar, de modo que um registro
inválido não persiste parcialmente nem altera dados anteriores. ``None`` é
desconhecido; ``0`` é preservado como zero quando a fonte o afirma.

Somente biblioteca padrão (``sqlite3``). Nenhum valor é inventado: campos
ausentes do contrato são gravados como ``NULL`` (desconhecido), jamais
preenchidos por inferência.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# Campos exatos do contrato v1, na ordem da spec.
CONTRACT_FIELDS = (
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
)

# Chave natural e campos obrigatórios do contrato.
_NATURAL_KEY_FIELDS = ("source_url", "competition_id", "role")

# Contadores de vagas: inteiro (não bool) ou None.
_INTEGER_FIELDS = ("immediate_vacancies", "reserve_vacancies", "indigenous_vacancies")
_TEXT_FIELDS = tuple(field for field in CONTRACT_FIELDS if field not in _INTEGER_FIELDS)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS concursos (
    competition_id      TEXT,
    competition         TEXT,
    agency              TEXT,
    role                TEXT,
    education           TEXT,
    immediate_vacancies INTEGER,
    reserve_vacancies   INTEGER,
    indigenous_vacancies INTEGER,
    registration_start  TEXT,
    registration_end    TEXT,
    registration_status TEXT,
    exam_date           TEXT,
    exam_location       TEXT,
    work_location       TEXT,
    source_name         TEXT,
    source_url          TEXT,
    evidence_url        TEXT,
    verified_at         TEXT,
    PRIMARY KEY (source_url, competition_id, role)
)
"""

_NONKEY_COLUMNS = [c for c in CONTRACT_FIELDS if c not in _NATURAL_KEY_FIELDS]

_INSERT_SQL = (
    "INSERT INTO concursos ("
    + ", ".join(CONTRACT_FIELDS)
    + ") VALUES ("
    + ", ".join("?" for _ in CONTRACT_FIELDS)
    + ") ON CONFLICT ("
    + ", ".join(_NATURAL_KEY_FIELDS)
    + ") DO UPDATE SET "
    + ", ".join(f"{column}=excluded.{column}" for column in _NONKEY_COLUMNS)
)

_SELECT_SQL = (
    "SELECT "
    + ", ".join(CONTRACT_FIELDS)
    + " FROM concursos ORDER BY source_name COLLATE NOCASE, competition_id,"
    + " role COLLATE NOCASE"
)


def _validate_record(record, index: int) -> dict:
    """Valida um registro do contrato v1 sem inventar valores.

    Levanta ``ValueError`` para registro não-dict, campos fora do contrato,
    campos obrigatórios ausentes/vazios, contadores de vaga não inteiros e
    ``verified_at`` com tipo inválido.
    """
    if not isinstance(record, dict):
        raise ValueError(
            f"registro {index}: esperado dict, recebido {type(record).__name__}"
        )

    unknown = sorted(set(record) - set(CONTRACT_FIELDS))
    if unknown:
        raise ValueError(
            f"registro {index}: campos fora do contrato v1: {', '.join(unknown)}"
        )

    for field in _NATURAL_KEY_FIELDS:
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"registro {index}: campo obrigatório {field!r} ausente ou inválido"
            )

    for field in _INTEGER_FIELDS:
        value = record.get(field)
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool)
        ):
            raise ValueError(
                f"registro {index}: campo {field!r} deve ser inteiro ou None"
            )

    for field in _TEXT_FIELDS:
        value = record.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(
                f"registro {index}: campo {field!r} deve ser string ou None"
            )

    verified_at = record.get("verified_at")
    if verified_at is not None and not isinstance(verified_at, str):
        raise ValueError(f"registro {index}: campo 'verified_at' deve ser string ou None")

    return record


def upsert_records(db_path, records) -> None:
    """Insere/atualiza registros do contrato v1 de forma transacional.

    ``records`` deve ser um iterável de dicts. O lote é validado integralmente
    antes de qualquer escrita: um registro inválido levanta ``ValueError`` e
    nada é gravado, preservando os dados anteriores. Lote vazio é um no-op.
    """
    if isinstance(records, (dict, str, bytes)):
        raise ValueError("records deve ser um iterável de registros (dicts)")

    try:
        materialized = list(records)
    except TypeError as exc:
        raise ValueError("records deve ser um iterável de registros (dicts)") from exc

    validated = [_validate_record(record, i) for i, record in enumerate(materialized)]
    if not validated:
        return

    rows = [tuple(record.get(column) for column in CONTRACT_FIELDS) for record in validated]

    connection = sqlite3.connect(db_path)
    try:
        connection.execute(_SCHEMA)
        try:
            connection.executemany(_INSERT_SQL, rows)
        except Exception:
            connection.rollback()
            raise
        connection.commit()
    finally:
        connection.close()


def list_records(db_path) -> list[dict]:
    """Retorna os registros persistidos como ``list[dict]`` JSON-compatível.

    Cada dict tem as chaves do contrato v1 na ordem da spec, preservando
    ``None`` e ``0``. Ordenação determinística por ``source_name``,
    ``competition_id`` e ``role``. Retorna lista vazia quando o banco ou a
    tabela ainda não existe.
    """
    path = Path(db_path)
    if not path.exists():
        return []

    connection = sqlite3.connect(db_path)
    try:
        try:
            cursor = connection.execute(_SELECT_SQL)
        except sqlite3.OperationalError as exc:
            if "no such table: concursos" in str(exc):
                return []
            raise
        rows = cursor.fetchall()
        return [dict(zip(CONTRACT_FIELDS, row)) for row in rows]
    finally:
        connection.close()
