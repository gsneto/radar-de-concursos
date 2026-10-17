"""Enriquecimento aditivo da base documental (Fase 25).

Escopo deliberadamente estreito: **criar a identidade de cargo que falta**, a partir do rótulo
literal evidenciado no próprio edital, para que a reconciliação humana existente
(``document_review.reconcile_role_label``) tenha um alvo.

O que este módulo **não** faz, por regra de domínio:

- não casa rótulos por similaridade textual;
- não reatribui propostas a cargos;
- não valida, não confirma e não resolve ambiguidade;
- não apaga nem reescreve proposta, evidência ou documento.

Todas as funções são idempotentes: reexecutar não duplica identidade nem proposta.
"""

from __future__ import annotations

import json
import re
from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from radar.document_fields import label_from_ambiguity
from radar.document_store import connect_documents, is_readable_schema

ENRICHMENT_VERSION = "enrichment_v1"

# Tamanho máximo do rótulo aceito como nome de cargo (evita lixo de extração virar identidade).
MAX_LABEL = 200

# Rótulos sintéticos: descrevem um fato, não um cargo. Nunca viram identidade de cargo.
_SYNTHETIC_PREFIXES = ("escolaridade declarada", "bloco ")


def clean_label(label):
    """Normaliza o rótulo de cargo, descartando sufixos de motivo e rótulos sintéticos.

    Só remove os sufixos que o próprio pipeline acrescenta:

    - ``— <motivo>`` (travessão em) de ``si_compatibility``;
    - ``- bloco <n>`` do quadro de vagas.

    Nomes reais de cargo podem conter hífen (``TÉCNICO - ENFERMAGEM``), então **não** se corta
    em qualquer ``" - "``. Rótulos que não descrevem cargo (ex.: ``escolaridade declarada``)
    são recusados.
    """
    if not isinstance(label, str):
        return None
    text = label.split(" — ", 1)[0]
    text = re.sub(r"\s+-\s+bloco\b.*$", "", text, flags=re.IGNORECASE)
    text = text.strip()
    if not text or len(text) > MAX_LABEL:
        return None
    lowered = text.lower()
    if any(lowered.startswith(prefix) for prefix in _SYNTHETIC_PREFIXES):
        return None
    if not any(ch.isalpha() for ch in text):
        return None
    return text


def _now():
    return datetime.now(timezone.utc).isoformat()


def document_role_candidates(db_path) -> list[dict]:
    """Rótulos de cargo evidenciados em propostas ambíguas, por concurso (somente leitura)."""
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = conn.execute(
            "SELECT contest_id, ambiguity_reason, COUNT(*) FROM propostas_campo "
            "WHERE ambiguity_reason IS NOT NULL GROUP BY contest_id, ambiguity_reason "
            "ORDER BY contest_id, ambiguity_reason").fetchall()
        existing = {(contest_id, name) for contest_id, name in conn.execute(
            "SELECT contest_id, name FROM cargos_identidade")}
    grouped = {}
    for contest_id, reason, count in rows:
        label = clean_label(label_from_ambiguity(reason))
        if not label:
            continue
        entry = grouped.setdefault((contest_id, label), {"contest_id": contest_id,
                                                         "label": label,
                                                         "propostas": 0})
        entry["propostas"] += int(count or 0)
    out = []
    for key in sorted(grouped):
        entry = grouped[key]
        entry["identidade_existente"] = key in existing
        out.append(entry)
    return out


def materialize_document_roles(db_path, *, dry_run=True, contest_ids=None) -> dict:
    """Cria identidades de cargo a partir dos rótulos evidenciados (idempotente).

    ``dry_run=True`` (padrão) apenas relata o que faria, sem gravar nada.
    """
    allowed = {str(c) for c in contest_ids} if contest_ids else None
    candidates = document_role_candidates(db_path)
    if allowed is not None:
        candidates = [c for c in candidates if c["contest_id"] in allowed]
    pendentes = [c for c in candidates if not c["identidade_existente"]]

    report = {
        "version": ENRICHMENT_VERSION,
        "dry_run": bool(dry_run),
        "rotulos_evidenciados": len(candidates),
        "identidades_existentes": len(candidates) - len(pendentes),
        "identidades_criadas": 0,
        "propostas_elegiveis": sum(c["propostas"] for c in candidates),
        "propostas_elegiveis_sem_identidade": sum(c["propostas"] for c in pendentes),
        "criadas": [],
    }
    if dry_run or not pendentes:
        report["seriam_criadas"] = [{"contest_id": c["contest_id"], "nome": c["label"],
                                     "propostas": c["propostas"]} for c in pendentes]
        return report

    with closing(connect_documents(db_path)) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            if not is_readable_schema(conn):
                raise ValueError("migração documental pendente")
            for candidate in pendentes:
                contest_id, name = candidate["contest_id"], candidate["label"]
                exists = conn.execute(
                    "SELECT id FROM cargos_identidade WHERE contest_id=? AND name=? "
                    "AND specialty IS NULL", (contest_id, name)).fetchone()
                if exists:
                    continue
                role_id = str(uuid4())
                conn.execute(
                    "INSERT INTO cargos_identidade (id,contest_id,name,specialty,created_at,code) "
                    "VALUES (?,?,?,?,?,?)",
                    (role_id, contest_id, name, None, _now(), None))
                report["identidades_criadas"] += 1
                report["criadas"].append({"contest_id": contest_id, "nome": name,
                                          "role_id": role_id,
                                          "propostas": candidate["propostas"]})
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    return report


def unresolved_role_summary(db_path) -> dict:
    """Quantos rótulos ainda não têm decisão humana de reconciliação."""
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        labels = {}
        for contest_id, reason in conn.execute(
                "SELECT contest_id, ambiguity_reason FROM propostas_campo "
                "WHERE ambiguity_reason IS NOT NULL"):
            label = clean_label(label_from_ambiguity(reason))
            if label:
                labels.setdefault(contest_id, set()).add(label)
        # A reconciliação grava o rótulo BRUTO (com sufixo de motivo); comparar pelo rótulo
        # limpo nos dois lados evita relatar progresso humano inexistente.
        reconciled = {(c, clean_label(label_from_ambiguity(l)) or l) for c, l in conn.execute(
            "SELECT contest_id, label FROM reconciliacoes_cargo")}
        roles = {(c, n) for c, n in conn.execute("SELECT contest_id, name FROM cargos_identidade")}
    total = sum(len(v) for v in labels.values())
    com_identidade = sum(1 for c, ls in labels.items() for l in ls if (c, l) in roles)
    com_decisao = sum(1 for c, ls in labels.items() for l in ls if (c, l) in reconciled)
    return {"version": ENRICHMENT_VERSION,
            "rotulos": total,
            "com_identidade": com_identidade,
            "com_decisao_humana": com_decisao,
            "sem_identidade": total - com_identidade,
            "sem_decisao_humana": total - com_decisao}
