"""Perfil de conhecimentos, conteúdo programático e inteligência de preparação (Fase 22).

Conecta a infraestrutura documental (conteúdo extraído como propostas com evidência) ao módulo
de estudos, **sem** fundir dimensões distintas:

- Conteúdo do edital = propostas `conteudo_*` (oficial, com evidência) — lidas aqui.
- Conhecimento declarado = `estudo_perfil` (pessoal).
- Progresso de estudo = `estudo_progresso`/`estudo_topicos` (pessoal).
- Cobertura = cálculo explicável sobre o subconjunto **identificado**.

Dados pessoais ficam em tabelas próprias, nunca expostos pelo contrato v1.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from radar import preparation
from radar.document_store import connect_documents

_CONTENT_FIELDS = ("conteudo_secao", "conteudo_disciplina", "conteudo_topico", "conteudo_subtopico")
_TOPIC_FIELDS = ("conteudo_topico", "conteudo_subtopico")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Perfil de conhecimentos -------------------------------------------------

def set_profile(db_path, *, disciplina, rotulo, nivel="nao_avaliado", revisar=False,
                confianca=None, observacoes=None, origem="usuario") -> dict:
    """Cria/atualiza a familiaridade declarada de um conceito (chave normalizada)."""
    if not isinstance(rotulo, str) or not rotulo.strip():
        raise ValueError("rótulo do conceito obrigatório")
    if nivel not in preparation.FAMILIARITY_LEVELS:
        raise ValueError("nível de familiaridade inválido")
    if confianca is not None and confianca not in preparation.CONFIDENCE_LEVELS:
        raise ValueError("confiança inválida")
    if origem not in preparation.ORIGINS:
        raise ValueError("origem inválida")
    key = preparation.conceito_key(disciplina, rotulo)
    now = _now()
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT id FROM estudo_perfil WHERE conceito_key=?", (key,)).fetchone()
        if row:
            pid = row[0]
            conn.execute(
                "UPDATE estudo_perfil SET disciplina=?, rotulo=?, nivel=?, revisar=?, confianca=?, "
                "observacoes=?, origem=?, updated_at=? WHERE id=?",
                (disciplina, rotulo.strip()[:200], nivel, 1 if revisar else 0, confianca,
                 (observacoes or None), origem, now, pid))
        else:
            pid = str(uuid4())
            conn.execute(
                "INSERT INTO estudo_perfil(id,conceito_key,disciplina,rotulo,nivel,revisar,"
                "confianca,observacoes,origem,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (pid, key, disciplina, rotulo.strip()[:200], nivel, 1 if revisar else 0,
                 confianca, (observacoes or None), origem, now, now))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"id": pid, "conceito_key": key, "nivel": nivel, "revisar": bool(revisar)}


def list_profile(db_path) -> list[dict]:
    conn = connect_documents(db_path)
    try:
        rows = conn.execute(
            "SELECT id,conceito_key,disciplina,rotulo,nivel,revisar,confianca,observacoes,origem,"
            "created_at,updated_at FROM estudo_perfil ORDER BY disciplina COLLATE NOCASE, rotulo COLLATE NOCASE"
        ).fetchall()
        keys = ("id", "conceito_key", "disciplina", "rotulo", "nivel", "revisar", "confianca",
                "observacoes", "origem", "created_at", "updated_at")
        return [dict(zip(keys, row)) for row in rows]
    finally:
        conn.close()


def profile_map(db_path) -> dict:
    return {item["conceito_key"]: {"nivel": item["nivel"], "revisar": bool(item["revisar"])}
            for item in list_profile(db_path)}


def delete_profile(db_path, conceito_key: str) -> bool:
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute("DELETE FROM estudo_perfil WHERE conceito_key=?", (conceito_key,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# --- Conteúdo programático (leitura das propostas oficiais) ------------------

def _content_rows(conn, contest_id):
    """Propostas de conteúdo com evidência (versão, hash, página, trecho) e revisão, em ordem."""
    return conn.execute(
        """SELECT p.id, p.field_name, p.value_json, p.ambiguity_reason, p.extracted_at,
        e.version_id, e.page_number, e.quote, v.document_id, v.sha256,
        (SELECT r.decision FROM revisoes_campo r WHERE r.proposal_id=p.id
         ORDER BY r.reviewed_at DESC, r.rowid DESC LIMIT 1) AS decision
        FROM propostas_campo p
        LEFT JOIN evidencias e ON e.id=p.evidence_id
        LEFT JOIN versoes_documento v ON v.id=e.version_id
        WHERE p.contest_id=? AND p.field_name IN (?,?,?,?)
        ORDER BY p.extracted_at, p.rowid""",
        (contest_id, *_CONTENT_FIELDS)).fetchall()


def resolve_program(db_path, contest_id: str) -> dict:
    """Estrutura o conteúdo programático de um concurso, com estado e evidência por item.

    Estado por item: ``confirmado`` (revisão validada), ``rejeitado`` (revisão), ou
    ``extraido_nao_revisado``. Itens com a **mesma chave de conceito** e redações divergentes
    sem revisão viram ``ambiguo`` (não se escolhe em silêncio). A disciplina de um tópico é a
    ``conteudo_disciplina`` mais recente **na mesma versão**.
    """
    conn = connect_documents(db_path)
    try:
        rows = _content_rows(conn, contest_id)
    finally:
        conn.close()

    items = []
    current_disc = {}
    for (pid, field, value_json, ambiguity, extracted_at, version_id, page, quote,
         document_id, sha256, decision) in rows:
        try:
            value = json.loads(value_json)
        except (TypeError, ValueError):
            continue
        if not isinstance(value, str) or not value.strip():
            continue
        estado = {"validado": "confirmado", "rejeitado": "rejeitado"}.get(decision, "extraido_nao_revisado")
        if field == "conteudo_disciplina":
            current_disc[version_id] = value.strip()
        disciplina = current_disc.get(version_id) if field in _TOPIC_FIELDS else None
        items.append({"id": pid, "field_name": field, "value": value.strip(), "estado": estado,
                      "disciplina": disciplina, "ambiguity_reason": ambiguity,
                      "version_id": version_id, "version_sha256": sha256, "page_number": page,
                      "quote": quote, "document_id": document_id, "extracted_at": extracted_at})

    # Ambiguidade: tópico sem disciplina de contexto, ou mesma chave de conceito com redações
    # divergentes (sem revisão resolvida). Nunca se escolhe em silêncio.
    by_key = {}
    for item in items:
        if item["field_name"] not in _TOPIC_FIELDS:
            continue
        key = preparation.conceito_key(item["disciplina"], item["value"])
        item["conceito_key"] = key
        by_key.setdefault(key, []).append(item)
    for item in items:
        if item["field_name"] in _TOPIC_FIELDS and not item["disciplina"] and item["estado"] == "extraido_nao_revisado":
            item["estado"] = "ambiguo"  # não é possível situar na hierarquia
    for key, group in by_key.items():
        distinct = {i["value"].strip() for i in group}
        if len(distinct) > 1 and not any(i["estado"] == "confirmado" for i in group):
            for i in group:
                if i["estado"] == "extraido_nao_revisado":
                    i["estado"] = "ambiguo"

    topicos = [i for i in items if i["field_name"] in _TOPIC_FIELDS]
    disciplinas = [i for i in items if i["field_name"] == "conteudo_disciplina"]
    secoes = [i for i in items if i["field_name"] == "conteudo_secao"]
    counts = {}
    for item in topicos:
        counts[item["estado"]] = counts.get(item["estado"], 0) + 1
    return {"contest_id": contest_id, "secoes": secoes, "disciplinas": disciplinas,
            "topicos": topicos, "counts": counts,
            "coverage_state": _coverage_state(items)}


def _coverage_state(items) -> str:
    """Estado de cobertura da extração do programa (honesto sobre o que falta)."""
    if not items:
        return "nao_localizado"
    if any(i["field_name"] == "conteudo_secao" and "(seção truncada)" in (i["value"] or "")
           for i in items):
        return "extraido_parcial"  # seção excedeu o limite de segurança
    if any(i["field_name"] in _TOPIC_FIELDS for i in items):
        revisados = any(i["estado"] == "confirmado" for i in items)
        return "extraido_nao_revisado" if not revisados else "extraido_parcial"
    return "extraido_nao_revisado"


# --- Progresso de estudo mapeado por conceito --------------------------------

def _progresso_map(conn, contest_id: str = "") -> dict:
    """Progresso de estudo mapeado por conceito, incluindo o geral e o do edital informado."""
    rows = conn.execute(
        """SELECT d.nome, t.nome, p.state
        FROM estudo_progresso p
        JOIN estudo_topicos t ON t.id=p.topico_id
        JOIN estudo_disciplinas d ON d.id=t.disciplina_id
        WHERE p.contest_id IN ('', ?)""", (contest_id or "",)).fetchall()
    out = {}
    for disc, topico, state in rows:
        out[preparation.conceito_key(disc, topico)] = {"state": state}
    return out


def _formal_status(conn, contest_id: str) -> tuple[str, bool]:
    """Estado formal do cargo e sinal de excepcionalidade, com a precedência documentada.

    ``(estado, exceptional)``: estado em ``SI_STATES`` e ``exceptional`` quando a aceitação de
    Sistemas de Informação é **explícita** e há ≥3 vagas indígenas imediatas conhecidas.
    """
    from radar.edital_requirements import SI_STATES
    rows = conn.execute(
        """SELECT p.value_json, p.ambiguity_reason, p.extracted_at,
        (SELECT r.decision FROM revisoes_campo r WHERE r.proposal_id=p.id
         ORDER BY r.reviewed_at DESC, r.rowid DESC LIMIT 1) AS decision
        FROM propostas_campo p WHERE p.contest_id=? AND p.field_name='si_compatibility'
        ORDER BY p.extracted_at, p.rowid""", (contest_id,)).fetchall()
    state = "nao_extraido"
    if rows:
        values = []
        for value_json, _amb, _at, decision in rows:
            try:
                values.append((json.loads(value_json), decision))
            except (TypeError, ValueError):
                continue
        validated = [v for v, d in values if d == "validado"]
        chosen = validated[-1] if validated else (values[-1][0] if values else None)
        distinct = {v for v, _ in values}
        if chosen in SI_STATES:
            state = "ambiguo" if (len(distinct) > 1 and not validated) else chosen
    indigenous = conn.execute(
        """SELECT value_json FROM propostas_campo WHERE contest_id=? AND field_name='indigenous_vacancies'
        ORDER BY extracted_at DESC, rowid DESC LIMIT 1""", (contest_id,)).fetchone()
    immediate = None
    if indigenous:
        try:
            immediate = json.loads(indigenous[0])
        except (TypeError, ValueError):
            immediate = None
    exceptional = (state == "aceito_expressamente" and isinstance(immediate, int)
                   and immediate >= 3)
    return state, exceptional


def preparation_report(db_path, contest_id: str) -> dict:
    """Cobertura de preparação de um concurso (explicável, com lacunas e perspectiva)."""
    program = resolve_program(db_path, contest_id)
    profile = profile_map(db_path)
    conn = connect_documents(db_path)
    try:
        progresso = _progresso_map(conn, contest_id)
        formal_state, exceptional = _formal_status(conn, contest_id)
    finally:
        conn.close()
    result = preparation.coverage(program["topicos"], profile, progresso=progresso)
    gaps = [{"conceito_key": t["conceito_key"], "disciplina": t["disciplina"], "rotulo": t["value"],
             "estado": t["estado"], "nivel": (profile.get(t["conceito_key"]) or {}).get("nivel", "nao_avaliado")}
            for t in program["topicos"]
            if t["estado"] in ("confirmado", "extraido_nao_revisado")
            and (profile.get(t["conceito_key"]) or {}).get("nivel") not in ("basico", "intermediario", "avancado")]
    perspective = preparation.perspective(
        formal_compatible=(formal_state in ("aceito_expressamente", "abrangido_por_categoria")),
        formal_ambiguous=(formal_state in ("ambiguo", "nao_extraido", "nao_informado")),
        formal_incompatible=(formal_state == "incompativel_com_requisito_explicito"),
        coverage_pct=result["pct"], gaps=gaps, exceptional=exceptional)
    return {"contest_id": contest_id, "coverage": result, "gaps": gaps,
            "program_counts": program["counts"], "coverage_state": program["coverage_state"],
            "formal_state": formal_state, "perspective": perspective,
            "perspective_label": preparation.PERSPECTIVE_LABELS.get(perspective)}


# --- Lacuna → plano de estudos (Frente D) ------------------------------------

def send_gap_to_study(db_path, contest_id: str, conceito_key: str) -> dict:
    """Cria (idempotente) disciplina/tópico no módulo de estudos a partir de uma lacuna.

    Reutiliza `study_store`; não duplica disciplina/tópico com o mesmo nome.
    """
    from radar import study_store
    program = resolve_program(db_path, contest_id)
    topic = next((t for t in program["topicos"] if t.get("conceito_key") == conceito_key), None)
    if topic is None:
        raise ValueError("conceito não encontrado no conteúdo do concurso")
    if topic["estado"] not in ("confirmado", "extraido_nao_revisado"):
        raise ValueError("apenas conteúdo identificado pode ir para o plano de estudos")
    disciplina_nome = (topic["disciplina"] or "Conteúdo do edital").strip()
    rotulo = topic["value"].strip()
    disciplina = next((d for d in study_store.list_disciplinas(db_path)
                       if preparation.normalize_text(d["nome"]) == preparation.normalize_text(disciplina_nome)), None)
    if disciplina is None:
        disciplina = study_store.create_disciplina(db_path, disciplina_nome[:200])
    existing = next((t for t in study_store.list_topicos(db_path, disciplina["id"])
                     if preparation.normalize_text(t["nome"]) == preparation.normalize_text(rotulo)), None)
    if existing is not None:
        return {"disciplina_id": disciplina["id"], "topico_id": existing["id"], "created": False}
    topico = study_store.create_topico(db_path, disciplina["id"], rotulo[:200])
    return {"disciplina_id": disciplina["id"], "topico_id": topico["id"], "created": True}
