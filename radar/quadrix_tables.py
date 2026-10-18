"""Estratégia específica para os quadros de vagas dos editais da Quadrix (PDF textual).

Diagnóstico da Fase 13: os editais da banca têm quadro de vagas em texto de PDF com
**duas linhas de cabeçalho** — um grupo de colunas ("Vagas efetivas"/"Vagas imediatas")
e o grupo de "Cadastro de reserva", cada um repetindo as mesmas modalidades — seguido de
linhas ``[código] rótulo <modalidades imediatas> <modalidades de reserva> <total>``.
O extrator genérico (`vacancy_tables`) opera sobre linhas com células separadas por
``" | "`` (HTML); o caminho de PDF anterior (`document_fields._pdf_table_proposals`) só
reconhecia o layout do DOU. Esta estratégia reconhece o layout da banca sem alterar as
regras já aprovadas para outras fontes.

Regras de contagem documentadas:
- ``immediate_vacancies`` = soma das modalidades sob o grupo "Vagas efetivas/imediatas".
- ``reserve_vacancies`` = soma das modalidades sob "Cadastro de reserva".
- ``indigenous_vacancies`` = valor da modalidade indígena **do grupo imediato**, quando a
  coluna existir (ex.: ``PI`` = pessoas indígenas, confirmado pela legenda do edital).
  Sem coluna indígena, nenhuma proposta indígena é gerada (não se inventa zero).
- A célula ``-`` é o marcador explícito de "sem vaga" (zero) da banca; a soma é conferida
  contra a coluna "Total de vagas" quando presente. Linha cuja soma não confere é
  descartada (não se propõe número incerto).
"""

from __future__ import annotations

import json
import re

# Modalidades reconhecidas nos cabeçalhos da Quadrix (rótulos curtos em maiúsculas).
MODALITY_TOKENS = frozenset({
    "AC", "PCD", "PN", "PI", "PQ", "PPP", "PPI", "HIPO", "IND", "INDIG", "INDIGENA", "Q",
})
# Modalidades que representam reserva indígena.
INDIGENOUS_TOKENS = frozenset({"PI", "IND", "INDIG", "INDIGENA"})

_HEADER_SIGNATURES = ("VAGAS EFETIVAS", "VAGAS IMEDIATAS")


def _is_value(token: str) -> bool:
    return token == "-" or token.isdigit()


def _is_code(token: str) -> bool:
    return token.isdigit() and 2 <= len(token) <= 4


def _is_terminator(token: str) -> bool:
    low = token.lower().rstrip(":.")
    if low in ("legenda", "anexo", "total"):
        return True
    # Números de seção como "2.1.2" ou "4.2".
    parts = token.split(".")
    return len(parts) >= 2 and all(part.isdigit() for part in parts)


def _tokenize(text: str) -> list[tuple[str, int, int]]:
    """Tokeniza preservando offsets de caractere de cada token."""
    import re
    return [(m.group(), m.start(), m.end()) for m in re.finditer(r"\S+", text)]


def _parse_quantity(token: str) -> int | None:
    if token == "-":
        return 0  # marcador explícito de "sem vaga" na banca
    if token.isdigit():
        return int(token)
    return None


def _modality_run(tokens, start):
    """Sequência maximal de modalidades conhecidas a partir de ``start``."""
    run = []
    i = start
    while i < len(tokens) and tokens[i][0] in MODALITY_TOKENS:
        run.append(tokens[i][0])
        i += 1
    return run, i


def parse_quadrix_proposals(blocks: list[dict], contest_id: str, *, label_prefix: str,
                            method: str = "tabela-quadrix-pdf") -> list[dict]:
    """Extrai propostas dos quadros de vagas da Quadrix presentes em blocos de PDF."""
    proposals = []
    for index, block in enumerate(blocks):
        if block.get("page_number") is None:
            continue  # só PDF textual (linhas de HTML têm separador de célula)
        text = block["text"]
        upper = text.upper()
        import re
        positions = sorted({m.start() for sig in _HEADER_SIGNATURES
                            for m in re.finditer(re.escape(sig), upper)})
        if not positions:
            continue
        proposals.extend(_extract_page(block, index, positions, contest_id, label_prefix, method))
    return proposals


# Localidade da vaga: aparece logo após o total da linha, antes da carga horária
# ("Cachoeiro de Itapemirim 40h"). É lotação/município da vaga, **não** local de prova.
_LOCALITY = re.compile(
    r"\s+([A-ZÀ-Þ][A-Za-zÀ-ÿ'’\-]+(?:\s+(?:de|da|do|das|dos|e|[A-ZÀ-Þ][A-Za-zÀ-ÿ'’\-]+)){0,5})"
    r"\s+\d{1,3}\s*h\b")


def _locality_after_row(text: str, row_end: int) -> dict | None:
    """Município/lotação imediatamente após a linha do quadro, com offsets."""
    window = text[row_end:row_end + 140]
    match = _LOCALITY.match(window)
    if match is None:
        return None
    value = " ".join(match.group(1).split())
    if len(value) < 3 or len(value) > 80:
        return None
    return {"value": value, "start": row_end + match.start(1),
            "end": row_end + match.end(1)}


def _extract_page(block, index, header_positions, contest_id, label_prefix, method):
    text = block["text"]
    tokens = _tokenize(text)
    proposals = []
    for n, pos in enumerate(header_positions):
        # Segmento da página até o próximo cabeçalho (ou fim).
        segment_end = header_positions[n + 1] if n + 1 < len(header_positions) else len(text)
        # Primeiro token do segmento com offset >= pos.
        seg_tokens = [t for t in tokens if pos <= t[1] < segment_end]
        if not seg_tokens:
            continue
        # Localiza a sequência de modalidades (cabeçalho de duas linhas): o maior
        # trecho de modalidades conhecidas que contenha "AC".
        run = None
        run_end_token = None
        for j, token in enumerate(seg_tokens):
            if token[0] not in MODALITY_TOKENS:
                continue
            if j > 0 and seg_tokens[j - 1][0] in MODALITY_TOKENS:
                continue  # não é o início de um trecho de modalidades
            candidate, end = _modality_run(seg_tokens, j)
            if "AC" in candidate and len(candidate) >= 2 and (run is None or len(candidate) > len(run)):
                run, run_end_token = candidate, end
        if run is None or len(run) % 2 != 0:
            continue
        half = len(run) // 2
        if run[:half] != run[half:]:
            continue  # grupos imediato/reserva divergentes: layout não reconhecido
        modalities = run[:half]
        if "AC" not in modalities:
            continue
        indigenous_index = next(
            (k for k, tok in enumerate(modalities) if tok in INDIGENOUS_TOKENS), None)
        width = 2 * half + 1  # imediatas + reserva + total
        data_tokens = seg_tokens[run_end_token:]
        has_code = bool(data_tokens) and _is_code(data_tokens[0][0])
        proposals.extend(_rows(
            block, index, data_tokens, has_code, width, half, modalities, indigenous_index,
            contest_id, label_prefix, method))
    return proposals


def _rows(block, index, data_tokens, has_code, width, half, modalities, indigenous_index,
          contest_id, label_prefix, method):
    text = block["text"]
    out = []
    i = 0
    n = len(data_tokens)
    while i < n:
        token = data_tokens[i][0]
        if _is_terminator(token):
            break
        code = None
        if has_code:
            # Ancora a linha no código: precisa ser seguido por rótulo (não valor).
            nxt = data_tokens[i + 1][0] if i + 1 < n else None
            if not (_is_code(token) and nxt is not None and not _is_value(nxt)):
                i += 1
                continue
            code = token
            row_start = data_tokens[i][1]
            i += 1
        else:
            row_start = data_tokens[i][1]
        label_parts = []
        hit_terminator = False
        while i < n and not _is_value(data_tokens[i][0]):
            if _is_terminator(data_tokens[i][0]):
                hit_terminator = True
                break
            label_parts.append(data_tokens[i][0])
            i += 1
        if hit_terminator:
            break
        if not label_parts:
            i += 1  # token inesperado entre linhas: segue, não aborta a página
            continue
        values = []
        while i < n and len(values) < width and _is_value(data_tokens[i][0]):
            values.append(data_tokens[i][0])
            i += 1
        # A corrida de valores precisa ter exatamente `width` e o token seguinte não
        # pode ser outro valor (evita deslocamento de coluna que passaria na soma).
        if len(values) != width or (i < n and _is_value(data_tokens[i][0])):
            while i < n and _is_value(data_tokens[i][0]):
                i += 1
            continue  # linha ambígua: não se propõe valor incerto
        numbers = [_parse_quantity(v) for v in values]
        if any(v is None for v in numbers):
            continue
        immediate = numbers[:half]
        reserve = numbers[half:2 * half]
        total = numbers[2 * half]
        if sum(immediate) + sum(reserve) != total:
            continue  # soma não confere com o total: descarta a linha
        label = " ".join(label_parts)
        row_end = data_tokens[i - 1][2]
        if code:
            label = f"{code} {label}"
        quote = text[row_start:row_end]
        ambiguity = label_prefix + label
        evidence = dict(block_index=index, quote=quote, start_offset=row_start,
                        end_offset=row_end, page_number=block.get("page_number"),
                        header=" | ".join(modalities), section=None, role_label=label)
        fields = {
            "immediate_vacancies": sum(immediate),
            "reserve_vacancies": sum(reserve),
        }
        if indigenous_index is not None:
            # Coluna indígena do grupo imediato e do grupo de reserva (semânticas distintas).
            fields["indigenous_vacancies"] = immediate[indigenous_index]
            fields["indigenous_reserve_vacancies"] = reserve[indigenous_index]
        for field, value in fields.items():
            out.append(dict(contest_id=contest_id, role_id=None, field_name=field,
                            value_json=json.dumps(value), value_type="integer",
                            extraction_method=method, ambiguity_reason=ambiguity,
                            evidence=dict(evidence)))
        # Município/lotação do código (opção de inscrição). A evidência abrange a linha
        # inteira (código, cargo, valores e localidade): a localidade é daquele código,
        # e dois códigos com o mesmo município continuam sendo registros distintos.
        locality = _locality_after_row(text, row_end)
        if locality:
            local_evidence = dict(evidence, quote=text[row_start:locality["end"]],
                                  start_offset=row_start,
                                  end_offset=locality["end"])
            out.append(dict(contest_id=contest_id, role_id=None,
                            field_name="vaga_municipio",
                            value_json=json.dumps(locality["value"]),
                            value_type="string", extraction_method=method,
                            ambiguity_reason=ambiguity,
                            evidence=dict(local_evidence)))
    return out
