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
FORMAT_VERSION = 2  # v2 acrescenta prática (flashcards/questões/simulados); v1 continua importável
SCHEMA_EXPORT_VERSION = 11

# Entidades exportadas e a ordem de importação (respeita dependências de FK).
_CORE_ENTITIES = ("disciplinas", "topicos", "progresso", "sessoes", "revisoes", "perfil")
# Entidades de prática (v2). Opcionais na importação: um arquivo v1 não as possui.
_PRACTICE_ENTITIES = ("flashcards", "flashcard_revisoes", "questoes", "questao_versoes",
                      "tentativas", "simulados", "simulado_questoes")
_ENTITIES = _CORE_ENTITIES + _PRACTICE_ENTITIES
_IMPORT_ORDER = ("disciplinas", "topicos", "progresso", "revisoes", "sessoes", "perfil",
                  "flashcards", "flashcard_revisoes", "questoes", "questao_versoes",
                  "tentativas", "simulados", "simulado_questoes")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rows(conn, sql, keys):
    return [dict(zip(keys, row)) for row in conn.execute(sql).fetchall()]


# --- Exportação --------------------------------------------------------------

def export_study_data(db_path) -> dict:
    """Exporta os dados pessoais de estudo num JSON versionado e validável.

    Tolerante a banco ainda **v11** (sem as tabelas de prática): exporta só o núcleo de
    estudo em vez de falhar.
    """
    conn = connect_documents(db_path)
    try:
        schema = conn.execute("PRAGMA user_version").fetchone()[0]
        present = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
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
            # --- Prática (v2) ---
            "flashcards": _rows(conn, "SELECT id,disciplina_id,topico_id,contest_id,conceito_key,"
                                      "frente,verso,tags,fonte,licenca,estado,ease,intervalo,"
                                      "repeticoes,proxima_revisao,ultima_revisao,revisoes,"
                                      "created_at,updated_at FROM pratica_flashcards",
                                ("id", "disciplina_id", "topico_id", "contest_id", "conceito_key",
                                 "frente", "verso", "tags", "fonte", "licenca", "estado", "ease",
                                 "intervalo", "repeticoes", "proxima_revisao", "ultima_revisao",
                                 "revisoes", "created_at", "updated_at")),
            "flashcard_revisoes": _rows(conn, "SELECT id,flashcard_id,qualidade,ease,intervalo,"
                                              "repeticoes,revisado_em,proxima_revisao "
                                              "FROM pratica_flashcard_revisoes",
                                        ("id", "flashcard_id", "qualidade", "ease", "intervalo",
                                         "repeticoes", "revisado_em", "proxima_revisao")),
            "questoes": _rows(conn, "SELECT id,versao,disciplina,topico,conceito_key,enunciado,"
                                    "alternativas_json,gabarito,comentario,dificuldade,tags,fonte,"
                                    "licenca,procedencia,estado,created_at,updated_at "
                                    "FROM pratica_questoes",
                              ("id", "versao", "disciplina", "topico", "conceito_key", "enunciado",
                               "alternativas_json", "gabarito", "comentario", "dificuldade", "tags",
                               "fonte", "licenca", "procedencia", "estado", "created_at", "updated_at")),
            "questao_versoes": _rows(conn, "SELECT id,questao_id,versao,enunciado,alternativas_json,"
                                           "gabarito,comentario,registrado_em "
                                           "FROM pratica_questao_versoes",
                                     ("id", "questao_id", "versao", "enunciado", "alternativas_json",
                                      "gabarito", "comentario", "registrado_em")),
            "tentativas": _rows(conn, "SELECT id,questao_id,questao_versao,resposta,correta,respondida,"
                                      "duracao_segundos,origem,simulado_id,disciplina,topico,"
                                      "conceito_key,created_at FROM pratica_tentativas",
                                ("id", "questao_id", "questao_versao", "resposta", "correta",
                                 "respondida", "duracao_segundos", "origem", "simulado_id",
                                 "disciplina", "topico", "conceito_key", "created_at")),
            "simulados": _rows(conn, "SELECT id,nome,duracao_segundos,iniciado_em,finalizado_em,"
                                     "estado,created_at FROM pratica_simulados",
                               ("id", "nome", "duracao_segundos", "iniciado_em", "finalizado_em",
                                "estado", "created_at")),
            "simulado_questoes": _rows(conn, "SELECT simulado_id,ordem,questao_id,questao_versao,"
                                             "resposta,respondida_em FROM pratica_simulado_questoes",
                                       ("simulado_id", "ordem", "questao_id", "questao_versao",
                                        "resposta", "respondida_em")),
        }
    finally:
        conn.close()
    if 'pratica_flashcards' not in present:
        # Banco v11: sem tabelas de prática, exporta apenas o núcleo (formato v2, listas vazias).
        for name in _PRACTICE_ENTITIES:
            data[name] = []
    counts = {name: len(data.get(name) or []) for name in _ENTITIES}
    return {"format": FORMAT, "format_version": FORMAT_VERSION, "exported_at": _now(),
            "schema_version": schema, "counts": counts, "data": data}


_REQUIRED = {
    "disciplinas": ("id", "nome"),
    "topicos": ("id", "disciplina_id", "nome"),
    "progresso": ("id", "topico_id", "state"),
    "sessoes": ("id", "estado"),
    "revisoes": ("id", "progresso_id", "agendada_para"),
    "perfil": ("id", "conceito_key", "rotulo", "nivel"),
    # Prática (v2)
    "flashcards": ("id", "frente", "verso"),
    "flashcard_revisoes": ("id", "flashcard_id", "qualidade"),
    "questoes": ("id", "enunciado", "gabarito"),
    "questao_versoes": ("id", "questao_id", "versao", "enunciado", "gabarito"),
    "tentativas": ("id", "questao_id", "questao_versao", "origem"),
    "simulados": ("id", "nome", "estado"),
    "simulado_questoes": ("simulado_id", "ordem", "questao_id", "questao_versao"),
}


_ENUMS = {
    ("flashcards", "estado"): {"ativo", "arquivado"},
    ("questoes", "estado"): {"ativo", "arquivado"},
    ("tentativas", "origem"): {"pratica", "simulado"},
    ("simulados", "estado"): {"em_andamento", "finalizado", "expirado"},
}


def validate_export(payload) -> list[str]:
    """Valida a estrutura e os **domínios** de um arquivo exportado.

    Compatível com **v1** (só entidades de estudo) e **v2** (acrescenta prática). As entidades
    de prática são opcionais: um arquivo v1 continua importável sem alteração.
    """
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
    # Entidades de estudo são obrigatórias em qualquer versão.
    for name in _CORE_ENTITIES:
        if name not in data or not isinstance(data[name], list):
            errors.append(f"entidade '{name}' ausente ou inválida")
    # Entidades de prática são opcionais, mas se presentes precisam ser listas válidas.
    for name in _PRACTICE_ENTITIES:
        if name in data and not isinstance(data[name], list):
            errors.append(f"entidade '{name}' inválida")
    for name in _ENTITIES:
        for item in data.get(name, []) or []:
            if not isinstance(item, dict):
                errors.append(f"{name}: item não é objeto")
                continue
            missing = [field for field in _REQUIRED[name]
                       if field not in item or item[field] is None or item[field] == ""]
            if missing:
                errors.append(f"{name}: item sem campo(s) obrigatório(s): {', '.join(missing)}")
                continue
            for (entity, field), allowed in _ENUMS.items():
                if entity == name and field in item and item[field] not in allowed:
                    errors.append(f"{name}: {field} inválido: {item[field]!r}")
            if name == "flashcard_revisoes":
                quality = item.get("qualidade")
                if not isinstance(quality, int) or isinstance(quality, bool) or not 0 <= quality <= 5:
                    errors.append("flashcard_revisoes: qualidade fora de 0..5")
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
        _import_practice(conn, data, report, dry_run)
        if not dry_run:
            conn.commit()
    except sqlite3.IntegrityError as error:
        # Violação de integridade é problema do **arquivo**, não de migração: rollback e
        # relatório de erro (nunca 503 "migração pendente").
        if not dry_run:
            conn.rollback()
        report["ok"] = False
        report["errors"].append(f"violação de integridade nos dados importados: {error}")
        report["created"] = report["updated"] = 0
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

def _import_practice(conn, data, report, dry_run):
    """Importa a prática (v2): flashcards, questões/versões, simulados e tentativas.

    Idempotente por id; FKs ausentes viram conflito (não abortam). Questões e alternativas
    são importadas **como registradas** (o conteúdo é do próprio usuário).
    """
    _import_flashcards(conn, data, report, dry_run)
    _import_questions(conn, data, report, dry_run)
    _import_exams(conn, data, report, dry_run)
    _import_attempts(conn, data, report, dry_run)


def _import_flashcards(conn, data, report, dry_run):
    for item in data.get("flashcards", []) or []:
        if conn.execute("SELECT 1 FROM pratica_flashcards WHERE id=?", (item["id"],)).fetchone():
            _bump(report, "flashcards", "skipped")
            continue
        disciplina_id, topico_id = item.get("disciplina_id"), item.get("topico_id")
        if disciplina_id and not conn.execute("SELECT 1 FROM estudo_disciplinas WHERE id=?",
                                              (disciplina_id,)).fetchone():
            report["conflicts"].append({"entity": "flashcards", "id": item["id"],
                                        "reason": "disciplina de origem ausente; cartão sem vínculo"})
            disciplina_id = None
        if topico_id and not conn.execute("SELECT 1 FROM estudo_topicos WHERE id=?",
                                          (topico_id,)).fetchone():
            report["conflicts"].append({"entity": "flashcards", "id": item["id"],
                                        "reason": "tópico de origem ausente; cartão sem vínculo"})
            topico_id = None
        if not dry_run:
            conn.execute(
                "INSERT INTO pratica_flashcards(id,disciplina_id,topico_id,contest_id,conceito_key,"
                "frente,verso,tags,fonte,licenca,estado,ease,intervalo,repeticoes,proxima_revisao,"
                "ultima_revisao,revisoes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (item["id"], disciplina_id, topico_id, item.get("contest_id") or "",
                 item.get("conceito_key"), item["frente"], item["verso"], item.get("tags"),
                 item.get("fonte"), item.get("licenca"), item.get("estado") or "ativo",
                 float(item.get("ease") or 2.5), int(item.get("intervalo") or 0),
                 int(item.get("repeticoes") or 0), item.get("proxima_revisao"),
                 item.get("ultima_revisao"), int(item.get("revisoes") or 0),
                 item.get("created_at") or _now(), item.get("updated_at") or _now()))
        _bump(report, "flashcards", "created")
    for item in data.get("flashcard_revisoes", []) or []:
        if not conn.execute("SELECT 1 FROM pratica_flashcards WHERE id=?",
                            (item.get("flashcard_id"),)).fetchone():
            report["conflicts"].append({"entity": "flashcard_revisoes", "id": item.get("id"),
                                        "reason": "cartão de origem ausente"})
            continue
        if conn.execute("SELECT 1 FROM pratica_flashcard_revisoes WHERE id=?", (item["id"],)).fetchone():
            _bump(report, "flashcard_revisoes", "skipped")
            continue
        if not dry_run:
            conn.execute(
                "INSERT INTO pratica_flashcard_revisoes(id,flashcard_id,qualidade,ease,intervalo,"
                "repeticoes,revisado_em,proxima_revisao) VALUES(?,?,?,?,?,?,?,?)",
                (item["id"], item["flashcard_id"], int(item["qualidade"]),
                 float(item.get("ease") or 2.5), int(item.get("intervalo") or 0),
                 int(item.get("repeticoes") or 0), item.get("revisado_em") or _now(),
                 item.get("proxima_revisao") or _now()[:10]))
        _bump(report, "flashcard_revisoes", "created")


def _import_questions(conn, data, report, dry_run):
    for item in data.get("questoes", []) or []:
        if conn.execute("SELECT 1 FROM pratica_questoes WHERE id=?", (item["id"],)).fetchone():
            _bump(report, "questoes", "skipped")
            continue
        if not dry_run:
            conn.execute(
                "INSERT INTO pratica_questoes(id,versao,disciplina,topico,conceito_key,enunciado,"
                "alternativas_json,gabarito,comentario,dificuldade,tags,fonte,licenca,procedencia,"
                "estado,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (item["id"], int(item.get("versao") or 1), item.get("disciplina"), item.get("topico"),
                 item.get("conceito_key"), item["enunciado"],
                 item.get("alternativas_json") or "[]", item["gabarito"], item.get("comentario"),
                 item.get("dificuldade"), item.get("tags"), item.get("fonte"), item.get("licenca"),
                 item.get("procedencia"), item.get("estado") or "ativo",
                 item.get("created_at") or _now(), item.get("updated_at") or _now()))
        _bump(report, "questoes", "created")
    # Versões: a chave real é (questao_id, versao) — o `UNIQUE` do schema. Inserir pelo id da
    # linha corromperia a cadeia (a próxima edição colidiria) ou abortaria a importação.
    for item in data.get("questao_versoes", []) or []:
        if not conn.execute("SELECT 1 FROM pratica_questoes WHERE id=?",
                            (item.get("questao_id"),)).fetchone():
            report["conflicts"].append({"entity": "questao_versoes", "id": item.get("id"),
                                        "reason": "questão de origem ausente"})
            continue
        existing = conn.execute(
            "SELECT id,enunciado,gabarito FROM pratica_questao_versoes WHERE questao_id=? AND versao=?",
            (item["questao_id"], int(item["versao"]))).fetchone()
        if existing:
            if existing[1] != item.get("enunciado") or existing[2] != item.get("gabarito"):
                report["conflicts"].append({
                    "entity": "questao_versoes", "id": item.get("id"),
                    "reason": "versão já existe com conteúdo divergente; preservado o local"})
            _bump(report, "questao_versoes", "skipped")
            continue
        if not dry_run:
            conn.execute(
                "INSERT INTO pratica_questao_versoes(id,questao_id,versao,enunciado,"
                "alternativas_json,gabarito,comentario,registrado_em) VALUES(?,?,?,?,?,?,?,?)",
                (item["id"], item["questao_id"], int(item["versao"]), item["enunciado"],
                 item.get("alternativas_json") or "[]", item["gabarito"], item.get("comentario"),
                 item.get("registrado_em") or _now()))
        _bump(report, "questao_versoes", "created")
    # Reconcilia `pratica_questoes.versao` com a maior versão existente (nunca reduz).
    if not dry_run:
        conn.execute(
            "UPDATE pratica_questoes SET versao = ("
            "  SELECT MAX(v.versao) FROM pratica_questao_versoes v WHERE v.questao_id = pratica_questoes.id"
            ") WHERE versao < ("
            "  SELECT MAX(v.versao) FROM pratica_questao_versoes v WHERE v.questao_id = pratica_questoes.id"
            ")")


def _import_exams(conn, data, report, dry_run):
    for item in data.get("simulados", []) or []:
        if conn.execute("SELECT 1 FROM pratica_simulados WHERE id=?", (item["id"],)).fetchone():
            _bump(report, "simulados", "skipped")
            continue
        estado = item.get("estado") or "em_andamento"
        # Um simulado em andamento importado é finalizado: não se retoma prova de outra origem.
        if estado == "em_andamento":
            estado = "finalizado"
            report["conflicts"].append({"entity": "simulados", "id": item.get("id"),
                                        "reason": "simulado em andamento finalizado na importação"})
        if not dry_run:
            conn.execute(
                "INSERT INTO pratica_simulados(id,nome,duracao_segundos,iniciado_em,finalizado_em,"
                "estado,created_at) VALUES(?,?,?,?,?,?,?)",
                (item["id"], item["nome"], item.get("duracao_segundos"),
                 item.get("iniciado_em") or _now(),
                 item.get("finalizado_em") or (_now() if estado == "finalizado" else None),
                 estado, item.get("created_at") or _now()))
        _bump(report, "simulados", "created")
    for item in data.get("simulado_questoes", []) or []:
        if not conn.execute("SELECT 1 FROM pratica_simulados WHERE id=?",
                            (item.get("simulado_id"),)).fetchone():
            report["conflicts"].append({"entity": "simulado_questoes", "id": item.get("simulado_id"),
                                        "reason": "simulado de origem ausente"})
            continue
        if not conn.execute("SELECT 1 FROM pratica_questoes WHERE id=?",
                            (item.get("questao_id"),)).fetchone():
            report["conflicts"].append({"entity": "simulado_questoes", "id": item.get("questao_id"),
                                        "reason": "questão de origem ausente"})
            continue
        if conn.execute("SELECT 1 FROM pratica_simulado_questoes WHERE simulado_id=? AND ordem=?",
                        (item["simulado_id"], int(item["ordem"]))).fetchone():
            _bump(report, "simulado_questoes", "skipped")
            continue
        if not dry_run:
            conn.execute(
                "INSERT INTO pratica_simulado_questoes(simulado_id,ordem,questao_id,questao_versao,"
                "resposta,respondida_em) VALUES(?,?,?,?,?,?)",
                (item["simulado_id"], int(item["ordem"]), item["questao_id"],
                 int(item["questao_versao"]), item.get("resposta"), item.get("respondida_em")))
        _bump(report, "simulado_questoes", "created")


def _import_attempts(conn, data, report, dry_run):
    for item in data.get("tentativas", []) or []:
        if not conn.execute("SELECT 1 FROM pratica_questoes WHERE id=?",
                            (item.get("questao_id"),)).fetchone():
            report["conflicts"].append({"entity": "tentativas", "id": item.get("id"),
                                        "reason": "questão de origem ausente"})
            continue
        if conn.execute("SELECT 1 FROM pratica_tentativas WHERE id=?", (item["id"],)).fetchone():
            _bump(report, "tentativas", "skipped")
            continue
        correta = item.get("correta")
        if not dry_run:
            conn.execute(
                "INSERT INTO pratica_tentativas(id,questao_id,questao_versao,resposta,correta,"
                "respondida,duracao_segundos,origem,simulado_id,disciplina,topico,conceito_key,"
                "created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (item["id"], item["questao_id"], int(item["questao_versao"]), item.get("resposta"),
                 None if correta is None else (1 if correta else 0),
                 int(item.get("respondida") or 0), item.get("duracao_segundos"),
                 item.get("origem") or "pratica", item.get("simulado_id"), item.get("disciplina"),
                 item.get("topico"), item.get("conceito_key"), item.get("created_at") or _now()))
        _bump(report, "tentativas", "created")


_TABLE_MAP = {
    "disciplinas": "estudo_disciplinas", "topicos": "estudo_topicos",
    "progresso": "estudo_progresso", "sessoes": "estudo_sessoes",
    "revisoes": "estudo_revisoes", "perfil": "estudo_perfil",
    "flashcards": "pratica_flashcards", "flashcard_revisoes": "pratica_flashcard_revisoes",
    "questoes": "pratica_questoes", "questao_versoes": "pratica_questao_versoes",
    "tentativas": "pratica_tentativas", "simulados": "pratica_simulados",
    "simulado_questoes": "pratica_simulado_questoes",
}


def _table_counts(db_path) -> dict:
    conn = connect_documents(db_path)
    try:
        present = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        return {name: (conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                       if table in present else 0)
                for name, table in _TABLE_MAP.items()}
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
