"""Requisitos em **seções numeradas** do edital, com ou sem código de cargo.

Alguns editais (ex.: Quadrix) publicam os requisitos no corpo, sob um cabeçalho de seção
``N.M NOME [ (CARGO NNN) ]`` seguido de subitens numerados ``N.M.k Requisitos: …``. O
código pode estar ausente (só o nome da seção). Esta camada:

1. Reconhece a seção e o subitem de requisitos pela **numeração** (``N.M`` casa ``N.M.k``).
2. Extrai o texto literal do requisito.
3. Quando há código no cabeçalho, delega a identidade ao fluxo por código (Fase 15).
4. Quando não há código, associa por **nome** da seção à tabela oficial de cargos, com
   estados explícitos — **nunca** por escolaridade.

Nada é promovido a validado; tudo continua proposta com evidência.
"""

from __future__ import annotations

import json
import re
from contextlib import closing

from radar.document_store import connect_documents, ensure_role, role_names_compatible
from radar.edital_requirements import _courses_from, classify_si_compatibility, parse_code_group
from radar.role_reconciliation import _clean_label

# Seção numerada: "N.M NOME" — o nome vai até o primeiro subitem "N.M.k".
# `(?<![\d.])` impede casar o "N.M" interno de um subitem "N.M.k".
_SECTION = re.compile(r"(?<![\d.])(\d+\.\d+)\s+(.+?)\s+(?=\1\.\d+\s)", re.S)
# Subitem de requisitos: "N.M.k Requisitos:".
_REQ_ITEM = re.compile(r"(?<!\d)(\d+)\.(\d+)\.(\d+)\s+Requisitos\s*:\s*", re.I)
# Código embutido no cabeçalho: "(CARGO 200)" / "(CÓDIGO 200)" / "(CÓDIGOS 200 ATÉ 206)".
_CODE_IN_NAME = re.compile(r"\(\s*(?:CARGO|C[ÓO]DIGOS?)\s+([^)]*)\)", re.I)
# Fim do valor: próximo subitem "N.M.k ".
_NEXT_ITEM = re.compile(r"(?<!\d)\d+\.\d+\.\d+\s")


def parse_sections(text: str) -> list[dict]:
    """Divide o texto em seções numeradas: ``{num, name, code_clause, body}``.

    ``name`` é o nome do cargo/serviço (código embutido removido); ``code_clause`` é o
    bloco de código literal quando presente.
    """
    if not isinstance(text, str) or not text:
        return []
    heads = []
    for match in _SECTION.finditer(text):
        name_raw = " ".join(match.group(2).split())
        code_clause = None
        code_match = _CODE_IN_NAME.search(name_raw)
        if code_match:
            code_clause = code_match.group(0)
            name_raw = (name_raw[:code_match.start()] + name_raw[code_match.end():]).strip()
        name = name_raw.strip(" –—-")
        heads.append({"num": match.group(1), "name": name, "code_clause": code_clause,
                      "start": match.start(), "body_start": match.end()})
    for index, head in enumerate(heads):
        head["body_end"] = heads[index + 1]["start"] if index + 1 < len(heads) else len(text)
    return heads


def _requirement_value(text: str, body_start: int, body_end: int, section_num: str):
    """Primeiro subitem ``N.M.k Requisitos:`` da seção, com valor e offsets."""
    body = text[body_start:body_end]
    for match in _REQ_ITEM.finditer(body):
        if f"{match.group(1)}.{match.group(2)}" != section_num:
            continue
        value_start = body_start + match.end()
        nxt = _NEXT_ITEM.search(body, match.end())
        value_end = body_start + (nxt.start() if nxt else len(body))
        raw = text[value_start:value_end]
        value = raw.strip()
        if not value:
            return None
        return {"value": value, "start": value_start, "end": value_start + len(raw.rstrip())}
    return None


def extract_section_education(blocks: list[dict], contest_id: str, *,
                              label_prefix: str, method: str = "requisitos-secao") -> list[dict]:
    """Propõe ``education``/``accepted_courses``/``si_compatibility`` por seção numerada.

    Seção com código → rótulo por código (identidade pelo fluxo de código). Seção sem
    código → rótulo pelo **nome** da seção (associação por nome na reconciliação).
    """
    proposals = []
    for index, block in enumerate(blocks):
        if block.get("page_number") is None:
            continue
        text = block["text"]
        if "equisito" not in text.lower():  # "Requisitos"/"REQUISITOS"/"requisito"
            continue
        for head in parse_sections(text):
            req = _requirement_value(text, head["body_start"], head["body_end"], head["num"])
            if req is None:
                continue
            value = req["value"]
            codes = parse_code_group(head["code_clause"]) if head["code_clause"] else []
            if codes:
                for code in codes:
                    label = code if len(codes) > 1 else f"{code} {head['name']}"
                    ambiguity = (f"{label_prefix}{code} — bloco {head['code_clause'].strip()}"
                                 if len(codes) > 1 else label_prefix + label)
                    proposals.extend(_emit(contest_id, index, block, req, value, label, ambiguity, method))
            else:
                label = head["name"]
                ambiguity = f"{label_prefix}{label}"
                proposals.extend(_emit(contest_id, index, block, req, value, label, ambiguity, method))
    return proposals


def _emit(contest_id, index, block, req, value, label, ambiguity, method):
    evidence = dict(block_index=index, quote=block["text"][req["start"]:req["end"]],
                    start_offset=req["start"], end_offset=req["end"],
                    page_number=block.get("page_number"), header="Requisitos",
                    section=None, role_label=label)
    out = [dict(contest_id=contest_id, role_id=None, field_name="education",
                value_json=json.dumps(value[:600]), value_type="string",
                extraction_method=method, ambiguity_reason=ambiguity, evidence=dict(evidence))]
    courses = _courses_from(value)
    if courses:
        out.append(dict(contest_id=contest_id, role_id=None, field_name="accepted_courses",
                        value_json=json.dumps(courses), value_type="string",
                        extraction_method=method, ambiguity_reason=ambiguity, evidence=dict(evidence)))
    state, reason = classify_si_compatibility(value)
    out.append(dict(contest_id=contest_id, role_id=None, field_name="si_compatibility",
                    value_json=json.dumps(state), value_type="string",
                    extraction_method="classificacao-si",
                    ambiguity_reason=f"{ambiguity} — {reason}", evidence=dict(evidence)))
    return out


def reconcile_sections_by_name(db_path, contest_id: str, observation_id: str,
                               cargo_table: list[dict], proposals: list[dict]) -> dict:
    """Associa seções sem código aos cargos oficiais **por nome** (nunca por escolaridade).

    - Nome exatamente igual a **um** cargo oficial → ``explicita`` (associa ``role_id``).
    - Nome exatamente igual a **vários** cargos → ``ambigua`` (não associa).
    - Sem igualdade, mas com tokens significativos em comum com **um** cargo → ``revisao``
      (candidata; não associa).
    - Sem correspondência → ``sem_cargo``.
    """
    by_name: dict[str, list[dict]] = {}
    for role in cargo_table:
        by_name.setdefault(_norm(role["name"]), []).append(role)

    result = {"explicita": 0, "sustentada": 0, "revisao": 0, "ambigua": 0, "sem_cargo": 0,
              "assigned": 0}
    for proposal in proposals:
        if proposal.get("role_id"):
            continue
        label = _section_label(proposal.get("ambiguity_reason"))
        if label is None:
            continue  # tem código: tratado pelo fluxo de código
        norm = _norm(label)
        exact = by_name.get(norm, [])
        if len(exact) == 1:
            role = exact[0]
            try:
                role_id = ensure_role(db_path, contest_id, observation_id, role["name"], code=role.get("code"))
            except ValueError:
                result["ambigua"] += 1  # conflito de identidade: não associa em silêncio
                continue
            proposal["role_id"] = role_id
            proposal["ambiguity_reason"] = (
                f"associado por nome exato de seção: {role['name']}"
                + (f" (código {role['code']})" if role.get("code") else ""))
            result["explicita"] += 1
            result["assigned"] += 1
        elif len(exact) > 1:
            result["ambigua"] += 1
            proposal["ambiguity_reason"] = (
                f"seção '{label}' corresponde a {len(exact)} cargos oficiais — revisar")
        else:
            candidates = [r for r in cargo_table if role_names_compatible(label, r["name"])]
            if len(candidates) == 1:
                result["revisao"] += 1
                proposal["ambiguity_reason"] = (
                    f"seção '{label}' sem código; candidato único por nome: "
                    f"{candidates[0]['name']} — revisar")
            elif len(candidates) > 1:
                result["ambigua"] += 1
                names = "; ".join(sorted({r["name"] for r in candidates})[:4])
                proposal["ambiguity_reason"] = (
                    f"seção '{label}' sem código; candidatos: {names} — revisar")
            else:
                result["sem_cargo"] += 1
                proposal["ambiguity_reason"] = f"seção '{label}' sem cargo oficial correspondente"
    return result


def _norm(text: str) -> str:
    from radar.document_store import normalize_role
    return normalize_role(text)


def _section_label(reason) -> str | None:
    """Rótulo de seção **sem código** (não começa por número de código).

    Remove apenas anotações **conhecidas** do extrator (não qualquer travessão em —,
    que pode fazer parte do nome do cargo).
    """
    from radar.document_fields import label_from_ambiguity
    label = label_from_ambiguity(reason)
    if not label:
        return None
    label = _clean_label(label)
    return None if re.match(r"^\d{2,5}\b", label) else label
