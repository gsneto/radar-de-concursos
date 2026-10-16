"""Localização estruturada de concursos: prova, lotação e abrangência.

Separa rigorosamente **local de prova**, **lotação** e **abrangência**, sempre a partir de
evidência documental. Nada é inferido (não se presume que a prova ocorre na cidade do órgão,
na capital do estado ou no local de lotação). Uma localização ausente **não** equivale a uma
localização distante, e um estado conhecido sem município confirmado **não** equivale a uma
coordenada precisa.

Este módulo é puro (sem banco): recebe propostas/valores já lidos do histórico documental e
devolve uma visão estruturada com estado de extração explícito.
"""

from __future__ import annotations

import re
import unicodedata

# Unidades da Federação (código -> nome normalizado).
UFS = {
    "AC": "acre", "AL": "alagoas", "AP": "amapa", "AM": "amazonas", "BA": "bahia",
    "CE": "ceara", "DF": "distrito federal", "ES": "espirito santo", "GO": "goias",
    "MA": "maranhao", "MT": "mato grosso", "MS": "mato grosso do sul", "MG": "minas gerais",
    "PA": "para", "PB": "paraiba", "PR": "parana", "PE": "pernambuco", "PI": "piaui",
    "RJ": "rio de janeiro", "RN": "rio grande do norte", "RS": "rio grande do sul",
    "RO": "rondonia", "RR": "roraima", "SC": "santa catarina", "SP": "sao paulo",
    "SE": "sergipe", "TO": "tocantins",
}
_UF_BY_NAME = {name: code for code, name in UFS.items()}
# Grafia oficial acentuada (para casar nomes de estado no texto cru, que traz acentos).
_UF_ACCENTED = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul",
    "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
    "SE": "Sergipe", "TO": "Tocantins",
}

# Estados de extração de uma localização (distintos de "distante").
LOCATION_STATES = (
    "confirmado_documentalmente",
    "extraido_nao_revisado",
    "ambiguo",
    "em_conflito",
    "nao_informado",
    "nao_extraido",
)

# Abrangência de atuação (lotação).
SCOPES = ("nacional", "estadual", "municipal", "regional", "desconhecida")

_NACIONAL = re.compile(
    r"\b(?:nacional|todo o (?:territ[óo]rio|pa[íi]s)|todas as unidades da federa[çc][ãa]o|"
    r"qualquer (?:munic[íi]pio|localidade)|em todo o brasil)\b", re.I)

# Palavras de texto corrido que nunca fazem parte de um nome de município. Sem essa guarda,
# "a definir - para todos" viraria município no Pará e "na cidade de Salvador" viraria um
# município gigante. Rejeitar é mais honesto do que fabricar uma localização.
_PROSE_STOPWORDS = {
    "cidade", "estado", "municipio", "local", "localidade", "prova", "provas", "vagas", "vaga",
    "cargo", "cargos", "candidatos", "candidato", "regiao", "uf", "inscricao", "inscricoes",
    "avenida", "rua", "travessa", "rodovia", "praca", "alameda", "estrada", "bairro", "distrito",
    "endereco", "site", "sede", "unidade", "polo", "nucleo",
    "para", "de", "da", "do", "das", "dos", "na", "no", "nas", "nos", "em", "a", "o", "as", "os",
    "e", "ao", "aos", "sera", "serao", "realizada", "realizado", "realizar", "realizadas",
    "todos", "todas", "definir", "definida", "ainda", "outros", "outras",
}
_CONNECTIVES = {"de", "da", "do", "das", "dos", "e"}

# Formas capitalizadas dos estados (com e sem acento) para casar nomes de estado no texto cru.
_STATE_FORMS = sorted(
    {form for form in _UF_ACCENTED.values()} | {name.title() for name in _UF_BY_NAME},
    key=len, reverse=True)
_STATE_ALT = "|".join(re.escape(form) for form in _STATE_FORMS)

# "Salvador/BA", "Salvador - BA", "Salvador (BA)", "Recife/PE" (UF por código).
_MUN_UF = re.compile(r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’.\- ]{0,60}?)\s*[/\-–(]\s*([A-Z]{2})\b")
# "Paulo Afonso - Bahia", "Belém / Pará" (UF por nome, capitalizada no texto).
_MUN_UF_NAME = re.compile(
    r"(?<![A-Za-zÀ-ÿ])([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’.\- ]{0,60}?)\s*[/\-–]\s*(" + _STATE_ALT + r")(?![A-Za-zÀ-ÿ])")
# "no estado da Bahia", "Estado de Pernambuco".
_UF_NAME = re.compile(
    r"\b(?:no\s+)?(?:estado\s+(?:da|de|do)\s+|uf\s*:?\s*)(" + _STATE_ALT + r")(?![A-Za-zÀ-ÿ])")


def _norm(text) -> str:
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^A-Za-z0-9 ]", " ", ascii_text.lower()).split())


def _title(text: str) -> str:
    """Capitaliza preservando conectivos minúsculos ("Juazeiro do Norte", "D'Oeste")."""
    out = []
    for index, word in enumerate(text.split()):
        if index > 0 and _norm(word) in _CONNECTIVES:
            out.append(word.lower())
        elif "'" in word or "’" in word:
            head, _, tail = word.replace("’", "'").partition("'")
            out.append(head[:1].upper() + head[1:].lower() + "'" + tail[:1].upper() + tail[1:].lower())
        else:
            out.append(word[:1].upper() + word[1:].lower())
    return " ".join(out)


def _clean_municipio(group: str):
    """Município plausível a partir de um grupo, ou ``None`` (texto corrido é rejeitado)."""
    words = [w for w in re.split(r"\s+", group.strip(" .,;:-\u2013\u2014")) if w]
    # Descarta palavras iniciais de texto corrido ("cidade de Paulo Afonso" -> "Paulo Afonso").
    start = 0
    while start < len(words) and _norm(words[start]) in _PROSE_STOPWORDS:
        start += 1
    words = words[start:]
    if not words or len(words) > 3:
        return None
    # Conectivos ("de", "do", "e") são permitidos dentro do nome; demais palavras de texto
    # corrido indicam que o grupo não é um município.
    if any(_norm(w) in (_PROSE_STOPWORDS - _CONNECTIVES) for w in words):
        return None
    if not words[0][:1].isupper():
        return None
    name = " ".join(words)
    if _norm(name) in _UF_BY_NAME:
        return None  # nome de estado não é município
    return _title(name)



def valid_uf(code) -> bool:
    return isinstance(code, str) and code.upper() in UFS


def parse_location(text) -> dict | None:
    """Interpreta um texto de localização em ``{municipio, uf, scope, confidence, reason}``.

    Conservador: só emite UF quando há marcador explícito (``Município/UF`` ou ``estado da X``).
    Devolve ``None`` quando não há localização reconhecível — nunca inventa.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    raw = text.strip()
    if _NACIONAL.search(raw):
        return {"municipio": None, "uf": None, "scope": "nacional",
                "confidence": "alta", "reason": "abrangência nacional declarada"}
    match = _MUN_UF.search(raw)
    if match:
        municipio = _clean_municipio(match.group(1))
        uf = match.group(2).upper()
        if uf in UFS and municipio:
            return {"municipio": municipio, "uf": uf, "scope": "municipal",
                    "confidence": "alta", "reason": "município com UF explícitos"}
    named = _MUN_UF_NAME.search(raw)
    if named:
        municipio = _clean_municipio(named.group(1))
        uf = _UF_BY_NAME.get(_norm(named.group(2)))
        if municipio and uf:
            return {"municipio": municipio, "uf": uf, "scope": "municipal",
                    "confidence": "alta", "reason": "município com UF explícitos"}
    uf_match = _UF_NAME.search(raw)
    if uf_match:
        uf = _UF_BY_NAME.get(_norm(uf_match.group(1)))
        if uf:
            return {"municipio": None, "uf": uf, "scope": "estadual",
                    "confidence": "media", "reason": "apenas o estado foi identificado"}
    # Só o código de UF isolado (ex.: "BA") ou o nome do estado isolado ("Rondônia").
    token = raw.strip().upper()
    if token in UFS:
        return {"municipio": None, "uf": token, "scope": "estadual",
                "confidence": "media", "reason": "apenas a UF foi identificada"}
    named_state = _UF_BY_NAME.get(_norm(raw))
    if named_state:
        return {"municipio": None, "uf": named_state, "scope": "estadual",
                "confidence": "media", "reason": "apenas o estado foi identificado"}
    return None


def _state_from_items(items: list[dict]) -> tuple[str, dict | None]:
    """Estado de extração + item representativo a partir das propostas de um campo."""
    if not items:
        return "nao_extraido", None
    states = {item.get("state") for item in items}
    distinct = {_norm(item.get("value")) for item in items}
    if "validado" in states:
        return "confirmado_documentalmente", _pick(items, "validado")
    if len(distinct) > 1:
        return "em_conflito", _pick(items, "ambiguo") or items[0]
    if states == {"ambiguo"}:
        return "ambiguo", items[0]
    return "extraido_nao_revisado", items[0]


def _pick(items: list[dict], state: str) -> dict | None:
    for item in items:
        if item.get("state") == state:
            return item
    return None


def _representative_value(items: list[dict]) -> str | None:
    """Valor textual literal mais representativo (validado > extraído > qualquer)."""
    for state in ("validado", "extraido", "ambiguo"):
        for item in items:
            if item.get("state") == state and isinstance(item.get("value"), str):
                return item["value"]
    for item in items:
        if isinstance(item.get("value"), str):
            return item["value"]
    return None


def _field_view(items: list[dict], *, analyzed: bool) -> dict:
    """Visão estruturada de um campo de localização (prova ou lotação)."""
    state, representative = _state_from_items(items)
    if not items and analyzed:
        state = "nao_informado"
    text = _representative_value(items)
    parsed = parse_location(text) if text else None
    view = {
        "state": state,
        "uf": parsed["uf"] if parsed else None,
        "municipios": [parsed["municipio"]] if parsed and parsed["municipio"] else [],
        "scope": parsed["scope"] if parsed else "desconhecida",
        "confidence": parsed["confidence"] if parsed else None,
        "text": text,
        "reason": parsed["reason"] if parsed else (
            "localização não identificada no texto documental" if text
            else "sem dado documental de localização"),
        "evidence": representative.get("evidence") if representative else None,
        "version_id": (representative.get("evidence") or {}).get("version_id") if representative else None,
    }
    return view


def _logical_items(by_field: dict, primary: str, extras: tuple[str, ...]) -> list[dict]:
    """Itens do campo primário; só usa os extras quando o primário está ausente.

    Evita falso conflito entre campos coerentes (ex.: ``exam_location="Salvador/BA"`` e
    ``exam_uf="BA"`` descrevem o mesmo local). O conflito é medido **dentro** de um campo.
    """
    items = by_field.get(primary, [])
    if items:
        return items
    combined = []
    for name in extras:
        combined.extend(by_field.get(name, []))
    return combined


def resolve_location(proposals: list[dict], *, analyzed: bool) -> dict:
    """Resolve a localização estruturada de um concurso a partir das propostas.

    ``proposals`` são propostas já lidas (com ``field_name``, ``value``, ``state`` e
    ``evidence``). ``analyzed`` indica se há documentos analisados (para distinguir
    "não informado no documento" de "não extraído"). Prova e lotação são resolvidas
    separadamente; a lotação **nunca** substitui o local de prova.
    """
    by_field: dict[str, list[dict]] = {}
    for item in proposals or []:
        by_field.setdefault(item.get("field_name"), []).append(item)

    exam_items = _logical_items(by_field, "exam_location", ("exam_municipio", "exam_uf"))
    work_items = _logical_items(by_field, "work_location", ("work_municipio", "work_uf"))

    return {"prova": _field_view(exam_items, analyzed=analyzed),
            "lotacao": _field_view(work_items, analyzed=analyzed)}
