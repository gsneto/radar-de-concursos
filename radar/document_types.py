"""Classificação documental compartilhada pelas fontes oficiais.

O bucket de armazenamento (`kind`) permanece grosseiro — ``edital``/``retificacao``/
``outro`` — por compatibilidade. O **tipo fino** (`tipo_documental`) distingue edital de
abertura, edital retificado, retificação, anexo, cronograma, comunicado, resultado,
convocação, homologação, gabarito e prova. Nunca trata todo PDF como edital.
"""

from __future__ import annotations

import re

# Ordem importa: o primeiro marcador encontrado define o tipo fino.
_FINE_TYPES = (
    ("gabarito", ("gabarito",)),
    ("prova", ("provas aplicadas", "prova aplicada", "caderno de prova", "versão padrão")),
    ("homologacao", ("homologa",)),
    ("convocacao", ("convoca",)),
    ("resultado", ("resultado",)),
    ("cronograma", ("cronograma",)),
    ("anexo", ("anexo",)),
    ("comunicado", ("comunicado", "aviso", "informe", "nota de esclarecimento")),
)


def classify(title: str) -> str:
    """Tipo documental fino pelo título. Edital puro é ``edital_abertura``."""
    if not isinstance(title, str):
        return "outro"
    norm = " ".join(title.lower().split())
    if not norm:
        return "outro"
    if "errata" in norm:
        return "retificacao"
    # Retificação quando o título começa pelo marcador ("1ª Retificação", "Retificação do Edital").
    if re.match(r"^\s*\d*\s*[ªºo]?\s*retifica", norm):
        return "retificacao"
    is_edital = "edital" in norm
    if is_edital and any(marker in norm for marker in
                         ("atualizado", "consolidado", "alterado", "retificado")):
        return "edital_retificado"
    if is_edital and "retifica" in norm:
        return "retificacao"  # ex.: "Edital nº 6 (Retificação)" é a retificação
    # Tipos finos explícitos antes da heurística ampla de "retifica" (evita que um
    # "Cronograma ... conforme retificações" vire retificação).
    for fine, markers in _FINE_TYPES:
        if any(marker in norm for marker in markers):
            return fine
    if "retifica" in norm:
        return "retificacao"
    if is_edital:
        return "edital_abertura"
    return "outro"


# --- Classificação por fonte (Fase 26) ----------------------------------------
# O bucket `kind` continua grosseiro. O tipo fino ganha valores de **página**, para separar
# descoberta (agregador) de fonte oficial sem promover nada a edital.
AGGREGATOR_HOSTS = ("pciconcursos.com.br", "pciconcursos.com")
BANCA_HOSTS = (
    "fgv.br", "quadrix.org.br", "cebraspe.org.br", "cebraspe.org", "ibfc.org.br",
    "aocp.com.br", "institutoaocp.org.br", "fcc.org.br", "conhecimento.fgv.br",
    "selecao.net.br", "ibfc.org",
)
GOV_HOST_SUFFIXES = (".gov.br", ".gov", ".leg.br", ".jus.br", ".mp.br", ".def.br")

PAGE_TYPES = ("pagina_agregador", "pagina_banca", "pagina_orgao")


def host_of(url: str | None) -> str:
    if not isinstance(url, str) or "//" not in url:
        return ""
    return url.split("//", 1)[1].split("/", 1)[0].lower().split(":")[0]


def _host_matches(host: str, known: str) -> bool:
    return bool(host) and (host == known or host.endswith("." + known))


def source_class(url: str | None) -> str | None:
    """Tipo de página pela **fonte** (nunca pelo título): agregador, banca ou órgão."""
    host = host_of(url)
    if not host:
        return None
    if any(_host_matches(host, known) for known in AGGREGATOR_HOSTS):
        return "pagina_agregador"
    if any(_host_matches(host, known) for known in BANCA_HOSTS):
        return "pagina_banca"
    if host.endswith(GOV_HOST_SUFFIXES):
        return "pagina_orgao"
    return None


def classify_document(title: str, url: str | None = None) -> str:
    """Tipo fino combinando título e fonte, de forma conservadora.

    O título manda: se ele identifica um ato (edital, retificação, resultado...), esse é o
    tipo. Só quando o título é inconclusivo a fonte classifica a **página**. Nunca promove
    página de agregador a edital.
    """
    source = source_class(url)
    if source == "pagina_agregador":
        # Página de agregador NUNCA é prova oficial, mesmo que o título diga "Retificação":
        # o ato oficial é o documento da banca/órgão, não a notícia que o anuncia.
        return source
    by_title = classify(title)
    if by_title != "outro":
        return by_title
    return source or "outro"


def kind_for(document_type: str) -> str:
    """Bucket de armazenamento (`kind`) a partir do tipo fino."""
    if document_type in ("edital_abertura", "edital_retificado"):
        return "edital"
    if document_type == "retificacao":
        return "retificacao"
    return "outro"
