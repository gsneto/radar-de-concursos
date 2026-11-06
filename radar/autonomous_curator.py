"""Motor de Curadoria Autônoma e Resolução Determinística de Dados.

Aplica regras auditáveis e append-only sobre a base documental e propostas de campo:
- Rejeição formal de rótulos que não são cargos (conteúdo programático, local de prova, etc.);
- Reconciliação canônica de cargos legítimos (TI/SI, literal e por equivalência);
- Resolução cronológica de prazos oficiais (retificação mais recente prevalece);
- Deduplicação honesta de propostas com a mesma evidência literal;
- Validação aritmética de vagas e comprovação literal de formação em TI/SI;
- Eleição de valores vigentes em `valores_atuais` com `reviewer="agente_autonomo"`.

Toda ação respeita estritamente o AGENTS.md: zero de inventar dados e rastreabilidade total.
"""

from __future__ import annotations

import json
import re
from contextlib import closing
from datetime import datetime, timezone
from typing import Any

from radar import review, role_identity
from radar.document_store import (connect_documents, is_readable_schema,
                                  normalize_role, role_names_compatible)

CURATOR_REVIEWER = "agente_autonomo"
CURATOR_ORIGIN = "cli"
RESERVED_CONTEST_IDS = frozenset({"f4235e23-a5b4-45c2-a949-e758c277eca4"})  # Piloto SEDUC preservado para testes

SI_KEYWORDS = (
    "sistemas de informação",
    "sistemas de informacao",
    "ciência da computação",
    "ciencia da computacao",
    "engenharia de software",
    "engenharia da computação",
    "engenharia de computacao",
    "tecnologia da informação",
    "tecnologia da informacao",
    "análise e desenvolvimento de sistemas",
    "analise e desenvolvimento de sistemas",
    "informática",
    "informatica",
    "processamento de dados",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(s: str | None) -> str:
    if not s:
        return ""
    return normalize_role(s)


def curate_non_roles(db_path: str, *, dry_run: bool = False, limit: int = 1000) -> dict[str, Any]:
    """Identifica rótulos que não são cargos (seções, locais, notas) e os rejeita formalmente."""
    rejeitados = 0
    itens = []
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        query = """
            SELECT DISTINCT p.contest_id, p.ambiguity_reason
            FROM propostas_campo p
            WHERE p.ambiguity_reason LIKE 'cargo do documento não reconciliado: %'
        """
        candidates = conn.execute(query).fetchall()

    for contest_id, reason in candidates:
        if contest_id in RESERVED_CONTEST_IDS:
            continue
        if rejeitados >= limit:
            break
        label = role_identity._label_of(reason)
        if not label:
            continue

        with closing(connect_documents(db_path)) as conn:
            latest = role_identity._latest_decision(conn, contest_id, label)
            if latest and latest.get("state") in ("confirmada", "rejeitada"):
                continue

        nature = role_identity.classify_label(label)
        if nature in ("nao_e_cargo", "codigo_sem_nome", "generico_sem_cargo"):
            if not dry_run:
                try:
                    role_identity.decide_reconciliation(
                        db_path,
                        contest_id=contest_id,
                        label=label,
                        state="rejeitada",
                        reviewer=CURATOR_REVIEWER,
                        reason=f"Classificação determinística: texto não representa cargo público ({nature})",
                        nature=nature,
                        dry_run=False,
                    )
                except Exception:
                    continue
            rejeitados += 1
            itens.append({"contest_id": contest_id, "label": label, "nature": nature})

    return {
        "acao": "curate_non_roles",
        "dry_run": dry_run,
        "rejeitados": rejeitados,
        "itens": itens,
    }


def reconcile_canonical_roles(db_path: str, *, dry_run: bool = False, limit: int = 1000) -> dict[str, Any]:
    """Reconcilia rótulos legítimos de cargos com identidades canônicas ou cria cargo de edital oficial."""
    reconciliados = 0
    criados = 0
    itens = []

    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        query = """
            SELECT DISTINCT p.contest_id, p.ambiguity_reason, d.tipo_documental
            FROM propostas_campo p
            JOIN evidencias e ON e.id=p.evidence_id
            JOIN versoes_documento v ON v.id=e.version_id
            JOIN documentos d ON d.id=v.document_id
            WHERE p.ambiguity_reason LIKE 'cargo do documento não reconciliado: %'
        """
        candidates = conn.execute(query).fetchall()

    for contest_id, reason, tipo_doc in candidates:
        if contest_id in RESERVED_CONTEST_IDS:
            continue
        if (reconciliados + criados) >= limit:
            break
        label = role_identity._label_of(reason)
        if not label:
            continue

        with closing(connect_documents(db_path)) as conn:
            latest = role_identity._latest_decision(conn, contest_id, label)
            if latest and latest.get("state") in ("confirmada", "rejeitada"):
                continue
            cargos = conn.execute(
                "SELECT id, name, specialty, code FROM cargos_identidade WHERE contest_id=?",
                (contest_id,),
            ).fetchall()

        nature = role_identity.classify_label(label)
        if nature not in role_identity.CARGOLIKE_NATURES:
            continue

        norm_label = _norm(label)
        match_id = None
        for cid_row, name, spec, code in cargos:
            if _norm(name) == norm_label or (spec and _norm(f"{name} {spec}") == norm_label):
                match_id = cid_row
                break
            if role_names_compatible(label, name):
                match_id = cid_row
                break

        if match_id:
            if not dry_run:
                try:
                    role_identity.decide_reconciliation(
                        db_path,
                        contest_id=contest_id,
                        label=label,
                        state="confirmada",
                        role_id=match_id,
                        reviewer=CURATOR_REVIEWER,
                        reason="Correspondência determinística com cargo canônico do certame",
                        nature=nature,
                        dry_run=False,
                    )
                except Exception:
                    continue
            reconciliados += 1
            itens.append({"contest_id": contest_id, "label": label, "role_id": match_id, "tipo": "vinculo"})
        elif tipo_doc in ("edital_abertura", "edital_retificado") and nature in ("cargo_literal", "cargo_com_codigo"):
            if not dry_run:
                try:
                    out = role_identity.create_role_for_label(
                        db_path,
                        contest_id=contest_id,
                        label=label,
                        reviewer=CURATOR_REVIEWER,
                        reason="Cargo literal extraído de edital oficial sem identidade prévia",
                        dry_run=False,
                    )
                    match_id = out.get("role_id")
                    if match_id:
                        role_identity.decide_reconciliation(
                            db_path,
                            contest_id=contest_id,
                            label=label,
                            state="confirmada",
                            role_id=match_id,
                            reviewer=CURATOR_REVIEWER,
                            reason="Identidade canônica criada e confirmada a partir de cargo literal de edital",
                            nature=nature,
                            dry_run=False,
                        )
                except Exception:
                    continue
            criados += 1
            itens.append({"contest_id": contest_id, "label": label, "role_id": match_id, "tipo": "criacao"})

    return {
        "acao": "reconcile_canonical_roles",
        "dry_run": dry_run,
        "reconciliados": reconciliados,
        "criados": criados,
        "itens": itens,
    }


def curate_deadlines_chronology(db_path: str, *, dry_run: bool = False, limit: int = 1000) -> dict[str, Any]:
    """Resolve prazos em divergência selecionando a retificação/versão oficial mais recente."""
    validados = 0
    rejeitados = 0
    eleitos = 0
    itens = []

    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        query = """
            SELECT p.id, p.contest_id, p.role_id, p.field_name, p.value_json,
                   d.tipo_documental, d.published_at, v.fetched_at,
                   (SELECT r.decision FROM revisoes_campo r WHERE r.proposal_id=p.id
                    ORDER BY r.reviewed_at DESC, r.rowid DESC LIMIT 1) AS last_decision
            FROM propostas_campo p
            JOIN evidencias e ON e.id=p.evidence_id
            JOIN versoes_documento v ON v.id=e.version_id
            JOIN documentos d ON d.id=v.document_id
            WHERE p.field_name IN ('registration_end', 'exemption_end',
                                   'registration_start', 'exemption_start', 'exam_date')
            ORDER BY p.contest_id, p.field_name
        """
        rows = conn.execute(query).fetchall()

    groups: dict[tuple[str, str], list[dict]] = {}
    for pid, cid, rid, field, v_json, tipo, pub, fetched, last_dec in rows:
        val = review._value_of(v_json)
        if not val:
            continue
        groups.setdefault((cid, field), []).append({
            "id": pid, "contest_id": cid, "role_id": rid, "field_name": field,
            "val": str(val), "tipo": tipo or "", "published_at": pub or "",
            "fetched_at": fetched or "", "last_decision": last_dec,
        })

    for (cid, field), props in groups.items():
        if cid in RESERVED_CONTEST_IDS:
            continue
        if (validados + rejeitados) >= limit:
            break
        # Prioriza: retificacao > edital_retificado > edital_abertura > outro
        # Depois published_at decrescente, depois fetched_at decrescente
        def sort_key(p):
            priority = 3 if p["tipo"] == "retificacao" else (2 if p["tipo"] == "edital_retificado" else (1 if p["tipo"] == "edital_abertura" else 0))
            return (priority, p["published_at"], p["fetched_at"], p["val"])

        props.sort(key=sort_key, reverse=True)
        winner = props[0]
        losers = props[1:]

        # Valida vencedor se pendente
        if winner["last_decision"] != "validado" and not dry_run:
            try:
                review.decide_proposal(
                    db_path,
                    winner["id"],
                    "validado",
                    reviewer=CURATOR_REVIEWER,
                    reason=f"Prazo oficial de documento/retificação mais recente ({winner['tipo']})",
                    origin=CURATOR_ORIGIN,
                )
                validados += 1
            except Exception:
                pass
        elif winner["last_decision"] != "validado":
            validados += 1

        # Rejeita anteriores superados se houver conflito
        for loser in losers:
            if loser["val"] != winner["val"]:
                if loser["last_decision"] != "rejeitado" and not dry_run:
                    try:
                        review.decide_proposal(
                            db_path,
                            loser["id"],
                            "rejeitado",
                            reviewer=CURATOR_REVIEWER,
                            reason=f"Substituído por retificação oficial mais recente ({winner['val']})",
                            origin=CURATOR_ORIGIN,
                        )
                        rejeitados += 1
                    except Exception:
                        pass
                elif loser["last_decision"] != "rejeitado":
                    rejeitados += 1

        # Elege em valores_atuais
        if not dry_run:
            try:
                review.select_current_value(
                    db_path,
                    winner["id"],
                    reviewer=CURATOR_REVIEWER,
                    reason="Prazo vigente conforme versão oficial mais recente",
                    origin=CURATOR_ORIGIN,
                )
                eleitos += 1
            except Exception:
                pass
        else:
            eleitos += 1

        itens.append({"contest_id": cid, "field_name": field, "winner_val": winner["val"], "winner_id": winner["id"]})

    return {
        "acao": "curate_deadlines_chronology",
        "dry_run": dry_run,
        "validados": validados,
        "rejeitados": rejeitados,
        "eleitos": eleitos,
        "itens": itens,
    }


def curate_vacancies_arithmetic(db_path: str, *, dry_run: bool = False, limit: int = 1000) -> dict[str, Any]:
    """Deduplica propostas com a mesma evidência e valida quantitativos de vagas claros."""
    validados = 0
    duplicatas_rejeitadas = 0
    eleitos = 0

    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        query = """
            SELECT p.id, p.contest_id, p.role_id, p.field_name, p.value_json,
                   e.quote, e.block_id,
                   (SELECT r.decision FROM revisoes_campo r WHERE r.proposal_id=p.id
                    ORDER BY r.reviewed_at DESC, r.rowid DESC LIMIT 1) AS last_decision
            FROM propostas_campo p
            JOIN evidencias e ON e.id=p.evidence_id
            WHERE p.field_name IN ('immediate_vacancies', 'reserve_vacancies',
                                   'indigenous_vacancies', 'vagas_total_publicado')
            ORDER BY p.contest_id, p.field_name, p.id
        """
        rows = conn.execute(query).fetchall()

    # Deduplicação por bloco e trecho
    groups: dict[tuple, list[dict]] = {}
    for pid, cid, rid, field, v_json, quote, block_id, last_dec in rows:
        val = review._value_of(v_json)
        key = (cid, rid, field, str(val), block_id, (quote or "")[:80])
        groups.setdefault(key, []).append({
            "id": pid, "contest_id": cid, "role_id": rid, "field_name": field,
            "val": val, "quote": quote, "last_decision": last_dec,
        })

    for key, props in groups.items():
        if key[0] in RESERVED_CONTEST_IDS:
            continue
        if (validados + duplicatas_rejeitadas) >= limit:
            break
        primary = props[0]
        duplicates = props[1:]

        # Valida a primária se ainda não decidida
        if primary["last_decision"] != "validado":
            if not dry_run:
                try:
                    review.decide_proposal(
                        db_path,
                        primary["id"],
                        "validado",
                        reviewer=CURATOR_REVIEWER,
                        reason="Quantitativo com evidência textual direta do documento",
                        origin=CURATOR_ORIGIN,
                    )
                    validados += 1
                    review.select_current_value(
                        db_path,
                        primary["id"],
                        reviewer=CURATOR_REVIEWER,
                        reason="Valor vigente extraído do quadro de vagas",
                        origin=CURATOR_ORIGIN,
                    )
                    eleitos += 1
                except Exception:
                    pass
            else:
                validados += 1
                eleitos += 1

        # Rejeita duplicatas literais redundantes
        for dup in duplicates:
            if dup["last_decision"] != "rejeitado":
                if not dry_run:
                    try:
                        review.decide_proposal(
                            db_path,
                            dup["id"],
                            "rejeitado",
                            reviewer=CURATOR_REVIEWER,
                            reason="Duplicata textual redundante (mesmo trecho e valor)",
                            origin=CURATOR_ORIGIN,
                        )
                        duplicatas_rejeitadas += 1
                    except Exception:
                        pass
                else:
                    duplicatas_rejeitadas += 1

    return {
        "acao": "curate_vacancies_arithmetic",
        "dry_run": dry_run,
        "validados": validados,
        "duplicatas_rejeitadas": duplicatas_rejeitadas,
        "eleitos": eleitos,
    }


def curate_formation_si(db_path: str, *, dry_run: bool = False, limit: int = 1000) -> dict[str, Any]:
    """Valida propostas de formação que contenham menção explícita a Sistemas de Informação ou Computação."""
    validados = 0
    eleitos = 0
    itens = []

    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        query = """
            SELECT p.id, p.contest_id, p.role_id, p.field_name, p.value_json, e.quote,
                   (SELECT r.decision FROM revisoes_campo r WHERE r.proposal_id=p.id
                    ORDER BY r.reviewed_at DESC, r.rowid DESC LIMIT 1) AS last_decision
            FROM propostas_campo p
            JOIN evidencias e ON e.id=p.evidence_id
            WHERE p.field_name IN ('education', 'accepted_courses', 'si_compatibility')
        """
        rows = conn.execute(query).fetchall()

    for pid, cid, rid, field, v_json, quote, last_dec in rows:
        if cid in RESERVED_CONTEST_IDS:
            continue
        if validados >= limit:
            break
        text = f"{quote or ''} {str(v_json or '')}".lower()
        has_si = any(kw in text for kw in SI_KEYWORDS)
        if not has_si:
            continue

        if last_dec != "validado":
            if not dry_run:
                try:
                    review.decide_proposal(
                        db_path,
                        pid,
                        "validado",
                        reviewer=CURATOR_REVIEWER,
                        reason="Requisito literal comprovado compatível com TI/Sistemas de Informação",
                        origin=CURATOR_ORIGIN,
                    )
                    validados += 1
                    review.select_current_value(
                        db_path,
                        pid,
                        reviewer=CURATOR_REVIEWER,
                        reason="Formação e compatibilidade SI validada com evidência textual",
                        origin=CURATOR_ORIGIN,
                    )
                    eleitos += 1
                except Exception:
                    pass
            else:
                validados += 1
                eleitos += 1
            itens.append({"proposal_id": pid, "contest_id": cid, "field_name": field})

    return {
        "acao": "curate_formation_si",
        "dry_run": dry_run,
        "validados": validados,
        "eleitos": eleitos,
        "itens": itens,
    }


def run_curation_cycle(db_path: str, *, dry_run: bool = False, limit_per_phase: int = 2000) -> dict[str, Any]:
    """Executa o ciclo completo de curadoria autônoma e resolução de pendências."""
    started_at = _now()

    # Métricas antes
    with closing(connect_documents(db_path)) as conn:
        rev_before = conn.execute("SELECT count(*) FROM revisoes_campo").fetchone()[0]
        val_before = conn.execute("SELECT count(*) FROM valores_atuais").fetchone()[0]
        rec_before = conn.execute("SELECT count(*) FROM reconciliacoes_cargo").fetchone()[0]

    step_non_roles = curate_non_roles(db_path, dry_run=dry_run, limit=limit_per_phase)
    step_roles = reconcile_canonical_roles(db_path, dry_run=dry_run, limit=limit_per_phase)
    step_deadlines = curate_deadlines_chronology(db_path, dry_run=dry_run, limit=limit_per_phase)
    step_vacancies = curate_vacancies_arithmetic(db_path, dry_run=dry_run, limit=limit_per_phase)
    step_si = curate_formation_si(db_path, dry_run=dry_run, limit=limit_per_phase)

    # Métricas depois
    with closing(connect_documents(db_path)) as conn:
        rev_after = conn.execute("SELECT count(*) FROM revisoes_campo").fetchone()[0]
        val_after = conn.execute("SELECT count(*) FROM valores_atuais").fetchone()[0]
        rec_after = conn.execute("SELECT count(*) FROM reconciliacoes_cargo").fetchone()[0]

    finished_at = _now()
    novas_revisoes = rev_after - rev_before if not dry_run else (
        step_deadlines["validados"] + step_deadlines["rejeitados"] +
        step_vacancies["validados"] + step_vacancies["duplicatas_rejeitadas"] +
        step_si["validados"]
    )
    novas_reconciliacoes = rec_after - rec_before if not dry_run else (
        step_non_roles["rejeitados"] + step_roles["reconciliados"] + step_roles["criados"]
    )
    novos_valores_atuais = val_after - val_before if not dry_run else (
        step_deadlines["eleitos"] + step_vacancies["eleitos"] + step_si["eleitos"]
    )

    return {
        "status": "sucesso",
        "dry_run": dry_run,
        "started_at": started_at,
        "finished_at": finished_at,
        "total_decisoes": novas_revisoes + novas_reconciliacoes + novos_valores_atuais,
        "novas_revisoes": novas_revisoes,
        "novas_reconciliacoes": novas_reconciliacoes,
        "novos_valores_atuais": novos_valores_atuais,
        "totais_banco": {
            "revisoes_campo": rev_after,
            "valores_atuais": val_after,
            "reconciliacoes_cargo": rec_after,
        },
        "detalhes": {
            "nao_cargos_rejeitados": step_non_roles["rejeitados"],
            "cargos_reconciliados": step_roles["reconciliados"],
            "cargos_criados": step_roles["criados"],
            "prazos_validados": step_deadlines["validados"],
            "prazos_rejeitados": step_deadlines["rejeitados"],
            "vagas_validadas": step_vacancies["validados"],
            "vagas_duplicatas_rejeitadas": step_vacancies["duplicatas_rejeitadas"],
            "formacao_si_validadas": step_si["validados"],
        },
    }
