"""Distribuição de vagas publicada em texto corrido (sem quadro).

Alguns editais publicam a distribuição na abertura, em uma frase: "restando a seguinte
distribuição: 19 (dezenove) vagas para ampla concorrência, 01 (uma) vaga para pessoas com
deficiência, … 1 (uma) vaga para indígenas e 1 (uma) vaga para quilombolas".

Regras:

- a quantidade é a **publicada**; percentual no corpo do edital não é convertido em vaga;
- o cargo vem da mesma frase do total ("provimento de N vagas no cargo de X"); sem essa
  amarração estrutural, nenhuma proposta é gerada;
- a soma das modalidades é conferida contra o total; divergência é registrada, não
  corrigida;
- a natureza é imediata apenas quando o texto fala de provimento/oferta; cadastro de
  reserva no mesmo trecho impede a leitura como vaga imediata.
"""

from __future__ import annotations

import json
import re

VERSION = "vagas_texto_v1"

TOTAL_RE = re.compile(
    r"provimento\s+de\s+(?P<total>\d{1,4})\s*\([^)]{2,40}\)\s*vagas?", re.I)
CARGO_RE = re.compile(
    r"no\s+cargo\s+de\s+(?P<cargo>[A-ZÀ-Þ][A-ZÀ-Þ0-9\s\-]{3,70}?)"
    r"(?:\s*,|\s*\.|\s+e\s|\s+do\s|\s+da\s|$)", re.I)
DISTRIBUTION_RE = re.compile(r"distribui[çc][ãa]o\s*:", re.I)
ITEM_RE = re.compile(
    r"(?P<count>\d{1,4})\s*\([^)]{2,40}\)\s*vagas?\s+para\s+"
    r"(?P<label>[a-zà-ÿ][a-zà-ÿ\s]{2,60}?)(?=\s*,\s*\d|\s*,\s*e\s*\d|\s+e\s+\d|\.|$)",
    re.I)

MODALITIES = (
    ("AC", re.compile(r"ampla\s+concorr", re.I)),
    ("PCD", re.compile(r"defici", re.I)),
    ("PP", re.compile(r"negros?|negras?|pretas?\s+e\s+pardas?", re.I)),
    ("PI", re.compile(r"ind[íi]genas?", re.I)),
    ("PQ", re.compile(r"quilombolas?", re.I)),
)
FIELD_BY_MODALITY = {
    "AC": None,
    "PCD": None,
    "PP": None,
    "PI": "indigenous_vacancies",
    "PQ": None,
}


def _modalities(label: str) -> set[str]:
    """Todas as modalidades que o rótulo nomeia (mais de uma = vaga unificada)."""
    return {name for name, pattern in MODALITIES if pattern.search(label)}


def parse_distribution(text: str) -> dict | None:
    """Distribuição explícita de vagas no texto (ou ``None`` quando não é uma).

    Devolve ``{"total", "cargo", "items", "combined", "quote"}``. Rótulo que nomeia dois
    grupos ("indígenas e quilombolas") não é vaga exclusiva: vai para ``combined``.
    """
    if not isinstance(text, str):
        return None
    total = TOTAL_RE.search(text)
    if total is None:
        return None
    # O cargo precisa estar na mesma frase do total: proximidade não é amarração.
    sentence = text[total.end():total.end() + 260]
    period = sentence.find(".")
    if period >= 0:
        sentence = sentence[:period]
    cargo = CARGO_RE.search(sentence)
    if cargo is None:
        return None
    marker = DISTRIBUTION_RE.search(text, total.end())
    if marker is None:
        return None
    tail = text[marker.end():marker.end() + 700]
    items, combined, cursor = {}, [], 0
    for match in ITEM_RE.finditer(tail):
        if match.start() < cursor:
            continue
        modalities = _modalities(match.group("label"))
        if not modalities:
            continue
        count = int(match.group("count"))
        if len(modalities) > 1:
            combined.append({"rotulo": " ".join(match.group("label").split()),
                             "quantidade": count, "modalidades": sorted(modalities)})
        else:
            items[modalities.pop()] = count
        cursor = match.end()
    if "PI" not in items and not any("PI" in entry["modalidades"] for entry in combined):
        return None
    start = total.start()
    end = marker.end() + cursor
    return {"total": int(total.group("total")),
            "cargo": " ".join(cargo.group("cargo").split()),
            "items": items, "combined": combined, "quote": text[start:end]}


def extract_distribution(blocks, contest_id: str, *, label_prefix: str) -> dict:
    """Propostas da distribuição explícita em texto corrido."""
    proposals, pendencias, rows = [], [], []
    for index, block in enumerate(blocks):
        text = block.get("text") or ""
        if "distribui" not in text.lower() or "indígen" not in text.lower():
            continue
        parsed = parse_distribution(text)
        if parsed is None:
            continue
        if block.get("page_number") is None:
            continue
        start = text.find(parsed["quote"])
        if start < 0:
            pendencias.append({"causa": "trecho_nao_localizado",
                               "page": block.get("page_number")})
            continue
        end = start + len(parsed["quote"])
        label = parsed["cargo"]
        reason = label_prefix + label
        sum_items = (sum(parsed["items"].values())
                     + sum(entry["quantidade"] for entry in parsed["combined"]))
        consistent = sum_items == parsed["total"]
        if not consistent:
            reason = (reason + " [conflito aritmetico: soma das modalidades "
                      f"{sum_items} != total {parsed['total']}]")
            pendencias.append({"causa": "soma_divergente",
                               "page": block.get("page_number"), "cargo": label,
                               "soma": sum_items, "total": parsed["total"],
                               "quote": parsed["quote"]})
        if parsed["combined"]:
            # Vaga unificada não é vaga exclusiva de nenhum dos grupos.
            pendencias.append({"causa": "modalidade_combinada",
                               "page": block.get("page_number"), "cargo": label,
                               "combinadas": parsed["combined"]})
        reserva_no_trecho = re.search(r"\bCR\b|cadastro\s+de\s+reserva",
                                      parsed["quote"], re.I) is not None
        if reserva_no_trecho:
            # Trecho que mistura imediato e cadastro de reserva não sustenta "imediato".
            pendencias.append({"causa": "cadastro_de_reserva_no_trecho",
                               "page": block.get("page_number"), "cargo": label})
            reason = reason + " [trecho menciona cadastro de reserva]"
        for modality, field in FIELD_BY_MODALITY.items():
            if field is None or modality not in parsed["items"]:
                continue
            proposals.append(dict(
                contest_id=contest_id, role_id=None, field_name=field,
                value_json=json.dumps(parsed["items"][modality]), value_type="integer",
                extraction_method="distribuicao-texto", ambiguity_reason=reason,
                evidence=dict(block_index=index, quote=parsed["quote"],
                              start_offset=start, end_offset=end,
                              page_number=block.get("page_number"),
                              header="distribuição publicada no texto", section=None,
                              role_label=label)))
        if not reserva_no_trecho:
            proposals.append(dict(
                contest_id=contest_id, role_id=None, field_name="immediate_vacancies",
                value_json=json.dumps(parsed["total"]), value_type="integer",
                extraction_method="distribuicao-texto", ambiguity_reason=reason,
                evidence=dict(block_index=index, quote=parsed["quote"],
                              start_offset=start, end_offset=end,
                              page_number=block.get("page_number"),
                              header="distribuição publicada no texto", section=None,
                              role_label=label)))
        rows.append({"page": block.get("page_number"), "cargo": label,
                     "total": parsed["total"], "itens": parsed["items"],
                     "combinadas": parsed["combined"], "consistente": consistent,
                     "quote": parsed["quote"]})
    return {"version": VERSION, "proposals": proposals, "rows": rows,
            "pendencias": pendencias}
