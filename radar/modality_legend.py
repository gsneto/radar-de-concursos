"""Semântica de modalidades de vaga declarada **pelo próprio documento**.

O Radar não pode impor uma taxonomia global: a mesma sigla pode significar coisas
diferentes em bancas diferentes. Este módulo lê as definições do edital (ex.:
``I – AC: Ampla Concorrência; ... VI – PPIQ: vaga unificada ...``) e devolve, para cada
sigla, se ela é categoria exclusiva, categoria unificada ou total agregado, com a
evidência literal que sustenta a leitura.

Também interpreta a notação de cadastro de reserva usada nos quadros
(``10+CR``, ``CR``, ``CR*``, ``15 + CR``) sem transformar reserva em vaga imediata nem
inventar quantidade que o documento não publica.
"""

from __future__ import annotations

import re
import unicodedata

# Siglas de modalidade aceitas como cabeçalho de coluna (forma curta).
SIGLA_RE = re.compile(r"[A-Z]{1,5}(?:/[A-Z]{1,5})?\*?")

# "I – AC: Ampla Concorrência" / "VII - PI/PQ: vaga unificada ..."
_DEFINITION = re.compile(
    r"(?P<roman>I{1,3}|IV|V|VI{0,3}|IX|X)\s*[–-]\s*"
    r"(?P<sigla>[A-Z]{1,5}(?:/[A-Z]{1,5})?\*?)\s*:\s*"
    r"(?P<label>[^;.]{3,180})")

_GROUPS = (
    ("pretas_e_pardas", re.compile(r"pretas?\s+e\s+pardas?|negros?", re.I)),
    ("indigenas", re.compile(r"ind[íi]genas?", re.I)),
    ("quilombolas", re.compile(r"quilombolas?", re.I)),
)

# Nota de asterisco: linha curta que explica o símbolo e fala de vaga/reserva.
_ASTERISK_NOTE = re.compile(
    r"(?:^|\s)\*{1,2}\s*([A-ZÀ-Þ][^.]{10,240}\.)", re.MULTILINE)


def normalize(text) -> str:
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    return " ".join("".join(ch for ch in decomposed
                            if not unicodedata.combining(ch)).upper().split())


def _sigla_key(sigla: str) -> str:
    return normalize(sigla).replace(" ", "")


def parse_definitions(text: str) -> dict[str, dict]:
    """Definições de sigla publicadas no documento (vazio quando não há)."""
    found: dict[str, dict] = {}
    for match in _DEFINITION.finditer(text or ""):
        sigla = _sigla_key(match.group("sigla"))
        label = " ".join(match.group("label").split())
        if not sigla or sigla in found:
            continue
        found[sigla] = {
            "sigla": sigla,
            "label": label,
            "unified": bool(re.search(r"unificad", label, re.I)),
            "groups": [name for name, pattern in _GROUPS if pattern.search(label)],
            "quote": " ".join(match.group(0).split()),
        }
    return found


def kind(definitions: dict[str, dict], sigla: str) -> str:
    """``exclusive``, ``unified``, ``aggregate`` ou ``unknown`` para a sigla."""
    key = _sigla_key(sigla)
    if key in ("TOTAL", "TOTALGERAL"):
        return "aggregate"
    entry = definitions.get(key)
    if entry is None:
        return "unknown"
    if entry["unified"] or len(entry["groups"]) > 1:
        # Definição que nomeia dois ou mais grupos é vaga unificada, mesmo sem a palavra.
        return "unified"
    if "total" in normalize(entry["label"]).lower():
        return "aggregate"
    return "exclusive"


def cr_notation(cell) -> dict | None:
    """Interpreta uma célula de vagas com notação de cadastro de reserva.

    Devolve ``immediate`` (int ou ``None``), ``reserve`` (bool), ``asterisk`` (bool) e
    ``explicit_zero`` (bool). ``None`` quando a célula não é uma quantidade.

    ``CR`` sem número nunca vira zero nem vaga imediata: a quantidade é desconhecida.
    """
    if not isinstance(cell, str):
        return None
    text = " ".join(cell.split())
    if not text:
        return None
    if text in ("-", "–", "—"):
        return {"immediate": 0, "reserve": False, "asterisk": False,
                "explicit_zero": True, "raw": text}
    match = re.fullmatch(r"(?P<number>\d{1,5})?\s*(?P<plus>\+)?\s*(?P<cr>CR)?"
                         r"\s*(?P<star>\*)?", text, re.I)
    if match is None:
        return None
    number = match.group("number")
    has_cr = bool(match.group("cr"))
    if number is None and not has_cr:
        return None
    return {
        "immediate": int(number) if number is not None else None,
        "reserve": has_cr,
        "asterisk": bool(match.group("star")),
        "explicit_zero": number is not None and int(number) == 0,
        "raw": text,
    }


def asterisk_note(text: str) -> str | None:
    """Nota que explica o asterisco do quadro, quando o documento a publica.

    Exige que a nota fale de vaga, reserva ou do próprio asterisco. A linha de renda do
    formulário socioeconômico (``RENDA*``) não é nota de quadro.
    """
    for match in _ASTERISK_NOTE.finditer(text or ""):
        note = " ".join(match.group(0).split())
        if re.search(r"\bvagas?\b|reserva|asterisco|posi[çc][ãa]o", note, re.I):
            return note
    return None
