"""Quadro de vagas com **total agregado** (ex.: IBFC) — sem inventar distribuição.

Formato real observado nos editais IBFC (verificado em 2026-10-17, concurso `ibfc-490`):

```
ANEXO I – QUADRO DE VAGAS
Função Temporária | Núcleo Territorial de Educação - NTE | Total de Vagas (Ampla, Negros e PCD)*
Professor Orientador de Estágio em Saúde - Enfermagem 01 – Sede: Irecê 06 ... 26 - Sede: Salvador 40
Professor Orientador de Estágio em Saúde - Radiologia 26 - Sede: Salvador 06
TOTAL 228
(*) Total de vagas incluindo as reservadas para candidatos com deficiência e a reserva de
vagas para negros.
```

A coluna publicada é **um total por linha**, que já inclui ampla, negros e PCD. O edital não
publica a abertura por modalidade nem menciona indígenas.

Regra de ouro: esse número vira ``vagas_total_publicado`` — **nunca**
``immediate_vacancies``, ``indigenous_vacancies`` ou ``reserve_vacancies``. Dividir o total por
percentual seria inventar a distribuição, exatamente o erro que produz falsa oportunidade.

Quando o cabeçalho tem colunas explícitas por modalidade, cada coluna vira o campo
correspondente (comportamento do extrator genérico, aqui protegido contra o rótulo agregado).
"""

from __future__ import annotations

import json
import re
import unicodedata

FIELD_TOTAL = "vagas_total_publicado"
METHOD = "quadro-vagas-agregado"

# Cabeçalho agregado: "Total de Vagas (Ampla, Negros e PCD)*".
_AGG_HEADER = re.compile(
    r"TOTAL\s+DE\s+VAGAS\s*(?:\(([^)]{3,160})\))?", re.IGNORECASE)
# Quantidade: aceita separador de milhar ("1.500") e normaliza para inteiro.
_QTY = r"(\d{1,3}(?:\.\d{3})+|\d{1,6})"
# Linha: "[NN –] Sede: <Localidade> <quantidade>" (case-insensitive: "SEDE:" existe).
# Localidade: só letras, espaços, apóstrofo e hífen. Sem dígitos/pontos — senão a regex
# engole a quantidade e o "TOTAL" seguinte como se fossem parte do nome.
_ROW = re.compile(
    r"(?:(\d{1,2})\s*[-–—]?\s*)?Sede\s*:\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' \-]{1,58}?)\s+"
    + _QTY + r"\b", re.I)
# Total do quadro.
_TOTAL = re.compile(r"\bTOTAL\s+" + _QTY + r"\b", re.I)
# Fim da tabela: próximo anexo/quadro (evita capturar linhas e TOTAL de outra tabela).
_REGION_END = re.compile(r"\bANEXO\b|\bQUADRO\s+DE\s+VAGAS\b|\bTABELA\b", re.I)


def _qty(text: str) -> int:
    return int(text.replace(".", ""))
# Nota de rodapé que explica o agregado.
_FOOTNOTE = re.compile(
    r"\(\s*\*\s*\)\s*Total\s+de\s+vagas\s+incluindo([^.]{0,240})", re.IGNORECASE)

# Nomes de coluna que não são cargo (o cargo não está na tabela).
_GENERIC_CARGO = {"MUNICIPIO", "FUNCAO TEMPORARIA", "CARGO", "ESPECIALIDADE", "NTE",
                  "NUCLEO TERRITORIAL DE EDUCACAO NTE", "TOTAL DE VAGAS"}

_MODALITY_WORDS = {
    "AMPLA": "ampla",
    "NEGROS": "negros",
    "NEGRA": "negros",
    "PCD": "pcd",
    "DEFICIENCIA": "pcd",
    "INDIGENA": "indigena",
    "INDIGENAS": "indigena",
    "QUILOMBOLA": "quilombola",
    "COTAS": "cotas",
}


def _norm(text: str) -> str:
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(ascii_text.upper().split())


def _modalities(header_clause: str | None) -> list[str]:
    if not header_clause:
        return []
    found = []
    for word in re.split(r"[,;/&]|\s+E\s+", _norm(header_clause)):
        word = word.strip(" .()")
        for token, canonical in _MODALITY_WORDS.items():
            if token in word and canonical not in found:
                found.append(canonical)
    return found


def _cargo_from(segment: str) -> str | None:
    """Cargo no texto entre a última linha e o cabeçalho (nunca um número ou 'Sede')."""
    cleaned = " ".join(segment.split())
    cleaned = cleaned.strip(" *()[]")
    cleaned = re.sub(r"^[\d\s\-–—\.*]+", "", cleaned)
    if len(cleaned) < 8:
        return None
    if _norm(cleaned).startswith("SEDE"):
        return None
    if not re.search(r"[A-Za-zÀ-ÿ]{4}", cleaned):
        return None
    # Segmento com números é lista de municípios/quantidades, não cargo: nesse layout
    # (NTE por município) o cargo não está na tabela e não pode ser adivinhado.
    if re.search(r"\d", cleaned):
        return None
    norm = _norm(cleaned)
    if norm in _GENERIC_CARGO or norm.startswith(("MUNICIPIO", "TOTAL DE VAGAS")):
        return None
    # Evita capturar o título do anexo como cargo.
    if _norm(cleaned).startswith(("ANEXO", "QUADRO DE VAGAS", "TOTAL")):
        tail = re.split(r"(?i)quadro\s+de\s+vagas", cleaned)[-1]
        cleaned = " ".join(tail.split())
        if len(cleaned) < 8:
            return None
    return cleaned[:160]


def parse_aggregate_table(blocks: list[dict], contest_id: str, *,
                          label_prefix: str) -> list[dict]:
    """Extrai ``vagas_total_publicado`` de quadros com total agregado.

    Devolve propostas no contrato de ``document_fields``. Não emite nenhum campo por
    modalidade quando o documento só publica o total.
    """
    proposals = []
    for index, block in enumerate(blocks):
        text = block.get("text") or ""
        if not isinstance(text, str) or "TOTAL DE VAGAS" not in _norm(text):
            continue
        header = _AGG_HEADER.search(text)
        if header is None:
            continue
        clause = header.group(1)
        modalities = _modalities(clause)
        # Só trata como agregado quando o cabeçalho nomeia modalidades (2+ ou 1 explícita
        # somada ao total). "Total de vagas" sem qualificação continua sendo total simples.
        if len(modalities) < 2:
            continue
        body_start = header.end()
        # A tabela termina no próximo anexo/quadro: linhas e TOTAL de outra tabela não entram.
        boundary = _REGION_END.search(text, body_start)
        region_end = boundary.start() if boundary else len(text)
        rows = [row for row in _ROW.finditer(text, body_start, region_end)]
        if not rows:
            continue
        totals = list(_TOTAL.finditer(text, body_start, region_end))
        total_match = totals[-1] if totals else None
        footnote = _FOOTNOTE.search(text, body_start, region_end)
        total_value = _qty(total_match.group(1)) if total_match else None
        cargo = _cargo_from(text[body_start:rows[0].start()])
        parsed_rows = []
        previous_end = rows[0].start()
        for position, row in enumerate(rows):
            between = text[previous_end:row.start()]
            candidate = _cargo_from(between)
            if candidate:
                cargo = candidate
            previous_end = row.end()
            quantity = _qty(row.group(3))
            parsed_rows.append({"cargo": cargo, "localidade": " ".join(row.group(2).split()),
                                "quantidade": quantity, "quote": row.group(0),
                                "start": row.start(), "end": row.end()})
        sum_rows = sum(row["quantidade"] for row in parsed_rows)
        notes = []
        notes.append("total agregado publicado ("
                     + " + ".join(modalities) + "): não distribuir por modalidade")
        if footnote:
            notes.append("nota do edital: total inclui as reservas")
        if total_value is not None and total_value != sum_rows:
            notes.append(f"conflito: TOTAL {total_value} difere da soma das linhas {sum_rows}")
        reason_base = "; ".join(notes)

        for row in parsed_rows:
            if not row["cargo"]:
                continue
            reason = f"{label_prefix}{row['cargo']} — {reason_base}"
            proposals.append(dict(
                contest_id=contest_id, role_id=None, field_name=FIELD_TOTAL,
                value_json=json.dumps(row["quantidade"]), value_type="integer",
                extraction_method=METHOD, ambiguity_reason=reason,
                evidence=dict(block_index=index, quote=row["quote"],
                              start_offset=row["start"], end_offset=row["end"])))
        if total_value is not None:
            quote = total_match.group(0)
            proposals.append(dict(
                contest_id=contest_id, role_id=None, field_name=FIELD_TOTAL,
                value_json=json.dumps(total_value), value_type="integer",
                extraction_method=METHOD,
                ambiguity_reason=("total do quadro — " + reason_base),
                evidence=dict(block_index=index, quote=quote,
                              start_offset=total_match.start(),
                              end_offset=total_match.end())))
    return proposals


def aggregate_summary(blocks: list[dict]) -> dict:
    """Resumo do quadro para diagnóstico (sem gravar nada)."""
    for index, block in enumerate(blocks):
        text = block.get("text") or ""
        header = _AGG_HEADER.search(text) if isinstance(text, str) else None
        if header is None:
            continue
        modalities = _modalities(header.group(1))
        boundary = _REGION_END.search(text, header.end())
        region_end = boundary.start() if boundary else len(text)
        rows = list(_ROW.finditer(text, header.end(), region_end))
        totals = list(_TOTAL.finditer(text, header.end(), region_end))
        total = totals[-1] if totals else None
        return {"block_index": index, "modalidades": modalities,
                "linhas": len(rows),
                "soma": sum(_qty(row.group(3)) for row in rows),
                "total_publicado": _qty(total.group(1)) if total else None,
                "nota_de_rodape": bool(_FOOTNOTE.search(text, header.end())),
                "agregado": len(modalities) >= 2}
    return {"agregado": False, "linhas": 0}
