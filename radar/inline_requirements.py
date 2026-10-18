"""Requisitos declarados **em texto corrido** (ex.: ``Requisito:`` do IBFC).

Formato real observado (verificado em 2026-10-17, concurso `ibfc-490`):

```
2.6.2. PROFESSOR ORIENTADOR DE ESTÁGIO EM SAÚDE PARA ATUAÇÃO NO CURSO DE RADIOLOGIA
Requisito: Diploma devidamente registrado de conclusão do curso de nível superior ...
```

O extrator de seções numeradas (`section_requirements`) exige um subitem ``N.M.k Requisitos:``
— este formato não tem. O extrator de rótulos (`edital_requirements`) exige "requisitos de
escolaridade"; ``Requisito:`` sozinho também não casa.

Este módulo cobre o padrão inline, com duas garantias:

1. o cargo vem do **cabeçalho imediatamente anterior** no mesmo bloco (sem associação por
   proximidade entre blocos diferentes);
2. a compatibilidade com Sistemas de Informação é **candidata** e sempre acompanha o trecho
   literal — nunca é conclusão jurídica nem aprovação.
"""

from __future__ import annotations

import json
import re

from radar.edital_requirements import classify_si_compatibility

METHOD = "requisito-inline"

# Rótulo isolado de requisito (não "requisitos de escolaridade", já coberto em outro lugar).
_LABEL = re.compile(
    r"(?<![A-Za-zÀ-ÿ])(?:requisitos?|escolaridade|forma[çc][ãa]o(?:\s+m[íi]nima)?|"
    r"habilita[çc][ãa]o)\s*:\s*", re.I)

# Cabeçalho de cargo: frase em maiúsculas (mín. 3 palavras) imediatamente antes do rótulo.
_CARGO_HEADER = re.compile(
    r"((?:[A-ZÀ-Þ0-9][A-ZÀ-Þ0-9À-ÿ'\.\-–/() ]{6,160}?))\s*$")

# Fim do valor: próximo item numerado, próximo rótulo ou pontuação forte.
_STOP = re.compile(
    r"(?:\s\d+\.\d+(?:\.\d+)?\.?\s|[.;]\s|"
    r"(?:\bRequisitos?\b|\bEscolaridade\b|\bForma[çc][ãa]o\b|\bAtribui[çc][õo]es\b)\s*:)",
    re.I)

# Curso citado no requisito: "curso de Nível Superior de Administração",
# "curso superior em Engenharia Civil", "graduação em ...". Corta antes de
# "em instituição", "fornecido/expedido por", "reconhecida pelo MEC".
_COURSE = re.compile(
    r"(?:curso\s+(?:de\s+)?(?:n[íi]vel\s+)?superior\s+(?:de|em)\s+|"
    r"curso\s+superior\s+(?:de|em)\s+|"
    r"gradua[çc][ãa]o\s+(?:em|de)\s+|"
    r"[áa]rea\s+de\s+)"
    r"([A-ZÀ-Þ][^,.;]{2,70})", re.I)
_COURSE_CUT = re.compile(
    r"\b(?:institui|fornecid|expedid|reconhecid|MEC|Minist[ée]rio)", re.I)
_GENERIC = {"INSTITUICAO", "ENSINO", "NIVEL", "CURSO", "AREA", "ESCOLA", "FACULDADE",
            "UNIVERSIDADE", "SUPERIOR", "MEDIO", "TECNICO", "GRADUACAO", "FORMACAO"}

_MIN_VALUE = 12
_MAX_VALUE = 600

# Só é formação/escolaridade o que fala de curso/nível/grau. "Requisito: CNH categoria B",
# "Registro no COREN" e "Experiência mínima" não são `education`.
_EDU_HINT = re.compile(
    r"curso|gradua[çc][ãa]o|licenciatura|bacharelado|tecn[óo]logo|"
    r"n[íi]vel\s+(?:superior|m[ée]dio|t[ée]cnico|fundamental)|"
    r"(?:superior|m[ée]dio|t[ée]cnico|fundamental)\s+(?:completo|incompleto)|"
    r"diploma|certificado\s+de\s+conclus|forma[çc][ãa]o\s+(?:em|de|superior)", re.I)
# Rótulo de Anexo II ("a) Requisitos:") é tratado pelo extrator de anexo.
_ANEXO_ITEM = re.compile(r"[a-z]\)\s*$", re.I)


def _cargo_before(text: str, position: int) -> str | None:
    """Cargo no trecho imediatamente anterior ao rótulo, no **mesmo** bloco."""
    window = text[max(0, position - 220):position]
    # Corta no fim do item anterior para não herdar um cargo distante.
    window = re.split(r"(?:\d+\.\d+(?:\.\d+)?\.?\s)", window)[-1]
    match = _CARGO_HEADER.search(window)
    if not match:
        return None
    candidate = " ".join(match.group(1).split()).strip(" -–—.:;")
    if len(candidate) < 10:
        return None
    if not re.search(r"[A-ZÀ-Þ]{3}", candidate):
        return None
    if candidate.upper().startswith(("ANEXO", "QUADRO", "TOTAL", "REQUISITO")):
        return None
    return candidate[:160]


def _courses_in(value: str) -> str | None:
    """Curso literal citado no requisito, sem capturar "instituição" ou genéricos."""
    match = _COURSE.search(value)
    if not match:
        return None
    segment = _COURSE_CUT.split(match.group(1), maxsplit=1)[0]
    course = " ".join(segment.split()).strip(" -–—.,;:")
    course = re.sub(r"^(?:em|de|da|do|na|no)\s+", "", course, flags=re.I)
    course = re.sub(r"\s+(?:em|de|da|do|na|no)$", "", course, flags=re.I)
    if len(course) < 3 or len(course) > 70:
        return None
    if course.upper() in _GENERIC:
        return None
    if not re.search(r"[A-Za-zÀ-ÿ]{4}", course):
        return None
    return course


def extract_inline_requirements(blocks: list[dict], contest_id: str, *,
                                label_prefix: str) -> list[dict]:
    """Extrai ``education``/``accepted_courses``/``si_compatibility`` de requisitos inline.

    ``role_id`` fica ``None`` e o cargo identificado entra no motivo da ambiguidade: o
    vínculo com a identidade de cargo exige reconciliação humana, como no resto do projeto.
    """
    proposals = []
    for index, block in enumerate(blocks):
        text = block.get("text") or ""
        if not isinstance(text, str) or ":" not in text:
            continue
        for label in _LABEL.finditer(text):
            # Evita reprocessar "requisitos de escolaridade" (outro extrator cuida).
            prefix_raw = text[max(0, label.start() - 30):label.start()]
            prefix = prefix_raw.lower()
            if "de escolaridade" in prefix or "de formação" in prefix or "de formacao" in prefix:
                continue
            if _ANEXO_ITEM.search(prefix_raw):
                continue  # "a) Requisitos:" do Anexo II: outro extrator cuida
            start = label.end()
            tail = text[start:start + _MAX_VALUE]
            stop = _STOP.search(tail)
            raw_value = tail[:stop.start()] if stop else tail
            value = " ".join(raw_value.split()).strip(" -–—;,:")
            if len(value) < _MIN_VALUE:
                continue
            if _EDU_HINT.search(value) is None:
                continue  # requisito não é de formação (CNH, conselho, experiência)
            end = start + len(raw_value.rstrip())
            cargo = _cargo_before(text, label.start())
            scope = (f"{label_prefix}{cargo}" if cargo
                     else "requisito sem cargo identificado no documento")
            evidence = dict(block_index=index, quote=text[start:end],
                            start_offset=start, end_offset=end)
            proposals.append(dict(
                contest_id=contest_id, role_id=None, field_name="education",
                value_json=json.dumps(value), value_type="string",
                extraction_method=METHOD,
                ambiguity_reason=f"{scope} — requisito declarado em texto corrido",
                evidence=dict(evidence)))
            courses = _courses_in(value)
            if courses:
                proposals.append(dict(
                    contest_id=contest_id, role_id=None, field_name="accepted_courses",
                    value_json=json.dumps(courses), value_type="string",
                    extraction_method=METHOD,
                    ambiguity_reason=f"{scope} — cursos citados no requisito",
                    evidence=dict(evidence)))
            state, reason = classify_si_compatibility(value)
            proposals.append(dict(
                contest_id=contest_id, role_id=None, field_name="si_compatibility",
                value_json=json.dumps(state), value_type="string",
                extraction_method="classificacao-si",
                ambiguity_reason=f"{scope} — {reason}",
                evidence=dict(evidence)))
    return proposals
