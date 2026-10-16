"""Reconciliação de cargos entre a página HTML oficial e o quadro de vagas do PDF.

A identidade do cargo é **contextualizada pelo concurso** e, quando existe, pelo
**código oficial** (chave estável). A associação usa o código — nunca apenas a
similaridade de nomes; o nome serve como verificação de consistência. Casos sem
código ou com nomes materialmente incompatíveis permanecem pendentes/ambíguos, e a
proposta documental continua existindo com o rótulo original.
"""

from __future__ import annotations

import re
from contextlib import closing

from radar.document_fields import LABEL_PREFIX, label_from_ambiguity
from radar.document_store import connect_documents, ensure_role, role_names_compatible

_CODE_RE = re.compile(r"^(\d{2,5})\b")
# Sufixos de anotação acrescentados pelo extrator após " — "; removidos para recuperar
# o rótulo limpo sem enfraquecer a checagem de nome quando o cargo contém "—".
_ANNOTATIONS = ("bloco ", "o edital cita", "categoria ampla", "cita área de computa",
                "requisito de área alheia", "requisitos presentes", "sem texto de requisitos")


def _clean_label(label: str) -> str:
    for annotation in _ANNOTATIONS:
        marker = " — " + annotation
        index = label.find(marker)
        if index >= 0:
            return label[:index].strip()
    return label.strip()


def _names_compatible(pdf_label: str, html_name: str) -> bool:
    """Compatível quando há ao menos um token significativo em comum.

    Tolerante a variação de formatação (local repetido, hífen, caixa); **não** funde
    cargos cujos nomes não compartilham nenhum token.
    """
    return role_names_compatible(pdf_label, html_name)


def reconcile_proposals_by_code(db_path, contest_id: str, observation_id: str,
                                cargo_table: list[dict], proposals: list[dict], *,
                                label_prefix: str = LABEL_PREFIX) -> dict:
    """Associa propostas (rótulo com código) aos cargos da tabela HTML, por código.

    Devolve contadores ``{assigned, created, reused, ambiguous, pending}`` e altera
    ``proposals`` no lugar (define ``role_id`` e o motivo da associação). Idempotente:
    reexecutar não cria cargos duplicados nem reatribui associações já feitas.
    """
    by_code: dict[str, list[dict]] = {}
    for role in cargo_table:
        by_code.setdefault(role["code"], []).append(role)

    result = {"assigned": 0, "created": 0, "reused": 0, "ambiguous": 0, "pending": 0,
              "missing_codes": []}
    with closing(connect_documents(db_path)) as conn:
        known = {row[0] for row in conn.execute(
            "SELECT code FROM cargos_identidade WHERE contest_id=? AND code IS NOT NULL",
            (contest_id,))}

    for proposal in proposals:
        if proposal.get("role_id"):
            continue
        label = label_from_ambiguity(proposal.get("ambiguity_reason"))
        if not label:
            continue
        # Remove anotação conhecida (ex.: justificativa de SI, "bloco CÓDIGOS …") sem
        # truncar nomes de cargo que contenham "—".
        label = _clean_label(label)
        match = _CODE_RE.match(label.strip())
        if match is None:
            result["pending"] += 1
            continue
        code = match.group(1)
        pdf_label = label.strip()[match.end():].strip()
        candidates = by_code.get(code, [])
        if not candidates:
            result["pending"] += 1  # código não consta da tabela HTML oficial
            if code not in result["missing_codes"]:
                result["missing_codes"].append(code)
            continue
        if len(candidates) > 1:
            result["ambiguous"] += 1  # mais de uma correspondência para o código
            continue
        html_name = candidates[0]["name"]
        if pdf_label and html_name and not _names_compatible(pdf_label, html_name):
            result["ambiguous"] += 1  # código igual, nome materialmente diferente
            continue
        try:
            role_id = ensure_role(db_path, contest_id, observation_id, html_name, code=code)
        except ValueError:
            result["ambiguous"] += 1  # conflito de identidade: não associa em silêncio
            continue
        proposal["role_id"] = role_id
        if code in known:
            result["reused"] += 1
        else:
            result["created"] += 1
            known.add(code)
        proposal["ambiguity_reason"] = (
            f"associado ao cargo {code} por código oficial (HTML da banca): {html_name}")
        result["assigned"] += 1
    return result


def link_contest_proposals(db_path, contest_id: str, observation_id: str,
                           cargo_table: list[dict]) -> dict:
    """Importa os cargos do HTML e vincula, por código, as propostas existentes do concurso.

    Atualiza ``propostas_campo.role_id`` (apenas as ainda não vinculadas, com rótulo de
    código) e o motivo da associação. Idempotente: reexecutar não duplica cargos nem
    reatribui propostas já associadas. Devolve os contadores da reconciliação.
    """
    with closing(connect_documents(db_path)) as conn:
        rows = conn.execute(
            """SELECT id, role_id, field_name, value_json, ambiguity_reason
            FROM propostas_campo WHERE contest_id=? AND role_id IS NULL""",
            (contest_id,)).fetchall()
    proposals = [{"id": r[0], "role_id": r[1], "field_name": r[2], "value_json": r[3],
                  "ambiguity_reason": r[4]} for r in rows]
    result = reconcile_proposals_by_code(db_path, contest_id, observation_id, cargo_table, proposals)
    updates = [(p["role_id"], p["ambiguity_reason"], p["id"]) for p in proposals if p.get("role_id")]
    if updates:
        with closing(connect_documents(db_path)) as conn, conn:
            conn.executemany("UPDATE propostas_campo SET role_id=?, ambiguity_reason=? WHERE id=?",
                             updates)
    return result
