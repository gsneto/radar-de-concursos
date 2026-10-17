"""Extração do **conteúdo programático** dos editais (Fase 22).

Reutiliza a infraestrutura documental existente: as seções de programa são detectadas no texto
dos blocos (páginas), e cada item vira uma **proposta** com evidência (trecho + página) no mesmo
fluxo de `record_analysis`, revisão humana (`revisoes_campo`) e detecção de conflito já usados
pelos demais campos. Nada é confirmado automaticamente: todo item nasce como **candidato**
(`ambiguity_reason` explícito) e precisa de revisão.

Níveis hierárquicos (campos de proposta):

- ``conteudo_secao`` — título da seção (ex.: "CONHECIMENTOS ESPECÍFICOS").
- ``conteudo_disciplina`` — disciplina/matéria.
- ``conteudo_topico`` — tópico sob uma disciplina.
- ``conteudo_subtopico`` — subitem mais profundo (numeração ``N.M``).

Conservador por princípio: só extrai **dentro** de seções de conteúdo reconhecidas; uma linha
ambígua é ignorada (não se inventa tópico); não transforma cada linha em disciplina.
"""

from __future__ import annotations

import json
import re
import unicodedata

# Títulos que iniciam uma seção de conteúdo programático (variação entre bancas).
# Comparados sobre o texto **normalizado** (minúsculas, sem acento). Aceita sufixos comuns
# ("DAS PROVAS", "POR CARGO", "BÁSICOS E ESPECÍFICOS") para não perder seções reais.
_CONTENT_HEADING = re.compile(
    r"^(?:anexo\s+[ivxlcdm0-9]+\s*[-: ]?\s*)?"
    r"(?:conteudos?\s+programaticos?"
    r"(?:\s+(?:das?\s+provas?(?:\s+objetivas?)?|por\s+cargo|do\s+cargo))?"
    r"|programa\s+(?:das?\s+provas?|de\s+provas?|de\s+disciplinas)"
    r"|conhecimentos\s+(?:basicos|gerais|especificos|complementares)"
    r"(?:\s+e\s+(?:basicos|gerais|especificos|complementares))*"
    r"(?:\s+das?\s+provas?)?"
    r"|conteudo\s+das?\s+provas?)"
    r"\s*:?\s*$")
# Títulos que **encerram** a seção de conteúdo (começam outra parte do edital). Palavras
# ambíguas (que também nomeiam disciplinas, como "RECURSOS") exigem preposição/artigo.
_STOP_HEADING = re.compile(
    r"^(?:anexo\s+[ivxlcdm0-9]+|cronograma|gabarito|bibliografia|referencias|disposicoes|"
    r"atribuicoes|remuneracao|jornada|requisitos|das?\s+inscricoes|das?\s+vagas|dos?\s+cargos|"
    r"dos?\s+requisitos|das?\s+provas|prova\s+objetiva|dos?\s+recursos|dos?\s+resultados?|"
    r"da\s+avaliacao|dos?\s+criterios|das?\s+etapas)\b")

# Numeração de item: "1.1.2 ...", "1.1 ...", "1) ...", "1. ...", "a) ...", "- ...", "• ...".
_SUBTOPIC = re.compile(r"^\(?\d+\.\d+(?:\.\d+)?\)?\s*(.+)$")
_TOPIC_NUM = re.compile(r"^\(?\d+[\.\)]\s+(.+)$")
_TOPIC_LETTER = re.compile(r"^[a-z][\.\)]\s+(.+)$", re.I)
_TOPIC_BULLET = re.compile(r"^[-–•*·]\s+(.+)$")
# Número (ponto/parêntese/espaço opcional) + texto: usado para distinguir disciplina de tópico.
_NUM_ANY = re.compile(r"^\(?\d+[\.\)]?\s+(.+)$")
_TOPIC_NUM_SPACE = re.compile(r"^\d+\s+(.+)$")
# "DISCIPLINA: itens" (disciplina seguida de dois-pontos na mesma linha).
_DISCIPLINA_COLON = re.compile(r"^([A-ZÀ-Þ][A-Za-zÀ-ÿ0-9 ./()\-]{1,70}?)\s*:\s*(.+)$")
# Título de disciplina: linha curta, sem ponto final, majoritariamente maiúscula.
_TITLE_LINE = re.compile(r"^[A-ZÀ-Þ0-9][A-Za-zÀ-ÿ0-9 .,/()\-–—]{1,80}$")
# Rótulos que não são disciplinas (evita "CARGO", "TOTAL" virarem matéria).
_NON_DISCIPLINA = {"total", "cargo", "cargos", "observacao", "observacoes", "legenda", "nota",
                   "fonte", "quadro", "tabela", "item", "itens", "pagina", "anexo", "sumario",
                   "indice", "geral", "gerais"}

_MAX_SECTION_LINES = 400  # limite de segurança para não engolir o documento inteiro


def _norm(text) -> str:
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^A-Za-z0-9 ]", " ", ascii_text.lower()).split())


def _clean(value: str) -> str:
    return " ".join((value or "").split()).strip(" .;,")


def _is_uppercase_title(value: str) -> bool:
    letters = [ch for ch in value if ch.isalpha()]
    if len(letters) < 3:
        return False
    upper = sum(1 for ch in letters if ch.isupper())
    return upper / len(letters) >= 0.7


def is_content_heading(line: str) -> bool:
    """A linha inicia uma seção de conteúdo programático?"""
    return bool(_CONTENT_HEADING.match(_norm(_clean(line))))


def is_stop_heading(line: str) -> bool:
    """A linha encerra a seção de conteúdo (inicia outra parte do edital)?"""
    return bool(_STOP_HEADING.match(_norm(_clean(line))))


def classify_line(line: str):
    """Classifica uma linha de conteúdo em ``(field_name, value)`` ou ``None``.

    Precisão acima de cobertura: linhas explicativas (texto corrido) são ignoradas.
    """
    stripped = (line or "").strip()
    if len(stripped) < 3:
        return None
    match = _SUBTOPIC.match(stripped)
    if match and _clean(match.group(1)):
        return "conteudo_subtopico", _clean(match.group(1))
    # "1. LÍNGUA PORTUGUESA" / "2 MATEMÁTICA" (título em maiúsculas) = disciplina, antes de
    # ser confundido com tópico pela numeração.
    match = _NUM_ANY.match(stripped)
    if match and _is_uppercase_title(match.group(1)) and _clean(match.group(1)):
        name = _clean(match.group(1))
        if _norm(name) not in _NON_DISCIPLINA:
            return "conteudo_disciplina", name
    for pattern in (_TOPIC_NUM, _TOPIC_NUM_SPACE, _TOPIC_LETTER, _TOPIC_BULLET):
        match = pattern.match(stripped)
        if match and _clean(match.group(1)):
            return "conteudo_topico", _clean(match.group(1))
    match = _DISCIPLINA_COLON.match(stripped)
    if match and _is_uppercase_title(match.group(1)) and _norm(_clean(match.group(1))) not in _NON_DISCIPLINA:
        return "conteudo_disciplina", _clean(match.group(1))
    if (_TITLE_LINE.match(stripped) and _is_uppercase_title(stripped)
            and _norm(_clean(stripped)) not in _NON_DISCIPLINA and not stripped.endswith(".")):
        return "conteudo_disciplina", _clean(stripped)
    return None


def discipline_tail(line: str):
    """Resto de ``"DISCIPLINA: itens"`` como tópico candidato, quando houver."""
    match = _DISCIPLINA_COLON.match((line or "").strip())
    if match and _is_uppercase_title(match.group(1)) and _clean(match.group(2)):
        return _clean(match.group(2))
    return None


def extract_program_content(blocks: list[dict], contest_id: str, *, label_prefix: str,
                            method: str = "conteudo-programatico") -> list[dict]:
    """Extrai itens de conteúdo programático como propostas com evidência.

    Percorre os blocos de **página** em ordem, mantendo a seção corrente: um título reconhecido
    abre a seção; um título de parada a encerra. Dentro da seção, cada linha é classificada em
    disciplina/tópico/subtópico (ou ignorada). A evidência é ancorada ao bloco/página exato da
    linha, então o item permanece rastreável até o edital de origem.
    """
    proposals = []
    section = None
    section_lines = 0
    for index, block in enumerate(blocks):
        if block.get("page_number") is None:
            continue  # só páginas entram no documento lógico de conteúdo
        text = block.get("text") or ""
        offset = 0
        for raw_line in text.split("\n"):
            lead = len(raw_line) - len(raw_line.lstrip())
            line_start = offset + lead
            offset += len(raw_line) + 1
            line = raw_line.strip()
            if not line:
                continue
            if is_content_heading(line):
                section = _clean(re.sub(r"^anexo\s+[ivxlcdm0-9]+\s*[-–—:]?\s*", "", line, flags=re.I))
                section_lines = 0
                proposals.append(_proposal(contest_id, index, block, line, line_start,
                                           "conteudo_secao", section, label_prefix, method))
                continue
            if section is None:
                continue
            if is_stop_heading(line):
                section = None
                continue
            section_lines += 1
            if section_lines > _MAX_SECTION_LINES:
                # Limite de segurança: para de extrair e registra a truncagem (visível na
                # cobertura), sem inventar conteúdo.
                proposals.append(_proposal(contest_id, index, block, line, line_start,
                                           "conteudo_secao", (section or "") + " (seção truncada)",
                                           label_prefix, method, section=section))
                section = None
                continue
            classified = classify_line(line)
            if classified is None:
                continue
            field_name, value = classified
            proposals.append(_proposal(contest_id, index, block, line, line_start,
                                       field_name, value, label_prefix, method, section=section))
            if field_name == "conteudo_disciplina":
                tail = discipline_tail(line)
                if tail:
                    proposals.append(_proposal(contest_id, index, block, line, line_start,
                                               "conteudo_topico", tail, label_prefix, method,
                                               section=section))
    return proposals


def _proposal(contest_id, block_index, block, line, line_start, field_name, value,
              label_prefix, method, section=None):
    """Monta uma proposta de conteúdo com evidência verificável (trecho literal do bloco)."""
    quote = line
    end_offset = line_start + len(quote)
    ambiguity = f"{label_prefix}conteúdo programático candidato ({field_name})"
    if section:
        ambiguity += f" — seção: {section}"
    ambiguity += "; revisar antes de considerar confirmado"
    evidence = dict(block_index=block_index, quote=quote, start_offset=line_start,
                    end_offset=end_offset, page_number=block.get("page_number"),
                    header=section or "Conteúdo programático", section=section, role_label=None)
    return dict(contest_id=contest_id, role_id=None, field_name=field_name,
                value_json=json.dumps(value[:400]), value_type="string",
                extraction_method=method, ambiguity_reason=ambiguity, evidence=evidence)
