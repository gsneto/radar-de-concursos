"""Extração do **local de prova** a partir do edital (Fase 26).

O campo permanecia em 0% porque não existia extrator: ``location.py`` apenas interpreta
propostas existentes. Este módulo cria as propostas com evidência, seguindo as regras do
domínio:

- local de prova **nunca** é inferido de lotação, sede do órgão, endereço da banca ou notícia;
- "as provas serão realizadas na cidade de X" é candidato a local de aplicação;
- "os locais serão divulgados em <data>" é registrado como **a divulgar**, não como ausente;
- menções que não são de prova (heteroidentificação, entrevista, atendimento especial,
  horário oficial de Brasília) são descartadas;
- lista de cidades **não** é reduzida a uma: vira um único valor com todas as cidades, ou
  propostas separadas por cidade quando o texto as separa claramente;
- toda proposta nasce como candidata (``ambiguity_reason``), exigindo revisão humana.

Nada é confirmado automaticamente.
"""

from __future__ import annotations

import json
import re

METHOD = "local-prova"

# Sentença que fala de aplicação/realização de prova.
_EXAM_CONTEXT = re.compile(
    r"\b(?:provas?|exame|aplica[cç][aã]o)\b"
    r"|\b(?:etapas?\s+e\s+(?:as\s+)?fases?|fases?\s+e\s+(?:as\s+)?etapas?)\b", re.I)
# Sentença que declara publicação futura dos locais.
# "serão" tem "ã": a classe precisa cobrir a/á/ã, senão a declaração de publicação
# futura não é reconhecida e o campo parece ausente.
_PENDING = re.compile(
    r"\b(?:loc(?:al|ais)\b[^.]{0,80}?(?:ser(?:a|á|ã)o?\s+divulgad|a\s+divulgar)"
    r"|ser(?:a|á|ã)o?\s+divulgad[^.]{0,60}?loc(?:al|ais))", re.I)
# "na cidade de Macapá", "no município de Santana", "no Município do Rio de Janeiro"
_CITY = re.compile(
    r"\b(?:na|no|em)\s+(?:cidade|munic[ií]pio)\s+(?:de|do|da)\s+"
    r"([A-ZÀ-Þ][^,;.()/]{2,60})"
    r"(?:\s*[/\-\u2013\u2014]\s*([A-Z]{2})\b)?"
    r"(?:,\s*([A-Za-zÀ-ÿ ]{2,20}))?",
    re.I)
# "nas cidades de Curitiba/PR e Maringá/PR" (lista de municípios)
_CITIES_PLURAL = re.compile(
    r"\b(?:nas|nos)\s+(?:cidades|munic[ií]pios)\s+(?:de|do|da)\s+(.{3,240}?)(?:[.;]|$)", re.I)
_CITY_UF_ANY = re.compile(r"([A-ZÀ-Þ][^,;.()/]{2,40}?)\s*/\s*([A-Z]{2})\b")
# "em Macapá/AP" (sem a palavra cidade) — só aceito com UF explícita.
_CITY_UF = re.compile(r"\bem\s+([A-ZÀ-Þ][^,;.()]{2,50})\s*[/-]\s*([A-Z]{2})\b")
# Contextos que mencionam cidade mas NÃO são local de prova.
_NOT_EXAM = re.compile(
    r"heteroidentifica|entrevista|autodeclara|atendimento\s+especial|hor[aá]rio\s+oficial"
    r"|verifica[cç][aã]o\s+da\s+condi[cç][aã]o|procedimentos?\s+presencia",
    re.I)
# "sede do órgão", "endereço da banca": não é local de prova.
_NOT_LOCATION = re.compile(
    r"sede\s+(?:do|da)\s+(?:[oó]rg[aã]o|banca|institui[cç][aã]o)"
    r"|lota[cç][aã]o|local\s+de\s+exerc[ií]cio|local\s+de\s+trabalho"
    r"|exerc[ií]cio\s+do\s+cargo", re.I)

_STATE_NAMES = {
    "acre": "AC", "alagoas": "AL", "amapá": "AP", "amapa": "AP", "amazonas": "AM",
    "bahia": "BA", "ceará": "CE", "ceara": "CE", "distrito federal": "DF",
    "espírito santo": "ES", "espirito santo": "ES", "goiás": "GO", "goias": "GO",
    "maranhão": "MA", "maranhao": "MA", "mato grosso": "MT", "mato grosso do sul": "MS",
    "minas gerais": "MG", "pará": "PA", "paraíba": "PB", "paraiba": "PB",
    "paraná": "PR", "parana": "PR", "pernambuco": "PE", "piauí": "PI", "piaui": "PI",
    "rio de janeiro": "RJ", "rio grande do norte": "RN", "rio grande do sul": "RS",
    "rondônia": "RO", "rondonia": "RO", "roraima": "RR", "santa catarina": "SC",
    "são paulo": "SP", "sao paulo": "SP", "sergipe": "SE", "tocantins": "TO",
}

# Texto de PDF perde as quebras de linha e os itens vêm como "1.4 As etapas ...": a fronteira
# real é o número do item seguido de maiúscula, não só o ponto final.
_SENTENCE_SPLIT = re.compile(
    r"(?<=[.;:!?])\s+(?=[A-ZÀ-Þ0-9])|(?<=\d)\s+(?=[A-ZÀ-Þ])")


def _clean(value: str) -> str:
    # Travessão/en-dash também são separadores ("Porto Alegre – RS") e não fazem parte do nome.
    return " ".join((value or "").split()).strip(" .,;:-\u2013\u2014")


VALID_UFS = frozenset(_STATE_NAMES.values()) | {"DF"}


def _valid_uf(value) -> str | None:
    """Aceita apenas UF real (evita "em"/"as"/"de" virarem unidade da federação)."""
    if not isinstance(value, str):
        return None
    candidate = value.strip().upper()
    return candidate if candidate in VALID_UFS else None


def _exam_clause(sentence: str) -> str | None:
    """Cláusula da frase que fala da prova, quando a lotação aparece junto."""
    parts = re.split(r"\s+e\s+|;", sentence)
    for part in parts:
        if _EXAM_CONTEXT.search(part) and not _NOT_LOCATION.search(part):
            return part
    return None


def _city_name(raw: str) -> str:
    """Nome do município a partir do trecho capturado, sem cauda descritiva."""
    text = _clean(raw)
    text = re.split(r"\s+(?:no|na|do|da|em)\s+(?:Estado|estado|UF|Unidade)\b", text)[0]
    # Cauda descritiva depois do município ("... das 13h às 18h", "... no dia 12").
    text = re.split(r"\s+(?:das?|às|as|no\s+dia|a\s+partir|segundo|conforme|onde|que)\b",
                    text)[0]
    # Conjunção seguida de minúscula encerra o nome ("Macapá e o candidato ...").
    text = re.split(r"\s+e\s+(?=[a-zà-ÿ])", text)[0]
    text = re.split(r"\s*[/\-\u2013\u2014]\s*[A-Z]{2}\s*$", text)[0]
    text = re.split(r"\s+[A-Z]{2}\s*$", text)[0]
    text = _clean(text)
    # Remove sufixos genéricos de local ("Município de X" já foi consumido pela âncora).
    return text[:60].strip()


def _split_city_list(city: str) -> list[str]:
    """"Macapá e Santana" são dois municípios; nunca um nome só."""
    parts = re.split(r"\s+e\s+(?=[A-ZÀ-Þ])", city or "")
    return [_clean(part) for part in parts if _clean(part)]


def _uf_from_text(text: str) -> str | None:
    """UF declarada de forma explícita: ``(AP)`` ou ``Estado do Amapá``.

    Não se procura nome de estado solto no texto: a preposição "para" (sem acento) casaria
    com "Pará" e produziria UF falsa.
    """
    match = re.search(r"\(\s*([A-Z]{2})\s*\)", text)
    if match:
        return match.group(1)
    match = re.search(r"\bEstado\s+(?:de|do|da)\s+([A-Za-zÀ-ÿ ]{3,30})", text, re.I)
    if match:
        name = _clean(match.group(1)).lower()
        for state, uf in sorted(_STATE_NAMES.items(), key=lambda item: -len(item[0])):
            if name.startswith(state):
                return uf
    return None


def find_exam_locations(blocks: list[dict]) -> list[dict]:
    """Candidatos de local de prova, com página e trecho literal.

    Devolve uma lista de ``{field_name, value, quote, page_number, start_offset,
    end_offset, note}``. Pode vir vazia (documento sem menção a local de prova) — o que
    **não** prova que o concurso não tenha local, apenas que este documento não o informa.
    """
    found: list[dict] = []
    pending: list[dict] = []
    for index, block in enumerate(blocks or []):
        if block.get("page_number") is None:
            continue
        text = block.get("text") or ""
        if not _EXAM_CONTEXT.search(text):
            continue
        cursor = 0
        for sentence in _SENTENCE_SPLIT.split(text):
            start = text.find(sentence, cursor)
            if start < 0:
                start = cursor
            cursor = start + len(sentence)
            if not _EXAM_CONTEXT.search(sentence) or _NOT_EXAM.search(sentence):
                continue
            if _NOT_LOCATION.search(sentence):
                # Frase fala de lotação/exercício: só aceita se a cidade estiver na
                # **cláusula da prova**, não na cláusula da lotação.
                sentence = _exam_clause(sentence)
                if sentence is None:
                    continue
            cities = []
            for match in _CITY.finditer(sentence):
                city = _city_name(match.group(1))
                uf = _valid_uf(match.group(2)) or _uf_from_text(sentence)
                if not uf:
                    # "cidade de Porto Alegre – RS": a UF vem depois do travessão.
                    tail = re.search(r"[/\-\u2013\u2014]\s*([A-Z]{2})\s*$",
                                     _clean(match.group(1)))
                    uf = _valid_uf(tail.group(1)) if tail else None
                if not uf and match.group(3):
                    raw = _clean(match.group(3))
                    uf = (_valid_uf(raw) if len(raw) == 2
                          else _STATE_NAMES.get(raw.lower()))
                for name in _split_city_list(city):
                    if len(name) >= 3:
                        cities.append((name, uf))
            if not cities:
                for plural in _CITIES_PLURAL.finditer(sentence):
                    for pair in _CITY_UF_ANY.finditer(plural.group(1)):
                        city = _city_name(pair.group(1))
                        for name in _split_city_list(city):
                            if len(name) >= 3:
                                cities.append((name, _valid_uf(pair.group(2))))
            if not cities:
                for match in _CITY_UF.finditer(sentence):
                    city = _city_name(match.group(1))
                    for name in _split_city_list(city):
                        if len(name) >= 3:
                            cities.append((name, _valid_uf(match.group(2))))
            if cities:
                # Remove duplicatas preservando a ordem de citação.
                by_name: dict[str, tuple[str, str | None]] = {}
                for city, uf in cities:
                    key = city.lower()
                    previous = by_name.get(key)
                    if previous is None or (not previous[1] and uf):
                        by_name[key] = (city, uf)
                unique = list(by_name.values())
                found.append({"cities": unique, "quote": sentence, "page_number":
                              block.get("page_number"), "start_offset": start,
                              "end_offset": start + len(sentence), "block_index": index,
                              "pending": False})
            elif _PENDING.search(sentence):
                pending.append({"cities": [], "quote": sentence,
                                "page_number": block.get("page_number"),
                                "start_offset": start, "end_offset": start + len(sentence),
                                "block_index": index, "pending": True})
    return found + pending


def extract_exam_location(blocks: list[dict], contest_id: str, *, label_prefix: str) -> list[dict]:
    """Propostas de local de prova (``exam_location``/``exam_municipio``/``exam_uf``).

    Regras de honestidade aplicadas:

    - várias cidades → **um** valor com todas ("Macapá/AP; Santana/AP"), nunca uma só;
    - "locais serão divulgados" → valor ``a_divulgar`` (informação declarada, não ausência);
    - ``exam_municipio``/``exam_uf`` só quando há **uma** cidade identificável;
    - ``exam_location`` só é emitido quando há cidade ou declaração de divulgação futura.
    """
    proposals: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in find_exam_locations(blocks):
        quote = item["quote"]
        if item["pending"]:
            value = "a_divulgar"
            note = ("o documento declara que os locais serão divulgados depois; "
                    "não é ausência de informação")
        else:
            parts = [f"{city}/{uf}" if uf else city for city, uf in item["cities"]]
            value = "; ".join(parts)
            note = ("local de aplicação citado no documento; revisar se vale para a etapa "
                    "de prova objetiva e se a lista está completa")
        evidence = dict(block_index=item["block_index"], quote=quote,
                        start_offset=item["start_offset"], end_offset=item["end_offset"],
                        page_number=item["page_number"], header="Local de prova")
        # "Salvador" e "Salvador/BA" são o mesmo local: a UF só qualifica, não diferencia.
        key = ("exam_location", re.sub(r"/[A-Z]{2}$", "", value).lower())
        if key in seen:
            if "/" in value:
                # Já registrado sem UF e agora há UF: substitui a proposta sem UF.
                for index, existing in enumerate(proposals):
                    if (existing["field_name"] == "exam_location"
                            and re.sub(r"/[A-Z]{2}$", "",
                                       json.loads(existing["value_json"]).lower()) == key[1]):
                        proposals[index] = _proposal(
                            contest_id, "exam_location", value,
                            existing["ambiguity_reason"], evidence)
                        break
            continue
        seen.add(key)
        ambiguity = f"{label_prefix}local de prova candidato — {note}"
        proposals.append(_proposal(contest_id, "exam_location", value, ambiguity, evidence))
        if not item["pending"] and len(item["cities"]) == 1:
            city, uf = item["cities"][0]
            for name, raw in (("exam_municipio", city), ("exam_uf", (uf or "").upper())):
                if not raw or (name, raw.lower()) in seen:
                    continue
                seen.add((name, raw.lower()))
                proposals.append(_proposal(contest_id, name, raw, ambiguity, evidence))
    return proposals


def _proposal(contest_id, field_name, value, ambiguity, evidence):
    return dict(contest_id=contest_id, role_id=None, field_name=field_name,
                value_json=json.dumps(value[:300]), value_type="string",
                extraction_method=METHOD, ambiguity_reason=ambiguity,
                evidence=dict(evidence))
