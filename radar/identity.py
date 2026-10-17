"""Identidade canônica do concurso, separada da identidade da fonte (Fase 27).

O problema estrutural que este módulo resolve: ``observacoes_concurso.competition_id`` é o
identificador **externo** da fonte. Quando a fonte é um catálogo ou uma seção de diário
oficial (``DOU-S3``), esse identificador descreve a *publicação*, não um certame. Usá-lo como
identidade de concurso agrupa atos de órgãos diferentes num único "concurso".

Conceitos separados aqui:

- **concurso** (``concursos_identidade.id``): uuid interno estável, independente de fonte.
  ``estado_identidade='certame'`` = oportunidade real; ``'container_fonte'`` = área de
  retenção de uma fonte cujo identificador não é de certame (nunca entra em métricas).
- **fonte / identificador externo** (``observacoes_concurso.competition_id``): o id que a
  fonte usa. ``tipo_identidade`` diz o que ele é (certame, seção de publicação, catálogo).
- **documento** (``documentos``): ato ou página; pertence a uma observação.
- **associação documento→concurso** (``associacoes_documento``): log append-only com estado,
  evidência, autor e justificativa. Um documento em container fica ``pendente`` até que
  exista evidência suficiente — nada é inventado.

Nenhuma função aqui aprova propostas de campo nem altera ``valores_atuais``.
"""

from __future__ import annotations

import json
import re
from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from radar.document_store import connect_documents, is_readable_schema

IDENTITY_VERSION = "identity_v1"

CONTEST_STATES = ("certame", "container_fonte")
OBSERVATION_TYPES = ("certame", "secao_publicacao", "catalogo", "desconhecida")
ASSOCIATION_STATES = ("confirmada", "candidata", "ambigua", "rejeitada", "pendente")

STATE_LABELS = {
    "confirmada": "Associação confirmada",
    "candidata": "Candidata (evidência parcial)",
    "ambigua": "Ambígua (mais de um candidato)",
    "rejeitada": "Associação rejeitada",
    "pendente": "Documento sem certame identificado",
}

# Identificadores de fonte que são publicação/catálogo, nunca certame.
_SECTION_ID = re.compile(r"^(?:DOU|DO)-?S?\d+$", re.I)
_CATALOG_HINTS = re.compile(r"^(?:catalogo|cat|lista)", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_external_id(competition_id) -> str:
    """Natureza do identificador externo, por regra explícita (nunca por suposição vaga)."""
    if not isinstance(competition_id, str) or not competition_id.strip():
        return "desconhecida"
    value = competition_id.strip()
    if _SECTION_ID.match(value):
        return "secao_publicacao"
    if _CATALOG_HINTS.match(value):
        return "catalogo"
    return "certame"


def _reviewer(decided_by, note):
    if not isinstance(decided_by, str) or not decided_by.strip():
        raise ValueError("autor da decisão obrigatório")
    if not isinstance(note, str) or not note.strip():
        raise ValueError("justificativa obrigatória")


# --- leitura ----------------------------------------------------------------

def contest_states(db_path) -> dict:
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        return {row[0]: row[1] for row in conn.execute(
            "SELECT id, estado_identidade FROM concursos_identidade")}


def containers(db_path) -> list[str]:
    """Concursos marcados como área de retenção (não são certames)."""
    return sorted(cid for cid, state in contest_states(db_path).items()
                  if state == "container_fonte")


def certame_ids(db_path) -> list[str]:
    """Ids de concursos que são certames de verdade (exclui containers)."""
    return sorted(cid for cid, state in contest_states(db_path).items()
                  if state != "container_fonte")


def current_association(conn, document_id: str) -> dict | None:
    row = conn.execute(
        "SELECT id,contest_id,state,evidence_json,score,decided_by,decided_at,note "
        "FROM associacoes_documento WHERE document_id=? "
        "ORDER BY decided_at DESC, rowid DESC LIMIT 1", (document_id,)).fetchone()
    if row is None:
        return None
    return {"id": row[0], "contest_id": row[1], "state": row[2],
            "evidence": _loads(row[3]), "score": row[4], "decided_by": row[5],
            "decided_at": row[6], "note": row[7]}


def _loads(raw):
    try:
        return json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}


# --- escrita ----------------------------------------------------------------

def set_contest_state(db_path, contest_id: str, state: str, *, decided_by: str, note: str,
                      dry_run: bool = True) -> dict:
    """Marca um concurso como certame ou container de fonte (idempotente)."""
    if state not in CONTEST_STATES:
        raise ValueError("estado de identidade inválido")
    _reviewer(decided_by, note)
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        row = conn.execute("SELECT estado_identidade FROM concursos_identidade WHERE id=?",
                           (contest_id,)).fetchone()
        if row is None:
            raise ValueError("concurso inexistente")
        changed = row[0] != state
    report = {"contest_id": contest_id, "de": row[0], "para": state, "alterado": changed,
              "dry_run": bool(dry_run)}
    if dry_run or not changed:
        return report
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute("UPDATE concursos_identidade SET estado_identidade=? WHERE id=?",
                     (state, contest_id))
    return report


def set_observation_type(db_path, observation_id: str, tipo: str, *,
                         dry_run: bool = True) -> dict:
    if tipo not in OBSERVATION_TYPES:
        raise ValueError("tipo de identidade inválido")
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        row = conn.execute("SELECT tipo_identidade FROM observacoes_concurso WHERE id=?",
                           (observation_id,)).fetchone()
        if row is None:
            raise ValueError("observação inexistente")
        changed = row[0] != tipo
    if not dry_run and changed:
        with closing(connect_documents(db_path)) as conn, conn:
            conn.execute("UPDATE observacoes_concurso SET tipo_identidade=? WHERE id=?",
                         (tipo, observation_id))
    return {"observation_id": observation_id, "de": row[0], "para": tipo,
            "alterado": changed, "dry_run": bool(dry_run)}


def record_association(db_path, document_id: str, contest_id, state: str, evidence: dict,
                       *, decided_by: str, note: str, score=None,
                       dry_run: bool = True) -> dict:
    """Registra uma decisão de associação (append-only, com histórico).

    ``contest_id`` pode ser ``None`` quando o estado é ``pendente`` (documento sem certame).
    Idempotente: repetir a mesma decisão (mesmo estado, destino e evidência) não duplica.
    """
    if state not in ASSOCIATION_STATES:
        raise ValueError("estado de associação inválido")
    # Rejeitar não exige destino: "este documento não pertence a certame identificado" é uma
    # decisão válida. Confirmar/candidatar/ambiguanar exigem o concurso pretendido.
    if state in ("confirmada", "candidata", "ambigua") and not contest_id:
        raise ValueError("associação não pendente exige concurso")
    if state == "pendente" and contest_id:
        raise ValueError("associação pendente não aponta para concurso")
    if not isinstance(evidence, dict) or not evidence:
        raise ValueError("evidência obrigatória")
    _reviewer(decided_by, note)
    payload = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        if not conn.execute("SELECT 1 FROM documentos WHERE id=?", (document_id,)).fetchone():
            raise ValueError("documento inexistente")
        if contest_id:
            target = conn.execute(
                "SELECT estado_identidade FROM concursos_identidade WHERE id=?",
                (contest_id,)).fetchone()
            if target is None:
                raise ValueError("concurso inexistente")
            if target[0] == "container_fonte":
                # Identidade de fonte nunca é identidade de certame.
                raise ValueError("container de fonte não é um certame associável")
        current = current_association(conn, document_id)
        same = (current is not None and current["state"] == state
                and current["contest_id"] == contest_id
                and json.dumps(current["evidence"], ensure_ascii=False, sort_keys=True) == payload)
    report = {"document_id": document_id, "contest_id": contest_id, "state": state,
              "duplicada": same, "dry_run": bool(dry_run)}
    if dry_run or same:
        return report
    association_id = str(uuid4())
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute(
            "INSERT INTO associacoes_documento (id,document_id,contest_id,state,evidence_json,"
            "score,decided_by,decided_at,note,supersedes_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (association_id, document_id, contest_id, state, payload,
             None if score is None else float(score), decided_by.strip(), _now(),
             note.strip(), current["id"] if current else None))
    report["id"] = association_id
    return report


# --- diagnóstico e reparação ------------------------------------------------

def identity_audit(db_path) -> dict:
    """Panorama da identidade: containers, tipos de identificador e associações."""
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        contests = conn.execute(
            "SELECT id, estado_identidade FROM concursos_identidade").fetchall()
        observations = conn.execute(
            "SELECT id, contest_id, source_url, competition_id, tipo_identidade "
            "FROM observacoes_concurso").fetchall()
        docs = conn.execute("SELECT id, contest_id FROM documentos").fetchall()
        assoc = {}
        for document_id, state in conn.execute(
                "SELECT document_id, state FROM associacoes_documento"):
            assoc[document_id] = state
        proposals = {row[0]: row[1] for row in conn.execute(
            "SELECT contest_id, COUNT(*) FROM propostas_campo GROUP BY contest_id")}

    container_ids = {cid for cid, state in contests if state == "container_fonte"}
    obs_by_contest = {}
    for observation_id, contest_id, source_url, competition_id, tipo in observations:
        obs_by_contest.setdefault(contest_id, []).append(
            {"observation_id": observation_id, "source_url": source_url,
             "competition_id": competition_id, "tipo_identidade": tipo})
    docs_by_contest = {}
    for document_id, contest_id in docs:
        docs_by_contest.setdefault(contest_id, []).append(document_id)

    suspects = []
    for contest_id, state in contests:
        if state == "container_fonte":
            continue
        for observation in obs_by_contest.get(contest_id, []):
            tipo = observation["tipo_identidade"]
            declared = classify_external_id(observation["competition_id"])
            if tipo != "certame" or declared != "certame":
                suspects.append({
                    "contest_id": contest_id,
                    "observation_id": observation["observation_id"],
                    "competition_id": observation["competition_id"],
                    "tipo_identidade": tipo,
                    "tipo_declarado": declared,
                    "documentos": len(docs_by_contest.get(contest_id, [])),
                    "motivo": ("identificador externo de fonte usado como identidade de "
                               "certame"),
                })
                break

    return {
        "version": IDENTITY_VERSION,
        "concursos": len(contests),
        "certames": len(contests) - len(container_ids),
        "containers": len(container_ids),
        "observacoes_por_tipo": _count(obs_by_contest, "tipo_identidade"),
        "documentos": len(docs),
        "documentos_em_container": sum(len(docs_by_contest.get(cid, []))
                                       for cid in container_ids),
        "documentos_com_associacao": len(assoc),
        "associacoes_por_estado": _count_states(assoc.values()),
        "propostas_em_container": sum(proposals.get(cid, 0) for cid in container_ids),
        "suspeitos": suspects,
        "limitacao": ("Container é área de retenção: não é certame e não entra em métricas "
                      "de cobertura. Documentos ali ficam pendentes até evidência suficiente."),
    }


def _count(items, key):
    out = {}
    for contest_id, rows in items.items():
        for row in rows:
            value = row[key]
            out[value] = out.get(value, 0) + 1
    return out


def _count_states(values):
    out = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return out


def _issuer_key(issuer) -> str | None:
    if not isinstance(issuer, str) or not issuer.strip():
        return None
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", issuer.lower()).split())


def repair_plan(db_path) -> dict:
    """Plano de reparação das identidades de fonte usadas como certame. Não grava nada.

    Para cada concurso cujo identificador externo é de publicação/catálogo:
    - o concurso vira ``container_fonte``;
    - cada documento recebe associação ``pendente`` com evidência (órgão, ato, data) e um
      ``grupo_candidato`` (órgão normalizado) para orientar a revisão humana.

    Nenhum certame novo é criado: um ato isolado não prova a identidade de um certame.
    """
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = conn.execute(
            """SELECT c.id, c.estado_identidade, o.id, o.competition_id, o.tipo_identidade,
                      o.source_url
               FROM concursos_identidade c
               JOIN observacoes_concurso o ON o.contest_id=c.id
               ORDER BY c.id""").fetchall()
        documents = {}
        for doc_id, contest_id, title, issuer, published, source_id, kind, tipo in conn.execute(
                "SELECT id, contest_id, title, issuer, published_at, source_identifier, kind, "
                "tipo_documental FROM documentos ORDER BY published_at, id"):
            documents.setdefault(contest_id, []).append(
                {"document_id": doc_id, "title": title, "issuer": issuer,
                 "published_at": published, "source_identifier": source_id,
                 "kind": kind, "tipo_documental": tipo})
        existing = {(row[0], row[1]) for row in conn.execute(
            "SELECT document_id, state FROM associacoes_documento")}
        contest_docs = {row[0]: row[1] for row in conn.execute(
            "SELECT contest_id, COUNT(*) FROM documentos GROUP BY contest_id")}
        proposals = {row[0]: row[1] for row in conn.execute(
            "SELECT contest_id, COUNT(*) FROM propostas_campo GROUP BY contest_id")}

    by_contest = {}
    for contest_id, state, observation_id, competition_id, tipo, source_url in rows:
        entry = by_contest.setdefault(contest_id, {"state": state, "observations": []})
        entry["observations"].append({
            "observation_id": observation_id, "competition_id": competition_id,
            "tipo_identidade": tipo, "source_url": source_url,
            "tipo_declarado": classify_external_id(competition_id)})

    actions = []
    for contest_id, entry in sorted(by_contest.items()):
        state = entry["state"]
        declared_types = {o["tipo_declarado"] for o in entry["observations"]}
        is_source_identity = (state == "container_fonte"
                              or any(o["tipo_identidade"] != "certame"
                                     for o in entry["observations"])
                              or "certame" not in declared_types)
        if not is_source_identity:
            continue
        precisa_estado = state != "container_fonte"
        precisa_tipo = any(o["tipo_identidade"] != o["tipo_declarado"]
                           for o in entry["observations"])
        com_associacao = {doc_id for doc_id, _ in existing}
        docs_sem_associacao = [d for d in documents.get(contest_id, [])
                               if d["document_id"] not in com_associacao]
        if not (precisa_estado or precisa_tipo or docs_sem_associacao):
            # Nada a corrigir: reparação já aplicada (e decisões humanas preservadas).
            continue
        primary = entry["observations"][0]
        observation_id = primary["observation_id"]
        competition_id = primary["competition_id"]
        tipo = primary["tipo_identidade"]
        source_url = primary["source_url"]
        declared = primary["tipo_declarado"]
        docs = documents.get(contest_id, [])
        groups = {}
        for doc in docs:
            key = _issuer_key(doc["issuer"])
            if key:
                group = groups.setdefault(key, {"orgao": doc["issuer"], "documentos": []})
                group["documentos"].append(doc["document_id"])
        actions.append({
            "contest_id": contest_id,
            "tipo_declarado": declared,
            "tipo_identidade": tipo,
            "competition_id": competition_id,
            "source_url": source_url,
            "estado_atual": state,
            "observacoes": entry["observations"],
            "acao": "marcar_container",
            "documentos": len(docs),
            "propostas": proposals.get(contest_id, 0),
            "grupos_candidatos": [
                {"chave": key, "documentos": group["documentos"],
                 "orgao": group["orgao"]}
                for key, group in sorted(groups.items())],
            "associacoes_pendentes_existentes": sum(
                1 for doc in docs if (doc["document_id"], "pendente") in existing),
            "amostra": [
                {"document_id": doc["document_id"], "title": doc["title"],
                 "issuer": doc["issuer"], "published_at": doc["published_at"],
                 "kind": doc["kind"], "tipo_documental": doc["tipo_documental"]}
                for doc in docs[:5]],
        })
    return {
        "version": IDENTITY_VERSION,
        "concursos_afetados": len(actions),
        "documentos_afetados": sum(a["documentos"] for a in actions),
        "propostas_afetadas": sum(a["propostas"] for a in actions),
        "acoes": actions,
        "limitacao": ("Nenhum certame é criado automaticamente. Documentos entram como "
                      "pendentes e a associação a um certame exige evidência e revisão."),
    }


def apply_repair(db_path, *, decided_by: str, note: str, dry_run: bool = True) -> dict:
    """Aplica o plano de reparação (idempotente). Só altera identidade e associações."""
    _reviewer(decided_by, note)
    plan = repair_plan(db_path)
    report = {"version": IDENTITY_VERSION, "dry_run": bool(dry_run),
              "concursos_marcados": 0, "observacoes_tipadas": 0,
              "associacoes_criadas": 0, "documentos": 0, "acoes": []}
    if dry_run:
        report["acoes"] = plan["acoes"]
        report["documentos"] = plan["documentos_afetados"]
        return report

    for action in plan["acoes"]:
        contest_id = action["contest_id"]
        change = set_contest_state(db_path, contest_id, "container_fonte",
                                   decided_by=decided_by, note=note, dry_run=False)
        if change["alterado"]:
            report["concursos_marcados"] += 1

        for observation in action["observacoes"]:
            if observation["tipo_identidade"] == observation["tipo_declarado"]:
                continue
            set_observation_type(db_path, observation["observation_id"],
                                 observation["tipo_declarado"], dry_run=False)
            report["observacoes_tipadas"] += 1
        group_of = {}
        for group in action["grupos_candidatos"]:
            for document_id in group["documentos"]:
                group_of[document_id] = group
        with closing(connect_documents(db_path)) as conn:
            docs = [row for row in conn.execute(
                "SELECT id, title, issuer, published_at, kind, tipo_documental "
                "FROM documentos WHERE contest_id=? ORDER BY published_at, id", (contest_id,))]
            atuais = {document_id: current_association(conn, document_id)
                      for document_id, *_ in docs}
        for document_id, title, issuer, published_at, kind, tipo in docs:
            atual = atuais.get(document_id)
            if atual is not None and atual["state"] != "pendente":
                # Decisão já tomada (por humano ou por fluxo posterior): não se sobrepõe.
                continue
            group = group_of.get(document_id, {})
            evidence = {
                "motivo": "identificador externo de fonte não identifica certame",
                "identificador_fonte": action["competition_id"],
                "fonte": action["source_url"],
                "orgao": issuer,
                "ato": title,
                "publicado_em": published_at,
                "tipo_documental": tipo or kind,
                "grupo_candidato": group.get("chave"),
            }
            result = record_association(
                db_path, document_id, None, "pendente", evidence,
                decided_by=decided_by, note=note, dry_run=False)
            report["documentos"] += 1
            if not result["duplicada"]:
                report["associacoes_criadas"] += 1
    return report


# --- fila de revisão de associações ----------------------------------------

def association_queue(db_path, *, limit=100, state=None) -> dict:
    """Documentos que precisam de decisão de associação, com evidência e candidatos.

    Não altera nada. ``state`` filtra por estado atual da associação.
    """
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        latest = {}
        for row in conn.execute(
                "SELECT id,document_id,contest_id,state,evidence_json,decided_at "
                "FROM associacoes_documento ORDER BY decided_at, rowid"):
            latest[row[1]] = {"id": row[0], "contest_id": row[2], "state": row[3],
                              "evidence": _loads(row[4]), "decided_at": row[5]}
        docs = {row[0]: {"document_id": row[0], "title": row[1], "issuer": row[2],
                         "published_at": row[3], "official_url": row[4],
                         "kind": row[5], "tipo_documental": row[6],
                         "contest_id": row[7]}
                for row in conn.execute(
                    "SELECT id,title,issuer,published_at,official_url,kind,tipo_documental,"
                    "contest_id FROM documentos")}

    items = []
    for document_id, entry in latest.items():
        if state and entry["state"] != state:
            continue
        doc = docs.get(document_id)
        if doc is None:
            continue
        items.append({
            "document_id": document_id,
            "documento": doc,
            "estado": entry["state"],
            "estado_label": STATE_LABELS.get(entry["state"], entry["state"]),
            "contest_id": entry["contest_id"],
            "evidencia": entry["evidence"],
            "decidido_em": entry["decided_at"],
        })
    items.sort(key=lambda item: (item["estado"] != "pendente",
                                 item["documento"].get("published_at") or "",
                                 item["document_id"]))
    counts = {}
    for entry in latest.values():
        counts[entry["state"]] = counts.get(entry["state"], 0) + 1
    return {"version": IDENTITY_VERSION, "total": len(items),
            "por_estado": counts, "itens": items[:max(0, int(limit))]}
