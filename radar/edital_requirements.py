"""Extração estruturada de requisitos de formação e de prazos de isenção (editais).

Duas capacidades, ambas conservadoras e pendentes de revisão humana:

- **Formação:** lê o texto de requisitos por cargo (ex.: Anexo II "a) Requisitos: ...")
  e propõe ``education`` (texto literal), ``accepted_courses`` (cursos/categoria) e
  ``si_compatibility`` (compatibilidade com o bacharelado em Sistemas de Informação).
- **Isenção da taxa:** lê o cronograma e separa início/fim da solicitação de isenção,
  resultado preliminar, prazo de recurso e resultado definitivo — **distintos** do prazo
  de inscrição e do pagamento da taxa.

Nada é promovido automaticamente; datas e cursos ficam como propostas com evidência.
"""

from __future__ import annotations

import json
import re
import unicodedata

# --- Normalização -----------------------------------------------------------

def _norm(text) -> str:
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^A-Za-z0-9 ]", " ", ascii_text.lower()).split())


# --- Compatibilidade com Sistemas de Informação -----------------------------

SI_STATES = ("aceito_expressamente", "abrangido_por_categoria",
             "incompativel_com_requisito_explicito", "ambiguo",
             "nao_extraido", "nao_informado")

_SI_LITERAL = re.compile(r"sistemas de informa", re.I)
# Categorias amplas que abrangem computação/TI (com marcador de abertura).
_BROAD_CATEGORY = ("tecnologia da informacao", "area de computacao", "ciencias da computacao",
                   "ciencia da computacao", "area de informatica", "computacao")
_OPEN_MARKERS = ("correlat", "tais como", "ou outros", "ou outras", "area de", "equivalentes",
                 "ou curso de", "dentre outros")
# Áreas claramente alheias à computação (para rejeição explícita).
_NON_COMPUTING = ("direito", "contabilidade", "ciencias contabeis", "enfermagem", "medicina",
                  "psicologia", "pedagogia", "servico social", "nutricao", "arquitetura",
                  "engenharia civil", "engenharia mecanica", "engenharia quimica", "biologia",
                  "quimica", "farmacia", "odontologia", "fisioterapia", "educacao fisica",
                  "letras", "historia", "geografia", "matematica", "fisica", "administracao",
                  "economia", "sociologia", "comunicacao social", "biblioteconomia")


def classify_si_compatibility(requirement_text) -> tuple[str, str]:
    """Classifica a compatibilidade do cargo com Sistemas de Informação (estado, motivo)."""
    if not isinstance(requirement_text, str) or not requirement_text.strip():
        return "nao_informado", "sem texto de requisitos"
    norm = _norm(requirement_text)
    if _SI_LITERAL.search(norm):
        return "aceito_expressamente", "o edital cita 'Sistemas de Informação' nos requisitos"
    broad = [tok for tok in _BROAD_CATEGORY if tok in norm]
    if broad:
        if any(marker in norm for marker in _OPEN_MARKERS):
            return "abrangido_por_categoria", (
                "categoria ampla de computação/TI com abertura a cursos correlatos")
        return "ambiguo", "cita área de computação/TI sem abertura explícita a correlatos"
    if any(tok in norm for tok in _NON_COMPUTING):
        return "incompativel_com_requisito_explicito", "requisito de área alheia à computação"
    return "ambiguo", "requisitos presentes, mas a compatibilidade não é determinável"


# --- Requisitos de formação --------------------------------------------------

# Cabeçalho de cargo no Anexo II: "1.1 NOME DO CARGO (CÓDIGO 404)" ou
# "(CÓDIGOS 200 ATÉ 206)"; o nome pode conter parênteses próprios (ex.: "(PST)") e é
# iniciado por letra maiúscula (evita capturar números de seção do texto corrido).
_CARGO_HEAD = re.compile(
    r"(\d+\.\d+(?:\.\d+)?)\s+([A-ZÁÂÃÀÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ0-9 .\-()/]{2,88}?)"
    r"\s*\(\s*(C[ÓO]DIGOS?[^)]{0,80}?)\s*\)", re.I)
_REQ_START = re.compile(r"a\)\s*Requisitos\s*:?", re.I)
_REQ_END = re.compile(r"b\)\s*Descri", re.I)
_TAIS_COMO = re.compile(r"(?:tais como|dentre (?:eles|os quais)|a seguir)\s*[:\-]?\s*", re.I)
_CURSO_EM = re.compile(r"\b(?:cursos?|gradua[çc][ãa]o|bacharelado|tecn[óo]logo)\b[^.]{0,40}?\bem\s+", re.I)
_COURSE_SPLIT = re.compile(r"\s*(?:,|;| ou | e )\s*", re.I)

# Faixa de códigos: "200 ATÉ 206", "400 A 403", "400-403", "400–403".
_CODE_RANGE = re.compile(r"(?<!\d)(\d{2,5})\s*(?:AT[ÉE]|A|-|–|—)\s*(\d{2,5})(?!\d)", re.I)
# Qualquer código avulso no bloco (lista: "400, 401 E 402").
_CODE_ANY = re.compile(r"(?<!\d)(\d{2,5})(?!\d)")
_MAX_RANGE_SPAN = 60  # uma faixa de cargos plausível; acima disso, não é código de cargo


def parse_code_group(clause: str) -> list[str]:
    """Interpreta um bloco de códigos expressamente indicado ("CÓDIGO 404",
    "CÓDIGOS 200 ATÉ 206", "CÓDIGOS 400, 401 E 402").

    Conservador: só reconhece faixa quando há marcador explícito entre dois números e a
    amplitude é plausível; caso contrário, trata como lista de códigos avulsos. Devolve a
    lista **normalizada** (zeros à esquerda preservados); nunca inventa códigos.
    """
    if not isinstance(clause, str):
        return []
    body = re.sub(r"^\s*C[ÓO]DIGOS?\b", "", clause, flags=re.I).strip()
    if not body or body == clause.strip():
        return []  # não começa por CÓDIGO(S): não é bloco de códigos
    codes: list[str] = []
    covered: list[tuple[int, int]] = []
    # Todas as faixas (inclusive implausíveis, que ficam "cobertas" e não viram avulsos).
    for rng in _CODE_RANGE.finditer(body):
        covered.append((rng.start(), rng.end()))
        lo, hi = int(rng.group(1)), int(rng.group(2))
        if lo <= hi and hi - lo <= _MAX_RANGE_SPAN:
            width = max(len(rng.group(1)), len(rng.group(2)))
            codes.extend(str(n).zfill(width) for n in range(lo, hi + 1))
    # Códigos avulsos que não fazem parte de nenhuma faixa (blocos mistos).
    for match in _CODE_ANY.finditer(body):
        if not any(s <= match.start() < e for s, e in covered):
            codes.append(match.group(1))
    # Dedup preservando a ordem.
    seen: set[str] = set()
    return [c for c in codes if not (c in seen or seen.add(c))]



def _courses_from(text: str) -> str | None:
    """Extrai a lista de cursos/categoria citada nos requisitos (texto literal).

    Só emite com marcador explícito ("tais como", "curso ... em") para não capturar
    frases genéricas como "curso de nível médio".
    """
    marker = _TAIS_COMO.search(text)
    if marker:
        segment = text[marker.end():]
    else:
        curso = _CURSO_EM.search(text)
        if curso is None:
            return None
        segment = text[curso.end():]
    segment = re.split(r"reconhecid|fornecid|expedid|pelo MEC|Minist[ée]rio|registrad",
                       segment, maxsplit=1, flags=re.I)[0]
    parts = [p.strip(" .;,") for p in _COURSE_SPLIT.split(segment) if p.strip(" .;,")]
    parts = [p for p in parts if 2 <= len(p) <= 60]
    if not parts:
        return None
    return "; ".join(parts[:12])


def extract_education(blocks: list[dict], contest_id: str, *, label_prefix: str,
                      method: str = "requisitos-formacao") -> list[dict]:
    """Propõe ``education``, ``accepted_courses`` e ``si_compatibility`` por cargo do Anexo II.

    Um bloco de requisitos pode valer para um código individual ou para um **conjunto**
    ("CÓDIGOS 200 ATÉ 206"): nesse caso, gera-se uma proposta por código do conjunto,
    todas com a **mesma evidência** (o trecho literal inclui o bloco de códigos), e a
    associação ao cargo é feita depois por código. Nada é confirmado automaticamente.
    """
    proposals = []
    for index, block in enumerate(blocks):
        if block.get("page_number") is None:
            continue
        text = block["text"]
        if not _REQ_START.search(text):
            continue
        for head in _CARGO_HEAD.finditer(text):
            name = " ".join(head.group(2).split())
            codes = parse_code_group(head.group(3))
            if not codes:
                continue
            req = _REQ_START.search(text, head.end())
            if req is None:
                continue
            # No Anexo II, "a) Requisitos" segue imediatamente o cabeçalho. Cabeçalhos do
            # conteúdo programático ("... (CÓDIGO NNN): 1 Fundamentos...") não têm esse
            # marcador perto — exigir proximidade evita associar o requisito de outro cargo.
            if req.start() - head.end() > 60:
                continue
            # A seção termina em "b) Descrição" (ou no próximo cabeçalho de cargo).
            nxt_head = _CARGO_HEAD.search(text, head.end())
            end_bound = nxt_head.start() if nxt_head else len(text)
            desc = _REQ_END.search(text, req.end())
            end = min(desc.start(), end_bound) if desc else end_bound
            quote_body = text[req.end():end].strip()
            if not quote_body:
                continue
            # Evidência inclui o bloco de códigos (forma literal de origem) + os requisitos.
            q_start = head.start(3)
            q_end = req.end() + len(text[req.end():end].rstrip())
            quote = text[q_start:q_end]
            group = len(codes) > 1
            block_literal = head.group(3).strip()
            for code in codes:
                if group:
                    label = code
                    ambiguity = f"{label_prefix}{code} — bloco {block_literal}"
                else:
                    label = f"{code} {name}"
                    ambiguity = label_prefix + label
                evidence = dict(block_index=index, quote=quote,
                                start_offset=q_start, end_offset=q_end,
                                page_number=block.get("page_number"), header="Requisitos",
                                section=None, role_label=label)
                proposals.append(dict(contest_id=contest_id, role_id=None, field_name="education",
                    value_json=json.dumps(quote_body[:600]), value_type="string",
                    extraction_method=method, ambiguity_reason=ambiguity, evidence=dict(evidence)))
                courses = _courses_from(quote_body)
                if courses:
                    proposals.append(dict(contest_id=contest_id, role_id=None, field_name="accepted_courses",
                        value_json=json.dumps(courses), value_type="string",
                        extraction_method=method, ambiguity_reason=ambiguity, evidence=dict(evidence)))
                state, reason = classify_si_compatibility(quote_body)
                proposals.append(dict(contest_id=contest_id, role_id=None, field_name="si_compatibility",
                    value_json=json.dumps(state), value_type="string",
                    extraction_method="classificacao-si", ambiguity_reason=f"{label_prefix}{label} — {reason}",
                    evidence=dict(evidence)))
    return proposals


# --- Requisitos declarados em rótulo (complemento genérico, multibanca) ---------
# Formas explícitas e comuns de declarar a escolaridade exigida fora do Anexo II
# (ex.: FGV, cujo edital traz "Requisitos de escolaridade ... Nível Superior – Direito").
_DECLARED_LABEL = re.compile(
    r"(?:requisitos?\s+de\s+escolaridade|escolaridade\s+(?:m[íi]nima|exigida|necess[áa]ria)|"
    r"requisitos?\s+de\s+forma[çc][ãa]o)\s*:?\s*", re.I)
_LEVEL = re.compile(
    r"\b(?:n[íi]vel|ensino)\s+(?:superior|m[ée]dio|t[ée]cnico|fundamental)\b"
    r"|\b(?:superior|m[ée]dio|t[ée]cnico|fundamental)\s+(?:completo|incompleto|em)\b"
    r"|\b(?:superior|m[ée]dio|t[ée]cnico|fundamental)\s*[-–—]\s*[A-Za-zÀ-ÿ]",
    re.I)
_DECLARED_STOP = re.compile(
    r"(?:R\$|valor\s+da\s+taxa|taxa\s+de\s+inscri|quadro\s+de\s+vagas|[.;\n])", re.I)


def extract_declared_education(blocks: list[dict], contest_id: str, *,
                               label_prefix: str, method: str = "escolaridade-rotulada") -> list[dict]:
    """Requisitos de escolaridade declarados por rótulo (genérico, sem código de cargo).

    Cobre formatos que não usam o Anexo II por cargo (ex.: FGV, requisito na tabela de
    vagas). É conservador: exige rótulo explícito e palavra de nível de ensino; a
    proposta fica no escopo do concurso (``role_id=None``), sem associação a cargo.
    """
    proposals = []
    for index, block in enumerate(blocks):
        if block.get("page_number") is None:
            continue
        text = block["text"]
        for label in _DECLARED_LABEL.finditer(text):
            window = text[label.end():label.end() + 200]
            # Não atravessar outro rótulo/quadro.
            hard = re.search(r"(?:quadro\s+de\s+vagas|requisitos?\s+de\s+escolaridade)", window[1:], re.I)
            if hard:
                window = window[:hard.start() + 1]
            level = _LEVEL.search(window)
            if level is None:
                continue
            segment = window[level.start():]
            stop = _DECLARED_STOP.search(segment)
            raw_value = (segment[:stop.start()] if stop else segment)
            value = raw_value.strip(" -–—;,")
            value = re.sub(r"\s+", " ", value)
            if len(value) < 3:
                continue
            v_start = label.end() + level.start()
            v_end = v_start + len(raw_value.rstrip())
            quote = text[v_start:v_end]
            evidence = dict(block_index=index, quote=quote, start_offset=v_start, end_offset=v_end,
                            page_number=block.get("page_number"), header="Requisitos de escolaridade",
                            section=None, role_label=None)
            label_txt = f"escolaridade declarada ({value[:40]})"
            ambiguity = label_prefix + label_txt
            proposals.append(dict(contest_id=contest_id, role_id=None, field_name="education",
                value_json=json.dumps(value[:600]), value_type="string",
                extraction_method=method, ambiguity_reason=ambiguity, evidence=dict(evidence)))
            courses = _courses_from(value)
            if courses:
                proposals.append(dict(contest_id=contest_id, role_id=None, field_name="accepted_courses",
                    value_json=json.dumps(courses), value_type="string",
                    extraction_method=method, ambiguity_reason=ambiguity, evidence=dict(evidence)))
            state, reason = classify_si_compatibility(value)
            proposals.append(dict(contest_id=contest_id, role_id=None, field_name="si_compatibility",
                value_json=json.dumps(state), value_type="string",
                extraction_method="classificacao-si", ambiguity_reason=f"{ambiguity} — {reason}",
                evidence=dict(evidence)))
    return proposals


# --- Prazos de isenção -------------------------------------------------------

_MONTH = {"01": 31, "02": 29, "03": 31, "04": 30, "05": 31, "06": 30,
          "07": 31, "08": 31, "09": 30, "10": 31, "11": 30, "12": 31}

# Atividades do cronograma ligadas à isenção (ordem de prioridade importa).
_ISENCAO_ACTIVITIES = (
    ("exemption_result_preliminary", re.compile(r"resultado preliminar[^.]{0,80}?isen", re.I)),
    ("exemption_appeal", re.compile(r"recurso[^.]{0,80}?isen", re.I)),
    ("exemption_result_final", re.compile(r"resultado definitivo[^.]{0,80}?isen", re.I)),
    ("exemption_start", re.compile(r"(?:per[íi]odo|prazo)?[^.]{0,60}?solicita[çc][ãa]o de isen", re.I)),
)

_DATE_SINGLE = re.compile(r"(\d{1,2})/(\d{2})/(\d{4})")
_DATE_PAIR = re.compile(r"(\d{1,2})\s*e\s*(\d{1,2})/(\d{2})/(\d{4})")
# Mesmo mês com "a": "18 a 19/03/2026".
_DATE_PAIR_A = re.compile(r"(\d{1,2})\s*a\s*(\d{1,2})/(\d{2})/(\d{4})")
_DATE_RANGE = re.compile(r"(\d{1,2})/(\d{2})\s*a\s*(\d{1,2})/(\d{2})/(\d{4})")


def _iso(day: int, month: int, year: int):
    if not (1 <= month <= 12 and 1 <= day <= _MONTH[f"{month:02d}"]):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def _dates_after(text: str, pos: int, max_gap: int = 160):
    """Primeira data (ou par) em até ``max_gap`` chars após ``pos``.

    Exigir proximidade evita casar o texto corrido do edital (que cita "isenção" sem
    data) em vez da linha do cronograma (atividade seguida da data).
    """
    window = text[pos:pos + max_gap]
    # Não atravessar fim de frase: evita capturar a data da inscrição/pagamento que
    # aparece logo depois da menção à isenção no texto corrido.
    window = re.split(r"[.\n]", window, maxsplit=1)[0]
    pair = _DATE_PAIR.search(window)
    pair_a = _DATE_PAIR_A.search(window)
    rng = _DATE_RANGE.search(window)
    single = _DATE_SINGLE.search(window)
    candidates = []
    if pair:
        candidates.append((pair.start(), "pair", pair))
    if pair_a:
        candidates.append((pair_a.start(), "pair", pair_a))
    if rng:
        candidates.append((rng.start(), "range", rng))
    if single:
        candidates.append((single.start(), "single", single))
    if not candidates:
        return None, None, None, None
    _, kind, match = min(candidates, key=lambda c: c[0])
    if kind == "pair":
        d1, d2, mm, yy = (int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4)))
        start, end = _iso(d1, mm, yy), _iso(d2, mm, yy)
        if start and end:
            return start, end, match.group(0), match.start()
    elif kind == "range":
        d1, m1, d2, m2, yy = (int(match.group(1)), int(match.group(2)), int(match.group(3)),
                              int(match.group(4)), int(match.group(5)))
        start, end = _iso(d1, m1, yy), _iso(d2, m2, yy)
        if start and end:
            return start, end, match.group(0), match.start()
    else:
        d, mm, yy = int(match.group(1)), int(match.group(2)), int(match.group(3))
        start = _iso(d, mm, yy)
        if start:
            return start, None, match.group(0), match.start()
    return None, None, None, None


def extract_exemption_dates(blocks: list[dict], contest_id: str, *, method: str = "cronograma"):
    """Propõe as datas de isenção a partir do cronograma (nunca do prazo de inscrição).

    Para cada atividade, usa a **primeira ocorrência cuja data esteja próxima** (linha do
    cronograma), ignorando o texto corrido que apenas menciona a isenção.
    """
    proposals = []
    for index, block in enumerate(blocks):
        if block.get("page_number") is None:
            continue
        text = block["text"]
        if "isen" not in text.lower():
            continue
        for field, pattern in _ISENCAO_ACTIVITIES:
            for match in pattern.finditer(text):
                start, end, quote, offset = _dates_after(text, match.end())
                if start is None:
                    continue
                quote_off = match.end() + offset
                evidence = dict(block_index=index, quote=quote, start_offset=quote_off,
                                end_offset=quote_off + len(quote), page_number=block.get("page_number"),
                                header="cronograma de isenção", section=None, role_label=None)
                proposals.append(dict(contest_id=contest_id, role_id=None, field_name=field,
                    value_json=json.dumps(start), value_type="string", extraction_method=method,
                    ambiguity_reason="data do cronograma de isenção; conferir com o edital",
                    evidence=dict(evidence)))
                if end and field == "exemption_start":
                    proposals.append(dict(contest_id=contest_id, role_id=None, field_name="exemption_end",
                        value_json=json.dumps(end), value_type="string", extraction_method=method,
                        ambiguity_reason="data do cronograma de isenção; conferir com o edital",
                        evidence=dict(evidence)))
                break  # primeira ocorrência com data próxima (linha do cronograma)
    return proposals
