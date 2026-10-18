"""Identidade canônica de cargo: auditoria de rótulos, sugestões e decisões (Fase 35).

O extrator marca toda proposta cujo cargo não foi associado a uma identidade com o prefixo
``cargo do documento não reconciliado: <rótulo>``. Esse rótulo é **texto do documento**, não
uma identidade: pode ser um cargo literal, uma abreviação, um código, uma especialidade — ou
nem ser cargo (local de prova, conteúdo programático, escolaridade).

Este módulo faz três coisas, sem nunca decidir sozinho:

1. **Auditoria**: classifica a natureza de cada rótulo e mostra a origem (documento, tipo,
   página, trecho) e por que ele não tem identidade.
2. **Sugestões**: propõe correspondências **dentro do mesmo concurso**, com fatores
   estruturais explicados. Similaridade textual é apenas um dos fatores e nunca basta.
3. **Decisão**: registra a decisão humana (confirmar, rejeitar, manter ambíguo, reabrir) em
   ``reconciliacoes_cargo``, append-only, com estado, natureza, evidência e vínculo com a
   decisão anterior.

Regras de honestidade:

- dois cargos com o mesmo nome em concursos diferentes continuam identidades distintas;
- nomes parecidos não são fundidos sem evidência;
- o nome original do edital nunca é substituído pelo normalizado;
- confirmar identidade **não** confirma vagas, requisitos, prazos nem compatibilidade.
"""

from __future__ import annotations

import json
import re
import unicodedata
from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from radar.document_store import (RECONCILIATION_STATES, connect_documents, ensure_role,
                                  is_readable_schema, normalize_role, role_names_compatible)

ROLE_IDENTITY_VERSION = "role_identity_v1"
LABEL_PREFIX = "cargo do documento não reconciliado: "

# Naturezas do rótulo. Distintas de propósito: só as quatro primeiras podem virar cargo.
NATURES = (
    "cargo_literal",
    "cargo_com_codigo",
    "abreviacao",
    "especialidade",
    "codigo_sem_nome",
    "nao_e_cargo",
    "generico_sem_cargo",
)
CARGOLIKE_NATURES = ("cargo_literal", "cargo_com_codigo", "abreviacao", "especialidade")

NATURE_LABELS = {
    "cargo_literal": "Cargo literal do documento",
    "cargo_com_codigo": "Código + nome do cargo",
    "abreviacao": "Abreviação de cargo",
    "especialidade": "Especialidade/área de atuação",
    "codigo_sem_nome": "Apenas código, sem nome",
    "nao_e_cargo": "Rótulo de outro campo (não é cargo)",
    "generico_sem_cargo": "Rótulo genérico sem cargo identificável",
}

# Estados de correspondência (vocabulário mínimo da fase).
MATCH_STATES = (
    "exata",
    "alias",
    "provavel",
    "ambigua",
    "duplicata_de_identidade",
    "rejeitada",
    "confirmada",
    "evidencia_insuficiente",
    "nao_e_cargo",
)
MATCH_LABELS = {
    "exata": "Correspondência exata sustentada por evidência",
    "alias": "Alias equivalente sustentado por evidência",
    "provavel": "Candidato provável (aguarda revisão)",
    "ambigua": "Ambíguo entre várias identidades",
    "duplicata_de_identidade": "Há duas identidades canônicas iguais no concurso",
    "rejeitada": "Correspondência rejeitada por decisão humana",
    "confirmada": "Correspondência confirmada por decisão humana",
    "evidencia_insuficiente": "Evidência insuficiente",
    "nao_e_cargo": "Não é um cargo individual identificável",
}

ACTION_LABELS = {
    "confirmar_correspondencia": "Confirmar correspondência (decisão humana)",
    "consolidar_identidade_duplicada": "Consolidar identidade duplicada (decisão humana)",
    "criar_identidade_a_partir_do_rotulo": "Criar identidade a partir do rótulo",
    "revisar_documento": "Revisar documento antes de decidir",
    "nao_reconciliar_como_cargo": "Não reconciliar como cargo",
    "manter_ambigua": "Manter ambígua",
    "decisao_registrada": "Decisão registrada; nada pendente",
}

# Marcadores de que o rótulo é de outro campo, não de cargo.
_NOT_CARGO = re.compile(
    r"^(local de prova|conteúdo programático|conteudo programatico|escolaridade declarada|"
    r"requisito sem cargo|data do cronograma|total do quadro|edição com múltiplos atos|"
    r"edicao com multiplos atos|vagas totais|quadro de vagas)", re.I)
_ESPECIALIDADE = re.compile(
    r"área de atuação|area de atuacao|especialidade|especialista em", re.I)
# Abreviação é marcada por estrutura, não por "parecer sigla": sigla entre parênteses
# ("(PST)"), token com ponto ("PROF.") ou numeral romano depois de travessão ("PROFESSOR IV").
# Um nome todo em maiúsculas NÃO é abreviação — foi o falso positivo que classificava
# "PROFESSOR ORIENTADOR DE ESTÁGIO..." como abreviação por causa da letra inicial.
_SIGLA = re.compile(r"\((?:[A-Z]{2,6})\)")
_DOT_ABBREV = re.compile(r"\b[A-Z]{2,6}\.")
# Sigla/numeral romano: token curto em maiúsculas (PII, PST, PAS, IV) que não é palavra
# comum. Nomes inteiros em maiúsculas têm tokens longos e não caem aqui.
_SHORT_UPPER = re.compile(r"\b[A-ZÀ-Þ]{2,4}\b")
_STOPWORDS = {"DE", "DA", "DO", "DAS", "DOS", "EM", "NA", "NO", "NAS", "NOS", "E", "A", "O",
              "AS", "OS", "AO", "AOS", "OU", "COM", "POR", "PARA", "NÍVEL", "NIVEL"}
_CODE_PREFIX = re.compile(r"^(\d{2,5})\s*[-–—.)]?\s*")
_TRAILING_ANNOTATION = re.compile(r"\s+—\s+.*$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(text) -> str:
    return normalize_role(text)


def _label_of(reason) -> str | None:
    """Rótulo a partir do motivo de ambiguidade do extrator (texto original)."""
    if not isinstance(reason, str) or not reason.startswith(LABEL_PREFIX):
        return None
    raw = reason[len(LABEL_PREFIX):]
    # A anotação depois de " — " é justificativa do extrator, não parte do rótulo.
    label = _TRAILING_ANNOTATION.sub("", raw).strip()
    return label or None


def classify_label(label) -> str:
    """Natureza do rótulo, por marcadores explícitos — nunca por adivinhação."""
    if not isinstance(label, str) or not label.strip():
        return "generico_sem_cargo"
    text = " ".join(label.split())
    if _NOT_CARGO.match(text):
        return "nao_e_cargo"
    if _CODE_PREFIX.match(text):
        rest = text[_CODE_PREFIX.match(text).end():].strip()
        return "cargo_com_codigo" if rest else "codigo_sem_nome"
    if _ESPECIALIDADE.search(text):
        return "especialidade"
    if _SIGLA.search(text) or _DOT_ABBREV.search(text):
        return "abreviacao"
    if any(token not in _STOPWORDS for token in _SHORT_UPPER.findall(text)):
        return "abreviacao"
    # Rótulo muito curto ou sem letras: genérico.
    letters = [ch for ch in text if ch.isalpha()]
    if len(letters) < 4:
        return "generico_sem_cargo"
    return "cargo_literal"


def _contest_label_rows(db_path):
    """Rótulos distintos por concurso, com a primeira evidência documental de cada um."""
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = conn.execute("""
            SELECT p.contest_id, p.ambiguity_reason, p.field_name, p.value_json,
                   p.extracted_at, d.title, d.tipo_documental, d.published_at, d.id,
                   e.page_number, e.quote, e.version_id, p.id
            FROM propostas_campo p
            JOIN evidencias e ON e.id=p.evidence_id
            JOIN versoes_documento v ON v.id=e.version_id
            JOIN documentos d ON d.id=v.document_id
            WHERE p.ambiguity_reason LIKE 'cargo do documento não reconciliado:%'
            ORDER BY p.contest_id, d.published_at, p.id
            """).fetchall()
        cargos = {}
        for contest_id, role_id, name, specialty, code in conn.execute(
                "SELECT contest_id, id, name, specialty, code FROM cargos_identidade"):
            cargos.setdefault(contest_id, []).append(
                {"role_id": role_id, "name": name, "specialty": specialty, "code": code})
        decisions = {}
        for row in conn.execute("""
                SELECT contest_id, label, role_id, state, reconciled_at, reviewer, reason,
                       nature, evidence_json, previous_id, id
                FROM reconciliacoes_cargo ORDER BY reconciled_at, rowid"""):
            decisions[(row[0], row[1])] = {
                "role_id": row[2], "state": row[3], "decided_at": row[4],
                "reviewer": row[5], "reason": row[6], "nature": row[7],
                "evidence": json.loads(row[8]) if row[8] else None,
                "previous_id": row[9], "decision_id": row[10]}
    return rows, cargos, decisions


def _duplicate_roles(cargos: list[dict]) -> dict:
    """Identidades canônicas duplicadas no mesmo concurso (mesmo nome e código).

    Duplicata é problema de higiene de identidade, não ambiguidade de correspondência: o
    rótulo aponta para o mesmo cargo duas vezes. Consolidar exige decisão humana.
    """
    grouped = {}
    for cargo in cargos:
        key = (_norm(cargo["name"]), str(cargo.get("code") or ""))
        grouped.setdefault(key, []).append(cargo["role_id"])
    return {key: ids for key, ids in grouped.items() if len(ids) > 1}


def _suggest(label: str, nature: str, cargos: list[dict]) -> list[dict]:
    """Candidatos de correspondência **no mesmo concurso**, com fatores explicados.

    ``pontuacao`` é estrutural e reproduzível (não é probabilidade). Nenhum candidato é
    promovido: só a decisão humana confirma.
    """
    if nature not in CARGOLIKE_NATURES:
        return []
    target = label
    code = None
    match = _CODE_PREFIX.match(label)
    if match:
        code = match.group(1)
        target = label[match.end():].strip() or label
    norm_target = _norm(target)
    suggestions = []
    for cargo in cargos:
        factors = []
        score = 0
        norm_name = _norm(cargo["name"])
        same_name = bool(norm_target) and norm_target == norm_name
        same_full = _norm(label) == norm_name
        if same_full:
            factors.append({"fator": "nome_identico", "pontos": 40,
                            "motivo": "rótulo e identidade têm o mesmo nome normalizado"})
            score += 40
        elif same_name:
            factors.append({"fator": "nome_identico_sem_codigo", "pontos": 35,
                            "motivo": "mesmo nome depois de remover o código do rótulo"})
            score += 35
        if code and cargo.get("code") and code == str(cargo["code"]):
            factors.append({"fator": "codigo_oficial", "pontos": 40,
                            "motivo": f"código {code} igual ao da identidade"})
            score += 40
        if not same_full and not same_name and norm_target and norm_name:
            if (norm_name.startswith(norm_target + " ")
                    or norm_target.startswith(norm_name + " ")):
                factors.append({"fator": "prefixo_de_nome", "pontos": 25,
                                "motivo": "um nome é prefixo de palavra do outro "
                                          "(abreviação possível)"})
                score += 25
        if nature == "especialidade" and cargo.get("specialty"):
            if _norm(cargo["specialty"]) and _norm(cargo["specialty"]) in _norm(label):
                factors.append({"fator": "especialidade_confere", "pontos": 15,
                                "motivo": "a especialidade da identidade aparece no rótulo"})
                score += 15
        # Candidato exige evidência estrutural: nome/código/prefixo/especialidade.
        # "Compartilhar uma palavra" não basta para sugerir identidade.
        if score < 25:
            continue
        code_match = bool(code and cargo.get("code") and code == str(cargo["code"]))
        name_compatible = same_name or role_names_compatible(target, cargo["name"])
        if code_match and not name_compatible:
            # Código igual com nome incompatível é pista fraca: não vira alias.
            factors.append({"fator": "codigo_sem_nome_compativel", "pontos": 0,
                            "motivo": "código confere, mas o nome do rótulo não "
                                      "corresponde ao da identidade"})
        if same_full:
            state = "exata"
        elif same_name or (code_match and name_compatible):
            state = "alias"
        else:
            state = "provavel"
        suggestions.append({"role_id": cargo["role_id"], "role_name": cargo["name"],
                            "specialty": cargo["specialty"], "code": cargo["code"],
                            "state": state, "pontuacao": score, "fatores": factors})
    rank = {"exata": 0, "alias": 1, "provavel": 2, "ambigua": 3}
    suggestions.sort(key=lambda item: (rank.get(item["state"], 9), -item["pontuacao"],
                                       item["role_name"] or ""))
    suggestions = suggestions[:5]
    # Empate no melhor nível de evidência com identidades diferentes é ambiguidade.
    if len(suggestions) > 1:
        best_rank = rank.get(suggestions[0]["state"], 9)
        same_rank = [item for item in suggestions
                     if rank.get(item["state"], 9) == best_rank]
        top = max(item["pontuacao"] for item in same_rank)
        tied = [item for item in same_rank if item["pontuacao"] == top]
        if len({item["role_id"] for item in tied}) > 1:
            for item in tied:
                item["state"] = "ambigua"
                item["fatores"].append({"fator": "empate_estrutural", "pontos": 0,
                                        "motivo": f"{len(tied)} identidades com a mesma "
                                                  "pontuação estrutural"})
    return suggestions


def label_inventory(db_path, *, contest_id=None, limit=5000) -> dict:
    """Diagnóstico dos rótulos: natureza, origem, candidatos e estado da decisão."""
    rows, cargos, decisions = _contest_label_rows(db_path)
    grouped = {}
    for (cid, reason, field, value, extracted_at, title, tipo, published, document_id,
         page, quote, version_id, proposal_id) in rows:
        label = _label_of(reason)
        if label is None:
            continue
        if contest_id and cid != contest_id:
            continue
        key = (cid, label)
        entry = grouped.get(key)
        if entry is None:
            nature = classify_label(label)
            suggestions = _suggest(label, nature, cargos.get(cid, []))
            decision = decisions.get(key)
            entry = grouped[key] = {
                "contest_id": cid, "label": label, "nature": nature,
                "nature_label": NATURE_LABELS[nature],
                "normalized": _norm(label),
                "proposals": 0, "fields": set(), "documents": {}, "pages": set(),
                "first_evidence": None, "suggestions": suggestions,
                "cargo_count": len(cargos.get(cid, [])),
                "decision": decision,
            }
        entry["proposals"] += 1
        entry["fields"].add(field)
        entry["documents"][document_id] = title
        if page is not None:
            entry["pages"].add(page)
        if entry["first_evidence"] is None:
            entry["first_evidence"] = {
                "document_id": document_id, "document_title": title,
                "tipo_documental": tipo, "published_at": published,
                "page_number": page, "quote": quote, "version_id": version_id,
                "proposal_id": proposal_id,
            }

    items = []
    for entry in grouped.values():
        decision = entry["decision"]
        duplicates = _duplicate_roles(cargos.get(entry["contest_id"], []))
        duplicate_ids = set()
        for ids in duplicates.values():
            duplicate_ids.update(ids)
        if decision and decision["state"] == "confirmada":
            state = "confirmada"
        elif decision and decision["state"] == "rejeitada":
            state = "rejeitada"
        elif decision and decision["state"] == "ambigua":
            state = "ambigua"
        elif entry["nature"] == "nao_e_cargo":
            state = "nao_e_cargo"
        elif not entry["suggestions"]:
            state = "evidencia_insuficiente"
        else:
            top_score = entry["suggestions"][0]["pontuacao"]
            top = [item for item in entry["suggestions"]
                   if item["pontuacao"] == top_score]
            distinct = {(_norm(item["role_name"]), str(item.get("code") or ""))
                        for item in top}
            if len(distinct) > 1:
                state = "ambigua"
            elif any(item["role_id"] in duplicate_ids for item in top):
                # Mesmo cargo, duas linhas canônicas: consolidar é decisão de identidade.
                state = "duplicata_de_identidade"
            else:
                state = top[0]["state"]
        # Ação proposta: sempre uma decisão humana, nunca executada aqui.
        if state in ("confirmada", "rejeitada"):
            action = "decisao_registrada"
        elif state == "nao_e_cargo":
            action = "nao_reconciliar_como_cargo"
        elif state == "duplicata_de_identidade":
            action = "consolidar_identidade_duplicada"
        elif state in ("exata", "alias", "provavel"):
            action = "confirmar_correspondencia"
        elif entry["cargo_count"] == 0 and entry["nature"] in CARGOLIKE_NATURES:
            action = "criar_identidade_a_partir_do_rotulo"
        elif state == "ambigua":
            action = "manter_ambigua"
        else:
            action = "revisar_documento"
        role_names = {cargo["role_id"]: cargo["name"]
                      for cargo in cargos.get(entry["contest_id"], [])}
        decision_role = (role_names.get(decision["role_id"])
                         if decision and decision.get("role_id") else None)
        items.append(dict(entry, fields=sorted(entry["fields"]),
                          documents=[{"document_id": k, "title": v}
                                     for k, v in entry["documents"].items()],
                          pages=sorted(entry["pages"]), state=state,
                          state_label=MATCH_LABELS[state],
                          acao_proposta=action,
                          acao_label=ACTION_LABELS[action],
                          decision_role_name=decision_role,
                          identidades_duplicadas=sorted(duplicate_ids)))
    items.sort(key=lambda item: (item["contest_id"], item["label"]))
    by_nature, by_state, by_contest = {}, {}, {}
    for item in items:
        by_nature[item["nature"]] = by_nature.get(item["nature"], 0) + 1
        by_state[item["state"]] = by_state.get(item["state"], 0) + 1
        by_contest[item["contest_id"]] = by_contest.get(item["contest_id"], 0) + 1
    return {
        "version": ROLE_IDENTITY_VERSION, "generated_at": _now(),
        "total_rotulos": len(items),
        "por_natureza": by_nature, "por_estado": by_state,
        "concursos": len(by_contest),
        "itens": items[:max(0, int(limit))],
        "limitacao": ("Natureza vem de marcadores explícitos do rótulo, não de julgamento "
                      "automático. Sugestão não é identidade confirmada; confirmar cargo não "
                      "confirma vagas, requisitos nem prazos."),
    }


def _latest_decision(conn, contest_id, label):
    row = conn.execute("""
        SELECT id, role_id, state, reconciled_at, reviewer, reason, nature, evidence_json
        FROM reconciliacoes_cargo WHERE contest_id=? AND label=?
        ORDER BY reconciled_at DESC, rowid DESC LIMIT 1""",
        (contest_id, label)).fetchone()
    if not row:
        return None
    return {"decision_id": row[0], "role_id": row[1], "state": row[2],
            "decided_at": row[3], "reviewer": row[4], "reason": row[5],
            "nature": row[6], "evidence": json.loads(row[7]) if row[7] else None}


def decide_reconciliation(db_path, *, contest_id: str, label: str, state: str,
                          reviewer: str, reason: str, role_id: str | None = None,
                          nature: str | None = None, evidence: dict | None = None,
                          expected_previous_id: str | None = None,
                          dry_run: bool = True) -> dict:
    """Registra decisão humana de identidade (append-only, com estado e histórico).

    Regras:

    - ``confirmada`` exige ``role_id`` do **mesmo concurso** e rótulo evidenciado;
    - ``rejeitada`` e ``ambigua`` não exigem cargo (não se inventa identidade);
    - mudar um vínculo já confirmado exige que a decisão vigente seja ``reaberta`` —
      sobrescrever em silêncio é o erro que a fase proíbe;
    - ``expected_previous_id`` protege contra decisão concorrente (ciclo/outro operador).
    """
    if state not in RECONCILIATION_STATES:
        raise ValueError("estado de reconciliação inválido")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("responsável obrigatório")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("justificativa obrigatória")
    if not isinstance(label, str) or not label.strip():
        raise ValueError("rótulo obrigatório")
    if nature is not None and nature not in NATURES:
        raise ValueError("natureza inválida")
    label = " ".join(label.split())

    # Validação e gravação na mesma conexão e sob o mesmo lock de escrita:
    # separar as duas abriria janela para duas decisões concorrentes passarem.
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        conn.execute("BEGIN IMMEDIATE")
        try:
            if not conn.execute("SELECT 1 FROM concursos_identidade WHERE id=?",
                                (contest_id,)).fetchone():
                raise ValueError("concurso inexistente")
            labels = {" ".join(_label_of(row[0]).split())
                      for row in conn.execute(
                          "SELECT DISTINCT ambiguity_reason FROM propostas_campo "
                          "WHERE contest_id=?", (contest_id,))
                      if _label_of(row[0]) is not None}
            if label not in labels:
                raise ValueError("rótulo sem evidência documental neste concurso")
            latest = _latest_decision(conn, contest_id, label)
            if expected_previous_id is not None:
                current_id = latest["decision_id"] if latest else None
                if expected_previous_id != current_id:
                    raise ValueError("decisão mudou desde a abertura; reavalie o rótulo")
            if state == "confirmada":
                if not role_id:
                    raise ValueError("confirmar exige cargo")
                if not conn.execute(
                        "SELECT 1 FROM cargos_identidade WHERE id=? AND contest_id=?",
                        (role_id, contest_id)).fetchone():
                    raise ValueError("cargo de outro concurso")
                if latest and latest["state"] == "confirmada" and \
                        latest["role_id"] != role_id:
                    raise ValueError(
                        "rótulo já confirmado em outro cargo; reabra antes de alterar")
                if latest and latest["state"] not in ("confirmada", "reaberta"):
                    raise ValueError(
                        "decisão vigente não é confirmação nem reabertura; reabra antes")
            else:
                if role_id:
                    raise ValueError("estado não confirmado não aceita cargo")
                role_id = None
                if state == "reaberta" and latest is None:
                    raise ValueError("não há decisão vigente para reabrir")
        except Exception:
            conn.rollback()
            raise

        payload = {"version": ROLE_IDENTITY_VERSION, "contest_id": contest_id,
                   "label": label, "state": state, "role_id": role_id,
                   "nature": nature or classify_label(label),
                   "evidence": evidence,
                   "previous_id": latest["decision_id"] if latest else None,
                   "dry_run": bool(dry_run)}
        if dry_run:
            conn.rollback()
            payload["would_write"] = True
            return payload

        decision_id = str(uuid4())
        at = _now()
        conn.execute("""INSERT INTO reconciliacoes_cargo
            (id,contest_id,label,role_id,reconciled_at,reviewer,reason,state,nature,
             evidence_json,previous_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (decision_id, contest_id, label, role_id, at, reviewer.strip(), reason.strip(),
             state, nature or classify_label(label),
             json.dumps(evidence, ensure_ascii=False) if evidence else None,
             latest["decision_id"] if latest else None))
        conn.commit()

    payload.update({"decision_id": decision_id, "decided_at": at, "dry_run": False,
                    "would_write": False})
    return payload


def reconciliation_history(db_path, *, contest_id: str, label: str) -> dict:
    """Histórico completo de decisões de um rótulo, em ordem cronológica."""
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = conn.execute("""
            SELECT r.id, r.role_id, r.state, r.reconciled_at, r.reviewer, r.reason,
                   r.nature, r.evidence_json, r.previous_id, c.name
            FROM reconciliacoes_cargo r
            LEFT JOIN cargos_identidade c ON c.id = r.role_id
            WHERE r.contest_id=? AND r.label=?
            ORDER BY r.reconciled_at, r.rowid""", (contest_id, label)).fetchall()
    items = [{"decision_id": row[0], "role_id": row[1], "state": row[2],
              "decided_at": row[3], "reviewer": row[4], "reason": row[5],
              "nature": row[6],
              "evidence": json.loads(row[7]) if row[7] else None,
              "previous_id": row[8], "role_name": row[9]} for row in rows]
    return {"version": ROLE_IDENTITY_VERSION, "contest_id": contest_id, "label": label,
            "total": len(items), "decisoes": items,
            "vigente": items[-1] if items else None,
            "limitacao": ("Histórico append-only: decisões anteriores não são apagadas. "
                          "A decisão vigente é a mais recente.")}


def create_role_for_label(db_path, *, contest_id: str, label: str, reviewer: str,
                          reason: str, specialty: str | None = None,
                          dry_run: bool = True) -> dict:
    """Cria identidade canônica a partir do rótulo, **por decisão humana**.

    Usado quando o concurso não tem nenhuma identidade de cargo para receber o rótulo. A
    identidade preserva o nome literal do documento; o normalizado fica só para comparação.
    """
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("responsável obrigatório")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("justificativa obrigatória")
    label = " ".join((label or "").split())
    if not label:
        raise ValueError("rótulo obrigatório")
    nature = classify_label(label)
    if nature not in CARGOLIKE_NATURES:
        raise ValueError(f"rótulo não é cargo ({NATURE_LABELS[nature]})")
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        labels = {" ".join(_label_of(row[0]).split())
                  for row in conn.execute(
                      "SELECT DISTINCT ambiguity_reason FROM propostas_campo "
                      "WHERE contest_id=?", (contest_id,))
                  if _label_of(row[0]) is not None}
        if label not in labels:
            raise ValueError("rótulo sem evidência documental neste concurso")
        observation = conn.execute(
            "SELECT id FROM observacoes_concurso WHERE contest_id=? "
            "ORDER BY observed_at LIMIT 1", (contest_id,)).fetchone()
        existing = conn.execute(
            "SELECT id FROM cargos_identidade WHERE contest_id=? AND name=? "
            "AND specialty IS ?", (contest_id, label, specialty)).fetchone()
    if existing:
        return {"version": ROLE_IDENTITY_VERSION, "role_id": existing[0],
                "created": False, "dry_run": bool(dry_run), "label": label,
                "nature": nature, "specialty": specialty}
    if dry_run:
        return {"version": ROLE_IDENTITY_VERSION, "role_id": None, "created": False,
                "would_create": True, "dry_run": True, "label": label,
                "nature": nature, "specialty": specialty}
    if observation is None:
        raise ValueError("concurso sem observação de origem; identidade não pode ser criada")
    role_id = ensure_role(db_path, contest_id, observation[0], label, specialty=specialty)
    return {"version": ROLE_IDENTITY_VERSION, "role_id": role_id, "created": True,
            "dry_run": False, "label": label, "nature": nature,
            "specialty": specialty}


def reconciliation_queue(db_path, *, contest_id=None, nature=None, state=None,
                         min_candidates=0, limit=100, offset=0) -> dict:
    """Fila de reconciliação ordenada por utilidade (propostas e evidência)."""
    limit = int(limit)
    offset = int(offset)
    if limit < 1 or limit > 500:
        raise ValueError("limite fora da faixa")
    if offset < 0:
        raise ValueError("deslocamento inválido")
    if nature and nature not in NATURES:
        raise ValueError("natureza inválida")
    if state and state not in MATCH_STATES:
        raise ValueError("estado inválido")
    report = label_inventory(db_path, contest_id=contest_id, limit=100000)
    items = report["itens"]
    if nature:
        items = [item for item in items if item["nature"] == nature]
    if state:
        items = [item for item in items if item["state"] == state]
    if min_candidates:
        items = [item for item in items if len(item["suggestions"]) >= int(min_candidates)]

    def utility(item):
        # Utilidade: quantidade de propostas resolvidas × qualidade da sugestão.
        top = item["suggestions"][0]["pontuacao"] if item["suggestions"] else 0
        return (-(item["proposals"] * max(top, 1)), item["contest_id"], item["label"])

    items.sort(key=utility)
    total = len(items)
    return {"version": ROLE_IDENTITY_VERSION, "generated_at": _now(),
            "total": total, "limit": limit, "offset": offset,
            "has_more": offset + limit < total,
            "itens": items[offset:offset + limit],
            "limitacao": ("Ordenação por utilidade estrutural: propostas afetadas e força da "
                          "sugestão. Sugestão não é confirmação.")}
