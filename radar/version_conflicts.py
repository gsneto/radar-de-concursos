"""Conflitos entre versões documentais (Fase 33).

Uma retificação não é um valor novo qualquer: é uma publicação posterior que **pode** ter
alterado um campo. Este módulo compara propostas do mesmo concurso/campo/escopo entre
documentos diferentes e responde, com evidência:

- ``retificacao_posterior``: documentos com datas distintas; o mais recente é o vigente
  **candidato** e o anterior fica registrado como substituído (nada é apagado);
- ``divergencia_sem_ordem``: valores divergentes sem ordem temporal confiável — não se
  escolhe em silêncio;
- ``escopo_diferente``: um valor declara "a divulgar" e outro um local concreto (etapas
  distintas), ou campos de escopo distinto (prova × lotação). Não é conflito de valor;
- ``equivalente``: mesmo valor após normalização (ex.: ``Salvador`` e ``Salvador/BA``).

Regras aplicadas:

- prazo de inscrição só é comparado entre documentos **autoritativos** (edital, edital
  retificado, retificação, cronograma). Resultado/homologação/gabarito/convocacão não
  definem prazo de inscrição e não entram na comparação;
- local de prova é comparado por município + UF; ``a_divulgar`` é declaração de escopo
  diferente, não divergência;
- nada é confirmado e nada é apagado: o resultado é insumo da revisão humana.
"""

from __future__ import annotations

import json
import re
import unicodedata
from contextlib import closing

from radar.document_store import connect_documents, is_readable_schema

CONFLICT_VERSION = "version_conflicts_v1"

# Documentos que podem definir/alterar prazos do certame.
AUTHORITATIVE_DOC_TYPES = ("edital_abertura", "edital_retificado", "retificacao", "cronograma")
# Documentos de resultado: publicam listas/atos, não regras do certame.
RESULT_DOC_TYPES = ("resultado", "homologacao", "gabarito", "convocacao")

DEADLINE_FIELDS = ("registration_start", "registration_end", "exemption_start",
                   "exemption_end", "exemption_appeal", "exemption_result_preliminary",
                   "exemption_result_final")
LOCATION_FIELDS = ("exam_location", "exam_municipio", "exam_uf", "work_location",
                   "work_municipio", "work_uf")
# Campos de escopo do concurso: um valor por concurso (sem cargo).
CONTEST_LEVEL_FIELDS = DEADLINE_FIELDS + LOCATION_FIELDS
# Campos por cargo: só comparáveis quando o cargo foi reconciliado.
ROLE_LEVEL_FIELDS = ("immediate_vacancies", "reserve_vacancies", "indigenous_vacancies",
                     "indigenous_reserve_vacancies", "education", "accepted_courses",
                     "si_compatibility")
# `vagas_total_publicado` é multi-valor por desenho (total do quadro + recortes de NTE):
# comparar valores diferentes não é conflito.
DECISIVE_FIELDS = CONTEST_LEVEL_FIELDS + ROLE_LEVEL_FIELDS


def _norm(text) -> str:
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^A-Za-z0-9 ]", " ", ascii_text.lower()).split())


def _value_key(field: str, value) -> tuple:
    """Chave de comparação normalizada (não altera o valor exibido)."""
    if field in LOCATION_FIELDS:
        if not isinstance(value, str):
            return ("?",)
        raw = " ".join(value.split())
        if raw.lower() in ("a_divulgar", "a divulgar"):
            return ("a_divulgar",)
        match = re.match(r"(.+?)\s*[/–—-]\s*([A-Za-z]{2})$", raw)
        if match:
            return (_norm(match.group(1)), match.group(2).upper())
        return (_norm(raw.rstrip(" –—-")), None)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return ("n", int(value))
    if isinstance(value, str):
        return ("s", _norm(value))
    return ("j", json.dumps(value, sort_keys=True, ensure_ascii=False))


def _parse_day(value):
    if not isinstance(value, str) or len(value) < 10:
        return None
    from datetime import date
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _document_day(row):
    """Data do documento: publicação quando existe, senão descoberta (nunca inventada)."""
    for candidate in (row.get("published_at"), row.get("discovered_at")):
        day = _parse_day(candidate)
        if day:
            return day
    return None


def _rows(db_path, fields):
    placeholders = ",".join("?" for _ in fields)
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = conn.execute(f"""
            SELECT p.id, p.contest_id, p.role_id, p.field_name, p.value_json,
                   p.ambiguity_reason, d.id, d.title, d.tipo_documental, d.published_at,
                   d.discovered_at, v.id, e.page_number, e.quote,
                   (SELECT r.decision FROM revisoes_campo r WHERE r.proposal_id=p.id
                    ORDER BY r.reviewed_at DESC, r.rowid DESC LIMIT 1)
            FROM propostas_campo p
            JOIN evidencias e ON e.id=p.evidence_id
            JOIN versoes_documento v ON v.id=e.version_id
            JOIN documentos d ON d.id=v.document_id
            WHERE p.field_name IN ({placeholders})
            ORDER BY p.contest_id, p.field_name, p.role_id, d.published_at, d.discovered_at
            """, tuple(fields)).fetchall()
    out = []
    for row in rows:
        try:
            value = json.loads(row[4])
        except (TypeError, ValueError):
            value = row[4]
        out.append({
            "proposal_id": row[0], "contest_id": row[1], "role_id": row[2],
            "field_name": row[3], "value": value, "ambiguity_reason": row[5],
            "document_id": row[6], "document_title": row[7], "document_type": row[8],
            "published_at": row[9], "discovered_at": row[10], "version_id": row[11],
            "page_number": row[12], "quote": row[13], "decision": row[14],
        })
    return out


def _authoritative(row) -> bool:
    """Prazo só vale de documento autoritativo; demais campos aceitam qualquer documento."""
    if row["field_name"] in DEADLINE_FIELDS:
        return (row["document_type"] or "") in AUTHORITATIVE_DOC_TYPES
    return True


def _classify(items: list[dict], field: str) -> dict | None:
    """Classifica um grupo de propostas do mesmo concurso/campo/escopo."""
    active = [item for item in items if item["decision"] != "rejeitado"]
    if len(active) < 2:
        return None
    keys = {_value_key(field, item["value"]) for item in active}
    if field in LOCATION_FIELDS:
        # Local: município sem UF e o mesmo município com UF são o mesmo lugar; várias
        # cidades no mesmo valor são legítimas (compara conjuntos, não strings).
        sets = []
        for item in active:
            if not isinstance(item["value"], str):
                continue
            parts = [part.strip() for part in item["value"].split(";") if part.strip()]
            sets.append({_value_key(field, part) for part in parts})
        if sets:
            names = [{key[0] for key in group} for group in sets]
            ufs = {key[1] for group in sets for key in group if len(key) > 1 and key[1]}
            if all(name_set == names[0] for name_set in names) and len(ufs) <= 1:
                return None
    if len(keys) == 1:
        raw = {json.dumps(item["value"], ensure_ascii=False) for item in active}
        if len(raw) == 1:
            return None
        return {"tipo": "equivalente",
                "motivo": "valores diferentes na forma, equivalentes após normalização",
                "valores": active}
    if field in LOCATION_FIELDS and ("a_divulgar",) in keys:
        others = [item for item in active
                  if _value_key(field, item["value"]) != ("a_divulgar",)]
        if others:
            return {"tipo": "escopo_diferente",
                    "motivo": ("um documento declara que o local será divulgado depois e "
                               "outro cita local concreto; não é divergência de valor"),
                    "valores": active}
    dated = [(item, _document_day(item)) for item in active]
    if all(day is not None for _, day in dated):
        latest = max(day for _, day in dated)
        newest = [item for item, day in dated if day == latest]
        older = [item for item, day in dated if day != latest]
        newest_keys = {_value_key(field, item["value"]) for item in newest}
        if len(newest_keys) > 1:
            return {"tipo": "divergencia_mesmo_documento",
                    "motivo": ("o documento mais recente traz valores diferentes para o "
                               "campo; não há como escolher sem revisão"),
                    "valores": active}
        if older:
            return {"tipo": "retificacao_posterior",
                    "motivo": "documento mais recente traz valor diferente do anterior",
                    "vigente": newest[0], "substituidos": older, "valores": active}
    return {"tipo": "divergencia_sem_ordem",
            "motivo": "valores divergentes sem ordem temporal confiável",
            "valores": active}


def conflicts(db_path, *, fields=None, contest_id=None, limit=500) -> dict:
    """Conflitos de valor entre documentos, com vigente/substituído quando há ordem."""
    fields = tuple(fields or DECISIVE_FIELDS)
    unknown = [field for field in fields if field not in DECISIVE_FIELDS]
    if unknown:
        raise ValueError(f"campo fora do escopo decisivo: {unknown[0]}")
    rows = _rows(db_path, fields)
    if contest_id:
        rows = [row for row in rows if row["contest_id"] == contest_id]
    grouped: dict[tuple, list[dict]] = {}
    for row in rows:
        if not _authoritative(row):
            continue
        # Escopo: campo de concurso não se compara entre cargos, e campo de cargo só é
        # comparável quando o cargo está reconciliado (senão são cargos distintos).
        if row["field_name"] in CONTEST_LEVEL_FIELDS and row["role_id"] is not None:
            continue
        if row["field_name"] in ROLE_LEVEL_FIELDS and row["role_id"] is None:
            continue
        grouped.setdefault((row["contest_id"], row["field_name"], row["role_id"]), []).append(row)
    items = []
    for (cid, field, role_id), group in grouped.items():
        classified = _classify(group, field)
        if classified is None or classified["tipo"] == "equivalente":
            continue
        classified.update({"contest_id": cid, "field_name": field, "role_id": role_id})
        items.append(classified)
    items.sort(key=lambda item: (item["tipo"], item["contest_id"], item["field_name"]))
    counts = {}
    for item in items:
        counts[item["tipo"]] = counts.get(item["tipo"], 0) + 1
    return {"version": CONFLICT_VERSION, "total": len(items), "por_tipo": counts,
            "itens": items[:max(0, int(limit))],
            "limitacao": ("Conflito é divergência documental registrada, não erro comprovado. "
                          "O valor vigente é candidato até decisão humana; nada é apagado.")}


def contest_conflict_ids(db_path, *, fields=None) -> set[str]:
    """Concursos com conflito real (exclui equivalência e escopo diferente)."""
    report = conflicts(db_path, fields=fields, limit=100000)
    return {item["contest_id"] for item in report["itens"]
            if item["tipo"] in ("retificacao_posterior", "divergencia_sem_ordem")}
