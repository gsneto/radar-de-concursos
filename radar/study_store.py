"""Persistência da gestão de estudos (tabelas `estudo_*`, dados pessoais).

Mesmo banco SQLite do Radar, mas em **tabelas separadas** que não são expostas pelo contrato
v1 nem pelas rotas de concursos. O catálogo (disciplinas/tópicos) é separado do progresso: o
progresso de um tópico é registrado por ``contest_id`` (``''`` = geral), de modo que estudar um
tópico para um edital **não** altera o progresso dele em outro.

O cronômetro é persistido como sessão: no máximo **uma** sessão aberta
(``em_andamento``/``pausada``) por vez; a retomada após reinício usa o estado persistido
(``inicio`` + acumulado), sem duplicar sessões. A duração é limitada a um teto plausível
(``study.MAX_SESSION_SECONDS``) para que um fechamento longo do aplicativo não vire horas de
estudo dormindo.

A revisão espaçada é **persistida** em `estudo_revisoes` (a agenda é a fonte de verdade):
concluir um tópico cria as datas; marcar uma revisão como feita grava ``feita_em``/``resultado``
e a próxima data não feita passa a ser a pendente.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from radar import study
from radar.document_store import connect_documents

_MAX_CONTEST_ID = 120


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return study.local_today().isoformat()


# --- Catálogo: disciplinas e tópicos -----------------------------------------

def create_disciplina(db_path, nome: str) -> dict:
    if not isinstance(nome, str) or not nome.strip():
        raise ValueError("nome da disciplina obrigatório")
    did = str(uuid4())
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT INTO estudo_disciplinas(id,nome,created_at) VALUES(?,?,?)",
                     (did, nome.strip()[:200], _now()))
        conn.commit()
    finally:
        conn.close()
    return {"id": did, "nome": nome.strip()[:200]}


def list_disciplinas(db_path) -> list[dict]:
    conn = connect_documents(db_path)
    try:
        rows = conn.execute(
            "SELECT id,nome,created_at FROM estudo_disciplinas ORDER BY nome COLLATE NOCASE, id"
        ).fetchall()
        return [dict(zip(("id", "nome", "created_at"), row)) for row in rows]
    finally:
        conn.close()


def delete_disciplina(db_path, disciplina_id: str) -> bool:
    """Remove a disciplina e, em cascata, seus tópicos, progresso, revisões e sessões."""
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        topico_ids = [row[0] for row in conn.execute(
            "SELECT id FROM estudo_topicos WHERE disciplina_id=?", (disciplina_id,)).fetchall()]
        for topico_id in topico_ids:
            _delete_topico_cascade(conn, topico_id)
        conn.execute("DELETE FROM estudo_sessoes WHERE disciplina_id=?", (disciplina_id,))
        cur = conn.execute("DELETE FROM estudo_disciplinas WHERE id=?", (disciplina_id,))
        conn.commit()
        return cur.rowcount > 0
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_topico(db_path, disciplina_id: str, nome: str, parent_id: str | None = None) -> dict:
    if not isinstance(nome, str) or not nome.strip():
        raise ValueError("nome do tópico obrigatório")
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        if not conn.execute("SELECT 1 FROM estudo_disciplinas WHERE id=?", (disciplina_id,)).fetchone():
            raise ValueError("disciplina inexistente")
        if parent_id and not conn.execute("SELECT 1 FROM estudo_topicos WHERE id=?", (parent_id,)).fetchone():
            raise ValueError("tópico-pai inexistente")
        tid = str(uuid4())
        conn.execute(
            "INSERT INTO estudo_topicos(id,disciplina_id,parent_id,nome,created_at) VALUES(?,?,?,?,?)",
            (tid, disciplina_id, parent_id, nome.strip()[:200], _now()))
        conn.commit()
    finally:
        conn.close()
    return {"id": tid, "disciplina_id": disciplina_id, "parent_id": parent_id, "nome": nome.strip()[:200]}


def list_topicos(db_path, disciplina_id: str | None = None) -> list[dict]:
    conn = connect_documents(db_path)
    try:
        if disciplina_id:
            rows = conn.execute(
                "SELECT id,disciplina_id,parent_id,nome,created_at FROM estudo_topicos "
                "WHERE disciplina_id=? ORDER BY nome COLLATE NOCASE, id", (disciplina_id,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT id,disciplina_id,parent_id,nome,created_at FROM estudo_topicos "
                "ORDER BY disciplina_id, nome COLLATE NOCASE, id").fetchall()
        return [dict(zip(("id", "disciplina_id", "parent_id", "nome", "created_at"), row)) for row in rows]
    finally:
        conn.close()


def _delete_topico_cascade(conn, topico_id: str) -> int:
    """Remove um tópico, seus filhos, progresso, revisões e sessões associadas."""
    children = [row[0] for row in conn.execute(
        "SELECT id FROM estudo_topicos WHERE parent_id=?", (topico_id,)).fetchall()]
    for child in children:
        _delete_topico_cascade(conn, child)
    conn.execute("DELETE FROM estudo_revisoes WHERE progresso_id IN "
                 "(SELECT id FROM estudo_progresso WHERE topico_id=?)", (topico_id,))
    conn.execute("DELETE FROM estudo_progresso WHERE topico_id=?", (topico_id,))
    conn.execute("UPDATE estudo_sessoes SET topico_id=NULL WHERE topico_id=?", (topico_id,))
    return conn.execute("DELETE FROM estudo_topicos WHERE id=?", (topico_id,)).rowcount


def delete_topico(db_path, topico_id: str) -> bool:
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        removed = _delete_topico_cascade(conn, topico_id)
        conn.commit()
        return removed > 0
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


# --- Progresso por (concurso, tópico) ----------------------------------------

def _clean_contest_id(contest_id) -> str:
    value = contest_id or ""
    if not isinstance(value, str):
        raise ValueError("contest_id inválido")
    value = value.strip()
    if len(value) > _MAX_CONTEST_ID:
        raise ValueError("contest_id acima do limite")
    return value


def set_progress(db_path, topico_id: str, state: str, *, contest_id: str = "") -> dict:
    """Define o estado de um tópico (em um edital ou geral) e (re)agenda revisões."""
    if state not in study.TOPIC_STATES:
        raise ValueError("estado de progresso inválido")
    contest_id = _clean_contest_id(contest_id)
    now = _now()
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        if not conn.execute("SELECT 1 FROM estudo_topicos WHERE id=?", (topico_id,)).fetchone():
            raise ValueError("tópico inexistente")
        row = conn.execute(
            "SELECT id FROM estudo_progresso WHERE contest_id=? AND topico_id=?",
            (contest_id, topico_id)).fetchone()
        concluido_em = _today() if state == "concluido" else None
        if row:
            pid = row[0]
            conn.execute(
                "UPDATE estudo_progresso SET state=?, data_conclusao=?, updated_at=? WHERE id=?",
                (state, concluido_em, now, pid))
            # Só reagenda quando passa a concluído; preserva o histórico já existente.
            if state == "concluido":
                conn.execute("DELETE FROM estudo_revisoes WHERE progresso_id=?", (pid,))
        else:
            pid = str(uuid4())
            conn.execute(
                "INSERT INTO estudo_progresso(id,contest_id,topico_id,state,data_conclusao,"
                "adiamentos,created_at,updated_at) VALUES(?,?,?,?,?,0,?,?)",
                (pid, contest_id, topico_id, state, concluido_em, now, now))
        if state == "concluido" and not conn.execute(
                "SELECT 1 FROM estudo_revisoes WHERE progresso_id=?", (pid,)).fetchone():
            for dia in study.revision_dates(concluido_em, [], 0):
                conn.execute("INSERT INTO estudo_revisoes(id,progresso_id,agendada_para,created_at) "
                             "VALUES(?,?,?,?)", (str(uuid4()), pid, dia, now))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"id": pid, "topico_id": topico_id, "contest_id": contest_id, "state": state}


def list_progresso(db_path, *, contest_id: str = "") -> list[dict]:
    contest_id = _clean_contest_id(contest_id)
    conn = connect_documents(db_path)
    try:
        rows = conn.execute(
            "SELECT id,contest_id,topico_id,state,data_conclusao,adiamentos,updated_at "
            "FROM estudo_progresso WHERE contest_id=? ORDER BY updated_at, id", (contest_id,)).fetchall()
        return [dict(zip(("id", "contest_id", "topico_id", "state", "data_conclusao",
                          "adiamentos", "updated_at"), row)) for row in rows]
    finally:
        conn.close()


def progresso_por_topico(db_path, contest_id: str = "") -> dict:
    """Mapa ``topico_id -> estado`` para um edital (ou geral), para exibição na interface."""
    return {item["topico_id"]: item["state"] for item in list_progresso(db_path, contest_id=contest_id)}


# --- Revisão espaçada (agenda persistida) ------------------------------------

def mark_revision_done(db_path, progresso_id: str, *, resultado: str | None = None) -> dict:
    """Marca como feita a revisão pendente mais antiga do progresso (grava ``feita_em``)."""
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT id,agendada_para FROM estudo_revisoes WHERE progresso_id=? AND feita_em IS NULL "
            "ORDER BY agendada_para, id LIMIT 1", (progresso_id,)).fetchone()
        if not row:
            conn.rollback()
            raise ValueError("não há revisão pendente para este progresso")
        conn.execute("UPDATE estudo_revisoes SET feita_em=?, resultado=? WHERE id=?",
                     (_now(), (resultado or "")[:200] or None, row[0]))
        conn.commit()
        return {"id": row[0], "progresso_id": progresso_id, "agendada_para": row[1], "feita": True}
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def pending_revisions(db_path, *, today=None) -> list[dict]:
    """Revisões **vencidas** a partir da agenda persistida (fonte de verdade)."""
    today = today or _today()
    conn = connect_documents(db_path)
    try:
        rows = conn.execute(
            """SELECT r.id, r.progresso_id, r.agendada_para, p.topico_id, p.contest_id
            FROM estudo_revisoes r JOIN estudo_progresso p ON p.id=r.progresso_id
            WHERE r.feita_em IS NULL AND r.agendada_para <= ?
            ORDER BY r.agendada_para, r.id""", (today,)).fetchall()
        return [dict(zip(("revisao_id", "progresso_id", "data", "topico_id", "contest_id"), row))
                for row in rows]
    finally:
        conn.close()


# --- Sessões de estudo (cronômetro) ------------------------------------------

def current_session(db_path) -> dict | None:
    """Sessão aberta (em andamento/pausada), para retomada após reinício."""
    conn = connect_documents(db_path)
    try:
        row = conn.execute(
            "SELECT id,disciplina_id,topico_id,contest_id,inicio,fim,duracao_segundos,estado,modo,notas,created_at "
            "FROM estudo_sessoes WHERE estado IN ('em_andamento','pausada') "
            "ORDER BY created_at DESC LIMIT 1").fetchone()
        if not row:
            return None
        return _row_to_session(row)
    finally:
        conn.close()


def start_session(db_path, *, disciplina_id=None, topico_id=None, contest_id: str = "",
                  modo: str = "livre") -> dict:
    """Inicia uma sessão. Recusa se já houver uma aberta (evita duplicação)."""
    if modo not in ("livre", "pomodoro"):
        raise ValueError("modo inválido")
    contest_id = _clean_contest_id(contest_id)
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM estudo_sessoes WHERE estado IN ('em_andamento','pausada')").fetchone():
            raise ValueError("já existe uma sessão em andamento")
        for table, value in (("estudo_disciplinas", disciplina_id), ("estudo_topicos", topico_id)):
            if value and not conn.execute(f"SELECT 1 FROM {table} WHERE id=?", (value,)).fetchone():
                raise ValueError("referência inexistente")
        sid = str(uuid4())
        now = _now()
        conn.execute(
            "INSERT INTO estudo_sessoes(id,disciplina_id,topico_id,contest_id,inicio,fim,"
            "duracao_segundos,estado,modo,notas,created_at) VALUES(?,?,?,?,?,NULL,0,'em_andamento',?,NULL,?)",
            (sid, disciplina_id, topico_id, contest_id, now, modo, now))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return current_session(db_path)


def _row_to_session(row) -> dict:
    keys = ("id", "disciplina_id", "topico_id", "contest_id", "inicio", "fim",
            "duracao_segundos", "estado", "modo", "notas", "created_at")
    session = dict(zip(keys, row))
    # Teto plausível também na leitura (não mostra "tempo dormindo").
    session["elapsed_seconds"] = study.capped_elapsed(session)
    return session


def _open_row(conn, session_id=None):
    if session_id:
        return conn.execute("SELECT id,duracao_segundos,estado,inicio FROM estudo_sessoes "
                            "WHERE id=? AND estado IN ('em_andamento','pausada')", (session_id,)).fetchone()
    return conn.execute("SELECT id,duracao_segundos,estado,inicio FROM estudo_sessoes "
                        "WHERE estado IN ('em_andamento','pausada') ORDER BY created_at DESC LIMIT 1").fetchone()


def _open_elapsed(row) -> int:
    return study.capped_elapsed({"duracao_segundos": row[1], "estado": row[2], "inicio": row[3]})


def pause_session(db_path, session_id: str | None = None) -> dict:
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = _open_row(conn, session_id)
        if not row or row[2] != "em_andamento":
            conn.rollback()
            raise ValueError("nenhuma sessão em andamento para pausar")
        conn.execute("UPDATE estudo_sessoes SET estado='pausada', duracao_segundos=?, inicio=NULL WHERE id=?",
                     (_open_elapsed(row), row[0]))
        conn.commit()
        sid = row[0]
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return _session_by_id(db_path, sid)


def resume_session(db_path, session_id: str | None = None) -> dict:
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = _open_row(conn, session_id)
        if not row or row[2] != "pausada":
            conn.rollback()
            raise ValueError("nenhuma sessão pausada para retomar")
        conn.execute("UPDATE estudo_sessoes SET estado='em_andamento', inicio=? WHERE id=?",
                     (_now(), row[0]))
        conn.commit()
        sid = row[0]
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return _session_by_id(db_path, sid)


def finish_session(db_path, session_id: str | None = None) -> dict:
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = _open_row(conn, session_id)
        if not row:
            conn.rollback()
            raise ValueError("nenhuma sessão aberta para concluir")
        now = _now()
        conn.execute("UPDATE estudo_sessoes SET estado='concluida', duracao_segundos=?, inicio=NULL, fim=? "
                     "WHERE id=?", (_open_elapsed(row), now, row[0]))
        conn.commit()
        sid = row[0]
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return _session_by_id(db_path, sid)


def discard_session(db_path, session_id: str | None = None) -> dict:
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = _open_row(conn, session_id)
        if not row:
            conn.rollback()
            raise ValueError("nenhuma sessão aberta para descartar")
        conn.execute("UPDATE estudo_sessoes SET estado='descartada', inicio=NULL, fim=? WHERE id=?",
                     (_now(), row[0]))
        conn.commit()
        sid = row[0]
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return _session_by_id(db_path, sid)


def _session_by_id(db_path, session_id: str) -> dict:
    conn = connect_documents(db_path)
    try:
        row = conn.execute(
            "SELECT id,disciplina_id,topico_id,contest_id,inicio,fim,duracao_segundos,estado,modo,notas,created_at "
            "FROM estudo_sessoes WHERE id=?", (session_id,)).fetchone()
        return _row_to_session(row)
    finally:
        conn.close()


def list_sessions(db_path, *, limit: int = 50, concluidas_only: bool = False) -> list[dict]:
    conn = connect_documents(db_path)
    try:
        where = "WHERE estado='concluida'" if concluidas_only else ""
        rows = conn.execute(
            f"SELECT id,disciplina_id,topico_id,contest_id,inicio,fim,duracao_segundos,estado,modo,notas,created_at "
            f"FROM estudo_sessoes {where} ORDER BY COALESCE(fim, inicio) DESC, id DESC LIMIT ?",
            (max(0, int(limit)),)).fetchall()
        keys = ("id", "disciplina_id", "topico_id", "contest_id", "inicio", "fim",
                "duracao_segundos", "estado", "modo", "notas", "created_at")
        return [dict(zip(keys, row)) for row in rows]
    finally:
        conn.close()


# --- Painel (agregados a partir dos dados persistidos) -----------------------

def study_dashboard(db_path, *, today=None) -> dict:
    """Agregados reais (não fictícios): progresso, tempo, revisões pendentes e sessão aberta.

    Totais agregados em SQL (sem truncar por limite de linhas) e revisões lidas da agenda
    persistida — nunca de exemplos fictícios.
    """
    today = today or _today()
    conn = connect_documents(db_path)
    try:
        disciplinas = [dict(zip(("id", "nome"), row)) for row in conn.execute(
            "SELECT id,nome FROM estudo_disciplinas ORDER BY nome COLLATE NOCASE, id").fetchall()]
        topicos = conn.execute(
            "SELECT id,disciplina_id FROM estudo_topicos ORDER BY disciplina_id, nome COLLATE NOCASE").fetchall()
        progresso = [dict(zip(("id", "contest_id", "topico_id", "state", "data_conclusao",
                              "adiamentos", "updated_at"), row)) for row in conn.execute(
            "SELECT id,contest_id,topico_id,state,data_conclusao,adiamentos,updated_at "
            "FROM estudo_progresso WHERE contest_id='' ORDER BY updated_at, id").fetchall()]
        total_segundos = conn.execute(
            "SELECT COALESCE(SUM(duracao_segundos),0) FROM estudo_sessoes WHERE estado='concluida'"
        ).fetchone()[0]
        semana_cutoff = (study.local_today(today) - timedelta(days=6)).isoformat()
        semana_segundos = conn.execute(
            "SELECT COALESCE(SUM(duracao_segundos),0) FROM estudo_sessoes "
            "WHERE estado='concluida' AND substr(COALESCE(fim,inicio),1,10) >= ?", (semana_cutoff,)
        ).fetchone()[0]
        sessoes_concluidas = conn.execute(
            "SELECT count(*) FROM estudo_sessoes WHERE estado='concluida'").fetchone()[0]
        por_disc = conn.execute(
            "SELECT disciplina_id, COALESCE(SUM(duracao_segundos),0) FROM estudo_sessoes "
            "WHERE estado='concluida' AND disciplina_id IS NOT NULL GROUP BY disciplina_id"
        ).fetchall()
        pendentes = conn.execute(
            "SELECT count(*) FROM estudo_revisoes WHERE feita_em IS NULL AND agendada_para <= ?",
            (today,)).fetchone()[0]
        revisoes = [dict(zip(("revisao_id", "progresso_id", "data", "topico_id"), row)) for row in conn.execute(
            """SELECT r.id, r.progresso_id, r.agendada_para, p.topico_id
            FROM estudo_revisoes r JOIN estudo_progresso p ON p.id=r.progresso_id
            WHERE r.feita_em IS NULL AND r.agendada_para <= ?
            ORDER BY r.agendada_para, r.id""", (today,)).fetchall()]
    finally:
        conn.close()

    state_by_topico = {item["topico_id"]: item["state"] for item in progresso}
    por_disciplina = {}
    for tid, disc_id in topicos:
        por_disciplina.setdefault(disc_id, []).append({"state": state_by_topico.get(tid, "nao_iniciado")})
    conteudo = study.content_progress([{"topicos": por_disciplina.get(d["id"], [])} for d in disciplinas])

    nome_por_disc = {d["id"]: d["nome"] for d in disciplinas}
    minutos_por_disc = [{"disciplina_id": did, "nome": nome_por_disc.get(did, did),
                         "minutos": round(int(seconds) / 60)}
                        for did, seconds in sorted(por_disc, key=lambda kv: -kv[1]) if seconds]

    return {
        "disciplinas": len(disciplinas),
        "topicos": len(topicos),
        "conteudo": conteudo,
        "progresso": progresso,
        "total_segundos": int(total_segundos),
        "semana_segundos": int(semana_segundos),
        "sessoes_concluidas": int(sessoes_concluidas),
        "minutos_por_disciplina": minutos_por_disc,
        "revisoes_pendentes": int(pendentes),
        "revisoes": revisoes,
        "sessao_aberta": current_session(db_path),
    }
