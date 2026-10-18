"""Contexto de menções textuais a indígenas.

Um edital pode dizer "indígena" por vários motivos: regra de reserva exclusiva,
regra de reserva combinada com outros grupos, documento de identificação (RANI),
vestuário, conteúdo programático ou procedimento de heteroidentificação. Só regra de
reserva sustenta estado de reserva; e reserva combinada não vira cota indígena.
"""

import re

MENTION_CONTEXTS = (
    "regra_de_reserva",
    "regra_de_reserva_combinada",
    "documento_de_identificacao",
    "vestuario_ou_adorno",
    "conteudo_programatico",
    "procedimento_de_heteroidentificacao",
    "outro",
)
MENTION_CONTEXT_LABELS = {
    "regra_de_reserva": "Regra de reserva de vagas para indígenas",
    "regra_de_reserva_combinada": ("Regra de reserva combinada com outros grupos "
                                   "(quantidade indígena não separável)"),
    "documento_de_identificacao": "Documento de identificação (ex.: RANI)",
    "vestuario_ou_adorno": "Vestuário ou adorno",
    "conteudo_programatico": "Conteúdo programático",
    "procedimento_de_heteroidentificacao": "Procedimento de heteroidentificação",
    "outro": "Outro contexto",
}
# Quanto maior, mais forte a evidência de reserva (usado para escolher a melhor janela).
CONTEXT_PRIORITY = {
    "regra_de_reserva": 4,
    "regra_de_reserva_combinada": 3,
    "procedimento_de_heteroidentificacao": 1,
    "conteudo_programatico": 1,
    "vestuario_ou_adorno": 1,
    "documento_de_identificacao": 1,
    "outro": 0,
}

_GROUP = r"negros?|negras?|pret[oa]s?|pard[oa]s?|quilombol"
_GROUP_RE = re.compile(_GROUP, re.I)
# Percentual ou número por extenso ligado a indígenas.
_NUM = re.compile(
    r"(?<!\d)\d{1,3}\s*%"
    r"|\d{1,3}\s*\((?:um|uma|dois|duas|tr[êe]s|quatro|cinco|seis|sete|oito|nove|dez|"
    r"onze|doze|treze|quatorze|catorze|quinze|dezesseis|dezessete|dezoito|dezenove|"
    r"vinte|trinta|quarenta|cinquenta|sessenta|setenta|oitenta|noventa|cem|cento)\b"
    r"[^)]{0,25}\)"
    r"|\d{1,3}\s*por\s+cento", re.I)
# Grupo antes ou depois de indígenas (a ordem não pode mudar o resultado).
_COMBINED = re.compile(
    rf"(?:{_GROUP})[^.]{{0,100}}ind[íi]gen"
    rf"|ind[íi]gen[^.]{{0,100}}(?:{_GROUP})", re.I)
# Reserva forte: sustenta regra mesmo sem percentual.
_STRONG_RESERVE = re.compile(
    r"reserva(?:das?|dos?|de\s+vagas)?|\bcotas?\b|quadro\s+de\s+vagas"
    r"|ampla\s+concorr[êe]ncia|vagas?\s+reservadas?", re.I)
# "vagas" sozinho só conta junto de percentual/vaga ligada a indígenas.
_WEAK_RESERVE = re.compile(r"\bvagas?\b", re.I)
# Legenda de coluna combinada: "N/I: Candidatos negros e indígenas".
_NI_LEGEND = re.compile(r"n\s*/\s*i\s*[:=]", re.I)

_OTHER_MARKERS = (
    ("documento_de_identificacao", (
        "registro administrativo de nascimento indígena", "rani",
        "certidão de nascimento indígena", "documento de identificação civil",
    )),
    ("vestuario_ou_adorno", (
        "adorno", "vestuário", "traje", "cocar", "pintura corporal", "acessório",
        "vestimenta",
    )),
    ("conteudo_programatico", (
        "direitos territoriais", "demarcação", "usucapião indígena", "terras indígenas",
        "estatuto do índio", "povos indígenas e das comunidades tradicionais",
        "direito da antidiscriminação", "direitos dos povos indígenas",
        "lei nº 14.701",
    )),
    ("procedimento_de_heteroidentificacao", (
        "heteroidentificação", "autodeclaração", "pertencimento étnico",
        "verificação documental", "atribuição identitária",
    )),
)


def _windows(text, radius=220):
    """Pares (posição, trecho) ao redor de cada ocorrência de 'indígena'."""
    low = (text or "").lower()
    found, position = [], low.find("indígen")
    if position < 0:
        position = low.find("indigen")
    while position >= 0:
        found.append((position, low[max(0, position - radius):position + radius]))
        following = low.find("indígen", position + 1)
        if following < 0:
            following = low.find("indigen", position + 1)
        position = following
    return found


def _specific_in(window):
    """Percentual/vaga ligado a indígenas, sem outro grupo na mesma frase."""
    for match in _NUM.finditer(window):
        tail = window[match.end():match.end() + 70]
        cut = tail.find("indígen")
        if cut < 0:
            cut = tail.find("indigen")
        if cut < 0 or "." in tail[:cut]:
            continue
        if _GROUP_RE.search(tail[:cut]):
            continue
        # "10% para indígenas e quilombolas": o percentual é compartilhado.
        word = re.match(r"ind[íi]gen\w*", tail[cut:])
        rest = tail[cut + (word.end() if word else 7):]
        if re.match(r"\s*(?:e|ou)\s+(?:" + _GROUP + r")", rest, re.I):
            continue
        return True
    return False


def _classify_window(window):
    """Contexto e força da evidência na janela (força separa regra quantificada de menção)."""
    strong = bool(_STRONG_RESERVE.search(window))
    if strong:
        if _specific_in(window):
            return "regra_de_reserva", 4
        if _COMBINED.search(window):
            return "regra_de_reserva_combinada", 3
        return "regra_de_reserva", 2
    if _WEAK_RESERVE.search(window) and _specific_in(window):
        return "regra_de_reserva", 4
    if _NI_LEGEND.search(window) and "indígen" in window:
        return "regra_de_reserva_combinada", 3
    for context, markers in _OTHER_MARKERS:
        if any(marker in window for marker in markers):
            return context, 1
    return "outro", 0


def classify(text, title=None):
    """Melhor contexto do texto, a posição da ocorrência e a força da evidência."""
    windows = _windows(text)
    if not windows:
        haystack = ((title or "") + " " + (text or "")).lower()
        context, strength = _classify_window(haystack)
        return context, 0, strength
    best_context, best_position, best_strength = "outro", windows[0][0], -1
    for position, window in windows:
        context, strength = _classify_window(window)
        if strength > best_strength:
            best_context, best_position, best_strength = context, position, strength
    return best_context, best_position, best_strength


def mention_context(text, title=None):
    """Classifica o contexto da menção; regra de reserva tem prioridade."""
    return classify(text, title)[0]


def snippet(text, position, radius=80, limit=200):
    """Trecho legível em volta da ocorrência que sustenta o contexto."""
    return " ".join((text or "")[max(0, position - radius):position + radius + 80].split())[:limit]
