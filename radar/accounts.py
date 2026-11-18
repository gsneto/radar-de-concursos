"""Contas de usuário, sessões seguras, planos e webhook de pagamento (SaaS multiusuário).

Mantém compatibilidade total com o uso local sem login: registros sem usuário ou do
perfil administrador continuam enxergando ``user_id = ''`` quando apropriado, enquanto
novos alunos recebem escopo isolado por ``user_id`` para concursos foco, flashcards,
questões, simulados e cronômetro de estudos.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from radar.document_store import connect_documents

VALID_ROLES = ("student", "admin")
VALID_PLANS = ("free", "pro", "founder")
VALID_PLAN_STATUSES = ("active", "trial", "past_due", "canceled")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _hash_password(password: str, salt: bytes | None = None) -> str:
    if not isinstance(password, str) or len(password) < 6:
        raise ValueError("a senha deve ter pelo menos 6 caracteres")
    salt = salt or os.urandom(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
        dklen=32,
    )
    return f"scrypt${salt.hex()}${derived.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, salt_hex, hash_hex = str(encoded).split("$", 2)
        if scheme != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=16384,
            r=8,
            p=1,
            dklen=32,
        )
        return hmac.compare_digest(derived, expected)
    except Exception:
        return False


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalize_email(email: str) -> str:
    cleaned = str(email or "").strip().lower()
    if not _EMAIL_RE.match(cleaned) or len(cleaned) > 200:
        raise ValueError("e-mail inválido")
    return cleaned


def _safe_user(row: tuple | None) -> dict[str, Any] | None:
    if not row:
        return None
    keys = ("id", "email", "name", "role", "plan", "plan_status", "created_at", "updated_at")
    return dict(zip(keys, row))


_USER_COLS = "id, email, name, role, plan, plan_status, created_at, updated_at"


def ensure_accounts_schema(db_path) -> None:
    """Cria tabelas de contas/billing e garante coluna user_id nas tabelas pessoais."""
    conn = connect_documents(db_path)
    try:
        present = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }

        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student' CHECK(role IN ('student','admin')),
                plan TEXT NOT NULL DEFAULT 'free' CHECK(plan IN ('free','pro','founder')),
                plan_status TEXT NOT NULL DEFAULT 'active' CHECK(plan_status IN ('active','trial','past_due','canceled')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_app_sessions_user ON app_sessions(user_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_billing_events (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                email TEXT NOT NULL,
                plan TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_billing_email ON app_billing_events(email, created_at)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_user_preferences (
                user_id TEXT PRIMARY KEY,
                prefs_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        # Adiciona user_id aditivo nas tabelas pessoais quando já existem no SQLite
        personal_tables = (
            "pratica_flashcards",
            "pratica_tentativas",
            "pratica_simulados",
            "estudo_sessoes",
            "estudo_progresso",
        )
        for table in personal_tables:
            if table not in present:
                continue
            cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if "user_id" not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT NOT NULL DEFAULT ''")
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_user ON {table}(user_id)")

        # Atualiza índice de sessão única em estudo_sessoes para isolar por user_id
        if "estudo_sessoes" in present:
            idx_sql = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_estudo_sessao_unica'"
            ).fetchone()
            if idx_sql and "user_id" not in (idx_sql[0] or ""):
                conn.execute("DROP INDEX IF EXISTS idx_estudo_sessao_unica")
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_estudo_sessao_unica "
                    "ON estudo_sessoes(user_id) WHERE estado IN ('em_andamento','pausada')"
                )

        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()

    # Garante UNIQUE(user_id, contest_id, topico_id) em estudo_progresso sem FKs quebradas
    _upgrade_estudo_progresso_unique(db_path)


def _upgrade_estudo_progresso_unique(db_path) -> None:
    conn = connect_documents(db_path)
    try:
        sql_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='estudo_progresso'"
        ).fetchone()
        if not sql_row or not sql_row[0]:
            return
        ddl = sql_row[0]
        if "UNIQUE(user_id, contest_id, topico_id)" in ddl or "UNIQUE(user_id,contest_id,topico_id)" in ddl:
            return
    finally:
        conn.close()

    conn2 = sqlite3.connect(db_path, timeout=15)
    try:
        conn2.execute("PRAGMA foreign_keys=OFF")
        conn2.execute("BEGIN IMMEDIATE")
        conn2.execute(
            """
            CREATE TABLE estudo_progresso_v2 (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT '',
                contest_id TEXT NOT NULL DEFAULT '',
                topico_id TEXT NOT NULL REFERENCES estudo_topicos(id),
                state TEXT NOT NULL CHECK(state IN ('nao_iniciado','estudando','revisado','concluido')),
                data_conclusao TEXT,
                adiamentos INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, contest_id, topico_id)
            )
            """
        )
        conn2.execute(
            """
            INSERT INTO estudo_progresso_v2
                (id, user_id, contest_id, topico_id, state, data_conclusao, adiamentos, created_at, updated_at)
            SELECT
                id, COALESCE(user_id, ''), contest_id, topico_id, state, data_conclusao, adiamentos, created_at, updated_at
            FROM estudo_progresso
            """
        )
        conn2.execute("DROP TABLE estudo_progresso")
        conn2.execute("ALTER TABLE estudo_progresso_v2 RENAME TO estudo_progresso")
        conn2.execute("CREATE INDEX IF NOT EXISTS idx_estudo_progresso_topico ON estudo_progresso(topico_id)")
        conn2.execute("CREATE INDEX IF NOT EXISTS idx_estudo_progresso_user ON estudo_progresso(user_id)")
        conn2.commit()
    except BaseException:
        conn2.rollback()
        raise
    finally:
        conn2.execute("PRAGMA foreign_keys=ON")
        conn2.close()


def has_admin_user(db_path) -> bool:
    ensure_accounts_schema(db_path)
    conn = connect_documents(db_path)
    try:
        row = conn.execute("SELECT 1 FROM app_users WHERE role='admin' LIMIT 1").fetchone()
        return row is not None
    finally:
        conn.close()


def register_user(
    db_path,
    *,
    name: str,
    email: str,
    password: str,
    role: str = "student",
    plan: str = "free",
    allow_bootstrap_admin: bool = False,
) -> dict[str, Any]:
    ensure_accounts_schema(db_path)
    clean_name = " ".join(str(name or "").split()).strip()[:120]
    if len(clean_name) < 2:
        raise ValueError("nome completo obrigatório")
    clean_email = _normalize_email(email)
    pw_hash = _hash_password(password)

    target_role = role if role in VALID_ROLES else "student"
    target_plan = plan if plan in VALID_PLANS else "free"
    now = _now_iso()
    uid = str(uuid4())

    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT 1 FROM app_users WHERE email=?", (clean_email,)).fetchone()
        if existing:
            raise ValueError("este e-mail já está cadastrado")

        if allow_bootstrap_admin:
            admin_exists = conn.execute("SELECT 1 FROM app_users WHERE role='admin' LIMIT 1").fetchone()
            if not admin_exists:
                target_role = "admin"
                target_plan = "founder"
        elif target_role == "admin":
            target_role = "student"

        # Se já existe compra aprovada para este e-mail via webhook, libera automaticamente!
        purchase = conn.execute(
            "SELECT plan, event_type FROM app_billing_events WHERE email=? ORDER BY created_at DESC LIMIT 1",
            (clean_email,),
        ).fetchone()
        if purchase and purchase[1] in ("purchase_approved", "subscription_active", "manual_grant"):
            if purchase[0] in VALID_PLANS:
                target_plan = purchase[0]

        conn.execute(
            f"""
            INSERT INTO app_users(id, email, name, password_hash, role, plan, plan_status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (uid, clean_email, clean_name, pw_hash, target_role, target_plan, now, now),
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()

    return get_user_by_id(db_path, uid)


def authenticate_user(db_path, *, email: str, password: str) -> dict[str, Any] | None:
    ensure_accounts_schema(db_path)
    try:
        clean_email = _normalize_email(email)
    except ValueError:
        return None
    conn = connect_documents(db_path)
    try:
        row = conn.execute(
            f"SELECT {_USER_COLS}, password_hash FROM app_users WHERE email=?",
            (clean_email,),
        ).fetchone()
        if not row:
            return None
        pw_hash = row[-1]
        if not _verify_password(password, pw_hash):
            return None
        return _safe_user(row[:-1])
    finally:
        conn.close()


def get_user_by_id(db_path, user_id: str) -> dict[str, Any] | None:
    ensure_accounts_schema(db_path)
    conn = connect_documents(db_path)
    try:
        row = conn.execute(f"SELECT {_USER_COLS} FROM app_users WHERE id=?", (user_id,)).fetchone()
        return _safe_user(row)
    finally:
        conn.close()


def create_session(db_path, user_id: str, *, days: int = 30) -> str:
    ensure_accounts_schema(db_path)
    token = secrets.token_urlsafe(32)
    digest = _token_digest(token)
    now = _now()
    expires = (now + timedelta(days=days)).isoformat()
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO app_sessions(token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (digest, user_id, expires, now.isoformat()),
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return token


def get_user_by_session_token(db_path, token: str | None) -> dict[str, Any] | None:
    if not token or not isinstance(token, str):
        return None
    ensure_accounts_schema(db_path)
    digest = _token_digest(token.strip())
    now_iso = _now_iso()
    conn = connect_documents(db_path)
    try:
        row = conn.execute(
            f"""
            SELECT {', '.join('u.' + c.strip() for c in _USER_COLS.split(','))}, s.expires_at
            FROM app_sessions s
            JOIN app_users u ON u.id = s.user_id
            WHERE s.token_hash = ?
            """,
            (digest,),
        ).fetchone()
        if not row:
            return None
        expires_at = row[-1]
        if expires_at < now_iso:
            return None
        return _safe_user(row[:-1])
    finally:
        conn.close()


def revoke_session(db_path, token: str | None) -> None:
    if not token:
        return
    ensure_accounts_schema(db_path)
    digest = _token_digest(token.strip())
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM app_sessions WHERE token_hash=?", (digest,))
        conn.commit()
    finally:
        conn.close()


def list_users(db_path, *, limit: int = 100) -> list[dict[str, Any]]:
    ensure_accounts_schema(db_path)
    conn = connect_documents(db_path)
    try:
        rows = conn.execute(
            f"SELECT {_USER_COLS} FROM app_users ORDER BY created_at DESC LIMIT ?",
            (max(1, int(limit)),),
        ).fetchall()
        return [_safe_user(r) for r in rows if r]
    finally:
        conn.close()


def set_user_plan(
    db_path,
    user_id: str,
    *,
    plan: str,
    plan_status: str = "active",
    role: str | None = None,
) -> dict[str, Any]:
    ensure_accounts_schema(db_path)
    if plan not in VALID_PLANS:
        raise ValueError("plano inválido")
    if plan_status not in VALID_PLAN_STATUSES:
        raise ValueError("status de plano inválido")
    if role is not None and role not in VALID_ROLES:
        raise ValueError("perfil inválido")

    now = _now_iso()
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        if role is not None:
            cur = conn.execute(
                "UPDATE app_users SET plan=?, plan_status=?, role=?, updated_at=? WHERE id=?",
                (plan, plan_status, role, now, user_id),
            )
        else:
            cur = conn.execute(
                "UPDATE app_users SET plan=?, plan_status=?, updated_at=? WHERE id=?",
                (plan, plan_status, now, user_id),
            )
        if cur.rowcount == 0:
            raise ValueError("usuário não encontrado")
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return get_user_by_id(db_path, user_id)


def apply_billing_event(
    db_path,
    *,
    provider: str,
    email: str,
    plan: str = "pro",
    event_type: str = "purchase_approved",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Processa evento de compra (Kiwify, Hotmart, Asaas, Stripe ou liberação manual)."""
    ensure_accounts_schema(db_path)
    clean_email = _normalize_email(email)
    target_plan = plan if plan in VALID_PLANS else "pro"
    target_status = "active" if event_type in ("purchase_approved", "subscription_active", "manual_grant") else "canceled"
    if event_type in ("subscription_late", "past_due"):
        target_status = "past_due"

    now = _now_iso()
    eid = str(uuid4())
    conn = connect_documents(db_path)
    updated_user_id: str | None = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO app_billing_events(id, provider, email, plan, event_type, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                eid,
                str(provider or "webhook")[:60],
                clean_email,
                target_plan,
                str(event_type)[:60],
                json.dumps(payload or {}, ensure_ascii=False)[:4000],
                now,
            ),
        )
        row = conn.execute("SELECT id FROM app_users WHERE email=?", (clean_email,)).fetchone()
        if row:
            updated_user_id = row[0]
            new_plan = target_plan if target_status == "active" else "free"
            conn.execute(
                "UPDATE app_users SET plan=?, plan_status=?, updated_at=? WHERE id=?",
                (new_plan, target_status, now, updated_user_id),
            )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "ok": True,
        "event_id": eid,
        "email": clean_email,
        "plan": target_plan,
        "plan_status": target_status,
        "user_updated": updated_user_id is not None,
    }


def list_billing_events(db_path, *, limit: int = 50) -> list[dict[str, Any]]:
    ensure_accounts_schema(db_path)
    conn = connect_documents(db_path)
    try:
        rows = conn.execute(
            "SELECT id, provider, email, plan, event_type, created_at FROM app_billing_events "
            "ORDER BY created_at DESC LIMIT ?",
            (max(1, int(limit)),),
        ).fetchall()
        keys = ("id", "provider", "email", "plan", "event_type", "created_at")
        return [dict(zip(keys, r)) for r in rows]
    finally:
        conn.close()
