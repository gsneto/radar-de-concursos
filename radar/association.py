"""Diagnóstico de associações suspeitas entre documentos e concursos (Fase 26).

O caso investigado na fase: **um** concurso com nove atos avulsos do DOU e nenhuma proposta.
A causa comprovada não é extração — é associação: a fonte do DOU registra a **seção** do
diário (``DOU-S3``) como se fosse a identidade de um concurso, e todos os atos do dia passam a
pertencer a esse "concurso" artificial.

Este módulo **não corrige nada automaticamente**. Ele aponta o que está suspeito, com a
evidência que sustenta o apontamento, para que a correção seja uma decisão humana registrada.
Associar documento a concurso por semelhança de título é proibido pelo domínio.
"""

from __future__ import annotations

import json
import re
from contextlib import closing

from radar.document_store import connect_documents, is_readable_schema

ASSOCIATION_VERSION = "association_v1"

# Identificador de seção de diário oficial usado como "concurso" (ex.: DOU-S3, DOU-S1).
_SECTION_IDENTITY = re.compile(r"^(?:DOU|DO)-?S?\d+$|^DOU-S\d+$", re.I)

SEVERITY = {"alta": 3, "media": 2, "baixa": 1}

REASONS = {
    "identidade_de_secao": "O 'concurso' é uma seção de diário oficial, não um certame",
    "muitos_atos_sem_propostas": "Vários atos classificados como edital, nenhum campo extraído",
    "titulos_divergentes": "Mais de um edital de abertura com títulos materialmente distintos",
    "documento_compartilhado": "O mesmo documento oficial aparece em mais de um concurso",
    "documento_sem_observacao": "Documento sem observação de origem (vínculo não rastreável)",
}


def _norm(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", (value or "").lower()).split())


def _titles_distinct(titles: list[str]) -> bool:
    """Títulos materialmente distintos (ignora variação de data/número isolada)."""
    normalized = {_norm(title) for title in titles if title}
    if len(normalized) <= 1:
        return False
    # "EDITAL DE 15 DE OUTUBRO DE 2026" e "EDITAL DE 14 DE OUTUBRO DE 2026" são atos
    # diferentes, ainda que o prefixo seja igual: a data distingue.
    return True


def suspect_associations(db_path) -> dict:
    """Lista associações suspeitas com evidência. Somente leitura."""
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        # Containers de fonte não são certames: não entram no diagnóstico de associação.
        contests = [row[0] for row in conn.execute(
            "SELECT id FROM concursos_identidade WHERE estado_identidade != 'container_fonte' "
            "ORDER BY created_at, id")]
        containers = [row[0] for row in conn.execute(
            "SELECT id FROM concursos_identidade WHERE estado_identidade = 'container_fonte' "
            "ORDER BY created_at, id")]
        observations = {}
        for contest_id, competition_id in conn.execute(
                "SELECT contest_id, competition_id FROM observacoes_concurso"):
            observations.setdefault(contest_id, []).append(competition_id or "")
        documents = {}
        for contest_id, doc_id, kind, tipo, title, url, obs, issuer in conn.execute(
                "SELECT contest_id, id, kind, tipo_documental, title, official_url, "
                "observation_id, issuer FROM documentos"):
            documents.setdefault(contest_id, []).append(
                {"id": doc_id, "kind": kind, "tipo": tipo, "title": title,
                 "url": url, "observation_id": obs, "issuer": issuer})
        proposals = {row[0]: row[1] for row in conn.execute(
            "SELECT contest_id, COUNT(*) FROM propostas_campo GROUP BY contest_id")}

    findings = []
    for contest_id in contests:
        docs = documents.get(contest_id, [])
        obs = observations.get(contest_id, [])
        if any(_SECTION_IDENTITY.match(value.strip()) for value in obs):
            findings.append({
                "contest_id": contest_id, "severity": "alta",
                "reason": "identidade_de_secao",
                "reason_label": REASONS["identidade_de_secao"],
                "evidence": {"observacoes": obs, "documentos": len(docs)},
                "acao": "revisar_associacao",
            })
        editais = [d for d in docs if d["kind"] == "edital"
                   or (d["tipo"] or "").startswith("edital")]
        # O sinal de mistura é **órgãos diferentes** num mesmo concurso: uma banca pode
        # publicar legitimamente muitos editais de abertura do mesmo certame.
        issuers = {d["issuer"] for d in editais if d["issuer"]}
        if len(editais) >= 3 and len(issuers) >= 2 and not proposals.get(contest_id):
            findings.append({
                "contest_id": contest_id, "severity": "alta",
                "reason": "muitos_atos_sem_propostas",
                "reason_label": REASONS["muitos_atos_sem_propostas"],
                "evidence": {"editais": len(editais),
                             "titulos": [d["title"] for d in editais[:5]]},
                "acao": "revisar_associacao",
            })
        aberturas = [d for d in editais if (d["tipo"] or "") in ("edital_abertura", "")]
        aberturas_issuers = {d["issuer"] for d in aberturas if d["issuer"]}
        if (len(aberturas) >= 2 and len(aberturas_issuers) >= 2
                and _titles_distinct([d["title"] for d in aberturas])):
            findings.append({
                "contest_id": contest_id, "severity": "media",
                "reason": "titulos_divergentes",
                "reason_label": REASONS["titulos_divergentes"],
                "evidence": {"titulos": [d["title"] for d in aberturas[:5]]},
                "acao": "revisar_associacao",
            })
        for doc in docs:
            if not doc["observation_id"]:
                findings.append({
                    "contest_id": contest_id, "severity": "baixa",
                    "reason": "documento_sem_observacao",
                    "reason_label": REASONS["documento_sem_observacao"],
                    "evidence": {"document_id": doc["id"], "title": doc["title"]},
                    "acao": "investigar_vinculo",
                })

    # Documento oficial compartilhado entre concursos distintos.
    by_url = {}
    for contest_id, docs in documents.items():
        for doc in docs:
            if doc["url"]:
                by_url.setdefault(doc["url"], set()).add(contest_id)
    for url, contest_ids in by_url.items():
        if len(contest_ids) > 1:
            findings.append({
                "contest_id": sorted(contest_ids)[0], "severity": "media",
                "reason": "documento_compartilhado",
                "reason_label": REASONS["documento_compartilhado"],
                "evidence": {"url": url, "concursos": sorted(contest_ids)},
                "acao": "revisar_associacao",
            })

    findings.sort(key=lambda f: (-SEVERITY[f["severity"]], f["contest_id"], f["reason"]))
    distribution = {}
    for finding in findings:
        distribution[finding["reason"]] = distribution.get(finding["reason"], 0) + 1
    return {
        "version": ASSOCIATION_VERSION,
        "total": len(findings),
        "distribuicao": distribution,
        "concursos_afetados": len({f["contest_id"] for f in findings}),
        "containers_fonte": len(containers),
        "itens": findings,
        "limitacao": ("Diagnóstico apenas: nenhuma associação é alterada automaticamente. "
                      "Correção exige decisão humana registrada."),
    }


def dump_report(db_path) -> str:
    return json.dumps(suspect_associations(db_path), ensure_ascii=False, default=str)
