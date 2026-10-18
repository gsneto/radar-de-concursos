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


# Marcadores por evento. A ordem não decide: vence o marcador mais próximo do trecho.
# "inscrição" só conta como evento quando não é qualificador de outro ("taxa de inscrição",
# "valor da inscrição", "inscritos"): nesses casos o evento é a isenção/pagamento.
_EVENT_PATTERNS = (
    ("isencao", re.compile(r"isen[çc]|isent", re.I)),
    ("recurso", re.compile(r"recurso", re.I)),
    ("prova", re.compile(r"provas?\b", re.I)),
    ("inscricao", re.compile(r"inscri[çc][ãa]o|inscri[çc][õo]es", re.I)),
)
_INSCRICAO_QUALIFIER = re.compile(
    r"(?:taxa|valor|pagamento|comprovante|guia|boleto|emiss[ãa]o)\s+d[aeo]s?\s+$", re.I)

# Duas camadas de contexto, da mais estreita para a mais ampla:
# 1. janela curta — o sujeito que rege o período está logo antes da primeira data;
# 2. frase — cobre frases longas ("inscrições ... de 27 de fevereiro ... até 10 de abril")
#    sem alcançar a frase vizinha, que é o que trocava o evento.
_EVENT_WINDOW = 160
_SENTENCE_BREAK = re.compile(r"(?<=[.;!?])\s+|\n+")


def event_window(text: str, start: int, limit: int = _EVENT_WINDOW) -> str:
    """Trecho imediatamente anterior ao início da citação."""
    return text[max(0, start - limit):start]


def _sentence_prefix(text: str, start: int) -> str:
    """Frase imediatamente anterior, sem limite artificial de tamanho.

    Um teto fixo cortava o início de frases longas e fazia o marcador desaparecer, o que
    rejeitava período de inscrição legítimo.
    """
    prefix = text[:start]
    cut = 0
    for match in _SENTENCE_BREAK.finditer(prefix):
        cut = match.end()
    return prefix[cut:]


def _nearest_marker(window: str):
    best = None
    for event, pattern in _EVENT_PATTERNS:
        for match in pattern.finditer(window):
            if event == "inscricao" and _INSCRICAO_QUALIFIER.search(window[:match.start()]):
                continue
            if best is None or match.start() > best[1]:
                best = (event, match.start(), match.group(0))
    return (best[0], best[2]) if best else None


def _events_in(window: str) -> set[str]:
    events = set()
    for event, pattern in _EVENT_PATTERNS:
        for match in pattern.finditer(window):
            if event == "inscricao" and _INSCRICAO_QUALIFIER.search(window[:match.start()]):
                continue
            events.add(event)
            break
    return events


def event_marker(text: str, start: int, quote: str | None = None,
                 strict: bool = True) -> tuple[str, str | None]:
    """Evento do trecho.

    Ordem: (1) se a própria citação nomeia um único evento ("Inscrições até ...",
    "... prova discursiva"), esse evento vale; (2) senão, marcador mais próximo na janela
    curta anterior; (3) senão, a frase — e só quando ela tem um único evento.
    Ambíguo não vira atribuição: a resposta é ``outro``.
    """
    if quote:
        inside = _events_in(quote.lower())
        if len(inside) == 1:
            event = inside.pop()
            for candidate, pattern in _EVENT_PATTERNS:
                if candidate != event:
                    continue
                found = pattern.search(quote.lower())
                if found:
                    return event, found.group(0)
    short = event_window(text, start).lower()
    # Ambiguidade só conta no trecho imediatamente antes da data: se dois eventos
    # aparecem na mesma oração ("a isenção e as inscrições ... no período"), o extrator
    # não atribui (`strict`). O diagnóstico pode usar o marcador mais próximo e sinalizar
    # a ambiguidade, sem transformar isso em decisão.
    if strict and len(_events_in(short[-80:])) > 1:
        return "outro", None
    found = _nearest_marker(short)
    if found:
        return found
    prefix = _sentence_prefix(text, start).lower()
    events = _events_in(prefix)
    if len(events) == 1:
        return _nearest_marker(prefix) or ("outro", None)
    return "outro", None


def event_ambiguous(text: str, start: int, quote: str | None = None) -> bool:
    """O trecho imediatamente anterior mistura eventos?"""
    if quote and len(_events_in(quote.lower())) == 1:
        return False
    return len(_events_in(event_window(text, start).lower()[-80:])) > 1


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
        # _TEXT_PERIOD não tem âncora própria: exige que a **frase** fale de inscrição.
        # Período de isenção e data de prova também usam "dia X ... dia Y" e não podem
        # virar prazo de inscrição só porque a página menciona "inscrição" em outra frase.
        event, _marker = event_marker(block_text, match.start())
        if event != "inscricao":
            continue
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
    """Lê o quadro de vagas mais completo do documento, por tabela.

    Agrupa as linhas por tabela e usa o extrator genérico (`vacancy_tables`) apenas
    na tabela com mais modalidades mapeadas — evita somar o mesmo fato declarado em
    duas tabelas. Só se aplica a documento de escopo do concurso (``role_id is None``).
    """
    if role_id is not None:
        return []
    from radar import vacancy_tables
    groups: list[list[dict]] = []
    current_table = None
    group: list[dict] = []
    for index, block in enumerate(blocks):
        if block.get("page_number") is not None:
            continue  # linhas de PDF tratadas em `_pdf_table_proposals`
        table = block.get("table")
        if table is None:
            continue
        if table != current_table:
            if group:
                groups.append(group)
            group = []
            current_table = table
        group.append({"index": index, "text": block["text"], "page_number": None})
    if group:
        groups.append(group)
    best = vacancy_tables.best_table(groups)
    if best is None:
        return []
    return vacancy_tables.extract(best, contest_id, label_prefix=LABEL_PREFIX)


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
        # Quadro com total agregado (ex.: IBFC): publica apenas `vagas_total_publicado`,
        # sem distribuir por modalidade e sem tocar em vagas indígenas.
        from radar import vacancy_aggregate
        proposals.extend(vacancy_aggregate.parse_aggregate_table(
            blocks, contest_id, label_prefix=LABEL_PREFIX))
        # Estratégia específica para o layout de quadro de vagas da banca Quadrix.
        from radar import quadrix_tables
        proposals.extend(quadrix_tables.parse_quadrix_proposals(
            blocks, contest_id, label_prefix=LABEL_PREFIX))
        # Requisitos de formação (Anexo II) e prazos de isenção (cronograma).
        from radar import edital_requirements, section_requirements
        education = edital_requirements.extract_education(
            blocks, contest_id, label_prefix=LABEL_PREFIX)
        # Seções numeradas no corpo (com ou sem código): cobre editais que não usam Anexo II.
        section_edu = section_requirements.extract_section_education(
            blocks, contest_id, label_prefix=LABEL_PREFIX)
        education = education + section_edu
        proposals.extend(education)
        if not education:
            # Sem Anexo II nem seção numerada: tenta requisitos declarados por rótulo (multibanca).
            proposals.extend(edital_requirements.extract_declared_education(
                blocks, contest_id, label_prefix=LABEL_PREFIX))
        # Requisito em texto corrido ("Requisito: ...") com cargo no cabeçalho anterior.
        # Roda sempre: o formato inline coexiste com Anexo II em alguns editais.
        from radar import inline_requirements
        inline = inline_requirements.extract_inline_requirements(
            blocks, contest_id, label_prefix=LABEL_PREFIX)
        # Dedup por evidência (campo + valor + trecho/offsets), não por valor isolado:
        # o mesmo valor em outro cargo/trecho é informação distinta.
        known = {(p["field_name"], p["value_json"], p["evidence"].get("quote"),
                  p["evidence"].get("start_offset"), p["evidence"].get("end_offset"))
                 for p in proposals}
        proposals.extend(p for p in inline
                         if (p["field_name"], p["value_json"], p["evidence"].get("quote"),
                             p["evidence"].get("start_offset"),
                             p["evidence"].get("end_offset")) not in known)
        proposals.extend(edital_requirements.extract_exemption_dates(blocks, contest_id))
        # Conteúdo programático (Fase 22): seções de programa, com evidência por item.
        from radar import program_content
        proposals.extend(program_content.extract_program_content(
            blocks, contest_id, label_prefix=LABEL_PREFIX))
        # Local de prova (Fase 26): nunca inferido de lotação/sede; "a divulgar" é
        # registrado como declaração, não como ausência.
        from radar import exam_location
        proposals.extend(exam_location.extract_exam_location(
            blocks, contest_id, label_prefix=LABEL_PREFIX))
    return proposals
