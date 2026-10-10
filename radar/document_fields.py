"""Padrões conservadores; resultados são propostas pendentes de revisão."""

from __future__ import annotations

import json
import re
from datetime import date


_PATTERNS = (
    ('immediate_vacancies', re.compile(r'\b(\d+)\s+vagas?\s+imediatas?\b', re.I)),
    ('reserve_vacancies', re.compile(r'\bn[aã]o\s+haver[áa]\s+cadastro\s+de\s+reserva\s*:\s*(0)\s+vagas?\b', re.I)),
    ('indigenous_vacancies', re.compile(r'\b(\d+)\s+vagas?\s+para\s+pessoas\s+ind[íi]genas\b', re.I)),
)
_REGISTRATION = re.compile(r'\binscri[çc][õo]es\s+de\s+(\d{1,2})\s+a\s+(\d{1,2})/(\d{2})/(\d{4})\b', re.I)
_NUMERIC_RANGE = re.compile(
    r'inscri[çc][õo]es\s+(\d{2})/(\d{2})/(\d{4})[^\d]{1,6}(\d{2})/(\d{2})/(\d{4})', re.I)
_MONTHS = {'janeiro': '01', 'fevereiro': '02', 'março': '03', 'abril': '04', 'maio': '05',
           'junho': '06', 'julho': '07', 'agosto': '08', 'setembro': '09', 'outubro': '10',
           'novembro': '11', 'dezembro': '12'}
_TEXT_PERIOD = re.compile(
    r'dia\s+(\d{1,2})\s+de\s+(' + '|'.join(_MONTHS) + r')\s+de\s+(\d{4})'
    r'.{0,80}?'
    r'dia\s+(\d{1,2})\s+de\s+(' + '|'.join(_MONTHS) + r')\s+de\s+(\d{4})',
    re.IGNORECASE | re.DOTALL,
)

# Prefixo do motivo de ambiguidade de linhas de tabela ainda não reconciliadas
# com uma identidade de cargo. Compartilhado com a projeção e a reconciliação.
LABEL_PREFIX = 'cargo do documento não reconciliado: '
# Uma edição oficial diária reúne vários atos; fatos não ancorados (fora do
# quadro de cotas) exigem conferência de escopo antes de valerem para o concurso.
PDF_SCOPE_REASON = 'edição com múltiplos atos: conferir se o trecho pertence ao edital do concurso'


def label_from_ambiguity(reason: str | None) -> str | None:
    if reason and reason.startswith(LABEL_PREFIX):
        return reason[len(LABEL_PREFIX):]
    return None


def _registration_dates(block_text: str):
    """Devolve pares (field_name, value, quote, start, end) para datas de inscrição reconhecidas."""
    found = []
    for match in _REGISTRATION.finditer(block_text):
        try:
            start = date(int(match.group(4)), int(match.group(3)), int(match.group(1)))
            end = date(int(match.group(4)), int(match.group(3)), int(match.group(2)))
            if start > end:
                continue
        except ValueError:
            continue
        found.append(('registration_start', start.isoformat(), match.group(), match.start(), match.end()))
        found.append(('registration_end', end.isoformat(), match.group(), match.start(), match.end()))
    for match in _NUMERIC_RANGE.finditer(block_text):
        try:
            start = date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
            end = date(int(match.group(6)), int(match.group(5)), int(match.group(4)))
            if start > end:
                continue
        except ValueError:
            continue
        found.append(('registration_start', start.isoformat(), match.group(), match.start(), match.end()))
        found.append(('registration_end', end.isoformat(), match.group(), match.start(), match.end()))
    for match in _TEXT_PERIOD.finditer(block_text):
        try:
            start = date(int(match.group(3)), int(_MONTHS[match.group(2).lower()]), int(match.group(1)))
            end = date(int(match.group(6)), int(_MONTHS[match.group(5).lower()]), int(match.group(4)))
            if start > end:
                continue
        except ValueError:
            continue
        found.append(('registration_start', start.isoformat(), match.group(), match.start(), match.end()))
        found.append(('registration_end', end.isoformat(), match.group(), match.start(), match.end()))
    return found


def _table_proposals(blocks: list[dict], contest_id: str, role_id: str | None) -> list[dict]:
    """Lê o quadro de cotas por cargo, sem replicar o total nem herdar o cargo do documento."""
    header_index = None
    for index, block in enumerate(blocks):
        cells = [cell.strip().upper() for cell in block['text'].split('|')]
        if any('VAGAS TOTAIS' in cell for cell in cells) and any('INDÍGENA' in cell for cell in cells):
            header_index = index
            table = block.get('table')
            total_column = next(i for i, cell in enumerate(cells) if 'VAGAS TOTAIS' in cell)
            indigenous_column = next(i for i, cell in enumerate(cells) if 'INDÍGENA' in cell)
            width = len(cells)
            break
    if header_index is None:
        return []
    proposals = []
    for index in range(header_index + 1, len(blocks)):
        block = blocks[index]
        if block.get('table') != table:
            break
        cells = [cell.strip() for cell in block['text'].split('|')]
        if len(cells) != width:
            continue
        if not (cells[total_column].isdigit() and cells[indigenous_column].isdigit()):
            continue
        label = cells[0]
        ambiguity = None if label.upper() == 'TOTAL' else LABEL_PREFIX + label
        evidence = dict(block_index=index, quote=block['text'],
                        start_offset=0, end_offset=len(block['text']))
        for field, column in (('immediate_vacancies', total_column),
                              ('indigenous_vacancies', indigenous_column)):
            proposals.append(dict(contest_id=contest_id, role_id=None, field_name=field,
                value_json=json.dumps(int(cells[column])), value_type='integer',
                extraction_method='tabela', ambiguity_reason=ambiguity, evidence=dict(evidence)))
    return proposals


_PDF_HEADER_TOKENS = ('VAGAS TOTAIS', 'PCD', 'NEGROS', 'QUILOMBOLAS', 'AMPLA')
# Seis inteiros consecutivos que terminam o segmento numérico da linha (não
# seguidos de mais dígitos), evitando capturar um dígito do rótulo do cargo.
_PDF_ROW = re.compile(r'(?<!\d)(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)(?!\s*\d)')
_PDF_TOTAL = re.compile(r'(?<!\d)TOTAL\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)(?!\s*\d)')


def _pdf_table_proposals(blocks: list[dict], contest_id: str, role_id: str | None) -> list[dict]:
    """Lê o quadro de cotas em texto de PDF, ancorado ao cabeçalho e à linha TOTAL.

    A edição diária reúne vários atos: o quadro encontrado pode não ser do
    edital do concurso, então suas linhas ficam ambíguas por escopo (TOTAL) ou
    por rótulo de cargo (linhas por cargo), nunca confirmadas automaticamente.
    """
    proposals = []
    for index, block in enumerate(blocks):
        if block.get('page_number') is None:
            continue
        text = block['text']
        marker = text.find('QUADRO GERAL DE VAGAS')
        if marker < 0:
            continue
        header_end = re.search(r'AMPLA\s+CONCORR\S*', text[marker:])
        if header_end is None:
            continue
        header_segment = text[marker:marker + header_end.end()]
        if not all(tok in header_segment for tok in _PDF_HEADER_TOKENS):
            continue
        region_start = marker + header_end.end()
        total = _PDF_TOTAL.search(text, region_start)
        if total is None:
            continue
        region = text[region_start:total.start()]
        total_evidence = dict(block_index=index, quote=total.group(0),
                              start_offset=total.start(), end_offset=total.end())
        for field, column in (('immediate_vacancies', 1), ('indigenous_vacancies', 4)):
            proposals.append(dict(contest_id=contest_id, role_id=None, field_name=field,
                value_json=json.dumps(int(total.group(column))), value_type='integer',
                extraction_method='tabela-pdf', ambiguity_reason=PDF_SCOPE_REASON,
                evidence=dict(total_evidence)))
        previous = 0
        for match in _PDF_ROW.finditer(region):
            label = ' '.join(region[previous:match.start()].split()).strip()
            row_start = previous
            previous = match.end()
            if not label:
                continue
            start = region_start + row_start
            end = region_start + match.end()
            evidence = dict(block_index=index, quote=text[start:end], start_offset=start, end_offset=end)
            ambiguity = LABEL_PREFIX + label
            for field, column in (('immediate_vacancies', 1), ('indigenous_vacancies', 4)):
                proposals.append(dict(contest_id=contest_id, role_id=None, field_name=field,
                    value_json=json.dumps(int(match.group(column))), value_type='integer',
                    extraction_method='tabela-pdf', ambiguity_reason=ambiguity,
                    evidence=dict(evidence)))
    return proposals


def invalid_registration_period(blocks: list[dict]) -> bool:
    """Identifica calendário/período reconhecido, mas impossível, para diagnóstico."""
    for block in blocks:
        for match in _REGISTRATION.finditer(block['text']):
            try:
                start = date(int(match.group(4)), int(match.group(3)), int(match.group(1)))
                end = date(int(match.group(4)), int(match.group(3)), int(match.group(2)))
                if start > end:
                    return True
            except ValueError:
                return True
        for match in _TEXT_PERIOD.finditer(block['text']):
            try:
                start = date(int(match.group(3)), int(_MONTHS[match.group(2).lower()]), int(match.group(1)))
                end = date(int(match.group(6)), int(_MONTHS[match.group(5).lower()]), int(match.group(4)))
                if start > end:
                    return True
            except ValueError:
                return True
        for match in _NUMERIC_RANGE.finditer(block['text']):
            try:
                start = date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
                end = date(int(match.group(6)), int(match.group(5)), int(match.group(4)))
                if start > end:
                    return True
            except ValueError:
                return True
    return False


def extract_field_proposals(blocks: list[dict], version_id: str, contest_id: str,
                            role_id: str | None = None) -> list[dict]:
    proposals = []
    for index, block in enumerate(blocks):
        text = block['text']
        scope = PDF_SCOPE_REASON if block.get('page_number') is not None else None
        for field, value, quote, start, end in _registration_dates(text):
            proposals.append(dict(contest_id=contest_id, role_id=role_id,
                field_name=field, value_json=json.dumps(value),
                value_type='string', extraction_method='regex', ambiguity_reason=scope,
                evidence=dict(block_index=index, quote=quote, start_offset=start, end_offset=end)))
        for field, pattern in _PATTERNS:
            for match in pattern.finditer(text):
                proposals.append(dict(contest_id=contest_id, role_id=role_id,
                    field_name=field, value_json=json.dumps(int(match.group(1))),
                    value_type='integer', extraction_method='regex', ambiguity_reason=scope,
                evidence=dict(block_index=index, quote=match.group(),
                              start_offset=match.start(), end_offset=match.end())))
    # O quadro de cotas é multi-cargo (escopo do concurso); não se aplica a um
    # documento já restrito a um cargo.
    if role_id is None:
        proposals.extend(_table_proposals(blocks, contest_id, role_id))
        proposals.extend(_pdf_table_proposals(blocks, contest_id, role_id))
    return proposals
