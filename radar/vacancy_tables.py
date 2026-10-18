"""Extrator genérico de quadro de vagas por cargo e modalidade.

Recebe linhas já extraídas (blocos com texto) e devolve propostas no contrato de
`document_fields`. Não conhece HTML nem PDF e não importa `document_fields`
(o prefixo de rótulo é injetado pelo chamador), evitando import circular.
"""

from __future__ import annotations

import json
import re
import unicodedata


# Tokens que identificam a coluna de identificação do cargo.
_ROLE_TOKENS = ("CARGO", "ESPECIALIDADE", "FUNCAO", "EMPREGO", "AREA", "OCUPACAO")
# Tokens de quantidade por modalidade (precedência: mais específico primeiro).
# "AMPLA" NÃO mapeia vagas imediatas: é uma modalidade (subconjunto), não o total.
_INDIGENA_TOKENS = ("INDIGENA", "INDIGENAS")
_RESERVE_TOKENS = ("CADASTRO DE RESERVA", "RESERVA")
_IMMEDIATE_TOKENS = ("VAGAS TOTAIS", "VAGAS IMEDIATAS", "IMEDIATAS", "VAGAS")
_TOTAL_ROLE_TOKENS = ("TOTAL", "TOTAL GERAL")

_CR_HEADER_RE = re.compile(r"\bCR\b")
_INT_RE = re.compile(r"\d+")
_SEPARATOR = " | "


def normalize(text) -> str:
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(ascii_text.upper().split())


# Modalidades de reserva/acesso: um cabeçalho que nomeia 2+ delas está publicando um
# **agregado**, não uma coluna única de vagas imediatas.
_MODALITY_TOKENS = ("AMPLA", "NEGROS", "NEGRA", "PCD", "DEFICIENCIA", "INDIGENA",
                    "INDIGENAS", "QUILOMBOLA", "COTAS")


def _is_aggregate_header(header_cell: str) -> bool:
    """Cabeçalho que publica um **total** já somando modalidades.

    Ex.: ``TOTAL DE VAGAS (AMPLA, NEGROS E PCD)``, ``VAGAS TOTAIS (AMPLA, NEGROS E PCD)``,
    ``QUANTIDADE DE VAGAS (AMPLA, NEGROS, PCD E INDÍGENAS)``. Mapear qualquer uma delas para
    vagas imediatas ou indígenas inventaria a distribuição — o erro que o projeto proíbe.
    A decisão é pelos **tokens de modalidade**, não pela palavra "TOTAL" (que aparece como
    "TOTAIS" e às vezes não aparece).
    """
    norm = normalize(header_cell)
    # Colunas separadas por modalidade são legítimas ("AMPLA", "INDIGENAS"…): o que
    # caracteriza agregado é a **lista entre parênteses** ou a palavra total.
    parenthetical = re.search(r"\(([^)]{3,160})\)", header_cell)
    if parenthetical:
        inside = normalize(parenthetical.group(1))
        modalities = {token for token in _MODALITY_TOKENS if token in inside}
        if len(modalities) >= 2:
            return True
    modalities = {token for token in _MODALITY_TOKENS if token in norm}
    return bool(modalities) and ("TOTAL" in norm or "TOTAIS" in norm)


def _field_for(header_cell: str) -> str | None:
    if _is_aggregate_header(header_cell):
        return None  # total agregado: tratado por `vacancy_aggregate`
    if any(token in header_cell for token in _INDIGENA_TOKENS):
        return "indigenous_vacancies"
    # "CR" só como palavra isolada (evita casar CRECHE, INSCRIÇÕES, CRONOGRAMA).
    if any(token in header_cell for token in _RESERVE_TOKENS) or _CR_HEADER_RE.search(header_cell):
        return "reserve_vacancies"
    if any(token in header_cell for token in _IMMEDIATE_TOKENS):
        return "immediate_vacancies"
    return None


def map_columns(header_cells: list[str]) -> tuple[int | None, dict[str, int]]:
    """Devolve (coluna_do_cargo, {campo: coluna}) independente da ordem das colunas."""
    header_norm = [normalize(cell) for cell in header_cells]
    role_column = None
    for index, cell in enumerate(header_norm):
        if any(token in cell for token in _ROLE_TOKENS):
            role_column = index
            break
    columns: dict[str, int] = {}
    for index, cell in enumerate(header_norm):
        field = _field_for(cell)
        if field and field not in columns:
            columns[field] = index
    return role_column, columns


def parse_quantity(cell) -> int | None:
    """Inteiro explícito na célula (inclui 0) ou ``None`` quando ausente/não numérico.

    Uma célula como ``"69 + CR*"`` devolve ``69`` (a quantidade imediata); o texto
    do cadastro de reserva permanece na evidência (``quote``), sem virar número.
    """
    if not isinstance(cell, str):
        return None
    match = _INT_RE.search(cell)
    return int(match.group()) if match else None


def _is_total(label: str) -> bool:
    norm = normalize(label)
    return any(norm == token or norm.startswith(token) for token in _TOTAL_ROLE_TOKENS)


def header_score(group: list[dict]) -> int:
    """Número de modalidades de vaga mapeadas no cabeçalho do grupo (0 se não há)."""
    for position in range(len(group)):
        candidate = _candidate_header(group, position)
        if candidate is not None:
            _, columns = map_columns(candidate[0])
            return len(columns)
    return 0


def best_table(groups: list[list[dict]]) -> list[dict] | None:
    """Escolhe o grupo de linhas com o quadro de vagas mais completo (mais modalidades).

    Evita somar o mesmo fato declarado em duas tabelas do mesmo documento (ex.: uma
    tabela simples `CARGO|VAGAS` e o quadro de cotas). Empate mantém o primeiro.
    """
    best = None
    best_score = 0
    for group in groups:
        score = header_score(group)
        if score > best_score:
            best_score, best = score, group
    return best


def _candidate_header(rows: list[dict], position: int):
    """Reconhece um cabeçalho (de uma ou duas linhas) a partir de ``position``.

    Devolve ``(header_cells, data_start)`` ou ``None``. Um cabeçalho de duas linhas
    ocorre quando a segunda linha completa colunas vazias da primeira (ex.:
    ``CARGO | VAGAS`` seguido de ``| TOTAL | INDÍGENAS``).
    """
    row_cells = rows[position]["text"].split(_SEPARATOR)
    role_column, columns = map_columns(row_cells)
    if role_column is None or not columns:
        return None
    if position + 1 < len(rows):
        next_cells = rows[position + 1]["text"].split(_SEPARATOR)
        if len(next_cells) == len(row_cells):
            merged = [a if normalize(a) else b for a, b in zip(row_cells, next_cells)]
            merged_role, merged_columns = map_columns(merged)
            if merged_role is not None and len(merged_columns) > len(columns):
                return merged, position + 2
    return row_cells, position + 1


def extract(rows: list[dict], contest_id: str, *, label_prefix: str,
            section_title: str | None = None, method: str = "tabela") -> list[dict]:
    """Extrai propostas de um quadro de vagas, com evidência.

    ``rows`` é uma lista de blocos de linha, cada um com ``index`` (índice do bloco
    na versão), ``text`` (células separadas por ``" | "``) e ``page_number``.
    A primeira linha com cabeçalho reconhecido define o papel das colunas. Um total
    global nunca é replicado por cargo; célula vazia não gera proposta; ``CR`` sem
    número não vira zero nem vaga imediata.
    """
    header_cells = None
    data_start = None
    for position in range(len(rows)):
        candidate = _candidate_header(rows, position)
        if candidate is not None:
            header_cells, data_start = candidate
            break
    if header_cells is None:
        return []

    role_column, columns = map_columns(header_cells)
    header_text = _SEPARATOR.join(header_cells)
    width = len(header_cells)
    proposals = []
    for row in rows[data_start:]:
        cells = row["text"].split(_SEPARATOR)
        if len(cells) != width or role_column >= len(cells):
            continue
        label = " ".join(cells[role_column].split())
        if not label:
            continue
        total_row = _is_total(label)
        ambiguity = None if total_row else label_prefix + label
        base_evidence = dict(block_index=row["index"], quote=row["text"],
                             start_offset=0, end_offset=len(row["text"]),
                             page_number=row.get("page_number"), header=header_text,
                             section=section_title,
                             role_label=None if total_row else label)
        for field, column in columns.items():
            if column >= len(cells):
                continue
            cell = cells[column]
            value = parse_quantity(cell)
            if field == "reserve_vacancies":
                # Reserva só com número explícito; "CR" sem número é desconhecido.
                if value is None:
                    continue
            elif value is None:
                continue
            proposals.append(dict(
                contest_id=contest_id, role_id=None, field_name=field,
                value_json=json.dumps(value), value_type="integer",
                extraction_method=method, ambiguity_reason=ambiguity,
                evidence=dict(base_evidence)))
    return proposals
