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

# --- Segmentação de texto "inline" (PDF sem quebras de linha) -------------------
# `document_extract` normaliza o texto do PDF com ``" ".join(...split())``, o que remove
# TODAS as quebras de linha. Sem re-segmentar, uma página inteira vira uma única "linha" e
# nenhum título/item é reconhecido — foi a causa comprovada de ``conteudo_programatico``
# ficar em 0% mesmo em editais que têm o anexo completo.
_HEADING_PHRASE = re.compile(
    r"^(?:anexo\s+[ivxlcdm0-9]+\s*[-–—:]\s*)?"
    r"conte[uú]do\s+program[aá]tic[oa]s?"
    r"(?:\s+(?:das?\s+provas?(?:\s+objetivas?)?|por\s+cargo|do\s+cargo))?",
    re.I)
_BLOCO_PHRASE = re.compile(r"^bloco\s+[ivxlcdm0-9]+\b", re.I)
# Início de item numerado: "1. Texto", "12. Texto". O contexto anterior é validado para não
# cortar "art. 5. O candidato" nem "nº 3. Anexo".
_ITEM_BOUNDARY = re.compile(r"(?<!\d)(?=\d{1,3}\.\s+[A-ZÀ-ÞÁÉÍÓÚÂÊÔÃÕÇ])")
_NOT_ITEM_BEFORE = ("art", "art.", "nº", "n°", "no", "item", "inciso", "parágrafo",
                    "paragrafo", "lei", "decreto", "portaria", "resolução", "resolucao")


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


def _previous_word(text: str, position: int) -> str:
    """Última palavra antes de ``position`` (para validar fronteira de item numerado)."""
    window = text[max(0, position - 14):position].strip().lower()
    return window.rsplit(" ", 1)[-1] if window else ""


def _split_inline(text: str) -> list[str]:
    """Re-segmenta um parágrafo longo em linhas lógicas, sem inventar conteúdo.

    Corta antes de títulos de conteúdo, de "BLOCO N" e de itens numerados cujo número não
    seja continuação de "art. 5" / "nº 3" etc. Cada pedaço é o texto original, apenas
    separado — nenhum caractere é criado, então a evidência continua literal.
    """
    pieces: list[str] = []
    for chunk in re.split(r"(?=\b(?:anexo\s+[ivxlcdm0-9]+\s*[-–—:]\s*)?conte[uú]do\s+program)",
                          text, flags=re.I):
        if not chunk.strip():
            continue
        for part in re.split(r"(?=\b(?:bloco\s+[ivxlcdm0-9]+|cargo\s*:))", chunk, flags=re.I):
            if not part.strip():
                continue
            start = 0
            for match in _ITEM_BOUNDARY.finditer(part):
                before = _previous_word(part, match.start())
                if before in _NOT_ITEM_BEFORE or before.isdigit():
                    continue
                if match.start() > start:
                    pieces.append(part[start:match.start()])
                start = match.start()
            pieces.append(part[start:])
    # Recompõe "ANEXO I –" + "CONTEÚDO PROGRAMÁTICO": o corte duplo separaria o rótulo do
    # anexo do título de conteúdo, e nenhum dos dois seria reconhecido isoladamente.
    merged: list[str] = []
    for piece in pieces:
        text_piece = piece.strip()
        if not text_piece:
            continue
        if merged and re.search(r"[-–—:]\s*$", merged[-1]) and re.match(
                r"(?i)^conte[uú]do\s+program", text_piece):
            merged[-1] = merged[-1] + " " + text_piece
            continue
        merged.append(text_piece)
    return merged


def logical_lines(text: str) -> list[tuple[int, str]]:
    """Linhas lógicas de um bloco, com o offset de cada uma no texto original.

    Blocos HTML já vêm com quebras de linha reais e são usados como estão. Blocos de PDF
    vêm como um único parágrafo: aí a segmentação inline reconstrói os limites.
    """
    if not isinstance(text, str) or not text:
        return []
    if "\n" in text:
        out, offset = [], 0
        for raw in text.split("\n"):
            lead = len(raw) - len(raw.lstrip())
            out.append((offset + lead, raw.strip()))
            offset += len(raw) + 1
        return out
    # Os offsets vêm da varredura do texto original, não de ``find`` sobre pedaços já
    # unidos (que poderia não existir literalmente e deslocaria a evidência).
    out, cursor = [], 0
    for piece in _split_inline(text):
        index = text.find(piece, cursor)
        if index < 0:
            # Peça recomposta (título unido): ancora no cursor atual e segue — nunca
            # inventa offset que não corresponda ao texto.
            index = cursor
        out.append((index, piece))
        cursor = max(index + len(piece), cursor + 1)
    return out


def _heading_and_remainder(line: str) -> tuple[str, str] | None:
    """Separa "TÍTULO DE CONTEÚDO <resto>" quando o título abre e o resto continua na linha."""
    match = _HEADING_PHRASE.match(line)
    if not match:
        return None
    heading = line[:match.end()].strip()
    remainder = line[match.end():].strip()
    return heading, remainder


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
        for line_start, line in logical_lines(text):
            if not line:
                continue
            split = _heading_and_remainder(line)
            if split and split[1]:
                # Título com o conteúdo na mesma linha: abre a seção e processa o resto.
                heading, remainder = split
                section = _clean(re.sub(r"^anexo\s+[ivxlcdm0-9]+\s*[-–—:]?\s*", "",
                                        heading, flags=re.I))
                section_lines = 0
                proposals.append(_proposal(contest_id, index, block, heading, line_start,
                                           "conteudo_secao", section, label_prefix, method))
                # O offset do resto é o início original + título + separador. Não se usa
                # ``min(...)`` com o comprimento do resto: isso deslocava a citação e
                # fazia ``record_analysis`` recusar o documento inteiro.
                remainder_start = line_start + len(heading) + 1
                line = remainder
                line_start = remainder_start
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
            bloco = _BLOCO_PHRASE.match(line)
            if bloco:
                # "BLOCO I DIREITO CIVIL" — o bloco é agrupamento, não matéria; o nome da
                # disciplina vem depois. O resto precisa parecer título de disciplina:
                # prosa, fórmula ou item numerado não viram matéria.
                rest = _clean(line[bloco.end():])
                if (rest and _is_uppercase_title(rest) and len(rest) <= 80
                        and not rest.endswith(".")
                        and _norm(rest) not in _NON_DISCIPLINA):
                    classified = ("conteudo_disciplina", rest)
                else:
                    classified = None
            else:
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
