"""Reparo rastreável de rótulos de escopo produzidos por versões anteriores do parser.

Motivo (Fase 42): o extrator de quadro largo costurava células que atravessam a página
usando **todas** as palavras acima da primeira linha, o que contaminava o rótulo da linha
anterior com o rótulo da linha seguinte. Duas linhas do Anexo II da SEDUC-PA ficaram com
rótulo errado/truncado no banco: uma com sufixo indevido ("… Assistente de") e outra com a
formação cortada ("Língua" em vez de "Língua Portuguesa").

O parser já foi corrigido. Este módulo repara **apenas o rótulo** (`ambiguity_reason`) das
propostas afetadas, porque o rótulo é a identidade do escopo na Mesa de Revisão e na matriz.
Nada mais é tocado: valor, evidência, offsets, versão e histórico permanecem intactos.

Guardas:

- só propostas de quadro largo (`quadro-colunas-pdf`);
- só quando o rótulo atual é **comprovável**: prefixo de palavras do rótulo do parser ou
  contém a marca legada de costura (`[rotulo completado na pagina seguinte]`);
- nunca quando há decisão humana, valor vigente ou lote de revisão apontando a proposta;
- idempotente: rodar de novo não encontra nada para reparar;
- cada alteração gera um evento documental `reparo_rotulo` com antes/depois.
"""

from __future__ import annotations

import json
import re
from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from radar.document_store import connect_documents, is_readable_schema

REPAIR_VERSION = "label_repair_v1"
LEGACY_NOTE = "[rotulo completado na pagina seguinte]"
PREFIX = "cargo do documento não reconciliado: "


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _words(text: str) -> list[str]:
    spaced = " ".join((text or "").replace("/", " / ").split())
    return [word for word in spaced.split(" ") if word and word != "/"]


def _label_of(reason: str) -> str:
    return reason[len(PREFIX):] if reason.startswith(PREFIX) else reason


FIELD_COLUMN = {
    "immediate_vacancies": "Total",
    "indigenous_vacancies": "PI",
    "unified_ppiq_vacancies": "PPIQ",
    "unified_pi_pq_vacancies": "PI/PQ",
}


def _shared_prefix(left: list[str], right: list[str]) -> int:
    count = 0
    for a, b in zip(left, right):
        if a != b:
            break
        count += 1
    return count


def _tail_numbers(quote: str) -> list[int]:
    """Últimos oito inteiros do trecho: a linha publicada do quadro largo."""
    numbers = re.findall(r"\d{1,5}", quote or "")
    if len(numbers) < 8:
        return []
    return [int(value) for value in numbers[-8:]]


def _best_row(rows, *, page, field, value, stored_label, quote=""):
    """Linha do parser que comprova o rótulo armazenado (ou ``None`` se ambíguo).

    A evidência muda quando o parser corrige a localização do trecho, então a linha é
    identificada pelos **números publicados no próprio trecho** (a linha inteira, não só o
    campo) e, como desempate, pelo prefixo de palavras do rótulo bruto.
    """
    column = FIELD_COLUMN.get(field)
    stored_words = _words(stored_label)
    tail = _tail_numbers(quote)
    candidates = [item for item in rows if item["page"] == page]
    if tail:
        exact = [item for item in candidates
                 if [item["valores"].get(name) for name in
                     ("AC", "PcD", "PP", "PI", "PQ", "PPIQ", "PI/PQ", "Total")] == tail]
        if exact:
            candidates = exact
    scored = []
    for item in candidates:
        if column is not None and item["valores"].get(column) != value:
            continue
        raw_words = _words((item.get("cargo_bruto") or item["cargo"]) + " " +
                           (item.get("formacao_bruta") or item["formacao"]))
        score = _shared_prefix(stored_words, raw_words)
        if raw_words and stored_words[:len(raw_words)] == raw_words:
            score += 10  # rótulo bruto é exatamente o prefixo do armazenado
        scored.append((score, item))
    if not scored:
        return None
    scored.sort(key=lambda pair: -pair[0])
    if scored[0][0] <= 0:
        return None
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None  # empate: não se escolhe linha por adivinhação
    return scored[0][1]


def _scope_part(label: str) -> str:
    """Parte do rótulo antes da regional ("cargo / formação")."""
    return label.split(" / DRE ")[0].strip()


def _provable(current_label: str, stored_label: str) -> bool:
    """O rótulo do parser comprova o reparo do rótulo armazenado?"""
    if LEGACY_NOTE in stored_label:
        return True
    stored_words = _words(_scope_part(stored_label))
    current_words = _words(_scope_part(current_label))
    if not stored_words or len(stored_words) >= len(current_words):
        return False
    return current_words[:len(stored_words)] == stored_words


def repair_labels(db_path, *, contest_id=None, dry_run=True, version_id=None) -> dict:
    """Repara rótulos de escopo divergentes do parser atual. Simula por padrão."""
    from radar import modality_legend, reprocess, vacancy_columns

    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        params = []
        where = ["p.extraction_method='quadro-colunas-pdf'"]
        if contest_id:
            where.append("p.contest_id=?")
            params.append(contest_id)
        if version_id:
            where.append("e.version_id=?")
            params.append(version_id)
        rows = conn.execute(
            "SELECT p.id, p.contest_id, p.role_id, p.field_name, p.ambiguity_reason, "
            "e.version_id, e.page_number, e.quote, p.value_json "
            "FROM propostas_campo p JOIN evidencias e ON e.id=p.evidence_id "
            "WHERE " + " AND ".join(where) + " ORDER BY e.version_id, e.page_number", params
        ).fetchall()
        blocked = {(row[0]) for row in conn.execute(
            "SELECT DISTINCT proposal_id FROM revisoes_campo")}
        blocked |= {row[0] for row in conn.execute(
            "SELECT DISTINCT proposal_id FROM valores_atuais")}
        blocked |= {row[0] for row in conn.execute(
            "SELECT DISTINCT proposal_id FROM lote_revisao_itens")}

    # Contexto atual do parser por versão (uma leitura por versão, não por proposta).
    contexts = {}
    for version in sorted({row[5] for row in rows}):
        with closing(connect_documents(db_path)) as conn:
            blocks = reprocess.stored_blocks(conn, version)
            artifact = reprocess._artifact_path(conn, version)
        definitions = {}
        for block in blocks:
            for key, value in modality_legend.parse_definitions(
                    block.get("text") or "").items():
                definitions.setdefault(key, value)
        report = vacancy_columns.parse_wide_table(
            blocks, "", label_prefix=PREFIX, pdf_path=artifact, definitions=definitions)
        contexts[version] = report["rows"]

    candidates, skipped = [], []
    for proposal_id, contest, role, field, reason, version, page, quote, value_json in rows:
        stored = _label_of(reason or "")
        try:
            value = json.loads(value_json)
        except (TypeError, ValueError):
            value = value_json
        item = _best_row(contexts.get(version, []), page=page, field=field, value=value,
                         stored_label=stored, quote=quote)
        if item is None:
            skipped.append({"proposal_id": proposal_id, "motivo": "linha_nao_reconhecida",
                            "armazenado": stored})
            continue
        current = vacancy_columns.compose_label(item["cargo"], item["formacao"],
                                                item["dre"])
        if stored == current:
            continue
        if not _provable(current, stored):
            skipped.append({"proposal_id": proposal_id, "motivo": "rotulo_nao_comprovado",
                            "armazenado": stored, "parser": current})
            continue
        if proposal_id in blocked:
            skipped.append({"proposal_id": proposal_id,
                            "motivo": "proposta_com_decisao_ou_lote",
                            "armazenado": stored, "parser": current})
            continue
        candidates.append({"proposal_id": proposal_id, "contest_id": contest,
                           "version_id": version, "page": page,
                           "field_name": field, "de": stored, "para": current})

    report = {"version": REPAIR_VERSION, "dry_run": bool(dry_run),
              "geradas": len(rows), "reparaveis": len(candidates),
              "ignoradas": len(skipped), "reparadas": 0, "itens": candidates,
              "ignorados": skipped[:50]}
    if dry_run or not candidates:
        return report

    with closing(connect_documents(db_path)) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            # Revalidação dentro da transação: nada é reparado se surgiu decisão no meio.
            blocked_tx = {row[0] for row in conn.execute(
                "SELECT DISTINCT proposal_id FROM revisoes_campo")}
            blocked_tx |= {row[0] for row in conn.execute(
                "SELECT DISTINCT proposal_id FROM valores_atuais")}
            blocked_tx |= {row[0] for row in conn.execute(
                "SELECT DISTINCT proposal_id FROM lote_revisao_itens")}
            applied = 0
            for item in candidates:
                if item["proposal_id"] in blocked_tx:
                    continue
                conn.execute("UPDATE propostas_campo SET ambiguity_reason=? WHERE id=?",
                             (PREFIX + item["para"], item["proposal_id"]))
                conn.execute(
                    "INSERT INTO eventos_documentais (id,document_id,version_id,event_type,"
                    "occurred_at,note) SELECT ?,d.id,v.id,'analise',?,? "
                    "FROM propostas_campo p JOIN evidencias e ON e.id=p.evidence_id "
                    "JOIN versoes_documento v ON v.id=e.version_id "
                    "JOIN documentos d ON d.id=v.document_id WHERE p.id=?",
                    (str(uuid4()), _now(),
                     json.dumps({"reparo": REPAIR_VERSION, "campo": "ambiguity_reason",
                                 "de": item["de"], "para": item["para"],
                                 "proposta": item["proposal_id"]}, ensure_ascii=False),
                     item["proposal_id"]))
                applied += 1
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    report["reparadas"] = applied
    return report
