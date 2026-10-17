"""Lógica pura de preparação: normalização de conceitos, cobertura e perspectivas (Fase 22).

Mantém **separadas** as dimensões (nunca as funde numa pontuação opaca):

- **Requisito formal do cargo** — já tratado por `si_compatibility` (Fases 14–15); não é
  conhecimento.
- **Conteúdo programático do edital** — o que o documento exige.
- **Conhecimento declarado** — familiaridade subjetiva do usuário (perfil).
- **Progresso de estudo** — o que foi estudado (módulo de estudos).
- **Desempenho** — resultados reais de questões, quando existirem.
- **Preparação estimada** — cobertura do conteúdo pelo perfil (aqui).

Cobertura **não** é probabilidade de aprovação e **não** se mistura com compatibilidade formal.
"""

from __future__ import annotations

import re
import unicodedata

# Níveis de **familiaridade declarada** (subjetivos). `revisar` é uma **necessidade de ação**,
# não um nível de domínio, e por isso não aparece aqui.
FAMILIARITY_LEVELS = ("nao_avaliado", "nao_conheco", "basico", "intermediario", "avancado")
FAMILIARITY_LABELS = {
    "nao_avaliado": "Não avaliado",
    "nao_conheco": "Ainda não conheço",
    "basico": "Conhecimento básico",
    "intermediario": "Conhecimento intermediário",
    "avancado": "Conhecimento avançado",
}
CONFIDENCE_LEVELS = ("baixa", "media", "alta")
# Origens: o que é declarado pelo usuário nunca se confunde com o que vem de resultado.
ORIGINS = ("usuario", "resultado")

# Níveis que contam como "conhecido" para cobertura (familiaridade >= básico).
_KNOWN_LEVELS = {"basico", "intermediario", "avancado"}

# Termos de ligação ignorados na chave de conceito (não diferenciam assuntos).
_STOPWORDS = {"de", "da", "do", "das", "dos", "e", "a", "o", "as", "os", "em", "no", "na",
              "nos", "nas", "para", "por", "com", "ao", "aos", "um", "uma", "sobre", "entre"}


def normalize_text(text) -> str:
    """Normaliza para comparação: minúsculas, sem acento, sem pontuação, espaços colapsados."""
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^A-Za-z0-9 ]", " ", ascii_text.lower()).split())


def conceito_key(disciplina, texto) -> str:
    """Chave estável de um conceito (disciplina + tópico), usada para casar entre editais.

    A normalização **sugere** equivalência, mas não a prova: dois assuntos podem compartilhar
    palavras ("segurança" em redes vs. legislação) e continuam distintos por causa da
    disciplina. A fusão definitiva é sempre uma decisão revisável.
    """
    disc = normalize_text(disciplina)
    body = normalize_text(texto)
    tokens = [t for t in body.split() if t not in _STOPWORDS]
    return f"{disc}::{'-'.join(tokens)}".strip(":")


def coverage(program_topics, profile, *, progresso=None) -> dict:
    """Cobertura de preparação **apenas** sobre o subconjunto identificado e explícito.

    ``program_topics``: lista de ``{conceito_key, disciplina, rotulo, estado}`` em que
    ``estado`` é o estado de extração/revisão: ``confirmado``, ``extraido_nao_revisado``,
    ``ambiguo``, ``rejeitado`` ou ``nao_extraido``.
    ``profile``: mapa ``conceito_key -> {nivel, revisar}``.
    ``progresso``: mapa ``conceito_key -> {state}`` (progresso de estudo), opcional.

    O denominador são os tópicos **identificados** (confirmados + extraídos, não ambíguos nem
    rejeitados). Conteúdo não extraído **não** entra como se fosse desconhecido do usuário. A
    cobertura **não** é probabilidade de aprovação e **não** se mistura com compatibilidade
    formal. O ``basis`` sempre explica o denominador.
    """
    profile = profile or {}
    progresso = progresso or {}
    counts = {"identificados": len(program_topics), "confirmados": 0, "extraidos": 0,
              "ambiguos": 0, "rejeitados": 0, "conhecidos": 0, "nao_conhecidos": 0,
              "em_estudo": 0, "revisar": 0, "sem_perfil": 0}
    denominator = 0
    known = 0
    for topic in program_topics:
        estado = topic.get("estado")
        if estado == "confirmado":
            counts["confirmados"] += 1
        elif estado == "extraido_nao_revisado":
            counts["extraidos"] += 1
        elif estado == "ambiguo":
            counts["ambiguos"] += 1
            continue
        elif estado == "rejeitado":
            counts["rejeitados"] += 1
            continue
        else:
            continue  # não extraído: fora do denominador
        denominator += 1
        entry = profile.get(topic.get("conceito_key")) or {}
        nivel = entry.get("nivel", "nao_avaliado")
        prog = (progresso.get(topic.get("conceito_key")) or {}).get("state")
        if prog == "estudando":
            counts["em_estudo"] += 1
        if entry.get("revisar"):
            counts["revisar"] += 1
        if nivel in _KNOWN_LEVELS:
            known += 1
            counts["conhecidos"] += 1
        elif nivel == "nao_conheco":
            counts["nao_conhecidos"] += 1
        else:
            counts["sem_perfil"] += 1
    pct = int((known / denominator) * 100 + 0.5) if denominator else None
    if denominator:
        basis = (f"cobertura sobre {denominator} tópico(s) identificado(s) "
                 f"({counts['confirmados']} confirmado(s) por revisão, "
                 f"{counts['extraidos']} ainda não revisado(s))")
    else:
        basis = "sem tópicos identificados: cobertura não calculável"
    return {"counts": counts, "denominator": denominator, "known": known, "pct": pct, "basis": basis}


def perspective(*, formal_compatible, formal_ambiguous, formal_incompatible,
                coverage_pct, gaps, exceptional) -> str:
    """Classifica a oportunidade em três perspectivas (regras documentadas).

    - ``formal_incompatible`` → requisito formal desfavorável.
    - ``formal_ambiguous`` (ou cobertura não calculável com formal ok) → exige confirmação.
    - formal ok + cobertura alta (>= 60%) e sem lacunas relevantes → boa aderência atual.
    - formal ok + lacunas → oportunidade para preparar.
    - formal ok + ``exceptional`` (vagas indígenas imediatas etc.) + lacunas → oportunidade
      excepcional apesar das lacunas.
    """
    if formal_incompatible:
        return "compatibilidade_desfavoravel"
    if formal_ambiguous:
        return "exige_confirmacao"
    if coverage_pct is None:
        return "exige_confirmacao"
    if coverage_pct >= 60 and not gaps:
        return "boa_aderencia"
    if exceptional:
        return "excepcional_com_lacunas"
    return "oportunidade_para_preparar"


PERSPECTIVE_LABELS = {
    "boa_aderencia": "Boa aderência atual",
    "oportunidade_para_preparar": "Oportunidade para preparar",
    "excepcional_com_lacunas": "Oportunidade excepcional apesar das lacunas",
    "exige_confirmacao": "Exige confirmação",
    "compatibilidade_desfavoravel": "Compatibilidade formal desfavorável",
}
