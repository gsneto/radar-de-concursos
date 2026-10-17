"""Persistência de flashcards, questões, tentativas e simulados (Fase 23).

Mesmo banco SQLite, tabelas `pratica_*` — **dados pessoais**, nunca expostos pelo contrato v1.
A lógica pura fica em `flashcards.py`, `questions.py` e `exams.py`; aqui só se lê/grava.

Garantias:
- Editar uma questão cria uma **nova versão** e arquiva a anterior no histórico; tentativas
  antigas continuam apontando para a versão que responderam.
- O simulado guarda a versão aplicada; a correção usa essa versão, não a atual.
- Respostas do simulado são salvas **progressivamente** (uma a uma), não só no final.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from radar import exams, flashcards, questions
from radar.document_store import connect_documents

_MAX_CONTEST_ID = 120


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value, limit=200) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split()).strip()
    return text[:limit] or None


# --- Flashcards --------------------------------------------------------------

def create_flashcard(db_path, *, frente, verso, disciplina_id=None, topico_id=None,
                     contest_id="", conceito_key=None, tags=None, fonte=None,
                     licenca=None) -> dict:
    if not _clean(frente) or not _clean(verso):
        raise ValueError("frente e verso são obrigatórios")
    contest_id = (contest_id or "")[:_MAX_CONTEST_ID]
    fid, now = str(uuid4()), _now()
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        for table, value in (("estudo_disciplinas", disciplina_id), ("estudo_topicos", topico_id)):
            if value and not conn.execute(f"SELECT 1 FROM {table} WHERE id=?", (value,)).fetchone():
                raise ValueError("referência inexistente")
        conn.execute(
            "INSERT INTO pratica_flashcards(id,disciplina_id,topico_id,contest_id,conceito_key,"
            "frente,verso,tags,fonte,licenca,estado,ease,intervalo,repeticoes,proxima_revisao,"
            "ultima_revisao,revisoes,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,'ativo',?,0,0,NULL,NULL,0,?,?)",
            (fid, disciplina_id, topico_id, contest_id, _clean(conceito_key, 300),
             _clean(frente, 4000), _clean(verso, 4000),
             json.dumps(questions.normalize_tags(tags), ensure_ascii=False),
             _clean(fonte), _clean(licenca), flashcards.DEFAULT_EASE, now, now))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return get_flashcard(db_path, fid)


def _flashcard_row(row) -> dict:
    keys = ("id", "disciplina_id", "topico_id", "contest_id", "conceito_key", "frente", "verso",
            "tags", "fonte", "licenca", "estado", "ease", "intervalo", "repeticoes",
            "proxima_revisao", "ultima_revisao", "revisoes", "created_at", "updated_at")
    card = dict(zip(keys, row))
    try:
        card["tags"] = json.loads(card.get("tags") or "[]")
    except (TypeError, ValueError):
        card["tags"] = []
    return card


_FLASHCARD_COLS = ("id,disciplina_id,topico_id,contest_id,conceito_key,frente,verso,tags,fonte,"
                   "licenca,estado,ease,intervalo,repeticoes,proxima_revisao,ultima_revisao,"
                   "revisoes,created_at,updated_at")


def get_flashcard(db_path, flashcard_id: str) -> dict | None:
    conn = connect_documents(db_path)
    try:
        row = conn.execute(f"SELECT {_FLASHCARD_COLS} FROM pratica_flashcards WHERE id=?",
                           (flashcard_id,)).fetchone()
        return _flashcard_row(row) if row else None
    finally:
        conn.close()


def list_flashcards(db_path, *, include_archived=False, disciplina_id=None) -> list[dict]:
    conn = connect_documents(db_path)
    try:
        where, params = [], []
        if not include_archived:
            where.append("estado='ativo'")
        if disciplina_id:
            where.append("disciplina_id=?")
            params.append(disciplina_id)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        rows = conn.execute(
            f"SELECT {_FLASHCARD_COLS} FROM pratica_flashcards {clause} "
            "ORDER BY created_at DESC, id", params).fetchall()
        return [_flashcard_row(row) for row in rows]
    finally:
        conn.close()


def update_flashcard(db_path, flashcard_id: str, *, frente=None, verso=None, tags=None,
                     estado=None) -> dict:
    """Edita frente/verso/tags ou arquiva. **Preserva** o histórico de revisões."""
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        if not conn.execute("SELECT 1 FROM pratica_flashcards WHERE id=?", (flashcard_id,)).fetchone():
            raise ValueError("flashcard inexistente")
        if estado is not None:
            if estado not in ("ativo", "arquivado"):
                raise ValueError("estado inválido")
            conn.execute("UPDATE pratica_flashcards SET estado=?, updated_at=? WHERE id=?",
                         (estado, _now(), flashcard_id))
        if frente is not None or verso is not None:
            row = conn.execute("SELECT frente,verso FROM pratica_flashcards WHERE id=?",
                               (flashcard_id,)).fetchone()
            new_frente = _clean(frente, 4000) if frente is not None else row[0]
            new_verso = _clean(verso, 4000) if verso is not None else row[1]
            if not new_frente or not new_verso:
                raise ValueError("frente e verso não podem ficar vazios")
            conn.execute("UPDATE pratica_flashcards SET frente=?, verso=?, updated_at=? WHERE id=?",
                         (new_frente, new_verso, _now(), flashcard_id))
        if tags is not None:
            conn.execute("UPDATE pratica_flashcards SET tags=?, updated_at=? WHERE id=?",
                         (json.dumps(questions.normalize_tags(tags), ensure_ascii=False),
                          _now(), flashcard_id))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return get_flashcard(db_path, flashcard_id)


def review_flashcard(db_path, flashcard_id: str, quality: int, *, now=None) -> dict:
    """Registra a avaliação e agenda a próxima revisão (SM-2-lite)."""
    today = flashcards.utc_today(now)
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT ease,intervalo,repeticoes,estado FROM pratica_flashcards WHERE id=?",
                           (flashcard_id,)).fetchone()
        if row is None:
            raise ValueError("flashcard inexistente")
        if row[3] != "ativo":
            raise ValueError("flashcard arquivado não pode ser revisado")
        result = flashcards.schedule_review(ease=row[0], interval=row[1], repetitions=row[2],
                                            quality=quality, today=today)
        at = _now()
        conn.execute(
            "UPDATE pratica_flashcards SET ease=?, intervalo=?, repeticoes=?, proxima_revisao=?, "
            "ultima_revisao=?, revisoes=revisoes+1, updated_at=? WHERE id=?",
            (result["ease"], result["intervalo"], result["repeticoes"],
             result["proxima_revisao"], at, at, flashcard_id))
        conn.execute(
            "INSERT INTO pratica_flashcard_revisoes(id,flashcard_id,qualidade,ease,intervalo,"
            "repeticoes,revisado_em,proxima_revisao) VALUES(?,?,?,?,?,?,?,?)",
            (str(uuid4()), flashcard_id, int(quality), result["ease"], result["intervalo"],
             result["repeticoes"], at, result["proxima_revisao"]))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return get_flashcard(db_path, flashcard_id)


def flashcard_reviews(db_path, flashcard_id: str) -> list[dict]:
    conn = connect_documents(db_path)
    try:
        rows = conn.execute(
            "SELECT id,qualidade,ease,intervalo,repeticoes,revisado_em,proxima_revisao "
            "FROM pratica_flashcard_revisoes WHERE flashcard_id=? ORDER BY revisado_em, id",
            (flashcard_id,)).fetchall()
        keys = ("id", "qualidade", "ease", "intervalo", "repeticoes", "revisado_em", "proxima_revisao")
        return [dict(zip(keys, row)) for row in rows]
    finally:
        conn.close()


def study_queue(db_path, *, limit=None, today=None) -> dict:
    """Fila de estudo: novos primeiro, depois vencidos (dados persistidos)."""
    cards = list_flashcards(db_path)
    return flashcards.queue(cards, today=today, limit=limit)


def flashcard_stats(db_path, *, today=None) -> dict:
    cards = list_flashcards(db_path, include_archived=True)
    conn = connect_documents(db_path)
    try:
        rows = conn.execute(
            "SELECT qualidade FROM pratica_flashcard_revisoes").fetchall()
    finally:
        conn.close()
    return flashcards.stats(cards, [{"qualidade": r[0]} for r in rows], today=today)


# --- Questões ----------------------------------------------------------------

_QUESTION_COLS = ("id,versao,tipo,disciplina,topico,conceito_key,enunciado,alternativas_json,"
                  "gabarito,comentario,dificuldade,tags,fonte,licenca,procedencia,estado,"
                  "created_at,updated_at")


def _question_row(row) -> dict:
    keys = _QUESTION_COLS.split(",")
    item = dict(zip(keys, row))
    item["alternativas"] = questions.parse_alternatives(item.pop("alternativas_json"))
    try:
        item["tags"] = json.loads(item.get("tags") or "[]")
    except (TypeError, ValueError):
        item["tags"] = []
    return item


def create_question(db_path, **kwargs) -> dict:
    """Cria uma questão validada (escolha única ou V/F) e registra a versão 1."""
    conceito_key = _clean(kwargs.pop("conceito_key", None), 300)
    procedencia = _clean(kwargs.pop("procedencia", None), 500)
    normalized = questions.validate_question(**kwargs)
    qid, now = str(uuid4()), _now()
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO pratica_questoes(id,versao,tipo,disciplina,topico,conceito_key,enunciado,"
            "alternativas_json,gabarito,comentario,dificuldade,tags,fonte,licenca,procedencia,"
            "estado,created_at,updated_at) VALUES(?,1,?,?,?,?,?,?,?,?,?,?,?,?,?,'ativo',?,?)",
            (qid, normalized["tipo"], normalized["disciplina"], normalized["topico"], conceito_key,
             normalized["enunciado"],
             questions.alternatives_json(normalized["alternativas"]), normalized["gabarito"],
             normalized["comentario"], normalized["dificuldade"],
             json.dumps(normalized["tags"], ensure_ascii=False), normalized["fonte"],
             normalized["licenca"], procedencia, now, now))
        _record_question_version(conn, qid, 1, normalized, now)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return get_question(db_path, qid)


def _record_question_version(conn, qid, versao, normalized, at):
    conn.execute(
        "INSERT INTO pratica_questao_versoes(id,questao_id,versao,enunciado,alternativas_json,"
        "gabarito,comentario,registrado_em) VALUES(?,?,?,?,?,?,?,?)",
        (str(uuid4()), qid, int(versao), normalized["enunciado"],
         questions.alternatives_json(normalized["alternativas"]), normalized["gabarito"],
         normalized["comentario"], at))


def get_question(db_path, question_id: str) -> dict | None:
    conn = connect_documents(db_path)
    try:
        row = conn.execute(f"SELECT {_QUESTION_COLS} FROM pratica_questoes WHERE id=?",
                           (question_id,)).fetchone()
        return _question_row(row) if row else None
    finally:
        conn.close()


def list_questions(db_path, *, include_archived=False, disciplina=None, topico=None,
                   include_answer_key=False) -> list[dict]:
    """Lista questões. Por padrão **sem** gabarito/comentário (não vaza a resposta na prática).

    ``answer_question`` devolve o gabarito após a tentativa; ``exam_result`` o devolve ao final
    do simulado.
    """
    conn = connect_documents(db_path)
    try:
        where, params = [], []
        if not include_archived:
            where.append("estado='ativo'")
        if disciplina:
            where.append("disciplina=?")
            params.append(disciplina)
        if topico:
            where.append("topico=?")
            params.append(topico)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        rows = conn.execute(f"SELECT {_QUESTION_COLS} FROM pratica_questoes {clause} "
                            "ORDER BY created_at DESC, id", params).fetchall()
        items = [_question_row(row) for row in rows]
        if not include_answer_key:
            for item in items:
                item.pop("gabarito", None)
                item.pop("comentario", None)
        return items
    finally:
        conn.close()


def update_question(db_path, question_id: str, **kwargs) -> dict:
    """Edita uma questão criando **nova versão** (o histórico de tentativas é preservado)."""
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(f"SELECT {_QUESTION_COLS} FROM pratica_questoes WHERE id=?",
                           (question_id,)).fetchone()
        if row is None:
            raise ValueError("questão inexistente")
        current = _question_row(row)
        merged = {
            "enunciado": kwargs.get("enunciado", current["enunciado"]),
            "alternativas": kwargs.get("alternativas", current["alternativas"]),
            "gabarito": kwargs.get("gabarito", current["gabarito"]),
            "tipo": kwargs.get("tipo", "escolha_unica"),
            "comentario": kwargs.get("comentario", current["comentario"]),
            "disciplina": kwargs.get("disciplina", current["disciplina"]),
            "topico": kwargs.get("topico", current["topico"]),
            "dificuldade": kwargs.get("dificuldade", current["dificuldade"]),
            "tags": kwargs.get("tags", current["tags"]),
            "fonte": kwargs.get("fonte", current["fonte"]),
            "licenca": kwargs.get("licenca", current["licenca"]),
        }
        normalized = questions.validate_question(**merged)
        new_version = int(current["versao"]) + 1
        now = _now()
        conn.execute(
            "UPDATE pratica_questoes SET versao=?, tipo=?, disciplina=?, topico=?, enunciado=?, "
            "alternativas_json=?, gabarito=?, comentario=?, dificuldade=?, tags=?, fonte=?, "
            "licenca=?, updated_at=? WHERE id=?",
            (new_version, normalized["tipo"], normalized["disciplina"], normalized["topico"],
             normalized["enunciado"],
             questions.alternatives_json(normalized["alternativas"]), normalized["gabarito"],
             normalized["comentario"], normalized["dificuldade"],
             json.dumps(normalized["tags"], ensure_ascii=False), normalized["fonte"],
             normalized["licenca"], now, question_id))
        _record_question_version(conn, question_id, new_version, normalized, now)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return get_question(db_path, question_id)


def archive_question(db_path, question_id: str) -> dict:
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute("UPDATE pratica_questoes SET estado='arquivado', updated_at=? WHERE id=?",
                           (_now(), question_id))
        conn.commit()
        if cur.rowcount == 0:
            raise ValueError("questão inexistente")
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return get_question(db_path, question_id)


def question_version(db_path, question_id: str, versao: int) -> dict | None:
    conn = connect_documents(db_path)
    try:
        row = conn.execute(
            "SELECT enunciado,alternativas_json,gabarito,comentario FROM pratica_questao_versoes "
            "WHERE questao_id=? AND versao=?", (question_id, int(versao))).fetchone()
        if row is None:
            return None
        return {"enunciado": row[0], "alternativas": questions.parse_alternatives(row[1]),
                "gabarito": row[2], "comentario": row[3]}
    finally:
        conn.close()


def answer_question(db_path, question_id: str, resposta, *, duracao_segundos=None,
                    origem="pratica", simulado_id=None, now=None) -> dict:
    """Registra uma tentativa de prática (correção imediata) com a **versão** respondida."""
    if origem not in ("pratica", "simulado"):
        raise ValueError("origem inválida")
    question = get_question(db_path, question_id)
    if question is None:
        raise ValueError("questão inexistente")
    if question["estado"] != "ativo":
        raise ValueError("questão arquivada não pode ser respondida")
    graded = questions.grade(question, resposta)
    tid, at = str(uuid4()), _now()
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO pratica_tentativas(id,questao_id,questao_versao,resposta,correta,respondida,"
            "duracao_segundos,origem,simulado_id,disciplina,topico,conceito_key,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tid, question_id, question["versao"], _clean(resposta, 20) if graded["respondida"] else None,
             1 if graded["correta"] else (0 if graded["respondida"] else None),
             1 if graded["respondida"] else 0,
             None if duracao_segundos is None else max(0, int(duracao_segundos)),
             origem, simulado_id, question["disciplina"], question["topico"],
             question["conceito_key"], at))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"id": tid, "questao_id": question_id, "questao_versao": question["versao"],
            "respondida": graded["respondida"], "correta": graded["correta"],
            "gabarito": question["gabarito"], "comentario": question["comentario"]}


def list_attempts(db_path, *, limit=200, simulado_id=None) -> list[dict]:
    conn = connect_documents(db_path)
    try:
        where, params = [], []
        if simulado_id:
            where.append("simulado_id=?")
            params.append(simulado_id)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        rows = conn.execute(
            "SELECT id,questao_id,questao_versao,resposta,correta,respondida,duracao_segundos,"
            f"origem,simulado_id,disciplina,topico,conceito_key,created_at FROM pratica_tentativas "
            f"{clause} ORDER BY created_at DESC, id LIMIT ?", (*params, max(0, int(limit)))).fetchall()
        keys = ("id", "questao_id", "questao_versao", "resposta", "correta", "respondida",
                "duracao_segundos", "origem", "simulado_id", "disciplina", "topico",
                "conceito_key", "created_at")
        out = []
        for row in rows:
            item = dict(zip(keys, row))
            item["correta"] = None if item["correta"] is None else bool(item["correta"])
            out.append(item)
        return out
    finally:
        conn.close()


# --- Simulados ---------------------------------------------------------------

def create_exam(db_path, *, nome, limit, duracao_segundos=None, seed=None, shuffle=True,
                exclude_answered=True, disciplina=None, topico=None, dificuldade=None,
                tags=None) -> dict:
    """Monta um simulado com questões **sem duplicação** e guarda a versão aplicada."""
    if not _clean(nome):
        raise ValueError("nome do simulado obrigatório")
    if duracao_segundos is not None:
        duracao_segundos = max(0, min(int(duracao_segundos), exams.MAX_DURATION_SECONDS))
        if duracao_segundos == 0:
            duracao_segundos = None
    pool = list_questions(db_path, disciplina=disciplina, topico=topico)
    answered = set()
    if exclude_answered:
        answered = {a["questao_id"] for a in list_attempts(db_path, limit=100000)}
    selected = exams.select_questions(pool, limit=limit, seed=seed, shuffle=shuffle,
                                      exclude_answered=answered, disciplina=disciplina,
                                      topico=topico, dificuldade=dificuldade, tags=tags)
    if not selected:
        raise ValueError("nenhuma questão elegível para o simulado")
    eid, now = str(uuid4()), _now()
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO pratica_simulados(id,nome,duracao_segundos,iniciado_em,finalizado_em,"
            "estado,created_at) VALUES(?,?,?,?,NULL,'em_andamento',?)",
            (eid, _clean(nome), duracao_segundos, now, now))
        for ordem, question in enumerate(selected):
            conn.execute(
                "INSERT INTO pratica_simulado_questoes(simulado_id,ordem,questao_id,questao_versao,"
                "resposta,respondida_em,disciplina,topico) VALUES(?,?,?,?,NULL,NULL,?,?)",
                (eid, ordem, question["id"], question["versao"],
                 question.get("disciplina"), question.get("topico")))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return get_exam(db_path, eid)


def get_exam(db_path, exam_id: str, *, now=None) -> dict | None:
    """Lê o simulado e, se o tempo expirou, **finaliza como expirado** (servidor decide)."""
    conn = connect_documents(db_path)
    try:
        row = conn.execute(
            "SELECT id,nome,duracao_segundos,iniciado_em,finalizado_em,estado,created_at "
            "FROM pratica_simulados WHERE id=?", (exam_id,)).fetchone()
        if row is None:
            return None
        keys = ("id", "nome", "duracao_segundos", "iniciado_em", "finalizado_em", "estado", "created_at")
        exam = dict(zip(keys, row))
        if exam["estado"] == "em_andamento" and exams.is_expired(
                exam["iniciado_em"], exam["duracao_segundos"], now=now):
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE pratica_simulados SET estado='expirado', finalizado_em=? WHERE id=?",
                         (_now(), exam_id))
            conn.commit()
            exam["estado"] = "expirado"
            exam["finalizado_em"] = _now()
    finally:
        conn.close()
    return exam


def exam_items(db_path, exam_id: str, *, include_answer_key=True) -> list[dict]:
    """Questões aplicadas, com a **versão** original (para revisão fiel).

    ``include_answer_key=False`` devolve a prova **sem gabarito/comentário** — usado para
    retomar um simulado em andamento sem vazar a resposta.
    """
    conn = connect_documents(db_path)
    try:
        rows = conn.execute(
            "SELECT sq.ordem,sq.questao_id,sq.questao_versao,sq.resposta,sq.respondida_em,"
            "COALESCE(sq.disciplina,q.disciplina),COALESCE(sq.topico,q.topico),q.estado "
            "FROM pratica_simulado_questoes sq "
            "JOIN pratica_questoes q ON q.id=sq.questao_id "
            "WHERE sq.simulado_id=? ORDER BY sq.ordem", (exam_id,)).fetchall()
        keys = ("ordem", "questao_id", "questao_versao", "resposta", "respondida_em",
                "disciplina", "topico", "questao_estado")
        items = [dict(zip(keys, row)) for row in rows]
    finally:
        conn.close()
    for item in items:
        version = question_version(db_path, item["questao_id"], item["questao_versao"])
        if version is None:
            current = get_question(db_path, item["questao_id"]) or {}
            version = {"enunciado": current.get("enunciado"), "alternativas": current.get("alternativas", []),
                       "gabarito": current.get("gabarito"), "comentario": current.get("comentario")}
        item.update({"enunciado": version["enunciado"], "alternativas": version["alternativas"],
                     "respondida": bool(item.get("resposta"))})
        if include_answer_key:
            item.update({"gabarito": version["gabarito"], "comentario": version["comentario"]})
    return items


def exam_questions(db_path, exam_id: str, *, now=None) -> dict:
    """Prova para **execução/retomada**: questões e respostas salvas, **sem** gabarito."""
    exam = get_exam(db_path, exam_id, now=now)
    if exam is None:
        raise ValueError("simulado inexistente")
    return {"simulado": exam,
            "restante_segundos": exams.remaining_seconds(exam["iniciado_em"],
                                                         exam["duracao_segundos"], now=now),
            "questoes": exam_items(db_path, exam_id, include_answer_key=False)}


def save_exam_answer(db_path, exam_id: str, ordem, resposta, *, now=None) -> dict:
    """Salva **progressivamente** a resposta de uma questão do simulado."""
    if ordem is None:
        raise ValueError("ordem obrigatória")
    try:
        ordem = int(ordem)
    except (TypeError, ValueError):
        raise ValueError("ordem inválida")
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT estado,duracao_segundos,iniciado_em FROM pratica_simulados WHERE id=?",
                           (exam_id,)).fetchone()
        if row is None:
            conn.rollback()
            raise ValueError("simulado inexistente")
        if row[0] != "em_andamento":
            conn.rollback()
            raise ValueError("simulado não está em andamento")
        if exams.is_expired(row[2], row[1], now=now):
            conn.execute("UPDATE pratica_simulados SET estado='expirado', finalizado_em=? WHERE id=?",
                         (_now(), exam_id))
            conn.commit()
            raise ValueError("tempo do simulado esgotado")
        if not conn.execute("SELECT 1 FROM pratica_simulado_questoes WHERE simulado_id=? AND ordem=?",
                            (exam_id, int(ordem))).fetchone():
            conn.rollback()
            raise ValueError("questão fora do simulado")
        conn.execute("UPDATE pratica_simulado_questoes SET resposta=?, respondida_em=? "
                     "WHERE simulado_id=? AND ordem=?",
                     (_clean(resposta, 20), _now(), exam_id, int(ordem)))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"simulado_id": exam_id, "ordem": int(ordem), "resposta": _clean(resposta, 20)}


def finish_exam(db_path, exam_id: str, *, now=None) -> dict:
    """Finaliza (manual ou por tempo) e **persiste** tentativas + resultado.

    **Idempotente**: a transição é condicional e atômica (`tentativas_gravadas`), então
    chamar duas vezes — ou duas requisições concorrentes — grava as tentativas **uma única
    vez**. Sem isso, métricas de desempenho seriam infladas.
    """
    exam = get_exam(db_path, exam_id, now=now)
    if exam is None:
        raise ValueError("simulado inexistente")
    items = exam_items(db_path, exam_id)
    at = _now()
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        # Releitura dentro da transação: evita corrida entre requisições concorrentes.
        row = conn.execute("SELECT estado,tentativas_gravadas FROM pratica_simulados WHERE id=?",
                           (exam_id,)).fetchone()
        if row is None:
            conn.rollback()
            raise ValueError("simulado inexistente")
        estado, gravadas = row[0], int(row[1] or 0)
        if gravadas:
            conn.rollback()
            return exam_result(db_path, exam_id, now=now)
        if estado == "em_andamento":
            cur = conn.execute(
                "UPDATE pratica_simulados SET estado='finalizado', finalizado_em=?, "
                "tentativas_gravadas=1 WHERE id=? AND tentativas_gravadas=0", (at, exam_id))
        elif estado == "expirado":
            cur = conn.execute(
                "UPDATE pratica_simulados SET tentativas_gravadas=1 "
                "WHERE id=? AND tentativas_gravadas=0", (exam_id,))
        else:
            conn.rollback()
            return exam_result(db_path, exam_id, now=now)
        if cur.rowcount != 1:
            conn.rollback()
            return exam_result(db_path, exam_id, now=now)
        # Persiste uma tentativa por questão aplicada (inclusive em branco, com respondida=0).
        for item in items:
            conn.execute(
                "INSERT INTO pratica_tentativas(id,questao_id,questao_versao,resposta,correta,"
                "respondida,duracao_segundos,origem,simulado_id,disciplina,topico,conceito_key,"
                "created_at) VALUES(?,?,?,?,?,?,NULL,'simulado',?,?,?,NULL,?)",
                (str(uuid4()), item["questao_id"], item["questao_versao"], item.get("resposta"),
                 1 if item.get("respondida") and str(item.get("resposta") or "").upper()
                 == str(item.get("gabarito") or "").upper() else (0 if item.get("respondida") else None),
                 1 if item.get("respondida") else 0, exam_id, item.get("disciplina"),
                 item.get("topico"), at))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return exam_result(db_path, exam_id, now=now)


def exam_result(db_path, exam_id: str, *, now=None) -> dict:
    """Resultado do simulado. **Não** revela gabarito de prova ainda em andamento."""
    exam = get_exam(db_path, exam_id, now=now)
    if exam is None:
        raise ValueError("simulado inexistente")
    if exam["estado"] == "em_andamento":
        raise ValueError("simulado em andamento: resultado indisponível antes de finalizar")
    items = exam_items(db_path, exam_id)
    result = exams.result(items, duration_seconds=exam["duracao_segundos"],
                          started_at=exam["iniciado_em"], finished_at=exam["finalizado_em"],
                          now=now, expired=exam["estado"] == "expirado")
    return {"simulado": exam, "resultado": result, "questoes": items}


def list_exams(db_path, *, limit=50) -> list[dict]:
    conn = connect_documents(db_path)
    try:
        rows = conn.execute(
            "SELECT id,nome,duracao_segundos,iniciado_em,finalizado_em,estado,created_at "
            "FROM pratica_simulados ORDER BY iniciado_em DESC, id LIMIT ?", (max(0, int(limit)),)).fetchall()
        keys = ("id", "nome", "duracao_segundos", "iniciado_em", "finalizado_em", "estado", "created_at")
        return [dict(zip(keys, row)) for row in rows]
    finally:
        conn.close()


# --- Desempenho agregado -----------------------------------------------------

def performance_report(db_path, *, include_blank=False) -> dict:
    """Desempenho **derivado das tentativas persistidas** (denominador explícito)."""
    attempts = list_attempts(db_path, limit=100000)
    return {"geral": questions.stats(attempts, include_blank=include_blank),
            "por_disciplina": questions.stats_by(attempts, "disciplina", include_blank=include_blank),
            "por_topico": questions.stats_by(attempts, "topico", include_blank=include_blank),
            "simulados": list_exams(db_path)}
