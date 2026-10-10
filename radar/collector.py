"""Conector HTML da fonte oficial da Prefeitura de Guajará-Mirim/RO (SEMED).

Coleta somente o que está textual e inequivocamente expresso na página do
artigo. Não interpreta edital nem retificações ligadas, não infere
escolaridade, local ou cota e não converte cadastro de reserva sem
quantitativo em zero. O parser falha fechado com ``ValueError`` quando a
estrutura ou os fatos esperados não são encontrados.
"""

from __future__ import annotations

import re
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SOURCE_URL = (
    "https://guajaramirim.ro.gov.br/"
    "prefeitura-de-guajara-mirim-abre-inscricoes-para-concurso-publico-"
    "da-educacao-com-107-vagas-e-cadastro-de-reserva/"
)
SOURCE_NAME = "Prefeitura Municipal de Guajará-Mirim/RO"
AGENCY = "Prefeitura Municipal de Guajará-Mirim/RO (SEMED)"
COMPETITION = "Concurso público da educação"

_ALLOWED_HOST = "guajaramirim.ro.gov.br"
_TIMEOUT_SECONDS = 15
_MAX_BYTES = 2_000_000
_REGISTRATION_CLOSED_STATUS = "encerradas conforme período divulgado"

_MONTH_NAMES = {
    "janeiro": "01",
    "fevereiro": "02",
    "março": "03",
    "abril": "04",
    "maio": "05",
    "junho": "06",
    "julho": "07",
    "agosto": "08",
    "setembro": "09",
    "outubro": "10",
    "novembro": "11",
    "dezembro": "12",
}
_MONTH_PATTERN = "|".join(_MONTH_NAMES)

# Formato real do artigo: número antes do cargo, ligados pelo conector
# explícito ``para``, com pontuação final opcional, por exemplo
# ``69 para Professor de Educação Infantil;``. O conector é obrigatório: uma
# lista alterada sem ``para`` falha fechado em vez de casar por permissividade.
_ROLE_RE = re.compile(
    r"^(?P<count>\d+)\s+para\s+(?P<role>Professor\b.+?)\s*[.;:]?$",
    re.IGNORECASE,
)
_COMPETITION_ID_RE = re.compile(r"n[ºo°]\s*(\d{3}/\d{4})", re.IGNORECASE)
_TOTAL_RE = re.compile(r"(\d+)\s+vagas?\b", re.IGNORECASE)
# Aceita período numérico (``10 a 30/07/2026``) e por extenso
# (``entre 10 e 30 de julho de 2026``). Dia final e mês/ano são obrigatórios.
_PERIOD_RE = re.compile(
    r"(?P<start_day>\d{1,2})"
    r"(?:/(?P<start_month>\d{2})/(?P<start_year>\d{4}))?"
    r"\s+(?:a|e|até)\s+"
    r"(?P<end_day>\d{1,2})"
    r"(?:/(?P<end_month>\d{2})/(?P<end_year>\d{4})"
    r"|\s+de\s+(?P<month_name>" + _MONTH_PATTERN + r")\s+de\s+(?P<text_year>\d{4}))",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_REALIZED_RE = re.compile(
    r"inscri[çc][õo]es(?:(?!\bn[aã]o\b)[^.\n])*\bforam\s+realizad",
    re.IGNORECASE,
)
_NO_RESERVE_RE = re.compile(
    r"n[aã]o\s+haver[áa]\s+cadastro\s+de\s+reserva\s*:\s*0\s+vagas?\b",
    re.IGNORECASE,
)
_EXAM_LOCATION_RE = re.compile(
    r"local\s+de\s+prova\s*:\s*([^.\n]+)", re.IGNORECASE
)
_WORK_LOCATION_RE = re.compile(
    r"local\s+de\s+exerc[íi]cio\s*:\s*([^.\n]+)", re.IGNORECASE
)

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value).strip()


class _ArticleTextParser(HTMLParser):
    """Extrai título da página e texto/listas visíveis do artigo oficial."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.list_items: list[str] = []
        self.text_parts: list[str] = []
        self._skip_depth = 0
        self._article_depth = 0
        self._in_title = False
        self._in_h1 = False
        self._li_buffer: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("script", "style"):
            self._skip_depth += 1
        elif tag == "article":
            self._article_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "h1" and self._article_depth:
            self._in_h1 = True
        elif tag == "li" and self._article_depth:
            self._li_buffer = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            if self._skip_depth:
                self._skip_depth -= 1
        elif tag == "article":
            if self._article_depth:
                self._article_depth -= 1
        elif tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        elif tag == "li" and self._li_buffer is not None:
            self.list_items.append(_normalize("".join(self._li_buffer)))
            self._li_buffer = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        if not self._article_depth:
            return
        self.text_parts.append(data)
        if self._in_h1:
            self.h1_parts.append(data)
        if self._li_buffer is not None:
            self._li_buffer.append(data)


def _extract_document(source_html: str) -> tuple[_ArticleTextParser, str, str]:
    parser = _ArticleTextParser()
    parser.feed(source_html)
    parser.close()
    title = _normalize(" ".join(parser.title_parts)) or _normalize(
        " ".join(parser.h1_parts)
    )
    text = _normalize(" ".join(parser.text_parts))
    return parser, title, text


def _period_to_iso(match: re.Match) -> tuple[str, str]:
    month_name = match.group("month_name")
    if month_name is not None:
        month = _MONTH_NAMES[month_name.lower()]
        year = match.group("text_year")
        start_month = end_month = month
        start_year = end_year = year
    else:
        start_month = match.group("start_month") or match.group("end_month")
        start_year = match.group("start_year") or match.group("end_year")
        end_month = match.group("end_month")
        end_year = match.group("end_year")
    start_day = int(match.group("start_day"))
    end_day = int(match.group("end_day"))
    start = date(int(start_year), int(start_month), start_day)
    end = date(int(end_year), int(end_month), end_day)
    if start > end:
        raise ValueError("período de inscrições invertido")
    return start.isoformat(), end.isoformat()


def _find_registration_period(text: str) -> re.Match | None:
    """Localiza o período somente em frase que trata de inscrições.

    Datas em rodapé, cookies, scripts, links ou metadados não bastam: a frase
    precisa conter ``inscri`` e o próprio período.
    """
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        if "inscri" in sentence.lower():
            match = _PERIOD_RE.search(sentence)
            if match is not None:
                return match
    return None


def _extract_roles(list_items: list[str]) -> list[tuple[str, int]]:
    roles: list[tuple[str, int]] = []
    seen: set[str] = set()
    for raw in list_items:
        match = _ROLE_RE.match(raw)
        if match is None:
            if re.search(r"\d", raw):
                raise ValueError(f"item de lista numerado fora do padrão oficial: {raw}")
            continue
        role = _normalize(match.group("role"))
        if role in seen:
            raise ValueError(f"cargo duplicado na página: {role}")
        seen.add(role)
        roles.append((role, int(match.group("count"))))
    return roles


def _extract_text_field(pattern: re.Pattern, text: str) -> str | None:
    match = pattern.search(text)
    if match is None:
        return None
    value = match.group(1).strip(" .;,")
    return value or None


def collect(source_html: str, verified_at: str) -> list[dict]:
    """Extrai um registro por cargo do HTML oficial da fonte.

    Retorna lista de dicts conforme o contrato v1. Falha com ``ValueError``
    em documento vazio, incompleto ou alterado, sem devolver registros
    parciais.
    """
    if not isinstance(source_html, str) or not source_html.strip():
        raise ValueError("HTML da fonte ausente ou vazio")

    parser, title, text = _extract_document(source_html)
    if not title:
        raise ValueError("título do artigo não encontrado")

    id_match = _COMPETITION_ID_RE.search(text)
    if id_match is None:
        raise ValueError("identificador do concurso não encontrado")
    competition_id = id_match.group(1)

    total_match = _TOTAL_RE.search(title)
    if total_match is None:
        raise ValueError("total de vagas não declarado no título")
    declared_total = int(total_match.group(1))

    period_match = _find_registration_period(text)
    if period_match is None:
        raise ValueError("período de inscrições não encontrado")
    registration_start, registration_end = _period_to_iso(period_match)

    roles = _extract_roles(parser.list_items)
    if not roles:
        raise ValueError("lista de cargos não encontrada")
    declared_sum = sum(count for _, count in roles)
    if declared_sum != declared_total:
        raise ValueError(
            "soma de vagas dos cargos difere do total declarado na página"
        )

    # O contrato v1 representa um cargo, não o total do certame. Totais
    # positivos sem distribuição publicada não podem ser repetidos por cargo.
    # Uma declaração inequívoca de inexistência de reserva vale para todos.
    reserve_vacancies = 0 if _NO_RESERVE_RE.search(text) else None
    indigenous_vacancies = None
    exam_location = _extract_text_field(_EXAM_LOCATION_RE, text)
    work_location = _extract_text_field(_WORK_LOCATION_RE, text)

    verified_date = verified_at[:10]
    if _REALIZED_RE.search(text) and registration_end < verified_date:
        registration_status: str | None = _REGISTRATION_CLOSED_STATUS
    else:
        registration_status = None

    records = []
    for role, immediate_vacancies in roles:
        records.append(
            {
                "competition_id": competition_id,
                "competition": COMPETITION,
                "agency": AGENCY,
                "role": role,
                "education": None,
                "immediate_vacancies": immediate_vacancies,
                "reserve_vacancies": reserve_vacancies,
                "indigenous_vacancies": indigenous_vacancies,
                "registration_start": registration_start,
                "registration_end": registration_end,
                "registration_status": registration_status,
                "exam_date": None,
                "exam_location": exam_location,
                "work_location": work_location,
                "source_name": SOURCE_NAME,
                "source_url": SOURCE_URL,
                "evidence_url": SOURCE_URL,
                "verified_at": verified_at,
            }
        )
    return records


def fetch_official() -> str:
    """Baixa o HTML da URL oficial fixa, com HTTPS, timeout e limite.

    Nunca finge sucesso: erros de rede ou HTTP propagam e resposta acima do
    limite levanta ``ValueError``.
    """
    parsed = urlparse(SOURCE_URL)
    if parsed.scheme != "https" or parsed.hostname != _ALLOWED_HOST:
        raise ValueError("URL oficial inválida: exigido HTTPS no host fixo")

    request = Request(SOURCE_URL, headers={"User-Agent": "radar-de-concursos/0.1"})
    with urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
        final_url = urlparse(response.geturl())
        if (
            final_url.scheme != "https"
            or final_url.hostname != _ALLOWED_HOST
            or final_url.path != parsed.path
        ):
            raise ValueError("redirecionamento para fora da fonte oficial")
        body = response.read(_MAX_BYTES + 1)
        if len(body) > _MAX_BYTES:
            raise ValueError("resposta da fonte excede o limite de bytes")
        charset = response.headers.get_content_charset() or "utf-8"

    try:
        return body.decode(charset)
    except (LookupError, UnicodeDecodeError):
        return body.decode("utf-8", errors="replace")
