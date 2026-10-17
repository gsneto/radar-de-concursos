"""Banco de questões: validação, correção e estatísticas (Fase 23).

Implementação **própria** (nenhum código de terceiros copiado): os repositórios candidatos
tinham licença ausente (spaced-repetition-app, javascript-quiz-app) ou conteúdo não
redistribuível (examsim), e a lógica necessária é pequena o bastante para não compensar
adaptação.

Regras de domínio:

- Só questões de **escolha única** (uma alternativa correta) ou **verdadeiro/falso** são
  aceitas; formato ambíguo é rejeitado (nunca se "adivinha" o gabarito).
- Uma tentativa registra a **versão** respondida: editar a questão não reescreve o histórico.
- Resposta em branco **não** é erro, a menos que a regra do simulado finalizado determine
  (aqui: ``correta=None`` e ``respondida=0``).
- Percentual de acerto **não** é probabilidade de aprovação.
"""

from __future__ import annotations

import json

ALTERNATIVA_IDS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIFFICULTIES = ("facil", "media", "dificil")
KINDS = ("escolha_unica", "verdadeiro_falso")


def _clean(value) -> str:
    return " ".join(str(value or "").split()).strip()


def validate_question(*, enunciado, alternativas=None, gabarito, tipo="escolha_unica",
                      comentario=None, disciplina=None, topico=None, dificuldade=None,
                      tags=None, fonte=None, licenca=None) -> dict:
    """Valida e normaliza uma questão; levanta ``ValueError`` se o formato for ambíguo."""
    enunciado = _clean(enunciado)
    if len(enunciado) < 5:
        raise ValueError("enunciado obrigatório (mínimo 5 caracteres)")
    if tipo not in KINDS:
        raise ValueError("tipo de questão inválido")

    if tipo == "verdadeiro_falso":
        alternativas = ["Verdadeiro", "Falso"]
        gabarito = _clean(gabarito).upper()
        if gabarito not in ("V", "F"):
            raise ValueError("gabarito de verdadeiro/falso deve ser V ou F")
        normalized = [{"id": "V", "texto": "Verdadeiro"}, {"id": "F", "texto": "Falso"}]
        correct = gabarito
    else:
        if not isinstance(alternativas, (list, tuple)) or len(alternativas) < 2:
            raise ValueError("questão de escolha única exige ao menos 2 alternativas")
        if len(alternativas) > len(ALTERNATIVA_IDS):
            raise ValueError(f"máximo de {len(ALTERNATIVA_IDS)} alternativas")
        normalized, seen, texts = [], set(), set()
        for index, item in enumerate(alternativas):
            if isinstance(item, dict):
                text = _clean(item.get("texto") or item.get("text"))
                letter = _clean(item.get("id") or ALTERNATIVA_IDS[index]).upper()
            else:
                text = _clean(item)
                letter = ALTERNATIVA_IDS[index]
            if not text:
                raise ValueError(f"alternativa {letter} vazia")
            if letter in seen:
                raise ValueError(f"alternativa duplicada: {letter}")
            # Textos iguais tornam o gabarito ambíguo (duas alternativas idênticas).
            normalized_text = _clean(text).lower()
            if normalized_text in texts:
                raise ValueError("alternativas com texto duplicado tornam a questão ambígua")
            seen.add(letter)
            texts.add(normalized_text)
            normalized.append({"id": letter, "texto": text})
        correct = _clean(gabarito).upper()
        if correct not in seen:
            raise ValueError("gabarito deve corresponder a uma alternativa existente")

    if dificuldade is not None and dificuldade not in DIFFICULTIES:
        raise ValueError("dificuldade inválida")
    tag_list = normalize_tags(tags)

    return {"tipo": tipo, "enunciado": enunciado, "alternativas": normalized,
            "gabarito": correct, "comentario": _clean(comentario) or None,
            "disciplina": _clean(disciplina) or None, "topico": _clean(topico) or None,
            "dificuldade": dificuldade, "tags": tag_list,
            "fonte": _clean(fonte) or None, "licenca": _clean(licenca) or None}


def normalize_tags(tags) -> list[str]:
    """Normaliza tags: string vira uma tag (nunca é iterada por caractere)."""
    if tags is None:
        return []
    if isinstance(tags, str):
        value = _clean(tags)
        return [value] if value else []
    if not isinstance(tags, (list, tuple)):
        raise ValueError("tags devem ser lista de textos")
    return sorted({_clean(t) for t in tags if _clean(t)})


def alternatives_json(alternativas) -> str:
    return json.dumps(alternativas, ensure_ascii=False)


def parse_alternatives(raw) -> list[dict]:
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def grade(question: dict, resposta) -> dict:
    """Corrige uma resposta contra o gabarito. Branco ≠ erro (``respondida=False``)."""
    answer = _clean(resposta).upper() if resposta is not None else ""
    if not answer:
        return {"respondida": False, "correta": None}
    return {"respondida": True, "correta": answer == _clean(question.get("gabarito")).upper()}


def stats(attempts, *, include_blank=False) -> dict:
    """Estatísticas de desempenho com denominador explícito.

    Por padrão, tentativas em branco **não** entram no denominador (não são erro). Com
    ``include_blank=True`` (simulado finalizado), brancos contam como erro.
    """
    attempts = list(attempts or [])
    respondidas = [a for a in attempts if a.get("respondida")]
    considered = attempts if include_blank else respondidas
    acertos = sum(1 for a in attempts if a.get("correta") is True)
    erros = sum(1 for a in respondidas if a.get("correta") is False)
    brancos = sum(1 for a in attempts if not a.get("respondida"))
    denominator = len(considered)
    pct = int((acertos / denominator) * 100 + 0.5) if denominator else None
    return {"total": len(attempts), "respondidas": len(respondidas), "acertos": acertos,
            "erros": erros, "brancos": brancos, "denominator": denominator, "pct": pct,
            "basis": (f"{pct}% sobre {denominator} tentativa(s)"
                      + ("" if include_blank else " respondida(s)")
                      if denominator else "sem tentativas: percentual não calculável")}


def stats_by(attempts, key: str, *, include_blank=False) -> list[dict]:
    """Agrupa estatísticas por ``disciplina`` ou ``topico`` (só grupos com dados)."""
    groups: dict[str, list] = {}
    for attempt in attempts or []:
        name = _clean(attempt.get(key)) or "(sem informação)"
        groups.setdefault(name, []).append(attempt)
    out = []
    for name, items in groups.items():
        result = stats(items, include_blank=include_blank)
        out.append({"grupo": name, **result})
    out.sort(key=lambda g: (-(g["total"] or 0), g["grupo"]))
    return out
