"""Exportação, importação, backup e restauração dos dados **pessoais** de estudo (Fase 22).

- Exporta apenas os registros pessoais do módulo de estudos (disciplinas, tópicos, progresso,
  sessões, revisões e perfil), num JSON **versionado** e validável. Não exporta o acervo
  documental de concursos.
- A importação valida antes de gravar, faz **prévia** (dry-run), não duplica, **preserva** os
  dados existentes por padrão e informa conflitos em vez de escolher em silêncio.
- O backup usa a API de backup do SQLite (consistente, sem copiar arquivo ativo) e verifica a
  integridade.

Nada aqui vai para o Git nem é enviado a serviços externos.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from radar import study
from radar.document_store import connect_documents

FORMAT = "radar-estudos"
FORMAT_VERSION = 1
SCHEMA_EXPORT_VERSION = 11

# Entidades exportadas e a ordem de importação (respeita dependências de FK).
_ENTITIES = ("disciplinas", "topicos", "progresso", "sessoes", "revisoes", "perfil")
_IMPORT_ORDER = ("disciplinas", "topicos", "progresso", "revisoes", "sessoes", "perfil")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rows(conn, sql, keys):
    return [dict(zip(keys, row)) for row in conn.execute(sql).fetchall()]


# --- Exportação --------------------------------------------------------------

def export_study_data(db_path) -> dict:
    """Exporta os dados pessoais de estudo num JSON versionado e validável."""
    conn = connect_documents(db_path)
    try:
        schema = conn.execute("PRAGMA user_version").fetchone()[0]
        data = {
            "disciplinas": _rows(conn, "SELECT id,nome,created_at FROM estudo_disciplinas",
                                 ("id", "nome", "created_at")),
            "topicos": _rows(conn, "SELECT id,disciplina_id,parent_id,nome,created_at FROM estudo_topicos",
                             ("id", "disciplina_id", "parent_id", "nome", "created_at")),
            "progresso": _rows(conn, "SELECT id,contest_id,topico_id,state,data_conclusao,adiamentos,"
                                     "created_at,updated_at FROM estudo_progresso",
                               ("id", "contest_id", "topico_id", "state", "data_conclusao",
                                "adiamentos", "created_at", "updated_at")),
            "sessoes": _rows(conn, "SELECT id,disciplina_id,topico_id,contest_id,inicio,fim,"
                                   "duracao_segundos,estado,modo,notas,created_at FROM estudo_sessoes",
                             ("id", "disciplina_id", "topico_id", "contest_id", "inicio", "fim",
                              "duracao_segundos", "estado", "modo", "notas", "created_at")),
            "revisoes": _rows(conn, "SELECT id,progresso_id,agendada_para,feita_em,resultado,created_at "
                                    "FROM estudo_revisoes",
                              ("id", "progresso_id", "agendada_para", "feita_em", "resultado", "created_at")),
            "perfil": _rows(conn, "SELECT id,conceito_key,disciplina,rotulo,nivel,revisar,confianca,"
                                  "observacoes,origem,created_at,updated_at FROM estudo_perfil",
                            ("id", "conceito_key", "disciplina", "rotulo", "nivel", "revisar",
                             "confianca", "observacoes", "origem", "created_at", "updated_at")),
        }
    finally:
        conn.close()
    counts = {name: len(data[name]) for name in _ENTITIES}
    return {"format": FORMAT, "format_version": FORMAT_VERSION, "exported_at": _now(),
            "schema_version": schema, "counts": counts, "data": data}


_REQUIRED = {
    "disciplinas": ("id", "nome"),
    "topicos": ("id", "disciplina_id", "nome"),
    "progresso": ("id", "topico_id", "state"),
    "sessoes": ("id", "estado"),
    "revisoes": ("id", "progresso_id", "agendada_para"),
    "perfil": ("id", "conceito_key", "rotulo", "nivel"),
}


def validate_export(payload) -> list[str]:
    """Valida a estrutura de um arquivo exportado; devolve a lista de erros (vazia = válido)."""
    errors = []
    if not isinstance(payload, dict):
        return ["arquivo não é um objeto JSON"]
    if payload.get("format") != FORMAT:
        errors.append(f"formato inesperado: {payload.get('format')!r}")
    version = payload.get("format_version")
    if not isinstance(version, int) or version < 1:
        errors.append("format_version ausente ou inválido")
    elif version > FORMAT_VERSION:
        errors.append(f"format_version {version} mais novo que o suportado ({FORMAT_VERSION})")
    data = payload.get("data")
    if not isinstance(data, dict):
        return errors + ["campo 'data' ausente ou inválido"]
    for name in _ENTITIES:
        if name not in data or not isinstance(data[name], list):
            errors.append(f"entidade '{name}' ausente ou inválida")
    for name in _ENTITIES:
        for item in data.get(name, []) or []:
            if not isinstance(item, dict):
                errors.append(f"{name}: item não é objeto")
                continue
            missing = [field for field in _REQUIRED[name] if not item.get(field)]
            if missing:
                errors.append(f"{name}: item sem campo(s) obrigatório(s): {', '.join(missing)}")
    return errors


# --- Importação --------------------------------------------------------------

def import_study_data(db_path, payload, *, dry_run: bool = False) -> dict:
    """Importa dados pessoais de estudo com prévia, deduplicação e relatório de conflitos.

    - Valida o arquivo antes de gravar.
    - Idempotente: reimportar o mesmo arquivo não duplica.
    - **Preserva** os registros existentes por padrão; conflitos são relatados, não sobrescritos.
    - Sessões abertas (`em_andamento`/`pausada`) são **finalizadas** na importação (o tempo
      estudado é preservado; evita duas sessões abertas simultâneas).
    """
    errors = validate_export(payload)
    if errors:
        return {"ok": False, "errors": errors, "created": 0, "updated": 0, "skipped": 0,
                "conflicts": [], "dry_run": dry_run}
    data = payload["data"]
    report = {"ok": True, "errors": [], "created": 0, "updated": 0, "skipped": 0,
              "conflicts": [], "dry_run": dry_run, "by_entity": {}}
    conn = connect_documents(db_path)
    try:
        if not dry_run:
            conn.execute("BEGIN IMMEDIATE")
        _import_disciplinas(conn, data, report, dry_run)
        _import_topicos(conn, data, report, dry_run)
        _import_progresso(conn, data, report, dry_run)
        _import_revisoes(conn, data, report, dry_run)
        _import_sessoes(conn, data, report, dry_run)
        _import_perfil(conn, data, report, dry_run)
        if not dry_run:
            conn.commit()
    except BaseException:
        if not dry_run:
            conn.rollback()
        raise
    finally:
        conn.close()
    return report


def _bump(report, entity, kind):
    report["by_entity"].setdefault(entity, {"created": 0, "updated": 0, "skipped": 0})
    report["by_entity"][entity][kind] += 1
    report[kind] += 1


def _import_disciplinas(conn, data, report, dry_run):
    for item in data.get("disciplinas", []):
        exists = conn.execute("SELECT 1 FROM estudo_disciplinas WHERE id=?", (item["id"],)).fetchone()
        if exists:
            _bump(report, "disciplinas", "skipped")
        else:
            if not dry_run:
                conn.execute("INSERT INTO estudo_disciplinas(id,nome,created_at) VALUES(?,?,?)",
                             (item["id"], item["nome"], item.get("created_at") or _now()))
            _bump(report, "disciplinas", "created")


def _import_topicos(conn, data, report, dry_run):
    imported = {row[0] for row in conn.execute("SELECT id FROM estudo_topicos")}
    imported |= {i["id"] for i in data.get("topicos", []) if isinstance(i, dict) and i.get("id")}
    for item in data.get("topicos", []):
        if not conn.execute("SELECT 1 FROM estudo_disciplinas WHERE id=?",
                            (item.get("disciplina_id"),)).fetchone():
            report["conflicts"].append({"entity": "topicos", "id": item.get("id"),
                                        "reason": "disciplina de origem ausente"})
            continue
        if item.get("parent_id") and item["parent_id"] not in imported:
            # Tópico-pai ausente no destino: importa na raiz (não aborta a importação).
            report["conflicts"].append({"entity": "topicos", "id": item.get("id"),
                                        "reason": "tópico-pai ausente; importado na raiz"})
            item = {**item, "parent_id": None}
        if conn.execute("SELECT 1 FROM estudo_topicos WHERE id=?", (item["id"],)).fetchone():
            _bump(report, "topicos", "skipped")
            continue
        if not dry_run:
            conn.execute("INSERT INTO estudo_topicos(id,disciplina_id,parent_id,nome,created_at) "
                         "VALUES(?,?,?,?,?)",
                         (item["id"], item["disciplina_id"], item.get("parent_id"), item["nome"],
                          item.get("created_at") or _now()))
        _bump(report, "topicos", "created")


def _import_progresso(conn, data, report, dry_run):
    for item in data.get("progresso", []):
        if not conn.execute("SELECT 1 FROM estudo_topicos WHERE id=?", (item.get("topico_id"),)).fetchone():
            report["conflicts"].append({"entity": "progresso", "id": item.get("id"),
                                        "reason": "tópico de origem ausente"})
            continue
        existing = conn.execute("SELECT id,state FROM estudo_progresso WHERE contest_id=? AND topico_id=?",
                                (item.get("contest_id", ""), item["topico_id"])).fetchone()
        if existing:
            if existing[1] != item.get("state"):
                report["conflicts"].append({"entity": "progresso", "id": item.get("id"),
                                            "reason": "progresso local difere; preservado o local"})
            _bump(report, "progresso", "skipped")
            continue
        if not dry_run:
            conn.execute("INSERT INTO estudo_progresso(id,contest_id,topico_id,state,data_conclusao,"
                         "adiamentos,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                         (item["id"], item.get("contest_id", ""), item["topico_id"], item["state"],
                          item.get("data_conclusao"), item.get("adiamentos", 0),
                          item.get("created_at") or _now(), item.get("updated_at") or _now()))
        _bump(report, "progresso", "created")


def _import_revisoes(conn, data, report, dry_run):
    for item in data.get("revisoes", []):
        if not conn.execute("SELECT 1 FROM estudo_progresso WHERE id=?",
                            (item.get("progresso_id"),)).fetchone():
            report["conflicts"].append({"entity": "revisoes", "id": item.get("id"),
                                        "reason": "progresso de origem ausente"})
            continue
        if conn.execute("SELECT 1 FROM estudo_revisoes WHERE id=?", (item["id"],)).fetchone():
            _bump(report, "revisoes", "skipped")
            continue
        if not dry_run:
            conn.execute("INSERT INTO estudo_revisoes(id,progresso_id,agendada_para,feita_em,resultado,"
                         "created_at) VALUES(?,?,?,?,?,?)",
                         (item["id"], item["progresso_id"], item["agendada_para"], item.get("feita_em"),
                          item.get("resultado"), item.get("created_at") or _now()))
        _bump(report, "revisoes", "created")


def _import_sessoes(conn, data, report, dry_run):
    for item in data.get("sessoes", []):
        if conn.execute("SELECT 1 FROM estudo_sessoes WHERE id=?", (item["id"],)).fetchone():
            _bump(report, "sessoes", "skipped")
            continue
        disciplina_id = item.get("disciplina_id")
        topico_id = item.get("topico_id")
        # FKs ausentes no destino viram nulo (preserva a sessão e o tempo), com aviso.
        if disciplina_id and not conn.execute("SELECT 1 FROM estudo_disciplinas WHERE id=?",
                                              (disciplina_id,)).fetchone():
            report["conflicts"].append({"entity": "sessoes", "id": item.get("id"),
                                        "reason": "disciplina de origem ausente; sessão sem vínculo"})
            disciplina_id = None
        if topico_id and not conn.execute("SELECT 1 FROM estudo_topicos WHERE id=?",
                                          (topico_id,)).fetchone():
            report["conflicts"].append({"entity": "sessoes", "id": item.get("id"),
                                        "reason": "tópico de origem ausente; sessão sem vínculo"})
            topico_id = None
        estado = item.get("estado")
        duracao = item.get("duracao_segundos", 0) or 0
        fim = item.get("fim")
        if estado in ("em_andamento", "pausada"):
            # Finaliza na importação **materializando** o tempo estudado (não perde a duração)
            # e evita duas sessões abertas simultâneas.
            duracao = study.capped_elapsed(item)
            fim = fim or _now()
            estado = "concluida"
            report["conflicts"].append({"entity": "sessoes", "id": item.get("id"),
                                        "reason": "sessão aberta finalizada na importação"})
        if not dry_run:
            conn.execute("INSERT INTO estudo_sessoes(id,disciplina_id,topico_id,contest_id,inicio,fim,"
                         "duracao_segundos,estado,modo,notas,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                         (item["id"], disciplina_id, topico_id, item.get("contest_id", ""),
                          item.get("inicio"), fim, duracao, estado, item.get("modo", "livre"),
                          item.get("notas"), item.get("created_at") or _now()))
        _bump(report, "sessoes", "created")


def _import_perfil(conn, data, report, dry_run):
    for item in data.get("perfil", []):
        existing = conn.execute("SELECT id FROM estudo_perfil WHERE conceito_key=?",
                                (item.get("conceito_key"),)).fetchone()
        if existing:
            _bump(report, "perfil", "skipped")
            continue
        if not dry_run:
            conn.execute("INSERT INTO estudo_perfil(id,conceito_key,disciplina,rotulo,nivel,revisar,"
                         "confianca,observacoes,origem,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                         (item["id"], item["conceito_key"], item.get("disciplina"), item["rotulo"],
                          item["nivel"], 1 if item.get("revisar") else 0, item.get("confianca"),
                          item.get("observacoes"), item.get("origem") or "usuario",
                          item.get("created_at") or _now(), item.get("updated_at") or _now()))
        _bump(report, "perfil", "created")


# --- Backup e restauração (SQLite consistente) -------------------------------

def _table_counts(db_path) -> dict:
    conn = connect_documents(db_path)
    try:
        present = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        counts = {}
        for name in ("disciplinas", "topicos", "progresso", "sessoes", "revisoes", "perfil"):
            table = f"estudo_{name}"
            counts[name] = (conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                            if table in present else 0)
        return counts
    finally:
        conn.close()


def backup_database(db_path, dest_path) -> dict:
    """Backup **consistente** do banco via API do SQLite, com verificação de integridade.

    Recusa sobrescrever o próprio banco de origem (o destino deve ser uma cópia separada).
    """
    dest = Path(dest_path)
    if dest.resolve() == Path(db_path).resolve():
        raise ValueError("o destino do backup não pode ser o próprio banco de origem")
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = connect_documents(db_path)
    try:
        target = sqlite3.connect(str(dest))
        try:
            source.backup(target)  # cópia consistente (respeita transações/journaling)
        finally:
            target.close()
    finally:
        source.close()
    integrity = _integrity(dest)
    return {"backup_path": str(dest), "integrity": integrity,
            "counts": _table_counts(dest) if integrity == "ok" else {}}


def _integrity(db_path) -> str:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()


def restore_database(backup_path, dest_path) -> dict:
    """Restaura um backup para um banco de destino (isolado), verificando integridade."""
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(str(backup_path))
    try:
        target = connect_documents(dest)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()
    integrity = _integrity(dest)
    return {"restored_to": str(dest), "integrity": integrity,
            "counts": _table_counts(dest) if integrity == "ok" else {}}
